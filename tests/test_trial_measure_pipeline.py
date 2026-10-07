"""Step-3 measurement end to end, without a model: engine exports that pass the export contract
feed the reader, judge and audit kits, and the auditor's register joins the engine's labels."""
import base64
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation import trial_accuracy, trial_audit, trial_judge, trial_pairs, trials
from decision_room.reports.verification_contract import canonical, figure_id, validate

DOCUMENT = {'prioridades': [{'texto': 'Llama a hostelería: el café de 1 kg cae un 42 % desde abril.'},
                            {'texto': 'Revisa el marketplace: 9 días sin registros en marzo.'}],
            'contexto': 'La web crece un 42 % frente al año pasado.'}


def export(job, wrong=False):
    """What export_run writes, following reports.verification_contract v1."""
    raw = json.dumps(DOCUMENT, ensure_ascii=False).encode()
    verified_sha = hashlib.sha256(canonical(DOCUMENT)).hexdigest()

    def figure(path, text, verified, value):
        field = trial_accuracy.pointer(DOCUMENT, path)
        start = field.index(text)
        return {'id': figure_id(verified_sha, path, start, start + len(text)), 'path': path,
                'span': {'start': start, 'end': start + len(text)}, 'text': text, 'value': value, 'unit': None,
                'status': 'verified' if verified else 'unverified', 'verified': verified, 'corrected_from': None,
                'evidence': [{'kind': 'execution', 'id': 'e1'}] if verified else [], 'recommendation_id': None}
    figures = [figure('/prioridades/0/texto', '42 %', True, '42'),
               figure('/prioridades/1/texto', '9 días', not wrong, '9'),
               figure('/contexto', '42 %', False, '42')]
    ledger = {'contract_version': 1, 'draft_sha256': hashlib.sha256(raw).hexdigest(), 'verified_sha256': verified_sha,
              'renderer_version': 'fixture-v1', 'figures': figures, 'issues': [],
              'summary': {s: sum(f['status'] == s for f in figures) for s in ('verified', 'unverified', 'uncertain', 'corrected')}}
    validate(ledger, DOCUMENT, raw)
    folder = job / 'engine'
    folder.mkdir()
    (folder / 'draft.raw').write_bytes(raw)
    (folder / 'draft.verified.json').write_text(json.dumps(DOCUMENT, ensure_ascii=False))
    (folder / 'verification.json').write_text(json.dumps(ledger, ensure_ascii=False))
    body = ''.join(f'<p>{p["texto"]}</p>' for p in DOCUMENT['prioridades']) + f'<p>{DOCUMENT["contexto"]}</p>'
    (folder / trial_pairs.CONTENT).write_text(f'<html><body>{body}</body></html>')
    (job / 'informe.html').write_text(f'<html><body>{body}<span class="marca">Verificada</span></body></html>')


class MeasurePipelineTests(unittest.TestCase):
    def test_kits_and_accuracy_join_work_on_contract_exports(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            batch = tmp / 'batch'
            (batch / 'inputs/albor/datos').mkdir(parents=True)
            (batch / 'inputs/albor/datos/v.csv').write_text('a\n1\n')
            (batch / 'inputs/albor/prompt.txt').write_text('Mi negocio es Demo.')
            order = [f'albor-{s}-{r}' for r in (1, 2) for s in ('engine', 'opencode', 'product')]
            for name in order:
                _, system, repetition = name.rsplit('-', 2)
                (batch / 'jobs' / name).mkdir(parents=True)
                trials.write(batch / 'jobs' / name / 'state.json', dict(
                    job=name, dataset='albor', system=system, repetition=int(repetition), status='not_run'))
            trials.write(batch / 'manifest.json', dict(systems=['engine', 'opencode', 'product'],
                                                      datasets={'albor': {}}, order=order))
            trial_pairs.plan(batch, seed=5)
            for name in order:
                job = batch / 'jobs' / name
                state = trials.read(job / 'state.json')
                trials.write(job / 'state.json', {**state, 'status': 'completed'})
                if 'engine' in name:
                    export(job, wrong=name.endswith('-2'))
                else:
                    (job / 'informe.html').write_text(f'<html><body><p>Informe de {name}</p></body></html>')

            readers = trial_pairs.kit(batch, tmp / 'contenido', 'contenido')
            self.assertEqual((readers['pairs'], readers['marks_not_removed']), (4, []))
            page = (tmp / 'contenido/comparacion.html').read_text()
            data = json.loads(page.split('const DATA=', 1)[1].split(', KIT=', 1)[0])
            shown = ''.join(base64.b64decode(i[s]).decode() for i in data for s in ('a', 'b'))
            self.assertNotIn('Verificada', shown)
            self.assertEqual(trial_judge.kit(batch, tmp / 'juez')['reports'], 6)
            self.assertEqual(trial_audit.kit(batch, tmp / 'auditoria')['reports'], 2)

            sheet = json.loads((tmp / 'auditoria/plantilla.json').read_text())
            for body in sheet['informes'].values():
                body.update(cifras_revisadas_total=3, registro_cifras=[
                    {'cita': 'el café de 1 kg cae un 42 % desde abril', 'valor_informe': '42 %',
                     'clase': 'correcta', 'sostiene_prioridad_v3': True},
                    {'cita': '9 días sin registros en marzo', 'valor_informe': '9 días',
                     'clase': 'correcta', 'sostiene_prioridad_v3': True},
                    {'cita': 'La web crece un 42 % frente al año pasado', 'valor_informe': '42 %',
                     'clase': 'correcta', 'sostiene_prioridad_v3': False}])
            (tmp / 'auditoria.json').write_text(json.dumps(sheet))
            (tmp / 'registro.json').write_text(json.dumps(trial_audit.unblind(batch, tmp / 'auditoria.json', 'auditoria')))
            result = trial_accuracy.arm(trial_accuracy.load(tmp / 'registro.json', batch))
            one, two = result['reports']['albor-engine-1'], result['reports']['albor-engine-2']
            self.assertEqual(one['by_status'], {'unverified': 1, 'verified': 2})
            self.assertTrue(one['conditions']['priority_all_verified_correct'])
            self.assertFalse(one['conditions']['others_at_least_95'])  # the context figure is not verified
            self.assertFalse(two['conditions']['priority_all_verified_correct'])
            self.assertFalse(result['passed'])


if __name__ == '__main__':
    unittest.main()
