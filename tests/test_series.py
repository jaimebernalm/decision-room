"""Series provenance, publication and completeness regression cases."""
from copy import deepcopy
import json
import unittest

from decision_room.execution_contract import validate_result
from decision_room.series import validate_series
from decision_room.agent.review_contract import checks, validate
from decision_room.agent.review_context import approval_digest
from decision_room.client_report import render_client
from test_client_report import sample


def example():
    return {'daily': {'unit': 'moneda no informada', 'grain': 'day',
                     'points': [{'label': '2026-01-01', 'value': '10'}, {'label': '2026-01-03', 'value': '20.005'}],
                     'evidence': {'tables': ['sales'], 'operation': 'Sum by date, no imputation.'}}}


def report():
    data = sample()
    obs = deepcopy(data['observations'][0]); obs['execution_id'] = 'series-only'
    obs['result']['series'] = example()
    data['observations'].append(obs)
    data['report']['charts'][0].update(points=[], series={'execution_id': 'series-only', 'series': 'daily'}, unit='moneda no informada')
    data['report']['highlights'] = [{'label': 'Último día', 'value': {'execution_id': 'calculation-a', 'metric': 'last'},
                                    'unit': 'moneda no informada', 'decimals': 2, 'claim_key': 'sales'}]
    return data


class SeriesTests(unittest.TestCase):
    def test_saved_output_accepts_series_and_preserves_old_results(self):
        data = sample()['observations'][0]['result']
        data.update(schema_version=1, notes=[])
        self.assertNotIn('series', validate_result(json.dumps(data), {'sales': {}}))
        data['series'] = example()
        self.assertEqual(validate_result(json.dumps(data), {'sales': {}})['series'], example())

    def test_untrusted_series_reject_bad_values_labels_sources_and_limits(self):
        for change in ('nan', 'bool', 'null', 'duplicate', 'reverse', 'bad_date', 'foreign', 'missing_evidence', 'excess'):
            with self.subTest(change=change), self.assertRaises(ValueError):
                s = example(); item = s['daily']
                if change in ('nan', 'bool', 'null'):
                    item['points'][0]['value'] = {'nan':'NaN', 'bool':True, 'null':None}[change]
                elif change == 'duplicate': item['points'][1]['label'] = item['points'][0]['label']
                elif change == 'reverse': item['points'].reverse()
                elif change == 'bad_date': item['points'][0]['label'] = 'Jan 1'
                elif change == 'foreign': item['evidence']['tables'] = ['foreign']
                elif change == 'missing_evidence': del item['evidence']
                else: item['points'] *= 184
                validate_series(s, {'sales': {}})

    def test_series_render_all_values_and_preserve_gaps_with_highlights(self):
        data = report(); html = render_client(data, 'today')
        self.assertEqual(html.count('<circle '), 2)
        self.assertNotIn('class="trend"', html)
        self.assertIn('Cifras clave', html)
        self.assertIn('20,01', html)
        self.assertIn('Sum by date, no imputation.', html)
        self.assertLess(html.index('Cifras clave'), html.index('Los datos, en perspectiva'))
        obs = data['observations'][0]['result']
        obs['metrics']['highlight_only'] = '100'
        obs['evidence'].append({'metric':'highlight_only','tables':['sales'],'operation':'Independent summary'})
        data['report']['highlights'][0]['value']['metric'] = 'highlight_only'
        self.assertIn('<th scope="row">highlight_only</th><td>100</td>', render_client(data, 'today'))

    def test_series_only_and_highlight_only_evidence_are_hashed(self):
        data = report(); before = approval_digest(data, 'knowledge')
        data['observations'][1]['result']['series']['daily']['points'][1]['value'] = '21'
        self.assertNotEqual(before, approval_digest(data, 'knowledge'))
        data['report']['charts'] = []
        data['report']['highlights'][0]['value']['execution_id'] = 'series-only'
        before = approval_digest(data, 'knowledge')
        data['observations'][1]['result']['metrics']['last'] = '500'
        self.assertNotEqual(before, approval_digest(data, 'knowledge'))

    def test_stale_omitted_unknown_series_and_unit_mismatch_block_publication(self):
        for change in ('stale', 'omitted', 'unknown', 'unit', 'mixed', 'highlight'):
            with self.subTest(change=change):
                data = report(); c = data['report']['charts'][0]; obs = data['observations'][1]
                if change == 'stale': obs['current'] = False
                elif change == 'omitted': obs['result_omitted'] = True
                elif change == 'unknown': c['series']['series'] = 'invented'
                elif change == 'unit': c['unit'] = 'EUR'
                elif change == 'mixed': c['points'] = sample()['report']['charts'][0]['points']
                else: data['report']['highlights'][0]['value']['metric'] = 'invented'
                self.assertTrue(any(not c['passed'] for c in checks(data['report'], data['observations'])))
                self.assertNotIn('<svg', render_client(data, 'today'))

    def test_incomplete_coverage_blocks_submission_and_approval(self):
        data = report()
        context = {**data, 'plan': {'investigations': [{'key':'trend', 'status':'ready'}]}, 'report_step':1, 'conversation':[]}
        raw = {'action':'submit', 'message':'Borrador', 'report':data['report']}
        with self.assertRaisesRegex(ValueError, 'question_coverage'): validate(raw, 'analyst', context)
        with self.assertRaisesRegex(ValueError, 'question_coverage'): validate({'action':'approve','message':'OK'}, 'reviewer', context)
        data['report']['question_coverage'] = [{'investigation_key':'trend','status':'answered','claim_keys':['sales'],'explanation':'Serie temporal.'}]
        validate(raw, 'analyst', context)
        data['report']['question_coverage'][0]['claim_keys'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'existing report claims'): validate(raw, 'analyst', context)

    def test_series_text_is_escaped_and_monthly_chart_is_not_daily(self):
        data = report(); s = data['observations'][1]['result']['series']['daily']
        s.update(grain='category'); s['points'][0]['label'] = '<script>alert(1)</script>'
        data['report']['charts'][0]['kind'] = 'bar'
        html = render_client(data, 'today')
        self.assertNotIn('<script>', html); self.assertIn('&lt;script&gt;', html)
        s.update(grain='month', points=[{'label':'2026-01','value':'1'}, {'label':'2026-02','value':'2'}])
        data['report']['charts'][0]['kind'] = 'line'
        self.assertNotIn('<svg', render_client(data, 'today'))
