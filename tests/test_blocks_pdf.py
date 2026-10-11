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
                         'Detalles de la comprobación independiente', 'Cifras que no se pudieron recalcular', 'Faltan registros'):
            self.assertIn(expected, text)
        self.assertNotIn('Revisado', text)
        self.assertNotIn('Verificado', text)

    def test_coverage_summary_is_not_a_quote(self):
        projection = blocks.parse(raw(FULL))
        text = text_of(blocks_pdf.render(projection, {'state': 'complete',
            'coverage': {'numeric_spans': 31, 'addressed_spans': 26, 'confirmed_spans': 26}, 'items': [
            {'block_id': 'b4', 'quote': '2026', 'status': 'unverifiable', 'coverage': True,
             'message': '3 cifras de esta prioridad no se recalcularon de forma independiente.'}]}))
        self.assertIn('Se examinaron 26 de los 31 números citados', text)
        self.assertNotIn('no se recalcularon de forma independiente', text)
        self.assertIn('Detalles de la comprobación independiente', text)
        self.assertNotIn('Cifras que no se pudieron recalcular', text)
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

    def test_stacked_charts_stack_segments_proportionally(self):
        from reportlab.graphics.shapes import Rect, String
        series = [{'nombre': 'Realizadas', 'valores': [100, 50]}, {'nombre': 'Canceladas', 'valores': [20, None]}]
        for kind, axis in (('apiladas', 'height'), ('barras_apiladas', 'width')):
            projection = blocks.parse(raw(doc({'tipo': 'grafico', 'grafico': kind, 'titulo': 'Citas',
                                                'categorias': ['ene', 'feb'], 'series': series})))
            drawing = blocks_pdf.chart_drawing(projection['blocks'][0])
            bars = [getattr(r, axis) for r in drawing.contents if isinstance(r, Rect) and r.width > 8 and r.height > 0.6]
            segments = sorted(bars)[-3:]  # 100, 50 and 20 units (legend squares are 8×8)
            self.assertAlmostEqual(segments[-1] / segments[0], 5, places=3)  # 100 vs 20
            self.assertAlmostEqual(segments[1] / segments[0], 2.5, places=3)  # 50 vs 20
            if kind == 'barras_apiladas':
                self.assertIn('120', [x.text for x in drawing.contents if isinstance(x, String)])

    def test_chart_values_go_to_one_appendix_instead_of_under_each_chart(self):
        chart = {'tipo': 'grafico', 'grafico': 'columnas', 'titulo': 'Citas por mes', 'categorias': ['ene', 'feb'],
                 'series': [{'nombre': '2026', 'valores': [612, 598], 'detalles': ['612 de 700', None]}]}
        fallback = {'tipo': 'grafico', 'grafico': 'radar', 'titulo': 'Radar', 'categorias': ['a'],
                    'series': [{'nombre': 's', 'valores': [7]}]}
        projection = blocks.parse(raw(doc(chart, {'tipo': 'texto', 'contenido': 'Después del gráfico.'}, fallback)))
        text = text_of(blocks_pdf.render(projection, None))
        self.assertLess(text.index('Después del gráfico.'), text.index('Valores de los gráficos'))
        self.assertGreater(text.index('612 de 700'), text.index('Valores de los gráficos'))  # exact values kept
        self.assertEqual(text.count('Valores de los gráficos'), 1)
        self.assertLess(text.index('Radar'), text.index('Valores de los gráficos'))  # undrawable stays inline
        drawing = blocks_pdf.chart_drawing(projection['blocks'][0])
        from reportlab.graphics.shapes import String
        self.assertIn('612', [x.text for x in drawing.contents if isinstance(x, String)])  # labelled columns

    def test_numeric_table_columns_align_right(self):
        projection = blocks.parse(raw(FULL))
        table = next(b for b in blocks.walk(projection['blocks']) if b['type'] == 'table')
        grid_table = blocks_pdf._table(table)[-1]
        name, units = grid_table._cellvalues[1]
        self.assertNotEqual(name.style.alignment, 2)
        self.assertEqual(units.style.alignment, 2)

    def test_stacked_gaps_are_never_totals_of_zero(self):
        from reportlab.graphics.shapes import String
        series = [{'nombre': 'A', 'valores': [2, 2, None]}, {'nombre': 'B', 'valores': [3, None, None]}]
        for kind in ('apiladas', 'barras_apiladas'):
            projection = blocks.parse(raw(doc({'tipo': 'grafico', 'grafico': kind, 'titulo': 'Huecos',
                                                'categorias': ['Completa', 'Parcial', 'Sin datos'], 'series': series})))
            labels = [x.text for x in blocks_pdf.chart_drawing(projection['blocks'][0]).contents if isinstance(x, String)]
            self.assertIn('5', labels)
            self.assertIn('2 (parcial)', labels)
            self.assertEqual(labels.count('0'), 0 if kind == 'barras_apiladas' else 1)  # only the axis
            self.assertNotIn('2', labels)

    def test_values_table_keeps_every_delivered_decimal(self):
        self.assertEqual(blocks_pdf._exact(0.1234, 2), 4)
        self.assertEqual(blocks_pdf._exact(12, 1), 1)
        self.assertEqual(blocks_pdf._exact(None, 2), 2)

    def test_series_colors_spread_from_dark_to_light(self):
        from reportlab.lib import colors
        hexes = [blocks_pdf._color(i, 3).hexval() for i in range(3)]
        expected = [colors.HexColor(blocks_pdf.BY_LIGHTNESS[i]).hexval() for i in (0, 2, 4)]
        self.assertEqual(hexes, expected)
        self.assertEqual(len(set(blocks_pdf._color(i, 6).hexval() for i in range(6))), 6)

    def test_long_figure_notes_paginate_and_disputed_figures_keep_their_notice(self):
        figures = [{'tipo': 'cifra', 'etiqueta': f'Total {i}', 'valor': 1, 'nota': 'palabra ' * 490} for i in range(3)]
        projection = blocks.parse(raw(doc(*figures, {'tipo': 'cifra', 'etiqueta': 'A', 'valor': 2},
                                          {'tipo': 'cifra', 'etiqueta': 'B', 'valor': 3}, {'tipo': 'cifra', 'etiqueta': 'C', 'valor': 4})))
        text = text_of(blocks_pdf.render(projection))  # no LayoutError
        self.assertEqual(text.count('Total 0'), 1)
        self.assertGreaterEqual(text.count('palabra'), 3 * 400)
        checks = {'state': 'complete', 'items': [
            {'block_id': 'b4', 'quote': '2', 'status': 'discrepancy', 'independent_value': 'dos'},
            {'block_id': 'b6', 'quote': '4', 'status': 'discrepancy', 'independent_value': 'cuatro'}]}
        text = text_of(blocks_pdf.render(projection, checks))
        self.assertLess(text.index('cálculo independiente: dos'), text.index('cálculo independiente: cuatro'))
        flow = blocks_pdf._blocks(projection['blocks'], {i['block_id']: [i] for i in checks['items']}, 0, {}, [])
        kinds = [type(x).__name__ for x in flow]
        notices = [i for i, x in enumerate(flow) if getattr(x, 'style', None) is blocks_pdf.NOTICE]
        self.assertEqual(len(notices), 2)
        for i in notices:  # each notice directly follows its own standalone figure paragraph
            self.assertEqual(kinds[i - 1], 'Paragraph')

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
