"""Saved view coverage: removing a view must not retain its claimed groups."""
from copy import deepcopy
from io import BytesIO
import unittest
from pypdf import PdfReader

from decision_room.agent.delivery_selection import selection_manifest, selection_notes, validate_selections
from decision_room.agent.review_context import approval_digest
from decision_room.agent.review_policy import delivery_manifest
from decision_room.client_report import render_client
from decision_room.report_pdf import render_pdf
from decision_room.web.dashboard import presentation
from test_temporal_delivery import multi


def inventory():
    data = multi()
    source = data['observations'][0]
    source['result']['series'] = {}
    template = data['report']['charts'][0]
    charts = []
    groups = [f'group_{i}' for i in range(18)]
    for batch in range(3):
        chart = deepcopy(template)
        name = f'view_{batch}'
        points, coordinates = [], []
        subset = groups[batch*6:(batch+1)*6]
        for month in ['2026-06', '2026-07', '2026-08']:
            for group in subset:
                label = f'{month}_{group}'
                points.append(dict(label=label,value='10'))
                coordinates.append(dict(label=label,category=month,series=group))
        source['result']['series'][name] = dict(unit='unidades',grain='category',points=points,
            evidence=dict(tables=['sales'],operation='Monthly quantities by explicitly selected groups.'))
        chart.update(key=name,series=dict(execution_id=source['execution_id'],series=name),points=[])
        chart['encoding'].update(series_order=subset,coordinates=coordinates)
        charts.append(chart)
    source['result']['series']['population'] = dict(unit='unidades',grain='category',
        points=[dict(label=g,value='30') for g in groups],
        evidence=dict(tables=['sales'],operation='All observed groups in received sales.'))
    data['report']['charts'] = charts
    data['report']['delivery_selections'] = [dict(key='groups',title='Grupos observados',
        chart_keys=[c['key'] for c in charts],axis='series',shown_group_count=18,
        population=dict(execution_id=source['execution_id'],series='population'),coverage='all_reference')]
    return data


class SelectionTests(unittest.TestCase):
    def test_full_and_focal_delivery_use_actual_union_not_point_count(self):
        data = inventory()
        result = validate_selections(data['report'],data['observations'],5)
        self.assertEqual((result[0]['actual_group_count'],result[0]['reference_group_count']),(18,18))
        data['report']['charts'].pop()
        selection = data['report']['delivery_selections'][0]
        selection.update(chart_keys=['view_0','view_1'],shown_group_count=12,coverage='selected')
        result = validate_selections(data['report'],data['observations'],5)
        self.assertEqual(result[0]['actual_group_count'],12)
        self.assertIn('12 elementos mostrados de 18',selection_notes(data['report'],data['observations'])[0])

    def test_removed_third_view_cannot_be_claimed_as_eighteen_groups(self):
        data = inventory(); data['report']['charts'].pop()
        with self.assertRaisesRegex(ValueError,'missing/duplicate'):
            validate_selections(data['report'],data['observations'],5)
        selection = data['report']['delivery_selections'][0]
        selection['chart_keys'].pop()
        with self.assertRaisesRegex(ValueError,'declares 18 groups but delivers 12'):
            validate_selections(data['report'],data['observations'],5)
        selection['shown_group_count'] = 12
        with self.assertRaisesRegex(ValueError,'whole saved reference'):
            validate_selections(data['report'],data['observations'],5)

    def test_old_reports_keep_manifest_and_new_charts_need_selection(self):
        data = multi()
        before = delivery_manifest(data['report'],data['observations'])
        self.assertNotIn('selections',before)
        validate_selections(data['report'],data['observations'],4)
        with self.assertRaisesRegex(ValueError,'Every current chart'):
            validate_selections(data['report'],data['observations'],5)
        data['report']['charts'] = []
        validate_selections(data['report'],data['observations'],5)

    def test_explicit_groups_cannot_use_obsolete_population_or_invented_coordinates(self):
        for mutation in ['obsolete','foreign','missing','duplicate','unknown_population']:
            data = inventory()
            if mutation == 'obsolete': data['observations'][0]['current'] = False
            elif mutation == 'foreign': data['report']['charts'][0]['encoding']['coordinates'][0]['series'] = 'invented'
            elif mutation == 'missing': data['report']['charts'][0]['encoding']['coordinates'].pop()
            elif mutation == 'duplicate':
                coords=data['report']['charts'][0]['encoding']['coordinates']; coords[0]=deepcopy(coords[1])
            else: data['report']['delivery_selections'][0]['population']['series']='missing'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                validate_selections(data['report'],data['observations'],5)

    def test_alternative_views_and_overlap_preserve_group_identities(self):
        data = multi(); chart = data['report']['charts'][0]
        data['report']['delivery_selections'] = [dict(key='channels',title='Canales',chart_keys=['trend'],
            axis='series',shown_group_count=2,population=None,coverage='selected')]
        for kind in ('line','bar','table'):
            chart['kind']=kind
            self.assertEqual(validate_selections(data['report'],data['observations'],5)[0]['groups'],['A','B'])
        other=deepcopy(chart); other['key']='other'; data['report']['charts'].append(other)
        data['report']['delivery_selections'][0]['chart_keys'].append('other')
        self.assertEqual(validate_selections(data['report'],data['observations'],5)[0]['actual_group_count'],2)

    def test_reference_population_is_bound_to_approval_even_if_not_plotted(self):
        data=inventory()
        extra=deepcopy(data['observations'][0]);extra['execution_id']='population-only'
        extra['result']['series']={'population':extra['result']['series']['population']}
        data['observations'].append(extra)
        data['report']['delivery_selections'][0]['population']['execution_id']='population-only'
        before=approval_digest(data,'knowledge')
        extra['result']['series']['population']['evidence']['operation']='Filtered source population.'
        self.assertNotEqual(before,approval_digest(data,'knowledge'))

    def test_client_and_pdf_preserve_exact_controller_count(self):
        data=multi()
        data['report']['delivery_selections']=[dict(key='channels',title='Canales observados',chart_keys=['trend'],
            axis='series',shown_group_count=2,population=None,coverage='selected')]
        note=selection_notes(data['report'],data['observations'])[0]
        data['report']['limitations'].append(note)
        html=render_client(data,'today')
        text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(presentation(data)))).pages)
        self.assertIn(note,html); self.assertIn(note,text)
        self.assertEqual(delivery_manifest(data['report'],data['observations'])['selections'][0]['actual_group_count'],2)


if __name__ == '__main__': unittest.main()
