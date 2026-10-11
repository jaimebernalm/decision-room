"""PDF of native v1 reports: escaped platform template, complete values, same check notices."""
import io
import json
import unittest

from pypdf import PdfReader

from decision_room.engine import blocks
from decision_room.reports import blocks_pdf
from tests.test_engine_blocks import FULL, doc, raw


def text_of(pdf):
    return '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


class BlocksPdfTests(unittest.TestCase):
    def test_complete_escaped_pdf_with_notices(self):
        projection = blocks.parse(raw(FULL))
        projection['title'] = '<b>Informe</b> & <script>'
        pdf = blocks_pdf.render(projection, {'state': 'complete', 'items': [
            {'block_id': 'b4', 'quote': '342 unidades', 'status': 'discrepancy', 'independent_value': '336'},
            {'block_id': 'b2', 'quote': '39.918,54', 'status': 'unverifiable', 'message': 'Sin detalle.'}]})
        self.assertTrue(pdf.startswith(b'%PDF-'))
        text = text_of(pdf)
        self.assertIn('<b>Informe</b> & <script>', text)  # shown literally, never interpreted
        for expected in ('39.918,54 €', '+4.918,54 € (+14,1 %)', '6.936,74 €', '15.630,29 €', 'Magnesio', '342',
                         'Prioridad 01', 'Cifra en revisión', 'cálculo independiente: 336',
                         'Cifras que no se pudieron comprobar', 'Faltan registros'):
            self.assertIn(expected, text)
        self.assertNotIn('Revisado', text)
        self.assertNotIn('Verificado', text)

    def test_coverage_summary_is_not_a_quote(self):
        projection = blocks.parse(raw(FULL))
        text = text_of(blocks_pdf.render(projection, {'state': 'complete', 'items': [
            {'block_id': 'b4', 'quote': '2026', 'status': 'unverifiable', 'coverage': True,
             'message': '3 fragmentos numéricos de esta prioridad quedaron sin comprobación explícita.'}]}))
        self.assertIn('3 fragmentos numéricos', text)
        self.assertNotIn('Cifras que no se pudieron comprobar', text)
        self.assertNotIn('«2026»', text)

    def test_eight_series_legend_stays_inside_the_drawing(self):
        series = [{'nombre': f'Serie número {j}', 'valores': [j + 1, j + 2]} for j in range(blocks.MAX_SERIES)]
        projection = blocks.parse(raw(doc({'tipo': 'grafico', 'grafico': 'columnas', 'titulo': 'Ocho', 'categorias': ['a', 'b'], 'series': series})))
        drawing = blocks_pdf.chart_drawing(projection['blocks'][0])
        from reportlab.graphics.shapes import String
        labels = [x for x in drawing.contents if isinstance(x, String) and x.text.startswith('Serie')]
        self.assertEqual(len(labels), blocks.MAX_SERIES)
        for label in labels:
            self.assertLessEqual(label.x + 90, drawing.width)
            self.assertLessEqual(label.y, drawing.height)
            self.assertGreaterEqual(label.y, 0)

    def test_extreme_sizes_paginate_without_loss(self):
        cats = [f'Categoría con una etiqueta bastante larga {i}' for i in range(blocks.MAX_CATEGORIES)]
        series = [{'nombre': f'S{j}', 'valores': [((-1) ** i) * (i + j + 0.5) for i in range(len(cats))]}
                  for j in range(blocks.MAX_SERIES)]
        rows = [[f'fila {i}', i * 1.5] for i in range(blocks.MAX_ROWS)]
        projection = blocks.parse(raw(doc(
            {'tipo': 'grafico', 'grafico': 'cambio', 'titulo': 'Muchos', 'categorias': cats, 'series': series},
            {'tipo': 'grafico', 'grafico': 'lineas', 'titulo': 'Huecos', 'categorias': ['a', 'b', 'c', 'd'],
             'series': [{'nombre': 'x', 'valores': [1, None, 3, 4]}]},
            {'tipo': 'grafico', 'grafico': 'columnas', 'titulo': 'Cols', 'categorias': ['a', 'b'],
             'series': [{'nombre': 'x', 'valores': [-1, 2]}]},
            {'tipo': 'grafico', 'grafico': 'radar', 'titulo': 'Desconocido', 'categorias': ['a'],
             'series': [{'nombre': 'x', 'valores': [7]}]},
            {'tipo': 'tabla', 'columnas': ['Fila', {'titulo': 'Valor', 'decimales': 1}], 'filas': rows})))
        text = text_of(blocks_pdf.render(projection))
        self.assertIn('fila 199', text)
        self.assertIn('298,5', text)
        self.assertIn(cats[-1][:30], text)
        self.assertIn('Desconocido', text)


if __name__ == '__main__':
    unittest.main()
