"""Accuracy audit kit: engine reports only, content version without marks, frozen and blind."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation import trial_accuracy as accuracy
from decision_room.evaluation import trial_audit as audit
from decision_room.evaluation import trials


def batch_with(root):
    (root / 'inputs/albor/datos').mkdir(parents=True)
    (root / 'inputs/albor/datos/v.csv').write_text('a\n1\n')
    (root / 'inputs/albor/prompt.txt').write_text('Mi negocio es Demo.')
    jobs = {'albor-engine-1': ('engine', '<p>Cae un 42 % <span class="verificada">verificada</span></p>', True),
            'albor-engine-2': ('engine', '<p>Sube un 7 % <span>sin comprobar</span></p>', False),
            'albor-opencode-1': ('opencode', '<p>Otro</p>', False)}
    for name, (system, html, content) in jobs.items():
        job = root / 'jobs' / name
        (job / 'engine').mkdir(parents=True)
        trials.write(job / 'state.json', dict(job=name, dataset='albor', system=system, status='completed'))
        (job / 'informe.html').write_text(html)
        if content:
            (job / 'engine' / audit.CONTENT).write_text('<p>Cae un 42 %</p>')
    trials.write(root / 'manifest.json', dict(order=list(jobs)))
    return root


class AuditKitTests(unittest.TestCase):
    def test_kit_is_engine_only_unmarked_frozen_and_keyed_outside(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = batch_with(tmp / 'batch')
            result = audit.kit(batch, tmp / 'auditoria')
            self.assertEqual(result, {'reports': 2, 'marks_not_removed': ['albor-engine-2']})
            out = tmp / 'auditoria'
            texts = [p.read_text() for p in (out / 'informes').glob('*.txt')]
            self.assertIn('Cae un 42 %', ''.join(texts))
            self.assertNotIn('verificada', ''.join(texts))
            self.assertNotIn('Otro', ''.join(texts))
            self.assertEqual((out / 'entradas/albor/prompt.txt').read_text(), 'Mi negocio es Demo.')
            for line in (out / 'MANIFIESTO.sha256').read_text().splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
            self.assertFalse(any('engine' in p.name or 'kit-key' in p.name for p in out.rglob('*')))
            self.assertIn('sostiene_prioridad_v3', (out / 'INSTRUCCIONES.md').read_text())

    def test_unblind_feeds_the_accuracy_join(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = batch_with(tmp / 'batch')
            audit.kit(batch, tmp / 'auditoria')
            sheet = json.loads((tmp / 'auditoria/plantilla.json').read_text())
            (tmp / 'a.json').write_text(json.dumps(sheet))
            with self.assertRaises(SystemExit):
                audit.unblind(batch, tmp / 'a.json', 'auditoria')
            for body in sheet['informes'].values():
                body.update(cifras_revisadas_total=1, registro_cifras=[{
                    'cita': 'Cae un 42 %', 'valor_informe': '42 %', 'clase': 'correcta', 'sostiene_prioridad_v3': True}])
            (tmp / 'a.json').write_text(json.dumps(sheet))
            register = audit.unblind(batch, tmp / 'a.json', 'auditoria')
            self.assertEqual(sorted(register), ['albor-engine-1', 'albor-engine-2'])
            (tmp / 'register.json').write_text(json.dumps(register))
            result = accuracy.arm(accuracy.load(tmp / 'register.json', batch))
            self.assertEqual(result['audited'], 2)
            self.assertFalse(result['passed'])  # no verification.json yet: every figure is unmarked


if __name__ == '__main__':
    unittest.main()
