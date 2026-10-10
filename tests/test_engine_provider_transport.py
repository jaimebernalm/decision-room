"""Real HTTP sockets exercise provider connection policy without model traffic."""
import json
import socket
import struct
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx

from decision_room.engine import admission, proxy
from decision_room.engine.export import export_run
from decision_room.engine.transport_trace import TransportTrace
from tests import test_engine_admission as fixtures


class TraceTests(unittest.TestCase):
    def test_trace_never_reads_info_and_missing_events_are_unknown(self):
        class PrivateInfo(dict):
            def __getitem__(self, key):
                raise AssertionError('Trace must not inspect transport information')
            def __iter__(self):
                raise AssertionError('Trace must not inspect transport information')
        trace = TransportTrace()
        private = PrivateInfo(secret='fixture-private-key', url='private/path')
        trace('http11.send_request_headers.started', private)
        trace('http11.send_request_headers.failed', private)
        trace('untrusted.private.event', private)
        result = trace.snapshot()
        self.assertIsNone(result['request_headers_sent'])
        self.assertIsNone(result['request_body_sent'])
        self.assertIsNone(result['new_connection_observed'])
        self.assertEqual(len(result['events_seconds']), 2)
        self.assertNotIn('private', json.dumps(result))
        self.assertIsNone(TransportTrace().snapshot()['response_headers_received'])


class ProviderTransportTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create
    inspect = fixtures.EngineTests.inspect

    def provider(self, failure=None):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers['content-length']))
                # Retain the actual objects: descriptor numbers can be reused.
                requests.append((self.path, self.connection))
                if self.path.endswith('input_tokens'):
                    value = {'input_tokens': 70}
                else:
                    if failure:
                        self.close_connection = True
                        if failure == 'partial_headers':
                            self.connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: applic')
                            self.connection.shutdown(socket.SHUT_WR)
                        else:
                            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                            self.connection.close()
                        return
                    value = {'status': 'completed', 'usage': {'input_tokens': 70, 'output_tokens': 5}}
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/v1', requests

    def forward(self, run, token):
        return proxy.forward(self.config, run, token,
            admission.canonical({'model': 'test-model', 'input': 'Compute', 'max_output_tokens': 20}),
            api_key='fixture-provider-key', send_headers=lambda *_: None, write=lambda _: None)

    def test_count_and_generation_open_distinct_connections_and_export_success_trace(self):
        upstream, requests = self.provider()
        run, token = self.create()
        with patch.object(proxy, 'UPSTREAM', upstream):
            self.forward(run, token)
        self.assertEqual([path for path, _ in requests], ['/v1/responses/input_tokens', '/v1/responses'])
        self.assertIsNot(requests[0][1], requests[1][1])
        call = self.inspect(run)['model_calls'][0]
        self.assertEqual(call['state'], 'settled')
        self.assertEqual(call['transport']['connection_policy'], 'no_keepalive')
        for phase in ('input_count', 'generation'):
            for key in ('new_connection_observed', 'request_headers_sent', 'request_body_sent', 'response_headers_received'):
                self.assertTrue(call['transport'][phase][key])
        self.assertNotIn('transport', call['billing'])
        dest = self.root/'success-export'
        export_run(self.config, self.business, run, dest)
        self.assertEqual(json.loads((dest/'proxy-calls.jsonl').read_text())['transport'], call['transport'])

    def test_reset_and_partial_headers_keep_uncertain_reservation_without_retry(self):
        for failure in ('reset', 'partial_headers'):
            with self.subTest(failure=failure):
                upstream, requests = self.provider(failure)
                run, token = self.create()
                with patch.object(proxy, 'UPSTREAM', upstream), self.assertRaises(httpx.TransportError):
                    self.forward(run, token)
                state = self.inspect(run)
                self.assertEqual((state['status'], state['charged_input'], state['charged_output']), ('aborted', 70, 20))
                call = state['model_calls'][0]
                self.assertEqual(call['state'], 'uncertain')
                diagnostic = call['diagnostic']
                self.assertEqual(diagnostic['stage'], 'open_provider_response')
                trace = diagnostic['transport']['generation']
                self.assertTrue(trace['new_connection_observed'])
                self.assertTrue(trace['request_body_sent'])
                self.assertIsNone(trace['response_headers_received'])
                self.assertIn('http11.receive_response_headers.failed', trace['events_seconds'])
                self.assertEqual(len(requests), 2)
                self.assertIsNot(requests[0][1], requests[1][1])
                dest = self.root/failure
                snapshot = export_run(self.config, self.business, run, dest)
                self.assertIn(diagnostic, snapshot['diagnostics'])
                saved = (dest/'proxy-calls.jsonl').read_text()
                self.assertNotIn('fixture-provider-key', saved)
                self.assertNotIn(upstream, saved)
                with self.assertRaises(admission.Denied):
                    admission.begin_call(self.config, run, token, 'retry-forbidden')

    def test_untraced_transport_does_not_claim_that_nothing_was_sent(self):
        run, token = self.create()
        def fail(_):
            raise httpx.ReadError('fixture-private-error')
        with self.assertRaises(httpx.ReadError):
            proxy.forward(self.config, run, token,
                admission.canonical({'model': 'test-model', 'input': 'Compute'}),
                api_key='fixture', send_headers=lambda *_: None, write=lambda _: None,
                transport=httpx.MockTransport(fail))
        receipt = self.inspect(run)['model_calls'][0]['transport']
        self.assertEqual(receipt['connection_policy'], 'injected_transport')
        self.assertEqual(receipt['input_count']['events_seconds'], {})
        self.assertIsNone(receipt['input_count']['request_body_sent'])
        self.assertIsNone(receipt['generation']['new_connection_observed'])
