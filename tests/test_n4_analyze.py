"""N4 conservative auditor-checker cross-match (frozen before the batch)."""
import importlib.util
import sys
import unittest
import unittest.mock

from decision_room.config import ROOT
from decision_room.engine import blocks
from tests.test_engine_blocks import doc, raw

sys.path.insert(0, str(ROOT / 'scripts/f5'))
spec = importlib.util.spec_from_file_location('n4_analyze', ROOT / 'scripts/f5/n4_analyze.py')
n4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(n4)

PROJECTION = blocks.parse(raw(doc(
    {'tipo': 'prioridad', 'titulo': 'Uno', 'bloques': [{'tipo': 'texto', 'contenido': 'Magnesio baja a 636 unidades. Web sube 50 unidades.'}]},
    {'tipo': 'prioridad', 'titulo': 'Dos', 'bloques': [{'tipo': 'texto', 'contenido': 'La web sube 50 unidades otra vez.'}]})))


class CrossMatchTests(unittest.TestCase):
    def setUp(self):
        self.priorities = n4.priority_texts(PROJECTION)

    def test_located_final_discrepancy_warns(self):
        items = [{'block_id': 'b1-1', 'quote': 'Magnesio baja a 636 unidades', 'status': 'discrepancy', 'located': True}]
        self.assertTrue(n4.warned('636 unidades', self.priorities, items))

    def test_repeated_quote_is_never_warned(self):
        items = [{'block_id': 'b1-1', 'quote': 'Web sube 50 unidades', 'status': 'discrepancy', 'located': True}]
        self.assertFalse(n4.warned('50 unidades', self.priorities, items))

    def test_coverage_and_other_priority_and_unverifiable_are_not_warnings(self):
        coverage = [{'block_id': 'b1', 'quote': '636 unidades', 'status': 'discrepancy', 'coverage': True, 'located': True}]
        other = [{'block_id': 'b2-1', 'quote': '636 unidades', 'status': 'discrepancy', 'located': True}]
        unlocated = [{'block_id': 'b1', 'quote': '636 unidades', 'status': 'discrepancy', 'located': False}]
        unverifiable = [{'block_id': 'b1-1', 'quote': '636 unidades', 'status': 'unverifiable'}]
        for items in (coverage, other, unverifiable, unlocated):
            self.assertFalse(n4.warned('636 unidades', self.priorities, items))
        self.assertFalse(n4.warned(None, self.priorities, unverifiable))

    def test_addressed_counts_confirmed_items_for_false_alarm_denominator(self):
        items = [{'block_id': 'b1-1', 'quote': '636 unidades', 'status': 'confirmed', 'located': True}]
        self.assertEqual(len(n4.addressed('Magnesio baja a 636 unidades', self.priorities, items)), 1)



class FullRuleTests(unittest.TestCase):
    """Synthetic 2 businesses x 2 arms x 1 repetition: kits key, evaluator outputs, run files, ledger."""
    def build(self, *, critical_cita='636 unidades', checker_hit=True, unsettled=False, blocks_pick='blocks', not_run=False):
        import json, sqlite3, tempfile
        from pathlib import Path
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); trial = root / 'trial'
        ledger = root / 'ledger.sqlite'
        db = sqlite3.connect(ledger)
        db.execute('CREATE TABLE calls(scope, charged, state)')
        jobs, attempts, reports, pairs = [], [], {}, {}
        for business in n4.BUSINESSES:
            for arm, label in (('opencode', 'v1'), ('blocks', 'blocks')):
                code = f'{business}-1-{arm}'
                run = trial / 'runs' / code; run.mkdir(parents=True)
                skip = not_run and business == 'clinica' and arm == 'blocks'
                if not skip:
                    (run / 'result.json').write_text(json.dumps(dict(engine_run_id=f'r-{code}', seconds=180 if arm == 'opencode' else 300)))
                    db.execute('INSERT INTO calls VALUES (?,?,?)', (f'engine:r-{code}', 150_000_000, 'reserved' if unsettled else 'settled'))
                jobs.append(dict(code=code, job_id=f'j-{code}', business_key=business, repetition=1, arm=arm))
                kit = f'R{len(reports)}'
                attempts.append(dict(code=code, business=business, repetition=1, arm=label, delivered=not skip,
                                     status='not_run' if skip else 'completed', trial=str(trial)))
                if not skip:
                    reports[kit] = dict(code=code, business=business, repetition=1, arm=label)
                if arm == 'blocks' and not skip:
                    (run / 'informe-bloques.json').write_text(json.dumps(PROJECTION))
                    items = [dict(block_id='b1-1', quote='Magnesio baja a 636 unidades', status='discrepancy' if checker_hit else 'confirmed', located=True),
                             dict(block_id='b1-1', quote='Web sube 50 unidades', status='confirmed', located=True)]
                    (run / 'checks-full.json').write_text(json.dumps(dict(state='complete', items=items)))
            pairs[f'{business}-1'] = dict(order=['v1', 'blocks'], kits={'v1': 'x', 'blocks': None if (not_run and business == 'clinica') else 'y'})
        db.commit(); db.close()
        (trial / 'manifest.json').write_text(json.dumps(dict(budget_path=str(ledger), config=dict(dsn='dbname=none host=/nonexistent'), jobs=jobs)))
        key = dict(attempts=attempts, reports=reports, pairs=pairs)
        (root / 'key.json').write_text(json.dumps(key))
        results = root / 'results'; results.mkdir()
        for kit, info in reports.items():
            blocks_arm = info['arm'] == 'blocks'
            claims = [dict(seccion='prioridad', calculable=True, veredicto='correcta', cita='Web sube 50 unidades')]
            if blocks_arm and critical_cita:
                claims.append(dict(seccion='prioridad', calculable=True, veredicto='critico', cita=critical_cita))
            (results / f'audit-{kit}.json').write_text(json.dumps(dict(claims=claims)))
            (results / f'group-{kit}.json').write_text(json.dumps(dict(material_distintos=0, criticos_distintos=int(blocks_arm and bool(critical_cita)))))
            (results / f'judge-{kit}.json').write_text(json.dumps({**{f'S{i}': 1 for i in range(1, 6)}, 'S6': 0}))
        for business in n4.BUSINESSES:
            for role in ('owner', 'advisor'):
                (results / f'{role}-{business}-1.json').write_text(json.dumps(dict(eleccion='B' if blocks_pick == 'blocks' else 'A')))
        seeded = root / 'seeded.json'
        seeded.write_text(json.dumps(dict(seeded=[dict(detected=True, checked=True), dict(detected=True, checked=True)])))
        out = root / 'out.json'
        with unittest.mock.patch.object(n4, 'load_engine_runs', return_value={}):
            n4.main(root / 'key.json', results, out, seeded)
        return json.loads(out.read_text())

    def test_warned_critical_passes_and_unwarned_fails_b(self):
        self.assertEqual(self.build()['outcome'], 'pasa')
        failed = self.build(checker_hit=False)
        self.assertFalse(failed['conditions']['b'])
        self.assertEqual(failed['checker']['natural']['critical_priority'], 2)
        self.assertEqual(failed['checker']['natural']['critical_warned'], 0)

    def test_natural_counts_are_per_report_not_cumulative(self):
        natural = self.build()['checker']['natural']
        self.assertEqual((natural['critical_priority'], natural['critical_warned']), (2, 2))

    def test_unresolved_costs_leave_e_unaccredited(self):
        result = self.build(unsettled=True)
        self.assertIsNone(result['conditions']['e'])
        self.assertEqual(result['outcome'], 'no_pasa')

    def test_reading_against_blocks_fails_c_and_not_run_is_incomplete(self):
        self.assertFalse(self.build(blocks_pick='v1')['conditions']['c'])
        self.assertEqual(self.build(not_run=True)['outcome'], 'incompleto')


if __name__ == '__main__':
    unittest.main()
