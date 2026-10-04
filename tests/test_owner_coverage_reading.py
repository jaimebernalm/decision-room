"""P3 omits controller counters, retaining the concrete unanswered request."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader

from decision_room.agent.research_agenda import limitation
from decision_room.owner_presentation import limits
from decision_room.web.dashboard import presentation
from decision_room.web.presentation_html import render
from decision_room.report_pdf import render_pdf
from test_owner_presentation import readable


class OwnerCoverageReadingTests(unittest.TestCase):
    def test_existing_approved_report_exports_pending_explanation_once_without_counters(self):
        data = readable()
        report = data['report']
        note = limitation({}, report)
        report['limitations'].append(note)
        original = deepcopy(data)
        view = presentation(data)
        self.assertTrue(view['partial'])
        self.assertEqual(view['limitations'].count('Faltan costes para comparar el beneficio.'), 1)
        for document in (render(view, 'today'), '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)):
            self.assertNotIn('Cobertura del encargo:', document)
            self.assertNotIn('entregables completos', document)
            self.assertEqual(document.count('Faltan costes para comparar el beneficio.'), 1)
        self.assertEqual(data, original)
        self.assertIn(note, data['report']['limitations']) # retained in the audit
        data['options'] = {}
        self.assertIn(note, presentation(data)['limitations']) # control unchanged

    def test_every_pending_explanation_survives_even_if_controller_note_was_truncated(self):
        report = readable()['report']
        report['owner_coverage'] = [dict(deliverable_index=i, status=status, claim_keys=[], explanation=text)
            for i, (status, text) in enumerate([
                ('partial', 'Falta información del primer periodo. ' * 30),
                ('unavailable', 'No se dispone de costes. ' * 30),
                ('deferred', 'Pendiente comprobar el último periodo. ' * 30)])]
        note = limitation({}, report)
        self.assertEqual(len(note), 1600)
        report['limitations'].append(note)
        result = limits(report)
        self.assertNotIn(note, result)
        for entry in report['owner_coverage']:
            self.assertEqual(result.count(entry['explanation']), 1)

    def test_complete_coverage_does_not_leave_an_internal_counter(self):
        report = readable()['report']
        report['owner_coverage'][0].update(status='complete', explanation='La comparación está respondida.')
        note = limitation({}, report)
        report['limitations'].append(note)
        self.assertNotIn(note, limits(report))
        self.assertIn('No conocemos costes ni causas.', limits(report))

    def test_only_exact_controller_note_is_removed(self):
        report = readable()['report']
        note = limitation({}, report)
        extra = note + ' Otra cautela no recogida en la cobertura.'
        report['limitations'].extend([extra, '  ' + note.replace(' ', '  ') + '  '])
        result = limits(report)
        self.assertIn(extra, result)
        self.assertEqual(sum('entregables completos' in item for item in result), 1)
