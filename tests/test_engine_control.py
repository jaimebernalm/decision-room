"""Real database outbox/crash semantics; provider and agent transport are simulated."""
import json
import os
import time
import subprocess
import sys
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
from decision_room.engine import admission, control
from decision_room.engine.client import DeliveryUncertain, ProtocolError
from decision_room.service import create_business, import_batch


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_control_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-control-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Control fixture')['id']
        source = self.root / 'units.csv'; source.write_text('quantity\n2\n3\n')
        batch = import_batch(self.config, self.business, [source])
        self.run, self.token = admission.create_run(self.config, self.business, batch['analysis']['id'],
            table_ids=[batch['files'][0]['table_id']], owner_context='Units', request_key=uuid4().hex, model='test-model')
        self.session = 'ses_' + uuid4().hex
        control.bind_session(self.config, self.business, self.run, self.session)

    def enqueue(self, key='initial', text='Explain the units.'):
        return control.enqueue_prompt(self.config, self.business, self.run, request_key=key, text=text)

    def state(self):
        return control.read_state(self.config, self.business, self.run)

    def message(self, row, *, role='user', text=None):
        return {'info': {'id': row['message_id'], 'sessionID': self.session, 'role': role},
                'parts': [{'id': 'prt_fixture', 'messageID': row['message_id'], 'sessionID': self.session,
                           'type': 'text', 'text': text if text is not None else row['prompt']}]}

    def test_session_binding_and_prompt_are_scoped_idempotent_and_serial(self):
        self.assertEqual(control.bind_session(self.config, self.business, self.run, self.session), self.session)
        with self.assertRaises(ValueError):
            control.bind_session(self.config, self.business, self.run, 'ses_other')
        barrier = threading.Barrier(2)
        def enqueue(_):
            barrier.wait(); return self.enqueue()
        with ThreadPoolExecutor(2) as pool:
            rows = list(pool.map(enqueue, range(2)))
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(len(self.state()['outbox']), 1)
        with self.assertRaises(ValueError):
            self.enqueue(text='Changed input')
        with self.assertRaises(admission.Denied):
            self.enqueue(key='next')
        with self.assertRaises(admission.Denied):
            control.read_state(self.config, uuid4(), self.run)
        with self.assertRaises(admission.Denied):
            control.enqueue_prompt(self.config, uuid4(), self.run, request_key='initial', text='Explain the units.')

    def test_204_is_not_confirmation_and_repeated_dispatch_does_not_resubmit(self):
        row = self.enqueue(); client = Mock(); client.message.return_value = None
        for _ in range(2):
            self.assertEqual(control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client), 'dispatching')
        client.submit.assert_called_once_with(self.session, message_id=row['message_id'], text=row['prompt'], model='test-model')
        client.message.return_value = self.message(row)
        self.assertEqual(control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client), 'confirmed')
        self.assertEqual(control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client), 'confirmed')
        self.assertEqual(client.submit.call_count, 1)
        self.assertEqual(len(self.state()['message_versions']), 1)
        self.assertEqual(self.enqueue(key='next')['state'], 'queued')

    def test_timeout_reconciles_later_without_sending_again(self):
        row = self.enqueue(); client = Mock(); client.submit.side_effect = RuntimeError('private transport data')
        with self.assertRaises(DeliveryUncertain) as error:
            control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client)
        self.assertNotIn('private', str(error.exception))
        self.assertEqual(self.state()['outbox'][0]['state'], 'dispatching')
        client.message.return_value = self.message(row)
        self.assertEqual(control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client), 'confirmed')
        self.assertEqual(client.submit.call_count, 1)

    def test_controller_exit_after_dispatch_marker_never_replays_even_if_message_absent(self):
        row = self.enqueue()
        script = '''import json,os,sys
from pathlib import Path
from decision_room.config import Config
from decision_room.engine.control import dispatch_prompt
p=json.load(sys.stdin)
class Client:
 def submit(self,*args,**kwargs):os._exit(21)
dispatch_prompt(Config(p['dsn'],Path(p['storage'])),p['business'],p['run'],p['message'],Client())
'''
        result = subprocess.run([sys.executable, '-c', script], input=json.dumps({
            'dsn': self.config.dsn, 'storage': str(self.config.storage), 'business': str(self.business),
            'run': str(self.run), 'message': row['message_id']}), text=True, capture_output=True)
        self.assertEqual(result.returncode, 21, result.stderr)
        client = Mock(); client.message.return_value = None
        self.assertEqual(control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client), 'dispatching')
        client.submit.assert_not_called()

    def test_confirmation_checks_exact_text_role_ids_and_dispatch_state(self):
        row = self.enqueue(); valid = self.message(row)
        with self.assertRaises(ProtocolError):
            control.confirm_prompt(self.config, self.business, self.run, row['message_id'], valid)
        client = Mock(); client.message.return_value = None
        control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client)
        invalid = [self.message(row, text='different'), self.message(row, role='assistant')]
        other_id = self.message({**row, 'message_id': 'msg_other'}); invalid.append(other_id)
        foreign = self.message(row); foreign['info']['sessionID'] = 'ses_other'; invalid.append(foreign)
        part = self.message(row); part['parts'][0]['messageID'] = 'msg_other'; invalid.append(part)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ProtocolError):
                control.confirm_prompt(self.config, self.business, self.run, row['message_id'], value)
        self.assertEqual(self.state()['outbox'][0]['state'], 'dispatching')
        self.assertEqual(control.confirm_prompt(self.config, self.business, self.run, row['message_id'], valid), 'confirmed')

    def test_partial_versions_are_retained_after_abort_and_shorter_observations(self):
        row = self.enqueue(); first = self.message(row, role='assistant', text='Partial')
        longer = self.message(row, role='assistant', text='Partial report with a result')
        for value in [first, longer, first]:
            control.record_messages(self.config, self.business, self.run, [value])
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET status='aborted' WHERE id=%s", (self.run,))
        final = self.message(row, role='assistant', text='Partial report with a result and conclusion')
        control.record_messages(self.config, self.business, self.run, [final])
        versions = self.state()['message_versions']
        self.assertEqual([v['content'] for v in versions], [first, longer, final])
        with self.assertRaises(admission.Denied):
            control.record_messages(self.config, uuid4(), self.run, [final])
        with connect(self.config) as db:
            db.execute('UPDATE engine_message_versions SET content=%s WHERE id=%s', ('{}', versions[0]['id']))
        with self.assertRaises(ValueError):
            self.state()

    def test_stopped_expired_and_over_budget_jobs_never_submit_queued_prompt(self):
        row = self.enqueue(); client = Mock()
        for status in ['waiting', 'pausing', 'aborted', 'failed', 'delivered']:
            with connect(self.config) as db:
                db.execute('UPDATE engine_runs SET status=%s WHERE id=%s', (status, self.run))
            with self.assertRaises(admission.Denied):
                control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client)
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET status='running',active_started_at=now()-interval '1 hour' WHERE id=%s", (self.run,))
        with self.assertRaises(admission.Aborted):
            control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client)
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['abort_reason'], 'active_time_limit')
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET status='running',active_started_at=now(),active_seconds=0,credential_expires_at=now()-interval '1 second' WHERE id=%s", (self.run,))
        with self.assertRaises(admission.Aborted):
            control.dispatch_prompt(self.config, self.business, self.run, row['message_id'], client)
        self.assertEqual(admission.inspect_run(self.config, self.business, self.run)['abort_reason'], 'credential_expired')
        client.submit.assert_not_called()

    @unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image for the real outbox test.')
    def test_real_opencode_persists_outbox_message_before_provider_failure(self):
        from tests.test_engine_image import isolated_server
        with connect(self.config) as db:
            row = db.execute('SELECT analysis_id,snapshot FROM engine_runs WHERE id=%s', (self.run,)).fetchone()
        run, token = admission.create_run(self.config, self.business, row['analysis_id'],
            table_ids=[t['id'] for t in row['snapshot']], owner_context='Units',
            request_key=uuid4().hex, model='gpt-6-luna')
        # No real provider exists at this loopback port and the network is internal.
        with isolated_server(os.environ['DECISION_ROOM_ENGINE_IMAGE_ID'], provider_unavailable=True) as (client, _, _):
            session = client.create_session(title='Durable outbox fixture', model='gpt-6-luna')
            control.bind_session(self.config, self.business, run, session['id'])
            queued = control.enqueue_prompt(self.config, self.business, run,
                                            request_key='once', text='Count the two fixture rows.')
            status = control.dispatch_prompt(self.config, self.business, run, queued['message_id'], client)
            for _ in range(30):
                if status == 'confirmed':
                    break
                time.sleep(0.1)
                status = control.dispatch_prompt(self.config, self.business, run, queued['message_id'], client)
            self.assertEqual(status, 'confirmed')
            client.abort(session['id'])
            messages = client.messages(session['id'])
            control.record_messages(self.config, self.business, run, messages)
            state = control.read_state(self.config, self.business, run)
            self.assertEqual(state['outbox'][0]['state'], 'confirmed')
            self.assertEqual(sum(m['info']['role'] == 'user' for m in messages), 1)
            self.assertGreaterEqual(len(state['message_versions']), 1)

    def test_only_one_controller_and_lock_released_after_exception(self):
        with control.controller_lock(self.config, self.business, self.run):
            with self.assertRaises(admission.Denied):
                with control.controller_lock(self.config, self.business, self.run):
                    self.fail('Second controller admitted')
        with self.assertRaises(RuntimeError):
            with control.controller_lock(self.config, self.business, self.run):
                raise RuntimeError('Controller exited')
        with control.controller_lock(self.config, self.business, self.run):
            pass


if __name__ == '__main__':
    unittest.main()
