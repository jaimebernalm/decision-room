"""Expose only available tool IDs and evidence pairs to structured decoding."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from decision_room.agent.model import ModelClient, ModelSettings


class ModelReferenceTests(unittest.TestCase):
    def schema(self, method, context):
        client = ModelClient(ModelSettings('test'))
        original = deepcopy(context)
        with patch.object(client, '_generate', return_value=({}, {})) as request:
            getattr(client, method)(context)
        self.assertEqual(context, original)
        return request.call_args.args[3]

    def test_planning_uses_catalog_ids_and_only_uninspected_tool_ids(self):
        context = {'catalog': [{'id': 'known'}, {'id': 'pending'}],
                   'uninspected_table_ids': ['pending']}
        schema = self.schema('generate', context)
        self.assertEqual(schema['properties']['table_ids']['items']['enum'], ['pending'])
        self.assertEqual(schema['$defs']['Investigation']['properties']['table_ids']['items']['enum'],
                         ['known', 'pending'])
        context['uninspected_table_ids'] = []
        self.assertEqual(self.schema('generate', context)['properties']['table_ids']['maxItems'], 0)

    def test_research_rejects_alias_foreign_finished_and_blocked_table_choices(self):
        context = {'table_catalog': [{'id': name, 'alias': f't{i}'}
                                    for i, name in enumerate(['ready-table', 'finished-table', 'blocked-table'], 1)],
                   'plan': {'investigations': [
                       {'key': 'work', 'status': 'ready', 'table_ids': ['ready-table', 'foreign-table']},
                       {'key': 'done', 'status': 'ready', 'table_ids': ['finished-table']},
                       {'key': 'wait', 'status': 'blocked', 'table_ids': ['blocked-table']}]},
                   'findings': [{'investigation_key': 'done'}], 'observations': []}
        choices = self.schema('generate_research', context)['properties']['table_ids']['items']['enum']
        self.assertEqual(choices, ['ready-table'])
        for invalid in ['t1', 'foreign-table', 'finished-table', 'blocked-table']:
            self.assertNotIn(invalid, choices)

    def test_review_keeps_real_execution_metric_pairs_and_excludes_unavailable_evidence(self):
        def observation(execution, current, status, metrics, evidenced):
            return {'execution_id': execution, 'current': current, 'status': status,
                    'result': {'metrics': dict.fromkeys(metrics, 1),
                               'evidence': [{'metric': key} for key in evidenced]}}
        context = {'tables': [{'id': 'table', 'alias': 't1'}], 'observations': [
            observation('first', True, 'completed', ['total', 'missing_provenance'], ['total']),
            observation('second', True, 'completed', ['daily'], ['daily']),
            observation('old', False, 'completed', ['old_metric'], ['old_metric']),
            observation('failed', True, 'failed', ['invalid'], ['invalid']),
            dict(observation('partial', True, 'completed', ['hidden'], ['hidden']), result_omitted=True),
            {'execution_id': 'omitted', 'current': True, 'status': 'completed', 'result': None}]}
        for method in ['generate_analyst_review', 'generate_reviewer']:
            with self.subTest(method=method):
                schema = self.schema(method, context)
                pairs = {(execution, metric)
                         for branch in schema['$defs']['MetricRef']['anyOf']
                         for execution in branch['properties']['execution_id']['enum']
                         for metric in branch['properties']['metric']['enum']}
                self.assertEqual(pairs, {('first', 'total'), ('second', 'daily')})
                self.assertNotIn(('first', 'daily'), pairs)
                self.assertEqual(schema['properties']['table_ids']['items']['enum'], ['table'])

    def test_operation_shapes_reject_extra_ratio_operands_without_limiting_sums(self):
        for method in ['generate_analyst_review', 'generate_reviewer']:
            schema = self.schema(method, {})
            def allowed(operation, count):
                return any(operation in b['properties']['operation']['enum']
                           and b['properties']['operands']['minItems'] <= count
                           <= b['properties']['operands']['maxItems']
                           for b in schema['$defs']['NumericCheck']['anyOf'])
            for operation in ['ratio_percent', 'percent_change']:
                self.assertTrue(allowed(operation, 2))
                self.assertFalse(allowed(operation, 1))
                self.assertFalse(allowed(operation, 3))
            self.assertTrue(allowed('sum', 4))
            self.assertFalse(allowed('sum', 0))
            self.assertTrue(allowed('equal', 1))
            self.assertFalse(allowed('equal', 2))
            for operation in ['zero', 'nonnegative']:
                self.assertTrue(allowed(operation, 0))
                self.assertFalse(allowed(operation, 1))

    def test_no_evidence_still_allows_questions_execution_and_withdrawal(self):
        context = {'tables': [{'id': 'table'}], 'observations': []}
        analyst = self.schema('generate_analyst_review', context)
        self.assertEqual(analyst['properties']['report'], {'type': 'null'})
        self.assertEqual(set(analyst['properties']['action']['enum']), {'execute', 'ask_owner', 'withdraw'})
        reviewer = self.schema('generate_reviewer', context)
        self.assertNotIn('approve', reviewer['properties']['action']['enum'])
        context['budgets'] = {'python_used': {'analyst': 3}, 'max_python_per_role': 3,
                              'questions_used': 3, 'max_questions': 3}
        self.assertEqual(self.schema('generate_analyst_review', context)['properties']['action']['enum'], ['withdraw'])

    def test_series_pairs_and_new_fields_are_required_for_strict_output(self):
        obs = lambda key,current: {'execution_id':key, 'current':current,'status':'completed',
                                   'result':{'series':{'monthly':{'unit':'units'}},'metrics':{'total':1},'evidence':[{'metric':'total'}]}}
        context = {'observations':[obs('current',True),obs('old',False)]}
        schema = self.schema('generate_analyst_review', context)
        pairs = schema['$defs']['SeriesRef']['anyOf']
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]['properties']['execution_id']['enum'],['current'])
        self.assertEqual(pairs[0]['properties']['series']['enum'],['monthly'])
        definitions = [schema['$defs']['ReportDraft'], *schema['$defs']['Chart']['anyOf']]
        for definition in definitions:
            self.assertEqual(set(definition['required']),set(definition['properties']))
        schema = self.schema('generate_analyst_review', {'observations':[]})
        self.assertEqual(schema['$defs']['Chart']['properties']['series'],{'type':'null'})

    def test_chart_choices_pair_saved_units_with_their_exact_execution_and_series(self):
        def observation(key, unit, **overrides):
            return {'execution_id': key, 'current': True, 'status': 'completed',
                    'result': {'series': {'same_key': {'unit': unit}},
                               'metrics': {'total': 1}, 'evidence': [{'metric': 'total'}]}, **overrides}
        context = {'observations': [observation('money', 'moneda no especificada'),
                                   observation('count', 'unidades'),
                                   observation('old', 'obsolete', current=False),
                                   observation('failed', 'failed', status='failed'),
                                   observation('omitted', 'omitted', result_omitted=True)]}
        for method in ('generate_analyst_review', 'generate_reviewer'):
            schema = self.schema(method, context)
            branches = schema['$defs']['Chart']['anyOf']
            scalar = [b for b in branches if b['properties']['series'] == {'type': 'null'}]
            self.assertEqual(len(scalar), 1)
            self.assertEqual(scalar[0]['properties']['points']['minItems'], 2)
            pairs = set()
            for branch in branches:
                props = branch['properties']
                if props['series'] == {'type': 'null'}: continue
                self.assertEqual(props['points']['maxItems'], 0)
                for ref in props['series']['anyOf']:
                    pairs.update((execution, key, unit)
                                 for execution in ref['properties']['execution_id']['enum']
                                 for key in ref['properties']['series']['enum']
                                 for unit in props['unit']['enum'])
            self.assertEqual(pairs, {('money', 'same_key', 'moneda no especificada'),
                                     ('count', 'same_key', 'unidades')})

    def test_coverage_schema_allows_blocked_explanations_without_answers(self):
        context = {'plan': {'investigations': [{'key': 'units', 'status': 'ready'},
                                               {'key': 'money', 'status': 'blocked'},
                                               {'key': 'profit', 'status': 'not_possible'}]}}
        schema = self.schema('generate_analyst_review', context)
        field = schema['$defs']['ReportDraft']['properties']['question_coverage']
        self.assertEqual((field['minItems'], field['maxItems']), (1, 3))
        pairs = set()
        for branch in schema['$defs']['QuestionCoverage']['anyOf']:
            props = branch['properties']
            pairs.update((key, status) for key in props['investigation_key']['enum']
                         for status in props['status']['enum'])
            if 'answered' not in props['status']['enum']:
                self.assertEqual(props['claim_keys']['maxItems'], 0)
        self.assertEqual(pairs, {('units', 'answered'), ('units', 'unavailable'),
                                 ('money', 'unavailable'), ('profit', 'unavailable')})


if __name__ == '__main__':
    unittest.main()
