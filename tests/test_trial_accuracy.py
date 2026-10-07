"""Accuracy condition of the step-3 gate: the auditor's register decides, engine labels only join."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation import trial_accuracy as accuracy


def entry(cita, valor, clase='correcta', priority=False):
    return {'cita': cita, 'valor_informe': valor, 'clase': clase, 'sostiene_prioridad_v3': priority}


def figure(text, status):
    return {'id': text, 'path': 'x', 'text': text, 'status': status}


class AccuracyTests(unittest.TestCase):
    def test_all_priority_figures_verified_and_correct_pass(self):
        entries = [entry('Hostelería cae un 42 % frente a marzo', '42 %', priority=True),
                   entry('La web suma 1.204 unidades', '1.204')]
        figures = [figure('42 %', 'verified'), figure('1.204', 'corrected')]
        result = accuracy.report(entries, figures)
        self.assertTrue(result['passed'])
        self.assertEqual((result['priority'], result['priority_verified_correct']), (1, 1))

    def test_unlabelled_or_conflicting_priority_figure_fails(self):
        entries = [entry('Cae un 42 %', '42 %', priority=True)]
        self.assertEqual(accuracy.report(entries, [])['by_status'], {'unmarked': 1})
        self.assertFalse(accuracy.report(entries, [])['passed'])
        conflicting = [figure('42 %', 'verified'), figure('42 %', 'unverified')]
        result = accuracy.report(entries, conflicting)
        self.assertEqual(result['conflicting'], 1)
        self.assertFalse(result['conditions']['priority_all_verified_correct'])

    def test_label_matches_whole_numbers_only(self):
        self.assertEqual(accuracy.label(entry('Sube un 14 %', '14 %'), [figure('4 %', 'verified')]), 'unmarked')
        self.assertEqual(accuracy.label(entry('Sube un 4,5 %', '4,5 %'), [figure('4', 'verified')]), 'unmarked')
        self.assertEqual(accuracy.label(entry('Sube un 4 % en web', '4 %'), [figure('4 %', 'verified')]), 'verified')

    def test_ambiguous_priority_figure_is_not_correct(self):
        result = accuracy.report([entry('Sube un 12 %', '12 %', 'ambigua', True)], [figure('12 %', 'verified')])
        self.assertFalse(result['conditions']['priority_all_verified_correct'])

    def test_error_labelled_verified_fails_even_outside_priorities(self):
        entries = [entry('La tienda vende 300', '300', 'error')] + [entry(f'Cifra {i}', str(i)) for i in range(30)]
        figures = [figure('300', 'verified')] + [figure(str(i), 'verified') for i in range(30)]
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
        figures = [figure(f'{i} unidades', 'verified') for i in range(19)] + [figure('19 unidades', 'unverified')]
        result = accuracy.report(entries, figures)
        self.assertEqual((result['others'], result['others_verified'], result['not_calculable']), (20, 19, 1))
        self.assertTrue(result['conditions']['others_at_least_95'])
        figures[-2] = figure('18 unidades', 'uncertain')
        result = accuracy.report(entries, figures)
        self.assertFalse(result['conditions']['others_at_least_95'])
        self.assertEqual(result['uncertain'], 1)

    def test_arm_needs_every_report_and_loads_engine_exports(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / 'jobs/albor-engine-1/engine').mkdir(parents=True)
            (batch / 'jobs/albor-engine-1/engine/verification.json').write_text(
                json.dumps({'figures': [figure('42 %', 'verified')]}))
            audit = batch.parent / (batch.name + '-audit.json')
            audit.write_text(json.dumps({
                'albor-engine-1': {'registro_cifras': [entry('Cae un 42 %', '42 %', priority=True)]},
                'albor-engine-2': {'registro_cifras': [entry('Cae un 7 %', '7 %', priority=True)]}}))
            try:
                result = accuracy.arm(accuracy.load(audit, batch))
            finally:
                audit.unlink()
            self.assertTrue(result['reports']['albor-engine-1']['passed'])
            self.assertFalse(result['reports']['albor-engine-2']['passed'])
            self.assertFalse(result['passed'])
            self.assertFalse(accuracy.arm({})['passed'])


if __name__ == '__main__':
    unittest.main()
