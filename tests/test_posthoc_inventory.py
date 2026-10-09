import copy
from pathlib import Path
import tempfile
import unittest

from decision_room.reports.posthoc.inventory import build_inventory, from_snapshot, validate
from decision_room.reports.posthoc.browser import chrome_binary
from decision_room.reports.posthoc.precision import Uncertain, compare, parse_literal, spanish_convention


def snapshot(*parts):
    return {'nodes':[{'path':[n], 'text':text} if isinstance(text,str) else text for n,text in enumerate(parts)]}


class InventoryTests(unittest.TestCase):
    def test_inline_entities_and_unicode_offsets(self):
        inv=from_snapshot(b'original', snapshot('😀 Total: 1.', '234,5', ' %'))
        self.assertEqual(inv['text'], '😀 Total: 1.234,5 %')
        entry=inv['occurrences'][0]
        self.assertEqual(entry['text'],'1.234,5 %')
        self.assertEqual(entry['span'],[9,18])
        self.assertEqual(entry['parts'][0],{'path':[0],'span':[10,12]})
        validate(inv)

    def test_year_followed_by_count_is_not_a_grouped_number(self):
        inv=from_snapshot(b'x',snapshot('En 2026 120 tiendas; total 74 440 unidades.'))
        self.assertEqual([o['text'] for o in inv['occurrences']],['2026','120','74 440'])

    def test_repeat_identity_and_source_integrity(self):
        snap=snapshot('Total 42.', {'separator':'\n'}, 'Total 42.')
        a=from_snapshot(b'a',snap); b=from_snapshot(b'b',snap)
        self.assertEqual(len(a['occurrences']),2)
        self.assertNotEqual(a['occurrences'][0]['id'], a['occurrences'][1]['id'])
        self.assertNotEqual(a['occurrences'][0]['id'], b['occurrences'][0]['id'])
        changed=copy.deepcopy(a); changed['occurrences'][0]['text']='43'
        with self.assertRaises(ValueError): validate(changed)

    def test_date_and_range_are_not_negative_counts(self):
        inv=from_snapshot(b'x', snapshot('2025-01-01; 10-20; caída −332; +12 %'))
        self.assertEqual([o['text'] for o in inv['occurrences']],['2025-01-01','10','20','−332','+12 %'])
        self.assertEqual(inv['occurrences'][0]['kind'],'date')

    def test_browser_visible_dynamic_and_hidden_text(self):
        try: chrome_binary()
        except RuntimeError: self.skipTest('Chrome not installed')
        html=b'''<!doctype html><style>.secret{display:none}</style><body>
        <h1>Informe</h1><p>Total <b>42</b>,5 %</p><p class="secret">999</p>
        <script>document.write('<p>Nuevo 73</p>')</script><svg width="100" height="30"><text y="20">88</text></svg>
        </body>'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.html'; path.write_bytes(html)
            inv=build_inventory(path)
            self.assertEqual([o['text'] for o in inv['occurrences']],['42,5 %','73','88'])
            self.assertEqual(path.read_bytes(),html)
            self.assertEqual(inv,build_inventory(path))


    def test_rendered_table_context_and_chart_region(self):
        try: chrome_binary()
        except RuntimeError: self.skipTest('Chrome not installed')
        html=b'<h1>Results</h1><h2>Year 2025</h2><table><caption>Sales</caption><tr><th>Canal</th><th>Units</th></tr><tr><th>North</th><td>42</td></tr></table><svg width="80" height="30"><text y="20">42</text></svg><h2>Year 2026</h2><p>Total 42</p>'
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.html';path.write_bytes(html)
            inv=build_inventory(path)
        numbers=[o for o in inv['occurrences'] if o['text']=='42']
        cell,chart,prose=numbers
        self.assertEqual(cell['context']['table']['row_headers'][0]['text'],'North')
        self.assertEqual(cell['context']['table']['column_headers'][0]['text'],'Units')
        self.assertEqual(cell['context']['table']['caption'][0]['text'],'Sales')
        self.assertEqual(chart['region'],'chart')
        self.assertEqual(cell['context']['section'][-1]['text'],'Year 2025')
        self.assertEqual(prose['context']['section'][-1]['text'],'Year 2026')
        for item in numbers:
            for ref in item['context']['section']:
                self.assertEqual(inv['text'][slice(*ref['span'])],ref['text'])


class PrecisionTests(unittest.TestCase):
    def test_convention_requires_positive_evidence(self):
        self.assertFalse(spanish_convention(['1.234']))
        with self.assertRaises(Uncertain): parse_literal('1.234')
        self.assertTrue(spanish_convention(['1.234','12,5 %']))
        self.assertEqual(str(parse_literal('1.234',spanish=True).displayed),'1234')
        self.assertFalse(spanish_convention(['12,5 %','12.50']))

    def test_scale_rounding_and_negative_ties(self):
        literal=parse_literal('1,2 M',spanish=True)
        self.assertTrue(compare(literal,'1249000'))
        self.assertFalse(compare(literal,'1251000'))
        self.assertFalse(compare(literal,'1250000'))
        self.assertTrue(compare(parse_literal('-1,3',spanish=True),'-1.25'))
        self.assertTrue(compare(parse_literal('1,3',spanish=True),'1.25'))

    def test_integer_count_is_exact_and_direction_is_not_erased(self):
        lit=parse_literal('12')
        self.assertFalse(compare(lit,'12.4',integer_quantity=True))
        self.assertTrue(compare(lit,'-12',direction=-1))
        self.assertFalse(compare(lit,'12',direction=-1))
        self.assertFalse(compare(parse_literal('+12'),'-12',direction=-1))

    def test_malformed_and_units_are_not_scales(self):
        for raw in ['1.23.4','1,234.5','1 23','12 kg','1-2','NaN','1e3']:
            with self.subTest(raw=raw), self.assertRaises(Uncertain): parse_literal(raw,spanish=True)
        self.assertEqual(str(parse_literal('74\u202f440').displayed),'74440')
        self.assertTrue(parse_literal('12,5 %',spanish=True).percent)

if __name__ == '__main__': unittest.main()
