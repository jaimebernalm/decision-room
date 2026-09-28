"""Operator and client cookies are independent; all readers are effect-free."""
import json
import threading
from datetime import timedelta
import unittest
from uuid import uuid4
from unittest.mock import patch
import httpx
import test_web as base
from decision_room.database import connect
from decision_room.web.server import Server
from decision_room.observability import store
from decision_room.web import activity,internal_monitor
from decision_room.agent.review import hold


class MonitorTests(unittest.TestCase):
    setUpClass=classmethod(base.WebTests.setUpClass.__func__)
    tearDownClass=classmethod(base.WebTests.tearDownClass.__func__)
    setUp=base.WebTests.setUp
    create=base.WebTests.create
    def tearDown(self):
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM activity_traces WHERE business_id=%s AND NOT history_complete',(self.business['id'],)).fetchone())
    def http(self,enabled=True):
        server=Server(self.ws,0,token='customer-test-key',internal_monitor=enabled,internal_token='operator-test-key')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        client=httpx.Client(base_url=server.origin,headers={'Origin':server.origin,'X-Decision-Room':'1'})
        self.addCleanup(client.close)
        return client,server
    def test_customer_does_not_authorize_internal_and_operator_needs_no_customer(self):
        job=self.create();client,server=self.http()
        self.assertEqual(client.get('/api/internal/investigations').status_code,401)
        self.assertEqual(client.post('/api/login',json={'token':'customer-test-key'}).status_code,200)
        self.assertEqual(client.get('/api/internal/investigations').status_code,401)
        self.assertEqual(client.get(f'/api/jobs/{job}/activity').status_code,200)
        client.cookies.clear()
        login=client.post('/api/internal/login',json={'token':'operator-test-key'})
        self.assertEqual(login.status_code,200)
        self.assertIn('Path=/api/internal',login.headers['set-cookie']);self.assertIn('HttpOnly',login.headers['set-cookie'])
        self.assertEqual(client.get('/api/workspace').status_code,401)
        listing=client.get('/api/internal/investigations');self.assertEqual(listing.status_code,200)
        self.assertEqual(len(listing.json()['items']),1)
        trace=listing.json()['items'][0]['id']
        page=client.get(f'/api/internal/investigations/{trace}')
        self.assertEqual(page.status_code,200);self.assertIn('resources',page.json())
        self.assertEqual(client.post(f'/api/internal/investigations/{trace}',json={}).status_code,405)
        self.assertEqual(client.post('/api/internal/logout',json={}).status_code,200)
        self.assertEqual(client.get('/api/internal/session').status_code,401)
    def test_disabled_wrong_origin_and_cross_process_details(self):
        disabled,_=self.http(False)
        self.assertEqual(disabled.post('/api/internal/login',json={'token':'operator-test-key'}).status_code,404)
        client,_=self.http()
        self.assertEqual(client.post('/api/internal/login',json={'token':'operator-test-key'},headers={'Origin':'http://untrusted'}).status_code,403)
        self.assertEqual(client.post('/api/internal/login',json={'token':'customer-test-key'}).status_code,401)
        one=self.create();two=self.create(request_key=str(uuid4()))
        with connect(self.config) as db:
            a=store.linked(db,self.business['id'],'job',one);b=store.linked(db,self.business['id'],'job',two)
            task=store.append(db,self.business['id'],b,kind='inspection',source_id='only-b',status='completed',public_text='Archivo preparado',dedupe_key='only-b')
        client.post('/api/internal/login',json={'token':'operator-test-key'})
        self.assertEqual(client.get(f'/api/internal/investigations/{a}/tasks/{task}').status_code,404)
        self.assertEqual(client.get(f'/api/internal/investigations/{b}/tasks/{task}').status_code,200)
    def test_public_payload_and_get_have_no_internal_fields_or_effects(self):
        job=self.create();client,_=self.http();client.post('/api/login',json={'token':'customer-test-key'})
        with connect(self.config) as db:
            trace=store.linked(db,self.business['id'],'job',job)
            store.append(db,self.business['id'],trace,kind='inspection',source_id='check',status='completed',public_text='Archivo preparado',dedupe_key='private-payload',payload={'code':'canary-private-output','rationale':'canary-private-rationale','prompt':'canary-private-prompt'})
            before=db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s',(trace,)).fetchone()['last_sequence']
            state=db.execute('SELECT status,phase FROM web_jobs WHERE id=%s',(job,)).fetchone()
        for _ in range(3):
            response=client.get(f'/api/jobs/{job}/activity');self.assertEqual(response.status_code,200)
            self.assertNotIn('canary-private',response.text);self.assertNotIn('payload',response.text);self.assertNotIn('actors',response.json())
        with connect(self.config) as db:
            self.assertEqual(before,db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s',(trace,)).fetchone()['last_sequence'])
            self.assertEqual(state,db.execute('SELECT status,phase FROM web_jobs WHERE id=%s',(job,)).fetchone())
        other=self.ws.save_business({'request_key':str(uuid4()),'name':'Other','description':'Other','expected_active_id':str(self.business['id'])})
        self.assertEqual(client.get(f'/api/jobs/{job}/activity').status_code,404)
    def test_legacy_read_and_unknown_resources_do_not_invent_history(self):
        job=self.create()
        with connect(self.config) as db:
            trace=store.linked(db,self.business['id'],'job',job)
            r=internal_monitor.read(self.ws,str(trace),{})['resources']
            self.assertIsNone(r['input_tokens']);self.assertIsNone(r['output_tokens'])
            db.execute('DELETE FROM activity_traces WHERE id=%s',(trace,))
        page=activity.read(self.ws,'job',job,{})
        self.assertEqual(page['status'],'historical');self.assertEqual(page['events'],[])
        with connect(self.config) as db:
            self.assertIsNone(store.linked(db,self.business['id'],'job',job))
    def test_approval_hold_and_missing_evidence_never_advertise_ready(self):
        job=self.create()
        for _ in range(5):
            self.ws.run_job(job);j=self.ws.detail(job)
            if j['status']=='completed': break
            self.assertEqual(j['status'],'waiting')
            q=j['questions'][0]
            self.ws.reply(job,dict(request_key=str(uuid4()),question_id=str(q['id']),phase=q['phase'],text='Amount is a row total. Confirmado.'))
        self.assertEqual(j['status'],'completed')
        with connect(self.config) as db:
            trace=store.linked(db,self.business['id'],'job',job)
            review_id=db.execute('SELECT review_id FROM web_jobs WHERE id=%s',(job,)).fetchone()['review_id']
        self.assertTrue(activity.read(self.ws,'job',job,{})['publishable'])
        hold(self.config,self.business['id'],review_id,reason='Independent test hold')
        blocked=activity.read(self.ws,'job',job,{})
        self.assertEqual(blocked['status'],'blocked');self.assertFalse(blocked['publishable'])
        with connect(self.config) as db:
            db.execute('DELETE FROM agent_review_holds WHERE review_id=%s',(review_id,))
            ex=db.execute("SELECT code_key FROM executions WHERE business_id=%s LIMIT 1",(self.business['id'],)).fetchone()
        (self.config.storage/ex['code_key']).unlink()
        unavailable=activity.read(self.ws,'job',job,{})
        self.assertEqual(unavailable['status'],'blocked');self.assertFalse(unavailable['publishable'])

    def test_duration_uses_domain_finish_and_http_counts_recover_from_attempt_records(self):
        job=self.create();self.ws.run_job(job)
        with connect(self.config) as db:
            trace=store.linked(db,self.business['id'],'job',job)
            root=db.execute('SELECT * FROM activity_traces WHERE id=%s',(trace,)).fetchone()
            call=db.execute("SELECT c.id FROM agent_calls c JOIN activity_links l ON l.source_id=c.id AND l.kind='call' WHERE l.trace_id=%s LIMIT 1",(trace,)).fetchone()
            self.assertIsNotNone(call)
            # A legacy successful call without attempt metadata still has the
            # captured provider responses. The same attempt may have two events.
            for status in ('retry_wait','completed'):
                store.append(db,self.business['id'],trace,kind='transport',source_id=f"{call['id']}:0",status=status,public_text='Petición registrada',
                    source={'call_id':str(call['id']),'attempt':0},dedupe_key=f'resource-{status}')
            db.execute("UPDATE web_jobs SET status='failed',updated_at=%s WHERE id=%s",(root['created_at']+timedelta(seconds=10),job))
            store.append(db,self.business['id'],trace,kind='inspection',source_id='late-recovery',status='completed',public_text='Registro recuperado',
                occurred_at=root['created_at']+timedelta(seconds=40),reconstructed=True,dedupe_key='late-recovery')
            result=internal_monitor.resources(db,root)
            self.assertEqual(result['wall_seconds'],10)
            self.assertEqual(result['http_attempts'],1)
            self.assertEqual(result['unknown_http_calls'],result['logical_calls']-1)
            self.assertLessEqual(result['provider_wait_seconds'],10)
