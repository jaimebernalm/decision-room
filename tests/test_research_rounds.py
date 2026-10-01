"""Round control uses scripted models; calculations use real Docker and PostgreSQL."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch

import test_research as base_tests
from test_research import ResearchModel
from decision_room.agent import research, review
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_agenda import agenda
from decision_room.database import connect
from decision_room.execution import execute
from test_review import DialogueModel


class RoundModel(ResearchModel):
    def __init__(self, *, blocked=False, discard=False):
        super().__init__()
        self.blocked, self.discard = blocked, discard
        self.seen = []

    def generate_research(self, context, correction=None):
        self.calls += 1
        self.seen.append(deepcopy(context))
        finished = {f['investigation_key'] for f in context['findings']} | set(context['budgets']['discarded_keys'])
        target = next(i for i in context['plan']['investigations'] if i['key'] not in finished and i['status'] == 'ready')
        key = target['key']
        action = dict(action='execute', investigation_key=key, table_ids=[], code='', summary='Comprobar contribución; no demuestra causa.', metric_keys=[], followups=[])
        prior = [o for o in context['observations'] if o['investigation_key'] == key]
        if prior:
            action.update(action='record_candidate', metric_keys=['total'])
            if key == 'sales':
                action['followups'] = [self.child(target, 'minor', 1), self.child(target, 'major', 5)]
                if self.blocked:
                    action['followups'][1].update(status='blocked', definitions_needed=['Confirmar si hay costes.'])
            return action, {}
        if self.discard and key == 'minor':
            return {**action, 'action': 'discard', 'summary': 'Aporta poco al objetivo; se descarta sin considerarlo completado.'}, {}
        table = context['table_catalog'][0]
        where = '' if key == 'sales' else ' WHERE CAST(quantity AS INTEGER) = ' + ('3' if key == 'major' else '2')
        query = f'SELECT SUM(CAST(quantity AS DECIMAL(18,2))*CAST(amount AS DECIMAL(18,2))) FROM {table["alias"]}' + where
        code = f'''from dr_runtime import connect, write_result
with connect() as db:
    total = db.execute({query!r}).fetchone()[0]
write_result({{'total':str(total)}}, evidence=[{{'metric':'total','tables':[{table['alias']!r}],'operation':{query!r}}}])
'''
        return {**action, 'table_ids': [table['id']], 'code': code}, {}

    @staticmethod
    def child(parent, key, relevance):
        return {k: v for k, v in {**parent, 'key': key, 'question': 'Comprobar contribución ' + key,
            'stage': 'breakdown', 'basis_metric_keys': ['total'],
            'focus': dict(segment=key, period='Extracto disponible', comparison='Contribución al total', decision_value='Localizar la contribución de este grupo.'),
            'priority': dict(relevance=relevance, magnitude=3, reliability=5, cost=1, reason='Prioridad estimada para el objetivo.')}.items()
            if k not in ('round', 'parent_key')}


class PartialReview(DialogueModel):
    def generate_analyst_review(self, context, correction=None):
        raw, usage = super().generate_analyst_review(context, correction)
        if raw.get('report') and context.get('research_coverage'):
            states = {i['key']: i['research_status'] for i in context['research_coverage']['investigations']}
            for item in raw['report']['question_coverage']:
                if states[item['investigation_key']] != 'candidate':
                    item.update(status='unavailable', claim_keys=[], explanation='Pendiente por presupuesto de investigación.')
            if any(i['status'] == 'unavailable' for i in raw['report']['question_coverage']):
                for entry in raw['report']['owner_coverage']:
                    entry.update(status='partial', explanation='Total disponible; desgloses pendientes en esta entrega.')
        return raw, usage


class RoundTests(unittest.TestCase):
    setUpClass = classmethod(base_tests.ResearchTests.setUpClass.__func__)
    tearDownClass = classmethod(base_tests.ResearchTests.tearDownClass.__func__)
    setUp = base_tests.ResearchTests.setUp
    start = base_tests.ResearchTests.start

    def test_evidence_linked_depth_and_priority(self):
        model = RoundModel()
        result = self.start(model=model)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([f['investigation_key'] for f in result['findings']], ['sales', 'major', 'minor'])
        values = [s['execution']['result']['metrics']['total'] for s in result['steps'] if s['action']['action'] == 'execute']
        self.assertEqual(values, ['80.0000', '60.0000', '20.0000'])
        self.assertEqual(result['coverage']['rounds_used'], 2)
        major = next(i for i in result['investigations'] if i['key'] == 'major')
        self.assertEqual((major['parent_key'], major['basis_metric_keys']), ('sales', ['total']))
        again = research.resume(self.config, self.business, result['id'], model=model)
        self.assertEqual(len(again['model_calls']), 6)
        self.assertEqual(len(again['steps']), 6)
        self.assertFalse(again['publishable'])

    def test_focus_survives_followup_and_missing_focus_is_rejected(self):
        model = RoundModel()
        self.start(model=model)
        context = next(c for c in model.seen if any(o['status'] == 'completed' for o in c['observations']) and not c['findings'])
        raw, _ = model.generate_research(context)
        snapshot = {'proposal': context['plan'], 'answers': context['answers'], 'tables': context['table_catalog']}
        accepted = validate_research_action(raw, snapshot, context['observations'], context['findings'], context['budgets'])
        history = [{'action': accepted}]
        child = next(i for i in agenda(snapshot, history)['proposal']['investigations'] if i['key'] == 'major')
        self.assertEqual(child['focus']['segment'], 'major')
        self.assertEqual(child['parent_key'], 'sales')
        raw['followups'][0].pop('focus')
        with self.assertRaisesRegex(ValueError, 'followup needs focus'):
            validate_research_action(raw, snapshot, context['observations'], context['findings'], context['budgets'])

    def test_execution_and_investigation_budgets_keep_reviewable_candidate(self):
        for option in ('max_executions', 'max_investigations'):
            with self.subTest(option=option):
                result = research.start(self.config, self.business, self.plan['id'], request_key=option, model=RoundModel(), **{option: 1})
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(len(result['findings']), 1)
                self.assertEqual(sum(s['action']['action'] == 'execute' for s in result['steps']), 1)
                self.assertEqual(sum(i['research_status'] == 'pending' for i in result['investigations']), 2)

    def test_round_budget_preserves_unexecuted_children(self):
        result = self.start(model=RoundModel(), max_rounds=1)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('rondas', result['issue'])
        self.assertEqual(len(result['model_calls']), 2)
        self.assertEqual(len(result['investigations']), 3)

    def test_model_budget_and_turn_budget_are_normal_stops(self):
        for option in ('max_model_calls', 'max_turns'):
            with self.subTest(option=option):
                result = research.start(self.config, self.business, self.plan['id'], request_key=option, model=RoundModel(), **{option: 3})
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(len(result['findings']), 1)
                self.assertEqual(len(result['model_calls']), 3)
                self.assertIn('alcanzado', result['issue'])

    def test_retrievals_and_corrections_consume_same_budget(self):
        class Retrieve(RoundModel):
            def generate_research(self, context, correction=None):
                return dict(action='retrieve', retrieval=dict(tool='search_memory', query='', id='', limit=1)), {}
        result = self.start(model=Retrieve(), max_model_calls=2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['model_calls']), 2)
        self.assertFalse(result['steps'])
        class Invalid(RoundModel):
            def generate_research(self, context, correction=None):
                return {'invalid_model_output': 'broken'}, {}
        result = research.start(self.config, self.business, self.plan['id'], request_key='correction-budget', model=Invalid(), max_model_calls=1)
        self.assertEqual((result['status'], len(result['model_calls'])), ('partial', 1))

    def test_time_limit_survives_recovery_without_duplicating_python(self):
        def crash(*args, **kwargs):
            execute(*args, **kwargs)
            raise SystemExit(17)
        with self.assertRaises(SystemExit):
            self.start(model=RoundModel(), executor=crash)
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_research WHERE session_id=%s', (self.plan['id'],)).fetchone()
        class Later:
            @staticmethod
            def now(tz):
                return datetime.now(timezone.utc) + timedelta(hours=1)
        with patch('decision_room.agent.research_graph.datetime', Later):
            result = research.resume(self.config, self.business, run['id'], model=RoundModel())
        self.assertEqual(result['status'], 'partial')
        self.assertIn('tiempo', result['issue'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 1)
        self.assertEqual(len(result['model_calls']), 1)
        self.assertEqual(result['steps'][0]['execution']['status'], 'completed')

    def test_recovery_in_second_round_reuses_write_ahead_action(self):
        seen = 0
        def crash(*args, **kwargs):
            nonlocal seen
            result = execute(*args, **kwargs)
            seen += 1
            if seen == 2:
                raise SystemExit(17)
            return result
        with self.assertRaises(SystemExit):
            self.start(model=RoundModel(), executor=crash)
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_research WHERE session_id=%s', (self.plan['id'],)).fetchone()
        result = research.resume(self.config, self.business, run['id'], model=RoundModel())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['model_calls']), 6)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 3)

    def test_blocked_and_discarded_work_remain_explicit(self):
        result = self.start(model=RoundModel(blocked=True, discard=True))
        self.assertEqual(result['status'], 'partial')
        states = {i['key']: i['research_status'] for i in result['investigations']}
        self.assertEqual(states, dict(sales='candidate', major='pending_definition', minor='discarded'))
        major = next(i for i in result['investigations'] if i['key'] == 'major')
        self.assertEqual(major['definitions_needed'], ['Confirmar si hay costes.'])
        self.assertTrue(next(i for i in result['investigations'] if i['key'] == 'minor')['resolution'])

    def test_followup_contract_rejects_invented_evidence_tables_dependencies_and_duplicates(self):
        result = self.start(model=RoundModel(), max_rounds=1)
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_research WHERE id=%s', (result['id'],)).fetchone()
        snapshot = agenda(run['snapshot'], [])
        action = result['steps'][1]['action']
        obs = [{'investigation_key': 'sales', 'status': 'completed', 'result': {'metrics': {'total': '80'}}}]
        for field, value in [('basis_metric_keys', ['fake']), ('table_ids', ['fake']), ('depends_on', ['fake']), ('key', 'sales')]:
            with self.subTest(field=field):
                bad = deepcopy(action)
                bad['followups'][0][field] = value
                with self.assertRaises(ValueError):
                    validate_research_action(bad, snapshot, obs, [], run['options'])

    def test_partial_report_includes_controller_scope_note(self):
        from test_review import DialogueModel
        result = self.start(model=RoundModel(), max_rounds=1)
        # Review fixtures use another model identity, retain session model as required.
        analyst, reviewer = PartialReview(), PartialReview()
        analyst.identity = self.model.identity
        reviewed = review.start(self.config, self.business, result['id'], request_key='partial-review', analyst=analyst, reviewer=reviewer)
        self.assertTrue(reviewed['publishable'])
        self.assertTrue(any('0 de 1' in l and '1 parciales' in l for l in reviewed['report']['limitations']))
        self.assertEqual(sum(q['status'] == 'unavailable' for q in reviewed['report']['question_coverage']), 2)
        self.assertFalse(analyst.contexts[-1]['delivery_capabilities']['execution_artifact_downloads'])
        self.assertFalse(reviewer.contexts[-1]['delivery_capabilities']['execution_artifact_downloads'])

    def test_customer_coverage_never_reinjects_internal_stopping_reason(self):
        from decision_room.agent.research_agenda import limitation
        summary = {'investigations': [{'key': 'one', 'question': 'Compare units'}],
                   'complete': False, 'stop_reason': 'No useful numerical work remains; private execution detail'}
        for status in ('answered', 'unavailable'):
            note = limitation(summary, {'question_coverage': [{'investigation_key': 'one', 'status': status}]})
            self.assertNotIn(summary['stop_reason'], note)
            self.assertNotIn('La investigación se detuvo', note)
            self.assertIn('1 de 1' if status == 'answered' else 'Sin completar en esta entrega: Compare units', note)

    def test_controller_note_preserves_all_twelve_substantive_limitations(self):
        from test_review import DialogueModel
        class ManyLimits(PartialReview):
            def generate_analyst_review(self, context, correction=None):
                raw, usage = super().generate_analyst_review(context, correction)
                if raw.get('report'):
                    raw['report']['limitations'] = ['Límite sustantivo ' + str(i) for i in range(12)]
                return raw, usage
        result = self.start(model=RoundModel(), max_rounds=1)
        roles = ManyLimits()
        reviewed = review.start(self.config, self.business, result['id'], request_key='all-limits', analyst=roles, reviewer=roles)
        self.assertTrue(reviewed['publishable'])
        self.assertEqual(len(reviewed['report']['limitations']), 13)
        self.assertEqual(reviewed['report']['limitations'][:12], ['Límite sustantivo ' + str(i) for i in range(12)])

    def test_computed_candidates_do_not_force_report_delivery_complete(self):
        class LimitedDelivery(PartialReview):
            def generate_analyst_review(self, context, correction=None):
                raw, usage = super().generate_analyst_review(context, correction)
                if raw.get('report'):
                    for entry in raw['report']['question_coverage']:
                        if entry['investigation_key'] != 'sales':
                            entry.update(status='unavailable', claim_keys=[], explanation='Detalle no incluido en esta entrega.')
                    raw['report']['limitations'].append('Cobertura de investigación: nota anterior que no describe la entrega.')
                    for entry in raw['report']['owner_coverage']:
                        entry.update(status='partial', explanation='Total disponible; detalle no incluido en esta entrega.')
                return raw, usage
        result = self.start(model=RoundModel())
        self.assertEqual(result['status'], 'completed')
        roles = LimitedDelivery()
        reviewed = review.start(self.config, self.business, result['id'], request_key='partial-delivery', analyst=roles, reviewer=roles)
        self.assertTrue(reviewed['publishable'])
        notes = reviewed['report']['limitations']
        self.assertEqual(sum(l.startswith('Cobertura del encargo:') for l in notes), 1)
        self.assertTrue(any('0 de 1' in l and '1 parciales' in l for l in notes))
        self.assertFalse(any('Cobertura de investigación:' in l or 'no queda trabajo' in l for l in notes))


if __name__ == '__main__':
    unittest.main()
