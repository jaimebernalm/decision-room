"""Phase-one guarantees: actual provider schema, private requests and scoped errors.

Only MockTransport is used; these tests must never invoke a live model.
"""
import base64
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from decision_room.agent.model import ModelClient, ModelSettings, ModelRequestUncertain
from decision_room.agent.persistence import _model_call
from decision_room.agent.context import fingerprint
from decision_room.agent.review_contract import ReportDraft, checks
from decision_room.chart_evidence import resolve_chart
from decision_room.execution_contract import validate_payload
from decision_room.database import connect
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_agenda import ResearchBudgetReached
from test_chart_layers import layered
import test_agent as agent_tests


class LayerProducerTests(unittest.TestCase):
    def validator(self, data, method='generate_analyst_review'):
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            getattr(client, method)({'observations': data['observations']})
        schema = client._wire_schema(request.call_args.args[3])
        return Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/Chart'})

    def test_real_producer_accepts_runtime_layers_and_all_surfaces_keep_values(self):
        from decision_room.web.dashboard import presentation
        from decision_room.client_report import render_client
        from decision_room.report_pdf import render_pdf
        data = layered()
        chart = ReportDraft.model_validate(data['report']).model_dump()['charts'][0]
        for role in ('generate_analyst_review', 'generate_reviewer'):
            self.validator(data, role).validate(chart)
        self.assertTrue(all(c['passed'] for c in checks(data['report'], data['observations'])))
        self.assertEqual(len(resolve_chart(chart, data['observations'])[1]), 18)
        self.assertEqual(len(presentation(data)['charts'][0]['points']), 18)
        self.assertIn('Media móvil 3 días', render_client(data, 'test-export'))
        self.assertTrue(render_pdf(presentation(data)).startswith(b'%PDF'))

    def test_layer_branch_excludes_mixed_units_grains_stale_or_impossible_forms(self):
        data = layered()
        saved = data['observations'][-1]['result']['series']
        saved['money'] = {**deepcopy(saved['raw']), 'unit': 'EUR'}
        saved['monthly'] = {**deepcopy(saved['raw']), 'grain': 'month',
                            'points': [{'label': '2026-01', 'value': '1'}, {'label': '2026-02', 'value': '2'}]}
        validator = self.validator(data)
        chart = ReportDraft.model_validate(data['report']).model_dump()['charts'][0]
        for fault in ('bar', 'unit', 'money', 'monthly', 'unknown', 'points', 'series', 'encoding'):
            bad = deepcopy(chart)
            if fault == 'bar': bad['kind'] = 'bar'
            elif fault == 'unit': bad['unit'] = 'EUR'
            elif fault in ('money', 'monthly', 'unknown'): bad['layers'][1]['series']['series'] = fault
            elif fault == 'points': bad['points'] = [{'label': 'x', 'value': {'execution_id': 'calculation-a', 'metric': 'first'}}]
            elif fault == 'series': bad['series'] = bad['layers'][0]['series']
            else: bad['encoding'] = {}
            with self.subTest(fault=fault): self.assertFalse(validator.is_valid(bad))
        data['observations'][-1]['current'] = False
        self.assertFalse(self.validator(data).is_valid(chart))

    def test_730_combined_layer_points_remain_available_beyond_single_series_limit(self):
        from datetime import date, timedelta
        from decision_room.series import validate_series
        data = layered()
        saved = data['observations'][-1]['result']['series']
        points = [dict(label=(date(2025, 1, 1) + timedelta(days=i)).isoformat(), value='10') for i in range(366)]
        saved['raw']['points'] = points
        saved['mean']['points'] = deepcopy(points[2:])
        validate_series(saved, {'sales': {}})
        chart = ReportDraft.model_validate(data['report']).model_dump()['charts'][0]
        for role in ('generate_analyst_review', 'generate_reviewer'):
            self.validator(data, role).validate(chart)
        self.assertEqual(len(resolve_chart(chart, data['observations'])[1]), 730)
        self.assertTrue(all(c['passed'] for c in checks(data['report'], data['observations'])))

    def test_single_point_layer_is_not_lost_by_single_series_chart_limits(self):
        data = layered(); data['observations'][-1]['result']['series']['mean']['points'] = [
            data['observations'][-1]['result']['series']['mean']['points'][-1]]
        chart = ReportDraft.model_validate(data['report']).model_dump()['charts'][0]
        self.validator(data).validate(chart)
        # This tests schema expressivity only; derivation truth remains runtime's job.


class ScopedErrorsTests(unittest.TestCase):
    def test_artifact_invalid_name_extension_and_duplicate_are_distinct(self):
        def payload(names):
            return json.dumps(dict(protocol=1, status='failed', exit_code=1,
                logs=dict(stdout='', stderr='', stdout_truncated=False, stderr_truncated=False),
                files=[{'name': n, 'base64': base64.b64encode(b'x').decode()} for n in names]))
        for names, code in [(['../out.csv'], 'artifact_invalid_name'), (['report.html'], 'artifact_unsupported_type'),
                            (['a.csv', 'a.csv'], 'artifact_duplicate_name')]:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                validate_payload(payload(names), {})
        self.assertEqual(validate_payload(payload(['a.csv']), {})[0], 'failed')

    def test_worker_limit_is_not_reported_as_global(self):
        action = dict(action='execute', investigation_key='q', code='print(1)', table_ids=['t'],
                      metric_keys=[], summary='Compute', followups=[], assignments=[], synthesis=None)
        plan = dict(answers=[], proposal={'questions': [], 'investigations': [dict(key='q', status='ready', table_ids=['t'], depends_on=[])]})
        opts = dict(max_executions=1, max_attempts_per_investigation=6, worker_assignment={'investigation_key': 'q'})
        with self.assertRaisesRegex(ResearchBudgetReached, 'worker assignment'):
            validate_research_action(action, plan, [{'investigation_key': 'q', 'status': 'failed'}], [], opts)
        attempts = [{**action, 'status': 'failed'}]
        with self.assertRaisesRegex(ValueError, 'investigation q .*not the global budget'):
            validate_research_action(action, plan, attempts, [], {**opts, 'max_executions': 10, 'max_attempts_per_investigation': 1})
        opts.pop('worker_assignment')
        with self.assertRaisesRegex(ResearchBudgetReached, 'research run'):
            validate_research_action(action, plan, [{'investigation_key': 'q', 'status': 'failed'}], [], opts)


class EffectiveRequestTests(unittest.TestCase):
    setUpClass = classmethod(agent_tests.AgentTests.setUpClass.__func__)
    tearDownClass = classmethod(agent_tests.AgentTests.tearDownClass.__func__)
    setUp = agent_tests.AgentTests.setUp
    start = agent_tests.AgentTests.start

    def test_exact_payload_correction_and_private_headers_survive_replay(self):
        run = self.start()
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
        settings = ModelSettings('gpt-6-luna', protocol='openai', base_url='https://api.openai.com/v1',
                                 reasoning='low', response_language='en')
        context = {'owner_context': 'Private synthetic test input', 'business_context': {'available': True}}
        with connect(self.config) as db:
            for correction in (None, 'Choose a supported series reference'):
                client = httpx.Client(transport=httpx.MockTransport(handler))
                with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-header-secret'}), patch('decision_room.agent.model.httpx.Client', return_value=client):
                    _model_call(db, run['id'], ModelClient(settings), context, correction, False, scope='effective-test')
                row = db.execute("SELECT * FROM agent_calls WHERE session_id=%s AND scope='effective-test' ORDER BY created_at DESC LIMIT 1", (run['id'],)).fetchone()
                record = row['effective_request']
                self.assertEqual(record['payload'], sent[-1])
                self.assertEqual(record['correction'], correction)
                self.assertIn('Application response language: English', record['payload']['messages'][0]['content'])
                self.assertIn('retrieve', json.dumps(record['payload']['response_format']))
                self.assertEqual(row['request_sha256'], fingerprint(record))
                self.assertNotIn('test-header-secret', json.dumps(record))
                if correction: self.assertIn(correction, record['payload']['messages'][-1]['content'])
                with patch('decision_room.agent.model.httpx.Client') as network:
                    _model_call(db, run['id'], ModelClient(settings), context, correction, False, scope='effective-test')
                    network.assert_not_called()
        self.assertEqual(len(sent), 2)

    def test_model_call_budget_identifies_phase_and_scope_without_network(self):
        run = self.start()
        with connect(self.config) as db, patch('decision_room.agent.model.httpx.Client') as network:
            with self.assertRaisesRegex(ValueError, "phase=research, scope='worker-a' "):
                _model_call(db, run['id'], ModelClient(ModelSettings('test')), {}, None, False,
                            phase='research', scope='worker-a', max_calls=0)
            network.assert_not_called()

    def test_request_is_saved_before_uncertain_transport_failure(self):
        run = self.start()
        def handler(request): raise httpx.ReadTimeout('simulated lost response')
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with connect(self.config) as db, patch('decision_room.agent.model.httpx.Client', return_value=client):
            with self.assertRaises(ModelRequestUncertain):
                _model_call(db, run['id'], ModelClient(ModelSettings('test', protocol='chat_completions')),
                            {'owner_context': 'uncertain'}, None, False, scope='uncertain-payload')
            row = db.execute("SELECT * FROM agent_calls WHERE session_id=%s AND scope='uncertain-payload'", (run['id'],)).fetchone()
            self.assertEqual(row['status'], 'running')
            self.assertIsNotNone(row['effective_request']['payload']['response_format']['json_schema']['schema'])


class DeliveryStateTests(unittest.TestCase):
    def test_only_current_controller_approval_enables_export(self):
        from decision_room.agent.review_context import delivery_state
        for status in ('stale', 'held', 'rejected', 'withdrawn', 'approved'):
            self.assertEqual(delivery_state(status)['report_exports'], 'unavailable')
        self.assertEqual(delivery_state('running')['report_exports'], 'pending_approval')
        self.assertEqual(delivery_state('approved', publishable=True)['report_exports'], 'available_on_request')


class DiscoveryRequestTests(unittest.TestCase):
    setUpClass = classmethod(agent_tests.AgentTests.setUpClass.__func__)
    tearDownClass = classmethod(agent_tests.AgentTests.tearDownClass.__func__)
    setUp = agent_tests.AgentTests.setUp
    def test_discovery_records_effective_schema_before_applying_proposal(self):
        from decision_room.data_knowledge.discovery import discover
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps(dict(tables=[], relations=[], limitations=[]))}}]})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch('decision_room.agent.model.httpx.Client', return_value=client):
            discover(self.config, self.business, self.analysis, ModelClient(ModelSettings('test', protocol='chat_completions')))
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM data_model_discoveries WHERE business_id=%s', (self.business,)).fetchone()
        self.assertEqual(row['effective_request']['payload'], sent[0])
        self.assertEqual(row['request_sha256'], fingerprint(row['effective_request']))


import test_conversations as conversation_tests


class ChatRequestTests(unittest.TestCase):
    setUpClass = classmethod(conversation_tests.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(conversation_tests.ConversationTests.tearDownClass.__func__)
    setUp = conversation_tests.ConversationTests.setUp
    chat = conversation_tests.ConversationTests.chat
    send = conversation_tests.ConversationTests.send

    def test_answer_and_review_store_their_own_effective_requests(self):
        class Model(conversation_tests.ChatModel):
            def generate_chat(inner, context, correction=None):
                return ModelClient(ModelSettings('test', protocol='chat_completions')).generate_chat(context, correction)
            def review_chat_answer(inner, context):
                return ModelClient(ModelSettings('test', protocol='chat_completions')).review_chat_answer(context)
        self.chats.ws.model_factory = Model
        sent = []
        def handler(request):
            payload = json.loads(request.content); sent.append(payload)
            fields = payload['response_format']['json_schema']['schema']['properties']
            output = dict(approved=True, issues=[]) if 'approved' in fields else conversation_tests.action('answer', text='Hola.', sources=[])
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]})
        factory = httpx.Client
        with patch('decision_room.agent.model.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(handler))):
            turn = self.send(self.chat(), 'Hola')
        with connect(self.config) as db:
            for table, payload in zip(('chat_calls', 'chat_answer_reviews'), sent):
                row = db.execute(f'SELECT * FROM {table} WHERE turn_id=%s', (turn['id'],)).fetchone()
                self.assertEqual(row['effective_request']['payload'], payload)
                self.assertEqual(row['request_sha256'], fingerprint(row['effective_request']))
        self.assertEqual(len(sent), 2)


import test_memory as memory_tests


class MemoryRequestTests(unittest.TestCase):
    setUpClass = classmethod(memory_tests.MemoryTests.setUpClass.__func__)
    tearDownClass = classmethod(memory_tests.MemoryTests.tearDownClass.__func__)
    setUp = memory_tests.MemoryTests.setUp
    capture = memory_tests.MemoryTests.capture
    source = memory_tests.MemoryTests.source

    def test_memory_correction_retains_both_effective_requests(self):
        from decision_room.memory import extraction
        source = self.capture('Cerramos los domingos.', allow_business=True)
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            candidate = memory_tests.candidate(scope='source', scope_id=None) if len(sent) == 1 else memory_tests.candidate()
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
                'content': json.dumps({'candidates': [candidate]})}}]})
        factory = httpx.Client
        with patch('decision_room.agent.model.httpx.Client', side_effect=lambda **kw: factory(transport=httpx.MockTransport(handler))):
            extraction.process(self.config, self.b, source['id'], ModelClient(ModelSettings('test', protocol='chat_completions')))
        self.assertEqual(self.source(source)['status'], 'applied')
        with connect(self.config) as db:
            rows = db.execute('SELECT * FROM memory_calls WHERE source_id=%s ORDER BY created_at', (source['id'],)).fetchall()
        self.assertEqual(len(rows), 2)
        for row, payload in zip(rows, sent):
            self.assertEqual(row['effective_request']['payload'], payload)
            self.assertEqual(row['request_sha256'], fingerprint(row['effective_request']))
        self.assertIsNone(rows[0]['effective_request']['correction'])
        self.assertTrue(rows[1]['effective_request']['correction'])


if __name__ == '__main__': unittest.main()
