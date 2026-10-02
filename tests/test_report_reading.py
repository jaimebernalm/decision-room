"""Editorial diagnostics stay separate from evidence and approval."""
from copy import deepcopy
import unittest

from decision_room.agent.report_reading import reading_feedback
from decision_room.agent.review_context import model_context


class ReportReadingTests(unittest.TestCase):
    def test_exact_repetition_is_located_without_removing_distinct_caveats(self):
        caveat = 'Los registros disponibles no certifican toda la actividad del negocio.'
        report = {'summary': 'Resultado del periodo.', 'scope': {'coverage': caveat},
                  'limitations': [caveat, 'No consta la disponibilidad de producto.'],
                  'claims': [{'key': 'focus', 'statement': 'Cae el canal observado.'}], 'charts': []}
        original = deepcopy(report)
        feedback = reading_feedback(report)
        self.assertEqual(feedback['repeated_passages'], [{'locations': ['scope.coverage', 'limitations[0]']}])
        self.assertEqual(report, original)
        self.assertEqual(feedback['summary_words'], 3)

    def test_orientation_compatibility_is_not_counted_as_visible_duplication(self):
        signal = 'El canal observado disminuye durante el periodo comparado.'
        check = 'Consultar disponibilidad del producto durante el periodo comparado.'
        report = {'summary': '', 'claims': [{'key': 'focus', 'statement': signal, 'next_step': check,
                  'orientation': {'signal': signal, 'next_check': check, 'reactions': [
                      {'condition': 'falta producto', 'reaction': 'Revisar reposición.'}]}}]}
        feedback = reading_feedback(report)
        self.assertEqual(feedback['repeated_passages'], [])
        self.assertEqual(feedback['first_reading_words'], len((signal + ' ' + check + ' falta producto Revisar reposición.').split()))

    def test_model_feedback_preserves_original_and_all_evidence(self):
        report = {'summary': 'La conclusión conserva la incertidumbre.', 'claims': [{'key': 'x',
                  'statement': 'Resultado observado', 'evidence': [{'execution_id': 'saved', 'metric': 'total'}]}]}
        context = {'report': report, 'observations': [], 'conversation': []}
        original = deepcopy(context)
        packed = model_context(context, 'analyst')
        self.assertIn('report_reading', packed)
        self.assertEqual(packed['report'], original['report'])
        self.assertEqual(context, original)
        self.assertIsNone(reading_feedback(None))

    def test_semantically_similar_or_short_labels_are_not_removed_or_claimed_identical(self):
        report = {'summary': 'Los datos no demuestran una caída de demanda.',
                  'limitations': ['No se conoce la demanda real del negocio.', 'Sin datos', 'Sin datos']}
        self.assertEqual(reading_feedback(report)['repeated_passages'], [])


if __name__ == '__main__':
    unittest.main()
