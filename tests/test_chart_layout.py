import unittest
from copy import deepcopy
from decision_room.chart_layout import panels, validate_encoding
from decision_room.agent.review_contract import checks
from decision_room.web.dashboard import projection
from decision_room.client_report import render_client
from test_client_report import sample

class ChartLayoutTests(unittest.TestCase):
    def data(self):
        data = sample()
        chart = data['report']['charts'][0]
        chart.update(kind='bar', points=[{'label':'a','value':{'execution_id':'calculation-a','metric':'first'}},
                                        {'label':'b','value':{'execution_id':'calculation-a','metric':'last'}}],
                     encoding={'category_title':'Producto','series_title':'Mes','measure':'level',
                               'series_order':['2026-06','2026-07'],
                               'coordinates':[{'label':'a','category':'Café','series':'2026-06'},
                                              {'label':'b','category':'Café','series':'2026-07'}]})
        return data
    def test_dimensions_preserve_evidence_and_export_legend(self):
        data=self.data()
        self.assertTrue(all(c['passed'] for c in checks(data['report'],data['observations'])))
        view=projection(data)
        self.assertEqual(view['charts'][0]['panels'][0]['series_order'],['2026-06','2026-07'])
        self.assertEqual([p['formatted'] for p in view['charts'][0]['points']],['10,00','20,01'])
        html=render_client(data,'today')
        for text in ['2026-06','2026-07','Café','<rect']:
            self.assertIn(text,html)
        data['observations'][0]['current']=False
        self.assertIsNone(projection(data))
    def test_invalid_mapping_duplicates_and_reversed_dates_block_publication(self):
        for mutation in ('missing','duplicate','reordered','unknown','line'):
            with self.subTest(mutation=mutation):
                data=self.data();chart=data['report']['charts'][0];enc=chart['encoding']
                if mutation=='missing': enc['coordinates'].pop()
                if mutation=='duplicate': enc['coordinates'][1]['series']='2026-06'
                if mutation=='reordered': enc['series_order'].reverse()
                if mutation=='unknown': enc['coordinates'][1]['label']='invented'
                if mutation=='line': chart['kind']='line'
                self.assertIsNone(projection(data))
    def test_legacy_split_is_exact_conservative_and_does_not_mutate(self):
        chart={'kind':'bar'}
        points=[{'label':f'{product} | {period}','value':i}
                for i,product in enumerate(('Producto A','Producto B'))
                for period in ('junio','julio','cambio junio-julio','agosto','cambio julio-agosto')]
        before=deepcopy(points);layout=panels(chart,points)
        self.assertEqual([p['measure'] for p in layout],['level','change'])
        self.assertEqual([len(p['coordinates']) for p in layout],[6,4])
        self.assertEqual(points,before)
        self.assertEqual(panels(chart,points+[{'label':'ambiguo','value':0}]),[])
        self.assertEqual(panels(chart,points+[points[0]]),[])
    def test_sparse_cells_are_valid_and_approval_covers_encoding(self):
        from decision_room.agent.review_context import approval_digest
        data=self.data();chart=data['report']['charts'][0]
        before=approval_digest(data,'context')
        chart['encoding']['coordinates'][1]['category']='Otro producto'
        validate_encoding(chart,chart['points'])
        self.assertNotEqual(before,approval_digest(data,'context'))

    def test_report_palette_distinguishes_collisions_and_is_order_independent(self):
        from decision_room.chart_layout import series_colors
        labels=['2025-01','2026-01','2026-07','junio','julio','agosto']
        colors=series_colors(labels)
        self.assertEqual(len(set(colors.values())),len(labels))
        self.assertEqual(colors,series_colors(reversed(labels)))

    def test_palette_remains_fixed_even_when_a_report_has_many_distinct_series(self):
        from decision_room.chart_layout import CHART_PALETTE, CHART_SERIES_PALETTE, CHART_NEUTRALS, series_colors
        self.assertEqual(len(CHART_SERIES_PALETTE), 6)
        self.assertEqual(len(CHART_NEUTRALS), 3)
        self.assertEqual(set(CHART_PALETTE), set(CHART_SERIES_PALETTE) | set(CHART_NEUTRALS.values()))
        colors=series_colors(f'series-{i}' for i in range(40))
        self.assertEqual(len(colors),40)
        self.assertLessEqual(set(colors.values()),set(CHART_SERIES_PALETTE))
        html=render_client(self.data(),'today')
        view=projection(self.data())
        for color in view['charts'][0]['panels'][0]['colors'].values():
            self.assertIn(color,CHART_PALETTE)
            self.assertIn(f'fill="{color}"',html)
