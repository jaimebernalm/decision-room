"""Accuracy condition of the step-3 gate: the auditor's register decides, engine labels only join."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation import trial_accuracy as accuracy


def entry(cita, valor, clase='correcta', priority=False):
    return {'cita': cita, 'valor_informe': valor, 'clase': clase, 'sostiene_prioridad_v3': priority}


def figure(text, status='verified', verified=None, path='/x', start=0):
    return {'id': f'{path}:{start}', 'path': path, 'span': {'start': start, 'end': start + len(text)},
            'text': text, 'status': status, 'verified': status == 'verified' if verified is None else verified}


def located(document, path, text, status='verified', verified=None, nth=0):
    field = accuracy.pointer(document, path)
    start = -1
    for _ in range(nth + 1):
        start = field.index(text, start + 1)
    return figure(text, status, verified, path, start)


class AccuracyTests(unittest.TestCase):
    def test_all_priority_figures_verified_and_correct_pass(self):
        entries = [entry('Hostelería cae un 42 % frente a marzo', '42 %', priority=True),
                   entry('La web suma 1.204 unidades', '1.204')]
        result = accuracy.report(entries, [figure('42 %'), figure('1.204', start=50)])
        self.assertTrue(result['passed'])
        self.assertEqual((result['priority'], result['priority_verified_correct']), (1, 1))

    def test_correction_alone_is_not_verification(self):
        entries = [entry('Cae un 42 %', '42 %', priority=True)]
        self.assertFalse(accuracy.report(entries, [figure('42 %', 'corrected', False)])['passed'])
        self.assertTrue(accuracy.report(entries, [figure('42 %', 'corrected', True)])['passed'])

    def test_unlabelled_or_duplicated_figure_is_not_verified(self):
        entries = [entry('Cae un 42 %', '42 %', priority=True)]
        self.assertEqual(accuracy.report(entries, [])['by_status'], {'unmarked': 1})
        twins = [figure('42 %', start=0), figure('42 %', start=30)]
        result = accuracy.report(entries, twins)
        self.assertEqual(result['ambiguous'], 1)
        self.assertFalse(result['conditions']['priority_all_verified_correct'])

    def test_location_in_the_verified_document_resolves_duplicates(self):
        document = {'secciones': [{'texto': 'La web sube un 42 % en junio.'},
                                  {'texto': 'Hostelería cae un 42 % desde abril.'}]}
        figures = [located(document, '/secciones/0/texto', '42 %', 'unverified'),
                   located(document, '/secciones/1/texto', '42 %')]
        self.assertEqual(accuracy.label(entry('Hostelería  cae un 42 % desde abril', '42 %'), figures, document), 'verified')
        self.assertEqual(accuracy.label(entry('La web sube un 42 % en junio', '42 %'), figures, document), 'unverified')
        same = {'p': 'Baja un 5 % y luego otro 5 % más.'}
        twice = [located(same, '/p', '5 %'), located(same, '/p', '5 %', nth=1)]
        self.assertEqual(accuracy.label(entry('Baja un 5 % y luego otro 5 % más', '5 %'), twice, same), 'ambiguous')

    def test_label_matches_whole_numbers_only(self):
        self.assertEqual(accuracy.label(entry('Sube un 14 %', '14 %'), [figure('4 %')]), 'unmarked')
        self.assertEqual(accuracy.label(entry('Sube un 4,5 %', '4,5 %'), [figure('4')]), 'unmarked')
        self.assertEqual(accuracy.label(entry('Sube un 4 % en web', '4 %'), [figure('4 %')]), 'verified')

    def test_ambiguous_priority_figure_is_not_correct(self):
        result = accuracy.report([entry('Sube un 12 %', '12 %', 'ambigua', True)], [figure('12 %')])
        self.assertFalse(result['conditions']['priority_all_verified_correct'])

    def test_error_labelled_verified_fails_even_outside_priorities(self):
        entries = [entry('La tienda vende 300 bolsas', '300')] + [entry(f'Cifra {i} kg', f'{i} kg') for i in range(30)]
        entries[0]['clase'] = 'error'
        figures = [figure('300')] + [figure(f'{i} kg', start=10 * i + 10) for i in range(30)]
        result = accuracy.report(entries, figures)
        self.assertEqual(result['errors_labelled_verified'], 1)
        self.assertFalse(result['passed'])
        figures[0] = figure('300', 'unverified')
        result = accuracy.report(entries, figures)
        self.assertTrue(result['passed'])
        self.assertEqual(result['error_rows'][0]['estado_motor'], 'unverified')

    def test_others_need_95_percent_verified_and_not_calculable_is_outside(self):
        entries = [entry(f'Cifra {i} unidades', f'{i} unidades') for i in range(20)]
        entries.append(entry('Sin dato de apertura', 'n/d', 'no_calculable'))
        figures = [figure(f'{i} unidades', start=20 * i) for i in range(19)] + [figure('19 unidades', 'unverified', start=380)]
        result = accuracy.report(entries, figures)
        self.assertEqual((result['others'], result['others_verified'], result['not_calculable']), (20, 19, 1))
        self.assertTrue(result['conditions']['others_at_least_95'])
        figures[-2] = figure('18 unidades', 'uncertain', start=360)
        result = accuracy.report(entries, figures)
        self.assertFalse(result['conditions']['others_at_least_95'])
        self.assertEqual(result['uncertain'], 1)

    def test_arm_needs_every_report_and_loads_engine_exports(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp) / 'batch'
            export = batch / 'jobs/albor-engine-1/engine'
            export.mkdir(parents=True)
            document = {'p': 'Cae un 42 % desde abril.'}
            (export / 'draft.verified.json').write_text(json.dumps(document))
            (export / 'verification.json').write_text(json.dumps({'figures': [located(document, '/p', '42 %')]}))
            audit = Path(tmp) / 'audit.json'
            audit.write_text(json.dumps({
                'albor-engine-1': {'registro_cifras': [entry('Cae un 42 % desde abril', '42 %', priority=True)]},
                'albor-engine-2': {'registro_cifras': [entry('Cae un 7 %', '7 %', priority=True)]}}))
            result = accuracy.arm(accuracy.load(audit, batch))
            self.assertTrue(result['reports']['albor-engine-1']['passed'])
            self.assertFalse(result['reports']['albor-engine-2']['passed'])
            self.assertFalse(result['passed'])
            self.assertFalse(accuracy.arm({})['passed'])


if __name__ == '__main__':
    unittest.main()
