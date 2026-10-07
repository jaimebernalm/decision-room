"""Signal judge kit and gate condition: blind codes, key outside the kit, preregistered scale."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation import trial_judge as judge
from decision_room.evaluation import trials


def batch_with(root, reports):
    order = []
    for name, (system, html) in reports.items():
        job = root / 'jobs' / name
        job.mkdir(parents=True)
        dataset = name.split('-')[0]
        trials.write(job / 'state.json', dict(job=name, dataset=dataset, system=system, status='completed'))
        if html is not None:
            (job / 'informe.html').write_text(html)
        order.append(name)
    trials.write(root / 'manifest.json', dict(order=order))
    return root


def sheet(kit_dir, scores):
    template = json.loads((kit_dir / 'plantilla.json').read_text())
    for code, marks in template['informes'].items():
        for signal, points in zip((*judge.SIGNALS, judge.DECOY), scores(code)):
            marks[signal]['puntos'] = points
    return template


class JudgeTests(unittest.TestCase):
    def test_kit_holds_only_delivered_reports_of_the_dataset_with_key_outside(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = batch_with(tmp / 'batch', {
                'albor-engine-1': ('engine', '<p>Decision Room · Informe de negocio</p><p>Hostelería</p>'),
                'albor-opencode-1': ('opencode', '<p>Web</p>'),
                'albor-product-1': ('product', '<p>   </p>'),
                'bruma-engine-1': ('engine', '<p>Bruma</p>')})
            result = judge.kit(batch, tmp / 'juez')
            self.assertEqual(result['reports'], 2)
            files = sorted(p.name for p in (tmp / 'juez/informes').glob('*.html'))
            self.assertTrue(all(f.startswith('albor-') for f in files))
            text = ''.join(p.read_text() for p in (tmp / 'juez/informes').glob('*.html'))
            self.assertNotIn('Decision Room', text)
            key = trials.read(batch / 'kit-key-juez.json')['codes']
            self.assertEqual(sorted(key.values()), ['albor-engine-1', 'albor-opencode-1'])
            self.assertFalse(any('engine' in p.name for p in (tmp / 'juez').rglob('*')))
            with self.assertRaises(SystemExit):
                judge.kit(batch, tmp / 'juez')

    def test_gate_needs_mean_eleven_thirds_and_no_decoy(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = batch_with(tmp / 'batch', {f'albor-engine-{i}': ('engine', f'<p>Informe {i}</p>') for i in (1, 2, 3)})
            judge.kit(batch, tmp / 'juez')
            key = trials.read(batch / 'kit-key-juez.json')['codes']
            totals = {'albor-engine-1': (2, 2, 0, 0, 0), 'albor-engine-2': (2, 2, 0, 0, 0), 'albor-engine-3': (2, 1, 0, 0, 0)}
            write = lambda scores: (tmp / 'juez-a.json').write_text(json.dumps(sheet(tmp / 'juez', scores)))
            write(lambda code: (*totals[key[code]], 0))
            result = judge.score(batch, tmp / 'juez-a.json', 'juez')
            self.assertAlmostEqual(result['gate']['mean_total'], 11 / 3)
            self.assertTrue(result['gate']['passed'])
            write(lambda code: (*totals[key[code]], 1 if key[code] == 'albor-engine-1' else 0))
            self.assertFalse(judge.score(batch, tmp / 'juez-a.json', 'juez')['gate']['passed'])
            totals['albor-engine-3'] = (1, 1, 0, 0, 0)
            write(lambda code: (*totals[key[code]], 0))
            self.assertFalse(judge.score(batch, tmp / 'juez-a.json', 'juez')['gate']['passed'])

    def test_incomplete_sheet_is_refused(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = batch_with(tmp / 'batch', {'albor-engine-1': ('engine', '<p>Uno</p>')})
            judge.kit(batch, tmp / 'juez')
            (tmp / 'juez-a.json').write_text(json.dumps(sheet(tmp / 'juez', lambda code: (2, 2, None, 0, 0, 0))))
            with self.assertRaises(SystemExit):
                judge.score(batch, tmp / 'juez-a.json', 'juez')


if __name__ == '__main__':
    unittest.main()
