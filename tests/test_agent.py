"""Real PostgreSQL/LangGraph recovery; scripted model is NOT a quality evaluation."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

import httpx

from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.service import create_business, import_batch
from decision_room.agent import service
from decision_room.agent.context import model_context, snapshot
from decision_room.agent.contracts import validate_action
from decision_room.agent.model import ModelAPIError, ModelClient, ModelSettings
from decision_room.agent.persistence import session_lock


class ScriptedModel:
    identity = {'model': 'scripted-test-only'}

    def __init__(self):
        self.calls = 0

    def generate(self, context, correction=None):
        self.calls += 1
        if not context['profiles']:
            return {'action': 'inspect', 'table_ids': [context['catalog'][0]['id']], 'proposal': None}, {}
        table = context['profiles'][0]['id']
        refs = [{'kind': 'column', 'id': table, 'column': 'amount'}]
        answers = context['answers']
        definition = {'aspect': 'meaning', 'statement': 'Importe pendiente de definir.',
                      'status': 'unresolved', 'references': refs}
        questions = [{'key': 'amount_basis', 'text': '¿Precio unitario o total de fila?',
                      'reason': 'Cambia el total de ventas.', 'references': refs,
                      'options': ['Unitario', 'Total de fila']}]
        if answers:
            questions = []
            if answers[0]['disposition'] == 'answered':
                definition.update(statement=answers[0]['text'], status='confirmed',
                                  references=[{'kind': 'answer', 'id': answers[0]['id'], 'column': ''}])
        investigation = {'key': 'sales', 'question': '¿Cuánto se vendió?', 'business_value': 'Entender ventas.',
                         'table_ids': [table], 'definitions_needed': ['Significado del importe'],
                         'depends_on': ['amount_basis'], 'proposed_operation': 'Sumar tras resolver la definición.',
                         'validation_needed': ['Comprobar tipos, alcance y definición.'], 'status': 'ready'}
        independent = {**investigation, 'key': 'units', 'question': '¿Cuántas unidades?',
                       'definitions_needed': [], 'depends_on': [], 'proposed_operation': 'Sumar quantity.'}
        return {'action': 'propose', 'table_ids': [], 'proposal': {
            'interpretations': [definition], 'investigations': [investigation, independent],
            'questions': questions, 'limitations': ['Propuesta sin cálculos.']}}, {'total_tokens': 10}


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_agent_test_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-agent-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Agent test')['id']
        file = self.root / 'sales.csv'
        file.write_text('quantity,amount\n2,10\n3,20\n')
        self.analysis = import_batch(self.config, self.business, [file])['analysis']['id']
        self.model = ScriptedModel()

    def start(self, **kwargs):
        return service.start(self.config, self.business, self.analysis, owner_context='Quantities are units.',
                             request_key='test', model=kwargs.pop('model', self.model), **kwargs)

    def answer(self, result, **kwargs):
        return service.answer(self.config, self.business, result['id'], question_id=result['questions'][0]['id'],
                              request_key='response', model=self.model, **kwargs)

    def test_wait_answer_replan_and_idempotency(self):
        first = self.start()
        self.assertEqual(first['status'], 'waiting')
        self.assertEqual(first['revisions'][0]['proposal']['investigations'][0]['status'], 'blocked')
        self.assertEqual(self.start()['id'], first['id'])
        self.assertEqual(self.model.calls, 1)
        result = self.answer(first, text='Amount is the whole row total.')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(result['revisions']), 2)
        self.assertFalse(result['questions'])
        self.assertEqual(result['revisions'][-1]['proposal']['interpretations'][0]['status'], 'confirmed')
        again = self.answer(first, text='Amount is the whole row total.')
        self.assertEqual(len(again['answers']), 1)
        self.assertEqual(self.model.calls, 2)
        with self.assertRaisesRegex(ValueError, 'already answered differently'):
            self.answer(first, text='Actually unit price.')
        with self.assertRaisesRegex(ValueError, 'Request key already used'):
            service.start(self.config, self.business, self.analysis, owner_context='Different', request_key='test', model=self.model)

    def test_unknown_or_declined_preserves_independent_work(self):
        for disposition in ('unknown', 'declined'):
            first = service.start(self.config, self.business, self.analysis, owner_context='',
                                  request_key=disposition, model=self.model)
            result = self.answer(first, disposition=disposition)
            self.assertEqual(result['status'], 'limited')
            self.assertFalse(result['questions'])
            work = result['revisions'][-1]['proposal']['investigations']
            self.assertEqual([i['status'] for i in work], ['blocked', 'ready'])
            self.assertEqual(result['revisions'][-1]['proposal']['interpretations'][0]['status'], 'unresolved')

    def test_answer_saved_before_process_interruption(self):
        first = self.start()
        with patch.object(service, '_drive', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.answer(first, text='Total of the row.')
        self.assertEqual(len(service.show(self.config, self.business, first['id'])['answers']), 1)
        result = service.resume(self.config, self.business, first['id'], model=ScriptedModel())
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(result['answers']), 1)
        self.assertEqual(len(result['model_calls']), 2)

    def test_restart_in_separate_python_processes(self):
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn,
               'DECISION_ROOM_STORAGE': str(self.config.storage)}
        preamble = """import sys,json
sys.path.insert(0,'tests')
from test_agent import ScriptedModel
from decision_room.agent import service
from decision_room.config import Config
"""
        first_code = preamble + f"r=service.start(Config.load(),{str(self.business)!r},{str(self.analysis)!r},owner_context='',request_key='process',model=ScriptedModel())\nprint(json.dumps(r,default=str))"
        first = json.loads(subprocess.check_output([sys.executable, '-c', first_code], env=env, text=True))
        self.assertEqual(first['status'], 'waiting')
        second_code = preamble + f"r=service.answer(Config.load(),{str(self.business)!r},{first['id']!r},question_id={first['questions'][0]['id']!r},text='Unit price.',request_key='process-answer',model=ScriptedModel())\nprint(json.dumps(r,default=str))"
        second = json.loads(subprocess.check_output([sys.executable, '-c', second_code], env=env, text=True))
        self.assertEqual(second['status'], 'ready')
        self.assertEqual(len(second['model_calls']), 2)
        self.assertFalse(second['questions'])

    def test_business_scope_and_concurrent_session_lock(self):
        first = self.start()
        other = create_business(self.config, 'Other')['id']
        for method in (service.show, service.resume):
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                method(self.config, other, first['id'])
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            service.answer(self.config, other, first['id'], question_id=first['questions'][0]['id'],
                           text='Unit price', request_key='bad', model=self.model)
        with session_lock(self.config, self.business, first['id']):
            with self.assertRaisesRegex(ValueError, 'already running'):
                service.resume(self.config, self.business, first['id'], model=self.model)

    def test_invalid_model_output_and_network_failure_are_recoverable(self):
        with patch.object(self.model, 'generate', return_value=({'action': 'invented'}, {})):
            with self.assertRaisesRegex(ValueError, 'failed validation twice'):
                self.start()
        with connect(self.config) as db:
            session = db.execute('SELECT id,status FROM agent_sessions WHERE business_id=%s', (self.business,)).fetchone()
        report = service.show(self.config, self.business, session['id'])
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(report['revisions'])
        self.assertEqual(len(report['model_calls']), 2)
        # Cached invalid outputs deliberately reproduce the failure, preventing infinite paid retries.
        with self.assertRaisesRegex(ValueError, 'failed validation twice'):
            service.resume(self.config, self.business, session['id'], model=self.model)
        with patch.object(self.model, 'generate', side_effect=ValueError('Connection unavailable')):
            with self.assertRaisesRegex(ValueError, 'Connection unavailable'):
                service.start(self.config, self.business, self.analysis, owner_context='', request_key='network', model=self.model)
        with connect(self.config) as db:
            sid = db.execute("SELECT id FROM agent_sessions WHERE business_id=%s AND request_key='network'", (self.business,)).fetchone()['id']
        self.assertEqual(service.resume(self.config, self.business, sid, model=self.model)['status'], 'waiting')

    def test_changed_sources_rejected_before_model_call(self):
        first = self.start()
        with connect(self.config) as db:
            db.execute('UPDATE prepared_tables SET row_count=row_count+1 WHERE analysis_id=%s', (self.analysis,))
        with self.assertRaisesRegex(ValueError, 'Source metadata changed'):
            service.resume(self.config, self.business, first['id'], model=self.model)
        self.assertEqual(self.model.calls, 1)

    def test_context_excludes_internal_paths_and_evaluation_files(self):
        source = snapshot(self.config, self.business, self.analysis, 'Business context')
        ids = [t['id'] for t in source['tables']]
        context = model_context(source, ids, [], None)
        text = json.dumps(context)
        for forbidden in ('parquet_key', 'original_key', 'evaluation/', 'expected.json', str(self.root), self.config.dsn):
            self.assertNotIn(forbidden, text)
        action, _ = self.model.generate(context)
        bad = copy.deepcopy(action)
        bad['proposal']['interpretations'][0]['references'][0]['column'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'Unknown column'):
            validate_action(bad, source, ids, [])
        bad = copy.deepcopy(action)
        bad['proposal']['interpretations'][0]['status'] = 'confirmed'
        with self.assertRaisesRegex(ValueError, 'require owner'):
            validate_action(bad, source, ids, [])
        with self.assertRaisesRegex(ValueError, 'Do not repeat'):
            validate_action(action, source, ids, [{'id': 'x', 'key': 'amount_basis', 'disposition': 'unknown'}])

    def test_model_endpoint_configuration(self):
        for url in ('http://remote.test/v1', 'https://key@provider.test/v1', 'https://provider.test/v1?key=secret'):
            with self.assertRaises(ValueError):
                ModelSettings('example-model', base_url=url)
        self.assertEqual(ModelSettings('example-model').base_url, 'http://127.0.0.1:1234/api/v1')

    def test_uncertain_request_requires_explicit_retry_and_honors_budget(self):
        with patch.object(self.model, 'generate', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.start()
        with connect(self.config) as db:
            session_id = db.execute('SELECT id FROM agent_sessions WHERE business_id=%s', (self.business,)).fetchone()['id']
        with self.assertRaisesRegex(ValueError, 'retry-model'):
            service.resume(self.config, self.business, session_id, model=self.model)
        report = service.resume(self.config, self.business, session_id, model=self.model, retry_uncertain=True)
        self.assertEqual(report['status'], 'waiting')
        self.assertEqual(report['model_calls'][0]['status'], 'interrupted')
        with connect(self.config) as db:
            for _ in range(18):
                db.execute("INSERT INTO agent_calls(id,session_id,call_key,status,prompt_version) VALUES (%s,%s,'budget','failed','test')",
                           (uuid4(), session_id))
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.answer(report, text='Unit price.')
        self.assertEqual(len(service.show(self.config, self.business, session_id)['answers']), 1)

    def test_native_and_compatible_transport_contracts(self):
        source = snapshot(self.config, self.business, self.analysis, '')
        ids = [t['id'] for t in source['tables']]
        context = model_context(source, ids, [], None)
        output, _ = self.model.generate(context)
        for protocol in ('lmstudio', 'lmstudio_structured', 'chat_completions'):
            captured = []
            def handler(request):
                captured.append(json.loads(request.content))
                if protocol == 'lmstudio':
                    return httpx.Response(200, json={'output': [{'type': 'message', 'content': json.dumps(output)}],
                                                    'stats': {'total_output_tokens': 100}})
                return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}],
                                                'usage': {'total_tokens': 100}})
            client = httpx.Client(transport=httpx.MockTransport(handler))
            with patch('decision_room.agent.model.httpx.Client', return_value=client):
                actual, usage = ModelClient(ModelSettings('test', protocol=protocol)).generate(context)
            self.assertEqual(actual, output)
            self.assertTrue(usage)
            if protocol == 'lmstudio':
                self.assertFalse(captured[0]['store'])
                self.assertEqual(captured[0]['reasoning'], 'off')
            else:
                self.assertEqual(captured[0]['response_format']['type'], 'json_schema')
                if protocol == 'lmstudio_structured':
                    self.assertEqual(captured[0]['reasoning_effort'], 'none')
                else:
                    self.assertNotIn('reasoning_effort', captured[0])
        for status in (400, 401, 503):
            client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='do not echo server secrets')))
            with patch('decision_room.agent.model.httpx.Client', return_value=client):
                with self.assertRaisesRegex(ModelAPIError, f'HTTP {status}') as error:
                    ModelClient(ModelSettings('test')).generate(context)
                self.assertEqual(error.exception.status_code, status)
                self.assertNotIn('server secrets', str(error.exception))
        self.assertEqual(ModelClient._action('```json\n{"action":"finish"}\n```'), {'action': 'finish'})
        invalid = ModelClient._action('{"code": "unescaped\nnewline"}')
        self.assertIn('invalid_model_output', invalid)
        self.assertLessEqual(len(invalid['raw_message_excerpt']), 12000)

    def test_table_inspection_loop_and_uninspected_coverage(self):
        files = []
        for n in range(4):
            path = self.root / f'part-{n}.csv'
            path.write_text(f'quantity,amount\n{n + 1},10\n')
            files.append(path)
        analysis = import_batch(self.config, self.business, files)['analysis']['id']
        report = service.start(self.config, self.business, analysis, owner_context='', request_key='catalog', model=self.model)
        self.assertEqual(report['status'], 'waiting')
        self.assertEqual(self.model.calls, 2)
        self.assertEqual(len(report['revisions'][0]['inspected_table_ids']), 1)
        self.assertIn('3 table profiles remain uninspected', report['revisions'][0]['proposal']['limitations'][-1])
        source = snapshot(self.config, self.business, analysis, '')
        with self.assertRaisesRegex(ValueError, 'previously unseen'):
            validate_action({'action': 'inspect', 'table_ids': [str(uuid4())], 'proposal': None}, source, [], [])
        with self.assertRaisesRegex(ValueError, '200 KB'):
            model_context(source, [], [], {'oversized': 'x' * 200000})

    def test_unknown_dependency_cannot_disappear_from_same_investigation(self):
        first = self.start()
        generate = self.model.generate
        def drop_dependency(context, correction=None):
            output, usage = generate(context, correction)
            output['proposal']['investigations'][0]['depends_on'] = []
            return output, usage
        with patch.object(self.model, 'generate', side_effect=drop_dependency):
            result = self.answer(first, disposition='unknown')
        investigation = result['revisions'][-1]['proposal']['investigations'][0]
        self.assertEqual(investigation['depends_on'], ['amount_basis'])
        self.assertEqual(investigation['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
