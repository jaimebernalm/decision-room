"""Public engine API with real persistence and deterministic agent simulation."""
import json
import threading
import httpx
import os
import re
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room import engine
from decision_room.database import connect
from decision_room.service import import_batch
from decision_room.engine.client import ProtocolError
from decision_room.engine import api, admission, checkpoint, questions, store
from decision_room.reports.verification_contract import validate
from tests import test_engine_questions as fixtures


class FakeRuntime:
    sessions = {}
    mode = 'deliver'
    def __init__(self, backend, **kwargs):
        self.__dict__.update(kwargs); self.container_id = '0' * 64
        self.state = self.sessions.setdefault(self.run_id, {'session': None, 'messages': []})
    def create(self): return self.container_id
    def install_files(self, part, files):
        assert part == 'inputs' and 'manifest.json' in files
    def stop(self): pass
    def remove(self): pass
    def restore(self, snapshot): checkpoint.inspect(snapshot)
    def capture(self, destination):
        destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
        source = destination.parent / (uuid4().hex + '.db')
        with sqlite3.connect(source) as db:
            db.execute('CREATE TABLE fixture(value TEXT)')
        result = checkpoint.capture(source, destination); source.unlink(); return result
    def start(self): return FakeClient(self)


class FakeClient:
    def __init__(self, runtime): self.runtime = runtime; self.state = runtime.state
    def close(self): pass
    def require_mcp(self): pass
    def _request(self, method, path): return [self.state['session']] if self.state['session'] else []
    def create_session(self, **kwargs):
        self.state['session'] = {'id': 'ses_' + uuid4().hex, 'title': kwargs['title']}
        return self.state['session']
    def submit(self, session, *, message_id, text, model):
        def message(ident, role, content, **kwargs):
            return {'info': {'id': ident, 'sessionID': session, 'role': role, **kwargs},
                    'parts': [{'messageID': ident, 'sessionID': session, 'type': 'text', 'text': content}]}
        self.state['messages'].append(message(message_id, 'user', text))
        if self.runtime.mode == 'wait' and not any(m['info']['role'] == 'assistant' for m in self.state['messages']):
            questions.request(self.config, self.runtime.run_id, self.runtime.token,
                              request_key='need-unit', text='What unit?', reason='Missing from source')
        else:
            raw = json.dumps({'schema_version': 1, 'title': 'Resultado', 'summary': 'Total: 5 unidades.', 'findings': []})
            store.receive_document(self.config, self.runtime.run_id, self.runtime.token, request_key='final', draft_json=raw)
        self.state['messages'].append(message('msg_' + uuid4().hex, 'assistant', 'Trabajo guardado.',
                                            parentID=message_id, time={'completed': 1}, finish='stop'))
    def message(self, session, message_id):
        return next((m for m in self.state['messages'] if m['info']['id'] == message_id), None)
    def messages(self, session, **kwargs): return list(self.state['messages'])
    def children(self, session): return []
    def statuses(self): return {}
    def abort(self, session): return True


class FakeTunnel:
    def __init__(self, *args): pass
    def start(self): return self
    def close(self): pass
    def check(self): pass


# Reuse only DB/fixture lifecycle, not the other class's tests.
class ApiTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.QuestionTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.QuestionTests.tearDownClass.__func__)
    def setUp(self):
        fixtures.QuestionTests.setUp(self)
        FakeRuntime.sessions = {}; FakeRuntime.mode = 'deliver'; FakeClient.config = self.config
        for target, value in [('Runtime', FakeRuntime), ('DockerBackend', lambda: object()),
                              ('JobTunnel', FakeTunnel), ('_service', lambda *a: SimpleNamespace(origin='http://127.0.0.1:1'))]:
            patcher = patch.object(api, target, value); patcher.start(); self.addCleanup(patcher.stop)
        row = api._row(self.config, self.business, self.run)
        self.analysis = row['analysis_id']; self.table = row['snapshot'][0]['id']

    def run_report(self, key='public', **kwargs):
        return engine.run_report(self.config, self.business, self.analysis, owner_context='Explain units', request_key=key, **kwargs)

    def test_public_delivery_export_idempotence_and_business_scope(self):
        result = self.run_report(); self.assertEqual(result['status'], 'delivered', result)
        self.assertEqual(result, self.run_report())
        dest = self.root / 'export'; exported = engine.export_run(self.config, self.business, result['engine_run_id'], dest)
        required = {'draft.raw', 'draft.verified.json', 'verification.json', 'informe.html', 'informe.contenido.html',
                    'run.json', 'session-export.json', 'proxy-calls.jsonl'}
        self.assertTrue(required <= {p.name for p in dest.iterdir()})
        validate(json.loads((dest/'verification.json').read_text()), json.loads((dest/'draft.verified.json').read_text()), (dest/'draft.raw').read_bytes())
        self.assertEqual(json.loads((dest/'run.json').read_text()), exported)
        self.assertNotIn('<mark', (dest/'informe.contenido.html').read_text())
        with self.assertRaises(admission.Denied):
            engine.export_run(self.config, uuid4(), result['engine_run_id'], self.root/'foreign')
        self.assertFalse((self.root/'foreign').exists())
        with self.assertRaises(ValueError):
            engine.run_report(self.config, self.business, self.analysis, owner_context='Different', request_key='public')

    def test_public_wait_answer_resume_preserves_session_and_single_answer(self):
        FakeRuntime.mode = 'wait'
        initial = self.run_report(); self.assertEqual(initial['status'], 'waiting', initial)
        run = initial['engine_run_id']; first_session = FakeRuntime.sessions[run]['session']['id']
        self.assertEqual(engine.resume_report(self.config, self.business, run)['status'], 'waiting')
        answer = {'question_id': initial['question']['question_id'], 'disposition': 'unknown', 'text': '', 'request_key': 'answer'}
        resumed = engine.resume_report(self.config, self.business, run, answer=answer)
        self.assertEqual(resumed['status'], 'delivered', resumed)
        self.assertEqual(FakeRuntime.sessions[run]['session']['id'], first_session)
        self.assertEqual(resumed, engine.resume_report(self.config, self.business, run, answer=answer))
        self.assertEqual(sum(m['info']['role']=='user' for m in FakeRuntime.sessions[run]['messages']), 2)
        with self.assertRaises(ValueError):
            engine.resume_report(self.config, self.business, run, answer={**answer, 'text': 'changed'})

    def test_recovery_with_uncertain_call_aborts_without_resending_and_stops(self):
        # Persist a bootstrap identity and an admitted call, as if the host died.
        run, token = admission.create_run(self.config, self.business, self.analysis, table_ids=[self.table],
            owner_context='Explain units', request_key='recovery', model='gpt-6-luna')
        meta = {'run_id': str(run), 'instance_id': str(uuid4()), 'image': 'sha256:'+'0'*64,
                'password': 'fixture', 'token': token, 'model': 'gpt-6-luna', 'initialized': True}
        path = api.folder(self.config, self.business, run)/'control.json'; api._save(path, meta)
        call = admission.begin_call(self.config, run, token, 'fixture')
        admission.reserve(self.config, run, token, call, 10, 20)
        with patch.object(FakeRuntime, 'stop') as stopped, patch.object(FakeClient, 'submit') as submitted:
            result = engine.resume_report(self.config, self.business, run)
            self.assertTrue(stopped.called); submitted.assert_not_called()
        self.assertEqual(result['status'], 'aborted')
        self.assertEqual(result['usage']['charged_output'], 20)
        self.assertEqual(result['usage']['cost_catalog']['status'], 'incomplete')
        self.assertTrue(json.loads(path.read_text())['checkpoint_key'])

    def test_tool_step_and_older_completion_do_not_finish_the_current_turn(self):
        def reply(finish, parent='current'):
            return {'info': {'role': 'assistant', 'parentID': parent, 'time': {'completed': 1}, 'finish': finish}}
        self.assertFalse(api._completed_turn([reply('stop', 'old'), reply('tool-calls')], 'current'))
        self.assertFalse(api._completed_turn([reply('stop'), reply('unknown')], 'current'))
        self.assertTrue(api._completed_turn([reply('tool-calls'), reply('stop')], 'current'))

    def test_terminal_replay_stops_container_left_by_crash(self):
        result = self.run_report()
        with patch.object(FakeRuntime, 'stop') as stopped, patch.object(FakeClient, 'submit') as submitted:
            again = engine.resume_report(self.config, self.business, result['engine_run_id'])
            stopped.assert_called_once(); submitted.assert_not_called()
        self.assertEqual(again['status'], 'delivered')

    def test_failure_after_binding_records_safe_stage_before_any_prompt(self):
        with patch.object(FakeClient, 'require_mcp', side_effect=ProtocolError('The job tool connection is not ready.')):
            result = self.run_report('mcp-not-ready')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['usage']['calls'], 0)
        diagnostic = result['diagnostics'][0]
        self.assertEqual((diagnostic['stage'], diagnostic['exception_type'], diagnostic['reason']),
                         ('require_mcp', 'ProtocolError', 'mcp_not_ready'))
        with connect(self.config) as db:
            self.assertEqual(db.execute("SELECT count(*) n FROM engine_events WHERE run_id=%s AND kind='session_bound'",
                                        (result['engine_run_id'],)).fetchone()['n'], 1)
            events = db.execute("SELECT payload FROM engine_events WHERE run_id=%s AND kind='controller_issue'",
                                (result['engine_run_id'],)).fetchall()
        self.assertEqual(events[0]['payload'], diagnostic)
        state = api.control.read_state(self.config, self.business, result['engine_run_id'])
        self.assertEqual(state['outbox'], [])
        dest = self.root/'diagnostic-export'
        engine.export_run(self.config, self.business, result['engine_run_id'], dest)
        self.assertEqual(json.loads((dest/'run.json').read_text())['diagnostics'], [diagnostic])

    def test_failure_keeps_delivered_raw_and_withholds_arbitrary_exception_text(self):
        secret = 'private credential and filesystem location'
        with patch.object(FakeClient, 'statuses', side_effect=RuntimeError(secret)):
            result = self.run_report('safe-failure')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['diagnostics'][0]['stage'], 'read_turn_status')
        self.assertEqual(result['diagnostics'][0]['exception_type'], 'RuntimeError')
        self.assertNotIn(secret, str(result))
        received = store.read_document(self.config, self.business, result['engine_run_id'])
        self.assertTrue(received['raw'])
        dest = self.root/'partial'; engine.export_run(self.config,self.business,result['engine_run_id'],dest)
        self.assertEqual((dest/'draft.raw').read_bytes(), received['raw'])

    def test_cleanup_failures_do_not_hide_primary_diagnostic_or_skip_runtime_stop(self):
        with patch.object(FakeClient, 'require_mcp', side_effect=ProtocolError('The job tool connection is not ready.')), \
             patch.object(FakeTunnel, 'close', side_effect=[None, RuntimeError('private tunnel detail')]), \
             patch.object(FakeClient, 'close', side_effect=[None, RuntimeError('private client detail')]), \
             patch.object(FakeRuntime, 'stop') as stopped:
            result = self.run_report('cleanup-failures')
        self.assertGreaterEqual(stopped.call_count, 2)
        self.assertEqual([d['stage'] for d in result['diagnostics']], ['require_mcp','close_tunnel','close_client'])
        self.assertNotIn('private', str(result))
        self.assertEqual(result['status'], 'failed')

    def test_failed_render_keeps_raw_and_removes_stale_render(self):
        result = self.run_report(); dest = self.root/'export'
        engine.export_run(self.config, self.business, result['engine_run_id'], dest)
        before = (dest/'draft.raw').read_bytes()
        with patch('decision_room.engine.export.render', side_effect=RuntimeError('secret diagnostic')):
            result = engine.export_run(self.config, self.business, result['engine_run_id'], dest)
        self.assertEqual((dest/'draft.raw').read_bytes(), before)
        self.assertIn('report_export_incomplete', result['issues'])
        self.assertNotIn('secret', str(result))
        self.assertFalse((dest/'informe.html').exists())
        self.assertTrue((dest/'verification.json').exists())


@unittest.skipUnless(os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID'), 'Build the pinned engine image.')
class RealApiTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.QuestionTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.QuestionTests.tearDownClass.__func__)
    setUp = fixtures.QuestionTests.setUp

    def test_real_opencode_delivers_through_mock_responses_and_real_mcp(self):
        self.real_roundtrip()

    def test_real_opencode_waits_and_restores_same_session_with_mock_provider(self):
        self.real_roundtrip(wait=True)

    def test_real_opencode_reads_scoped_inputs_and_discovers_table_for_mcp(self):
        self.real_roundtrip(discover=True)

    def test_real_opencode_receives_shape_error_and_delivers_corrected_revision(self):
        self.real_roundtrip(repair=True)

    def real_roundtrip(self, wait=False, discover=False, repair=False):
        calls = []; actions = []; discovered = {}; provider_errors = []
        analysis = api._row(self.config, self.business, self.run)['analysis_id']
        if discover:
            source = self.root / 'periods.csv'
            source.write_text('date,product,channel,quantity\n2025-01-01,Item,Local,2\n2025-01-31,Item,Local,0\n2025-02-01,Item,Local,3\n2025-02-28,Item,Local,0\n')
            analysis = import_batch(self.config, self.business, [source])['analysis']['id']
        discovery = ['read_manifest', 'read_csv', 'read_outside', 'panorama', 'checkpoint_draft', 'panorama_next', 'consulta', 'calculo']
        def provider(request):
            self.assertEqual(request.url.host, 'api.openai.com')
            body = json.loads(request.content)
            if request.url.path.endswith('input_tokens'):
                return httpx.Response(200, json={'input_tokens': 10})
            self.assertEqual(body['max_output_tokens'], 16000)
            calls.append(body)
            action = ('malformed_draft' if repair and not actions
                      else discovery[len(actions)] if discover and len(actions) < len(discovery)
                      else 'preguntar_propietario' if wait and not actions else 'entregar_informe')
            tool_name = ('read' if action.startswith('read_') else 'panorama' if action == 'panorama_next'
                         else 'entregar_informe' if action in ('checkpoint_draft', 'malformed_draft') else action)
            tools = [t for t in body.get('tools', []) if t['name'].endswith(tool_name)]
            if repair and actions and actions[-1] == 'malformed_draft':
                outputs = [x.get('output', '') for x in body.get('input', []) if isinstance(x, dict) and x.get('type') == 'function_call_output']
                self.assertTrue(outputs)
                self.assertIn('/limitations', str(outputs[-1]))
                self.assertIn('string', str(outputs[-1]))
                self.assertIn('Raw draft saved', str(outputs[-1]))
            if discover and actions and actions[-1] in discovery:
                outputs = [x.get('output', '') for x in body.get('input', []) if isinstance(x, dict) and x.get('type') == 'function_call_output']
                output = str(outputs[-1]) if outputs else ''
                if actions[-1] == 'read_manifest':
                    matched = re.search(r'"id"\s*:\s*"([0-9a-f-]{36})"', output)
                    self.assertIsNotNone(matched, output)
                    discovered['table'] = matched[1]
                    self.assertIn('quantity', output)
                elif actions[-1] == 'read_csv':
                    self.assertIn('quantity', output)
                    self.assertNotIn('permission', output)
                elif actions[-1] == 'read_outside':
                    self.assertIn('external_directory', output)
                elif actions[-1] == 'panorama':
                    self.assertIn('deterministic_panorama', output)
                    self.assertNotIn('Invalid or unsuccessful', output)
                    for match in re.finditer(r'\{', output):
                        try:
                            data, _ = json.JSONDecoder().raw_decode(output[match.start():])
                        except ValueError:
                            continue
                        if isinstance(data, dict) and 'next_call' in data:
                            discovered['next_call'] = data['next_call']; break
                    self.assertEqual(discovered['next_call']['name'], 'panorama')
                    self.assertTrue(discovered['next_call']['reuse_previous_arguments'])
                    self.assertGreater(discovered['next_call']['arguments']['cursor'], 0)
                elif actions[-1] == 'checkpoint_draft':
                    self.assertIn('pending', output)
                elif actions[-1] == 'panorama_next':
                    self.assertIn('"requested_cursor":' + str(discovered['next_call']['arguments']['cursor']), output)
                    self.assertNotIn('Invalid or unsuccessful', output)
                elif actions[-1] == 'consulta':
                    self.assertIn('"status":"completed"', output)
                    self.assertIn('/metrics/rows', output)
                elif actions[-1] == 'calculo':
                    self.assertIn('deterministic_calculation', output)
                    self.assertIn('/metrics/units', output)
                    matched = re.search(r'"execution_id"\s*:\s*"([0-9a-f-]{36})"', output)
                    self.assertIsNotNone(matched, output)
                    discovered['calculation'] = matched[1]
            already = action in actions
            events = []
            def event(kind, **fields): events.append({'type': kind, **fields})
            response = {'id': 'resp_fixture_' + str(len(calls)), 'object': 'response', 'created_at': 1, 'model': 'gpt-6-luna',
                        'service_tier': 'default', 'status': 'in_progress', 'output': []}
            event('response.created', response=response.copy())
            if tools and not already:
                arguments = ({'request_key': 'fixture-question', 'text': 'What unit?', 'reason': 'Missing unit', 'options': []}
                    if action == 'preguntar_propietario' else {'request_key': 'fixture-final', 'draft_json': json.dumps({
                        'schema_version': 1, 'title': 'Fixture', 'summary': 'Total 5 unidades.', 'findings': []})})
                if action == 'read_manifest': arguments = {'filePath': '/inputs/manifest.json'}
                elif action == 'read_csv': arguments = {'filePath': '/inputs/' + discovered['table'] + '.csv'}
                elif action == 'read_outside': arguments = {'filePath': '/etc/hostname'}
                elif action == 'panorama': arguments = {'table_id': discovered['table'], 'request_key': 'discovered-table'}
                elif action == 'panorama_next':
                    arguments = {'table_id': discovered['table'], 'request_key': 'discovered-table',
                                 **discovered['next_call']['arguments']}
                elif action == 'checkpoint_draft':
                    arguments = {'request_key': 'checkpoint-before-next-page', 'draft_json': json.dumps({
                        'schema_version': 1, 'title': 'Avance', 'summary': 'Comparación pendiente.', 'findings': []})}
                elif action == 'malformed_draft':
                    arguments = {'request_key': 'needs-shape-correction', 'draft_json': json.dumps({
                        'schema_version': 1, 'title': 'Fixture', 'summary': 'Total 5 unidades.', 'limitations': ['Unresolved scope.'], 'findings': []})}
                elif action == 'consulta':
                    description = tools[0]['description']
                    self.assertIn('NO implicit Python variable named tables', description)
                    # Execute the advertised example verbatim, using the UUID
                    # discovered by the real native read of the job manifest.
                    program = description.split('from dr_runtime import connect, write_result', 1)[1].split('Returns execution_id', 1)[0]
                    program = 'from dr_runtime import connect, write_result' + program
                    arguments = {'tables': {'data': discovered['table']}, 'request_key': 'documented-example', 'code': program}
                elif action == 'calculo':
                    arguments = {'table_id': discovered['table'], 'request_key': 'scoped-units', 'recipes': [
                        {'key': 'units', 'operation': 'sum', 'column': 'quantity', 'filters': []}]}
                elif action == 'entregar_informe' and discover:
                    arguments['draft_json'] = json.dumps({'schema_version': 1, 'title': 'Fixture',
                        'summary': 'Total 5 unidades.', 'findings': [], 'facts': ['units'],
                        'numbers': [{'key': 'units', 'metric': 'units', 'execution_id': discovered['calculation']}]})

                actions.append(action)
                args = json.dumps(arguments)
                item = {'type': 'function_call', 'id': 'fc_fixture_' + str(len(calls)), 'call_id': 'call_fixture_' + str(len(calls)),
                        'name': tools[0]['name'], 'arguments': ''}
                event('response.output_item.added', output_index=0, item=item.copy())
                event('response.function_call_arguments.delta', item_id=item['id'], output_index=0, delta=args)
                item['arguments'] = args; item['status'] = 'completed'
                event('response.function_call_arguments.done', item_id=item['id'], output_index=0, arguments=args)
            else:
                item = {'type': 'message', 'id': 'msg_fixture_output_' + str(len(calls)), 'role': 'assistant', 'content': [], 'status': 'in_progress'}
                event('response.output_item.added', output_index=0, item=item.copy())
                part = {'type': 'output_text', 'text': '', 'annotations': []}
                event('response.content_part.added', item_id=item['id'], output_index=0, content_index=0, part=part.copy())
                event('response.output_text.delta', item_id=item['id'], output_index=0, content_index=0, delta='Guardado.')
                part['text'] = 'Guardado.'; item['content'] = [part]; item['status'] = 'completed'
                event('response.output_text.done', item_id=item['id'], output_index=0, content_index=0, text='Guardado.')
                event('response.content_part.done', item_id=item['id'], output_index=0, content_index=0, part=part)
            event('response.output_item.done', output_index=0, item=item)
            response.update(status='completed', output=[item], usage={'input_tokens': 10, 'output_tokens': 5,
                'input_tokens_details': {'cached_tokens': 2, 'cache_write_tokens': 3}})
            event('response.completed', response=response)
            return httpx.Response(200, headers={'content-type': 'text/event-stream'},
                content=b''.join(('data: '+json.dumps(e)+'\n\n').encode() for e in events))
        def checked_provider(request):
            try:
                return provider(request)
            except Exception as error:
                provider_errors.append(error)
                raise
        server = api.Server(self.config, api_key='offline-fixture', backend=api.DockerBackend(), transport=httpx.MockTransport(checked_provider))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with patch.object(api, '_service', return_value=server):
            result = engine.run_report(self.config, self.business, analysis, owner_context='Count fixture units',
                request_key='real-mock-provider', limits={'active_seconds': 90 if discover else 45})
        if wait:
            self.assertEqual(result['status'], 'waiting', result)
            run = result['engine_run_id']
            state = api.control.read_state(self.config, self.business, run)
            first_session = state['session_id']
            with patch.object(api, '_service', return_value=server):
                result = engine.resume_report(self.config, self.business, run, answer={
                    'question_id': result['question']['question_id'], 'disposition': 'unknown', 'text': '', 'request_key': 'fixture-answer'})
            self.assertEqual(api.control.read_state(self.config, self.business, run)['session_id'], first_session)
        path = api.folder(self.config, self.business, result['engine_run_id'])
        meta = json.loads((path/'control.json').read_text())
        runtime = api.Runtime(api.DockerBackend(), **{k: meta[k] for k in ('run_id','instance_id','image','password','token','model')})
        self.addCleanup(runtime.remove)
        if provider_errors:
            raise provider_errors[0]
        self.assertEqual(result['status'], 'delivered', result)
        self.assertGreaterEqual(len(calls), 2)
        if repair:
            self.assertEqual(actions, ['malformed_draft', 'entregar_informe'])
            with connect(self.config) as db:
                revisions = db.execute('''SELECT r.raw FROM engine_document_revisions r
                    JOIN engine_documents d ON d.id=r.document_id WHERE d.run_id=%s ORDER BY r.ordinal''',
                    (result['engine_run_id'],)).fetchall()
            self.assertEqual(len(revisions), 2)
            self.assertIsInstance(json.loads(bytes(revisions[0]['raw']))['limitations'], list)
            self.assertNotIn('report_format_fallback', result['issues'])
        if discover:
            self.assertEqual(actions, [*discovery, 'entregar_informe'])
            with connect(self.config) as db:
                self.assertEqual(db.execute('SELECT count(*) n FROM engine_panoramas WHERE run_id=%s',
                                            (result['engine_run_id'],)).fetchone()['n'], 1)
            self.assertNotIn('Comparación pendiente', (path/'export/draft.raw').read_text())
            ledger = json.loads((path/'export/verification.json').read_text())
            self.assertEqual([f['value'] for f in ledger['figures'] if f['verified']], ['5.00', '4', '4'])
            self.assertFalse(next(f for f in ledger['figures'] if f['path'] == '/summary')['verified'])
        self.assertTrue((path/'export/informe.contenido.html').exists())
        self.assertEqual(result['usage']['cost_catalog']['status'], 'estimated')
        self.assertFalse(runtime._inspect()['State']['Running'])

    def test_real_controller_with_disabled_provider_exports_failure_without_model_spend(self):
        analysis = api._row(self.config, self.business, self.run)['analysis_id']
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            result = engine.run_report(self.config, self.business, analysis, owner_context='Count fixture units',
                request_key='real-no-provider', limits={'active_seconds': 45})
        run = result['engine_run_id']
        path = api.folder(self.config, self.business, run)
        meta = json.loads((path/'control.json').read_text())
        runtime = api.Runtime(api.DockerBackend(), **{k: meta[k] for k in ('run_id','instance_id','image','password','token','model')})
        self.addCleanup(runtime.remove)
        self.assertIn(result['status'], ('failed', 'aborted'), result)
        self.assertEqual(result['usage']['calls'], 0)
        self.assertNotIn('controller_failure', result['issues'], result)
        state = api.control.read_state(self.config, self.business, run)
        self.assertTrue(state['session_id'])
        self.assertEqual(len(state['outbox']), 1)
        self.assertEqual(state['outbox'][0]['state'], 'confirmed')
        exported = engine.export_run(self.config, self.business, run, self.root/'real-export')
        self.assertEqual(exported['engine_run_id'], run)
        self.assertTrue((self.root/'real-export/session-export.json').exists())
        self.assertFalse(runtime._inspect()['State']['Running'])


if __name__ == '__main__': unittest.main()
