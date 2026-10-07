"""SIGKILL at durable boundaries: real processes/PostgreSQL/HTTP, no provider API."""
import multiprocessing
import os
import secrets
import signal
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from uuid import uuid4

import httpx

from decision_room.database import connect
from decision_room.engine import admission, api, control, store
from decision_room.engine.container import Runtime
from decision_room.engine.server import Server
from decision_room.docker_backend import DockerBackend
from tests import test_engine_admission as fixtures


def _park(pipe, value):
    pipe.send(value)
    threading.Event().wait()  # Parent kills this process; no cleanup or exception path.


def _draft_child(config, run, token, pipe, before_commit):
    if before_commit:
        original = admission._event
        def event(db, run_id, kind, payload):
            original(db, run_id, kind, payload)
            if kind == 'draft_received':
                _park(pipe, 'uncommitted')
        admission._event = event
    receipt = store.receive_document(config, run, token, request_key='interrupted', draft_json=b'{"unfinished":')
    _park(pipe, receipt)


def _controller_child(config, business, run, message_id, pipe):
    class Client:
        def submit(self, *args, **kwargs):
            _park(pipe, 'dispatching')
    with control.controller_lock(config, business, run):
        control.dispatch_prompt(config, business, run, message_id, Client())


def _proxy_child(config, pipe):
    def provider(request):
        if request.url.path.endswith('/input_tokens'):
            return httpx.Response(200, json={'input_tokens': 70})
        _park(pipe, 'admitted')
    with Server(config, api_key='synthetic-provider-key', transport=httpx.MockTransport(provider)) as server:
        pipe.send(server.origin)
        server.serve_forever()


class FaultTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create
    inspect = fixtures.EngineTests.inspect

    def child(self, target, *args):
        context = multiprocessing.get_context('spawn')
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=target, args=(*args, child))
        process.start(); child.close()
        def cleanup():
            if process.is_alive():
                process.kill()
            process.join(10)
            parent.close()
            process.close()
        self.addCleanup(cleanup)
        return process, parent

    def receive(self, pipe):
        self.assertTrue(pipe.poll(20), 'Child did not reach the fault boundary within 20 seconds.')
        return pipe.recv()

    def kill(self, process):
        process.kill(); process.join(10)
        self.assertEqual(process.exitcode, -signal.SIGKILL)

    def test_sigkill_before_and_after_draft_commit_preserves_exactly_one_retry(self):
        # Separate jobs ensure rollback and committed acknowledgement loss are distinct.
        for before in (True, False):
            with self.subTest(before_commit=before):
                run, token = self.create()
                store.receive_document(self.config, run, token, request_key='prior', draft_json=b'prior partial')
                context = multiprocessing.get_context('spawn')
                parent, child = context.Pipe(duplex=False)
                process = context.Process(target=_draft_child, args=(self.config, run, token, child, before))
                process.start(); child.close()
                try:
                    reached = self.receive(parent)
                    self.kill(process)
                    current = store.read_document(self.config, self.business, run)
                    self.assertEqual(current['raw'], b'prior partial' if before else b'{"unfinished":')
                    receipt = store.receive_document(self.config, run, token, request_key='interrupted', draft_json=b'{"unfinished":')
                    self.assertEqual(receipt['ordinal'], 2)
                    if not before:
                        self.assertEqual(receipt, reached)
                    with connect(self.config) as db:
                        count = db.execute("SELECT count(*) n FROM engine_events WHERE run_id=%s AND kind='draft_received'", (run,)).fetchone()['n']
                    self.assertEqual(count, 2)
                finally:
                    if process.is_alive(): process.kill()
                    process.join(10); parent.close(); process.close()

    def test_sigkill_controller_releases_lock_but_never_replays_uncertain_prompt(self):
        run, token = self.create()
        session = 'ses_' + uuid4().hex
        control.bind_session(self.config, self.business, run, session)
        row = control.enqueue_prompt(self.config, self.business, run, request_key='initial', text='Explain units.')
        process, pipe = self.child(_controller_child, self.config, self.business, run, row['message_id'])
        self.assertEqual(self.receive(pipe), 'dispatching'); self.kill(process)
        client = Mock(); client.message.return_value = None
        with control.controller_lock(self.config, self.business, run):
            self.assertEqual(control.dispatch_prompt(self.config, self.business, run, row['message_id'], client), 'dispatching')
        client.submit.assert_not_called()
        client.message.return_value = {'info': {'id': row['message_id'], 'sessionID': session, 'role': 'user'},
            'parts': [{'messageID': row['message_id'], 'sessionID': session, 'type': 'text', 'text': row['prompt']}]}
        self.assertEqual(control.dispatch_prompt(self.config, self.business, run, row['message_id'], client), 'confirmed')
        client.submit.assert_not_called()
        self.assertEqual(len(control.read_state(self.config, self.business, run)['outbox']), 1)

    def test_each_limit_preserves_raw_and_rejects_further_admission(self):
        for kind in ('input', 'output', 'per_call', 'calls', 'active'):
            with self.subTest(limit=kind):
                run, token = self.create(limits=admission.Limits(input_tokens=100, output_tokens=30, output_per_call=20, calls=2))
                store.receive_document(self.config, run, token, request_key='partial', draft_json=b'kept before limit')
                first = admission.begin_call(self.config, run, token, 'first')
                with self.assertRaises(admission.Aborted):
                    if kind == 'input':
                        admission.reserve(self.config, run, token, first, 101, 20)
                    elif kind == 'per_call':
                        admission.reserve(self.config, run, token, first, 1, 21)
                    elif kind == 'active':
                        with connect(self.config) as db:
                            db.execute("UPDATE engine_runs SET active_started_at=now()-interval '1 hour' WHERE id=%s", (run,))
                        admission.authenticate(self.config, run, token)
                    else:
                        second = admission.begin_call(self.config, run, token, 'second')
                        if kind == 'calls':
                            admission.begin_call(self.config, run, token, 'third')
                        else:
                            admission.reserve(self.config, run, token, first, 1, 20)
                            admission.reserve(self.config, run, token, second, 1, 20)
                self.assertEqual(self.inspect(run)['status'], 'aborted')
                with self.assertRaises(admission.Denied):
                    admission.begin_call(self.config, run, token, 'late')
                dest = self.root / kind
                store.export_raw(self.config, self.business, run, dest)
                self.assertEqual((dest/'draft.raw').read_bytes(), b'kept before limit')

    def test_concurrent_output_reservations_preserve_raw_and_charge_only_admitted_call(self):
        run, token = self.create(limits=admission.Limits(output_tokens=30, output_per_call=20))
        store.receive_document(self.config, run, token, request_key='partial', draft_json=b'kept')
        calls = [admission.begin_call(self.config, run, token, str(i)) for i in range(2)]
        barrier = threading.Barrier(2)
        def reserve(call):
            barrier.wait()
            try:
                admission.reserve(self.config, run, token, call, 10, 20)
                return True
            except admission.Denied:
                return False
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(reserve, calls)), 1)
        row = self.inspect(run)
        self.assertEqual((row['status'], row['charged_input'], row['charged_output']), ('aborted', 10, 20))
        self.assertEqual(store.read_document(self.config, self.business, run)['raw'], b'kept')

    def test_sse_disconnect_then_http_reconnect_retains_raw_and_never_replays_provider(self):
        run, token = self.create()
        store.receive_document(self.config, run, token, request_key='partial', draft_json=b'kept before stream')
        seen = []
        class BrokenStream(httpx.SyncByteStream):
            def __iter__(self):
                yield b'data: {"type":"response.output_text.delta","delta":"Partial"}\n\n'
                raise httpx.ReadError('Synthetic upstream disconnect')
        def provider(request):
            seen.append(request.url.path)
            if request.url.path.endswith('/input_tokens'):
                return httpx.Response(200, json={'input_tokens': 70})
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=BrokenStream())
        server = Server(self.config, api_key='synthetic', transport=httpx.MockTransport(provider))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = server.origin+f'/jobs/{run}/v1/responses'
        arguments = {'headers': {'Authorization': 'Bearer '+token},
                     'json': {'model': 'test-model', 'input': 'Compute', 'stream': True, 'max_output_tokens': 20}}
        with httpx.Client(trust_env=False, timeout=10) as client:
            result = client.post(url, **arguments)
            self.assertEqual(result.status_code, 200)
            self.assertIn('Partial', result.text)
        # A fresh TCP connection is allowed to ask, but cannot replay an uncertain call.
        with httpx.Client(trust_env=False, timeout=10) as client:
            self.assertEqual(client.post(url, **arguments).status_code, 403)
        row = self.inspect(run)
        self.assertEqual((row['status'], row['charged_input'], row['charged_output'], row['calls']), ('aborted', 70, 20, 1))
        self.assertEqual(seen, ['/v1/responses/input_tokens', '/v1/responses'])
        self.assertEqual(store.read_document(self.config, self.business, run)['raw'], b'kept before stream')

    @unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image.')
    def test_sigkill_http_proxy_then_real_controller_recovery_keeps_unknown_reservation(self):
        run, token = self.create()
        store.receive_document(self.config, run, token, request_key='partial', draft_json=b'partial before upstream')
        meta = {'run_id': str(run), 'instance_id': str(uuid4()), 'image': os.environ['DECISION_ROOM_ENGINE_IMAGE_ID'],
                'password': secrets.token_urlsafe(32), 'token': token, 'model': 'test-model', 'initialized': True}
        runtime = Runtime(DockerBackend(), **{k: meta[k] for k in ('run_id','instance_id','image','password','token','model')})
        self.addCleanup(runtime.remove); runtime.create()
        with runtime.start() as client:
            session = client.create_session(title='Proxy crash fixture', model='test-model')
            control.bind_session(self.config, self.business, run, session['id'])
        path = api.folder(self.config, self.business, run)/'control.json'; api._save(path, meta)
        process, pipe = self.child(_proxy_child, self.config)
        origin = self.receive(pipe)
        def request():
            try:
                with httpx.Client(trust_env=False, timeout=20) as client:
                    return client.post(origin+f'/jobs/{run}/v1/responses', headers={'Authorization': 'Bearer '+token},
                        json={'model': 'test-model', 'input': 'Compute', 'max_output_tokens': 20}).status_code
            except httpx.TransportError:
                return 'connection-lost'
        with ThreadPoolExecutor(1) as pool:
            response = pool.submit(request)
            self.assertEqual(self.receive(pipe), 'admitted')
            self.kill(process)
            self.assertEqual(response.result(timeout=20), 'connection-lost')
        self.assertEqual(self.inspect(run)['model_calls'][0]['state'], 'admitted')
        api._drive(self.config, self.business, run)
        row = self.inspect(run)
        self.assertEqual((row['status'], row['charged_input'], row['charged_output'], row['calls']), ('aborted', 70, 20, 1))
        self.assertEqual(row['abort_reason'], 'controller_recovery_usage_unknown')
        self.assertFalse(runtime._inspect()['State']['Running'])
        api._drive(self.config, self.business, run)
        self.assertEqual(self.inspect(run)['calls'], 1)
        dest = self.root/'recovered'; api.export_run(self.config, self.business, run, dest)
        self.assertEqual((dest/'draft.raw').read_bytes(), b'partial before upstream')
        self.assertTrue((dest/'proxy-calls.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
