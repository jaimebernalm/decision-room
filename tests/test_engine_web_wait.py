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
    setUp = fixtures.WebTests.setUp
    create = fixtures.WebTests.create
    pinned = job_fixtures.EngineJobTests.pinned
    fake_runtime = job_fixtures.EngineJobTests.fake_runtime

    def wait(self):
        self.fake_runtime(); FakeRuntime.mode = 'wait'
        job = self.create(engine_kind='opencode', engine_questions=True)
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
