"""Real PostgreSQL/Docker fan-out, recovery and shared budget boundaries."""
from copy import deepcopy
from threading import Barrier, Lock
from time import sleep
import unittest

from psycopg.types.json import Jsonb

import test_research as base
from decision_room.agent import research
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_agenda import agenda
from decision_room.database import connect
from decision_room.execution import execute


class TeamModel(base.ResearchModel):
    def generate_research(self, context, correction=None):
        if context['budgets'].get('worker_assignment'):
            return super().generate_research(context, correction)
        empty = dict(investigation_key='', code='', table_ids=[], metric_keys=[], followups=[], summary='Encargos independientes y síntesis.')
        finished = {f['investigation_key'] for f in context['findings']}
        available = [i for i in context['plan']['investigations'] if i['status'] == 'ready' and i['key'] not in finished]
        if available:
            return dict(empty, action='delegate', assignments=[
                {'investigation_key': i['key'], 'instruction': 'Calcular con evidencia y límites.'}
                for i in available]), {}
        return dict(empty, action='finish', synthesis={
            'priorities': [dict(investigation_key=f['investigation_key'], reason='Útil para la pregunta.', next_check='Contrastar alcance con propietario.')
                           for f in context['findings'] if f['status'] == 'candidate'],
            'excluded': [], 'disagreements': []}), {}


class ParallelTests(unittest.TestCase):
    setUpClass = classmethod(base.ResearchTests.setUpClass.__func__)
    tearDownClass = classmethod(base.ResearchTests.tearDownClass.__func__)

    def setUp(self):
        base.ResearchTests.setUp(self)
        with connect(self.config) as db:
            row = db.execute('SELECT proposal FROM agent_revisions WHERE session_id=%s', (self.plan['id'],)).fetchone()
            proposal = row['proposal']
            proposal['investigations'].append({**proposal['investigations'][0], 'key': 'units', 'question': 'Unidades vendidas'})
            db.execute('UPDATE agent_revisions SET proposal=%s WHERE session_id=%s', (Jsonb(proposal), self.plan['id']))
        self.model = TeamModel()

    def start(self, **kwargs):
        return base.ResearchTests.start(self, delegation=True, **kwargs)

    def test_actual_overlap_evidence_synthesis_and_idempotent_merge(self):
        barrier = Barrier(2)
        def together(*args, **kwargs):
            barrier.wait(timeout=10)
            return execute(*args, **kwargs)
        result = self.start(executor=together, max_parallel=2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['branches']), 2)
        self.assertEqual(len(result['model_calls']), 6)
        self.assertEqual([f['investigation_key'] for f in result['findings']], ['sales', 'units'])
        values = [s['execution']['result']['metrics']['total'] for s in result['steps'] if s['action']['action'] == 'execute']
        self.assertEqual(values, ['80.0000', '5.00'])
        self.assertEqual(len(result['synthesis']['priorities']), 2)
        self.assertFalse(result['publishable'])
        again = research.resume(self.config, self.business, result['id'], model=self.model)
        self.assertEqual(len(again['steps']), len(result['steps']))
        self.assertEqual(len(again['model_calls']), 6)
        self.assertEqual([s['execution_id'] for s in again['steps']], [s['execution_id'] for s in result['steps']])

    def test_sequential_mode_keeps_assignments_and_never_overlaps(self):
        active = maximum = 0
        lock = Lock()
        def measured(*args, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                sleep(.03)
                return execute(*args, **kwargs)
            finally:
                with lock:
                    active -= 1
        result = self.start(max_parallel=1, executor=measured)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(maximum, 1)
        self.assertEqual(len(result['branches']), 2)

    def test_interrupted_branch_keeps_successful_sibling_and_reuses_execution(self):
        lock = Lock()
        crashed = False
        def crash_once(*args, **kwargs):
            nonlocal crashed
            result = execute(*args, **kwargs)
            with lock:
                if not crashed:
                    crashed = True
                    raise SystemExit(17)
            return result
        with self.assertRaises(SystemExit):
            self.start(executor=crash_once)
        with connect(self.config) as db:
            parent = db.execute("SELECT * FROM agent_research WHERE session_id=%s AND request_key='research'", (self.plan['id'],)).fetchone()
            children = db.execute('SELECT r.status FROM agent_research r JOIN agent_research_branches b ON b.child_id=r.id WHERE b.parent_id=%s', (parent['id'],)).fetchall()
            self.assertIn('completed', [r['status'] for r in children])
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 2)
        result = research.resume(self.config, self.business, parent['id'], model=self.model)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['model_calls']), 6)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 2)

    def test_recovery_after_atomic_merge_reuses_children_and_step_ids(self):
        from unittest.mock import patch
        from decision_room.agent.parallel_research import dispatch
        def crash(*args, **kwargs):
            dispatch(*args, **kwargs)
            raise SystemExit(18)
        with patch('decision_room.agent.parallel_research.dispatch', crash), self.assertRaises(SystemExit):
            self.start()
        with connect(self.config) as db:
            parent = db.execute("SELECT id FROM agent_research WHERE session_id=%s AND request_key='research'", (self.plan['id'],)).fetchone()['id']
            before = db.execute('SELECT step,execution_id FROM agent_research_steps WHERE research_id=%s ORDER BY step', (parent,)).fetchall()
        result = research.resume(self.config, self.business, parent, model=self.model)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['model_calls']), 6)
        self.assertEqual([(s['step'], s['execution_id']) for s in result['steps'][:len(before)]],
                         [(s['step'], s['execution_id']) for s in before])

    def test_crash_after_model_response_reuses_decision_context(self):
        from unittest.mock import patch
        with patch('decision_room.agent.research_graph.validate_research_action', side_effect=SystemExit(19)), self.assertRaises(SystemExit):
            self.start()
        with connect(self.config) as db:
            parent = db.execute("SELECT id FROM agent_research WHERE session_id=%s AND request_key='research'", (self.plan['id'],)).fetchone()['id']
        result = research.resume(self.config, self.business, parent, model=self.model)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['model_calls']), 6)

    def test_global_call_execution_and_turn_reservations(self):
        result = self.start(max_model_calls=8, max_turns=8, max_executions=2)
        self.assertEqual(result['status'], 'completed')
        self.assertLessEqual(len(result['model_calls']), 8)
        self.assertLessEqual(len(result['steps']), 8)
        self.assertEqual(result['coverage']['executions_requested'], 2)
        for branch in result['branches']:
            self.assertEqual(branch['options']['max_executions'], 1)
            self.assertEqual(branch['options']['max_model_calls'], 2)
            self.assertFalse(branch['options']['delegation'])

    def test_worker_finish_also_consumes_global_decision_budget(self):
        class EarlyStop(TeamModel):
            def generate_research(self, context, correction=None):
                if context['budgets'].get('worker_assignment'):
                    return dict(action='finish', investigation_key='', table_ids=[], code='', metric_keys=[], summary='No se obtuvo resultado.'), {}
                return super().generate_research(context, correction)
        result = self.start(model=EarlyStop(), max_turns=8)
        self.assertEqual(result['status'], 'partial')
        with connect(self.config) as db:
            from decision_room.agent.parallel_research import decisions
            self.assertLessEqual(decisions(db, result['id']), 8)
        self.assertLessEqual(len(result['model_calls']), 8)

    def test_no_budget_no_worker_started(self):
        result = self.start(max_model_calls=4)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['branches'], [])
        self.assertEqual(len(result['model_calls']), 1)

    def test_worker_followup_waits_for_parent_evidence_and_next_coordinator_round(self):
        class Directed(TeamModel):
            def generate_research(self, context, correction=None):
                raw, usage = super().generate_research(context, correction)
                task = context['budgets'].get('worker_assignment')
                if task and task['investigation_key'] == 'units' and raw['action'] == 'record_candidate':
                    parent = context['plan']['investigations'][0]
                    raw['followups'] = [{k: v for k, v in dict(parent, key='units__verify', question='Verificar alcance de unidades',
                        depends_on=['units'], stage='verify', basis_metric_keys=['total'],
                        focus=dict(segment='Unidades', period='Extracto', comparison='Verificar alcance', decision_value='Confirmar cobertura del extracto.'),
                        priority=dict(relevance=5,magnitude=3,reliability=5,cost=1,reason='Comprobar alcance.')).items()
                        if k not in ('round', 'parent_key')}]
                return raw, usage
        result = self.start(model=Directed())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['branches']), 3)
        descendant = next(i for i in result['investigations'] if i['key'] == 'units__verify')
        self.assertEqual((descendant['round'], descendant['parent_key']), (2, 'units'))
        self.assertEqual([b['dispatch_step'] for b in result['branches'][:2]], [1, 1])
        self.assertGreater(result['branches'][2]['dispatch_step'], 1)
        with connect(self.config) as db:
            child = db.execute('SELECT snapshot FROM agent_research WHERE id=%s', (result['branches'][2]['child_id'],)).fetchone()
            shared = child['snapshot']['coordination']['findings']
            self.assertIn('units', [f['investigation_key'] for f in shared])

    def test_principal_can_expand_worker_evidence_without_reregistering_it(self):
        class Expand(TeamModel):
            def generate_research(self, context, correction=None):
                if not context['budgets'].get('worker_assignment') and len(context['findings']) == 2 and not any(i['key'] == 'units__focus' for i in context['plan']['investigations']):
                    task = next(i for i in context['plan']['investigations'] if i['key'] == 'units')
                    child = {k: v for k, v in dict(task, key='units__focus', question='Profundizar en el segmento observado',
                        depends_on=['units'], stage='breakdown', basis_metric_keys=['total'],
                        focus=dict(segment='Unidades', period='Extracto', comparison='Desglose del grupo', decision_value='Localizar contribuciones al total.'),
                        priority=dict(relevance=5,magnitude=4,reliability=5,cost=1,reason='Contraste material.')).items()
                        if k not in ('round','parent_key')}
                    return dict(action='expand',investigation_key='units',table_ids=[],code='',metric_keys=['total'],
                                followups=[child],summary='Profundizar con la evidencia de la rama.'), {}
                return super().generate_research(context, correction)
        result = self.start(model=Expand())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([s['action']['action'] for s in result['steps']].count('expand'), 1)
        self.assertEqual([f['investigation_key'] for f in result['findings']].count('units'), 1)
        self.assertEqual(len(result['branches']), 3)
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_research WHERE id=%s', (result['id'],)).fetchone()
        raw = next(s['action'] for s in result['steps'] if s['action']['action'] == 'expand')
        with self.assertRaisesRegex(ValueError, 'Only the coordinator'):
            validate_research_action(raw, run['snapshot'], [], result['findings'],
                                     {**run['options'],'worker_assignment': {'investigation_key':'units'}})

    def test_sandbox_three_slots_same_request_lock_and_recovery_exclusion(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from decision_room.execution import recover_executions
        ready, release = Event(), Event()
        lock = Lock()
        entered = 0
        class HoldingBackend:
            manifest = {'test': 'slot boundary'}
            def run(self, *args):
                nonlocal entered
                with lock:
                    entered += 1
                    if entered == 3:
                        ready.set()
                release.wait(timeout=10)
                raise ValueError('Intentional test stop after slot admission.')
        with connect(self.config) as db:
            table = db.execute('SELECT id FROM prepared_tables WHERE analysis_id=%s', (self.analysis,)).fetchone()['id']
        def run(key):
            return execute(self.config, self.business, self.analysis, code='pass', tables={'t1': str(table)},
                           request_key=key, backend=HoldingBackend())
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(run, f'slot-{n}') for n in range(3)]
            try:
                self.assertTrue(ready.wait(timeout=10))
                with self.assertRaisesRegex(ValueError, 'capacity reached'):
                    run('fourth')
                with self.assertRaisesRegex(ValueError, 'already running'):
                    run('slot-0')
                with self.assertRaisesRegex(ValueError, 'controller is active'):
                    recover_executions(self.config, self.business)
            finally:
                release.set()
            self.assertTrue(all(f.result()['status'] == 'failed' for f in futures))

    def test_partial_worker_does_not_prevent_other_delivery(self):
        class OneBlocked(TeamModel):
            def generate_research(self, context, correction=None):
                assignment = context['budgets'].get('worker_assignment')
                if assignment and assignment['investigation_key'] == 'units':
                    return dict(action='block', investigation_key='units', code='', table_ids=[], metric_keys=[],
                                summary='Definición incompatible detectada en esta rama.'), {}
                return super().generate_research(context, correction)
        result = self.start(model=OneBlocked())
        self.assertEqual(result['status'], 'partial')
        self.assertEqual({f['investigation_key']: f['status'] for f in result['findings']}, {'sales': 'candidate', 'units': 'blocked'})
        self.assertEqual(len(result['synthesis']['priorities']), 1)

    def test_worker_namespace_recursion_scope_dependencies_and_disagreements(self):
        result = self.start()
        with connect(self.config) as db:
            run = db.execute('SELECT * FROM agent_research WHERE id=%s', (result['id'],)).fetchone()
        snapshot = agenda(run['snapshot'], [])
        delegate = result['steps'][0]['action']
        for mutate in ('recursive', 'unknown', 'duplicate', 'blocked', 'round'):
            raw, options, snap = deepcopy(delegate), deepcopy(run['options']), deepcopy(snapshot)
            if mutate == 'recursive':
                options['worker_assignment'] = raw['assignments'][0]
            elif mutate == 'unknown':
                raw['assignments'][0]['investigation_key'] = 'foreign'
            elif mutate == 'duplicate':
                raw['assignments'][1] = raw['assignments'][0]
            elif mutate == 'blocked':
                snap['proposal']['investigations'][0]['depends_on'] = ['unknown']
            else:
                snap['proposal']['investigations'][0]['round'] = 99
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_research_action(raw, snap, [], [], options)
        raw = deepcopy(result['steps'][-1]['action'])
        raw['synthesis']['disagreements'] = [dict(investigation_keys=['sales', 'units'], explanation='Bases incompatibles.', resolution='unresolved')]
        with self.assertRaisesRegex(ValueError, 'cannot be prioritized'):
            validate_research_action(raw, snapshot, [], result['findings'], {**run['options'], 'delegated': True})
        raw['synthesis']['excluded'] = raw['synthesis']['priorities']
        raw['synthesis']['priorities'] = []
        validate_research_action(raw, snapshot, [], result['findings'], run['options'])
        raw['synthesis'] = None
        with self.assertRaisesRegex(ValueError, 'synthesize'):
            validate_research_action(raw, snapshot, [], result['findings'], {**run['options'], 'delegated': True})
        foreign = base.create_business(self.config, 'Other')['id']
        with self.assertRaises(ValueError):
            research.show(self.config, foreign, result['id'])


if __name__ == '__main__':
    unittest.main()
