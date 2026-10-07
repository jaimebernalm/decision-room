import json
from html.parser import HTMLParser
import re
import unittest
import xml.etree.ElementTree as ET

from decision_room.reports.verification import build
from decision_room.reports.verification_contract import validate
from decision_room.web.report_projection import project, render


class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self, data): self.parts.append(data)


class ChartTests(unittest.TestCase):
    def document(self, kind='bar', **extra):
        return {'schema_version': 1, 'title': 'Informe', 'summary': 'Comparación de registros.', 'findings': [],
                'numbers': [{'key': 'a', 'execution_id': 'fixture', 'metric': 'a', 'unit': 'cantidad', 'decimals': 1},
                            {'key': 'b', 'execution_id': 'fixture', 'metric': 'b', 'unit': 'cantidad', 'decimals': 1}],
                'charts': [{'key': 'comparison', 'kind': kind, 'title': 'Cambios', 'caption': 'Valores por grupo.',
                            'series': [{'key': 'quantity', 'label': 'Cantidad', 'points': [
                                {'label': 'Norte', 'number_key': 'a'}, {'label': 'Sur', 'number_key': 'b'}]}]}], **extra}

    def build(self, source, resolver=True):
        raw=json.dumps(source).encode()
        doc, ledger=build(raw, resolver=(lambda r: {'status': 'unverified', 'value': {'a':'-12.5','b':'25'}[r['key']],
                                                  'origin': 'agent_calculation'}) if resolver else None)
        validate(ledger,doc,raw)
        return doc,ledger,render(project(doc))

    def test_reference_occurrences_bind_table_geometry_and_ledger(self):
        doc,ledger,html=self.build(self.document())
        self.assertEqual(doc['charts'][0]['series'][0]['points'][0]['value_text'], '-12.5')
        points=[f for f in ledger['figures'] if f['path'].endswith('/value_text')]
        self.assertEqual([p['value'] for p in points], ['-12.5','25.0'])
        self.assertFalse(any(p['verified'] for p in points))
        svg=ET.fromstring(re.search(r'<svg.*?</svg>', html, re.S)[0])
        rectangles=svg.findall('rect'); self.assertEqual(len(rectangles),2)
        baseline=float(svg.find('line').attrib['y1'])
        self.assertAlmostEqual(float(rectangles[0].attrib['y']),baseline,places=3)
        self.assertLess(float(rectangles[1].attrib['y']),baseline)
        self.assertTrue(all(float(r.attrib['height'])>=0 for r in rectangles))
        self.assertIn('-12.5',html); self.assertIn('25.0',html)

    def test_unknown_value_keeps_textual_table_without_false_zero(self):
        doc,ledger,html=self.build(self.document(),resolver=False)
        self.assertNotIn('<svg',html); self.assertIn('{{n:a}}',html)
        self.assertTrue(all(f['status']=='uncertain' for f in ledger['figures']))
        self.assertIn('sin resolver',html)

    def test_line_category_mismatch_and_mixed_units_keep_full_tables(self):
        source=self.document('line')
        source['charts'][0]['series'].append({'key':'other','label':'Otra','points':[{'label':'Este','number_key':'a'}]})
        _,_,html=self.build(source)
        self.assertNotIn('<svg',html); self.assertIn('Este',html)
        source=self.document(); source['numbers'][1]['unit']='euros'
        _,_,html=self.build(source)
        self.assertNotIn('<svg',html); self.assertIn('unidades distintas',html)

    def test_plain_and_marked_render_have_identical_chart_text_and_geometry(self):
        doc,ledger,marked=self.build(self.document('line'))
        plain=render(project(doc),marks=False)
        a=Text(); b=Text(); a.feed(marked.split('<footer>')[0]); b.feed(plain.split('</main>')[0])
        self.assertEqual(a.parts,b.parts)
        self.assertEqual(re.search(r'<svg.*?</svg>',marked,re.S)[0],re.search(r'<svg.*?</svg>',plain,re.S)[0])
        self.assertIn('<mark',marked); self.assertNotIn('<mark',plain)

    def test_agent_cannot_supply_geometry_or_replace_evidence_values(self):
        for mutation in [lambda c:c.update(svg='<script>steal()</script>'),
                         lambda c:c['series'][0]['points'][0].update(value=999),
                         lambda c:c.update(recommendation_id='invented')]:
            source=self.document(); mutation(source['charts'][0]); raw=json.dumps(source).encode()
            doc,ledger=build(raw)
            self.assertEqual(doc['summary'],raw.decode()); self.assertIn('report_format_fallback',ledger['issues'])
            html=render(project(doc)); self.assertNotIn('<script>',html); self.assertNotIn('<svg',html)

    def test_bounds_and_duplicate_keys_preserve_raw_in_fallback(self):
        for count in [9,101]:
            source=self.document()
            if count==9: source['charts']*=count
            else: source['charts'][0]['series'][0]['points']*=count
            doc,ledger,_=self.build(source)
            self.assertIn('report_format_fallback',ledger['issues'])

    def test_html_labels_are_escaped_in_svg_and_table(self):
        source=self.document(); source['charts'][0]['title']='<img src=x onerror=run()>'
        source['charts'][0]['series'][0]['points'][0]['label']='A<&'
        _,_,html=self.build(source)
        self.assertNotIn('<img',html); self.assertIn('A&lt;&amp;',html)
        ET.fromstring(re.search(r'<svg.*?</svg>',html,re.S)[0])
