"""Generic failures; no live models, trial reports, or planted business signals."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from decision_room.agent import research, review
from decision_room.agent.research_recovery import recovery_actions, REASON
from decision_room.config import Config
from decision_room.database import connect
from test_research import ResearchModel
import test_research as base
from test_research_continuity import ContinuingModel, fixtures, ref


class RecoveryContractTests(unittest.TestCase):
    def test_flag_defaults_off(self):
        self.assertFalse(Config('', Path('.')).research_validation_recovery)

    def test_keeps_series_and_prior_success_without_accepting_a_conclusion(self):
        s, o, b = fixtures()
        o.append(dict(o[0], execution_id='failed', status='failed', result=None))
        actions = recovery_actions(s, o, [], b)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['action'], 'record_candidate')
        self.assertEqual(actions[0]['evidence_refs'], [ref(metrics=['total'], series=['groups'])])
        self.assertEqual(actions[0]['summary'], REASON)
        self.assertEqual(actions[0]['closure']['reason'], 'unusable')
        self.assertIsNone(actions[0]['synthesis'])

    def test_legacy_does_not_promote_prior_success_after_failure(self):
        s, o, b = fixtures(); b['research_continuity'] = False
        o.append(dict(o[0], execution_id='failed', status='failed', result=None))
        actions = recovery_actions(s, o, [], b)
        self.assertEqual(actions[0]['action'], 'block')
        self.assertNotIn('evidence_refs', actions[0])

    def test_invalid_or_hidden_evidence_never_becomes_a_candidate(self):
        for changes in [dict(status='failed', result=None), dict(result_omitted=True), dict(current=False),
                        dict(result={'metrics': {}, 'series': {}})]:
            s, o, b = fixtures(); o[0].update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(recovery_actions(s, o, [], b)[0]['action'], 'block')
        self.assertEqual(recovery_actions(s, [], [], b), [])

    def test_unresolved_dependencies_and_existing_candidates_are_respected(self):
        s, o, b = fixtures()
        self.assertEqual(recovery_actions(s, o, [dict(investigation_key='sales', status='candidate')], b), [])
        s['proposal']['investigations'][0]['status'] = 'blocked'
        self.assertEqual(recovery_actions(s, o, [], b), [])


class InvalidAfterEvidence(ContinuingModel):
    def __init__(self, after=2, once=False, delegated=False):
        super().__init__(delegated=delegated)
        self.after, self.once, self.invalids = after, once, 0

    def generate_research(self, context, correction=None):
        if self.delegated and not context['budgets'].get('worker_assignment'):
            return super().generate_research(context, correction)
        if len(context['observations']) >= self.after and (not self.once or not self.invalids):
            self.calls += 1; self.invalids += 1
            return dict(action='execute', investigation_key='sales', code='raise RuntimeError("must not execute")',
                        table_ids=[context['table_catalog'][0]['id']], metric_keys=[], summary='Unsupported conclusion.',
                        continuation=None), {}
        return super().generate_research(context, correction)


class RecoveryIntegrationTests(unittest.TestCase):
    setUpClass = classmethod(base.ResearchTests.setUpClass.__func__)
    tearDownClass = classmethod(base.ResearchTests.tearDownClass.__func__)
    setUp = base.ResearchTests.setUp
    start = base.ResearchTests.start

    def test_enabled_keeps_evidence_marks_partial_and_hands_off_to_review(self):
        m = InvalidAfterEvidence()
        run = self.start(model=m, research_continuity=True, research_validation_recovery=True)
        self.assertEqual(run['status'], 'partial')
        self.assertFalse(run['publishable'])
        self.assertEqual(m.invalids, 2)
        self.assertEqual(len(run['findings'][0]['evidence_refs']), 2)
        self.assertEqual(run['findings'][0]['system_recovery']['source'], 'system')
        self.assertEqual(run['findings'][0]['summary'], REASON)
        self.assertEqual(len([s for s in run['steps'] if s['action']['action'] == 'execute']), 2)
        with connect(self.config) as db:
            calls = db.execute("SELECT output FROM agent_calls WHERE scope=%s AND phase='research' ORDER BY created_at", (str(run['id']),)).fetchall()
        self.assertEqual(len(calls), 4)
        self.assertEqual([c['output']['summary'] for c in calls[-2:]], ['Unsupported conclusion.'] * 2)
        with patch('decision_room.agent.review._drive') as drive:
            review.start(self.config, self.business, run['id'], request_key='salvaged', analyst=m, reviewer=m)
        snapshot = drive.call_args.args[3]['snapshot']
        self.assertFalse(snapshot['research_coverage']['complete'])
        self.assertTrue(snapshot['research_coverage']['validation_recovery'])
        self.assertEqual(len(snapshot['executions']), 2)
        count = m.calls
        research.resume(replace(self.config, research_validation_recovery=False), self.business, run['id'], model=m)
        self.assertEqual(m.calls, count)
        with self.assertRaisesRegex(ValueError, 'different knowledge or options'):
            self.start(model=m, research_continuity=True, research_validation_recovery=False)

    def test_disabled_keeps_double_rejection_failure(self):
        with self.assertRaisesRegex(ValueError, 'failed validation twice'):
            self.start(model=InvalidAfterEvidence(), research_continuity=True)

    def test_corrected_second_response_does_not_activate_recovery(self):
        m = InvalidAfterEvidence(once=True)
        run = self.start(model=m, research_continuity=True, research_validation_recovery=True)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(m.invalids, 1)
        self.assertNotIn('system_recovery', run['findings'][0])

    def test_no_evidence_is_partial_without_inventing_a_candidate(self):
        class Invalid(ResearchModel):
            def generate_research(self, context, correction=None): return {'action': 'invented'}, {}
        run = self.start(model=Invalid(), research_validation_recovery=True)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['findings'], [])
        with self.assertRaisesRegex(ValueError, 'at least one registered candidate'):
            review.start(self.config, self.business, run['id'], request_key='no-evidence')

    def test_legacy_scalar_evidence_is_salvaged_independently_of_continuity(self):
        run = self.start(model=ResearchModel(invented_metric=True), research_validation_recovery=True)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['findings'][0]['metric_keys'], ['total'])
        self.assertNotIn('research_continuity', run['options'])

    def test_business_planner_rejection_closes_existing_candidates_as_partial(self):
        class BadPlanner(ContinuingModel):
            def generate_business_planner(self, context, correction=None):
                if context['stage'] != 'initial': return {'action': 'invented'}, {}
                return super().generate_business_planner(context, correction)
        run = self.start(model=BadPlanner(), research_continuity=True, research_validation_recovery=True, business_planner=True)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(len(run['findings']), 1)
        self.assertNotIn('system_recovery', run['findings'][0])
        self.assertEqual(run['issue'], REASON)

    def test_worker_recovery_is_inherited_and_visible_to_coordinator(self):
        m = InvalidAfterEvidence(delegated=True)
        run = self.start(model=m, research_continuity=True, research_validation_recovery=True, delegation=True)
        self.assertEqual(run['status'], 'partial')
        self.assertIn('system_recovery', run['findings'][0])
        self.assertFalse(run['publishable'])

    def test_crash_after_recovery_write_replays_without_calls_or_duplicates(self):
        m = InvalidAfterEvidence()
        def crash(db):
            saved = db.execute("SELECT 1 FROM agent_research_steps WHERE action ? 'system_recovery' LIMIT 1").fetchone()
            if saved: raise SystemExit(17)
        with patch('decision_room.agent.research_graph.notify', side_effect=crash), self.assertRaises(SystemExit):
            self.start(model=m, research_continuity=True, research_validation_recovery=True)
        with connect(self.config) as db:
            run_id = db.execute('SELECT id FROM agent_research WHERE session_id=%s', (self.plan['id'],)).fetchone()['id']
        count = m.calls
        run = research.resume(self.config, self.business, run_id, model=m)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(len(run['findings']), 1)
        self.assertEqual(m.calls, count)

    def test_transport_errors_are_not_swallowed(self):
        class TransportFailure(ResearchModel):
            def generate_research(self, context, correction=None): raise ValueError('Model transport unavailable')
        with self.assertRaisesRegex(ValueError, 'Model transport unavailable'):
            self.start(model=TransportFailure(), research_validation_recovery=True)
