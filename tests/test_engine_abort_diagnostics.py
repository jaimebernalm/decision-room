"""Aborts retain their boundary, reservations and partials without exposing errors."""
import json
import unittest
from unittest.mock import patch

import httpx

from decision_room.engine import admission, api, proxy, store
from decision_room.engine.export import export_run
from tests import test_engine_admission as fixtures


class AbortDiagnosticsTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create
    inspect = fixtures.EngineTests.inspect

    def partial(self, run, token):
        raw = b'{"schema_version":1,"title":"Partial","summary":"Work saved before interruption.","findings":[]}'
        store.receive_document(self.config, run, token, request_key='partial', html=raw)
        return raw

    def test_proxy_failure_boundaries_export_safely_and_never_release_unknown_reservations(self):
        for boundary in ('count_input', 'open_provider_response', 'read_provider_stream', 'write_downstream_chunk'):
            with self.subTest(boundary=boundary):
                run, token = self.create()
                raw = self.partial(run, token)
                seen = []
                private = 'fixture-secret-token and private/storage/location'
                class Interrupted(httpx.SyncByteStream):
                    def __iter__(self):
                        yield b'data: {"type":"response.output_text.delta","delta":"Work"}\n\n'
                        raise httpx.ReadTimeout(private)
                def provider(request):
                    seen.append(request.url.path)
                    if request.url.path.endswith('input_tokens'):
                        if boundary == 'count_input':
                            raise httpx.ReadTimeout(private)
                        return httpx.Response(200, json={'input_tokens': 70})
                    if boundary == 'open_provider_response':
                        raise httpx.ReadTimeout(private)
                    return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=Interrupted())
                def write(_):
                    if boundary == 'write_downstream_chunk':
                        raise BrokenPipeError(private)
                with self.assertRaises((httpx.ReadTimeout, BrokenPipeError)):
                    proxy.forward(self.config, run, token,
                        admission.canonical({'model': 'test-model', 'input': 'Compute', 'stream': True, 'max_output_tokens': 20}),
                        api_key='fixture-provider-key', send_headers=lambda *_: None, write=write,
                        transport=httpx.MockTransport(provider))
                state = self.inspect(run)
                self.assertEqual(state['status'], 'aborted')
                self.assertEqual((state['charged_input'], state['charged_output']), (0, 0) if boundary == 'count_input' else (70, 20))
                diagnostic = state['model_calls'][0]['diagnostic']
                self.assertEqual(diagnostic['stage'], boundary)
                self.assertEqual(diagnostic['exception_type'], 'BrokenPipeError' if boundary == 'write_downstream_chunk' else 'ReadTimeout')
                self.assertNotIn(private, json.dumps(diagnostic))
                dest = self.root / str(run)
                result = export_run(self.config, self.business, run, dest)
                self.assertEqual(result['status'], 'aborted')
                self.assertEqual((dest/'draft.raw').read_bytes(), raw)
                self.assertIn(diagnostic, result['diagnostics'])
                self.assertTrue((dest/'informe.raw.html').exists())
                self.assertEqual(json.loads((dest/'proxy-calls.jsonl').read_text())['diagnostic'], diagnostic)
                self.assertEqual(result['usage']['cost_catalog']['status'], 'incomplete')
                with self.assertRaises(admission.Denied):
                    admission.begin_call(self.config, run, token, 'do-not-retry')
                self.assertEqual(len(seen), 1 if boundary == 'count_input' else 2)

    def test_quota_rejection_records_limiting_dimension_and_keeps_its_actual_reason(self):
        run, token = self.create(limits=admission.Limits(output_tokens=30, output_per_call=20))
        raw = self.partial(run, token)
        call = admission.begin_call(self.config, run, token, 'first')
        admission.reserve(self.config, run, token, call, 10, 20)
        admission.settle(self.config, run, call, usage={'input': 10, 'cached': 0, 'output': 15})
        seen = []
        def provider(request):
            seen.append(request.url.path)
            return httpx.Response(200, json={'input_tokens': 10})
        with self.assertRaises(admission.Aborted):
            proxy.forward(self.config, run, token,
                admission.canonical({'model': 'test-model', 'input': 'Compute', 'max_output_tokens': 20}),
                api_key='fixture', send_headers=lambda *_: None, write=lambda _: None,
                transport=httpx.MockTransport(provider))
        dest = self.root / 'quota'
        result = export_run(self.config, self.business, run, dest)
        self.assertEqual(result['status'], 'aborted')
        self.assertEqual((dest/'draft.raw').read_bytes(), raw)
        self.assertNotIn('provider_usage_unknown', result['issues'])
        limited = next(d for d in result['diagnostics'] if d.get('limit') == 'output')
        self.assertEqual((limited['stage'], limited['requested_output'], limited['charged_output']), ('reserve_tokens', 20, 15))
        self.assertEqual(seen, ['/v1/responses/input_tokens'])
        self.assertEqual(self.inspect(run)['model_calls'][-1]['issue'], 'token_limit')

    def test_controller_deadline_without_exception_is_diagnostic_but_not_delivery(self):
        run, token = self.create()
        self.partial(run, token)
        api._finish(self.config, self.business, run, 'aborted', 'active_time_limit')
        result = export_run(self.config, self.business, run, self.root/'controller')
        self.assertEqual(result['status'], 'aborted')
        self.assertIn({'code': 'active_time_limit', 'reason': 'active_time_limit', 'stage': 'controller_finished'}, result['diagnostics'])

    def test_diagnostic_write_failure_does_not_prevent_uncertain_settlement(self):
        run, token = self.create()
        original = admission._event
        def event(db, run, kind, payload):
            if kind == 'proxy_issue':
                raise RuntimeError('Synthetic diagnostic storage failure')
            return original(db, run, kind, payload)
        def provider(request):
            if request.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 70})
            raise httpx.ReadTimeout('Synthetic transport failure')
        with patch.object(admission, '_event', side_effect=event), self.assertRaises(RuntimeError):
            proxy.forward(self.config, run, token,
                admission.canonical({'model': 'test-model', 'input': 'Compute', 'max_output_tokens': 20}),
                api_key='fixture', send_headers=lambda *_: None, write=lambda _: None,
                transport=httpx.MockTransport(provider))
        state = self.inspect(run)
        self.assertEqual((state['status'], state['charged_input'], state['charged_output']), ('aborted', 70, 20))
        self.assertEqual(state['model_calls'][0]['state'], 'uncertain')
