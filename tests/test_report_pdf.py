"""Independent PDF checks: complete approved content, static graphics and paging."""
import unittest
from copy import deepcopy
from io import BytesIO
from pypdf import PdfReader
from decision_room.report_pdf import render_pdf
from decision_room.web.dashboard import presentation
from test_client_report import sample

class ReportPdfTests(unittest.TestCase):
    def test_contains_full_reviewed_content_exact_values_and_no_private_transcript(self):
        data = sample()
        data['report']['question_coverage'] = [dict(investigation_key='q', status='deferred', claim_keys=[], explanation='Detalle pendiente de datos')]
        pdf = render_pdf(presentation(data))
        self.assertTrue(pdf.startswith(b'%PDF-'))
        reader = PdfReader(BytesIO(pdf))
        text = '\n'.join(p.extract_text() for p in reader.pages)
        for item in ['Ventas registradas', 'No demuestra un cambio de demanda.', 'Comprobar la cobertura',
                     'Sumar los importes', 'ventas.csv', '10,00', '20,01', 'No conocemos costes',
                     'Detalle pendiente de datos', 'Entrega parcial']:
            self.assertIn(item, text)
        for item in ['PRIVATE', 'calculation-a', 'Ver detalle', 'Ocultar detalle']:
            self.assertNotIn(item, text)
        self.assertFalse(reader.get_fields())
        self.assertTrue(any(b' re' in p.get_contents().get_data() or b' m' in p.get_contents().get_data() for p in reader.pages))

    def test_long_text_and_full_tables_paginate_without_losing_final_rows(self):
        report = presentation(sample())
        report['claims'][0]['statement'] = 'Explicación completa. ' * 400
        report['charts'][0].update(kind='bar',panels=[],points=[
            dict(label=f'Producto largo número {i}',value=str(i),formatted=f'{i},00') for i in range(48)])
        pdf=render_pdf(report)
        pages=PdfReader(BytesIO(pdf)).pages
        text='\n'.join(p.extract_text() for p in pages)
        self.assertGreater(len(pages), 3)
        self.assertIn('Producto largo número 47',text)
        self.assertIn('47,00',text)
        self.assertIn('No conocemos costes ni causas.',text)

    def test_long_common_prefix_does_not_hide_category_identity_in_chart(self):
        from decision_room.report_pdf import bar_drawings
        from reportlab.graphics.shapes import String
        labels = ['Producto de referencia ' * 7 + suffix for suffix in ('Canal A', 'Canal B')]
        chart = dict(kind='bar', points=[dict(label=label, value=str(i+1)) for i, label in enumerate(labels)])
        drawings = list(bar_drawings(chart))
        for label in labels:
            self.assertTrue(any(label.replace(' ', '') in ''.join(
                shape.text for shape in drawing.contents if isinstance(shape, String)
            ).replace(' ', '') for _, drawing in drawings))

    def test_unpublishable_data_is_rejected_before_pdf_materialization(self):
        from decision_room.web.errors import WebError
        for change in ['unapproved','stale']:
            data=sample()
            if change=='unapproved':data['publishable']=False
            else:data['observations'][0]['current']=False
            with self.assertRaises(WebError):presentation(data)
