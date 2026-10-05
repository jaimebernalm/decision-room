"""P3b readability using generic saved evidence, without analytical changes."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader
from decision_room.owner_presentation import guidance, orientation, source_summary
from decision_room.agent.owner_presentation import feedback, SYSTEM, VERSION
from decision_room.web.dashboard import presentation
from decision_room.web.presentation_editing import relabel
from decision_room.web.presentation_html import render
from decision_room.report_pdf import render_pdf
from test_owner_presentation import readable
from test_chart_layers import layered


class P3bTests(unittest.TestCase):
    def test_layer_ids_become_business_names_and_keep_original_values_and_links(self):
        data = layered(); data['options'] = {'owner_presentation': True}
        original = deepcopy(data)
        view = presentation(data)
        chart = view['charts'][0]
        self.assertEqual(chart['points'][0]['label'], 'Registro diario · 2026-01-01')
        self.assertEqual(chart['points'][0]['original_label'], 'observed:2026-01-01')
        self.assertEqual(chart['points'][0]['value'], '1')
        self.assertEqual(chart['panels'][0]['coordinates'][0]['label'], chart['points'][0]['label'])
        labeled = relabel(view, [])
        self.assertEqual(labeled['charts'][0]['points'][0]['original_label'], 'observed:2026-01-01')
        html = render(labeled, 'today')
        self.assertNotIn('observed:', html)
        self.assertNotIn('Mean of the current', html)
        self.assertNotIn('<table>', html) # no duplicate time series below line chart
        pdf = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(labeled))).pages)
        self.assertIn('observed:2026-01-01', pdf)
        self.assertEqual(data, original)
        data['options'] = {}
        self.assertEqual(presentation(data)['charts'][0]['points'][0]['label'], 'observed:2026-01-01')

    def test_reactions_collapse_only_identical_outcomes_and_do_not_double_si(self):
        claim = readable()['report']['claims'][0]
        claim['orientation']['reactions'] = [dict(condition='Si Si hay cobertura completa', reaction='Comparar cantidades.'),
                                            dict(condition='Si falta cobertura', reaction='Pedir los registros.')]
        self.assertNotIn('Si Si', str(guidance(claim)))
        self.assertEqual(len(orientation(claim['orientation'])['reactions']), 2)
        claim['orientation']['reactions'][1]['reaction'] = 'Comparar cantidades.'
        original = deepcopy(claim)
        result = orientation(claim['orientation'])
        self.assertEqual(result['reactions'], [])
        self.assertEqual(result['reaction_summary'], 'Si hay cobertura completa o si falta cobertura: Comparar cantidades.')
        self.assertEqual(sum(text.endswith('Comparar cantidades.') for _, text in guidance(claim)), 1)
        self.assertEqual(claim, original)

    def test_software_notes_leave_business_limits_but_remain_in_pdf_audit(self):
        data = readable()
        note = 'La exportación HTML no ha sido verificada en el navegador.'
        data['report']['limitations'] += [note, 'Versión 0', 'La exportación de productos no ha sido verificada.', 'Los costes de envío no se han verificado.']
        view = presentation(data)
        html = render(view, 'today')
        self.assertNotIn(note, html)
        self.assertNotIn('Versión 0', html)
        self.assertIn('Los costes de envío no se han verificado.', html)
        self.assertIn('La exportación de productos no ha sido verificada.', html)
        pdf = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        self.assertGreater(pdf.index(note), pdf.index('Fuentes, cálculos y valores originales'))
        self.assertIn(note, data['report']['limitations'])

    def test_editorial_review_targets_jargon_repeated_causality_and_reactions(self):
        data = readable()['report']
        data['claims'][0]['statement'] = 'Pares focales y liderazgo aritmético; no demuestra causalidad.'
        data['summary'] = 'No demuestra causalidad.'
        hints = feedback(data)
        self.assertIn('technical_language', {x['issue'] for x in hints['locations']})
        self.assertGreaterEqual(len(hints['repeated_causal_caveat_locations']), 2)
        self.assertTrue(VERSION.startswith('owner-presentation-v'))
        self.assertIn('DIFFERENT decisions', SYSTEM)
        self.assertIn('ONCE in limitations', SYSTEM)
        note = source_summary(['x' * 300 + '.csv'], 'enero')
        self.assertLess(len(note), 120)
        self.assertIn('1 archivo del análisis', note)
