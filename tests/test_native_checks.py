"""Native cycle recovery, delegated authority and quotas on a real disposable DB."""
import json
from unittest.mock import patch
from uuid import uuid4
import unittest
from psycopg.types.json import Jsonb
from decision_room.database import connect, migrate
from decision_room.engine import admission, api, blocks, check_contract as contract, native_checks as checks, profile, store, control
from tests import test_engine_admission as fixtures
from tests.test_native_blocks import example
from tests.engine_fakes import FakeRuntime, FakeClient, FakeTunnel
from types import SimpleNamespace


class CheckTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp=fixtures.EngineTests.setUp
    create=fixtures.EngineTests.create

    def native(self):
        run,token=self.create(engine_config=profile.configuration(model='test-model',format='blocks'))
        receipt=store.receive_document(self.config,run,token,request_key='draft',html=json.dumps(example()).encode(),via='file')
        receipt=store.read_document(self.config,self.business,run)
        return run,token,receipt,api._row(self.config,self.business,run)

    def insert(self,run,receipt,token='checker-token'):
        ident=uuid4()
        with connect(self.config) as db:
            db.execute('''INSERT INTO engine_native_checks(id,run_id,business_id,revision_id,raw_sha256,version,
                credential_sha256,instance_id,message_id,input_sha256) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (ident,run,self.business,receipt['revision_id'],receipt['raw_sha256'],contract.VERSION+'-initial',
                 admission.sha(token.encode()),uuid4(),'msg_'+uuid4().hex,'a'*64))
        return ident

    def test_delegate_cannot_access_mcp_receipts_owner_or_another_run_and_shares_parent_quotas(self):
        run,token,receipt,row=self.native(); ident=self.insert(run,receipt)
        self.assertEqual(admission.authenticate(self.config,run,'checker-token',allow_checker=True)['id'],run)
        with self.assertRaises(admission.Denied):admission.authenticate(self.config,run,'checker-token')
        from decision_room.engine import gateway,questions
        with self.assertRaises(admission.Denied):gateway.dispatch(self.config,run,'checker-token',{'jsonrpc':'2.0','id':1,'method':'tools/list'})
        with self.assertRaises(admission.Denied):store.receive_document(self.config,run,'checker-token',request_key='x',html=b'{}')
        with self.assertRaises(admission.Denied):questions.request(self.config,run,'checker-token',request_key='q',text='Q',reason='R')
        for i in range(20):
            call=admission.begin_call(self.config,run,'checker-token','a'*64)
            admission.reserve(self.config,run,'checker-token',call,10,5)
            admission.settle(self.config,run,call,usage=dict(input=10,output=5,cached=0))
        with self.assertRaises(admission.Denied):admission.begin_call(self.config,run,'checker-token','a'*64)
        usage=admission.inspect_run(self.config,self.business,run)
        self.assertEqual((usage['calls'],usage['charged_input'],usage['charged_output']),(20,200,100))
        self.assertEqual(usage['status'],'running')

    def test_checker_inputs_exclude_panorama_writer_state_and_results(self):
        run,token,receipt,row=self.native()
        files=checks.inputs(self.config,row,receipt,blocks.parse(receipt['raw']))
        self.assertTrue(any(k.startswith('datos/') for k in files))
        self.assertEqual(set(k for k in files if not k.startswith('datos/')),{'manifest.json','prioridades.json','contexto/definiciones.txt'})
        self.assertNotIn('panorama.md',files)
        priorities=json.loads(files['prioridades.json'])
        self.assertEqual(priorities['revision_sha256'],receipt['raw_sha256'])
        self.assertNotIn('state',files)
        self.assertNotIn('informe.json', files['contexto/definiciones.txt'].decode())
        self.assertNotIn('comprobar_informe', files['contexto/definiciones.txt'].decode())

    def test_recovery_never_resends_or_grants_another_budget_and_preserves_draft(self):
        run,token,receipt,row=self.native();ident=self.insert(run,receipt)
        # Even if death was before submit, lack of an acknowledgement is not a
        # licence to launch another checker. No Docker mutation when no meta.
        with patch.object(api,'Runtime',side_effect=AssertionError('new runtime')):
            self.assertTrue(checks.recover(self.config,row))
            self.assertFalse(checks.recover(self.config,row))
        self.assertEqual(store.read_document(self.config,self.business,run)['raw'],receipt['raw'])
        with connect(self.config) as db:
            check=db.execute('SELECT * FROM engine_native_checks WHERE id=%s',(ident,)).fetchone()
            self.assertEqual(check['status'],'incomplete')
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_runs WHERE business_id=%s',(self.business,)).fetchone()['n'],1)
        migrate(self.config);migrate(self.config)

    def test_context_revocation_and_result_hash_are_fail_closed(self):
        run,token,receipt,row=self.native();ident=self.insert(run,receipt)
        with patch.object(checks.registry,'reason',return_value='memory_changed'),self.assertRaises(admission.Denied):
            checks._finish_check(self.config,row,ident,result=dict(state='complete',items=[]))
        with self.assertRaises(ValueError):checks._result(dict(status='complete',result=dict(state='complete'),result_sha256='b'*64))

    def test_check_identity_and_completion_are_immutable(self):
        run,token,receipt,row=self.native();ident=self.insert(run,receipt)
        result=dict(state='complete',items=[],version=contract.VERSION,revision_sha256=receipt['raw_sha256'])
        checks._finish_check(self.config,row,ident,result=result)
        self.assertEqual(checks._finish_check(self.config,row,ident,result=result),result)
        with connect(self.config) as db:
            with self.assertRaises(Exception):db.execute('UPDATE engine_native_checks SET result=%s WHERE id=%s',(Jsonb({}),ident))
            with self.assertRaises(Exception):db.execute('DELETE FROM engine_native_checks WHERE id=%s',(ident,))
            with self.assertRaises(Exception):db.execute('UPDATE engine_native_checks SET business_id=%s WHERE id=%s',(uuid4(),ident))

    def test_recovery_accounts_inflight_delegate_without_new_allowance(self):
        run,token,receipt,row=self.native();self.insert(run,receipt)
        call=admission.begin_call(self.config,run,'checker-token','f'*64)
        admission.reserve(self.config,run,'checker-token',call,100,20)
        checks.recover(self.config,row)
        usage=admission.inspect_run(self.config,self.business,run)
        self.assertEqual(usage['status'],'aborted')
        self.assertEqual(usage['model_calls'][0]['state'],'uncertain')
        self.assertEqual((usage['charged_input'],usage['charged_output']),(100,20))

    def test_delegated_proxy_spends_the_same_parent_dollar_ledger(self):
        from decision_room.engine import proxy,provider_budget
        import httpx
        run,token=admission.create_run(self.config,self.business,self.analysis,table_ids=[self.table],owner_context='Fixture units',
            request_key=uuid4().hex,model='gpt-6-luna',engine_config=profile.configuration(model='gpt-6-luna',format='blocks',usd_cap_micro=400000))
        store.receive_document(self.config,run,token,request_key='draft',html=json.dumps(example()).encode(),via='file')
        receipt=store.read_document(self.config,self.business,run);self.insert(run,receipt)
        sent=[]
        def provider(request):
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':1})
            sent.append(request)
            state=provider_budget.ledger(self.config,api._row(self.config,self.business,run)).snapshot()
            self.assertEqual(state['charged_nano_usd'],358500000)
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default','status':'completed',
                'usage':{'input_tokens':1050000,'output_tokens':128000}})
        with self.assertRaises(admission.Aborted):
            proxy.forward(self.config,run,'checker-token',admission.canonical({'model':'gpt-6-luna','input':'Fixture','stream':False}),
                api_key='test-only',transport=httpx.MockTransport(provider),send_headers=lambda *a:None,write=lambda *a:None)
        self.assertEqual(len(sent),1)
        self.assertEqual(provider_budget.ledger(self.config,api._row(self.config,self.business,run)).snapshot()['charged_nano_usd'],358500000)

    def test_standalone_retained_check_has_no_writer_cycle_or_publication_and_no_replay(self):
        raw=json.dumps(example()).encode();FakeRuntime.sessions={};FakeClient.config=self.config
        IndependentRuntime.payloads=[];IndependentClient.checker_results=[]
        run,token=admission.create_run(self.config,self.business,self.analysis,table_ids=[self.table],owner_context='Fixture units',
            request_key=uuid4().hex,model='gpt-6-luna',engine_config=profile.configuration(model='gpt-6-luna',format='blocks',usd_cap_micro=400000,image='sha256:'+'a'*64))
        with patch.object(api,'Runtime',IndependentRuntime),patch.object(api,'DockerBackend',lambda:object()),patch.object(api,'JobTunnel',FakeTunnel),patch.object(api,'_service',lambda *a:SimpleNamespace(origin='http://127.0.0.1:1')):
            result=checks.run_standalone(self.config,self.business,run,token,raw)
            self.assertEqual(result['state'],'complete')
            self.assertEqual(checks.run_standalone(self.config,self.business,run,token,raw),result)
            with self.assertRaises(ValueError):checks.run_standalone(self.config,self.business,run,token,raw.replace(b'5 units',b'4 units')+b' ')
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM engine_sessions WHERE run_id=%s',(run,)).fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM engine_native_cycles WHERE run_id=%s',(run,)).fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM report_documents WHERE source_run_id=%s',(run,)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_native_checks WHERE run_id=%s',(run,)).fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT status FROM engine_runs WHERE id=%s',(run,)).fetchone()['status'],'failed')


class IndependentRuntime(FakeRuntime):
    """Fake isolated volumes, exercising the real checker controller, not its output."""
    payloads=[]
    def __init__(self, backend, **kwargs):
        super().__init__(backend,**kwargs)
        # Checker generations never share the writer's state even under one run.
        if kwargs['token'].startswith('checker'):
            raise AssertionError('Tests must use real delegated credentials.')
        from decision_room.database import connect
        with connect(FakeClient.config) as db:
            check=db.execute('SELECT 1 FROM engine_native_checks WHERE instance_id=%s',(kwargs['instance_id'],)).fetchone()
        self.checker=bool(check)
        if self.checker:self.state=self.sessions.setdefault(self.instance_id,{'session':None,'messages':[]})
    def start(self):return IndependentClient(self)


class IndependentClient(FakeClient):
    checker_results=[]
    def submit(self, session, **kwargs):
        if self.runtime.checker:
            priority=json.loads(self.state['files']['prioridades.json'])
            value=(self.checker_results.pop(0)(priority) if self.checker_results else
                   dict(version=contract.VERSION,revision_sha256=priority['revision_sha256'],items=[],coverage_notes='Sin confirmación; caso simulado.'))
            self.runtime.payload=json.dumps(value).encode()
        else:
            self.runtime.payload=IndependentRuntime.payloads.pop(0) if IndependentRuntime.payloads else json.dumps(example()).encode()
        super().submit(session,**kwargs)


class ProductCycleTests(unittest.TestCase):
    from tests import test_engine_jobs as product
    setUpClass=classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass=classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp=product.EngineJobTests.setUp
    create=product.EngineJobTests.create
    pinned=product.EngineJobTests.pinned
    fake_runtime=product.EngineJobTests.fake_runtime

    def runtime(self):
        self.fake_runtime();IndependentRuntime.payloads=[];IndependentClient.checker_results=[]
        p=patch.object(api,'Runtime',IndependentRuntime);p.start();self.addCleanup(p.stop)

    def test_complete_checker_uses_independent_files_and_publication_with_warnings(self):
        from decision_room.reports import reading
        self.runtime();job=self.create(engine_kind='opencode',engine_format='blocks')
        self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'completed',row['issue'])
        with reading.read(self.config,row['business_id'],row['report_document_id']) as (db,doc,rev):
            self.assertEqual(doc['current_revision_id'],rev['id'])
            self.assertTrue(reading.metadata(db,doc,rev)['is_current'])
            view=reading.view(db,doc,rev)
            self.assertEqual(view['checks']['state'],'complete')
            self.assertTrue(view['checks']['items'])
            self.assertTrue(all(i['status']=='unverifiable' for i in view['checks']['items']))
            chat=reading.chat_document(db,row['business_id'],doc['id'])
            self.assertEqual(chat['origin'],'engine_blocks')
            self.assertIn('no se recalcularon de forma independiente',chat['text'])
            checks_rows=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchall()
            self.assertEqual(len(checks_rows),1)
            self.assertEqual(checks_rows[0]['status'],'complete')
            state=IndependentRuntime.sessions[str(checks_rows[0]['instance_id'])]
            self.assertNotIn('contexto/panorama.md',state['files'])
            self.assertNotIn('herramientas/comprobar_informe.py',state['files'])
            runrow=api._row(self.config,row['business_id'],row['engine_run_id'])
            definitions=checks.inputs(self.config,runrow,store.read_document(self.config,row['business_id'],row['engine_run_id']),view['blocks'])['contexto/definiciones.txt'].decode()
            self.assertEqual(definitions,runrow['brief']['checker_context'])
            self.assertNotIn('informe.json',definitions);self.assertNotIn('comprobar_informe',definitions)
        exported=api.export_run(self.config,row['business_id'],row['engine_run_id'],self.config.storage/'check-export')
        audit=json.loads((self.config.storage/'check-export/native-checks.json').read_text())
        self.assertEqual(audit[0]['status'],'complete');self.assertIn('coverage',audit[0]['result'])
        self.assertNotIn('credential',json.dumps(audit));self.assertEqual(exported['native_cycle']['stage'],'complete')
        self.ws.run_job(job)
        self.assertEqual(len([m for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages'] if m['info']['role']=='user']),1)

    @staticmethod
    def discrepancy(data):
        p=data['priorities'][0];start=p['text'].index('5 unidades')
        return dict(version=contract.VERSION,revision_sha256=data['revision_sha256'],coverage_notes='',items=[
            dict(priority_id=p['block_id'],quote='5 unidades',start=start,end=start+len('5 unidades'),
                 status='discrepancy',independent_value='4 unidades',method='Sumar CSV; caso simulado.',message='Discrepancia simulada.')])

    def test_one_correction_same_writer_session_final_check_and_disagreement_visible(self):
        from decision_room.reports import reading
        self.runtime();IndependentClient.checker_results=[self.discrepancy,self.discrepancy]
        job=self.create(engine_kind='opencode',engine_format='blocks');self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'completed',row['issue'])
        with reading.read(self.config,row['business_id'],row['report_document_id']) as (db,doc,rev):
            cycle=db.execute('SELECT * FROM engine_native_cycles WHERE run_id=%s',(row['engine_run_id'],)).fetchone()
            self.assertTrue(cycle['correction_used']);self.assertEqual(cycle['stage'],'complete')
            results=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s ORDER BY started_at',(row['engine_run_id'],)).fetchall()
            self.assertEqual([r['version'] for r in results],[contract.VERSION+'-initial',contract.VERSION+'-final'])
            self.assertNotEqual(results[0]['instance_id'],results[1]['instance_id'])
            self.assertNotEqual(results[0]['session_id'],results[1]['session_id'])
            self.assertEqual(results[1]['revision_id'],rev['id'])
            self.assertTrue(any(i['status']=='discrepancy' for i in reading.view(db,doc,rev)['checks']['items']))
            outbox=db.execute('SELECT * FROM engine_prompt_outbox WHERE run_id=%s ORDER BY created_at',(row['engine_run_id'],)).fetchall()
            self.assertEqual(len(outbox),2);self.assertEqual(outbox[0]['session_id'],outbox[1]['session_id'])
            self.assertIn('Recalcula',outbox[1]['prompt']);self.assertIn('4 unidades',outbox[1]['prompt'])
        self.ws.run_job(job)
        self.assertEqual(sum(m['info']['role']=='user' for m in IndependentRuntime.sessions[str(row['engine_run_id'])]['messages']),2)

    def test_invalid_checker_publishes_valid_draft_with_visible_incomplete_notice(self):
        from decision_room.reports import reading
        self.runtime();IndependentClient.checker_results=[lambda _:dict(invalid=True)]
        job=self.create(engine_kind='opencode',engine_format='blocks');self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'completed',row['issue'])
        with reading.read(self.config,row['business_id'],row['report_document_id']) as (db,doc,rev):
            self.assertEqual(doc['current_revision_id'],rev['id'])
            self.assertEqual(reading.view(db,doc,rev)['checks']['state'],'incomplete')
            text=reading.chat_document(db,row['business_id'],doc['id'])['text']
            self.assertIn('Comprobación independiente de cifras: no completada',text)
            self.assertNotIn('Comprobación independiente: incomplete',text)
            check=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchone()
            self.assertEqual(check['status'],'incomplete');self.assertIsNotNone(check['raw_result'])

    def test_format_repair_consumes_only_correction_then_runs_final_checker(self):
        self.runtime();IndependentRuntime.payloads=[b'{"cut":',json.dumps(example()).encode()]
        IndependentClient.checker_results=[self.discrepancy]
        job=self.create(engine_kind='opencode',engine_format='blocks');self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'completed',row['issue'])
        with connect(self.config) as db:
            cycle=db.execute('SELECT * FROM engine_native_cycles WHERE run_id=%s',(row['engine_run_id'],)).fetchone()
            self.assertTrue(cycle['correction_used']);self.assertEqual(cycle['stage'],'complete')
            check=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchone()
            self.assertEqual(check['version'],contract.VERSION+'-final')
            self.assertTrue(any(i['status']=='discrepancy' for i in check['result']['items']))
            outbox=db.execute('SELECT * FROM engine_prompt_outbox WHERE run_id=%s ORDER BY created_at',(row['engine_run_id'],)).fetchall()
            self.assertEqual([p['request_key'] for p in outbox],['initial','native-format-repair'])
            self.assertTrue(any('JSON no válido' in p for p in json.loads(outbox[1]['prompt'][len(contract.FORMAT_REPAIR):])))
            receipts=db.execute('SELECT raw FROM engine_document_revisions WHERE business_id=%s AND document_id=%s ORDER BY ordinal',(row['business_id'],row['report_document_id'])).fetchall()
            self.assertEqual(len(receipts),2);self.assertEqual(bytes(receipts[0]['raw']),b'{"cut":')

    def test_second_invalid_format_keeps_both_receipts_without_publication(self):
        self.runtime();IndependentRuntime.payloads=[b'{"first":',b'{"second":']
        job=self.create(engine_kind='opencode',engine_format='blocks');self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'failed')
        with connect(self.config) as db:
            doc=db.execute('SELECT * FROM report_documents WHERE id=%s',(row['report_document_id'],)).fetchone()
            self.assertIsNone(doc['current_revision_id'])
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_document_revisions WHERE document_id=%s',(doc['id'],)).fetchone()['n'],2)
            self.assertFalse(db.execute('SELECT 1 FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchone())
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_prompt_outbox WHERE run_id=%s',(row['engine_run_id'],)).fetchone()['n'],2)

    def test_global_budget_stop_never_promotes_an_incomplete_checker(self):
        from decision_room.engine import provider_budget
        self.runtime()
        def invalid(data):
            with connect(self.config) as db:row=db.execute('SELECT * FROM engine_runs WHERE business_id=%s ORDER BY created_at DESC LIMIT 1',(self.business['id'],)).fetchone()
            provider_budget.ledger(self.config,row).stop()
            return dict(invalid=True)
        IndependentClient.checker_results=[invalid]
        job=self.create(engine_kind='opencode',engine_format='blocks');self.ws.run_job(job);row=self.ws.row(job)
        self.assertEqual(row['status'],'failed')
        with connect(self.config) as db:
            doc=db.execute('SELECT * FROM report_documents WHERE id=%s',(row['report_document_id'],)).fetchone()
            self.assertIsNone(doc['current_revision_id'])

    def test_checker_death_and_complete_receipt_recovery_do_not_replay(self):
        for boundary in ('submit','result'):
            with self.subTest(boundary=boundary):
                self.runtime();job=self.create(request_key=str(uuid4()),engine_kind='opencode',engine_format='blocks')
                if boundary=='submit':
                    original=IndependentClient.submit
                    def death(client,*args,**kwargs):
                        original(client,*args,**kwargs)
                        if client.runtime.checker:raise SystemExit('Simulated controller death')
                    p=patch.object(IndependentClient,'submit',death)
                else:
                    original=checks._finish_check
                    def death(*args,**kwargs):
                        original(*args,**kwargs)
                        if kwargs.get('result'):raise SystemExit('Simulated controller death')
                    p=patch.object(checks,'_finish_check',death)
                with p,self.assertRaises(SystemExit):self.ws.run_job(job)
                self.ws.run_job(job);row=self.ws.row(job)
                self.assertEqual(row['status'],'failed' if boundary=='submit' else 'completed',row['issue'])
                with connect(self.config) as db:
                    results=db.execute('SELECT * FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchall()
                    self.assertEqual(len(results),1)
                    doc=db.execute('SELECT * FROM report_documents WHERE id=%s',(row['report_document_id'],)).fetchone()
                    self.assertEqual(bool(doc['current_revision_id']),boundary=='result')
                self.assertEqual(sum(m['info']['role']=='user' for m in IndependentRuntime.sessions[str(row['engine_run_id'])]['messages']),1)

    def test_two_workers_create_only_one_independent_checker(self):
        import threading
        self.runtime();job=self.create(engine_kind='opencode',engine_format='blocks');errors=[]
        def work():
            try:self.ws.run_job(job)
            except Exception as e:errors.append(e)
        workers=[threading.Thread(target=work) for _ in range(2)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(10);self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        row=self.ws.row(job);self.assertEqual(row['status'],'completed',row['issue'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_native_checks WHERE run_id=%s',(row['engine_run_id'],)).fetchone()['n'],1)
