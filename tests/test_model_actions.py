"""Expose only planning actions possible in the current durable state."""
import unittest
from unittest.mock import patch

from decision_room.agent.model import ModelClient, ModelSettings


class ModelActionTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
