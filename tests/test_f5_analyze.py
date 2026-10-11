"""The F5 analysis applies the frozen rule, including unaccredited and incomplete cases."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from decision_room.config import ROOT

spec = importlib.util.spec_from_file_location('analyze', ROOT / 'scripts/f5/analyze.py')
analyze = importlib.util.module_from_spec(spec); spec.loader.exec_module(analyze)


class AnalyzeTests(unittest.TestCase):
    def build(self, *, legacy_delivered=True, drop=None, owner_pick='v1', material=0, signals=(2, 2, 2, 2, 2), rejected=False, crash=False):
        root = Path(tempfile.mkdtemp(dir=self.temp.name))
        trial, results = root / 'trial', root / 'results'
        (trial / 'runs').mkdir(parents=True); results.mkdir()
        ledger = root / 'ledger.sqlite'
        db = sqlite3.connect(ledger); db.execute('CREATE TABLE calls (scope TEXT, charged INTEGER, state TEXT)')
        jobs, attempts, reports, pairs = [], [], {}, {}
        number = 100
        for business in ('herbolario', 'clinica'):
            for i in range(1, 7):
                kits = {}
                for arm in ('v1', 'legacy'):
                    code = f"{business}-{i}-{'opencode' if arm == 'v1' else 'legacy'}"
                    job = f'job-{number}'
                    jobs.append(dict(code=code, job_id=job))
                    delivered = arm == 'v1' or legacy_delivered
                    (trial / 'runs' / code).mkdir()
                    (trial / 'runs' / code / 'result.json').write_text(json.dumps(
                        dict(status='completed' if delivered else 'blocked', seconds=120, engine_run_id=None)))
                    db.execute('INSERT INTO calls VALUES (?,?,?)', ('web:' + job, 100_000_000, 'settled'))
                    attempts.append(dict(code=code, business=business, repetition=i, arm=arm, delivered=delivered,
                                         status='completed' if delivered else 'blocked', trial=str(trial)))
                    kit = None
                    if delivered:
                        kit = f'R{number}'; reports[kit] = dict(code=code, business=business, repetition=i, arm=arm)
                        if drop != kit:
                            (results / f'group-{kit}.json').write_text(json.dumps(dict(material_distintos=material if arm == 'v1' else 0, criticos_distintos=0)))
                            (results / f'audit-{kit}.json').write_text(json.dumps(dict(claims=[dict(calculable=True, seccion='prioridad', veredicto='correcta')])))
                            (results / f'judge-{kit}.json').write_text(json.dumps(dict(zip(['S1', 'S2', 'S3', 'S4', 'S5', 'S6'], [*(signals if arm == 'v1' else (2, 2, 2, 2, 2)), 0]))))
                    kits[arm] = kit
                    number += 1
                name = f'{business}-{i}'
                pairs[name] = dict(order=['v1', 'legacy'], kits=kits)
                if all(kits.values()):
                    for role in ('owner', 'advisor'):
                        (results / f'{role}-{name}.json').write_text(json.dumps(dict(eleccion='A' if owner_pick == 'v1' else 'B')))
        db.commit(); db.close()
        if rejected:
            db = sqlite3.connect(ledger); db.execute('INSERT INTO calls VALUES (?,?,?)', ('web:job-100', 268_644_000, 'rejected')); db.commit(); db.close()
        if crash:
            (trial / 'runs' / 'herbolario-1-opencode' / 'result.json').unlink()
            (trial / 'runs' / 'herbolario-1-opencode' / 'failure.json').write_text('{}')
        (trial / 'manifest.json').write_text(json.dumps(dict(budget_path=str(ledger), jobs=jobs, config=dict(dsn='dbname=f5_analyze_absent connect_timeout=1'))))
        key = root / 'key.json'; key.write_text(json.dumps(dict(attempts=attempts, reports=reports, pairs=pairs)))
        out = root / 'out.json'
        analyze.main(key, results, out)
        return json.loads(out.read_text())['conditions']

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def test_all_conditions_met_is_candidate_unless_cost_sources_are_unknown(self):
        # The fixture database is absent, so engine runs cannot be confirmed: (e) is not accredited.
        result = self.build()
        self.assertIsNone(result['e']); self.assertEqual(result['outcome'], 'mixto')
        with unittest.mock.patch.object(analyze, 'load_engine_runs', return_value={}):
            self.assertEqual(self.build()['outcome'], 'candidato')

    def test_terminal_rejection_is_charged_but_not_uncertain(self):
        with unittest.mock.patch.object(analyze, 'load_engine_runs', return_value={}):
            result = self.build(rejected=True)
        self.assertTrue(result['e'])

    def test_crash_without_result_has_no_duration_and_is_not_accredited(self):
        with unittest.mock.patch.object(analyze, 'load_engine_runs', return_value={}):
            result = self.build(crash=True)
        self.assertIsNone(result['e'])

    def test_no_legacy_delivery_leaves_comparisons_unaccredited_not_failed(self):
        result = self.build(legacy_delivered=False)
        self.assertIsNone(result['b']); self.assertIsNone(result['d']); self.assertTrue(result['c'])
        self.assertEqual(result['outcome'], 'mixto')

    def test_missing_evaluation_is_incomplete_never_candidate(self):
        self.assertEqual(self.build(drop='R100')['outcome'], 'incompleto')

    def test_two_failed_conditions_is_not_a_candidate(self):
        self.assertEqual(self.build(owner_pick='legacy', material=2)['outcome'], 'no_candidato')

    def test_one_failed_condition_is_mixed(self):
        self.assertEqual(self.build(signals=(0, 0, 0, 0, 0))['outcome'], 'mixto')


if __name__ == '__main__':
    unittest.main()
