"""Native v1 block format: strict parsing, free structure, projection and canonical text."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from decision_room.engine import blocks


def doc(*items, title='Cómo va el año'):
    return {'version': blocks.VERSION, 'titulo': title, 'bloques': list(items)}


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


FULL = doc(
    {'tipo': 'texto', 'contenido': 'La web crece.\n\nDistribuidores cae.'},
    {'tipo': 'cifra', 'etiqueta': 'Importe neto', 'valor': 39918.54, 'unidad': '€', 'periodo': 'ene–ago 2026',
     'anterior': {'valor': 35000, 'periodo': 'ene–ago 2025'}},
    {'tipo': 'seccion', 'titulo': 'Canales', 'bloques': [
        {'tipo': 'grafico', 'grafico': 'cambio', 'titulo': 'Cambio por canal', 'unidad': '€',
         'categorias': ['Web', 'Tienda', 'Distribuidores'],
         'series': [{'nombre': 'Cambio', 'valores': [6936.74, 120, -15630.29]}]},
        {'tipo': 'tabla', 'titulo': 'Detalle', 'columnas': ['Producto', {'titulo': 'Unidades', 'decimales': 0}],
         'filas': [['Magnesio', 342], ['Colágeno', None]]},
    ]},
    {'tipo': 'prioridad', 'titulo': 'Validar Distribuidores', 'bloques': [
        {'tipo': 'texto', 'contenido': [{'parrafo': ['Magnesio cae a ', {'texto': '342 unidades', 'negrita': True}]},
                                        {'lista': ['Revisar pedidos', ['Comparar con ', {'texto': 'facturas', 'cursiva': True}]],
                                         'numerada': True}]},
    ]},
    {'tipo': 'aviso', 'contenido': 'Faltan registros del 4 al 26 de julio.'},
)


class BlocksTests(unittest.TestCase):
    def test_free_structure_projection_and_text(self):
        p = blocks.parse(raw(FULL))
        self.assertEqual(p['schema'], blocks.VERSION)
        self.assertEqual([b['type'] for b in p['blocks']], ['text', 'figure', 'section', 'priority', 'notice'])
        ids = [b['id'] for b in blocks.walk(p['blocks'])]
        self.assertEqual(ids, ['b1', 'b2', 'b3', 'b3-1', 'b3-2', 'b4', 'b4-1', 'b5'])
        figure = p['blocks'][1]
        self.assertEqual((figure['change'], figure['change_pct'], figure['decimals']), (4918.54, 14.1, 2))
        chart = p['blocks'][2]['blocks'][0]
        self.assertEqual((chart['kind'], chart['fallback']), ('change', False))
        self.assertEqual(chart['series'][0]['values'], [6936.74, 120, -15630.29])
        text = blocks.canonical_text(p)
        self.assertIn('Importe neto: 39.918,54 € (ene–ago 2026); antes 35.000,00 € (ene–ago 2025); cambio +4.918,54 € (+14,1 %)', text)
        self.assertIn('Cambio: Web 6.936,74; Tienda 120,00; Distribuidores −15.630,29', text)
        self.assertIn('Magnesio | 342', text)
        self.assertIn('1. Revisar pedidos', text)
        self.assertIn('Aviso: Faltan registros', text)
        pr = blocks.priorities(p)
        self.assertEqual([x['block_id'] for x in pr], ['b4'])
        self.assertIn('Magnesio cae a 342 unidades', pr[0]['text'])
        json.dumps(p)  # the projection is plain JSON

    def test_minimal_report_and_priority_with_free_content(self):
        p = blocks.parse(raw(doc({'tipo': 'prioridad', 'titulo': 'Mirar la app', 'bloques': [{'tipo': 'texto', 'contenido': 'Lo que quiera.'}]})))
        self.assertEqual(p['blocks'][0]['type'], 'priority')

    def test_unknown_chart_kind_falls_back_to_table(self):
        p = blocks.parse(raw(doc({'tipo': 'grafico', 'grafico': 'dispersión', 'titulo': 'X', 'categorias': ['a', 'b'],
                                  'series': [{'nombre': 's', 'valores': [1, None]}]})))
        chart = p['blocks'][0]
        self.assertEqual((chart['kind'], chart['fallback'], chart['requested_kind']), ('table', True, 'dispersión'))
        self.assertEqual(chart['series'][0]['values'], [1, None])

    def assertInvalid(self, payload, fragment):
        with self.assertRaises(blocks.BlocksError) as caught:
            blocks.parse(payload if isinstance(payload, bytes) else raw(payload))
        self.assertTrue(any(fragment in p for p in caught.exception.problems), caught.exception.problems)

    def test_strict_json(self):
        self.assertInvalid(b'{"version":"a","version":"b"}', 'clave repetida')
        self.assertInvalid(b'{"valor": NaN}', 'NaN')
        self.assertInvalid('{"x": "\udcff"}'.encode('utf-8', 'surrogatepass'), 'UTF-8')
        self.assertInvalid(b'\xef\xbb\xbf{}', 'BOM')
        self.assertInvalid(b'x' * (blocks.MAX_BYTES + 1), 'máximo')
        self.assertInvalid(b'<html></html>', 'JSON no válido')

    def test_schema_errors_are_specific(self):
        self.assertInvalid({'version': 'otra', 'titulo': 't', 'bloques': [{'tipo': 'texto', 'contenido': 'a'}]}, 'informe.version')
        self.assertInvalid(doc({'tipo': 'html', 'contenido': '<b>x</b>'}), 'tipo de bloque desconocido')
        self.assertInvalid(doc({'tipo': 'texto', 'contenido': 'a', 'estilo': 'rojo'}), 'campos no admitidos')
        self.assertInvalid(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': '1.234'}), 'debe ser un número')
        self.assertInvalid(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': True}), 'debe ser un número')
        self.assertInvalid(doc({'tipo': 'grafico', 'grafico': 'barras', 'titulo': 't', 'categorias': ['a', 'b'],
                                'series': [{'nombre': 's', 'valores': [1]}]}), 'un valor (o null) por categoría')
        self.assertInvalid(doc({'tipo': 'grafico', 'grafico': 'barras', 'titulo': 't', 'categorias': ['a'],
                                'series': [{'nombre': 's', 'valores': [None]}]}), 'ningún valor numérico')
        self.assertInvalid(doc({'tipo': 'tabla', 'columnas': ['a', 'b'], 'filas': [['x']]}), 'debe tener 2 celdas')
        self.assertInvalid(doc({'tipo': 'prioridad', 'titulo': 'a', 'bloques': [
            {'tipo': 'prioridad', 'titulo': 'b', 'bloques': [{'tipo': 'texto', 'contenido': 'c'}]}]}), 'dentro de otra prioridad')
        self.assertInvalid(doc({'tipo': 'texto', 'contenido': 'a\x07b'}), 'caracteres de control')
        self.assertInvalid(doc(), 'lista no vacía')

    def test_global_limits(self):
        many = [{'tipo': 'texto', 'contenido': 'x'}] * (blocks.MAX_BLOCKS + 1)
        self.assertInvalid(doc(*many), 'más de')
        deep = {'tipo': 'texto', 'contenido': 'x'}
        for _ in range(blocks.MAX_DEPTH + 1):
            deep = {'tipo': 'seccion', 'titulo': 's', 'bloques': [deep]}
        self.assertInvalid(doc(deep), 'niveles')
        self.assertInvalid(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': 1e16}), 'rango')

    def test_gap_is_not_zero_and_negative_formatting(self):
        p = blocks.parse(raw(doc({'tipo': 'grafico', 'grafico': 'lineas', 'titulo': 'Tasa', 'unidad': '%', 'decimales': 1,
                                  'categorias': ['ene', 'feb', 'mar'],
                                  'series': [{'nombre': 'App', 'valores': [13.7, None, -2.25], 'detalles': ['17 de 124', None, None]}]})))
        line = blocks.canonical_text(p)
        self.assertIn('App: ene 13,7 [17 de 124]; feb —; mar −2,3', line)

    def test_tiny_and_extreme_numbers(self):
        self.assertInvalid(b'{"valor": 1e-9999}', 'rango')
        self.assertInvalid(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': 1e-20}), 'rango')
        self.assertInvalid(b'{"valor": 1e999999999}', 'rango')
        p = blocks.parse(raw(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': 1, 'anterior': {'valor': 1e-15}})))
        self.assertEqual(p['blocks'][0]['change'], 0.999999999999999)  # exact difference; huge percentage stays finite
        self.assertIsNotNone(p['blocks'][0]['change_pct'])

    def test_table_cells_keep_their_own_decimals_unless_the_column_sets_them(self):
        p = blocks.parse(raw(doc({'tipo': 'tabla', 'columnas': ['Indicador', '2025', {'titulo': 'Fijo', 'decimales': 1}],
                                  'filas': [['Unidades', 36644, 2], ['Importe', 504162.69, 2.25]]})))
        text = blocks.canonical_text(p)
        self.assertIn('Unidades | 36.644 | 2,0', text)
        self.assertIn('Importe | 504.162,69 | 2,3 [exacto: 2,25]', text)

    def test_huge_derived_percentage_formats(self):
        p = blocks.parse(raw(doc({'tipo': 'cifra', 'etiqueta': 'x', 'valor': 999999999999999, 'anterior': {'valor': 1e-15}})))
        self.assertIn('cambio +999.999.999.999.999', blocks.canonical_text(p))
        from decision_room.reports import blocks_pdf
        self.assertTrue(blocks_pdf.render(p).startswith(b'%PDF-'))

    def test_exact_values_survive_rounding(self):
        p = blocks.parse(raw(doc({'tipo': 'cifra', 'etiqueta': 'Tasa', 'valor': 0.0001},
                                 {'tipo': 'cifra', 'etiqueta': 'Media', 'valor': 1.25, 'decimales': 0},
                                 {'tipo': 'tabla', 'columnas': [{'titulo': 'v', 'decimales': 0}], 'filas': [[2.5]]})))
        self.assertEqual(p['blocks'][0]['decimals'], 4)
        text = blocks.canonical_text(p)
        self.assertIn('Tasa: 0,0001', text)
        self.assertIn('Media: 1 [exacto: 1,25]', text)
        self.assertIn('3 [exacto: 2,5]', text)

    def test_cli_matches_product_validation(self):
        script = Path(blocks.__file__)
        tmp = Path(self.id().replace('.', '_') + '.json')
        try:
            tmp.write_bytes(raw(FULL))
            ok = subprocess.run([sys.executable, '-I', str(script), str(tmp)], capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertIn('Informe válido: 8 bloques, 1 prioridades', ok.stdout)
            tmp.write_bytes(raw(doc({'tipo': 'texto'})))
            bad = subprocess.run([sys.executable, '-I', str(script), str(tmp)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertIn('faltan los campos «contenido»', bad.stdout)
            guide = subprocess.run([sys.executable, '-I', str(script), '--formato'], capture_output=True, text=True)
            self.assertIn('informe-bloques-1', guide.stdout)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()


class HomeFigureTests(unittest.TestCase):
    def test_disputes_cover_the_block_and_its_ancestors(self):
        from decision_room.web.home import disputed
        items = [{'block_id': 'b5-1', 'status': 'discrepancy'}, {'block_id': 'b2', 'status': 'unverifiable'}]
        self.assertTrue(disputed('b5-1-3', items))
        self.assertTrue(disputed('b5-1', items))
        self.assertFalse(disputed('b5-10', items))
        self.assertFalse(disputed('b2', items))
