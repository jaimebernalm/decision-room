"""Full private pipeline; simulated responder sees only compact HTTP messages.

These are contract/transport tests, not a model quality or cache-hit measurement.
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import httpx
import jsonschema
from decision_room.agent import research, review, service
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.review_contract import ReviewAction
from decision_room.database import connect
from test_research import ResearchModel
from test_review import action, assessed, draft
import test_sales_panorama_integration as panorama_tests


class ThreeQuestions(ResearchModel):
    def generate(self, context, correction=None):
        result, usage = super().generate(context, correction)
        task = result['proposal']['investigations'][0]
        result['proposal']['investigations'] = [{**deepcopy(task), 'key': key}
                                                for key in ('sales', 'units', 'channels')]
        return result, usage

    def generate_research(self, context, correction=None):
        closed = {f['investigation_key'] for f in context['findings']}
        pending = [i for i in context['plan']['investigations'] if i['key'] not in closed]
        if not pending:
            return super().generate_research(context, correction)
        scoped = deepcopy(context)
        scoped['plan']['investigations'] = pending[:1]
        scoped['observations'] = [o for o in context['observations']
                                  if o.get('investigation_key') == pending[0]['key']]
        return super().generate_research(scoped, correction)


class WireRoles:
    # Use the fixture's frozen identity; serialization still runs through ModelClient.
    identity = ResearchModel.identity

    def __init__(self):
        self.client = ModelClient(ModelSettings('gpt-6-luna', protocol='openai',
            base_url='https://api.openai.com/v1', tokens_per_minute=0))

    def generate_analyst_review(self, context, correction=None):
        return self.client.generate_analyst_review(context, correction)

    def generate_reviewer(self, context, correction=None):
        return self.client.generate_reviewer(context, correction)


def visible_context(payload):
    """No access to the original graph context, database, files or hidden evidence."""
    visible = {}
    for message in payload['messages'][1:]:
        content = message['content']
        text = content if isinstance(content, str) else ''.join(p['text'] for p in content)
        block = json.loads(text)  # A correction message makes this first-try test fail.
        visible.update(block.get('stable_review_context', block.get('review_evidence', block)))
    return visible


def response_from_wire(payload):
    context = visible_context(payload)
    if context['role'] == 'analyst':
        report = draft(context)
        report['question_coverage'] = [dict(investigation_key=key, status='answered',
            claim_keys=['sales'], explanation='Total registrado calculado para esta pregunta de prueba.')
            for key in context['required_coverage_keys']]
        claim = report['claims'][0]
        claim['focal_combinations'] = [dict(table_id=context['tables'][0]['id'], product=None, channel=None)]
        if context['citable_panorama_metrics']:
            claim['panorama_priority'] = dict(comparison={'basis':'panorama'},
                alternative='La cobertura de los registros requiere comprobación antes de interpretar diferencias.',
                why_first='El total describe el alcance disponible antes de asignar prioridades comerciales.',
                evidence=[context['citable_panorama_metrics'][0]])
        report['panorama_dispositions'] = {key:dict(disposition='priority', claim_key='sales',
            reason='Comprobar los registros disponibles antes de atribuir cambios a la demanda.')
            for key in context.get('panorama_obligations', {}).get('required_gap_keys', [])}
        response = action('submit', report=report)
    else:
        response = assessed(action('approve'), context)
    wire = ReviewAction.model_validate(response).model_dump()
    if wire['report'] is not None:
        decisions = wire['report']['panorama_dispositions']
        wire['report']['panorama_dispositions'] = [dict(signal_key=k, decision=v) for k,v in decisions.items()]
    if 'retrieval' in payload['response_format']['json_schema']['schema']['properties']:
        wire['retrieval'] = None
    jsonschema.validate(wire, payload['response_format']['json_schema']['schema'])
    return wire


class WireOnlyReviewTests(unittest.TestCase):
    setUpClass = classmethod(panorama_tests.PanoramaPersistenceTests.setUpClass.__func__)
    tearDownClass = classmethod(panorama_tests.PanoramaPersistenceTests.tearDownClass.__func__)
    setUp = panorama_tests.PanoramaPersistenceTests.setUp

    def test_first_submit_and_approval_with_and_without_panorama_use_only_wire_data(self):
        model = ThreeQuestions()
        parent = service.start(self.config, self.business, self.analysis,
            owner_context='Amount is unit price. Quantity is units.', request_key='plan', model=model)
        run = research.start(self.config, self.business, parent['id'], request_key='research', model=model, delegation=False)
        self.assertEqual(len(run['findings']), 3)
        real_client = httpx.AsyncClient
        for panorama in (False, True):
            with self.subTest(panorama=panorama):
                sent = []
                def handler(request):
                    payload = json.loads(request.content)
                    sent.append(payload)
                    response = response_from_wire(payload)
                    return httpx.Response(200, json={'choices':[{'finish_reason':'stop',
                        'message':{'content':json.dumps(response)}}], 'usage':{'prompt_tokens':1000}})
                roles = WireRoles()
                with patch('decision_room.agent.model.httpx.AsyncClient',
                           side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)), \
                     patch.dict('os.environ', {'OPENAI_API_KEY':'test-only'}):
                    result = review.start(self.config, self.business, run['id'], request_key=f'wire-{panorama}',
                        analyst=roles, reviewer=roles, sales_panorama=panorama, review_context_budget=True,
                        review_stable_prefix=True, review_loop_guard=True, panorama_obligation_guard=True,
                        review_explicit_cache=True)
                self.assertTrue(result['publishable'], result.get('issue'))
                self.assertEqual(len(sent), 2)
                self.assertEqual([e['action']['action'] for e in result['conversation']], ['submit','approve'])
                for payload in sent:
                    visible = visible_context(payload)
                    self.assertEqual(visible['required_coverage_keys'], ['channels','sales','units'])
                    self.assertIn('review_archive', visible)
                    self.assertEqual(bool(visible['citable_panorama_metrics']), panorama)
                    self.assertTrue(payload['prompt_cache_key'].startswith('dr-review-'))
                with connect(self.config) as db:
                    audit = db.execute('SELECT effective_request,context_payload FROM agent_calls WHERE scope=%s ORDER BY created_at',
                                       (str(result['id']),)).fetchall()
                self.assertEqual(len(audit), 2)
                self.assertTrue(all(a['effective_request']['context_budget']['level'] >= 0 for a in audit))
                from decision_room.agent.review_requirements import inventories
                for recorded, payload in zip(audit, sent, strict=True):
                    self.assertEqual(recorded['effective_request']['payload'], payload)
                    visible = visible_context(payload)
                    for field, complete in inventories(recorded['context_payload']).items():
                        self.assertEqual(visible[field], complete)
                self.assertTrue(result['options']['review_explicit_cache'])
                self.assertEqual({q['investigation_key'] for q in result['report']['question_coverage']},
                                 {'channels','sales','units'})
