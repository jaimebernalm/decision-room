"""Real PostgreSQL/HTTP/Docker; provider traffic stays in httpx.MockTransport."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.engine import admission, gateway, proxy
from decision_room.engine.server import Server
from decision_room.service import create_business, import_batch
from decision_room.storage import Storage


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Engine fixture')['id']
        source = self.root / 'units.csv'
        source.write_text('quantity\n2\n3\n')
        batch = import_batch(self.config, self.business, [source])
        self.analysis = batch['analysis']['id']
        self.table = batch['files'][0]['table_id']

    def create(self, **kwargs):
        return admission.create_run(self.config, self.business, self.analysis,
                                    table_ids=[self.table], owner_context=kwargs.pop('owner_context', 'Units only.'),
                                    request_key=kwargs.pop('request_key', uuid4().hex), model='test-model', **kwargs)

    def inspect(self, run):
        return admission.inspect_run(self.config, self.business, run)

    def test_creation_idempotency_and_secret_not_persisted(self):
        run, token = self.create(request_key='once')
        self.assertEqual(self.create(request_key='once'), (run, None))
        with self.assertRaises(ValueError):
            self.create(request_key='once', owner_context='Different input')
        with connect(self.config) as db:
            rows = db.execute('SELECT * FROM engine_runs WHERE id=%s', (run,)).fetchall()
            events = db.execute('SELECT * FROM engine_events WHERE run_id=%s', (run,)).fetchall()
        self.assertNotIn(token, json.dumps([rows, events], default=str))
        self.assertEqual(admission.authenticate(self.config, run, token)['business_id'], self.business)

    def test_cross_job_business_expired_revoked_and_waiting_denied(self):
        first, token = self.create()
        second, other = self.create()
        for run, key in [(first, other), (second, token), (uuid4(), token), ('bad-id', token)]:
            with self.assertRaises(admission.Denied):
                admission.authenticate(self.config, run, key)
        foreign = create_business(self.config, 'Other fixture')['id']
        foreign_source = self.root / 'foreign.csv'
        foreign_source.write_text('quantity\n9\n')
        imported = import_batch(self.config, foreign, [foreign_source])
        foreign_run, foreign_token = admission.create_run(
            self.config, foreign, imported['analysis']['id'],
            table_ids=[imported['files'][0]['table_id']], owner_context='Other',
            request_key='foreign', model='test-model')
        for target, key in [(first, foreign_token), (foreign_run, token)]:
            with self.assertRaises(admission.Denied):
                admission.authenticate(self.config, target, key)
        with self.assertRaises(admission.Denied):
            admission.inspect_run(self.config, foreign, first)
        with self.assertRaises(admission.Denied):
            admission.revoke(self.config, foreign, first)
        with connect(self.config) as db:
            db.execute("UPDATE engine_runs SET credential_expires_at=now()-interval '1 second' WHERE id=%s", (first,))
            db.execute("UPDATE engine_runs SET status='waiting',active_started_at=NULL WHERE id=%s", (second,))
        for run, key in [(first, token), (second, other)]:
            with self.assertRaises(admission.Denied):
                admission.authenticate(self.config, run, key)
        third, third_token = self.create()
        admission.revoke(self.config, self.business, third)
        with self.assertRaises(admission.Denied):
            admission.authenticate(self.config, third, third_token)

    def test_changed_snapshot_aborts_before_admission(self):
        run, token = self.create()
        with connect(self.config) as db:
            db.execute('UPDATE prepared_tables SET parquet_sha256=%s WHERE id=%s', ('0'*64, self.table))
        with self.assertRaises(admission.Aborted):
            admission.begin_call(self.config, run, token, 'hash')
        state = self.inspect(run)
        self.assertEqual((state['status'], state['abort_reason'], state['calls']), ('aborted', 'snapshot_changed', 0))

    def test_changed_file_bytes_are_detected_even_with_unchanged_metadata(self):
        run, token = self.create()
        with connect(self.config) as db:
            key = db.execute('SELECT parquet_key FROM prepared_tables WHERE id=%s', (self.table,)).fetchone()['parquet_key']
        path = Storage(self.config.storage).path(self.business, key)
        path.chmod(0o600)
        path.write_bytes(b'changed')
        with self.assertRaises(admission.Aborted):
            admission.authenticate(self.config, run, token)

    def test_concurrent_reservations_cannot_over_admit(self):
        run, token = self.create(limits=admission.Limits(input_tokens=100, output_tokens=100, output_per_call=20))
        calls = [admission.begin_call(self.config, run, token, str(i)) for i in range(2)]
        barrier = threading.Barrier(2)
        def reserve(call):
            barrier.wait()
            try:
                admission.reserve(self.config, run, token, call, 70, 20)
                return 'admitted'
            except admission.Aborted:
                return 'aborted'
            except admission.Denied:
                return 'denied'
        with ThreadPoolExecutor(2) as pool:
            states = list(pool.map(reserve, calls))
        self.assertEqual(states.count('admitted'), 1)
        state = self.inspect(run)
        self.assertEqual((state['charged_input'], state['charged_output'], state['status']), (70, 20, 'aborted'))

    def test_unknown_usage_survives_fresh_process(self):
        run, token = self.create(request_key='uncertain')
        call = admission.begin_call(self.config, run, token, 'hash')
        admission.reserve(self.config, run, token, call, 70, 20)
        admission.settle(self.config, run, call)
        state = self.inspect(run)
        self.assertEqual((state['charged_input'], state['charged_output'], state['status']), (70, 20, 'aborted'))
        code = ('import json,sys; from pathlib import Path; from decision_room.config import Config; '
                'from decision_room.engine.admission import inspect_run; '
                'p=json.load(sys.stdin); r=inspect_run(Config(p[0],Path(p[1])),p[2],p[3]); '
                'print(json.dumps([r["charged_input"],r["charged_output"],r["status"]]))')
        output = subprocess.check_output([sys.executable, '-c', code], input=json.dumps([self.config.dsn, str(self.config.storage), str(self.business), str(run)]), text=True)
        self.assertEqual(json.loads(output), [70, 20, 'aborted'])
        self.assertEqual(self.create(request_key='uncertain'), (run, None))

    def test_settlement_releases_only_known_usage_and_is_idempotent(self):
        run, token = self.create()
        call = admission.begin_call(self.config, run, token, 'hash')
        admission.reserve(self.config, run, token, call, 70, 20)
        usage = {'input': 60, 'cached': 40, 'output': 9}
        admission.settle(self.config, run, call, usage=usage)
        admission.settle(self.config, run, call, usage=usage)
        self.assertEqual((self.inspect(run)['charged_input'], self.inspect(run)['charged_output']), (60, 9))
        with self.assertRaises(ValueError):
            admission.settle(self.config, run, call, usage={**usage, 'output': 8})

    def test_count_output_and_active_limits_abort_durably(self):
        for limit in ['calls', 'output', 'active']:
            with self.subTest(limit=limit):
                run, token = self.create(limits=admission.Limits(calls=1, output_per_call=5))
                call = admission.begin_call(self.config, run, token, 'hash')
                with self.assertRaises(admission.Aborted):
                    if limit == 'calls':
                        admission.begin_call(self.config, run, token, 'second')
                    elif limit == 'output':
                        admission.reserve(self.config, run, token, call, 1, 6)
                    else:
                        with connect(self.config) as db:
                            db.execute("UPDATE engine_runs SET active_started_at=now()-interval '1 hour' WHERE id=%s", (run,))
                        admission.authenticate(self.config, run, token)
                self.assertEqual(self.inspect(run)['status'], 'aborted')

    def test_cumulative_output_includes_concurrent_reservations(self):
        run, token = self.create(limits=admission.Limits(output_tokens=30, output_per_call=20))
        first = admission.begin_call(self.config, run, token, 'first')
        second = admission.begin_call(self.config, run, token, 'second')
        admission.reserve(self.config, run, token, first, 2, 20)
        with self.assertRaises(admission.Aborted):
            admission.reserve(self.config, run, token, second, 2, 20)
        state = self.inspect(run)
        self.assertEqual((state['charged_output'], state['abort_reason']), (20, 'token_limit'))
        admission.settle(self.config, run, first, usage={'input': 2, 'cached': 0, 'output': 5})
        self.assertEqual((self.inspect(run)['charged_output'], self.inspect(run)['status']), (5, 'aborted'))
        with self.assertRaises(admission.Denied):
            admission.begin_call(self.config, run, token, 'cannot-resume-on-refund')

    def test_http_proxy_hides_provider_errors_and_persists_abort(self):
        run, token = self.create()
        paths = []
        def provider(request):
            paths.append(request.url.path)
            return httpx.Response(503, text='private-provider-body')
        server = Server(self.config, api_key='test-secret', transport=httpx.MockTransport(provider))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = server.origin + f'/jobs/{run}/v1/responses'
        with httpx.Client(trust_env=False) as client:
            response = client.post(url, headers={'Authorization': 'Bearer ' + token},
                                   json={'model': 'test-model', 'input': 'Compute'})
            self.assertEqual(response.status_code, 429)
            self.assertNotIn('private-provider-body', response.text)
            self.assertNotIn('test-secret', response.text)
            self.assertEqual(self.inspect(run)['status'], 'aborted')
            again = client.post(url, headers={'Authorization': 'Bearer ' + token},
                                json={'model': 'test-model', 'input': 'Compute'})
            self.assertEqual(again.status_code, 403)
        self.assertEqual(paths, ['/v1/responses/input_tokens'])

    def test_provider_exceeding_reservation_is_recorded_not_hidden(self):
        run, token = self.create()
        call = admission.begin_call(self.config, run, token, 'hash')
        admission.reserve(self.config, run, token, call, 7, 8)
        reason = admission.settle(self.config, run, call, usage={'input': 9, 'cached': 0, 'output': 10})
        self.assertEqual(reason, 'provider_usage_exceeded_reservation')
        self.assertEqual((self.inspect(run)['charged_input'], self.inspect(run)['status']), (9, 'aborted'))

    def forward(self, run, token, handler, request=None):
        headers, chunks = [], []
        proxy.forward(self.config, run, token, admission.canonical(request or {'model': 'test-model', 'input': 'Compute.'}),
                      api_key='provider-test-only', transport=httpx.MockTransport(handler),
                      send_headers=lambda *args: headers.append(args), write=chunks.append)
        return headers, b''.join(chunks)

    def test_proxy_counts_same_input_caps_output_and_records_actual_usage(self):
        run, token = self.create()
        seen = []
        request = {'model': 'test-model', 'input': [{'role': 'user', 'content': 'Compute.'}],
                   'instructions': 'Use units', 'tools': [{'type': 'function', 'name': 'f', 'parameters': {}}],
                   'max_output_tokens': 999999, 'store': True}
        def handler(req):
            seen.append(json.loads(req.content))
            self.assertEqual(req.headers['Authorization'], 'Bearer provider-test-only')
            self.assertNotIn(token, req.content.decode())
            if req.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 7})
            return httpx.Response(200, json={'status': 'completed', 'usage': {'input_tokens': 7, 'output_tokens': 5, 'input_tokens_details': {'cached_tokens': 3}}, 'output': []})
        self.forward(run, token, handler, request)
        self.assertEqual(seen[0], {k: v for k, v in seen[1].items() if k in proxy.COUNT_FIELDS})
        self.assertEqual((seen[1]['max_output_tokens'], seen[1]['store']), (16000, False))
        self.assertEqual(seen[1]['service_tier'], 'default')
        self.assertNotIn('service_tier', seen[0])
        state = self.inspect(run)
        self.assertEqual((state['charged_input'], state['charged_output'], state['calls']), (7, 5, 1))
        self.assertIsNotNone(state['model_calls'][0]['admitted_at'])
        self.assertGreaterEqual(state['model_calls'][0]['count_seconds'], 0)

    def test_larger_default_per_call_preserves_explicit_limits_and_total_reservations(self):
        old, old_token = self.create(limits=admission.Limits(output_per_call=8000))
        current, token = self.create()
        self.assertEqual(admission.authenticate(self.config, old, old_token)['limits']['output_per_call'], 8000)
        self.assertEqual(admission.authenticate(self.config, current, token)['limits']['output_per_call'], 16000)
        seen = []
        def handler(request):
            if request.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 10})
            seen.append(json.loads(request.content)['max_output_tokens'])
            return httpx.Response(200, json={'status': 'completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}})
        self.forward(old, old_token, handler, {'model': 'test-model', 'input': 'Compute', 'max_output_tokens': 32000})
        self.assertEqual(seen, [8000])
        for i in range(8):
            call = admission.begin_call(self.config, current, token, str(i))
            admission.reserve(self.config, current, token, call, 10, 16000)
            admission.settle(self.config, current, call, usage={'input': 10, 'cached': 0, 'output': 15000})
        call = admission.begin_call(self.config, current, token, 'over-total')
        with self.assertRaises(admission.Aborted):
            admission.reserve(self.config, current, token, call, 10, 16000)
        state = self.inspect(current)
        self.assertEqual((state['charged_output'], state['abort_reason']), (120000, 'token_limit'))

    def test_processing_tier_cannot_be_upgraded_or_inherited_from_project(self):
        run, token = self.create()
        seen = []
        def provider(request):
            seen.append(request)
            self.fail('Tier rejected before any provider call or quota reservation')
        for tier in ['auto', 'fast', 'priority', 'flex', None, 1, {}, ['default']]:
            with self.subTest(tier=tier), self.assertRaises(admission.Denied):
                self.forward(run, token, provider,
                             {'model': 'test-model', 'input': 'Compute.', 'service_tier': tier})
        self.assertEqual(seen, [])
        self.assertEqual(self.inspect(run)['calls'], 0)
        job = admission.authenticate(self.config, run, token)
        request, count = proxy.prepare(admission.canonical(
            {'model': 'test-model', 'input': 'Compute.', 'service_tier': 'default'}), job)
        self.assertEqual(request['service_tier'], 'default')
        self.assertNotIn('service_tier', count)

    def test_count_failure_aborts_without_generation(self):
        run, token = self.create()
        paths = []
        def handler(req):
            paths.append(req.url.path)
            return httpx.Response(503, text='upstream-private-text')
        with self.assertRaises(admission.Aborted):
            self.forward(run, token, handler)
        self.assertEqual(paths, ['/v1/responses/input_tokens'])
        self.assertEqual(self.inspect(run)['abort_reason'], 'input_count_failed')

    def test_disconnect_without_usage_keeps_reservation(self):
        run, token = self.create()
        def handler(req):
            if req.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 7})
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=b'data: {"type":"response.output_text.delta","delta":"partial"}\n\n')
        with self.assertRaises(admission.Aborted):
            self.forward(run, token, handler, {'model': 'test-model', 'input': 'Compute', 'stream': True})
        state = self.inspect(run)
        self.assertEqual((state['charged_input'], state['charged_output'], state['status']), (7, 16000, 'aborted'))

    def test_sse_parser_handles_fragmentation_and_incomplete_usage(self):
        parser = proxy.EventUsage()
        event = 'data: {"type":"response.incomplete","response":{"status":"incomplete","usage":{"input_tokens":7,"output_tokens":8}},"label":"á"}\r\n\r\n'.encode()
        for byte in event:
            parser.feed(bytes([byte]))
        self.assertEqual(parser.usage, {'input': 7, 'cached': 0, 'output': 8})
        self.assertEqual(parser.status, 'incomplete')

    def test_proxy_rejects_remote_context_media_and_wrong_model(self):
        run, token = self.create()
        job = admission.authenticate(self.config, run, token)
        for extra in [{'previous_response_id': 'other-response'}, {'conversation': 'other-conversation'},
                      {'model': 'other-model'}, {'tools': [{'type': 'web_search'}]},
                      {'input': [{'type': 'item_reference', 'id': 'other-item'}]},
                      {'input': [{'role': 'user', 'content': [{'type': 'input_image', 'image_url': 'https://example.com'}]}]}]:
            with self.subTest(extra=extra), self.assertRaises(admission.Denied):
                proxy.prepare(admission.canonical({'model': 'test-model', 'input': 'Compute', **extra}), job)

    def test_mcp_real_calculation_idempotency_and_cross_job_result_denial(self):
        run, token = self.create()
        code = "from dr_runtime import connect, write_result\nwith connect() as db:\n    n = db.execute('SELECT sum(CAST(quantity AS BIGINT)) FROM units').fetchone()[0]\nwrite_result({'total':int(n)}, evidence=[{'metric':'total','tables':['units'],'operation':'SUM(quantity)'}])\n"
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'consulta', 'arguments': {'code': code, 'tables': {'units': str(self.table)}, 'request_key': 'sum'}}}
        first = gateway.dispatch(self.config, run, token, message)
        second = gateway.dispatch(self.config, run, token, message)
        a = json.loads(first['result']['content'][0]['text']); b = json.loads(second['result']['content'][0]['text'])
        self.assertEqual(a['execution_id'], b['execution_id'])
        self.assertEqual(a['status'], 'completed')
        self.assertIn({'path': '/metrics/total', 'part': 0, 'value': 5}, a['rows'])
        self.assertNotIn(str(self.config.storage), json.dumps(first))
        other, other_token = self.create()
        with self.assertRaises(admission.Denied):
            gateway.dispatch(self.config, other, other_token, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'resultado', 'arguments': {'execution_id': a['execution_id']}}})
        message['params']['arguments']['code'] += '\n# different request'
        changed = gateway.dispatch(self.config, run, token, message)
        self.assertTrue(changed['result']['isError'])

    def test_mcp_forbids_arbitrary_tables_and_scope_parameters(self):
        run, token = self.create()
        job = admission.authenticate(self.config, run, token)
        args = {'code': 'pass', 'request_key': 'bad', 'tables': {'units': str(uuid4())}}
        with self.assertRaises(admission.Denied):
            gateway.consulta(self.config, job, token, args)
        with self.assertRaises(ValueError):
            gateway.consulta(self.config, job, token, {**args, 'business_id': str(uuid4())})

    def test_pages_preserve_long_unicode_cells_and_bound_entire_mcp_response(self):
        value = '漢字' * 10000
        record = {'id': uuid4(), 'status': 'completed', 'result': {'metrics': {str(i): value for i in range(10)}}}
        cursor = 0; rows = []
        while True:
            page = gateway.page_result(record, cursor)
            self.assertLessEqual(len(page['rows']), 100)
            encoded = admission.canonical({'jsonrpc': '2.0', 'id': 1, 'result': {'content': [{'type': 'text', 'text': admission.canonical(page).decode()}]}})
            self.assertLessEqual(len(encoded), 64*1024)
            self.assertTrue(all(len(row['value']) <= 512 for row in page['rows']))
            rows += page['rows']
            if page['cursor'] is None:
                break
            self.assertGreater(page['cursor'], cursor)
            call = page['next_call']
            self.assertFalse(call['reuse_previous_arguments'])
            self.assertEqual(call['name'], 'resultado')
            self.assertEqual(call['arguments']['execution_id'], str(record['id']))
            self.assertEqual(call['arguments']['cursor'], page['next_cursor'])
            self.assertEqual(page['requested_cursor'], cursor)
            cursor = call['arguments']['cursor']
        self.assertIsNone(page['next_call'])
        self.assertEqual(''.join(r['value'] for r in rows if r['path'] == '/metrics/0'), value)
        self.assertEqual(len(rows), page['total_rows'])

    def test_http_auth_origin_protocol_and_exact_routes(self):
        run, token = self.create()
        server = Server(self.config)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        url = server.origin + f'/jobs/{run}/mcp'
        headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream'}
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}}
        with httpx.Client(trust_env=False) as client:
            self.assertEqual(client.post(url, json=payload).status_code, 403)
            self.assertEqual(client.post(url, json=payload, headers={**headers, 'Origin': 'https://foreign.invalid'}).status_code, 403)
            self.assertEqual(client.post(url+'?extra=1', json=payload, headers=headers).status_code, 403)
            self.assertEqual(client.post(url, json=payload, headers={**headers, 'MCP-Protocol-Version': 'bad'}).status_code, 400)
            self.assertEqual(client.get(url, headers=headers).status_code, 405)
            response = client.post(url, json=payload, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['result']['protocolVersion'], '2025-06-18')
            response = client.post(url, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}, headers=headers)
            self.assertEqual((response.status_code, response.content), (202, b''))


if __name__ == '__main__':
    unittest.main()
