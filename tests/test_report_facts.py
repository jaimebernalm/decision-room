"""Scoped facts cannot certify a free-prose attribution or agent-labelled unit."""
from datetime import date
import json
import unittest

from decision_room.engine import admission, numbers
from decision_room.reports import panorama_facts
from decision_room.reports.verification import build
from decision_room.reports.verification_contract import validate
from decision_room.sales_panorama import summarize
from decision_room.web.report_projection import project, render
from tests import test_engine_panorama as fixtures


class FactTests(unittest.TestCase):
    def raw(self, **extra):
        return json.dumps({'schema_version':1, 'title':'Lectura', 'summary':'Importe {{n:q}} euros.',
            'findings':[{'key':'priority','title':'Investigar','statement':'Hipótesis pendiente.', 'facts':['q']}],
            'numbers':[{'key':'q','execution_id':'fixture','metric':'total','unit':'euros','decimals':1}], **extra}).encode()

    def check(self, ref):
        return {'status':'verified_in_scope', 'origin':'deterministic_panorama', 'value':'15', 'original_value':'15',
                'display':{'label':'Cantidad registrada del grupo', 'scope':'Canal «Sur»; columna «quantity».',
                           'unit':'cantidad registrada', 'limitation':'No certifica cobertura ni causas.'}}

    def test_only_recipe_generated_scope_receives_verified_label(self):
        raw=self.raw(); doc,ledger=build(raw,resolver=self.check)
        fact=doc['findings'][0]['facts'][0]['text']
        self.assertIn('15.0 cantidad registrada',fact); self.assertIn('Canal «Sur»',fact)
        scoped=[f for f in ledger['figures'] if f['path'].startswith('/findings/0/facts/')]
        inline=[f for f in ledger['figures'] if f['path']=='/summary']
        self.assertTrue(scoped[0]['verified']); self.assertFalse(inline[0]['verified'])
        self.assertEqual(scoped[0]['unit'],'cantidad registrada')
        self.assertEqual(scoped[0]['recommendation_id'],'priority')
        self.assertEqual(scoped[0]['path'],'/findings/0/facts/0/text')
        validate(ledger,doc,raw)
        self.assertIn('Canal «Sur»',render(project(doc),marks=False))
        self.assertIn('class="checked"',render(project(doc)))

    def test_facts_stay_with_their_finding_including_a_fact_only_finding(self):
        raw=self.raw(findings=[{'key':'first','title':'Primero','facts':['q']},
                              {'key':'second','title':'Segundo','facts':['q']},
                              {'key':'third','facts':['q']}],facts=['q'])
        doc,ledger=build(raw,resolver=self.check)
        html=render(project(doc),marks=False)
        self.assertEqual(html.count('<aside'),4)
        first=html.index('<h2>Primero'); second=html.index('<h2>Segundo')
        self.assertEqual(html[:first].count('<aside'),1)
        self.assertEqual(html[first:second].count('<aside'),1)
        self.assertEqual(html[second:].count('<aside'),2)

    def test_correction_retains_original_and_scoped_proof_without_approving_prose(self):
        def check(ref): return {**self.check(ref), 'status':'corrected_in_scope','original_value':'999'}
        doc,ledger=build(self.raw(),resolver=check)
        figures=[f for f in ledger['figures'] if f['value']=='15.0']
        self.assertEqual([f['status'] for f in figures],['corrected','corrected'])
        self.assertEqual([f['verified'] for f in figures],[False,True])
        self.assertTrue(all(f['corrected_from']=='999' for f in figures))

    def test_agent_or_unavailable_recipe_never_certifies_fact(self):
        for status,origin in [('unverified','agent_calculation'),('unavailable','deterministic_panorama')]:
            doc,ledger=build(self.raw(),resolver=lambda ref:{**self.check(ref),'status':status,'origin':origin})
            self.assertFalse(any(f['verified'] for f in ledger['figures']))
            self.assertIn('sin ámbito comprobado',doc['findings'][0]['facts'][0]['text'])

    def test_source_names_that_look_like_templates_are_literal_scope_data(self):
        def check(ref):
            value=self.check(ref); value['display']['scope']='Canal «{{n:q}}»; columna «quantity».'; return value
        doc,ledger=build(self.raw(),resolver=check)
        self.assertIn('Canal «{{n:q}}»',doc['findings'][0]['facts'][0]['text'])
        self.assertEqual(sum(f['verified'] for f in ledger['figures']),1)

    def test_excess_generated_facts_preserves_raw_without_expanding(self):
        raw=json.dumps({'schema_version':1,'title':'Many facts','summary':'Keep this',
            'findings':[{'key':str(i),'facts':['q']*32} for i in range(9)]}).encode()
        doc,ledger=build(raw,resolver=self.check)
        self.assertEqual(doc['summary'],raw.decode())
        self.assertIn('report_format_fallback',ledger['issues'])
        self.assertFalse(any(f['verified'] for f in ledger['figures']))

    def test_agent_cannot_override_generated_fact_label_scope_or_value(self):
        raw=self.raw(facts=[{'number_key':'q','scope':'Producto Norte','value':999}])
        doc,ledger=build(raw,resolver=self.check)
        self.assertEqual(doc['summary'],raw.decode())
        self.assertIn('report_format_fallback',ledger['issues'])
        self.assertFalse(any(f['verified'] for f in ledger['figures']))

    def test_panorama_descriptors_distinguish_product_channel_period_and_units(self):
        data=summarize([(date(2025,1,1),'Same','Same',2,1),(date(2025,1,31),'Same','Same',3,1),
                        (date(2025,2,1),'Same','Same',4,1),(date(2025,2,28),'Same','Same',6,1)],
                       {'date':'date','product':'product','channel':'channel','quantity':'quantity'},4)
        summary=data['summary']
        product=panorama_facts.describe(summary,'product_0_total')
        channel=panorama_facts.describe(summary,'channel_0_total')
        self.assertIn('Producto «Same»',product['scope']); self.assertNotIn('Canal «Same»',product['scope'])
        self.assertIn('Canal «Same»',channel['scope'])
        period=panorama_facts.describe(summary,'period_current')
        self.assertIn('2025-02-01',period['scope']); self.assertNotIn('2025-01-01',period['scope'])
        self.assertEqual(panorama_facts.describe(summary,'before_days')['unit'],'días naturales')
        self.assertIsNone(panorama_facts.describe(summary,'unknown'))


class FactIntegrationTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PanoramaTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PanoramaTests.tearDownClass.__func__)
    setUp=fixtures.PanoramaTests.setUp
    create=fixtures.PanoramaTests.create
    calculate=fixtures.PanoramaTests.calculate

    def test_fact_is_generated_after_recalculation_of_own_snapshot_only(self):
        row=self.calculate()
        observation=next(o for o in row['body']['observations'] if 'total' in o['result']['metrics'])
        ref={'key':'total','execution_id':observation['execution_id'],'metric':'total'}
        raw=json.dumps({'schema_version':1,'title':'Resumen','summary':'','findings':[],
                        'facts':['total'],'numbers':[ref]}).encode()
        job=admission.authenticate(self.config,self.run,self.token)
        doc,ledger=build(raw,resolver=lambda r:numbers._check(self.config,job,r,{}))
        verified=[f for f in ledger['figures'] if f['verified']]
        self.assertEqual(len(verified),1); self.assertEqual(verified[0]['value'],'15.00')
        self.assertIn('quantity',doc['facts'][0]['text'])
        other,token=self.create(); foreign=admission.authenticate(self.config,other,token)
        doc,ledger=build(raw,resolver=lambda r:numbers._check(self.config,foreign,r,{}))
        self.assertFalse(any(f['verified'] for f in ledger['figures']))
