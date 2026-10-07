"""Percentage recipes use compatible operands and preserve their visible bases."""
from copy import deepcopy
from datetime import date
import json
import unittest

from decision_room.engine import admission, numbers, ratios
from decision_room.reports.verification import build
from decision_room.reports.verification_contract import validate
from decision_room.reports import panorama_facts
from decision_room.sales_panorama import summarize
from decision_room.web.report_projection import project, render
from tests import test_engine_panorama as fixtures


class RatioTests(unittest.TestCase):
    def source(self, before=5, current=10):
        from decimal import Decimal
        return summarize([(date(2025,1,1),'Item','Local',Decimal(before),1),
                          (date(2025,1,31),'Item','Local',Decimal(0),1),
                          (date(2025,2,1),'Item','Local',Decimal(current),1),
                          (date(2025,2,28),'Item','Local',Decimal(0),1)],
                         {'date':'date','product':'product','channel':'channel','quantity':'quantity'},4)

    def test_ratios_are_engine_only_and_keep_unadjusted_windows(self):
        source=self.source(); before=deepcopy(source); extended=ratios.extend(source)
        self.assertEqual(source,before); self.assertNotIn('ratios',source['summary'])
        values=extended['result']['metrics']
        self.assertEqual(values['period_current_change_pct'],'100')
        self.assertEqual(values['channel_0_total_share_pct'],'100')
        fact=panorama_facts.describe(extended['summary'],'period_current_change_pct',values)
        self.assertIn('2025-01-01',fact['scope']); self.assertIn('2025-02-28',fact['scope'])
        self.assertIn('No ajusta distinta duración',fact['scope'])
        self.assertEqual([float(x['value']) for x in fact['operands']],[10,5])
        self.assertEqual(fact['unit'],'%')

    def test_zero_negative_or_missing_bases_do_not_fabricate_percentages(self):
        for before in (0,-5):
            body=ratios.extend(self.source(before=before))
            self.assertNotIn('period_current_change_pct',body['result']['metrics'])
            item=next(r for r in body['summary']['ratios'] if r['left']['metric']=='period_current')
            self.assertIsNone(item['value']); self.assertIn('cero o negativa',item['reason'])
        source=self.source(); source['summary']['comparison']['status']='unavailable'
        body=ratios.extend(source)
        self.assertFalse(any(r['kind']=='change' for r in body['summary']['ratios']))
        self.assertEqual(ratios.extend({'status':'unavailable','reason':'missing'}),{'status':'unavailable','reason':'missing'})

    def test_share_does_not_claim_negative_quantity_is_a_positive_fraction(self):
        source=self.source(); metric=source['summary']['totals']['channel'][0]['value']['metric']
        source['result']['metrics'][metric]='-2'
        body=ratios.extend(source)
        self.assertNotIn(metric+'_share_pct',body['result']['metrics'])
        item=next(r for r in body['summary']['ratios'] if r['left']['metric']==metric)
        self.assertIn('fuera del total',item['reason'])

    def test_decrease_and_fractional_base_are_decimal_not_integer_division(self):
        body=ratios.extend(self.source(before='0.3',current='0.2'))
        self.assertEqual(body['result']['metrics']['period_current_change_pct'],'-33.333333333333')

    def test_fact_renders_percentage_and_both_operands_with_distinct_exact_spans(self):
        body=ratios.extend(self.source()); metric='period_current_change_pct'
        display=panorama_facts.describe(body['summary'],metric,body['result']['metrics'])
        raw=json.dumps({'schema_version':1,'title':'Comparación','summary':'','findings':[],
                        'facts':['ratio'],'numbers':[{'key':'ratio','execution_id':'fixture','metric':metric}]}).encode()
        doc,ledger=build(raw,resolver=lambda _:{'value':'100','status':'verified_in_scope','origin':'deterministic_panorama','display':display})
        figures=[f for f in ledger['figures'] if f['verified']]
        self.assertEqual([f['text'] for f in figures],['100.00','10','5'])
        self.assertEqual([f['unit'] for f in figures],['%','cantidad registrada','cantidad registrada'])
        self.assertTrue(all(f['path']=='/facts/0/text' for f in figures))
        self.assertIn('Anterior (base): 5 cantidad registrada',render(project(doc),marks=False))
        self.assertEqual(len(set(f['id'] for f in figures)),3)
        validate(ledger,doc,raw)


class RatioIntegrationTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PanoramaTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PanoramaTests.tearDownClass.__func__)
    setUp=fixtures.PanoramaTests.setUp
    create=fixtures.PanoramaTests.create
    calculate=fixtures.PanoramaTests.calculate

    def test_frozen_ratios_are_paged_evidence_recalculated_from_the_same_snapshot(self):
        row=self.calculate(); metric='period_current_change_pct'
        observation=next(o for o in row['body']['observations'] if metric in o['result']['metrics'])
        self.assertEqual(observation['specification']['ratios'],ratios.identity())
        ref={'key':'growth','execution_id':observation['execution_id'],'metric':metric}
        checked=numbers.verify(self.config,self.run,self.token,request_key='growth',numbers=[ref])['body']['checks'][0]
        self.assertEqual((checked['status'],checked['value']),('verified_in_scope','100'))
        raw=json.dumps({'schema_version':1,'title':'Variación','summary':'','findings':[{'key':'review','facts':['growth']}], 'numbers':[ref]}).encode()
        job=admission.authenticate(self.config,self.run,self.token)
        doc,ledger=build(raw,resolver=lambda r:numbers._check(self.config,job,r,{}))
        self.assertEqual([f['value'] for f in ledger['figures'] if f['verified']],['100.00','10','5'])
        validate(ledger,doc,raw)
        other,token=self.create()
        checked=numbers.verify(self.config,other,token,request_key='foreign',numbers=[ref])['body']['checks'][0]
        self.assertEqual(checked['status'],'unavailable')

    def test_changed_recipe_identity_is_not_recertified(self):
        from unittest.mock import patch
        row=self.calculate(); metric='period_current_change_pct'
        observation=next(o for o in row['body']['observations'] if metric in o['result']['metrics'])
        ref={'key':'growth','execution_id':observation['execution_id'],'metric':metric}
        with patch.object(ratios,'identity',return_value={'version':'other','code_sha256':'0'*64}):
            checked=numbers.verify(self.config,self.run,self.token,request_key='changed',numbers=[ref])['body']['checks'][0]
        self.assertEqual((checked['status'],checked['reason']),('unverified','recipe_unavailable'))
