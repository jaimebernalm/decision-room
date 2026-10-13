"""The checker's coverage self-check counts exactly what the platform will publish."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from decision_room.engine import blocks, check_contract as contract, check_coverage as coverage


def projection():
    return blocks.parse(json.dumps(dict(version=blocks.VERSION, titulo='T', bloques=[
        dict(tipo='prioridad', titulo='1. Revisar la app', bloques=[
            dict(tipo='texto', contenido='La app reúne 111 de 212 ausencias (52,4 %).'),
            dict(tipo='tabla', titulo='Por canal', columnas=['Canal', 'Citas', 'Ausencias'],
                 filas=[['App', 745, 111], ['Web', 1054, 78]]),
            dict(tipo='accion', comprobar='Cruzar los registros de reserva.')])])).encode())


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.projection = projection()
        self.priority = blocks.priorities(self.projection)[0]
        self.text = self.priority['text']
        self.data = dict(revision_sha256='a' * 64, priorities=[dict(self.priority, lineas=coverage.lines(self.text))])

    def item(self, line, status='confirmed'):
        return dict(priority_id=self.priority['block_id'], quote=line['texto'], start=line['start'], end=line['end'],
                    status=status, independent_value=None, method='Recalculado desde los CSV.', message='')

    def check(self, items):
        return dict(version=contract.VERSION, revision_sha256='a' * 64, items=items, coverage_notes='')

    def run_tool(self, check):
        with tempfile.TemporaryDirectory() as folder:
            priorities, output = Path(folder) / 'prioridades.json', Path(folder) / 'comprobacion.json'
            priorities.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
            output.write_text(check if isinstance(check, str) else json.dumps(check, ensure_ascii=False), encoding='utf-8')
            printed = io.StringIO()
            with redirect_stdout(printed):
                status = coverage.main(['comprobar_cobertura.py', str(output)], priorities=str(priorities))
        return status, printed.getvalue()

    def test_the_priority_ordinal_is_not_a_figure_and_lines_carry_exact_offsets(self):
        self.assertTrue(self.text.startswith('Prioridad: 1. Revisar'))
        self.assertEqual([m.group() for m in coverage.numbers(self.text)], ['111', '212', '52,4 %', '745', '111', '1.054', '78'])
        lines = coverage.lines(self.text)
        self.assertEqual([line['cifras'] for line in lines], [3, 2, 2])
        for line in lines:
            self.assertEqual(self.text[line['start']:line['end']], line['texto'])
        result = contract.parse(json.dumps(self.check([])).encode(), self.projection, 'a' * 64)
        self.assertEqual(result['coverage']['numeric_spans'], 7)
        self.assertEqual(result['items'][-1]['quote'], '111')
        self.assertIn('7 cifras de esta prioridad', result['items'][-1]['message'])

    def test_one_item_per_line_covers_every_figure_for_the_tool_and_the_platform(self):
        check = self.check([self.item(line) for line in coverage.lines(self.text)])
        status, printed = self.run_tool(check)
        self.assertEqual(status, 0, printed)
        self.assertIn('Las 7 cifras', printed)
        result = contract.parse(json.dumps(check).encode(), self.projection, 'a' * 64)
        self.assertEqual(result['coverage'], dict(numeric_spans=7, addressed_spans=7, confirmed_spans=7, priorities=1))
        self.assertEqual(contract.visible(result)['items'], [])
        self.assertEqual({i['block_id'] for i in result['items']}, {'b1-1', 'b1-2'})

    def test_lines_left_without_an_item_are_listed_with_their_offsets(self):
        first, *rest = coverage.lines(self.text)
        status, printed = self.run_tool(self.check([self.item(first)]))
        self.assertEqual(status, 1)
        self.assertIn('4 de 7 cifras', printed)
        listed = [json.loads(line) for line in printed.splitlines() if line.startswith('{')]
        self.assertEqual([(x['start'], x['end'], x['cifras_sin_item']) for x in listed], [(x['start'], x['end'], 2) for x in rest])
        result = contract.parse(json.dumps(self.check([self.item(first)])).encode(), self.projection, 'a' * 64)
        self.assertEqual(result['coverage']['addressed_spans'], 3)

    def test_what_the_platform_refuses_is_reported_before_coverage(self):
        line = coverage.lines(self.text)[0]
        cases = [
            dict(self.item(line), start=line['start'] + 1),
            dict(self.item(line), start=None, end=None),
            dict(self.item(line), method=''),
            dict(self.item(line), priority_id='b99'),
            dict(self.item(line), status='ok'),
        ]
        for item in cases:
            with self.subTest(item=item):
                status, printed = self.run_tool(self.check([item]))
                self.assertEqual(status, 1)
                self.assertIn('todavía no es válido', printed)
                with self.assertRaises(contract.CheckError):
                    contract.parse(json.dumps(self.check([item])).encode(), self.projection, 'a' * 64)
        status, printed = self.run_tool(dict(self.check([self.item(line)]), revision_sha256='b' * 64))
        self.assertIn('revision_sha256', printed)
        self.assertEqual(self.run_tool('{')[0], 1)

    def test_the_prompt_asks_for_every_figure_and_names_the_tool_and_lines(self):
        self.assertIn('en lineas, cada\nlínea de ese texto que tiene cifras', contract.PROMPT)
        self.assertIn('python3 /inputs/herramientas/comprobar_cobertura.py /work/comprobacion.json', contract.PROMPT)
        self.assertIn('cada fila es una línea', contract.PROMPT)
