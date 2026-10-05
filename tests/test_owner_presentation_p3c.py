"""P3c reading projection preserves evidence and specific business conditions."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader

from decision_room.agent.delivery_selection import selection_notes
from decision_room.agent.owner_presentation import feedback, SYSTEM, VERSION
from decision_room.owner_presentation import clean_reading, delivery_note
from decision_room.report_pdf import render_pdf
from decision_room.web.dashboard import presentation
from decision_room.web.presentation_html import render
from test_owner_presentation import readable


class P3cTests(unittest.TestCase):
    def test_browser_and_selection_notes_leave_reading_not_audit(self):
        data=readable(); report=data['report']
        report['delivery_selections']=[dict(key='dates',title='Fechas del extracto',chart_keys=['trend'],axis='points',
            shown_group_count=2,population=None,coverage='selected')]
        note=selection_notes(report,data['observations'])[0]
        report['limitations'].append(note)
        browser='No se comprobó que el informe se abra en navegador.'
        report['summary'] += ' '+browser
        report['scope']['coverage'] += ' No se acredita que el informe se abra en navegador.'
        report['limitations'] += [browser+' Faltan costes para decidir.', 'Anexo técnico.']
        original=deepcopy(data)
        view=presentation(data); html=render(view,'today')
        for phrase in ('No se comprobó','No se acredita','Selección entregada','Anexo técnico'):
            self.assertNotIn(phrase,html)
        self.assertIn('Faltan costes para decidir.',html)
        self.assertIn('No se comprobó',str(view['technical_notes']))
        self.assertEqual(data,original)
        self.assertIn(note,data['report']['limitations'])
        self.assertEqual(view['charts'][0]['points'][0]['value'],'10.00')
        data['options']={}
        control=render(presentation(data),'today')
        self.assertIn(note,control)
        self.assertIn(browser,control)

    def test_generic_caveats_once_and_specific_conditions_preserved(self):
        data=readable(); report=data['report']
        report['summary']+=' Estos datos son sintéticos. No se puede inferir causalidad.'
        report['scope']['coverage']+=' Son datos simulados.'
        report['claims'][0]['interpretation']='El último registro es mayor. No demuestra causalidad.'
        specific='Si el canal dejó de registrar días, la comparación no permite decidir aumentar la inversión.'
        report['claims'][0]['orientation']['next_check']=specific
        report['charts'][0]['caption']+=' Los datos no permiten establecer causalidad.'
        report['limitations'] += ['Datos sintéticos.','No se puede establecer causalidad.']
        original=deepcopy(data); view=presentation(data)
        html=render(view,'today')
        self.assertEqual(html.count('Estos datos son sintéticos.'),1)
        self.assertEqual(html.count('No se puede inferir causalidad.'),1)
        self.assertNotIn('Son datos simulados.',html)
        self.assertNotIn('No demuestra causalidad.',html)
        self.assertIn(specific,html)
        self.assertIn('No conocemos costes ni causas.',view['limitations']) # distinct caveat, not erased
        self.assertIn('No se puede inferir causalidad.',view['limitations'])
        self.assertEqual(clean_reading(view),view)
        pdf='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        body=pdf.split('Fuentes, cálculos y valores originales')[0]
        self.assertEqual(body.count('Estos datos son sintéticos.'),1)
        self.assertEqual(body.count('No se puede inferir causalidad.'),1)
        self.assertEqual(data,original)

    def test_no_empty_scope_box_when_only_technical_note_remains(self):
        data=readable()
        data['report']['scope']['coverage']='No se comprobó que el informe se abra en navegador.'
        view=presentation(data)
        self.assertEqual(view['scope']['coverage'],'')
        self.assertNotIn('<aside class="coverage">',render(view,'today'))
        pdf='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        self.assertNotIn('Contexto y alcance',pdf)

    def test_business_limits_are_not_software_notes(self):
        for text in ('La exportación de productos no ha sido verificada.',
                     'No se comprobó que las ventas del canal Navegador fueran completas.',
                     'El informe no acredita que haya bajado la demanda.',
                     'No se comprobó que el informe se abra en navegador. Faltan costes.',
                     'Versión 0 del catálogo de precios pendiente de confirmar.'):
            self.assertFalse(delivery_note(text),text)
        self.assertTrue(delivery_note('No se acredita que el informe se abra en navegador.'))

    def test_editorial_feedback_covers_jargon_provenance_and_window_reason(self):
        report=readable()['report']
        phrases=['mitades cronológicas','unidades por fecha observada','conciliar captura/mapeo','imputar ceros','meses emparejados']
        for phrase in phrases:
            report['claims'][0]['interpretation']=phrase
            self.assertIn('technical_language',{i['issue'] for i in feedback(report)['locations']})
        report['summary']='Datos sintéticos.'
        report['limitations'].append('Estos datos son simulados.')
        self.assertEqual(len(feedback(report)['synthetic_caveat_locations']),2)
        self.assertIn('ONE short sentence explaining why',SYSTEM)
        self.assertIn('Never infer synthetic provenance',SYSTEM)
        self.assertEqual(VERSION,'owner-presentation-v3')
