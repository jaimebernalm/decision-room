"""Expose only planning actions possible in the current durable state."""
import unittest
from unittest.mock import patch

from decision_room.agent.model import ModelClient, ModelSettings


class ModelActionTests(unittest.TestCase):
    def test_conversation_schema_supports_direct_replies_with_strict_provider_fields(self):
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_chat({})
        schema = request.call_args.args[3]
        self.assertEqual(set(schema['required']), set(schema['properties']))
        self.assertEqual(schema['properties']['action']['enum'], ['retrieve', 'investigate', 'answer'])
        self.assertIn('text', schema['properties'])
        self.assertIn('sources', schema['properties'])
        self.assertNotIn('reply_kind', schema['properties'])

    def test_inspection_is_available_only_when_profiles_remain(self):
        client = ModelClient(ModelSettings('test'))
        for uninspected in ([], ['remaining-table']):
            with patch.object(client, '_generate', return_value=({}, {})) as request:
                client.generate({'uninspected_table_ids': uninspected})
            schema = request.call_args.args[3]
            properties = schema['properties']
            if uninspected:
                self.assertIn('inspect', properties['action']['enum'])
                self.assertIn({'type': 'null'}, properties['proposal']['anyOf'])
            else:
                self.assertEqual(properties['action']['enum'], ['propose'])
                self.assertEqual(properties['table_ids']['maxItems'], 0)
                self.assertEqual(properties['proposal'], {'$ref': '#/$defs/Proposal'})
            self.assertEqual(schema['$defs']['Proposal']['properties']['questions']['maxItems'], 3)
            self.assertNotIn('sales', str(schema['$defs']['Proposal']['properties']))

    def test_research_cannot_re_record_finished_work_or_finish_pending_attempt(self):
        client = ModelClient(ModelSettings('test'))
        context = {'plan': {'investigations': [
            {'key': 'done', 'status': 'ready'}, {'key': 'next', 'status': 'ready'},
            {'key': 'unresolved', 'status': 'blocked'}]},
            'findings': [{'investigation_key': 'done'}],
            'observations': [{'investigation_key': 'done', 'status': 'completed'}]}
        def schema():
            with patch.object(client, '_generate', return_value=({}, {})) as request:
                client.generate_research(context)
            return request.call_args.args[3]['properties']
        properties = schema()
        self.assertEqual(properties['investigation_key']['enum'], ['next', ''])
        self.assertNotIn('record_candidate', properties['action']['enum'])
        context['observations'].append({'investigation_key': 'next', 'status': 'failed'})
        self.assertNotIn('finish', schema()['action']['enum'])
        context['observations'][-1]['status'] = 'completed'
        self.assertIn('record_candidate', schema()['action']['enum'])
        context['findings'].append({'investigation_key': 'next'})
        self.assertEqual(schema()['action']['enum'], ['finish'])
        self.assertEqual(schema()['metric_keys']['maxItems'], 0)

    def test_coordinator_delegates_but_can_repair_its_initial_execution(self):
        client = ModelClient(ModelSettings('test'))
        context = dict(plan={'investigations': [dict(key='root', status='ready'), dict(key='branch', status='ready')]},
                       findings=[dict(investigation_key='root')], observations=[dict(investigation_key='root', status='completed')],
                       budgets={'delegation': True})
        def properties():
            with patch.object(client, '_generate', return_value=({}, {})) as request:
                client.generate_research(context)
            return request.call_args.args[3]['properties']
        self.assertIn('delegate', properties()['action']['enum'])
        self.assertNotIn('execute', properties()['action']['enum'])
        context['findings'] = []
        context['observations'][0]['status'] = 'failed'
        self.assertIn('execute', properties()['action']['enum'])
        context['budgets'] = {'delegation': False, 'worker_assignment': {'investigation_key': 'branch'}}
        self.assertNotIn('delegate', properties()['action']['enum'])
        self.assertEqual(properties()['assignments']['maxItems'], 0)

    def test_role_boundaries_and_failed_checks_limit_offered_actions(self):
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_analyst_review({})
        self.assertNotIn('approve', request.call_args.args[3]['properties']['action']['enum'])
        for report,passed,can_approve in [(None,True,False),({'title':'draft'},False,False),({'title':'draft'},True,True)]:
            with patch.object(client, '_generate', return_value=({}, {})) as request:
                client.generate_reviewer({'report':report,'checks':[{'passed':passed}]})
            allowed=request.call_args.args[3]['properties']['action']['enum']
            self.assertNotIn('submit',allowed)
            self.assertEqual('approve' in allowed,can_approve)
        context={'report':{'title':'draft'},'report_step':1,'checks':[{'passed':True}],
                 'conversation':[{'step':2,'action':{'action':'execute'}}],
                 'budgets':{'python_used':{'reviewer':3},'max_python_per_role':3,
                            'questions_used':3,'max_questions':3}}
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            client.generate_reviewer(context)
        self.assertEqual(request.call_args.args[3]['properties']['action']['enum'],['revise','reject'])

class PlanningReferenceSchemaTests(unittest.TestCase):
    def test_unknown_tables_and_cross_table_columns_are_not_offered(self):
        client = ModelClient(ModelSettings('test'))
        context = dict(catalog=[{'id':'seen'},{'id':'unseen'}], profiles=[{'id':'seen','column_names':['quantity']}],
                       uninspected_table_ids=['unseen'], answers=[])
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate(context)
        schema=request.call_args.args[3]
        choices={(kind,ident,column) for branch in schema['$defs']['Reference']['anyOf']
                 for kind in branch['properties']['kind']['enum']
                 for ident in branch['properties']['id']['enum']
                 for column in branch['properties']['column']['enum']}
        self.assertIn(('column','seen','quantity'),choices)
        self.assertNotIn(('table','unseen',''),choices)
        self.assertNotIn(('column','seen','price'),choices)
        self.assertEqual(schema['$defs']['Investigation']['properties']['table_ids']['items']['enum'],['seen'])
        context['profiles']=[]
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate(context)
        schema=request.call_args.args[3]
        self.assertEqual(schema['properties']['action']['enum'],['inspect'])
        self.assertEqual(schema['properties']['proposal'],{'type':'null'})

    def test_blocked_and_discarded_tasks_are_not_synthesis_candidates(self):
        client=ModelClient(ModelSettings('test'))
        context=dict(findings=[dict(investigation_key='blocked',status='blocked'),dict(investigation_key='supported',status='candidate')])
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_research(context)
        schema=request.call_args.args[3]
        self.assertEqual(schema['$defs']['RankedFinding']['properties']['investigation_key']['enum'],['supported'])
        context['findings']=context['findings'][:1]
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_research(context)
        schema=request.call_args.args[3]
        for field in ('priorities','excluded','disagreements'):
            self.assertEqual(schema['$defs']['Synthesis']['properties'][field]['maxItems'],0)

    def test_success_is_registered_before_further_execution(self):
        client=ModelClient(ModelSettings('test'))
        context=dict(plan={'investigations':[dict(key='calculated',status='ready'),dict(key='next',status='ready')]},
                     findings=[],observations=[dict(investigation_key='calculated',status='completed')])
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_research(context)
        properties=request.call_args.args[3]['properties']
        self.assertEqual(properties['action']['enum'],['record_candidate','block'])
        self.assertEqual(properties['investigation_key']['enum'],['calculated'])
        context['observations'][0]['result_omitted']=True
        with patch.object(client,'_generate',return_value=({},{})) as request:
            client.generate_research(context)
        self.assertIn('execute',request.call_args.args[3]['properties']['action']['enum'])


if __name__ == '__main__':
    unittest.main()
