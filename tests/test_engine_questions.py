"""Real PostgreSQL/SQLite owner-wait protocol; no container driver or model calls."""
import secrets
import json
import httpx
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.engine import admission, checkpoint, control, gateway, questions, store
from decision_room.engine.server import Server
from decision_room.service import create_business, import_batch


class QuestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_questions_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-questions-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Owner question fixture')['id']
        source = self.root / 'units.csv'; source.write_text('quantity\n2\n3\n')
        batch = import_batch(self.config, self.business, [source])
        self.run, self.token = admission.create_run(self.config, self.business, batch['analysis']['id'],
            table_ids=[batch['files'][0]['table_id']], owner_context='Units', request_key=uuid4().hex, model='test-model')
        self.session = 'ses_' + uuid4().hex
        control.bind_session(self.config, self.business, self.run, self.session)
        self.key = f'{self.business}/engine/{self.run}/checkpoints/{uuid4()}'
        state = self.root / 'state.db'
        with sqlite3.connect(state) as db:
            db.execute('CREATE TABLE fixture(value TEXT)')
            db.execute("INSERT INTO fixture VALUES ('saved')")
        checkpoint.capture(state, self.config.storage / self.key)

    def request(self, **changes):
        return questions.request(self.config, self.run, self.token,
                                 **{'request_key': 'owner-1', 'text': 'What is the unit?',
                                    'reason': 'The source does not declare it.', 'options': ['units', 'packages'], **changes})

    def pause(self):
        q = self.request()
        questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        return q

    def answer(self, q, **changes):
        return questions.answer(self.config, self.business, self.run,
            **{'question_id': q['question_id'], 'disposition': 'answered', 'text': 'units', 'request_key': 'answer-1', **changes})

    def test_question_concurrent_retry_closes_admission_and_keeps_raw(self):
        store.receive_document(self.config, self.run, self.token, request_key='draft', draft_json='partial raw')
        barrier = threading.Barrier(2)
        def ask(_):
            barrier.wait(); return self.request()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(ask, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0]['state'], 'pausing')
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'pausing')
        with self.assertRaises(admission.Denied):
            admission.begin_call(self.config, self.run, self.token, 'fixture')
        with self.assertRaises(admission.Denied):
            store.receive_document(self.config, self.run, self.token, request_key='late', draft_json='late')
        self.assertEqual(store.read_document(self.config, self.business, self.run)['raw'], b'partial raw')
        with self.assertRaises(ValueError):
            self.request(text='Changed')
        with self.assertRaises(admission.Denied):
            self.request(request_key='another')

    def test_gateway_allows_only_identical_question_receipt_while_waiting(self):
        args = {'request_key': 'owner-1', 'text': 'What is the unit?', 'reason': 'Unknown'}
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'preguntar_propietario', 'arguments': args}}
        first = gateway.dispatch(self.config, self.run, self.token, message)
        self.assertEqual(first, gateway.dispatch(self.config, self.run, self.token, message))
        denied = {**message, 'params': {'name': 'entregar_informe', 'arguments': {'request_key': 'late', 'draft_json': '{}'}}}
        with self.assertRaises(admission.Denied):
            gateway.dispatch(self.config, self.run, self.token, denied)
        admission.revoke(self.config, self.business, self.run)
        with self.assertRaises(admission.Denied):
            gateway.dispatch(self.config, self.run, self.token, message)

    def test_checkpoint_pin_is_scoped_validated_and_does_not_reset_expiry(self):
        q = self.request()
        for key in [str(uuid4()) + '/checkpoints/nope', self.key + '/../../../../other', self.key + '/missing']:
            with self.assertRaises((ValueError, OSError)):
                questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=key)
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'pausing')
        first = questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        before = questions.read(self.config, self.business, self.run)
        self.assertEqual(first, questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key))
        self.assertEqual(before['expires_at'], questions.read(self.config, self.business, self.run)['expires_at'])
        self.assertEqual(self.request()['state'], 'waiting')
        with self.assertRaises(admission.Denied):
            questions.read(self.config, uuid4(), self.run)
        file = self.config.storage / self.key / 'opencode.db'
        file.chmod(0o600); file.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)

    def test_unsettled_call_blocks_waiting_then_unknown_usage_aborts(self):
        call = admission.begin_call(self.config, self.run, self.token, 'fixture')
        admission.reserve(self.config, self.run, self.token, call, 100, 100)
        q = self.request()
        with self.assertRaises(admission.Denied):
            questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        admission.settle(self.config, self.run, call, reason='transport_lost')
        with self.assertRaises(admission.Denied):
            questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        run = admission.inspect_run(self.config, self.business, self.run)
        self.assertEqual(run['status'], 'aborted')
        self.assertEqual((run['charged_input'], run['charged_output']), (100, 100))

    def test_unconfirmed_prompt_blocks_pause_until_exact_reconciliation(self):
        outbox = control.enqueue_prompt(self.config, self.business, self.run, request_key='initial', text='Investigate')
        client = Mock(); client.message.return_value = None
        control.dispatch_prompt(self.config, self.business, self.run, outbox['message_id'], client)
        q = self.request()
        with self.assertRaises(admission.Denied):
            questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        persisted = {'info': {'id': outbox['message_id'], 'sessionID': self.session, 'role': 'user'},
                     'parts': [{'messageID': outbox['message_id'], 'sessionID': self.session, 'type': 'text', 'text': outbox['prompt']}]}
        control.confirm_prompt(self.config, self.business, self.run, outbox['message_id'], persisted)
        self.assertEqual(questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)['state'], 'waiting')

    def test_answer_durable_before_activation_and_retries_cannot_overwrite_it(self):
        q = self.pause()
        received = self.answer(q)
        self.assertEqual(received, self.answer(q))
        for change in [{'text': 'packages'}, {'request_key': 'different'}, {'disposition': 'declined'}]:
            with self.assertRaises(ValueError):
                self.answer(q, **change)
        with self.assertRaises(admission.Denied):
            questions.answer(self.config, uuid4(), self.run, question_id=q['question_id'], disposition='unknown', text='', request_key='x')
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'waiting')
        self.assertEqual(control.read_state(self.config, self.business, self.run)['outbox'], [])
        with self.assertRaises(ValueError):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=self.token)
        token = secrets.token_urlsafe(32)
        msg = questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=token)
        self.assertEqual(msg, questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=token))
        with self.assertRaises(ValueError):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=secrets.token_urlsafe(32))
        with self.assertRaises(admission.Denied):
            admission.authenticate(self.config, self.run, self.token)
        self.assertEqual(admission.authenticate(self.config, self.run, token)['id'], self.run)
        outbox = control.read_state(self.config, self.business, self.run)['outbox']
        self.assertEqual(len(outbox), 1)
        self.assertEqual(outbox[0]['state'], 'queued')
        self.assertIn('"disposition":"answered"', outbox[0]['prompt'])
        self.assertIsNone(questions.read(self.config, self.business, self.run))

    def test_wait_expiry_requires_explicit_answer_and_preserves_consumed_budget(self):
        call = admission.begin_call(self.config, self.run, self.token, 'fixture')
        admission.reserve(self.config, self.run, self.token, call, 100, 100)
        admission.settle(self.config, self.run, call, usage={'input': 100, 'cached': 10, 'output': 30})
        q = self.pause()
        with connect(self.config) as db:
            db.execute("UPDATE engine_owner_questions SET expires_at=now()-interval '1 day' WHERE id=%s", (q['question_id'],))
            db.execute("UPDATE engine_runs SET credential_expires_at=now()-interval '1 day' WHERE id=%s", (self.run,))
            seconds = db.execute('SELECT active_seconds FROM engine_runs WHERE id=%s', (self.run,)).fetchone()['active_seconds']
        self.assertTrue(questions.read(self.config, self.business, self.run)['expired'])
        token = secrets.token_urlsafe(32)
        with self.assertRaises(admission.Denied):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=token)
        self.answer(q, disposition='unknown', text='')
        questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=token)
        run = admission.inspect_run(self.config, self.business, self.run)
        self.assertEqual((run['charged_input'], run['charged_output'], run['calls']), (100, 30, 1))
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT active_seconds FROM engine_runs WHERE id=%s', (self.run,)).fetchone()['active_seconds'], seconds)
        self.assertIn('"disposition":"unknown"', control.read_state(self.config, self.business, self.run)['outbox'][0]['prompt'])

    def test_concurrent_activation_queues_once_and_declined_is_not_an_answer(self):
        q = self.pause(); self.answer(q, disposition='declined', text='')
        token = secrets.token_urlsafe(32); barrier = threading.Barrier(2)
        def activate(_):
            barrier.wait()
            return questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=token)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(activate, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(control.read_state(self.config, self.business, self.run)['outbox']), 1)

    def test_corrupt_checkpoint_and_revocation_prevent_activation(self):
        q = self.pause(); self.answer(q)
        file = self.config.storage / self.key / 'opencode.db'
        file.chmod(0o600); file.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=secrets.token_urlsafe(32))
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'waiting')
        admission.revoke(self.config, self.business, self.run)
        with self.assertRaises(admission.Denied):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=secrets.token_urlsafe(32))

    def test_time_limit_while_pausing_aborts_without_wait_reset(self):
        q = self.request()
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET active_started_at=now()-interval '1 hour' WHERE id=%s", (self.run,))
        with self.assertRaises(admission.Aborted):
            questions.confirm_waiting(self.config, self.business, self.run, q['question_id'], checkpoint_key=self.key)
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['abort_reason'], 'active_time_limit')

    def test_changed_snapshot_prevents_new_question_or_answer_activation(self):
        q = self.pause(); self.answer(q)
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET snapshot_sha256='changed' WHERE id=%s", (self.run,))
        with self.assertRaises(admission.Aborted):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=secrets.token_urlsafe(32))
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['abort_reason'], 'snapshot_changed')
        self.assertEqual(control.read_state(self.config, self.business, self.run)['outbox'], [])

    def test_invalid_question_does_not_pause_or_write_a_receipt(self):
        for changes in [{'text': ''}, {'reason': 'x' * 4097}, {'options': ['x'] * 9},
                        {'options': [1]}, {'request_key': ''}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.request(**changes)
        self.assertIsNone(questions.read(self.config, self.business, self.run))
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['status'], 'running')

    def test_http_receipt_retry_and_late_delivery_denial(self):
        server = Server(self.config)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json, text/event-stream'}
            url = server.origin + f'/jobs/{self.run}/mcp'
            payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
                'name': 'preguntar_propietario', 'arguments': {'request_key': 'http', 'text': 'Unit?', 'reason': 'Missing'}}}
            with httpx.Client(trust_env=False, timeout=5) as client:
                first = client.post(url, json=payload, headers=headers)
                self.assertEqual(first.status_code, 200)
                second = client.post(url, json=payload, headers=headers)
                self.assertEqual(second.status_code, 200)
                self.assertEqual(first.json(), second.json())
                payload['params'] = {'name': 'entregar_informe', 'arguments': {'request_key': 'late', 'draft_json': '{}'}}
                self.assertEqual(client.post(url, json=payload, headers=headers).status_code, 403)
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=5)

    def test_corrupt_answer_never_enters_the_outbox(self):
        q = self.pause(); self.answer(q)
        with connect(self.config) as db:
            db.execute('UPDATE engine_owner_answers SET body=%s WHERE question_id=%s',
                       (json.dumps({'disposition': 'answered', 'text': 'different'}), q['question_id']))
        with self.assertRaises(ValueError):
            questions.activate_answer(self.config, self.business, self.run, q['question_id'], new_token=secrets.token_urlsafe(32))
        self.assertEqual(control.read_state(self.config, self.business, self.run)['outbox'], [])


if __name__ == '__main__':
    unittest.main()
