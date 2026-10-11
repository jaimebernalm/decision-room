"""M5 whole-lot decision fixtures: read-only ledgers, run files and valid evaluations."""
import copy
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from decision_room.agent import api_budget
from decision_room.config import ROOT
from decision_room.engine import blocks

sys.path.insert(0, str(ROOT / 'scripts/f5'))
spec = importlib.util.spec_from_file_location('m5_analyze', ROOT / 'scripts/f5/m5_analyze.py')
m5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m5)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class M5Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.trial = self.root / 'trial'; self.results = self.root / 'results'
        self.budget = self.root / 'budget.sqlite'; self.storage = self.root / 'storage'
        api_budget.Ledger.create(self.budget, cap_micro_usd=5_000_000, scope_cap_micro_usd=1_000_000,
                                explicit_http_rejections=True, scope_uncertainty=True)
        self.key = dict(attempts=[], reports={}, pairs={}); self.jobs = []
        projection = blocks.parse(json.dumps({'version': blocks.VERSION, 'titulo': 'Informe sintético', 'bloques': [
            {'tipo': 'prioridad', 'titulo': 'Observar', 'bloques': [{'tipo': 'texto', 'contenido': 'La cifra es 50 unidades.'}]}]}).encode())
        for business in m5.BUSINESSES:
            for repetition in range(1, 6):
                kits = {}
                for arm in m5.ARMS:
                    code = f'{business}-{repetition}-{arm}'; kit = f'R{len(self.key["reports"]):03d}'
                    job = dict(code=code, job_id='j-'+code, business_id='b-'+code, business_key=business,
                               repetition=repetition, arm='opencode' if arm == 'v1' else 'blocks')
                    self.jobs.append(job)
                    self.key['attempts'].append(dict(code=code, business=business, repetition=repetition, arm=arm,
                                                     status='completed', delivered=True, trial=str(self.trial)))
                    self.key['reports'][kit] = dict(code=code, business=business, repetition=repetition, arm=arm)
                    kits[arm] = kit
                    run = self.run_dir(code)
                    save(run / 'started.json', {'job': job})
                    save(run / 'result.json', dict(engine_run_id='r-'+code, seconds=180))
                    p4 = self.storage / job['business_id'] / 'provider-budgets' / ('r-'+code+'.sqlite')
                    api_budget.Ledger.create(p4, cap_micro_usd=1_000_000, scope_cap_micro_usd=1_000_000)
                    for ledger in (self.budget, p4):
                        with sqlite3.connect(ledger) as db:
                            db.execute('INSERT INTO calls(id,scope,state,reserved,charged) VALUES (?,?,?,?,?)',
                                       (code, 'engine:r-'+code, 'settled', 358_500_000, 100_000_000))
                    if arm == 'blocks':
                        save(run / 'informe-bloques.json', projection)
                        save(run / 'checks-full.json', dict(state='complete', items=[dict(block_id='b1-1', quote='50 unidades', status='confirmed', located=True)]))
                    self.audit(kit)
                    save(self.results / f'judge-{kit}.json', dict(report=kit, **{f'S{i}': 1 for i in range(1, 6)}, S6=0))
                pair = f'{business}-{repetition}'
                self.key['pairs'][pair] = dict(order=['v1', 'blocks'] if repetition % 2 else ['blocks', 'v1'], kits=kits, images=8)
                for role in m5.ROLES:
                    self.pick(pair, role, 'blocks')
        save(self.trial / 'manifest.json', dict(budget_path=str(self.budget), config=dict(storage=str(self.storage), dsn='unused'), jobs=self.jobs))

    def run_dir(self, code):
        return self.trial / 'runs' / code

    def audit(self, kit, verdict='correcta'):
        claims = [dict(texto='La cifra es 50 unidades.', cita='50 unidades', seccion='prioridad', tipo='cifra', calculable=True, veredicto=verdict)]
        den = dict(prioridad_calculables=1, prioridad_correctas=int(verdict == 'correcta'), resto_calculables=0, resto_correctas=0)
        save(self.results / f'audit-{kit}.json', dict(report=kit, claims=claims, denominadores=den))
        material = verdict in ('material', 'critico')
        save(self.results / f'group-{kit}.json', dict(report=kit, grupos=[dict(afirmaciones=[0], nivel=verdict)] if material else [], material_distintos=int(material), criticos_distintos=int(verdict == 'critico')))

    def pick(self, pair, role, choice):
        order = self.key['pairs'][pair]['order']
        save(self.results / f'{role}-{pair}.json', dict(pair=pair, eleccion='empate' if choice == 'tie' else 'AB'[order.index(choice)], motivo='Juicio sintético'))

    def attempt(self, code):
        return next(a for a in self.key['attempts'] if a['code'] == code)

    def kit(self, code):
        return next(k for k, v in self.key['reports'].items() if v['code'] == code)

    def lose(self, code, *, not_run=False):
        a = self.attempt(code); a.update(delivered=False, status='not_run' if not_run else 'failed')
        kit = self.kit(code); del self.key['reports'][kit]
        self.key['pairs'][f'{a["business"]}-{a["repetition"]}']['kits'][a['arm']] = None
        if not_run:
            (self.run_dir(code) / 'started.json').unlink(); (self.run_dir(code) / 'result.json').unlink()
            with sqlite3.connect(self.budget) as db:
                db.execute('DELETE FROM calls WHERE id=?', (code,))
        else:
            value = json.loads((self.run_dir(code) / 'result.json').read_text()); value['issue'] = 'provider_failed'
            save(self.run_dir(code) / 'result.json', value)

    def result(self):
        with patch.object(m5, 'load_engine_runs', return_value={}):
            return m5.analyze(self.key, self.results)

    def test_complete_improvement_is_read_only(self):
        before = hashlib.sha256(self.budget.read_bytes()).hexdigest()
        value = self.result()
        self.assertEqual(value['outcome'], 'mejor')
        self.assertEqual(value['conditions'], dict.fromkeys('abcdef', True))
        self.assertEqual(value['reading']['points'], 20)
        self.assertEqual(before, hashlib.sha256(self.budget.read_bytes()).hexdigest())
        self.assertNotIn('usd', self.key['attempts'][0])

    def test_balanced_order_ties_and_exact_thresholds(self):
        for pair in self.key['pairs']:
            for role in m5.ROLES:
                self.pick(pair, role, 'tie')
        self.assertEqual(self.result()['outcome'], 'no_peor')
        for pair, role in [('herbolario-1','owner'), ('herbolario-2','owner'), ('clinica-1','owner')]:
            self.pick(pair, role, 'blocks')
        self.assertEqual(self.result()['reading']['points'], 11.5)
        self.assertEqual(self.result()['outcome'], 'no_peor')
        self.pick('clinica-2', 'owner', 'blocks')
        self.assertEqual(self.result()['outcome'], 'mejor')
        for pair in self.key['pairs']:
            for role in m5.ROLES:
                self.pick(pair, role, 'v1')
        self.assertFalse(self.result()['conditions']['c'])
        self.assertEqual(self.result()['outcome'], 'no_pasa')

    def test_single_and_both_deliveries_use_fixed_positions(self):
        self.lose('herbolario-1-v1')
        self.lose('herbolario-2-blocks')
        self.lose('herbolario-3-v1'); self.lose('herbolario-3-blocks')
        r = self.result()['reading']
        self.assertEqual((r['denominator'], r['reader_positions'], r['delivery_positions']), (20, 14, 6))
        points = {p['pair']: p['points'] for p in r['positions']}
        self.assertEqual([points[f'herbolario-{i}'] for i in range(1, 4)], [1, 0, 0.5])
        self.assertEqual(r['points'], 17)

    def test_all_losses_count_with_plus_one_threshold(self):
        self.lose('herbolario-1-blocks')
        self.assertTrue(self.result()['conditions']['a'])
        self.lose('herbolario-2-blocks')
        r = self.result(); self.assertFalse(r['conditions']['a'])
        self.assertEqual(r['businesses']['herbolario']['arms']['blocks']['losses_by_cause'], {'provider_failed': 2})

    def test_not_run_is_incomplete_without_zero_cost_or_loss(self):
        self.lose('clinica-5-blocks', not_run=True)
        r = self.result(); self.assertEqual(r['outcome'], 'incompleto')
        self.assertIsNone(r['conditions']['a']); self.assertIsNone(r['conditions']['c'])
        a = next(a for a in r['attempts'] if a['code'] == 'clinica-5-blocks')
        self.assertIsNone(a['usd']); self.assertIsNone(a['seconds'])
        self.assertEqual(r['businesses']['clinica']['arms']['blocks']['losses'], 0)

    def test_missing_capture_and_reader_are_not_delivery_ties(self):
        self.key['pairs']['herbolario-1']['reading'] = 'incomplete_over_image_limit'
        r = self.result(); self.assertIsNone(r['conditions']['c']); self.assertEqual(r['outcome'], 'incompleto')
        del self.key['pairs']['herbolario-1']['reading']
        (self.results / 'advisor-herbolario-1.json').unlink()
        self.assertIsNone(self.result()['reading']['points'])

    def test_critical_even_with_warning_fails_exactness(self):
        code = 'herbolario-1-blocks'; self.audit(self.kit(code), 'critico')
        save(self.run_dir(code) / 'checks-full.json', dict(state='complete', items=[dict(block_id='b1-1', quote='50 unidades', status='discrepancy', located=True)]))
        r = self.result(); self.assertFalse(r['conditions']['b'])
        self.assertEqual(r['businesses']['herbolario']['arms']['blocks']['checker']['critical_warned'], 1)

    def test_material_means_compare_within_business(self):
        self.audit(self.kit('herbolario-1-blocks'), 'material')
        for i in range(1, 6):
            self.audit(self.kit(f'clinica-{i}-v1'), 'material')
        self.assertFalse(self.result()['conditions']['b'])  # pooling would hide this worsening

    def test_missing_judge_does_not_publish_partial_mean(self):
        (self.results / f'judge-{self.kit("clinica-1-blocks")}.json').unlink()
        r = self.result(); self.assertIsNone(r['conditions']['d'])
        self.assertIsNone(r['businesses']['clinica']['arms']['blocks']['signal_mean'])
        self.assertEqual(r['outcome'], 'incompleto')

    def test_signals_half_point_tolerance_per_business(self):
        for i in range(1,6):
            kit=self.kit(f'clinica-{i}-blocks')
            save(self.results / f'judge-{kit}.json', dict(report=kit, **{f'S{i}': 0 for i in range(1,6)}, S6=0))
        self.assertFalse(self.result()['conditions']['d'])

    def test_terminal_uncertainty_is_a_charged_bound_not_pending(self):
        code = 'herbolario-1-blocks'; self.lose(code)
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE calls SET state='uncertain', charged=reserved WHERE id=?", (code,))
        r=self.result(); a=next(a for a in r['attempts'] if a['code']==code)
        self.assertEqual(a['uncertain_nano'], 358_500_000); self.assertEqual(a['pending'], 0)
        self.assertEqual(a['known_usage_nano'], 0); self.assertTrue(r['conditions']['e'])
        self.assertEqual(r['businesses']['herbolario']['arms']['blocks']['cost_n'], 5)

    def test_reserved_source_is_unaccredited_and_unknown_is_not_zero(self):
        code='herbolario-1-blocks'
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE calls SET state='reserved', charged=reserved WHERE id=?", (code,))
        self.assertIsNone(self.result()['conditions']['e'])
        save(self.run_dir(code) / 'result.json', dict(seconds=180))
        with patch.object(m5,'load_engine_runs',return_value=None):
            r=m5.analyze(self.key,self.results)
        a=next(a for a in r['attempts'] if a['code']==code)
        self.assertIsNone(a['usd']); self.assertIsNone(a['calls']); self.assertIsNone(r['conditions']['e'])

    def test_no_delivery_and_empty_examined_denominators_are_not_passes(self):
        for i in range(1,6):
            self.lose(f'herbolario-{i}-blocks')
        r=self.result()
        for condition in 'bdf': self.assertIsNone(r['conditions'][condition])
        self.assertEqual(r['outcome'], 'incompleto')

    def test_false_alarm_requires_positive_denominator_per_business(self):
        for i in range(1,6):
            save(self.run_dir(f'clinica-{i}-blocks') / 'checks-full.json', dict(state='complete',items=[dict(block_id='b1-1',quote='50 unidades',status='unverifiable',located=True)]))
        self.assertIsNone(self.result()['conditions']['f'])
        save(self.run_dir('clinica-1-blocks') / 'checks-full.json', dict(state='complete',items=[dict(block_id='b1-1',quote='50 unidades',status='discrepancy',located=True)]))
        r=self.result(); self.assertFalse(r['conditions']['f'])
        self.assertEqual(r['businesses']['clinica']['arms']['blocks']['checker']['false_alarms'], 1)

    def test_coverage_and_ambiguous_quotes_are_never_confirmations(self):
        for i in range(1,6):
            run=self.run_dir(f'clinica-{i}-blocks')
            p=json.loads((run/'informe-bloques.json').read_text()); p['blocks'][0]['blocks'][0]['content'][0]['spans'][0]['text']='50 unidades y 50 unidades'
            save(run/'informe-bloques.json',p)
        self.assertIsNone(self.result()['conditions']['f'])

    def test_cost_factor_and_hard_ceiling_are_distinct(self):
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE calls SET charged=210000000 WHERE scope LIKE 'engine:r-clinica-%-blocks'")
        self.assertFalse(self.result()['conditions']['e'])
        with sqlite3.connect(self.budget) as db: db.execute('UPDATE policy SET cap=6000000000')
        self.assertFalse(self.result()['conditions']['e'])
        p4=self.storage/'b-herbolario-1-blocks'/'provider-budgets'/'r-herbolario-1-blocks.sqlite'
        with sqlite3.connect(p4) as db: db.execute('UPDATE policy SET cap=2000000000')
        self.assertFalse(self.result()['attempts'][1]['p4_limits'])

    def test_bad_schema_and_empty_correct_audit_do_not_become_zeros(self):
        kit=self.kit('herbolario-1-blocks')
        save(self.results/f'audit-{kit}.json',dict(report=kit,claims=[]))
        r=self.result(); self.assertIsNone(r['conditions']['b']); self.assertEqual(r['outcome'],'incompleto')

    def test_terminal_rejection_is_separate_from_usage_and_uncertainty(self):
        code='herbolario-1-blocks'; self.lose(code)
        with sqlite3.connect(self.budget) as db:
            db.execute("UPDATE calls SET state='rejected', charged=reserved WHERE id=?", (code,))
        r=self.result(); a=next(a for a in r['attempts'] if a['code']==code)
        self.assertEqual(a['rejected_nano'], 358_500_000); self.assertEqual(a['uncertain_nano'], 0)
        self.assertEqual(a['known_usage_nano'], 0); self.assertTrue(r['conditions']['e'])

    def test_p4_missing_or_pending_cannot_accredit_cost(self):
        p4=self.storage/'b-herbolario-1-blocks'/'provider-budgets'/'r-herbolario-1-blocks.sqlite'
        with sqlite3.connect(p4) as db: db.execute("UPDATE calls SET state='reserved',charged=reserved")
        self.assertIsNone(self.result()['conditions']['e'])
        p4.unlink()
        self.assertIsNone(self.result()['conditions']['e'])

    def test_unattributed_calls_and_missing_manifest_make_trial_incomplete(self):
        with sqlite3.connect(self.budget) as db:
            db.execute('INSERT INTO calls(id,scope,state,reserved,charged) VALUES (?,?,?,?,?)',
                       ('extra','engine:unknown','settled',358_500_000,100_000))
        self.assertEqual(self.result()['outcome'],'incompleto')
        (self.trial/'manifest.json').unlink()
        r=self.result(); self.assertEqual(r['outcome'],'incompleto'); self.assertIsNone(r['conditions']['e'])

    def test_duplicate_json_fields_are_rejected_not_repaired(self):
        kit=self.kit('herbolario-1-blocks')
        (self.results/f'judge-{kit}.json').write_text('{"report":"'+kit+'","S1":1,"S1":2}')
        r=self.result(); self.assertIsNone(r['conditions']['d']); self.assertEqual(r['outcome'],'incompleto')

    def test_duplicate_missing_attempt_and_wrong_pair_report_refused(self):
        key=copy.deepcopy(self.key); key['attempts'][1]=key['attempts'][0]
        with self.assertRaises(ValueError): m5.analyze(key,self.results)
        key=copy.deepcopy(self.key); key['attempts'].pop()
        with self.assertRaises(ValueError): m5.analyze(key,self.results)
        self.key['pairs']['herbolario-1']['kits']['blocks']=self.key['pairs']['clinica-1']['kits']['blocks']
        self.assertIsNone(self.result()['conditions']['c'])


if __name__=='__main__': unittest.main()
