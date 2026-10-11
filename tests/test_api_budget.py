"""Durable ceilings at the shared outbound boundary; no provider calls."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from decision_room.agent import api_budget as budget


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'budget.sqlite'
        self.ledger = budget.Ledger.create(self.path, cap_micro_usd=1_000_000, scope_cap_micro_usd=500_000)
        self.payload = {'model':'gpt-6-luna','max_completion_tokens':1000,'messages':[]}

    def response(self, request, **changes):
        result = {'model':'gpt-6-luna','service_tier':'default',
                  'usage':{'prompt_tokens':10000,'completion_tokens':1000}}
        result.update(changes)
        return httpx.Response(200,json=result)

    def client(self, handler=None, identifier='job:1'):
        return httpx.Client(transport=budget.BudgetTransport(self.ledger,
            httpx.MockTransport(handler or self.response),identifier))

    def test_known_usage_releases_only_unused_envelope_and_survives_restart(self):
        def handler(request):
            self.assertEqual(json.loads(request.read())['service_tier'],'default')
            # Reservation is durable before forwarding.
            state=budget.Ledger(self.path).snapshot()
            self.assertEqual(state['calls'][0]['state'],'reserved')
            return self.response(request)
        with self.client(handler) as client:
            client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
        state=budget.Ledger(self.path).snapshot()
        self.assertEqual(state['charged_nano_usd'],1_750_000)
        self.assertFalse(state['uncertain'])
        self.assertNotIn('messages',json.dumps(state))
        with self.assertRaises(FileExistsError):
            budget.Ledger.create(self.path,cap_micro_usd=2_000_000,scope_cap_micro_usd=500_000)

    def test_two_workers_reserve_atomically_and_kill_switch_never_sends(self):
        gate=threading.Barrier(2)
        sent=[]; errors=[]
        def work():
            try:
                gate.wait()
                call=self.ledger.reserve('same','digest','/v1/responses',1000)
                sent.append(call)
            except budget.BudgetStopped:
                errors.append(True)
        workers=[threading.Thread(target=work) for _ in range(2)]
        for w in workers:w.start()
        for w in workers:w.join(5);self.assertFalse(w.is_alive())
        self.assertEqual((len(sent),len(errors)),(1,1))
        self.ledger.stop()
        with self.client(lambda r:self.fail('Sent after stop')) as client,self.assertRaises(budget.BudgetStopped):
            client.post('https://api.openai.com/v1/chat/completions',json=self.payload)

    def test_unknown_http_error_and_disconnect_hold_full_reservation_and_halt(self):
        for mode in ('usage','http','disconnect'):
            with self.subTest(mode=mode):
                path=Path(self.temp.name)/(mode+'.sqlite')
                ledger=budget.Ledger.create(path,cap_micro_usd=1_000_000,scope_cap_micro_usd=500_000)
                def handler(request):
                    if mode=='disconnect':raise httpx.ReadError('lost')
                    if mode=='http':return httpx.Response(503)
                    return self.response(request,usage={})
                with httpx.Client(transport=budget.BudgetTransport(ledger,httpx.MockTransport(handler),'j')) as client:
                    try:client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
                    except httpx.ReadError:pass
                    with self.assertRaises(budget.BudgetStopped):
                        client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
                state=ledger.snapshot()
                self.assertTrue(state['uncertain'])
                self.assertEqual(state['charged_nano_usd'],263_250_000)

    def test_sse_settles_and_early_close_stays_uncertain(self):
        payload={'model':'gpt-6-luna','max_output_tokens':1000,'stream':True}
        result={'type':'response.completed','response':{'model':'gpt-6-luna', 'service_tier':'default',
            'usage':{'input_tokens':300000,'output_tokens':1000}}}
        def handler(request):
            return httpx.Response(200,headers={'content-type':'text/event-stream'},
                                  content=b'data: '+json.dumps(result).encode()+b'\n\n')
        with self.client(handler) as client:
            client.post('https://api.openai.com/v1/responses',json=payload)
        self.assertEqual(self.ledger.snapshot()['charged_nano_usd'],75_750_000)
        with self.client(handler,identifier='job:2') as client:
            with client.stream('POST','https://api.openai.com/v1/responses',json=payload):pass
        self.assertTrue(self.ledger.snapshot()['uncertain'])

    def test_foreign_model_tier_origin_and_missing_ceiling_do_not_send(self):
        cases=[('https://evil.invalid/v1/chat/completions',self.payload),
            ('https://api.openai.com/v1/chat/completions',{**self.payload,'model':'other'}),
            ('https://api.openai.com/v1/chat/completions',{**self.payload,'service_tier':'priority'}),
            ('https://api.openai.com/v1/chat/completions',{'model':'gpt-6-luna'})]
        with self.client(lambda r:self.fail('Forbidden request sent')) as client:
            for url,payload in cases:
                with self.subTest(url=url,payload=payload),self.assertRaises(budget.BudgetStopped):
                    client.post(url,json=payload)
        self.assertEqual(self.ledger.snapshot()['calls'],[])

    def test_optional_transport_preserves_injected_transport_without_budget(self):
        inner=httpx.MockTransport(self.response)
        with patch.dict('os.environ',{},clear=True):self.assertIs(budget.transport(inner),inner)
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':str(self.path)}),budget.scope('job:x'):
            wrapped=budget.transport(inner)
            self.assertEqual(wrapped.identifier,'job:x')

    def test_global_ceiling_across_different_scopes_and_counterfeit_usage(self):
        path=Path(self.temp.name)/'shared.sqlite'
        ledger=budget.Ledger.create(path,cap_micro_usd=300000,scope_cap_micro_usd=300000)
        call=ledger.reserve('first','digest','/v1/responses',1000)
        with self.assertRaises(budget.BudgetStopped):ledger.reserve('second','digest','/v1/responses',1000)
        # Invalid types/overruns never release a reservation or reset a ceiling.
        ledger.settle(call,{'model':'gpt-6-luna','service_tier':'default',
            'usage':{'input_tokens':True,'output_tokens':0}})
        self.assertTrue(ledger.snapshot()['policy']['stopped'])
        self.assertEqual(ledger.snapshot()['charged_nano_usd'],263250000)

    def test_scope_token_call_and_elapsed_limits_are_durable(self):
        for kind,limits in [('input',{'input_tokens':1050000}),('output',{'output_tokens':1000}),
                            ('calls',{'calls':1}),('seconds',{'seconds':1})]:
            with self.subTest(kind=kind):
                ledger=budget.Ledger.create(Path(self.temp.name)/(kind+'.sqlite'),
                    cap_micro_usd=1000000,scope_cap_micro_usd=1000000,**limits)
                call=ledger.reserve('same','digest','/v1/responses',1000)
                ledger.settle(call,{'model':'gpt-6-luna','service_tier':'default',
                    'usage':{'input_tokens':1000,'output_tokens':1000}})
                if kind=='seconds':
                    with ledger.db() as db:db.execute("UPDATE calls SET created_at=datetime('now','-2 seconds')")
                with self.assertRaises(budget.BudgetStopped):ledger.reserve('same','digest','/v1/responses',1000)

    def test_catalog_receipt_is_separate_from_conservative_envelope(self):
        call=self.ledger.reserve('same','digest','/v1/responses',1000)
        self.ledger.settle(call,{'model':'gpt-6-luna','service_tier':'default',
            'usage':{'input_tokens':1000,'output_tokens':100,'input_tokens_details':{'cached_tokens':200,'cache_write_tokens':0}}})
        snapshot=self.ledger.snapshot()
        self.assertEqual(snapshot['charged_nano_usd'],175000)
        self.assertEqual(snapshot['cost_catalog']['cost'],'0.000132')

    def test_explicit_rejection_is_opt_in_keeps_charge_and_allows_a_separate_attempt(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                ledger=budget.Ledger.create(Path(self.temp.name)/(str(enabled)+'.sqlite'),
                    cap_micro_usd=1000000,scope_cap_micro_usd=1000000,
                    explicit_http_rejections=enabled)
                error={'error':{'message':'Synthetic rate limit','code':'rate_limit'}}
                with httpx.Client(transport=budget.BudgetTransport(ledger,
                    httpx.MockTransport(lambda r:httpx.Response(429,json=error)),'j')) as client:
                    response=client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
                    self.assertEqual(response.json(),error)
                state=ledger.snapshot()
                call=state['calls'][0]
                self.assertEqual(call['http_status'],429)
                self.assertEqual(call['state'],'rejected' if enabled else 'uncertain')
                self.assertEqual(call['charged'],call['reserved'])
                self.assertEqual(call['charged'],263250000)
                self.assertEqual(bool(state['policy']['stopped']),not enabled)
                self.assertEqual(state['uncertain'],not enabled)
                self.assertIsNone(call['cost_catalog']['cost'])
                if enabled:
                    with httpx.Client(transport=budget.BudgetTransport(ledger,
                        httpx.MockTransport(self.response),'j')) as client:
                        client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
                    self.assertEqual(len(ledger.snapshot()['calls']),2)
                    # A later callback cannot invent usage or release the rejection.
                    ledger.settle(call['id'],{'model':'gpt-6-luna','service_tier':'default',
                        'usage':{'input_tokens':0,'output_tokens':0}})
                    self.assertEqual(ledger.snapshot()['charged_nano_usd'],265000000)

    def test_rejected_attempt_counts_against_quotas_and_restart_does_not_reset_it(self):
        path=Path(self.temp.name)/'rejection-cap.sqlite'
        ledger=budget.Ledger.create(path,cap_micro_usd=1000000,scope_cap_micro_usd=1000000,
            explicit_http_rejections=True,calls=1)
        with httpx.Client(transport=budget.BudgetTransport(ledger,
            httpx.MockTransport(lambda r:httpx.Response(503,json={'error':{'message':'Unavailable'}})),'j')) as client:
            client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
        reopened=budget.Ledger(path)
        with self.assertRaises(budget.BudgetStopped):reopened.reserve('j','sha','/v1/responses',1000)
        self.assertEqual(reopened.snapshot()['policy']['version'],budget.REJECTION_VERSION)
        self.assertEqual(reopened.snapshot()['charged_nano_usd'],263250000)

    def test_error_requires_complete_strict_json_and_unknown_success_still_stops(self):
        cases=[(503,b'not json'),(503,b'{"error":{}}'),
            (503,b'{"error":{"message":"bad"},"usage":null}'),
            (503,b'{"error":{"message":"bad","usage":0}}'),
            (503,b'{"error":{"message":"bad"},"output":[]}'),
            (503,b'{"error":{"message":"bad"},"error":{"message":"other"}}'),
            (503,b'{"error":{"message":"bad","number":NaN}}'),
            (302,b'{"error":{"message":"redirect"}}'),
            (200,b'{"error":{"message":"bad"}}'),
            (503,b'{"error":{"message":"'+b'a'*65536+b'"}}')]
        for index,(status,body) in enumerate(cases):
            with self.subTest(index=index):
                ledger=budget.Ledger.create(Path(self.temp.name)/f'bad-{index}.sqlite',
                    cap_micro_usd=1000000,scope_cap_micro_usd=1000000,explicit_http_rejections=True)
                with httpx.Client(transport=budget.BudgetTransport(ledger,
                    httpx.MockTransport(lambda r:httpx.Response(status,content=body)),'j')) as client:
                    try:client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
                    except ValueError:pass
                state=ledger.snapshot()
                self.assertEqual(state['calls'][0]['http_status'],status)
                self.assertEqual(state['calls'][0]['state'],'uncertain')
                self.assertTrue(state['policy']['stopped'])

    def test_interrupted_http_error_is_uncertain_even_with_complete_json_prefix(self):
        class Interrupted(httpx.SyncByteStream):
            def __iter__(self):
                yield b'{"error":{"message":"Unavailable"}}'
                raise httpx.ReadError('Synthetic interruption')
        ledger=budget.Ledger.create(Path(self.temp.name)/'interrupted.sqlite',
            cap_micro_usd=1000000,scope_cap_micro_usd=1000000,explicit_http_rejections=True)
        with httpx.Client(transport=budget.BudgetTransport(ledger,
            httpx.MockTransport(lambda r:httpx.Response(503,stream=Interrupted())),'j')) as client:
            with self.assertRaises(httpx.ReadError):
                client.post('https://api.openai.com/v1/chat/completions',json=self.payload)
        state=ledger.snapshot()
        self.assertEqual(state['calls'][0]['http_status'],503)
        self.assertTrue(state['policy']['stopped'])
        self.assertEqual(state['calls'][0]['state'],'uncertain')


class ProductBudgetTests(unittest.TestCase):
    from tests import test_engine_admission as fixtures
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp

    def test_product_retry_reserves_each_http_attempt_without_changing_old_policy(self):
        from decision_room.agent.model import ModelClient,ModelSettings
        path=self.config.storage/'http-rejection-budget.sqlite'
        ledger=budget.Ledger.create(path,cap_micro_usd=1000000,scope_cap_micro_usd=1000000,
            explicit_http_rejections=True)
        sent=[]
        def provider(request):
            sent.append(request)
            if len(sent)==1:return httpx.Response(429,json={'error':{'message':'Synthetic rate limit'}})
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default',
                'usage':{'prompt_tokens':20,'completion_tokens':10},
                'choices':[{'finish_reason':'stop','message':{'content':'{"action":"inspect"}'}}]})
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':str(path),'OPENAI_API_KEY':'test-only'}):
            actual=budget.transport
            with budget.scope('web:fixture'),patch.object(budget,'transport',side_effect=lambda *a,**kw:actual(httpx.MockTransport(provider),**kw)),patch('decision_room.agent.model.time.sleep'):
                action,usage=ModelClient(ModelSettings('gpt-6-luna',protocol='openai',base_url='https://api.openai.com/v1',reasoning='low')).generate({})
        self.assertEqual(action['action'],'inspect')
        self.assertEqual([a['status'] for a in usage['transport_attempts']],[429,200])
        state=ledger.snapshot()
        self.assertEqual({c['http_status']:c['state'] for c in state['calls']},{429:'rejected',200:'settled'})
        rejected=next(c for c in state['calls'] if c['http_status']==429)
        self.assertEqual(state['charged_nano_usd'],rejected['reserved']+7500)
        self.assertFalse(state['policy']['stopped'])

    def test_both_real_model_boundaries_share_one_durable_ledger(self):
        from decision_room.agent.model import ModelClient,ModelSettings
        from decision_room.engine import admission,proxy
        path=self.config.storage/'api-budget.sqlite'
        ledger=budget.Ledger.create(path,cap_micro_usd=1000000,scope_cap_micro_usd=500000)
        def provider(request):
            if request.url.path.endswith('/input_tokens'):return httpx.Response(200,json={'input_tokens':20})
            self.assertEqual(json.loads(request.read())['service_tier'],'default')
            if request.url.path.endswith('/chat/completions'):
                return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default',
                    'usage':{'prompt_tokens':20,'completion_tokens':10},
                    'choices':[{'finish_reason':'stop','message':{'content':'{"action":"inspect"}'}}]})
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default','status':'completed',
                'usage':{'input_tokens':20,'output_tokens':10}})
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':str(path),'OPENAI_API_KEY':'test-only'}):
            actual=budget.transport
            with budget.scope('web:fixture'),patch.object(budget,'transport',side_effect=lambda *a,**kw:actual(httpx.MockTransport(provider),**kw)):
                ModelClient(ModelSettings('gpt-6-luna',protocol='openai',base_url='https://api.openai.com/v1',reasoning='low')).generate({})
            run,token=admission.create_run(self.config,self.business,self.analysis,table_ids=[self.table],
                owner_context='Fixture',request_key='shared-budget',model='gpt-6-luna')
            proxy.forward(self.config,run,token,admission.canonical({'model':'gpt-6-luna','input':'Fixture','stream':False}),
                api_key='test-only',transport=httpx.MockTransport(provider),send_headers=lambda *a:None,write=lambda *a:None)
        calls=ledger.snapshot()['calls']
        self.assertEqual(len(calls),2)
        self.assertEqual({c['scope'] for c in calls},{'web:fixture','engine:'+str(run)})
        self.assertTrue(all(c['state']=='settled' for c in calls))
        self.assertEqual(ledger.snapshot()['charged_nano_usd'],15000)
