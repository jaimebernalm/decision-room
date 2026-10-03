"""Independent rolling math, saved layer provenance and consistent delivery."""
from copy import deepcopy
from datetime import date, timedelta
import unittest

from decision_room.agent.review_contract import ReportDraft, checks
from decision_room.agent.review_context import approval_digest
from decision_room.agent.delivery_selection import selection_manifest
from decision_room.series import validate_series
from decision_room.chart_evidence import resolve_chart
from decision_room.client_report import render_client
from decision_room.web.dashboard import presentation
from decision_room.report_pdf import render_pdf, line_drawing
from test_client_report import sample


def evidence():
    raw = dict(unit='unidades', grain='day', points=[dict(label=(date(2026, 1, 1)+timedelta(days=i)).isoformat(), value=str(i+1)) for i in range(10)],
               evidence=dict(tables=['sales'], operation='Observed daily sums, no imputation.'))
    mean = dict(unit='unidades', grain='day', points=[dict(label=(date(2026, 1, 3)+timedelta(days=i)).isoformat(), value=str(i+2)) for i in range(8)],
                evidence=dict(tables=['sales'], operation='Mean of the current and previous two consecutive calendar days, HALF_UP to two decimals.'),
                derivation=dict(kind='rolling_mean', source_series='raw', window=3, decimals=2, alignment='trailing', missing='require_full_window'))
    return dict(raw=raw, mean=mean)


def layered():
    data=sample()
    observation=deepcopy(data['observations'][0]); observation['execution_id']='layers-only'
    observation['result']['series']=evidence()
    data['observations'].append(observation)
    chart=data['report']['charts'][0]
    chart.update(points=[], series=None, encoding=None, temporal_grain=None, unit='unidades', layers=[
        dict(key='observed', name='Registro diario', series=dict(execution_id='layers-only', series='raw'), role='observed', style='solid', weight='normal', description='Unidades registradas por fecha.'),
        dict(key='mean', name='Media móvil 3 días', series=dict(execution_id='layers-only', series='mean'), role='derived', style='dashed', weight='emphasis', description='Tres días consecutivos completos, ventana retrospectiva.')])
    return data


class ChartLayerTests(unittest.TestCase):
    def test_rolling_values_and_dates_are_recomputed_without_imputation(self):
        original=evidence()
        validate_series(original, {'sales': {}})
        for fault in ('value', 'lookahead', 'early', 'gap', 'partial', 'unit', 'source', 'tables', 'self'):
            value=deepcopy(original)
            if fault=='value': value['mean']['points'][0]['value']='99'
            elif fault=='lookahead': value['mean']['points'][0]['label']='2026-01-02'
            elif fault=='early': value['mean']['points'].insert(0,dict(label='2026-01-01',value='1'))
            elif fault=='gap': del value['raw']['points'][4]
            elif fault=='partial': value['mean']['points'].pop()
            elif fault=='unit': value['mean']['unit']='EUR'
            elif fault=='source': value['mean']['derivation']['source_series']='absent'
            elif fault=='tables': value['mean']['evidence']['tables']=['other']
            else: value['mean']['derivation']['source_series']='mean'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                validate_series(value, {'sales': {}, 'other': {}})
        self.assertEqual(original,evidence())

    def test_calendar_gaps_remove_all_affected_windows_and_round_once(self):
        series=evidence(); del series['raw']['points'][4]
        series['mean']['points']=[p for p in series['mean']['points'] if p['label'] not in ('2026-01-05','2026-01-06','2026-01-07')]
        validate_series(series,{'sales': {}})
        # Independently known values: mean(3,4,5,6)=4.5 must round HALF_UP to 5.
        series=evidence(); series['mean']['derivation'].update(window=4,decimals=0)
        series['mean']['points']=[dict(label=f'2026-01-{day:02}',value=str(day-1)) for day in range(4,11)]
        validate_series(series,{'sales': {}})
        series['mean']['points'][1]['value']='3' # mean(2,3,4,5)=3.5, not 3.
        with self.assertRaises(ValueError): validate_series(series,{'sales': {}})

    def test_layers_resolve_dates_values_styles_and_early_absences(self):
        data=layered(); original=deepcopy(data)
        ReportDraft.model_validate(data['report'])
        self.assertTrue(all(c['passed'] for c in checks(data['report'],data['observations'])))
        chart,points=resolve_chart(data['report']['charts'][0],data['observations'])
        self.assertEqual(len(points),18)
        coordinates=chart['encoding']['coordinates']
        self.assertEqual(coordinates[0]['category'],'2026-01-01')
        self.assertFalse(any(c['category']=='2026-01-01' and c['series']=='Media móvil 3 días' for c in coordinates))
        self.assertEqual(chart['encoding']['styles']['Media móvil 3 días']['style'],'dashed')
        data['report']['delivery_selections']=[dict(key='curves',title='Dos medidas',chart_keys=['trend'],axis='series',shown_group_count=2,population=None,coverage='selected')]
        self.assertEqual(selection_manifest(data['report'],data['observations'])[0]['actual_group_count'],2)
        self.assertEqual(original['report'],layered()['report'])

    def test_wrong_units_grains_aliases_duplicate_names_and_stale_layers_fail_closed(self):
        for fault in ('unit','grain','alias','duplicate','stale','mixed','bar'):
            data=layered(); chart=data['report']['charts'][0]
            if fault=='unit': chart['unit']='EUR'
            elif fault=='grain':
                # A separate valid monthly series still cannot be on a daily axis.
                saved=data['observations'][1]['result']['series']
                saved['mean']=dict(unit='unidades',grain='month',points=[dict(label='2026-01',value='1'),dict(label='2026-02',value='2')],evidence=dict(tables=['sales'],operation='Monthly sums.'))
            elif fault=='alias': chart['layers'][1]['series']['series']='absent'
            elif fault=='duplicate': chart['layers'][1]['name']=chart['layers'][0]['name']
            elif fault=='stale': data['observations'][1]['current']=False
            elif fault=='mixed': chart['points']=[dict(label='2026-01-01',value=dict(execution_id='calculation-a',metric='first'))]
            else: chart['kind']='bar'
            with self.subTest(fault=fault):
                self.assertFalse(all(c['passed'] for c in checks(data['report'],data['observations'])))

    def test_layer_only_evidence_and_visual_choices_change_the_approval_digest(self):
        data=layered(); before=approval_digest(data,'knowledge')
        data['observations'][1]['code']='Changed independently saved producer'
        self.assertNotEqual(before,approval_digest(data,'knowledge'))
        data=layered(); data['report']['charts'][0]['layers'][1]['weight']='normal'
        self.assertNotEqual(before,approval_digest(data,'knowledge'))

    def test_web_html_and_pdf_keep_each_saved_layer_and_style(self):
        data=layered()
        view=presentation(data)
        self.assertEqual(len(view['charts'][0]['points']),18)
        self.assertEqual(view['charts'][0]['panels'][0]['styles']['Media móvil 3 días']['weight'],'emphasis')
        self.assertIn('Mean of the current',view['claims'][0]['evidence_details']['operations'][1])
        self.assertIn('ventas.csv',view['claims'][0]['evidence_details']['files'])
        html=render_client(data,'today')
        self.assertIn('stroke-dasharray="6 4"',html)
        self.assertIn('stroke-width:2.8',html)
        self.assertIn('Media móvil 3 días',html)
        drawing=line_drawing(view['charts'][0])
        self.assertTrue(any(getattr(shape,'strokeDashArray',None)==[6,4] for shape in drawing.contents))
        self.assertTrue(render_pdf(view).startswith(b'%PDF-'))
