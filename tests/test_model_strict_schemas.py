"""Exercise every producer through the actual HTTP payload, without network/model calls.

Draft202012Validator alone does not enforce OpenAI's stricter object contract.
https://developers.openai.com/api/docs/guides/structured-outputs
"""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from decision_room.agent.model import ModelClient, ModelSettings, record_request
from decision_room.agent.research_context import prompt_context
from test_chart_layers import layered
from test_research_continuity import fixtures, ref


def assert_strict_objects(test, schema):
    Draft202012Validator.check_schema(schema)
    test.assertEqual(schema.get('type'), 'object')
    test.assertNotIn('anyOf', schema)

    def visit(node, path='$'):
        if isinstance(node, dict):
            types = node.get('type', [])
            if types == 'object' or 'object' in types or 'properties' in node:
                test.assertIs(node.get('additionalProperties'), False, path)
                properties = node.get('properties', {})
                required = node.get('required', [])
                test.assertEqual(set(required), set(properties), path)
                test.assertEqual(len(required), len(set(required)), path)
            if '$ref' in node:
                test.assertTrue(node['$ref'].startswith('#/'), path)
                target = schema
                for part in node['$ref'][2:].split('/'):
                    target = target[part.replace('~1', '/').replace('~0', '~')]
            for key, value in node.items():
                visit(value, f'{path}/{key}')
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit(value, f'{path}/{index}')
    visit(schema)


def cases():
    table = dict(id='t', column_names=['day', 'quantity', 'Group "A"'])
    plan = dict(investigations=[dict(key='sales', status='ready', table_ids=['t'])])
    planning = dict(catalog=[table], profiles=[table], uninspected_table_ids=[], answers=[])
    yield 'planning-profiled', 'generate', planning
    yield 'planning-inspection', 'generate', {**planning, 'profiles': [], 'uninspected_table_ids': ['t']}
    yield 'chat', 'generate_chat', dict(message={'text': 'Comparar cantidades registradas.'}, chat_context={'profile': {}}, retrievals=[])
    yield 'onboarding', 'generate_chat', dict(onboarding=True)
    yield 'chat-review', 'review_chat_answer', dict(answer='Se registran cinco unidades.')
    yield 'dashboard', 'generate_dashboard', dict(businesses=[])
    for tables in ([], [table]):
        yield f'discovery-{len(tables)}', 'generate_data_discovery', dict(tables=tables)
    for scope in ('business', 'session'):
        yield f'memory-{scope}', 'generate_memory', dict(groups=[{'id': 'g'}], source=dict(
            default_scope=scope, scope_id=None if scope == 'business' else 'session-1', allow_business=True))
    for stage in ('initial', 'checkpoint', 'delivery'):
        yield f'planner-{stage}', 'generate_business_planner', dict(
            stage=stage, table_catalog=[table], plan=plan,
            findings=[dict(investigation_key='sales', status='candidate')],
            owner_replies=[dict(disposition='answered')] if stage == 'delivery' else [])

    for continuity in (False, True):
        for state in ('first', 'coordinator-first', 'worker-first', 'success', 'multiple', 'later-failure',
                      'metrics-only', 'series-only', 'stale', 'hidden', 'expand', 'budget', 'worker'):
            snapshot, observations, options = fixtures()
            snapshot['tables'][0].update(column_names=table['column_names'])
            options['research_continuity'] = continuity
            findings = []
            if state in ('first', 'coordinator-first', 'worker-first'):
                observations = []
                if state == 'coordinator-first':
                    options['delegation'] = True
                elif state == 'worker-first':
                    options['worker_assignment'] = dict(investigation_key='sales', instruction='Comparar grupos.')
            elif state == 'multiple':
                observations.append(dict(deepcopy(observations[0]), execution_id='e2', step=2))
            elif state == 'metrics-only':
                observations[0]['result']['series'] = {}
            elif state == 'stale':
                observations[0]['current'] = False
            elif state == 'later-failure':
                observations.append(dict(observations[0], execution_id='e2', status='failed', result=None))
            elif state == 'series-only':
                observations[0]['result']['metrics'] = {}
            elif state == 'hidden':
                observations[0]['result']['notes'] = ['x' * 65000]
            elif state == 'expand':
                findings = [dict(investigation_key='sales', status='candidate', execution_id='e1',
                                 metric_keys=['total'], evidence_refs=[ref(metrics=['total'], series=['groups'])])]
                options['delegation'] = True
            elif state == 'budget':
                options['max_executions'] = 1
            elif state == 'worker':
                options['worker_assignment'] = dict(investigation_key='sales', instruction='Comparar grupos.')
            yield f'research-{continuity}-{state}', 'generate_research', prompt_context(
                snapshot, observations, findings, options, len(observations))

    for method in ('generate_analyst_review', 'generate_reviewer'):
        for state in ('empty', 'layers', 'series-only', 'stale', 'budget'):
            context = layered()
            context.update(plan=plan, review_policy=5, delivery_quality=1,
                           accepted_owner_request={'deliverables': ['Comparar cantidades']},
                           conversation=[dict(step=1, action={'action': 'execute'})], report_step=2)
            context['report']['owner_coverage'] = [dict(deliverable_index=0, status='partial', claim_keys=[])]
            if state == 'empty':
                context['observations'] = []
            elif state == 'series-only':
                for observation in context['observations']:
                    observation['result']['metrics'] = {}
            elif state == 'stale':
                for observation in context['observations']:
                    observation['current'] = False
            elif state == 'budget':
                context['budgets'] = dict(python_used={'analyst': 3, 'reviewer': 3}, questions_used=3)
            yield f'{method}-{state}', method, context


class StrictProviderSchemaTests(unittest.TestCase):
    def capture(self, method, context):
        payloads, recorded = [], []
        def handler(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [dict(finish_reason='stop', message={'content': '{}'})]})
        transport = httpx.Client(transport=httpx.MockTransport(handler))
        with patch('decision_room.agent.model.httpx.Client', return_value=transport), \
             patch.dict('os.environ', {'OPENAI_API_KEY': 'test-placeholder'}, clear=True), \
             record_request(recorded.append):
            client = ModelClient(ModelSettings('test', protocol='openai', base_url='https://api.openai.com/v1'))
            getattr(client, method)(deepcopy(context))
        self.assertEqual(len(payloads), 1)
        self.assertEqual(recorded[0]['payload'], payloads[0])
        wire = payloads[0]['response_format']['json_schema']
        self.assertIs(wire['strict'], True)
        return wire['schema']

    def test_all_producers_emit_strict_objects_in_final_payload(self):
        covered = set()
        for name, method, context in cases():
            covered.add(method)
            # Exercise schema_for's late retrieval injection as used by the agents.
            retrieval = method in {'generate', 'generate_research',
                                   'generate_business_planner', 'generate_analyst_review', 'generate_reviewer'}
            for memory in (False, True) if retrieval else (False,):
                with self.subTest(case=name, memory=memory):
                    effective = deepcopy(context)
                    if memory:
                        effective['business_context'] = dict(retrievals=[], profile={'name': 'Synthetic'})
                    assert_strict_objects(self, self.capture(method, effective))
        # New producers must join this matrix instead of silently escaping coverage.
        producers = {name for name in vars(ModelClient)
                     if name == 'generate' or name.startswith('generate_') or name == 'review_chat_answer'}
        self.assertEqual(covered, producers)

    def test_checker_detects_missing_required_and_open_objects_in_nested_branches(self):
        _, _, context = next(c for c in cases() if c[0] == 'research-True-success')
        schema = self.capture('generate_research', context)
        for fault in ('required', 'additionalProperties'):
            bad = deepcopy(schema)
            branch = bad['properties']['decision']['anyOf'][0]
            if fault == 'required':
                branch['required'] = ['execution_id']
            else:
                branch.pop('additionalProperties')
            with self.subTest(fault=fault), self.assertRaises(AssertionError):
                assert_strict_objects(self, bad)

    def test_evidence_requires_explicit_lists_but_accepts_empty_unused_list(self):
        for name in ('research-True-first', 'research-True-success'):
            _, _, context = next(c for c in cases() if c[0] == name)
            schema = self.capture('generate_research', context)
            validator = Draft202012Validator({'$defs': schema['$defs'], '$ref': '#/$defs/EvidenceRef'})
            for value in (ref(metrics=['total']), ref(series=['groups'])):
                validator.validate(value)
                for field in ('metric_keys', 'series_keys'):
                    bad = dict(value)
                    bad.pop(field)
                    self.assertFalse(validator.is_valid(bad), (name, field))
