"""Product ceilings hold before sends even when input counting underestimates."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from decision_room.agent import api_budget
from decision_room.config import Config
from decision_room.engine import admission, profile, provider_budget, proxy, job_profile, export
from tests import test_engine_admission as fixtures


class BudgetTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp

    def create(self, *, cap=1_000_000, request_key=None):
        return admission.create_run(self.config, self.business, self.analysis,
            table_ids=[self.table], owner_context='Synthetic units', model='gpt-6-luna',
            engine_config=profile.configuration(usd_cap_micro=cap),
            request_key=request_key or uuid4().hex)

    def forward(self, run, token, handler):
        return proxy.forward(self.config, run, token,
            admission.canonical({'model':'gpt-6-luna','input':'Synthetic input','stream':False}),
            api_key='test-only',transport=httpx.MockTransport(handler),
            send_headers=lambda *a:None,write=lambda *a:None)

    def test_counter_underestimate_is_already_bounded_before_provider_usage(self):
        run,token=self.create(cap=400000)
        def provider(request):
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':1})
            state=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token)).snapshot()
            self.assertEqual(state['charged_nano_usd'],358500000)
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default','status':'completed',
                'usage':{'input_tokens':1050000,'output_tokens':128000}})
        with self.assertRaises(admission.Aborted):self.forward(run,token,provider)
        ledger=api_budget.Ledger(provider_budget.path(self.config,self.business,run))
        self.assertEqual(ledger.snapshot()['charged_nano_usd'],358500000)
        self.assertLessEqual(ledger.snapshot()['charged_nano_usd'],400000000)
        self.assertEqual(admission.inspect_run(self.config,self.business,run)['abort_reason'],
            'provider_usage_exceeded_reservation')

    def test_concurrent_sends_cannot_exceed_cap_even_with_low_counts(self):
        run,token=self.create(cap=600000)
        ledger=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token))
        gate=threading.Barrier(2); sent=[]
        def provider(request):
            sent.append(request)
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default',
                'usage':{'input_tokens':1050000,'output_tokens':128000}})
        def work():
            with httpx.Client(transport=api_budget.BudgetTransport(ledger,httpx.MockTransport(provider),'engine:'+str(run),reserve_model_output=True)) as client:
                gate.wait()
                try:client.post('https://api.openai.com/v1/responses',json={'model':'gpt-6-luna','input':'X','max_output_tokens':16000})
                except api_budget.BudgetStopped:return 'blocked'
                return 'sent'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(lambda _:work(),range(2)))
        self.assertEqual(sorted(outcomes),['blocked','sent'])
        self.assertEqual(len(sent),1)
        self.assertLessEqual(ledger.snapshot()['charged_nano_usd'],600000000)

    def test_crash_pending_receipt_and_replay_never_create_a_new_allowance(self):
        run,token=self.create(cap=400000,request_key='once')
        ledger=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token))
        ledger.reserve('engine:'+str(run),'sha','/v1/responses',api_budget.MAX_OUTPUT)
        self.assertEqual(self.create(cap=400000,request_key='once'),(run,None))
        reopened=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token))
        self.assertTrue(reopened.snapshot()['uncertain'])
        with self.assertRaises(api_budget.BudgetStopped):reopened.reserve('engine:'+str(run),'sha','/v1/responses',api_budget.MAX_OUTPUT)
        self.assertEqual(reopened.snapshot()['charged_nano_usd'],358500000)
        metadata=admission.inspect_run(self.config,self.business,run)['provider_budget']
        self.assertTrue(metadata['uncertain'])
        self.assertEqual(metadata['charged_nano_usd'],358500000)
        self.assertEqual(export.snapshot(self.config,self.business,run)['usage']['provider_budget'],metadata)

    def test_missing_or_replaced_budget_refuses_even_input_counting(self):
        for state in ('missing','replaced','corrupt'):
            with self.subTest(state=state):
                run,token=self.create()
                path=provider_budget.path(self.config,self.business,run)
                path.unlink()
                if state=='replaced':api_budget.Ledger.create(path,cap_micro_usd=2000000,scope_cap_micro_usd=2000000)
                if state=='corrupt':path.write_bytes(b'Invalid budget')
                with self.assertRaises(api_budget.BudgetStopped):
                    self.forward(run,token,lambda r:self.fail('Sent without its frozen budget'))
                self.assertEqual(path.exists(),state!='missing')
                metadata=admission.inspect_run(self.config,self.business,run)['provider_budget']
                self.assertEqual(metadata['status'],'unavailable')
                self.assertIsNone(metadata['charged_nano_usd'])

    def test_sigkill_during_a_provider_send_keeps_the_full_reservation(self):
        run,token=self.create(cap=400000,request_key='killed')
        path=provider_budget.path(self.config,self.business,run)
        marker=self.root/'provider-started'
        code='''
import sys,time
from pathlib import Path
import httpx
from decision_room.agent import api_budget
def provider(request):
    Path(sys.argv[2]).write_text('reserved before provider')
    time.sleep(60)
    raise AssertionError('Parent should kill the fake provider')
ledger=api_budget.Ledger(sys.argv[1])
with httpx.Client(transport=api_budget.BudgetTransport(ledger,httpx.MockTransport(provider),sys.argv[3],reserve_model_output=True)) as client:
    client.post('https://api.openai.com/v1/responses',json={'model':'gpt-6-luna','input':'X','max_output_tokens':16000})
'''
        process=subprocess.Popen([sys.executable,'-c',code,str(path),str(marker),'engine:'+str(run)],
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+10
            while not marker.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(.02)
            self.assertTrue(marker.exists(),'The fake provider never received the reserved request')
            process.kill();self.assertEqual(process.wait(timeout=5),-9)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=5)
        self.assertEqual(self.create(cap=400000,request_key='killed'),(run,None))
        state=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token)).snapshot()
        self.assertTrue(state['uncertain'])
        self.assertEqual(state['charged_nano_usd'],358500000)
        self.assertEqual(len(state['calls']),1)

    def test_per_run_envelope_and_trial_envelope_both_charge_the_same_send(self):
        run,token=self.create()
        path=self.root/'trial.sqlite'
        shared=api_budget.Ledger.create(path,cap_micro_usd=1000000,scope_cap_micro_usd=1000000)
        def provider(request):
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':20})
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default','status':'completed',
                'usage':{'input_tokens':20,'output_tokens':10}})
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':str(path)}):
            self.forward(run,token,provider)
        own=provider_budget.ledger(self.config,admission.authenticate(self.config,run,token)).snapshot()
        self.assertEqual(own['charged_nano_usd'],7500)
        self.assertEqual(shared.snapshot()['charged_nano_usd'],7500)
        self.assertEqual(len(own['calls']),1)

    def test_waiting_time_and_another_run_do_not_reset_or_share_the_budget(self):
        first,token=self.create(cap=400000)
        second,other=self.create(cap=400000)
        own=provider_budget.ledger(self.config,admission.authenticate(self.config,first,token))
        call=own.reserve('engine:'+str(first),'sha','/v1/responses',api_budget.MAX_OUTPUT)
        own.settle(call,{'model':'gpt-6-luna','service_tier':'default',
                        'usage':{'input_tokens':20,'output_tokens':10}})
        with own.db() as db:db.execute("UPDATE calls SET created_at=datetime('now','-8 days')")
        # The dollar balance survives waiting; the engine's own active-time quota
        # remains authoritative, rather than counting the owner's waiting days.
        resumed=provider_budget.ledger(self.config,admission.authenticate(self.config,first,token))
        resumed.reserve('engine:'+str(first),'sha','/v1/responses',api_budget.MAX_OUTPUT)
        other_budget=provider_budget.ledger(self.config,admission.authenticate(self.config,second,other))
        self.assertEqual(other_budget.snapshot()['charged_nano_usd'],0)
        self.assertEqual(resumed.snapshot()['charged_nano_usd'],358507500)

    def test_creation_cap_is_fixed_and_impossible_configuration_is_refused(self):
        with patch.dict('os.environ',{'DECISION_ROOM_ENGINE_IMAGE_ID':'sha256:'+'a'*64}):
            kind,settings=job_profile.selection(self.config,{'engine_kind':'opencode'})
            self.assertEqual(settings['profile']['version'],'html-v1-budget-1')
            self.assertEqual(settings['profile']['usd_ceiling']['cap_micro_usd'],1000000)
            old={'engine_kind':kind,'engine_config':settings}
            _,replay=job_profile.selection(replace(self.config,engine_usd_cap_micro=2000000),{},old)
            self.assertEqual(replay,settings)
            with self.assertRaises(ValueError):
                job_profile.selection(replace(self.config,engine_usd_cap_micro=1),{'engine_kind':'opencode'})
        for value in ('NaN','Infinity','0','-1','0.1234567','1.000000000000000000000000000001','1e999999999'):
            with patch.dict('os.environ',{'DECISION_ROOM_ENGINE_USD_CAP':value}),self.assertRaises(ValueError):Config.load()


if __name__=='__main__':unittest.main()
