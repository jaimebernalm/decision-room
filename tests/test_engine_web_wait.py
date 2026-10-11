"""Run-scoped owner replies with PostgreSQL and a fake runtime; no model traffic."""
import threading
import unittest
from uuid import uuid4
from unittest.mock import patch

from decision_room.database import connect
from decision_room.engine import api, questions
from decision_room.web.service import WebError
from tests import test_web as fixtures
from tests import test_engine_jobs as job_fixtures
from tests.engine_fakes import FakeRuntime


class EngineWaitTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.WebTests.tearDownClass.__func__)
    def setUp(self):
        from dataclasses import replace
        # This fixture also creates chat-linked jobs; remove those references
        # before the web fixture clears its jobs in this disposable database.
        with connect(replace(self.base, dsn=self.dsn)) as db:
            db.execute('DELETE FROM chat_turns')
            db.execute('DELETE FROM chat_conversations')
        fixtures.WebTests.setUp(self)
    create = fixtures.WebTests.create
    pinned = job_fixtures.EngineJobTests.pinned
    fake_runtime = job_fixtures.EngineJobTests.fake_runtime

    def wait(self):
        self.fake_runtime(); FakeRuntime.mode = 'wait'
        job = self.create(request_key=str(uuid4()), engine_kind='opencode', engine_questions=True)
        self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'waiting', row['issue'])
        detail = self.ws.detail(job)
        q = detail['questions'][0]
        data = dict(business_id=str(row['business_id']), run_id=str(row['engine_run_id']),
                    question_id=q['id'], phase='engine', disposition='answered', text='Unidades vendidas', request_key=str(uuid4()))
        return job, data

    def test_reply_receipt_and_web_queue_are_atomic_and_pending_clears_only_on_ack(self):
        job, data = self.wait(); row = self.ws.row(job)
        with connect(self.config) as db:
            before = db.execute('SELECT revision FROM memory_heads WHERE business_id=%s', (row['business_id'],)).fetchone()['revision']
            frozen = db.execute('SELECT prompt,input_context,limits FROM engine_runs WHERE id=%s', (row['engine_run_id'],)).fetchone()
        writer = questions._answer
        def crash(*args, **kwargs):
            writer(*args, **kwargs); raise SystemExit('Death before web receipt')
        with patch.object(questions, '_answer', side_effect=crash), self.assertRaises(SystemExit):
            self.ws.reply(job, data)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_owner_answers WHERE run_id=%s', (row['engine_run_id'],)).fetchone()['n'], 0)
        self.ws.reply(job, data); self.ws.reply(job, data)
        self.assertIsNotNone(self.ws.row(job)['pending_answer'])
        with patch.object(api, '_drive', side_effect=SystemExit('Before dispatch')), self.assertRaises(SystemExit):
            self.ws.run_job(job)
        self.assertIsNotNone(self.ws.row(job)['pending_answer'])
        self.ws.run_job(job)
        after = self.ws.row(job)
        self.assertEqual(after['status'], 'completed', after['issue'])
        self.assertIsNone(after['pending_answer'])
        self.assertEqual(after['engine_run_id'], row['engine_run_id'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT revision FROM memory_heads WHERE business_id=%s', (row['business_id'],)).fetchone()['revision'], before)
            self.assertEqual(db.execute('SELECT prompt,input_context,limits FROM engine_runs WHERE id=%s', (row['engine_run_id'],)).fetchone(), frozen)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_owner_answers WHERE run_id=%s', (row['engine_run_id'],)).fetchone()['n'], 1)
        self.ws.reply(job, data)  # retry after completion is still the same receipt

    def test_two_answers_and_foreign_run_never_replace_the_first(self):
        job, data = self.wait()
        with self.assertRaises(WebError):
            self.ws.reply(job, {**data, 'run_id': str(uuid4())})
        with self.assertRaises(WebError):
            self.ws.reply(job, {**data, 'question_id': str(uuid4())})
        outcomes=[]; barrier=threading.Barrier(2)
        def answer(i):
            barrier.wait()
            try: self.ws.reply(job, {**data, 'request_key': str(uuid4()), 'text': str(i)}); outcomes.append('saved')
            except WebError: outcomes.append('conflict')
        threads=[threading.Thread(target=answer,args=(i,)) for i in range(2)]
        for t in threads:t.start()
        for t in threads:t.join(5); self.assertFalse(t.is_alive())
        self.assertCountEqual(outcomes,['saved','conflict'])

    def test_expired_wait_is_visible_and_does_not_accept_web_resume(self):
        job,data=self.wait()
        with connect(self.config) as db:
            db.execute("UPDATE engine_owner_questions SET expires_at=now()-interval '1 second' WHERE id=%s", (data['question_id'],))
        detail=self.ws.detail(job)
        self.assertEqual((detail['status'],detail['questions']),('blocked',[]))
        with self.assertRaises(WebError):self.ws.reply(job,data)
        self.assertIsNone(self.ws.row(job)['pending_answer'])

    def test_saved_answer_expiration_or_definition_change_blocks_without_start(self):
        from decision_room.data_knowledge.service import ensure, change
        for problem in ('expired', 'definitions'):
            job, data = self.wait(); self.ws.reply(job, data); row = self.ws.row(job)
            if problem == 'expired':
                with connect(self.config) as db:
                    db.execute("UPDATE engine_owner_questions SET expires_at=now()-interval '1 second' WHERE id=%s", (data['question_id'],))
            else:
                model = ensure(self.config, row['business_id'], row['analysis_id'])
                change(self.config, row['business_id'], row['analysis_id'], model['revision'], 'table',
                       {'id': model['body']['tables'][0]['id'], 'grain': 'registro corregido'})
            with patch.object(FakeRuntime, 'start', side_effect=AssertionError('Must not start')), patch.object(FakeRuntime, 'restore', side_effect=AssertionError('Must not restore')):
                self.ws.run_job(job)
            after = self.ws.row(job)
            self.assertEqual(after['status'], 'blocked', after['issue'])
            self.assertEqual(after['pending_answer'], row['pending_answer'])
            with connect(self.config) as db:
                self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_owner_answers WHERE run_id=%s', (row['engine_run_id'],)).fetchone()['n'], 1)
            self.assertFalse(any('Owner response' in p['parts'][0]['text'] for p in FakeRuntime.sessions[str(row['engine_run_id'])]['messages']))

    def kill_worker(self, job, target, *, after=True, data=None):
        """Actual SIGKILL; fake runtime persistence is a test-owned local pickle."""
        import json, os, pickle, signal, subprocess, sys
        from pathlib import Path
        state_path = Path(self.temp.name) / 'fake-runtime-state'
        state_path.write_bytes(pickle.dumps(FakeRuntime.sessions))
        module, attribute = target
        module_name = module.__module__ if isinstance(module, type) else module.__name__
        class_name = module.__name__ if isinstance(module, type) else ''
        code = r"""
import importlib, json, os, pickle, signal, sys
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from decision_room.config import Config
from decision_room.engine import api
from decision_room.web.service import Workspace
from decision_room.web.engine_jobs import run
from tests.engine_fakes import FakeRuntime, FakeClient, FakeTunnel
state_path=Path(sys.argv[1]);FakeRuntime.sessions=pickle.loads(state_path.read_bytes());FakeRuntime.mode='wait'
config=replace(Config.load(),storage=Path(sys.argv[2]));FakeClient.config=config
module=importlib.import_module(sys.argv[4]);target=getattr(module,sys.argv[5]) if sys.argv[5] else module
original=getattr(target,sys.argv[6])
def die(*args,**kwargs):
    value=original(*args,**kwargs) if sys.argv[7]=='after' else None
    state_path.write_bytes(pickle.dumps(FakeRuntime.sessions))
    os.kill(os.getpid(),signal.SIGKILL)
with patch.object(api,'Runtime',FakeRuntime),patch.object(api,'DockerBackend',lambda:object()),patch.object(api,'JobTunnel',FakeTunnel),patch.object(api,'_service',lambda *a:SimpleNamespace(origin='http://127.0.0.1:1')),patch.object(target,sys.argv[6],new=die):
    workspace=Workspace(config)
    if sys.argv[8]:workspace.reply(sys.argv[3],json.loads(sys.argv[8]))
    else:run(workspace,sys.argv[3])
"""
        env={**os.environ,'DECISION_ROOM_DATABASE_URL':self.config.dsn,'OPENAI_API_KEY':''}
        result=subprocess.run([sys.executable,'-c',code,str(state_path),str(self.config.storage),str(job),module_name,class_name,attribute,'after' if after else 'before',json.dumps(data) if data else ''],env=env,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,-signal.SIGKILL,result.stderr.decode())
        FakeRuntime.sessions=pickle.loads(state_path.read_bytes())

    def test_sigkill_pause_and_checkpoint_recovery_do_not_start_agent(self):
        for target in ((questions, 'request'), (api, '_checkpoint'), (questions, 'confirm_waiting')):
            self.fake_runtime(); FakeRuntime.mode='wait'
            job=self.create(request_key=str(uuid4()), engine_kind='opencode', engine_questions=True)
            self.kill_worker(job, target)
            with patch.object(FakeRuntime, 'start', side_effect=AssertionError('Paused recovery must stay stopped')):
                self.ws.run_job(job)
            row=self.ws.row(job)
            # A question killed before prompt acknowledgement is retained but
            # cannot honestly enter waiting: conservative failure, no replay.
            expected='failed' if target[1]=='request' else 'waiting'
            self.assertEqual(row['status'], expected, row['issue'])
            self.assertEqual(sum(m['info']['role']=='user' for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages']),1)
            with connect(self.config) as db:
                self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_owner_questions WHERE run_id=%s', (row['engine_run_id'],)).fetchone()['n'],1)

    def test_sigkill_resume_boundaries_keep_session_and_exactly_one_answer(self):
        from decision_room.engine import control
        from tests.engine_fakes import FakeClient
        for target, after in (((questions,'activate_answer'),False), ((questions,'activate_answer'),True),
                              ((FakeClient,'submit'),True), ((control,'confirm_prompt'),True)):
            job,data=self.wait(); self.ws.reply(job,data); row=self.ws.row(job)
            original_session=FakeRuntime.sessions[str(row['engine_run_id'])]['session']['id']
            original_files=FakeRuntime.sessions[str(row['engine_run_id'])]['files'].copy()
            self.kill_worker(job,target,after=after)
            with patch.object(FakeRuntime,'restore',side_effect=AssertionError('Must reuse completed restore')):
                self.ws.run_job(job)
            current=self.ws.row(job)
            self.assertEqual(current['status'],'completed',current['issue'])
            self.assertIsNone(current['pending_answer'])
            state=FakeRuntime.sessions[str(row['engine_run_id'])]
            self.assertEqual(state['session']['id'],original_session)
            self.assertEqual(state['files'],original_files)
            self.assertEqual(sum(m['info']['role']=='user' for m in state['messages']),2)

    def test_restore_failure_keeps_receipt_and_checkpoint_without_new_generation(self):
        from pathlib import Path
        import json
        from decision_room.engine.export import folder
        job,data=self.wait();self.ws.reply(job,data);row=self.ws.row(job)
        with patch.object(FakeRuntime,'restore',side_effect=ValueError('Incomplete restore')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'],'failed')
        self.assertIsNotNone(self.ws.row(job)['pending_answer'])
        meta_path=folder(self.config,row['business_id'],row['engine_run_id'])/'control.json'
        meta=json.loads(meta_path.read_text())
        self.assertTrue(meta['restoring'])
        self.assertTrue((Path(self.config.storage)/meta['checkpoint_key']).exists())
        with patch.object(FakeRuntime,'start',side_effect=AssertionError('No retry')):
            self.ws.run_job(job)
        self.assertEqual(json.loads(meta_path.read_text())['instance_id'],meta['instance_id'])

    def test_two_workers_resume_once_and_lost_transport_ack_is_reconciled(self):
        from tests.engine_fakes import FakeClient
        job,data=self.wait(); self.ws.reply(job,data)
        original=FakeClient.submit
        def accepted_but_timeout(*args,**kwargs):
            original(*args,**kwargs);raise TimeoutError('Lost transport acknowledgement')
        barrier=threading.Barrier(2);errors=[]
        def worker():
            try: barrier.wait();self.ws.run_job(job)
            except BaseException as error:errors.append(error)
        with patch.object(FakeClient,'submit',new=accepted_but_timeout):
            threads=[threading.Thread(target=worker) for _ in range(2)]
            for t in threads:t.start()
            for t in threads:t.join(10);self.assertFalse(t.is_alive())
        self.assertEqual(errors,[])
        row=self.ws.row(job)
        self.assertEqual(row['status'],'completed',row['issue'])
        self.assertIsNone(row['pending_answer'])
        self.assertEqual(sum(m['info']['role']=='user' for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages']),2)

    def test_deep_guard_serializes_memory_writer_then_releases_lock(self):
        from decision_room.memory import service as memory
        job,data=self.wait(); row=self.ws.row(job)
        entered=threading.Event();release=threading.Event();written=threading.Event();errors=[]
        original=questions.context_reason
        def held_guard(*args,**kwargs):
            entered.set()
            if not release.wait(5):raise TimeoutError('Test lock release')
            return original(*args,**kwargs)
        def guard():
            try: questions.check_resume(self.config,row['business_id'],row['engine_run_id'],data['question_id'])
            except BaseException as error:errors.append(error)
        def writer():
            try:
                with connect(self.config) as db,db.transaction():
                    memory.lock(db,row['business_id'])
                    db.execute('UPDATE memory_heads SET revision=revision+1 WHERE business_id=%s',(row['business_id'],))
                written.set()
            except BaseException as error:errors.append(error)
        with patch.object(questions,'context_reason',side_effect=held_guard):
            first=threading.Thread(target=guard);first.start();self.assertTrue(entered.wait(5))
            second=threading.Thread(target=writer);second.start()
            self.assertFalse(written.wait(.1));release.set()
            for t in (first,second):t.join(5);self.assertFalse(t.is_alive())
        self.assertTrue(written.is_set());self.assertEqual(errors,[])

    def test_sigkill_during_restore_is_terminal_and_retains_answer(self):
        job,data=self.wait();self.ws.reply(job,data)
        self.kill_worker(job,(FakeRuntime,'restore'),after=True)
        with patch.object(FakeRuntime,'start',side_effect=AssertionError('No start after partial restore')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'],'failed')
        self.assertIsNotNone(self.ws.row(job)['pending_answer'])

    def test_context_change_after_activation_blocks_queued_owner_turn(self):
        from tests.engine_fakes import FakeClient
        from decision_room.data_knowledge.service import ensure,change
        job,data=self.wait();self.ws.reply(job,data);row=self.ws.row(job)
        original=questions.activate_answer
        def activate(*args,**kwargs):
            result=original(*args,**kwargs)
            model=ensure(self.config,row['business_id'],row['analysis_id'])
            change(self.config,row['business_id'],row['analysis_id'],model['revision'],'table',
                   {'id':model['body']['tables'][0]['id'],'grain':'nueva definición'})
            return result
        with patch.object(questions,'activate_answer',new=activate),patch.object(FakeClient,'submit',side_effect=AssertionError('No owner turn after revocation')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'],'blocked')
        self.assertIsNotNone(self.ws.row(job)['pending_answer'])

    def test_waiting_without_answer_never_starts_runtime(self):
        job,_=self.wait()
        with patch.object(FakeRuntime,'start',side_effect=AssertionError('Waiting is stopped')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'],'waiting')

    def test_sigkill_before_and_after_web_reply_transaction(self):
        from decision_room.web import engine_wait
        for target in ((questions,'_answer'),(engine_wait,'reply')):
            job,data=self.wait()
            self.kill_worker(job,target,data=data)
            row=self.ws.row(job)
            if target[1]=='_answer':
                self.assertIsNone(row['pending_answer'])
                with connect(self.config) as db:
                    self.assertFalse(db.execute('SELECT 1 FROM engine_owner_answers WHERE run_id=%s',(row['engine_run_id'],)).fetchone())
                self.ws.reply(job,data)
            else:self.assertIsNotNone(row['pending_answer'])
            self.ws.run_job(job)
            self.assertEqual(self.ws.row(job)['status'],'completed')
            self.assertIsNone(self.ws.row(job)['pending_answer'])

    def test_chat_answer_freezes_run_identity_and_never_captures_business_memory(self):
        from dataclasses import asdict,replace
        from psycopg.types.json import Jsonb
        from decision_room.conversations import Conversations
        from psycopg.conninfo import make_conninfo
        from decision_room.engine import admission,store
        from decision_room.reports.store import adopt
        self.config=replace(self.config,dsn=make_conninfo(self.config.dsn,options='-c statement_timeout=3000'));self.ws.config=self.config
        job,data=self.wait();row=self.ws.row(job)
        raw=b'<h1>Partial work</h1>'
        store.receive_file(self.config,row['business_id'],row['engine_run_id'],dict(status='received',raw=raw,bytes=len(raw),sha256=admission.sha(raw)))
        adopt(self.config,row['business_id'],row['engine_run_id'])
        chats=Conversations(self.ws.scoped(row['business_id']))
        chat=chats.create(dict(business_id=str(row['business_id']),request_key=str(uuid4()),analysis_id=str(row['analysis_id'])))['id']
        parent=uuid4()
        with connect(self.config) as db:
            db.execute('''INSERT INTO chat_turns(id,business_id,conversation_id,ordinal,request_key,payload,status,model_settings,job_id,response)
                VALUES(%s,%s,%s,1,%s,%s,'waiting',%s,%s,%s)''',
                (parent,row['business_id'],chat,uuid4(),Jsonb({'text':'Analiza mis datos','disposition':'answered'}),Jsonb(asdict(self.ws.settings)),job,Jsonb({'kind':'questions','questions':self.ws.detail(job)['questions']})))
            before=db.execute('SELECT revision FROM memory_heads WHERE business_id=%s',(row['business_id'],)).fetchone()['revision']
        answer=chats.send(chat,dict(business_id=str(row['business_id']),request_key=str(uuid4()),question_id=data['question_id'],text='No lo sé',disposition='unknown',context_references=[dict(kind='business',source_id=str(row['business_id']),source_version=str(self.business['profile_revision']),element_key='profile')]))['id']
        with connect(self.config) as db:
            turn=db.execute('SELECT * FROM chat_turns WHERE id=%s',(answer,)).fetchone()
            self.assertEqual(turn['payload']['run_id'],data['run_id'])
            self.assertIsNone(turn['memory_source_id'])
        chats.run(answer)
        self.assertEqual(self.ws.row(job)['pending_answer']['run_id'],data['run_id'])
        self.ws.run_job(job);chats.run(answer)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT revision FROM memory_heads WHERE business_id=%s',(row['business_id'],)).fetchone()['revision'],before)
            self.assertEqual(db.execute('SELECT status FROM chat_turns WHERE id=%s',(answer,)).fetchone()['status'],'completed')
