"""Provider encoding must not corrupt legitimate quoted source names."""
import json
import unittest
from unittest.mock import patch

import httpx

from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.series import evidence_value


class WireSchemaTests(unittest.TestCase):
    def test_chart_coordinates_and_attachment_option_have_provider_strict_schemas(self):
        client=ModelClient(ModelSettings('test'))
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_analyst_review({})
        schema=request.call_args.args[3]
        for name in ('ChartEncoding','ChartCoordinate','PointDetail','UsefulnessAudit','OwnerCoverage','OwnerUtility','DecisionOrientation'):
            definition=schema['$defs'][name]
            self.assertEqual(set(definition['required']),set(definition['properties']))
        self.assertIn('encoding',schema['$defs']['Chart']['required'])
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_chat({})
        schema=request.call_args.args[3]
        self.assertIn('include_report',schema['required'])
        self.assertNotIn('default',schema['properties']['include_report'])

    def test_saved_series_without_redundant_scalars_can_support_a_report(self):
        client=ModelClient(ModelSettings('test'))
        context={'observations':[{'execution_id':'e','current':True,'status':'completed','result':{
            'metrics':{},'evidence':[],'series':{'monthly':{'unit':'units','grain':'month',
            'points':[{'label':'2026-06','value':2},{'label':'2026-07','value':3}]}}}}]}
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_analyst_review(context)
        schema=request.call_args.args[3]
        self.assertIn('submit',schema['properties']['action']['enum'])
        self.assertNotIn('#/$defs/MetricRef',json.dumps(schema))

    def test_candidate_metric_choices_use_latest_saved_results(self):
        client=ModelClient(ModelSettings('test'))
        context={'observations':[
            {'investigation_key':'sales','status':'completed','result':{'metrics':{'old':1}}},
            {'investigation_key':'sales','status':'completed','result':{'metrics':{'current':2}}},
            {'investigation_key':'other','status':'failed','result':{'metrics':{'invalid':3}}}]}
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_research(context)
        self.assertEqual(request.call_args.args[3]['properties']['metric_keys']['items']['enum'],['current'])

    def test_activity_labels_keep_planning_and_followups_provider_strict(self):
        client = ModelClient(ModelSettings('test'))
        for method in ('generate', 'generate_research'):
            with patch.object(client, '_generate', return_value=({}, {})) as request:
                getattr(client, method)({})
            schema = request.call_args.args[3]
            for definition in schema.get('$defs', {}).values():
                if definition.get('type') == 'object':
                    self.assertEqual(set(definition.get('required', [])), set(definition['properties']))
            field = schema['$defs']['Investigation' if method == 'generate' else 'Followup']['properties']['activity_label']
            self.assertNotIn('default', field)

    def test_business_planner_question_references_and_actions_are_scoped(self):
        client = ModelClient(ModelSettings('test'))
        context = dict(stage='checkpoint', table_catalog=[dict(id='sales',column_names=['amount'])],
                       plan={'investigations':[{'key':'q'}]}, findings=[], owner_replies=[])
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_business_planner(context)
        schema = request.call_args.args[3]
        self.assertEqual(schema['properties']['action']['enum'], ['guide','ask_owner'])
        self.assertEqual(set(schema['required']), set(schema['properties']))
        self.assertIn('orientation', schema['required'])
        self.assertEqual(schema['properties']['evidence_keys']['maxItems'],0)
        branches = schema['$defs']['Reference']['anyOf']
        self.assertEqual([b['properties']['kind']['enum'][0] for b in branches], ['owner_context','table','column'])
        column = branches[-1]['properties']
        self.assertEqual(column['id']['enum'],['sales'])
        self.assertEqual(column['column']['enum'],['amount'])

    def test_discovery_can_only_choose_actual_table_ids(self):
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_data_discovery({'tables': [{'id': 'one'}, {'id': 'two'}]})
        schema = request.call_args.args[3]
        self.assertEqual(schema['$defs']['TableMeaning']['properties']['id']['enum'], ['one', 'two'])
        for field in ('source', 'target'):
            self.assertEqual(schema['$defs']['RelationProposal']['properties'][field]['enum'], ['one', 'two'])

    def test_reviewer_can_fail_an_answer_but_cannot_misclassify_its_delivery(self):
        client = ModelClient(ModelSettings('test'))
        context = {'report': {'question_coverage': [dict(investigation_key='q', status='answered', claim_keys=['c'])]}}
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_reviewer(context)
        branch = request.call_args.args[3]['$defs']['QuestionUtility']['anyOf'][0]
        self.assertEqual(branch['properties']['verdict']['enum'], ['pass', 'fail'])
        self.assertEqual(branch['properties']['claim_keys']['items']['enum'], ['c'])
        context['report']['question_coverage'][0].update(status='deferred', claim_keys=[])
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_reviewer(context)
        branch = request.call_args.args[3]['$defs']['QuestionUtility']['anyOf'][0]
        self.assertEqual(branch['properties']['verdict']['enum'], ['deferred', 'fail'])
        self.assertEqual(branch['properties']['claim_keys']['maxItems'], 0)

    def test_quoted_columns_survive_context_and_only_affected_enum_is_relaxed(self):
        context = dict(catalog=[{'id': 'source'}], profiles=[{'id': 'source', 'column_names': ['Size "large"']}],
                       uninspected_table_ids=[], answers=[])
        payloads = []
        def handler(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}], 'usage': {}})
        with patch('decision_room.agent.model.httpx.Client', return_value=httpx.Client(transport=httpx.MockTransport(handler))), \
             patch.dict('os.environ', {'OPENAI_API_KEY': 'test-placeholder'}):
            ModelClient(ModelSettings('test', protocol='openai', base_url='https://api.openai.com/v1', reasoning='low')).generate(context)
        payload = payloads[0]
        self.assertEqual(json.loads(payload['messages'][1]['content'])['profiles'][0]['column_names'], ['Size "large"'])
        schema = payload['response_format']['json_schema']['schema']
        branches = schema['$defs']['Reference']['anyOf']
        column = next(b for b in branches if b['properties']['kind']['enum'] == ['column'])
        self.assertNotIn('enum', column['properties']['column'])
        self.assertEqual(column['properties']['column']['type'], 'string')
        self.assertEqual(column['properties']['id']['enum'], ['source'])
        self.assertEqual(schema['properties']['action']['enum'], ['propose'])
        self.assertEqual(context['profiles'][0]['column_names'], ['Size "large"'])

    def test_exact_quote_label_is_still_required_by_evidence_validator(self):
        label = 'Product "large"'
        observations = [dict(execution_id='e', current=True, status='completed', inputs={'t': {}}, result={
            'series': {'items': dict(unit='units', grain='category', points=[dict(label=label, value=2), dict(label='Other', value=3)],
                                    evidence=dict(tables=['t'], operation='Sum by original name'))}})]
        ref = dict(execution_id='e', series='items', label=label)
        self.assertEqual(evidence_value(observations, ref), 2)
        with self.assertRaisesRegex(ValueError, 'Unknown saved series label'):
            evidence_value(observations, {**ref, 'label': 'Product large'})
        schema = {'type': 'string', 'enum': [label, 'Other']}
        self.assertNotIn('enum', ModelClient._wire_schema(schema))
        self.assertEqual(schema['enum'], [label, 'Other'])


if __name__ == '__main__':
    unittest.main()
