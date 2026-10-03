"""The same synthetic context drives schema and domain-validator regressions."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.research_context import prompt_context
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_continuity import ContinuityAction
from decision_room.memory.retrieval import schema_for
from test_research_continuity import fixtures, ref, action, closure
from test_model_strict_schemas import assert_strict_objects


class SchemaParityTests(unittest.TestCase):
    def setUp(self):
        self.s, self.o, self.b = fixtures()
        self.f = []

    def schema(self):
        c = prompt_context(self.s, self.o, self.f, self.b, 1)
        client = ModelClient(ModelSettings('test'))
        with patch.object(client, '_generate', return_value=({}, {})) as call:
            client.generate_research(c)
        schema = client._wire_schema(call.call_args.args[3])
        assert_strict_objects(self, schema)
        return schema

    def accepted(self, value):
        normalized = ContinuityAction.model_validate(value).model_dump()
        Draft202012Validator(self.schema()).validate({'decision': normalized})
        validate_research_action(normalized, self.s, self.o, self.f, self.b)
        return normalized

    def rejected(self, value):
        self.assertFalse(Draft202012Validator(self.schema()).is_valid({'decision': value}))
        with self.assertRaises(ValueError):
            validate_research_action(value, self.s, self.o, self.f, self.b)

    def continuing(self):
        return action(continuation=dict(evidence=[ref(series=['groups'])],
                      next_calculation='Medir dispersión.', decision_if_different='Cambiar la siguiente revisión.'))

    def test_execute_success_requires_non_null_continuation_in_both_contracts(self):
        a = self.accepted(self.continuing())
        a['continuation'] = None
        self.rejected(a)

    def test_initial_execute_and_later_failure_allow_null(self):
        self.o = []
        self.accepted(action())
        self.s, self.o, self.b = fixtures()
        self.o.append(dict(self.o[0], execution_id='e2', status='failed', result=None))
        self.accepted(action())

    def test_action_fields_and_closure_are_correlated(self):
        a = self.accepted(action('record_candidate', evidence_refs=[ref(series=['groups'])], closure=closure()))
        for field, value in [('closure', None), ('code', 'print(1)'), ('table_ids', ['t']),
                             ('continuation', self.continuing()['continuation']), ('evidence_refs', [])]:
            with self.subTest(field=field):
                bad = deepcopy(a); bad[field] = value; self.rejected(bad)
        b = self.accepted(action('block', closure=closure('missing_data')))
        b['closure']['pending_calculation'] = None
        self.rejected(b)

    def test_refs_reject_unknown_empty_and_cross_task_keys(self):
        other = deepcopy(self.o[0]); other.update(execution_id='e-other', investigation_key='other')
        self.o.append(other)
        a = self.accepted(action('record_candidate', evidence_refs=[ref(series=['groups'])], closure=closure()))
        for r in [ref('invented', series=['groups']), ref(metrics=['invented']), ref(series=['invented']),
                  ref('e-other', series=['groups']), ref()]:
            with self.subTest(ref=r):
                bad = deepcopy(a); bad['evidence_refs'] = [r]; self.rejected(bad)

    def test_omitted_stale_and_failed_evidence_are_not_offered(self):
        self.o.append(dict(deepcopy(self.o[0]), execution_id='e2'))
        a = self.accepted(action('record_candidate', evidence_refs=[ref(series=['groups'])], closure=closure()))
        for changes in [dict(current=False), dict(result_omitted=True), dict(status='failed', result=None)]:
            with self.subTest(changes=changes):
                original = deepcopy(self.o[0]); self.o[0].update(changes)
                self.rejected(a); self.o[0] = original

    def test_multiple_tasks_bind_continuation_and_authorized_tables(self):
        self.s['proposal']['investigations'].append(dict(self.s['proposal']['investigations'][0], key='other', table_ids=['t2']))
        self.s['tables'].append(dict(id='t2', alias='t2'))
        a = self.accepted(self.continuing())
        a['investigation_key'] = 'other'
        self.rejected(a)
        a = self.accepted(self.continuing()); a['table_ids'] = ['t2']; self.rejected(a)
        fresh = action()
        fresh.update(investigation_key='other', table_ids=['t2'])
        self.accepted(fresh)

    def test_execution_budgets_are_bound_to_task(self):
        for changes in [dict(max_executions=1), dict(max_attempts_per_investigation=1), dict(max_rounds=0)]:
            with self.subTest(changes=changes):
                self.b.update(changes)
                a = ContinuityAction.model_validate(self.continuing()).model_dump()
                self.rejected(a)
                self.b = fixtures()[2]

    def expansion(self):
        self.b['delegation'] = True
        self.o.append(dict(deepcopy(self.o[0]), execution_id='unregistered'))
        self.f = [dict(investigation_key='sales', status='candidate', metric_keys=[], execution_id='e1',
                       evidence_refs=[ref(series=['groups'])])]
        child = dict(self.s['proposal']['investigations'][0], key='followup_1', question='Qué grupo explica la dispersión',
                     stage='breakdown', priority=dict(relevance=3, magnitude=3, reliability=3, cost=1, reason='Cambiar decisión'),
                     basis_metric_keys=[], basis_evidence=[ref(series=['groups'])])
        child.update(focus=None)
        return action('expand', evidence_refs=[ref(series=['groups'])], followups_unused=[child])

    def test_expansion_restricts_parent_and_child_refs_to_registered_keys(self):
        a = self.expansion(); a['followups'] = a.pop('followups_unused')
        a = self.accepted(a)
        for path in ('parent', 'child'):
            for badref in [ref('unregistered', series=['groups']), ref(metrics=['total'])]:
                with self.subTest(path=path, ref=badref):
                    bad = deepcopy(a)
                    if path == 'parent': bad['evidence_refs'] = [badref]
                    else: bad['followups'][0]['basis_evidence'] = [badref]
                    self.rejected(bad)
        bad = deepcopy(a); bad['followups'] = []; self.rejected(bad)

    def test_worker_cannot_expand_registered_parent(self):
        a = self.expansion(); a['followups'] = a.pop('followups_unused')
        a = self.accepted(a)
        # Give worker an unfinished task, so closing/discard remains available.
        self.s['proposal']['investigations'].append(dict(self.s['proposal']['investigations'][0], key='other'))
        self.b['worker_assignment'] = dict(investigation_key='other')
        self.rejected(a)

    def test_retrieval_is_separate_and_cannot_null_a_continuation(self):
        schema = schema_for(self.schema()); assert_strict_objects(self, schema)
        v = Draft202012Validator(schema)
        a = ContinuityAction.model_validate(self.continuing()).model_dump()
        a['retrieval'] = None; v.validate({'decision': a})
        a['continuation'] = None; self.assertFalse(v.is_valid({'decision': a}))
        a.update(action='retrieve', investigation_key='', code='', table_ids=[],
                 retrieval=dict(tool='search_datasets', query='', id='', limit=1))
        v.validate({'decision': a})
        self.assertFalse(v.is_valid({'decision': a, 'action': 'execute'}))
