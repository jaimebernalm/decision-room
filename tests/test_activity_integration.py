"""Capture protocol with real database, sandbox and scripted product agents."""
import threading
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
import httpx
import test_research as base
import test_parallel_research as parallel_base
import test_business_planner as planner_base
from test_business_planner import PlannerModel
from test_review import DialogueModel
from decision_room.database import connect
from decision_room.agent import research,review
from decision_room.agent.persistence import _model_call
from decision_room.agent.model import ModelClient,ModelSettings,record_transport
from decision_room.observability import store,collector,projection,runtime


class CaptureTests(unittest.TestCase):
    setUpClass=classmethod(base.ResearchTests.setUpClass.__func__)
    tearDownClass=classmethod(base.ResearchTests.tearDownClass.__func__)
    def setUp(self): parallel_base.ParallelTests.setUp(self)
    def tearDown(self):
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM activity_traces WHERE business_id=%s AND NOT history_complete',(self.business,)).fetchone())
    def test_parallel_question_recovery_and_review_preserve_events(self):
        model=PlannerModel()
        run=research.start(self.config,self.business,self.plan['id'],request_key='observed',model=model,business_planner=True,quality_first=True)
        self.assertEqual(run['status'],'waiting')
        with connect(self.config) as db:
            trace=store.linked(db,self.business,'session',self.plan['id'])
            initial=db.execute('SELECT count(*) n FROM activity_events WHERE trace_id=%s',(trace,)).fetchone()['n']
            calls=db.execute('SELECT count(*) n FROM agent_calls WHERE session_id=%s',(self.plan['id'],)).fetchone()['n']
            q=projection.page(db,self.business,trace,{})
            self.assertTrue(any(t['status']=='waiting_owner' for t in q['active_tasks']))
            branches=db.execute("SELECT * FROM activity_tasks WHERE trace_id=%s AND kind='branch'",(trace,)).fetchall()
            self.assertEqual(len(branches),2)
            self.assertTrue(all(t['status']=='completed' for t in branches))
            for _ in range(3): projection.page(db,self.business,trace,{})
            self.assertEqual(db.execute('SELECT count(*) n FROM agent_calls WHERE session_id=%s',(self.plan['id'],)).fetchone()['n'],calls)
            self.assertEqual(db.execute('SELECT count(*) n FROM activity_events WHERE trace_id=%s',(trace,)).fetchone()['n'],initial)
        pending=run['pending_questions'][0]
        done=research.answer(self.config,self.business,run['id'],question_id=pending['id'],text='Hubo obras.',request_key='answer',model=model)
        roles=DialogueModel();roles.identity=model.identity
        delivery=review.start(self.config,self.business,done['id'],request_key='review',analyst=roles,reviewer=roles)
        self.assertTrue(delivery['publishable'])
        with connect(self.config) as db:
            tasks=db.execute('SELECT * FROM activity_tasks WHERE trace_id=%s',(trace,)).fetchall()
            self.assertTrue(any(t['kind']=='review_step' and t['source'].get('action')=='approve' for t in tasks))
            self.assertFalse(any(t['kind']=='planner_consult' and t['status']=='waiting_owner' for t in tasks))
            self.assertEqual(len([t for t in tasks if t['kind']=='execution']),len({s['execution_id'] for s in done['steps'] if s['execution_id']}))
            count=db.execute('SELECT count(*) n FROM activity_events WHERE trace_id=%s',(trace,)).fetchone()['n']
            collector.reconcile(db,self.business,trace,reconstructed=True)
            self.assertEqual(count,db.execute('SELECT count(*) n FROM activity_events WHERE trace_id=%s',(trace,)).fetchone()['n'])
    def test_network_start_is_visible_before_slow_call_finishes(self):
        entered=threading.Event();release=threading.Event();errors=[]
        class Slow(type(self.model)):
            def generate_research(self,*args,**kwargs):
                entered.set();release.wait(10)
                return super().generate_research(*args,**kwargs)
        def work():
            try: research.start(self.config,self.business,self.plan['id'],request_key='slow',model=Slow(),delegation=True)
            except BaseException as e: errors.append(e)
        thread=threading.Thread(target=work);thread.start()
        try:
            self.assertTrue(entered.wait(10))
            with connect(self.config) as db:
                trace=store.linked(db,self.business,'session',self.plan['id'])
                calls=db.execute("SELECT * FROM activity_tasks WHERE trace_id=%s AND kind='call' AND status='running'",(trace,)).fetchall()
                self.assertEqual(len(calls),1)
                self.assertTrue(db.execute('SELECT worker_active FROM activity_traces WHERE id=%s',(trace,)).fetchone()['worker_active'])
        finally: release.set();thread.join(15)
        self.assertEqual(errors,[])
    def test_reconstruction_does_not_rerun_and_filtered_pagination_is_complete(self):
        with connect(self.config) as db:
            trace=store.linked(db,self.business,'session',self.plan['id'])
            for i in range(1000):
                store.append(db,self.business,trace,kind='call' if i%2 else 'inspection',source_id=str(i),status='completed',public_text='Actividad registrada',dedupe_key=f'load-{i}')
            after=f'{trace}:0';seen=set();scanned=0
            while True:
                page=projection.page(db,self.business,trace,{'after':[after],'limit':['100']})
                for e in page['events']:
                    self.assertNotIn(e['id'],seen);seen.add(e['id'])
                scanned=int(page['next_cursor'].split(':')[1]);after=page['next_cursor']
                if not page['has_more']: break
            self.assertEqual(scanned,db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s',(trace,)).fetchone()['last_sequence'])
            self.assertGreaterEqual(len(seen),500)
            self.assertLess(len(json.dumps(page,default=str).encode()),100000)
            with self.assertRaisesRegex(Exception,'cursor'): projection.page(db,self.business,trace,{'after':[f'{uuid4()}:1']})
    def test_replay_is_a_reuse_not_a_new_call(self):
        with connect(self.config) as db:
            call=db.execute("SELECT * FROM agent_calls WHERE session_id=%s AND status='completed' AND phase='planning' ORDER BY created_at LIMIT 1",(self.plan['id'],)).fetchone()
            before=db.execute('SELECT count(*) n FROM agent_calls WHERE session_id=%s',(self.plan['id'],)).fetchone()['n']
            with runtime.capture(self.config,self.business,'session',self.plan['id'],db=db),patch.object(self.model,'generate',side_effect=AssertionError('Replay called model')):
                for _ in range(2):
                    self.assertEqual(_model_call(db,self.plan['id'],self.model,call['context_payload'],None,False),call['output'])
            trace=store.linked(db,self.business,'session',self.plan['id'])
            self.assertEqual(db.execute('SELECT count(*) n FROM agent_calls WHERE session_id=%s',(self.plan['id'],)).fetchone()['n'],before)
            self.assertEqual(db.execute("SELECT count(*) n FROM activity_events WHERE trace_id=%s AND type='result.reused'",(trace,)).fetchone()['n'],1)
    def test_transport_waits_are_real_and_finish_after_recovery(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response([429,503,200][len(seen)-1],headers={'Retry-After':'1'},json={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}],'usage':{}})
        client=httpx.Client(transport=httpx.MockTransport(handler));observed=[]
        def waiting(seconds):
            with connect(self.config) as observer:
                trace=store.linked(observer,self.business,'session',self.plan['id'])
                observed.append(observer.execute("SELECT count(*) n FROM activity_tasks WHERE trace_id=%s AND status='retry_wait'",(trace,)).fetchone()['n'])
        with runtime.capture(self.config,self.business,'session',self.plan['id']),runtime.call_context(uuid4()),record_transport(runtime.transport),patch('decision_room.agent.model.httpx.Client',return_value=client),patch('decision_room.agent.model.time.sleep',side_effect=waiting):
            ModelClient(ModelSettings('test',protocol='chat_completions')).generate({})
        self.assertEqual(observed,[1,1]);self.assertEqual(len(seen),3)
        with connect(self.config) as db:
            trace=store.linked(db,self.business,'session',self.plan['id'])
            self.assertFalse(db.execute("SELECT 1 FROM activity_tasks WHERE trace_id=%s AND status='retry_wait'",(trace,)).fetchone())
    def test_reconciliation_after_missed_emission_does_not_repeat_effects(self):
        with patch.object(collector,'reconcile',return_value=None):
            done=research.start(self.config,self.business,self.plan['id'],request_key='missed',model=self.model,delegation=True)
        with connect(self.config) as db:
            trace=store.linked(db,self.business,'session',self.plan['id'])
            counts=lambda:tuple(db.execute(f'SELECT count(*) n FROM {table}').fetchone()['n'] for table in ('agent_calls','executions'))
            before=counts()
            collector.reconcile(db,self.business,trace,reconstructed=True)
            self.assertEqual(before,counts())
            self.assertTrue(db.execute('SELECT 1 FROM activity_events WHERE trace_id=%s AND reconstructed',(trace,)).fetchone())
            self.assertEqual(len(db.execute("SELECT id FROM activity_tasks WHERE trace_id=%s AND kind='execution'",(trace,)).fetchall()),len({s['execution_id'] for s in done['steps'] if s['execution_id']}))


class ContinuityTests(unittest.TestCase):
    setUpClass=classmethod(planner_base.PlannerWebTests.setUpClass.__func__)
    tearDownClass=classmethod(planner_base.PlannerWebTests.tearDownClass.__func__)
    setUp=planner_base.PlannerWebTests.setUp
    create=planner_base.PlannerWebTests.create
    answer=planner_base.PlannerWebTests.answer
    def test_definition_successor_keeps_process_and_superseded_evidence(self):
        planner_base.PlannerWebTests.test_definition_answer_replans_the_same_web_job(self)
        with connect(self.config) as db:
            traces=db.execute('SELECT DISTINCT trace_id FROM activity_links WHERE business_id=%s',(self.business['id'],)).fetchall()
            self.assertEqual(len(traces),1)
            trace=traces[0]['trace_id']
            sessions=db.execute("SELECT count(*) n FROM activity_links WHERE trace_id=%s AND kind='session'",(trace,)).fetchone()['n']
            self.assertEqual(sessions,2)
            old=db.execute("SELECT id FROM activity_tasks WHERE trace_id=%s AND kind='research' AND status='superseded'",(trace,)).fetchall()
            self.assertEqual(len(old),1)
            self.assertFalse(db.execute('SELECT 1 FROM activity_traces WHERE id=%s AND NOT history_complete',(trace,)).fetchone())
    def test_stalled_worker_is_unconfirmed_without_fabricating_failure(self):
        job=self.create()
        with connect(self.config) as db:
            trace=store.linked(db,self.business['id'],'job',job)
            db.execute("UPDATE activity_traces SET worker_active=true,heartbeat_at=now()-interval '2 minutes' WHERE id=%s",(trace,))
            page=projection.page(db,self.business['id'],trace,{})
            self.assertEqual(page['worker_health'],'unconfirmed')
            self.assertEqual(page['status'],'queued')
            self.assertFalse(page['terminal'])
