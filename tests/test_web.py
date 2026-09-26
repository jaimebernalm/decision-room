"""Local web boundary and durable orchestration; scripted AI is not quality evidence."""
import json
import tempfile
import threading
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.agent import review
from decision_room.agent.model import ModelAPIError, ModelNotReady, ModelSettings, ModelRequestUncertain
from decision_room.web.server import Server
from decision_room.web.service import Workspace, WebError, MAX_UPLOAD
from test_agent import ScriptedModel
from test_review import DialogueModel, action


SETTINGS = ModelSettings(model='scripted-web-test-only')


class WebModel(DialogueModel):
    def __init__(self, settings=SETTINGS):
        super().__init__('owner')
        self.identity = asdict(settings)

    def generate_memory(self, context, correction=None):
        return {"candidates": []}, {}

    def generate(self, context, correction=None):
        data, usage = ScriptedModel.generate(self, context, correction)
        data['proposal']['investigations'] = data['proposal']['investigations'][:1]
        return data, usage

    def generate_reviewer(self, context, correction=None):
        asked = any(e['action']['action'] == 'ask_owner' for e in context['conversation'])
        if not asked:
            return action('ask_owner', question='¿Confirmas que amount es el total de cada fila?'), {}
        return action('approve', 'Revisión controlada de la evidencia.'), {}

    def generate_analyst_review(self, context, correction=None):
        response, usage = super().generate_analyst_review(context, correction)
        if response['report'] and any('row total' in a['text'] for a in context['owner_answers']):
            response['report']['claims'][0]['method'] = 'Suma de los importes de cada fila.'
        return response, usage


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_web_test_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-web-test-')
        self.addCleanup(self.temp.cleanup)
        self.config = replace(self.base, dsn=self.dsn, storage=Path(self.temp.name))
        with connect(self.config) as db, db.transaction():
            db.execute('DELETE FROM web_replies')
            db.execute('DELETE FROM web_jobs')
            db.execute('UPDATE web_workspace SET active_business_id=NULL')
            db.execute('DELETE FROM web_businesses')
        self.ws = Workspace(self.config, SETTINGS, WebModel)
        self.business = self.ws.save_business({'request_key': str(uuid4()), 'name': 'Test shop',
                                              'description': 'unit price, selected sales only'})
        self.metadata = {'request_key': str(uuid4()), 'business_id': str(self.business['id']), 'profile_revision': 1,
                         'goal': 'Understand sales', 'title': 'Web test'}
        self.csv = b'quantity,amount\n2,10\n3,20\n'

    def create(self, **changes):
        filename = changes.pop('filename', 'sales.csv')
        return self.ws.create({**self.metadata, **changes}, filename, self.csv)['id']

    def http(self):
        server = Server(self.ws, 0, token='test-local-access')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        client = httpx.Client(base_url=server.origin, headers={'Origin': server.origin, 'X-Decision-Room': '1'})
        self.addCleanup(client.close)
        return client, server

    def answer(self, job, text='unit price', disposition='answered'):
        data = self.ws.detail(job)
        q = data['questions'][0]
        answer = {'request_key': str(uuid4()), 'question_id': q['id'], 'phase': q['phase'], 'text': text, 'disposition': disposition}
        self.ws.reply(job, answer)
        return answer

    def complete(self):
        job = self.create()
        self.ws.run_job(job)
        self.assertEqual(self.ws.detail(job)['status'], 'waiting')
        self.answer(job)
        self.ws.run_job(job)
        self.assertEqual(self.ws.detail(job)['phase'], 'review')
        self.assertEqual(self.ws.detail(job)['status'], 'waiting')
        self.answer(job, 'Amount is row total.')
        self.ws.run_job(job)
        self.assertTrue(self.ws.detail(job)['publishable'])
        return job

    def test_upload_idempotency_and_changed_payload_rejected(self):
        job = self.create()
        self.assertEqual(self.create(), job)
        self.assertEqual(self.ws.upload(job), ('sales.csv', self.csv))
        with self.assertRaises(WebError):
            self.create(title='Different content')
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM web_jobs WHERE request_key=%s', (self.metadata['request_key'],)).fetchone()['n'], 1)

    def test_upload_constraints_and_missing_model(self):
        for filename, content in [('../secret.csv', self.csv), ('C:\\secret.csv', self.csv), ('x.xlsx', self.csv),
                                  ('x.csv', b''), ('x.csv', b'\xff'), ('x.csv', b'x' * (MAX_UPLOAD + 1))]:
            with self.subTest(filename=filename, length=len(content)), self.assertRaises(WebError):
                self.ws.create(self.metadata, filename, content)
        for update in [{'business': ''}, {'context': ''}, {'request_key': 'bad'}, {'context': 'x' * 6001}]:
            with self.assertRaises(WebError):
                self.create(**update)
        self.ws.settings = None
        with self.assertRaises(WebError):
            self.create()

    def test_changed_private_upload_is_not_served_as_original(self):
        job = self.create()
        row = self.ws.row(job)
        (self.config.storage / row['upload_key']).write_bytes(b'changed')
        with self.assertRaisesRegex(WebError, 'no coincide'):
            self.ws.upload(job)
        self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'], 'failed')
        self.assertIsNone(self.ws.row(job)['analysis_id'])

    def test_real_pipeline_planning_and_review_answers_report_and_hold(self):
        job = self.complete()
        detail = self.ws.detail(job)
        self.assertEqual(len(detail['answers']), 2)
        self.assertEqual(detail['files'][0]['row_count'], 2)
        html = self.ws.report(job)
        self.assertIn('Ver cómo se ha calculado', html)
        self.assertIn('30.00', html)
        self.assertNotIn('storage_key', html)
        dashboard = self.ws.dashboard()
        self.assertEqual(dashboard['selected_id'], job)
        self.assertEqual(dashboard['report']['title'], 'Ventas seleccionadas')
        self.assertEqual(len(dashboard['reports']), 1)
        client, _ = self.http()
        client.post('/api/login', json={'token': 'test-local-access'})
        self.assertEqual(client.get('/api/dashboard').json()['selected_id'], job)
        row = self.ws.row(job)
        review.hold(self.config, row['business_id'], row['review_id'], reason='Controlled hold for test.')
        self.assertFalse(self.ws.detail(job)['publishable'])
        self.assertEqual(self.ws.detail(job)['status'], 'blocked')
        self.assertEqual(next(j for j in self.ws.listing() if str(j['id']) == job)['status'], 'blocked')
        self.assertIsNone(self.ws.dashboard()['report'])
        self.assertIsNone(client.get('/api/dashboard').json()['report'])
        with self.assertRaises(WebError):
            self.ws.report(job)

    def test_resume_new_workspace_preserves_question_and_answer_idempotency(self):
        job = self.create()
        self.ws.run_job(job)
        first = self.ws.detail(job)
        self.ws = Workspace(self.config, SETTINGS, WebModel)
        self.assertEqual(self.ws.detail(job)['questions'], first['questions'])
        self.assertEqual(self.ws.detail(job)['status'], 'waiting')
        reply = self.answer(job)
        self.ws.reply(job, reply)
        with self.assertRaises(WebError):
            self.ws.reply(job, {**reply, 'text': 'different'})
        with self.assertRaises(WebError):
            self.ws.reply(job, {**reply, 'request_key': str(uuid4())})
        self.ws.run_job(job)
        self.ws.reply(job, reply)
        self.assertEqual(len(self.ws.detail(job)['answers']), 1)
        self.assertEqual(self.ws.detail(job)['questions'][0]['phase'], 'review')

    def test_unknown_answer_blocks_dependent_calculation(self):
        job = self.create()
        self.ws.run_job(job)
        self.answer(job, '', 'unknown')
        self.ws.run_job(job)
        self.assertEqual(self.ws.detail(job)['status'], 'blocked')
        self.assertIsNone(self.ws.row(job)['research_id'])
        with self.assertRaises(WebError):
            self.ws.report(job)

    def test_recovery_after_child_saved_before_parent_link(self):
        job = self.create()
        original = self.ws.update
        def crash(job_id, **values):
            if 'session_id' in values:
                raise KeyboardInterrupt()
            return original(job_id, **values)
        with patch.object(self.ws, 'update', side_effect=crash), self.assertRaises(KeyboardInterrupt):
            self.ws.run_job(job)
        self.assertIsNone(self.ws.row(job)['session_id'])
        ws = Workspace(self.config, SETTINGS, WebModel)
        self.assertTrue(ws.work_once())
        self.assertFalse(ws.work_once())
        self.assertEqual(ws.detail(job)['status'], 'waiting')
        with connect(self.config) as db:
            sessions = db.execute('SELECT count(*) AS n FROM agent_sessions WHERE business_id=%s', (ws.row(job)['business_id'],)).fetchone()['n']
            self.assertEqual(sessions, 1)

    def test_recover_answer_saved_before_model_interruption(self):
        job = self.create()
        self.ws.run_job(job)
        self.answer(job)
        from decision_room.agent import service as planning
        with patch.object(planning, '_drive', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.ws.run_job(job)
        self.assertEqual(len(self.ws.detail(job)['answers']), 1)
        ws = Workspace(self.config, SETTINGS, WebModel)
        ws.run_job(job)
        self.assertEqual(len(ws.detail(job)['answers']), 1)
        self.assertEqual(ws.detail(job)['phase'], 'review')

    def test_worker_exclusion(self):
        self.create()
        with connect(self.config) as db:
            db.execute('SELECT pg_advisory_lock(87120938)')
            with patch.object(self.ws, 'run_job') as drive:
                self.assertFalse(self.ws.work_once())
                drive.assert_not_called()

    def test_explicit_retry_recovers_uncertain_call_after_saved_answer(self):
        job = self.create()
        self.ws.run_job(job)
        self.answer(job)
        with patch.object(WebModel, 'generate', side_effect=ModelRequestUncertain('Uncertain test response')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'], 'failed')
        self.assertEqual(len(self.ws.detail(job)['answers']), 1)
        self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'], 'failed')
        self.ws.retry(job)
        self.ws.run_job(job)
        self.assertEqual(self.ws.detail(job)['status'], 'waiting')
        self.assertEqual(self.ws.detail(job)['phase'], 'review')
        self.assertEqual(len(self.ws.detail(job)['answers']), 1)

    def test_explicit_retry_recovers_uncertain_review_answer(self):
        job = self.create()
        self.ws.run_job(job)
        self.answer(job)
        self.ws.run_job(job)
        self.answer(job, 'Amount is row total.')
        with patch.object(WebModel, 'generate_analyst_review', side_effect=ModelRequestUncertain('Uncertain review response')):
            self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['status'], 'failed')
        self.assertEqual(len(self.ws.detail(job)['answers']), 2)
        self.ws.retry(job)
        self.ws.run_job(job)
        self.assertTrue(self.ws.detail(job)['publishable'])
        self.assertEqual(len(self.ws.detail(job)['answers']), 2)

    def test_failures_do_not_leak_internal_paths_or_auto_retry(self):
        job = self.create()
        with patch('decision_room.web.service.ingestion.import_batch', side_effect=RuntimeError('private/path/password')):
            self.ws.run_job(job)
        data = self.ws.detail(job)
        self.assertEqual(data['status'], 'failed')
        self.assertNotIn('password', json.dumps(data, default=str))
        self.ws.retry(job)
        self.assertTrue(self.ws.row(job)['retry_uncertain'])
        with self.assertRaises(WebError):
            self.ws.retry(job)

    def test_model_rejection_in_review_is_explained_and_retry_keeps_progress(self):
        job = self.create()
        self.ws.run_job(job)
        self.answer(job)
        with patch.object(WebModel, 'generate_analyst_review', side_effect=ModelAPIError(400)):
            self.ws.run_job(job)
        failed = self.ws.row(job)
        self.assertEqual(failed['status'], 'failed')
        self.assertIn('HTTP 400', self.ws.detail(job)['issue'])
        self.assertIn('no reinicia el modelo', self.ws.detail(job)['issue'])
        self.assertIsNotNone(failed['review_id'])
        self.assertFalse(self.ws.work_once())  # No repeated requests until explicit retry.
        client, _ = self.http()
        client.post('/api/login', json={'token': 'test-local-access'})
        with patch.object(WebModel, 'check_ready', create=True, side_effect=ModelNotReady('El modelo no está cargado.')):
            response = client.post(f'/api/jobs/{job}/retry', json={})
        self.assertEqual(response.status_code, 409)
        self.assertIn('no está cargado', response.json()['error'])
        self.assertEqual(self.ws.row(job)['status'], 'failed')
        self.assertFalse(self.ws.row(job)['retry_uncertain'])
        self.assertFalse(self.ws.work_once())
        self.ws.retry(job)
        self.ws.run_job(job)
        resumed = self.ws.row(job)
        self.assertEqual(resumed['status'], 'waiting')
        for key in ('analysis_id', 'session_id', 'research_id', 'review_id'):
            self.assertEqual(failed[key], resumed[key])
        self.assertEqual(len(self.ws.detail(job)['answers']), 1)

    def test_missing_evidence_blocks_only_affected_report(self):
        job = self.complete()
        with patch('decision_room.web.service.review.show', side_effect=FileNotFoundError('private missing evidence')):
            self.assertEqual(self.ws.detail(job)['status'], 'blocked')
            self.assertEqual(next(j for j in self.ws.listing() if str(j['id']) == job)['status'], 'blocked')
            with self.assertRaises(WebError):
                self.ws.report(job)

    def test_http_rejects_oversized_body_before_reading_it(self):
        from http.client import HTTPConnection
        _, server = self.http()
        connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        self.addCleanup(connection.close)
        connection.putrequest('POST', '/api/jobs')
        for key, value in {'Origin': server.origin, 'X-Decision-Room': '1', 'Cookie': 'dr_session=test-local-access',
                           'Content-Type': 'multipart/form-data; boundary=test', 'Content-Length': str(MAX_UPLOAD + 50_001)}.items():
            connection.putheader(key, value)
        connection.endheaders()
        self.assertEqual(connection.getresponse().status, 413)

    def test_http_auth_origin_host_limits_and_static_csp(self):
        client, server = self.http()
        self.assertEqual(client.get('/').status_code, 200)
        self.assertIn("script-src 'self'", client.get('/').headers['Content-Security-Policy'])
        self.assertEqual(client.get('/api/workspace').status_code, 401)
        self.assertEqual(client.get('/api/dashboard').status_code, 401)
        self.assertEqual(client.post('/api/login', json={'token': 'bad'}).status_code, 401)
        self.assertEqual(client.post('/api/login', json={'token': 'test-local-access'}, headers={'Origin': 'https://outside.test'}).status_code, 403)
        response = client.post('/api/login', json={'token': 'test-local-access'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=Strict', response.headers['set-cookie'])
        self.assertEqual(client.get('/api/workspace').status_code, 200)
        self.assertIsNone(client.get('/api/dashboard').json()['report'])
        self.assertEqual(client.get('/api/workspace', headers={'Host': 'outside.test'}).status_code, 403)
        self.assertEqual(client.post('/api/jobs', content=b'x', headers={'X-Decision-Room': ''}).status_code, 403)
        created = client.post('/api/jobs', files={'metadata': (None, json.dumps(self.metadata)), 'file': ('sales.csv', self.csv)})
        self.assertEqual(created.status_code, 202)
        download = client.get('/api/jobs/' + created.json()['id'] + '/file')
        self.assertEqual(download.content, self.csv)
        self.assertIn('attachment', download.headers['Content-Disposition'])
        self.assertEqual(client.get('/api/jobs/' + str(uuid4())).status_code, 404)
        self.assertEqual(client.get('/api/jobs/not-a-uuid').status_code, 400)
        self.assertEqual(client.get('/api/jobs/' + str(uuid4()) + '/file').status_code, 404)
        self.assertEqual(client.get('/api/sample').status_code, 200)
        self.assertEqual(client.get('/styles.css').status_code, 200)

    def test_cross_question_and_unreviewed_report_denied(self):
        job = self.create()
        self.ws.run_job(job)
        question = self.ws.detail(job)['questions'][0]
        other = self.create(request_key=str(uuid4()))
        self.ws.run_job(other)
        with self.assertRaises(WebError):
            self.ws.reply(other, {'request_key': str(uuid4()), 'question_id': question['id'], 'phase': 'planning', 'text': 'row total'})
        with self.assertRaises(WebError):
            self.ws.report(other)
        serialized = json.dumps(self.ws.detail(job), default=str)
        for private in ['source_snapshot', 'model_settings', 'upload_key', 'original_key', 'parquet_key', 'dsn']:
            self.assertNotIn('"' + private + '"', serialized)

    def test_profile_saved_without_model_and_recovered_in_another_process(self):
        import os
        import subprocess
        import sys
        self.ws.settings = None
        before = self.ws.state()['business']
        self.assertEqual(before['onboarding_status'], 'context_saved')
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn,
               'DECISION_ROOM_STORAGE': str(self.config.storage)}
        code = "from decision_room.config import Config; from decision_room.web.service import Workspace; import json; print(json.dumps(Workspace(Config.load()).state(),default=str))"
        saved = json.loads(subprocess.check_output([sys.executable, '-c', code], env=env))
        self.assertEqual(saved['business']['id'], str(before['id']))
        self.assertEqual(saved['business']['description'], before['description'])
        self.assertEqual(saved['analyses'], [])
        self.assertFalse(saved['configured'])

    def test_profile_retries_validation_and_concurrent_edit(self):
        from concurrent.futures import ThreadPoolExecutor
        update = {'business_id': str(self.business['id']), 'profile_revision': 1,
                  'name': 'Changed name', 'description': 'Same store with updated context'}
        def save(name):
            try:
                return self.ws.save_business({**update, 'name': name})
            except WebError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(save, ['First edit', 'Second edit']))
        self.assertEqual(sum(isinstance(x, dict) for x in outcomes), 1)
        self.assertIn(409, outcomes)
        current = self.ws.state()['business']
        repeated = self.ws.save_business({**update, 'name': current['name']})
        self.assertEqual(repeated['profile_revision'], 2)
        for invalid in [{'name': ''}, {'description': ''}, {'description': 'x' * 6001}]:
            with self.assertRaises(WebError):
                self.ws.save_business({**update, **invalid})

    def test_edit_keeps_original_upload_context_and_pending_job_snapshot(self):
        job = self.create()
        old = self.ws.row(job)
        current = self.ws.save_business({'business_id': str(self.business['id']), 'profile_revision': 1,
                                        'name': 'Renamed shop', 'description': 'New general context'})
        self.assertEqual(self.ws.upload(job)[1], self.csv)
        self.assertEqual(self.create(), job)  # A retry keeps the original revision.
        with self.assertRaises(WebError):
            self.create(request_key=str(uuid4()))  # A stale new form cannot start work.
        other = self.create(request_key=str(uuid4()), profile_revision=current['profile_revision'], goal='Different question')
        self.assertEqual(self.ws.row(other)['business_id'], old['business_id'])
        self.assertEqual(self.ws.row(other)['context'], 'New general context')
        self.assertEqual(self.ws.row(job)['context'], old['context'])
        self.ws.run_job(job)
        with connect(self.config) as db:
            source = db.execute('SELECT source_snapshot FROM agent_sessions WHERE id=%s',
                                (self.ws.row(job)['session_id'],)).fetchone()['source_snapshot']
        self.assertEqual(source['owner_context'], old['goal'] or 'Exploración general de la actividad disponible.')
        self.assertNotIn('New general context', source['owner_context'])

    def test_two_completed_questions_reuse_one_batch_but_keep_separate_sessions(self):
        first = self.complete()
        self.metadata.update(request_key=str(uuid4()), goal='A second question', title='Another report')
        second = self.complete()
        a, b = self.ws.row(first), self.ws.row(second)
        self.assertEqual(a['business_id'], b['business_id'])
        self.assertEqual(a['analysis_id'], b['analysis_id'])
        for key in ('session_id', 'research_id', 'review_id'):
            self.assertNotEqual(a[key], b[key])
        self.assertEqual(len(self.ws.listing()), 2)
        self.assertTrue(self.ws.detail(first)['publishable'])
        self.assertTrue(self.ws.detail(second)['publishable'])
        self.assertIn('30.00', self.ws.report(first))
        self.assertIn('30.00', self.ws.report(second))
        self.assertEqual(self.ws.dashboard()['selected_id'], second)
        self.assertEqual(self.ws.dashboard(first)['selected_id'], first)
        self.assertEqual(len(self.ws.dashboard()['reports']), 2)
        self.assertEqual(self.ws.state()['business']['description'], self.business['description'])
        self.assertEqual(self.ws.state()['business']['onboarding_status'], 'analysis_started')

    def test_identical_upload_with_new_filename_keeps_prior_report_publishable(self):
        first = self.complete()
        second = self.create(request_key=str(uuid4()), filename='same-sales-renamed.csv')
        self.ws.run_job(second)
        self.assertEqual(self.ws.row(first)['analysis_id'], self.ws.row(second)['analysis_id'])
        self.assertTrue(self.ws.detail(first)['publishable'])
        self.assertIn('30.00', self.ws.report(first))
        self.assertEqual(self.ws.upload(second)[0], 'same-sales-renamed.csv')

    def test_recovery_uses_exact_batch_not_latest_for_same_business(self):
        first = self.create()
        self.ws.run_job(first)
        from decision_room import service as ingestion
        original = ingestion.import_batch
        def import_then_crash(*args, **kwargs):
            original(*args, **kwargs)
            raise KeyboardInterrupt()
        self.csv = b'quantity,amount\n1,90\n'
        second = self.create(request_key=str(uuid4()), goal='New period')
        with patch.object(ingestion, 'import_batch', side_effect=import_then_crash), self.assertRaises(KeyboardInterrupt):
            self.ws.run_job(second)
        self.assertIsNone(self.ws.row(second)['analysis_id'])
        # A third, later batch is saved before the second job recovers.
        third = self.ws.create({**self.metadata, 'request_key': str(uuid4())}, 'sales.csv', b'quantity,amount\n1,500\n')['id']
        self.ws.run_job(third)
        resumed = Workspace(self.config, SETTINGS, WebModel)
        resumed.run_job(second)
        self.assertEqual(resumed.detail(second)['files'][0]['row_count'], 1)
        ids = {resumed.row(j)['analysis_id'] for j in (first, second, third)}
        self.assertEqual(len(ids), 3)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM analyses WHERE business_id=%s',
                                        (self.business['id'],)).fetchone()['n'], 3)

    def test_business_selection_is_explicit_scoped_and_worker_continues_old_job(self):
        first = self.create()
        other = self.ws.save_business({'request_key': str(uuid4()), 'expected_active_id': str(self.business['id']),
                                      'name': 'Test shop', 'description': 'A separate shop with the same name'})
        self.assertNotEqual(other['id'], self.business['id'])
        self.assertEqual(self.ws.listing(), [])
        self.assertIsNone(self.ws.dashboard(first)['report'])
        for operation in (self.ws.detail, self.ws.upload, self.ws.report, self.ws.retry):
            with self.subTest(operation=operation.__name__), self.assertRaises(WebError) as caught:
                operation(first)
            self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(WebError):
            self.ws.reply(first, {'request_key': str(uuid4()), 'text': 'answer'})
        with self.assertRaises(WebError):
            self.create()
        self.assertTrue(self.ws.work_once())
        self.assertEqual(self.ws.state()['business']['id'], other['id'])
        self.ws.select_business({'business_id': str(self.business['id'])})
        self.assertEqual(self.ws.detail(first)['status'], 'waiting')
        self.assertEqual(self.ws.upload(first)[1], self.csv)
        from decision_room.service import create_business
        unrelated = create_business(self.config, 'Private CLI case')
        with self.assertRaises(WebError):
            self.ws.select_business({'business_id': str(unrelated['id'])})

    def test_http_business_routes_and_every_job_route_respect_selection(self):
        job = self.create()
        client, _ = self.http()
        self.assertEqual(client.post('/api/business/select', json={'business_id': str(self.business['id'])}).status_code, 401)
        client.post('/api/login', json={'token': 'test-local-access'})
        body = {'request_key': str(uuid4()), 'expected_active_id': str(self.business['id']),
                'name': 'Another shop', 'description': 'A different business'}
        saved = client.post('/api/business', json=body)
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(client.post('/api/business', json=body).json(), saved.json())
        for suffix in ('', '/file', '/report'):
            self.assertEqual(client.get(f'/api/jobs/{job}{suffix}').status_code, 404)
        self.assertEqual(client.post(f'/api/jobs/{job}/retry', json={}).status_code, 404)
        self.assertEqual(client.post(f'/api/jobs/{job}/answers', json={'request_key': str(uuid4()), 'text': 'answer'}).status_code, 404)
        self.assertEqual(client.get('/api/workspace').json()['analyses'], [])
        self.assertEqual(client.post('/api/jobs', files={'metadata': (None, json.dumps(self.metadata)), 'file': ('sales.csv', self.csv)}).status_code, 409)
        restored = client.post('/api/business/select', json={'business_id': str(self.business['id'])})
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(client.get(f'/api/jobs/{job}/file').content, self.csv)
        self.assertEqual(len(client.get('/api/workspace').json()['analyses']), 1)

    def test_migrate_legacy_approved_report_keeps_evidence_and_checkpoints(self):
        job = self.complete()
        before = self.ws.row(job)
        html = self.ws.report(job)
        # Recreate the schema-7 boundary, keeping all analytical rows and files.
        with connect(self.config) as db, db.transaction():
            db.execute('DROP TABLE web_workspace')
            db.execute('DROP TABLE web_businesses')
            db.execute('ALTER TABLE web_jobs DROP COLUMN business_name, DROP COLUMN business_revision')
            db.execute('DELETE FROM schema_versions WHERE version=8')
        migrate(self.config)
        resumed = Workspace(self.config, SETTINGS, WebModel)
        after = resumed.row(job)
        for field in ('business_id', 'analysis_id', 'session_id', 'research_id', 'review_id', 'upload_key', 'request_sha256'):
            self.assertEqual(before[field], after[field])
        self.assertEqual(resumed.report(job), html)
        self.assertEqual(resumed.upload(job)[1], self.csv)
        self.assertTrue(resumed.detail(job)['publishable'])

    def test_second_server_does_not_migrate_under_running_app(self):
        from decision_room.web import __main__ as web_main
        _, server = self.http()
        with patch('sys.argv', ['decision_room.web', '--port', str(server.server_port)]), \
                patch.object(web_main.Config, 'load', return_value=self.config), \
                patch.object(web_main.ModelSettings, 'load', return_value=SETTINGS), \
                patch.object(web_main, 'migrate') as migrate_database, \
                self.assertRaises(SystemExit):
            web_main.main()
        migrate_database.assert_not_called()

    def test_new_answers_capture_memory_atomically_and_worker_recovers(self):
        from decision_room.memory import extraction
        job = self.create()
        self.ws.run_job(job)
        self.answer(job)
        # A failed queue insert also rolls back the planning answer; the web
        # reply remains durable and retryable, without a misleading memory save.
        with patch('decision_room.agent.service.capture_answer', side_effect=RuntimeError('queue unavailable')):
            self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'failed')
        self.assertIsNotNone(row['pending_answer'])
        with connect(self.config) as db:
            count = db.execute('SELECT count(*) AS n FROM agent_answers a JOIN agent_questions q ON q.id=a.question_id WHERE q.session_id=%s', (row['session_id'],)).fetchone()['n']
        self.assertEqual(count, 0)
        self.ws.retry(job)
        self.ws.run_job(job)
        self.assertEqual(self.ws.detail(job)['phase'], 'review')
        self.answer(job, 'Amount is row total.')
        with patch('decision_room.agent.review.capture_answer', side_effect=RuntimeError('queue unavailable')):
            self.ws.run_job(job)
        row = self.ws.row(job)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM agent_review_answers WHERE review_id=%s', (row['review_id'],)).fetchone()['n'], 0)
        self.ws.retry(job)
        self.ws.run_job(job)
        self.assertTrue(self.ws.detail(job)['publishable'])
        with connect(self.config) as db:
            sources = db.execute('SELECT * FROM memory_sources WHERE business_id=%s ORDER BY created_at', (self.business['id'],)).fetchall()
        self.assertEqual([s['payload']['kind'] for s in sources], ['profile', 'planning_answer', 'review_answer'])
        self.assertEqual([s['payload']['text'] for s in sources][1:], ['unit price', 'Amount is row total.'])
        self.assertTrue(all(s['payload']['default_scope'] == 'source' for s in sources[1:]))
        self.assertEqual(self.ws.state()['memory']['pending'], 3)
        restarted = Workspace(self.config, SETTINGS, WebModel)
        for _ in range(3):
            self.assertTrue(extraction.work_once(self.config, WebModel, SETTINGS))
        self.assertEqual(restarted.state()['memory']['pending'], 0)
        self.assertEqual(restarted.state()['memory']['applied'], 3)
        self.assertFalse(extraction.work_once(self.config, WebModel, SETTINGS))
        self.assertTrue(restarted.detail(job)['publishable'])

    def test_memory_retry_http_only_retries_active_business(self):
        with connect(self.config) as db:
            db.execute("UPDATE memory_sources SET status='failed' WHERE business_id=%s", (self.business['id'],))
        other = self.ws.save_business({'request_key': str(uuid4()), 'expected_active_id': str(self.business['id']),
                                      'name': 'Other shop', 'description': 'Separate context'})
        with connect(self.config) as db:
            db.execute("UPDATE memory_sources SET status='uncertain' WHERE business_id=%s", (other['id'],))
        client, _ = self.http()
        self.assertEqual(client.post('/api/memory/retry', json={}).status_code, 401)
        client.post('/api/login', json={'token': 'test-local-access'})
        self.assertEqual(client.post('/api/memory/retry', json={'business_id': str(self.business['id'])}).status_code, 409)
        self.assertEqual(client.post('/api/memory/retry', json={'business_id': str(other['id'])}).status_code, 202)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM memory_sources WHERE business_id=%s', (self.business['id'],)).fetchone()['status'], 'failed')
            self.assertEqual(db.execute('SELECT status FROM memory_sources WHERE business_id=%s', (other['id'],)).fetchone()['status'], 'pending')

    def test_memory_migration_preserves_old_answers_without_reinterpreting_them(self):
        job = self.complete()
        report = self.ws.report(job)
        with connect(self.config) as db, db.transaction():
            db.execute('DROP TABLE chat_answer_reviews,chat_retrievals,chat_calls,chat_turns,chat_conversations')
            db.execute('DROP TABLE memory_commands,memory_calls,memory_revisions,memory_facts,memory_heads,memory_sources')
            db.execute('DELETE FROM schema_versions WHERE version=9')
        migrate(self.config)
        with connect(self.config) as db:
            sources = db.execute('SELECT payload FROM memory_sources').fetchall()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]['payload']['kind'], 'profile')
        self.assertEqual(len(self.ws.detail(job)['answers']), 2)
        self.assertEqual(self.ws.report(job), report)


    def test_memory_correction_replans_web_job_and_preserves_old_report(self):
        from test_context_memory import MemoryAwareModel
        from test_memory import content
        from decision_room.memory import service as memory
        from decision_room.service import import_batch
        class Model(MemoryAwareModel):
            def __init__(self, settings):
                super().__init__()
                self.identity=asdict(settings)
        self.ws.model_factory=Model
        job=self.create()
        row=self.ws.row(job)
        data=import_batch(self.config,self.business['id'],[self.config.storage/row['upload_key']])
        source=str(data['files'][0]['source_id'])
        value=content('Amount is unit price. Quantity is units.',topic='amount_basis',kind='definition',scope='source',scope_id=source)
        fact=memory.change(self.config,self.business['id'],action='declare',request_key='base',content=value)
        self.ws.run_job(job)
        self.assertTrue(self.ws.detail(job)['publishable'])
        original=self.ws.row(job)
        memory.change(self.config,self.business['id'],action='correct',request_key='correct',fact_id=fact['fact_id'],expected_revision=1,
                      content={**value,'statement':'Amount is row total. Quantity is units.'})
        self.assertFalse(self.ws.detail(job)['publishable'])
        self.assertTrue(self.ws.detail(job)['context_stale'])
        with self.assertRaises(WebError):
            self.ws.report(job)
        self.ws.retry(job)
        self.assertEqual(self.ws.detail(job)['status'], 'queued')  # Keep the browser polling during replanning.
        self.ws.run_job(job)
        updated=self.ws.row(job)
        self.assertNotEqual(updated['session_id'],original['session_id'])
        self.assertNotEqual(updated['review_id'],original['review_id'])
        self.assertTrue(self.ws.detail(job)['publishable'])
        self.assertFalse(review.show(self.config,self.business['id'],original['review_id'])['publishable'])
        self.ws.sync(job)
        self.assertEqual(self.ws.row(job)['review_id'],updated['review_id'])
        with connect(self.config) as db:
            totals=db.execute('SELECT result FROM executions WHERE business_id=%s ORDER BY created_at',(self.business['id'],)).fetchall()
        self.assertEqual(totals[0]['result']['metrics']['total'],'80.0000')
        self.assertEqual(totals[-1]['result']['metrics']['total'],'30.00')

    def test_web_replan_recovers_successor_after_process_interruption(self):
        from decision_room.memory import service as memory
        from test_memory import content
        job=self.create()
        self.ws.run_job(job)
        original=self.ws.row(job)
        memory.change(self.config,self.business['id'],action='declare',request_key='new-context',content=content())
        self.ws.retry(job)
        update=self.ws.update
        def crash(job_id,**values):
            if values.get('session_id') and values['session_id']!=original['session_id']:
                raise KeyboardInterrupt
            return update(job_id,**values)
        with patch.object(self.ws,'update',side_effect=crash),self.assertRaises(KeyboardInterrupt):
            self.ws.run_job(job)
        recovered=Workspace(self.config,SETTINGS,WebModel)
        row=recovered.sync(job)
        self.assertNotEqual(row['session_id'],original['session_id'])
        self.assertIsNone(row['review_id'])
        recovered.run_job(job)
        self.assertEqual(recovered.detail(job)['status'],'waiting')
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM agent_sessions WHERE business_id=%s',(self.business['id'],)).fetchone()['n'],2)


if __name__ == '__main__':
    unittest.main()
