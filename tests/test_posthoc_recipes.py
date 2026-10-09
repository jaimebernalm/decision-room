import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import duckdb
from decision_room.reports.posthoc.inventory import from_snapshot, sha
from decision_room.reports.posthoc import recipes
from decision_room.reports.posthoc.interpretation import masked_request, verify, resolved_reading, segments_of


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.path=self.root/'table.parquet'
        with duckdb.connect() as db:
            db.execute('CREATE TABLE t(day VARCHAR, channel VARCHAR, units INTEGER)')
            db.execute("INSERT INTO t VALUES ('2025-08-30 00:00:00','North',10),('2025-08-31 23:59:59','North',5),('2025-08-31 12:00:00','South',15)")
            db.execute('COPY t TO ?',[str(self.path)])
        self.sources={'sales':{'table_id':'sales','snapshot_sha256':'a'*64,'path':str(self.path),
                'parquet_sha256':sha(self.path.read_bytes()),'columns':[
                    {'name':'day','numeric':False},
                    {'name':'channel','numeric':False,'categories':['North','South']},
                    {'name':'units','numeric':True,'integer':True,'unit':'unidades'}]}}
        self.text='Suma de unidades, North, periodo 2025-08-30 a 2025-08-31: 15. Otra cifra 15.'
        self.inv=from_snapshot(b'original',{'nodes':[{'path':[0],'text':self.text}]})
        self.number=next(o for o in self.inv['occurrences'] if o['text']=='15')

    def recipe(self,request=None):
        text=(request or masked_request(self.inv,self.number,self.sources))['masked_text']
        def ref(value):
            a=text.index(value);return {'span':[a,a+len(value)],'text':value}
        return {'operation':'sum','operands':[{'table_id':'sales','snapshot_sha256':'a'*64,
            'aggregate':'sum','column':'units','filters':[
                {'column':'channel','operator':'in','values':['North']},
                {'column':'day','operator':'date_between','values':['2025-08-30','2025-08-31']}],
            'evidence':{'column':[ref('unidades')],'population':[ref('North')],
                        'period':[ref('2025-08-30 a 2025-08-31')]}}],
            'unit':'unidades','direction':None,'evidence':{'operation':[ref('Suma')],
            'unit':[ref('unidades')],'direction':[]}}

    def test_inclusive_calendar_day_and_hash_guard(self):
        req=masked_request(self.inv,self.number,self.sources);recipe=self.recipe(req)
        recipes.validate(recipe,req['masked_text'],self.sources)
        self.assertEqual(recipes.recalculate(recipe,self.sources)['value'],'15')
        self.path.write_bytes(b'changed')
        with self.assertRaises(ValueError): recipes.recalculate(recipe,self.sources)

    def test_unsupported_units_and_unproved_share_population(self):
        r=self.recipe();r['unit']='euros'
        with self.assertRaises(recipes.Unsupported): recipes.validate(r,self.text,self.sources)
        r=self.recipe();r['operation']='share';r['unit']='%';r['operands']=[copy.deepcopy(r['operands'][0]) for _ in range(2)]
        r['operands'][1]['filters'][0]['values']=['South']
        with self.assertRaises(ValueError): recipes.validate(r,self.text,self.sources)

    def test_derived_operations_empty_selection_and_daily_mean(self):
        a=self.recipe()['operands'][0]
        b=copy.deepcopy(a);b['filters']=[b['filters'][1]]
        for op,expected,unit in [('difference','-15','unidades'),('percent_change','-50','%'),
                                 ('share','50','%'),('quotient','0.5','cociente')]:
            r=self.recipe();r.update(operation=op,operands=[a,b],unit=unit)
            # Arithmetic is independent of whether an unfiltered denominator
            # passes the occurrence-specific totality veto.
            self.assertEqual(float(recipes.recalculate(r,self.sources)['value']),float(expected))
        r=self.recipe();r.update(operation='daily_mean',unit='unidades/día')
        recipes.validate(r,self.text,self.sources)
        self.assertEqual(recipes.recalculate(r,self.sources)['value'],'7.5')
        r=self.recipe();r['operands'][0]['filters'][1]['values']=['2024-01-01','2024-01-02']
        with self.assertRaises(recipes.Unsupported):recipes.recalculate(r,self.sources)

    def test_repeated_value_different_period_does_not_inherit_state(self):
        self.text='Suma de unidades, North, periodo 2025-08-30 a 2025-08-31: 15. Suma de unidades, North, periodo 2025-08-30 a 2025-08-30: 15.'
        self.inv=from_snapshot(b'two periods',{'nodes':[{'path':[0],'text':self.text}]})
        values=[o for o in self.inv['occurrences'] if o['text']=='15']
        def ask(prompt,request,key):
            r=self.recipe(request)
            if request['occurrence_id']==values[1]['id']:
                r['operands'][0]['filters'][1]['values']=['2025-08-30','2025-08-30']
                a=request['masked_text'].index('2025-08-30 a 2025-08-30')
                r['operands'][0]['evidence']['period']=[{'span':[a,a+23],'text':request['masked_text'][a:a+23]}]
            return {'status':'claim','reason':'Separate grounded period','recipe':r}
        ledger=verify(self.inv,self.sources,ask,self.root/'run')
        self.assertEqual([ledger[o['id']]['status'] for o in values],['verified','discrepancy'])

    def test_group_totality_veto_does_not_propagate_a_neighbours_scope(self):
        text='Total de unidades, periodo 2025-08-30 a 2025-08-31: 30.\nTotal de North, unidades, periodo 2025-08-30 a 2025-08-31: 30.'
        first,second=text.split('\n')
        inv=from_snapshot(b'totals',{'nodes':[{'path':[0],'text':first},{'separator':'\n'},{'path':[1],'text':second}]})
        def ask(prompt,request,key):
            readings=[]
            for target in request['targets']:
                start=request['masked_text'].rfind('\n',0,target['span'][0])+1
                def ref(value):
                    a=request['masked_text'].index(value,start)
                    return {'span':[a,a+len(value)],'text':value}
                r=self.recipe()
                r['evidence']={'operation':[ref('Total')],'unit':[ref('unidades')],'direction':[]}
                o=r['operands'][0];o['filters']=o['filters'][1:]
                o['evidence']={'column':[ref('unidades')],'population':[ref('Total')],
                               'period':[ref('2025-08-30 a 2025-08-31')]}
                readings.append({'occurrence_id':target['occurrence_id'],'status':'claim','reason':'fixture','recipe':r})
            return {'readings':readings}
        ledger=verify(inv,self.sources,ask,self.root/'totals',batch_size=4)
        values=[o for o in inv['occurrences'] if o['text']=='30']
        self.assertEqual([ledger[o['id']]['status'] for o in values],['verified','uncertain'])

    def test_missing_or_wrong_citation_cannot_certify(self):
        r=self.recipe();r['operands'][0]['evidence']['period']=[]
        with self.assertRaises(ValueError): recipes.validate(r,self.text,self.sources)
        r=self.recipe();r['evidence']['operation'][0]['text']='Media'
        with self.assertRaises(ValueError): recipes.validate(r,self.text,self.sources)

    def test_period_citations_must_include_each_boundary_year(self):
        text='Suma de unidades North, ene–ago, 2025, 2026'
        def ref(value):
            start=text.index(value)
            return {'span':[start,start+len(value)],'text':value}
        r=self.recipe()
        r['evidence']={'operation':[ref('Suma')],'unit':[ref('unidades')],'direction':[]}
        o=r['operands'][0]
        o['filters'][1]['values']=['2025-01-01','2026-08-31']
        o['evidence']={'column':[ref('unidades')],'population':[ref('North')],
                       'period':[ref('ene–ago')]}
        with self.assertRaisesRegex(ValueError,'cited calendar years'):
            recipes.validate(r,text,self.sources)
        o['evidence']['period'].append(ref('2025'))
        with self.assertRaisesRegex(ValueError,'cited calendar years'):
            recipes.validate(r,text,self.sources)
        o['evidence']['period'].append(ref('2026'))
        recipes.validate(r,text,self.sources)

    def test_two_isolated_calls_freeze_before_recalculation(self):
        calls=[]; real=recipes.recalculate
        def ask(prompt,request,key):
            self.assertNotIn('15',request['masked_text'])
            self.assertNotIn('15',json.dumps(request['context']))
            self.assertNotIn('path',request['catalog'][0])
            calls.append(copy.deepcopy(request))
            return {'status':'claim','reason':'Grounded','recipe':self.recipe(request)}
        def recalc(recipe,sources):
            folders=list((self.root/'run').glob('*/agreed-before-recalculation.json'))
            self.assertTrue(folders)
            return real(recipe,sources)
        with patch.object(recipes,'recalculate',side_effect=recalc):
            ledger=verify(self.inv,self.sources,ask,self.root/'run')
        self.assertEqual(calls[0],calls[1])
        self.assertEqual(ledger[self.number['id']]['status'],'verified')
        with self.assertRaises(FileExistsError): verify(self.inv,self.sources,ask,self.root/'run')

    def test_disagreement_prevents_recalculation_even_when_values_equal(self):
        n=0
        def ask(prompt,request,key):
            nonlocal n
            r=self.recipe(request);n+=1
            if n%2==0:
                r['operands'][0]['filters'][1]['values']=['2025-08-30','2025-08-30']
            return {'status':'claim','reason':'Reading','recipe':r}
        with patch.object(recipes,'recalculate',side_effect=AssertionError('must not calculate')):
            ledger=verify(self.inv,self.sources,ask,self.root/'run')
        self.assertEqual(ledger[self.number['id']]['status'],'uncertain')

    def test_batch_masks_all_targets_and_compares_each_separately(self):
        calls=[]
        def ask(prompt,request,key):
            self.assertNotIn('15',request['masked_text'])
            for target in request['targets']:
                excerpt=target['excerpt'];a,b=excerpt['span'];x,y=excerpt['focus']
                self.assertEqual(excerpt['text'],request['masked_text'][a:b])
                self.assertEqual(excerpt['text'][x:y],'██')
                self.assertNotIn('15',excerpt['text'])
            calls.append(copy.deepcopy(request))
            responses=[]
            for index,target in enumerate(request['targets']):
                r=self.recipe(request)
                if len(calls)==2 and index==1:
                    r['operands'][0]['filters'][1]['values']=['2025-08-30','2025-08-30']
                responses.append({'occurrence_id':target['occurrence_id'],'status':'claim','reason':'Grounded','recipe':r})
            return {'readings':responses}
        ledger=verify(self.inv,self.sources,ask,self.root/'run',batch_size=4)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0],calls[1])
        values=[o for o in self.inv['occurrences'] if o['text']=='15']
        self.assertEqual([ledger[o['id']]['status'] for o in values],['verified','uncertain'])

    def test_alias_citation_cannot_ground_a_different_code(self):
        r=self.recipe();r['operands'][0]['filters'][0]['values']=['South']
        with self.assertRaises(ValueError):recipes.validate(r,self.text,self.sources)
        self.sources['sales']['columns'][1]['aliases']=[{'name':'North','code':'South'}]
        recipes.validate(r,self.text,self.sources)

    def test_mask_equivalent_numeric_spellings_and_percent_spaces(self):
        text='Total 10.679; otra vez 10 679; +10.679; 10,679 mil. Contexto 12,5 %. 42% y 42 %.'
        inv=from_snapshot(b'aliases',{'nodes':[{'path':[0],'text':text}]})
        req=masked_request(inv,inv['occurrences'][0],self.sources)
        for visible in ['10.679','10 679','10,679']:self.assertNotIn(visible,req['masked_text'])
        target=next(o for o in inv['occurrences'] if o['text']=='42%')
        req=masked_request(inv,target,self.sources)
        self.assertNotIn('42',req['masked_text'])

    def test_approximate_values_remain_uncertain_without_model_calls(self):
        inv=from_snapshot(b'approximate',{'nodes':[{'path':[0],'text':'Unas 42 unidades; entre 10 y 20 unidades.'}]})
        def ask(*args):raise AssertionError('Approximation is outside exact verification')
        ledger=verify(inv,self.sources,ask,self.root/'approximate',batch_size=4)
        self.assertEqual(len(ledger),3)
        self.assertEqual({r['status'] for r in ledger.values()},{'uncertain'})

    def test_segment_quotes_resolve_before_recalculation(self):
        def ask(prompt,request,key):
            r=self.recipe(request)
            for evidence in [r['evidence']]+[o['evidence'] for o in r['operands']]:
                for field,refs in evidence.items():
                    evidence[field]=[{'segment_id':next(seg['id'] for seg in request['segments'] if seg['span'][0]<=ref['span'][0]<ref['span'][1]<=seg['span'][1]),'text':ref['text']} for ref in refs]
            return {'status':'claim','reason':'Grounded exact segment quotes','recipe':r}
        ledger=verify(self.inv,self.sources,ask,self.root/'segmented')
        self.assertEqual(ledger[self.number['id']]['status'],'verified')
        folder=self.root/'segmented'/self.number['id']
        self.assertIn('segment_id',(folder/'1.response.json').read_text())
        self.assertNotIn('segment_id',(folder/'1.resolved.json').read_text())
        self.assertTrue((folder/'agreed-before-recalculation.json').exists())

    def test_segment_requires_unique_quote_and_mask_only_is_not_evidence(self):
        from decision_room.reports.posthoc.precision import Uncertain
        text='North North. ██ %'
        request={'masked_text':text,'segments':segments_of(text)}
        reading={'status':'claim','recipe':{'evidence':{'operation':[{'segment_id':'s0000','text':'North'}]},'operands':[]}}
        with self.assertRaises(Uncertain):resolved_reading(reading,request)
        reading['recipe']['evidence']['operation'][0]['text']='South'
        with self.assertRaises(Uncertain):resolved_reading(reading,request)
        reading['recipe']['evidence']['operation'][0]['text']='██ %'
        normalized=resolved_reading(reading,request)
        with self.assertRaises(ValueError):recipes.citation(normalized['recipe']['evidence']['operation'][0],text)
        for value in ['(█████%)','[██]','«██»','— (█ / █) —']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                recipes.citation({'span':[0,len(value)],'text':value},value)

    def test_percent_literal_against_grounded_points_is_discrepancy(self):
        text='Diferencia en puntos porcentuales entre North y el total: 0 %.'
        inv=from_snapshot(b'points',{'nodes':[{'path':[0],'text':text}]})
        recipe=self.recipe();recipe.update(operation='percentage_points',unit='puntos porcentuales')
        a=recipe['operands'][0];b=copy.deepcopy(a);b['filters']=[b['filters'][1]]
        recipe['operands']=[a,b,copy.deepcopy(a),copy.deepcopy(b)]
        # Isolate the comparison policy; grounding is exercised by the other tests.
        def ask(*args):return {'status':'claim','reason':'Grounded points','recipe':recipe}
        with patch.object(recipes,'validate',return_value=None):
            ledger=verify(inv,self.sources,ask,self.root/'points')
        number=next(o for o in inv['occurrences'] if o['text']=='0 %')
        self.assertEqual(ledger[number['id']]['recalculated']['value'],'0')
        self.assertEqual(ledger[number['id']]['status'],'discrepancy')

    def test_provider_failure_is_not_swallowed_or_retried(self):
        calls=[]
        def ask(*args): calls.append(1);raise ConnectionError('offline')
        with self.assertRaises(ConnectionError): verify(self.inv,self.sources,ask,self.root/'run')
        self.assertEqual(len(calls),1)
        self.assertEqual(json.loads((self.root/'run/run.json').read_text())['status'],'failed')
        self.assertFalse((self.root/'run/ledger.json').exists())

if __name__=='__main__':unittest.main()

class SourceTests(unittest.TestCase):
    def test_metadata_has_codes_and_unique_aliases_without_numeric_measure_values(self):
        from decision_room.reports.posthoc.sources import prepare
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'facts.csv').write_text('product_id,unidades\n01,391\n02,876\n01,999\n')
            (root/'products.csv').write_text('product_id,nombre\n01,Small box\n02,Large box\n')
            sources=prepare([root/'facts.csv',root/'products.csv'],root/'prepared')
            public=recipes.public_catalog(sources)
            self.assertNotIn('391',json.dumps(public))
            self.assertNotIn('876',json.dumps(public))
            self.assertNotIn('path',json.dumps(public))
            fact=next(s for s in sources.values() if s['source_name']=='facts.csv')
            ids=next(c for c in fact['columns'] if c['name']=='product_id')
            self.assertEqual(ids['categories'],['01','02'])
            self.assertEqual({a['name']:a['code'] for a in ids['aliases']},{'Large box':'02','Small box':'01'})
            self.assertNotIn('grain',fact)
