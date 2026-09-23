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
        self.ws = Workspace(self.config, SETTINGS, WebModel)
        self.metadata = {'request_key': str(uuid4()), 'business': 'Test shop', 'context': 'unit price, selected sales only',
                         'goal': 'Understand sales', 'title': 'Web test'}
        self.csv = b'quantity,amount\n2,10\n3,20\n'

    def create(self, **changes):
        return self.ws.create({**self.metadata, **changes}, 'sales.csv', self.csv)['id']

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
        row = self.ws.row(job)
        review.hold(self.config, row['business_id'], row['review_id'], reason='Controlled hold for test.')
        self.assertFalse(self.ws.detail(job)['publishable'])
        self.assertEqual(self.ws.detail(job)['status'], 'blocked')
        self.assertEqual(next(j for j in self.ws.listing() if str(j['id']) == job)['status'], 'blocked')
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
        self.assertEqual(client.post('/api/login', json={'token': 'bad'}).status_code, 401)
        self.assertEqual(client.post('/api/login', json={'token': 'test-local-access'}, headers={'Origin': 'https://outside.test'}).status_code, 403)
        response = client.post('/api/login', json={'token': 'test-local-access'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=Strict', response.headers['set-cookie'])
        self.assertEqual(client.get('/api/workspace').status_code, 200)
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


if __name__ == '__main__':
    unittest.main()
