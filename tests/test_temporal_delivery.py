"""Calendar gaps and multi-series evidence independently checked across surfaces."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader
from decision_room.agent.review_contract import checks
from decision_room.periods import period_index, validate_periods
from decision_room.web.dashboard import presentation
from decision_room.client_report import render_client
from decision_room.report_pdf import render_pdf, line_drawing
from reportlab.graphics.shapes import Line
from test_client_report import sample


def multi():
    data = sample()
    points = [{'label': label, 'value': str(value)} for label, value in [('j_a',10),('j_b',20),('l_a',12),('s_b',30)]]
    data['observations'][0]['result']['series'] = {'channels': dict(unit='unidades', grain='category', points=points,
        evidence=dict(tables=['sales'],operation='Observed monthly quantities by channel; no imputation.'))}
    data['report']['charts'][0].update(series=dict(execution_id='calculation-a',series='channels'), points=[],
        unit='unidades', encoding=dict(category_title='Mes',series_title='Canal',measure='level',temporal_grain='month',
            series_order=['A','B'],coordinates=[dict(label=p['label'],category=month,series=channel)
                for p,month,channel in zip(points,['2026-06','2026-06','2026-07','2026-09'],['A','B','A','B'])]))
    return data


class TemporalDeliveryTests(unittest.TestCase):
    def test_monthly_multi_series_preserve_missing_cells_and_exact_export_values(self):
        data = multi()
        self.assertTrue(all(c['passed'] for c in checks(data['report'],data['observations'])))
        view = presentation(data); chart = view['charts'][0]
        self.assertEqual(chart['temporal_grain'],'month')
        self.assertEqual([p['value'] for p in chart['points']],['10','20','12','30'])
        html = render_client(data,'today')
        self.assertEqual(html.count('<circle '),4)
        self.assertEqual(html.count('class="trend"'),1) # A June-July only; B July absent and August missing.
        for label in ['2026-06','2026-07','2026-09','Sin dato','10,00','30,00']:
            self.assertIn(label,html)
        text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(view))).pages)
        for label in ['2026-06','2026-07','2026-09','Sin dato','10,00','30,00']:
            self.assertIn(label,text)
        # Only one coloured data connection, excluding the grey axis/grid lines.
        drawing = line_drawing(chart)
        self.assertEqual(sum(isinstance(s,Line) and s.strokeWidth==1.8 for s in drawing.contents),1)
    def test_editorial_alternatives_pass_without_changing_evidence(self):
        data = multi(); old = deepcopy(data['observations'])
        for kind in ('bar','line','table'):
            data['report']['charts'][0]['kind']=kind
            self.assertTrue(all(c['passed'] for c in checks(data['report'],data['observations'])))
            self.assertIsNotNone(presentation(data))
        self.assertEqual(data['observations'],old)
    def test_line_scale_is_agent_selected_but_bar_baseline_stays_honest(self):
        data = multi(); chart = data['report']['charts'][0]
        chart['scale'] = 'data'
        self.assertTrue(all(c['passed'] for c in checks(data['report'],data['observations'])))
        chart['kind'] = 'bar'
        self.assertFalse(all(c['passed'] for c in checks(data['report'],data['observations'])))

    def test_arbitrary_unordered_or_misdeclared_periods_are_rejected(self):
        for change in ('category','reversed','grain','duplicate'):
            data = multi(); enc=data['report']['charts'][0]['encoding']
            if change=='category': enc['coordinates'][0]['category']='Canal A'
            if change=='reversed': enc['coordinates'].reverse()
            if change=='grain': enc['temporal_grain']='day'
            if change=='duplicate': enc['coordinates'][1]['label']='j_a'
            with self.subTest(change=change): self.assertFalse(all(c['passed'] for c in checks(data['report'],data['observations'])))
    def test_months_quarters_and_years_have_actual_calendar_spacing(self):
        for grain,labels in [('month',['2026-06','2026-07','2026-09']),('quarter',['2026-Q1','2026-Q2','2026-Q4']),('year',['2024','2025','2027'])]:
            indices=validate_periods(labels,grain)
            self.assertEqual([indices[1]-indices[0],indices[2]-indices[1]],[1,2])
        with self.assertRaises(ValueError): period_index('2026-06','day')

if __name__=='__main__': unittest.main()
