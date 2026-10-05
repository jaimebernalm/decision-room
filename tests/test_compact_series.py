"""Compacted wire series remain compatible and charts resolve full stored data."""
from copy import deepcopy
from datetime import date,timedelta
import json
import unittest
from unittest.mock import patch
import httpx
from decision_room.agent.model import ModelClient,ModelSettings,record_request
from decision_room.agent.review_budget import compact
from decision_room.agent.review_contract import checks
from decision_room.chart_evidence import resolve_chart
from decision_room.series import validate_series
from test_review_budget import large_context


def context():
    result=large_context()
    item=next(o for o in result['observations'] if o['execution_id']=='layers-only')
    series=item['result']['series']
    for key,offset in (('raw',0),('mean',2)):
        series[key]['unit']='unidades registradas (unidad de conteo definida por el propietario)'
        series[key]['points']=[dict(label=str(date(2021,9,1)+timedelta(days=i)),value=str(i+1 if key=='raw' else i)) for i in range(offset,90)]
    validate_series(series,{'sales':{}})
    return result


class CompactSeriesTests(unittest.TestCase):
    def test_metadata_and_sampling_for_both_budget_levels(self):
        source=context(); original=deepcopy(source)
        for level in (0,1):
            packed=compact(source,level)
            item=next(o for o in packed['observations'] if o['execution_id']=='layers-only')
            for key,series in item['result']['series'].items():
                full=next(o for o in source['observations'] if o['execution_id']=='layers-only')['result']['series'][key]
                self.assertEqual(series['unit'],full['unit'])
                self.assertEqual(series['grain'],'day')
                self.assertEqual(series['label'],key)
                self.assertEqual(series['point_count'],len(full['points']))
                self.assertTrue(series['sampled']);self.assertTrue(series['points_summary']['sampled'])
                self.assertEqual(series['first_point'],full['points'][0])
                self.assertEqual(series['last_point'],full['points'][-1])
                self.assertEqual(series['minimum'],full['points'][0])
                self.assertEqual(series['maximum'],full['points'][-1])
                self.assertIn('read_review_context',series['points_summary']['detail'])
        self.assertEqual(source,original)

    def test_extrema_are_from_full_series_even_when_absent_in_sample(self):
        source=context()
        series=next(o for o in source['observations'] if o['execution_id']=='layers-only')['result']['series']
        del series['mean']
        series['raw']['points'][5]['value']='-12.500'
        series['raw']['points'][6]['value']='999.125'
        packed=next(o for o in compact(source)['observations'] if o['execution_id']=='layers-only')['result']['series']['raw']
        self.assertEqual(packed['minimum']['value'],'-12.500')
        self.assertEqual(packed['maximum']['value'],'999.125')
        self.assertNotIn(packed['minimum'],packed['points'])
        self.assertNotIn(packed['maximum'],packed['points'])

    def test_http_payload_supports_layers_with_all_original_points(self):
        for stable in (False,True):
            source=context();source['budgets']['review_stable_prefix']=stable
            saved=[]
            transport=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={
                'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})))
            with patch('decision_room.agent.model.httpx.AsyncClient',return_value=transport),record_request(saved.append):
                ModelClient(ModelSettings('offline',protocol='chat_completions')).generate_analyst_review(source)
            packed={}
            for message in saved[0]['payload']['messages'][1:]:
                data=json.loads(message['content']);packed.update(data.get('stable_review_context',data.get('review_evidence',data)))
            visible=next(o for o in packed['observations'] if o['execution_id']=='layers-only')['result']['series']
            report=deepcopy(source['report']);chart=report['charts'][0]
            chart['unit']=visible['raw']['unit']
            for layer,key in zip(chart['layers'],('raw','mean')):
                layer['series']=visible[key]['full_series_reference']
            self.assertTrue(all(c['passed'] for c in checks(report,source['observations'])))
            _,points=resolve_chart(chart,source['observations'])
            self.assertEqual(len(points),178)
            self.assertLess(len(visible['raw']['points']),90)
            self.assertEqual(chart['points'],[])
            chart['unit']='unidades registradas'  # plausible abbreviation is incompatible
            self.assertFalse(all(c['passed'] for c in checks(report,source['observations'])))
