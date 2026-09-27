"""Real PostgreSQL + full Parquet checks, without model guesses."""
from uuid import uuid4
import unittest

import test_agent
from test_agent import ScriptedModel
from decision_room import service as ingestion
from decision_room.database import connect
from decision_room.data_knowledge import service as knowledge
from decision_room.memory import context, retrieval
from decision_room.agent import service as agent
from decision_room.conversations import snapshot, fresh, dependencies_current
from decision_room.web import data_model


class DataKnowledgeTests(unittest.TestCase):
    setUpClass = classmethod(test_agent.AgentTests.setUpClass.__func__)
    tearDownClass = classmethod(test_agent.AgentTests.tearDownClass.__func__)
    setUp = test_agent.AgentTests.setUp
    # Reuse database lifecycle, not the parent's full model test suite.
    def tables(self, files):
        paths=[]
        for name,content in files.items():
            path=self.root/name
            path.write_text(content)
            paths.append(path)
        analysis=ingestion.import_batch(self.config,self.business,paths)['analysis']['id']
        with connect(self.config) as db:
            model=knowledge.latest(db,self.business,analysis)
        return analysis,model

    def test_whole_file_profiles_and_unsafe_relation(self):
        analysis,model=self.tables({'Customers.csv':'CustomerID,name\n01,A\n02,B\n02,C\n',
            'Invoices.csv':'InvoiceID,CustomerID,amount,date\n1,01,10,2025-01-01\n2,02,20,2025-02-01\n3,03,bad,invalid\n4,,40,2025-03-01\n'})
        relations=model['body']['relations']
        self.assertEqual(len(relations),1)
        r=relations[0]
        self.assertEqual(r['semantic_status'],'proposed')
        self.assertEqual(r['verification'],'attention')
        self.assertEqual(r['evidence']['unmatched_rows'],1)
        self.assertEqual(r['evidence']['extra_rows'],1)
        self.assertEqual(r['evidence']['left_join_rows'],5)
        self.assertEqual(r['evidence']['source']['missing_rows'],1)
        invoice=next(t for t in model['body']['tables'] if t['name']=='Invoices.csv')
        amount=next(c for c in invoice['columns'] if c['name']=='amount')
        self.assertEqual(amount['logical_type'],'text')
        self.assertEqual(amount['numeric_parseable'],3)
        self.assertEqual(knowledge.ensure(self.config,self.business,analysis)['revision'],1)

    def test_composite_many_to_many_and_lexical_identity(self):
        analysis,model=self.tables({'left.csv':'a,b,amount\n01,x,10\n01,x,20\n2,y,30\n',
                                   'right.csv':'a,b,name\n01,x,A\n01,x,B\n2,z,C\n'})
        self.assertEqual(model['body']['relations'],[])
        left,right=model['body']['tables']
        result=knowledge.change(self.config,self.business,analysis,1,'relation',dict(source=left['id'],target=right['id'],
            source_columns=['a','b'],target_columns=['a','b'],semantic_status='confirmed',description='Business linkage'))
        r=result['body']['relations'][0]
        self.assertEqual(r['cardinality'],'many-to-many')
        self.assertEqual(r['verification'],'attention')
        self.assertEqual(r['evidence']['inner_join_rows'],4)
        self.assertEqual(r['evidence']['extra_rows'],2)
        self.assertEqual(r['evidence']['unmatched_rows'],1)
        with self.assertRaises(ValueError):
            knowledge.change(self.config,self.business,analysis,1,'table',{'id':left['id'],'grain':'stale'})
        result=knowledge.change(self.config,self.business,analysis,2,'table',{'id':left['id'],'declared_keys':[['a','b']]})
        self.assertFalse(result['body']['tables'][0]['declared_keys'][0]['valid'])
        with connect(self.config) as db:
            self.assertEqual(knowledge.latest(db,self.business,analysis,1)['body']['relations'],[])

    def test_reuse_reports_chat_and_correction_invalidation(self):
        first=agent.start(self.config,self.business,self.analysis,owner_context='units',request_key='first',model=ScriptedModel())
        second=agent.start(self.config,self.business,self.analysis,owner_context='units',request_key='second',model=ScriptedModel())
        with connect(self.config) as db:
            m=context.manifest(db,first['id'])
            table=m['selection']['original_source']['tables'][0]['id']
            observed,deps=retrieval.retrieve(self.config,db,first['id'],dict(tool='inspect_dataset',id=table,query='',limit=1))
            chat=snapshot(db,self.business,self.analysis,'Explain the data')
            other,deps2=retrieval.retrieve(self.config,db,None,dict(tool='inspect_dataset',id=table,query='',limit=1),manifest=chat)
            self.assertEqual(observed['data_model'],other['data_model'])
            self.assertTrue(fresh(db,chat))
            self.assertEqual(context.manifest(db,second['id'])['initial_context']['data_model']['revision'],1)
        changed=knowledge.change(self.config,self.business,self.analysis,1,'table',{'id':table,'grain':'A sale','columns':[{'name':'amount','meaning':'Gross amount','unit':'EUR'}]})
        with connect(self.config) as db:
            self.assertFalse(fresh(db,chat))
            self.assertFalse(dependencies_current(self.config,db,chat,[{'dependencies':deps2}]))
            self.assertIn('Data model corrected',context.reason(db,first['id']))
            self.assertIn('Data model corrected',context.reason(db,second['id']))
            self.assertEqual(knowledge.inspect(db,self.business,table)['revision'],changed['revision'])
        third=agent.start(self.config,self.business,self.analysis,owner_context='units',request_key='third',model=ScriptedModel())
        with connect(self.config) as db:
            self.assertIsNone(context.reason(db,third['id']))
            self.assertEqual(context.manifest(db,third['id'])['initial_context']['data_model']['revision'],2)

    def test_replacement_revalidates_and_isolation(self):
        analysis,model=self.tables({'Customers.csv':'CustomerID,name\n1,A\n2,B\n','Invoices.csv':'InvoiceID,CustomerID\n1,1\n2,2\n'})
        r=model['body']['relations'][0]
        knowledge.change(self.config,self.business,analysis,1,'relation',{k:r[k] for k in ('source','target','source_columns','target_columns')}|{'semantic_status':'confirmed'})
        newer,newmodel=self.tables({'Customers.csv':'CustomerID,name\n1,A\n1,B\n','Invoices.csv':'InvoiceID,CustomerID\n1,1\n2,2\n'})
        self.assertNotEqual(analysis,newer)
        self.assertEqual(newmodel['body']['relations'][0]['semantic_status'],'proposed')
        self.assertEqual(newmodel['body']['relations'][0]['verification'],'attention')
        other=ingestion.create_business(self.config,'Other business')['id']
        with connect(self.config) as db:
            self.assertIsNone(knowledge.latest(db,other,analysis))
            self.assertIsNone(knowledge.inspect(db,other,r['source']))
        with self.assertRaises(ValueError):
            knowledge.change(self.config,other,analysis,2,'table',{'id':r['source'],'grain':'private'})

    def test_metric_scope_and_web_graph_same_document(self):
        with connect(self.config) as db:
            model=knowledge.latest(db,self.business,self.analysis)
        table=model['body']['tables'][0]['id']
        saved=knowledge.change(self.config,self.business,self.analysis,1,'metric',dict(key='net',name='Net sales',definition='amount minus tax, signed returns retained',unit='EUR',table_ids=[table],period_from='2025-01-01',period_until='2025-12-31'))
        class Workspace:
            config=self.config
            def business_id(inner):return self.business
        web=data_model.read(Workspace(),str(self.analysis))
        with connect(self.config) as db:
            read=knowledge.inspect(db,self.business,table)
        self.assertEqual(web['model']['body']['metrics'],read['metrics'])
        self.assertEqual(web['model']['revision'],saved['revision'])
        self.assertEqual(len(web['history']),2)

    def test_invalid_retrieval_is_bounded_correction(self):
        class BadLookup(ScriptedModel):
            def generate(inner,ctx,correction=None):
                if not correction:
                    return {'action':'retrieve','retrieval':None,'table_ids':[],'proposal':None},{}
                return super().generate(ctx,correction)
        result=agent.start(self.config,self.business,self.analysis,owner_context='units',request_key='bad-null',model=BadLookup())
        self.assertEqual(result['status'],'waiting')
        with connect(self.config) as db:
            for bad in (None,{'tool':'open_report','id':'','query':'','limit':1},{'tool':'inspect_dataset','id':'invalid','query':'','limit':1}):
                with self.assertRaises(ValueError):
                    retrieval.retrieve(self.config,db,result['id'],bad)

    def test_completed_reports_keep_history_and_require_review_after_correction(self):
        from test_research import ResearchModel
        from test_review import DialogueModel
        from decision_room.agent import research, review
        reports=[]
        for number in range(2):
            model=ResearchModel()
            plan=agent.start(self.config,self.business,self.analysis,owner_context='Amount is unit price. Quantity is units.',request_key=f'report-{number}',model=model)
            run=research.start(self.config,self.business,plan['id'],request_key=f'research-{number}',model=model)
            class BadLookupOnce(DialogueModel):
                malformed = True
                def generate_reviewer(inner, ctx, correction=None):
                    if inner.malformed:
                        inner.malformed=False
                        return dict(action='retrieve',retrieval=None if number==0 else dict(tool='open_report',id='',query='',limit=1),code='',table_ids=[],report=None,question='',message='Lookup'),{}
                    return super().generate_reviewer(ctx,correction)
            roles=BadLookupOnce()
            report=review.start(self.config,self.business,run['id'],request_key=f'review-{number}',analyst=roles,reviewer=roles)
            self.assertTrue(report['publishable'])
            self.assertTrue(all(c['business_context']['data_model']['revision']==1 for c in roles.contexts))
            reports.append(report)
        with connect(self.config) as db:
            model=knowledge.latest(db,self.business,self.analysis)
        knowledge.change(self.config,self.business,self.analysis,1,'table',dict(id=model['body']['tables'][0]['id'],grain='A recorded sale'))
        for previous in reports:
            now=review.show(self.config,self.business,previous['id'])
            self.assertFalse(now['publishable'])
            self.assertEqual(now['status'],'stale')
            self.assertEqual(now['approved_sha256'],previous['approved_sha256'])

    def test_catalog_citations_are_delivered_scoped_and_confirmed_only(self):
        from decision_room.agent.contracts import validate_action
        from copy import deepcopy
        with connect(self.config) as db:
            model=knowledge.latest(db,self.business,self.analysis)
        table=model['body']['tables'][0]['id']
        knowledge.change(self.config,self.business,self.analysis,1,'metric',dict(key='amount',name='Amount',definition='Total of each sale',unit='EUR',table_ids=[table]))
        plan=agent.start(self.config,self.business,self.analysis,owner_context='Analyze data',request_key='citations',model=ScriptedModel())
        with connect(self.config) as db:
            m=context.manifest(db,plan['id'])
            retrieval.save(self.config,db,plan['id'],'test',1,dict(tool='inspect_dataset',id=table,query='',limit=1))
            supplied=context.delivered(db,plan['id'])
            refs=supplied['retrievals'][0]['response']['data_model']['references']
            metric=next(r for r in refs if r['kind']=='metric')
            unconfirmed=next(r for r in refs if r['kind']=='table')
        action=deepcopy(plan['revisions'][0]['proposal'])
        action['interpretations']=[dict(aspect='meaning',status='confirmed',statement='Owner declares the total of each sale.',references=[dict(kind='data_model',id=metric['reference'],column='')])]
        raw=dict(action='propose',table_ids=[],proposal=action)
        source={**m['selection']['original_source'],'business_context':supplied}
        validate_action(raw,source,[table],[])
        action['interpretations'][0]['references'][0]['id']='dm:invented'
        with self.assertRaisesRegex(ValueError,'exact delivered'):
            validate_action(raw,source,[table],[])
        action['interpretations'][0]['references'][0]['id']=unconfirmed['reference']
        with self.assertRaisesRegex(ValueError,'Confirmed definitions'):
            validate_action(raw,source,[table],[])
        action['interpretations'][0]['references'][0]['id']=metric['reference']
        supplied['authorized_analysis_id']=str(uuid4())
        with self.assertRaisesRegex(ValueError,'scoped'):
            validate_action(raw,source,[table],[])

    def test_key_arguments_are_arrays_and_preserve_leading_zeroes(self):
        analysis,model=self.tables({'left.csv':'a\n01\n','right.csv':'a\n1\n'})
        a,b=model['body']['tables']
        payload=dict(source=a['id'],target=b['id'],source_columns='a',target_columns=['a'])
        with self.assertRaisesRegex(ValueError,'lista'):
            knowledge.change(self.config,self.business,analysis,1,'relation',payload)
        payload['source_columns']=['a']
        saved=knowledge.change(self.config,self.business,analysis,1,'relation',payload)
        self.assertEqual(saved['body']['relations'][0]['evidence']['unmatched_rows'],1)
        self.assertEqual(saved['body']['relations'][0]['verification'],'attention')

    def test_http_auth_business_scope_history_and_optimistic_edit(self):
        import threading
        import httpx
        from decision_room.web.server import Server
        from decision_room.web.service import Workspace
        with connect(self.config) as db:
            db.execute('INSERT INTO web_businesses(business_id,creation_key,creation_sha256) VALUES (%s,%s,%s)',(self.business,uuid4(),'test'))
            db.execute('UPDATE web_workspace SET active_business_id=%s WHERE singleton',(self.business,))
            table=knowledge.latest(db,self.business,self.analysis)['body']['tables'][0]['id']
        server=Server(Workspace(self.config),0,token='catalog-local-test')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=httpx.Client(base_url=server.origin,headers={'Origin':server.origin,'X-Decision-Room':'1'})
        self.addCleanup(client.close)
        path='/api/business/data-model'
        query=dict(analysis_id=str(self.analysis))
        self.assertEqual(client.get(path,params=query).status_code,401)
        self.assertEqual(client.post('/api/login',json={'token':'catalog-local-test'}).status_code,200)
        self.assertEqual(client.get(path,params=query).json()['model']['revision'],1)
        payload=dict(business_id=str(uuid4()),analysis_id=str(self.analysis),action='table',expected_revision=1,payload={'id':table,'grain':'One sale'})
        self.assertEqual(client.post(path,json=payload).status_code,409)
        payload['business_id']=str(self.business)
        self.assertEqual(client.post(path,json=payload).json()['model']['revision'],2)
        payload['payload']['grain']='Different edit from an old page'
        self.assertEqual(client.post(path,json=payload).status_code,409)
        historic=client.get(path,params={**query,'revision':1}).json()
        self.assertEqual(historic['model']['body']['tables'][0]['grain'],'')
        self.assertEqual(client.get(path,params={**query,'revision':999}).status_code,404)
        self.assertEqual(client.get(path,params={'analysis_id':str(uuid4())}).status_code,404)

    def test_changed_prepared_metadata_cannot_reuse_old_model(self):
        from psycopg.types.json import Jsonb
        with connect(self.config) as db:
            model=knowledge.latest(db,self.business,self.analysis)
            table=model['body']['tables'][0]
            source=db.execute('SELECT original_names FROM sources WHERE id=%s',(table['source_id'],)).fetchone()
            db.execute('UPDATE sources SET original_names=%s WHERE id=%s',(Jsonb(['renamed.csv',*source['original_names']]),table['source_id']))
            self.assertFalse(knowledge.current(db,self.business,{'analysis_id':str(self.analysis),'revision':1}))
            self.assertIsNone(knowledge.inspect(db,self.business,table['id']))
        rebuilt=knowledge.ensure(self.config,self.business,self.analysis)
        self.assertEqual(rebuilt['revision'],2)
        self.assertEqual(rebuilt['body']['tables'][0]['name'],'renamed.csv')
