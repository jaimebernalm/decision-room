"""Immutable creation paths, with fake agents and an isolated PostgreSQL DB."""
import io
import unittest
import threading
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.engine import admission, api, store
from types import SimpleNamespace
from tests.engine_fakes import FakeRuntime, FakeClient, FakeTunnel
from decision_room.service import import_batch
from decision_room.web.service import Workspace, WebError
from tests import test_web as fixtures


class EngineJobTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.WebTests.tearDownClass.__func__)
    setUp = fixtures.WebTests.setUp
    create = fixtures.WebTests.create

    def pinned(self):
        p = patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': 'sha256:'+'a'*64})
        p.start(); self.addCleanup(p.stop)

    def test_question_opt_in_is_versioned_immutable_and_not_a_legacy_option(self):
        self.pinned()
        job = self.create(engine_kind='opencode', engine_questions=True)
        row = self.ws.row(job)
        self.assertTrue(row['engine_config']['profile']['questions'])
        self.assertEqual(row['engine_config']['profile']['version'], 'html-v1-questions-1')
        with self.assertRaises(WebError):
            self.create(engine_kind='opencode', engine_questions=False)
        with self.assertRaises(WebError):
            self.ws.create({**self.metadata, 'request_key': str(uuid4()), 'engine_questions': True}, 'sales.csv', self.csv)

    def test_single_batch_dataset_selection_and_retry_after_default_change(self):
        self.pinned()
        single = self.create(engine_kind='opencode')
        self.assertEqual(self.ws.row(single)['engine_kind'], 'opencode')
        staged = self.ws.stage_upload('units.csv', io.BytesIO(self.csv), len(self.csv))
        batch = self.ws.create_batch({**self.metadata, 'request_key': str(uuid4()), 'files': [staged['id']], 'engine_kind': 'opencode'})['id']
        csv = Path(self.temp.name)/'prepared.csv'; csv.write_bytes(self.csv)
        dataset = import_batch(self.config, self.business['id'], [csv])['analysis']['id']
        data = {**self.metadata, 'request_key': str(uuid4()), 'analysis_id': str(dataset), 'engine_kind': 'opencode'}
        prepared = self.ws.create_from_dataset(data)['id']
        for job in (single, batch, prepared):
            row = self.ws.row(job); settings = row['engine_config']
            self.assertEqual(settings['profile']['model'], 'gpt-6-luna')
            self.assertEqual(settings['profile']['variant'], 'low')
            self.assertEqual(settings['owner_sha256'], admission.sha(admission.canonical([settings['owner_context'], settings['goal']])))
            self.assertNotIn('prompt', settings)  # The brief is generated at run creation from prepared data.
            self.assertEqual(settings['input_request_sha256'], row['request_sha256'])
            self.assertIsNone(row['report_document_id'])
            self.assertIsNone(row['engine_run_id'])
        # Defaults and image changes cannot change a replay's captured settings.
        self.ws.config = replace(self.config, report_engine='legacy', engine_calls=2)
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': ''}):
            self.assertEqual(self.ws.create_from_dataset({k:v for k,v in data.items() if k!='engine_kind'})['id'], prepared)
        with self.assertRaises(WebError):
            self.ws.create_from_dataset({**data, 'engine_kind': 'legacy'})
        with connect(self.config) as db:
            with self.assertRaises(Exception): db.execute("UPDATE web_jobs SET engine_kind='legacy' WHERE id=%s", (single,))
            with self.assertRaises(Exception): db.execute("UPDATE web_jobs SET engine_config='{}' WHERE id=%s", (single,))

    def test_legacy_default_and_explicit_engine_without_local_model(self):
        legacy = self.create()
        self.assertEqual(self.ws.row(legacy)['engine_kind'], 'legacy')
        self.pinned()
        self.ws.config = replace(self.config, report_engine='opencode')
        self.assertEqual(self.create(), legacy)
        self.ws.settings = None
        engine = self.create(request_key=str(uuid4()))
        self.assertEqual(self.ws.row(engine)['engine_kind'], 'opencode')
        with self.assertRaises(WebError): self.create(request_key=str(uuid4()), engine_kind='other')
        with self.assertRaises(WebError): self.create(request_key=str(uuid4()), engine_kind='legacy')

    def fake_runtime(self):
        self.pinned()
        FakeRuntime.sessions = {}; FakeRuntime.mode = 'deliver'; FakeClient.config = self.config
        FakeRuntime.payload = b'<!doctype html><h1>Resultado</h1><p>5 unidades.</p>'
        for target, value in [('Runtime', FakeRuntime), ('DockerBackend', lambda: object()), ('JobTunnel', FakeTunnel),
                              ('_service', lambda *a: SimpleNamespace(origin='http://127.0.0.1:1'))]:
            p = patch.object(api, target, value); p.start(); self.addCleanup(p.stop)
        def forbidden(*args, **kwargs): raise AssertionError('Legacy report path entered')
        self.ws.model_factory = forbidden
        for target in ('memory_extraction.prepare', 'recover_executions', 'planning.start', 'research.start', 'review.start'):
            p = patch('decision_room.web.service.'+target, side_effect=forbidden); p.start(); self.addCleanup(p.stop)

    def test_run_dispatches_before_legacy_preludio_and_keeps_ids_separate(self):
        self.fake_runtime()
        job = self.create(engine_kind='opencode')
        self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'completed', row['issue'])
        self.assertEqual(row['phase'], 'engine')
        self.assertIsNotNone(row['engine_run_id'])
        self.assertTrue(all(row[k] is None for k in ('session_id', 'research_id', 'review_id')))
        receipt = store.read_document(self.config, row['business_id'], row['engine_run_id'])
        self.assertEqual(str(row['report_document_id']), receipt['document_id'])
        self.assertEqual(receipt['delivery_via'], 'file')
        self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['engine_run_id'], row['engine_run_id'])
        self.assertEqual(sum(m['info']['role']=='user' for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages']), 1)
        with self.assertRaises(WebError): self.ws.retry(job)

    def test_restart_after_run_creation_and_after_delivery_never_replays_prompt(self):
        self.fake_runtime()
        for boundary in ('link', 'finish'):
            job = self.create(request_key=str(uuid4()), engine_kind='opencode')
            if boundary == 'link':
                original = self.ws.update
                def crash(ident, **values):
                    if values.get('engine_run_id'): raise SystemExit('Simulated process death')
                    return original(ident, **values)
                p = patch.object(self.ws, 'update', side_effect=crash)
            else:
                p = patch.object(api, '_finish', side_effect=SystemExit('Simulated process death'))
            with p, self.assertRaises(SystemExit): self.ws.run_job(job)
            self.ws.run_job(job)
            row = self.ws.row(job)
            self.assertEqual(row['status'], 'completed', row['issue'])
            self.assertEqual(sum(m['info']['role']=='user' for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages']), 1)
            with connect(self.config) as db:
                self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_runs WHERE business_id=%s AND request_key=%s',
                                            (row['business_id'], 'web:'+job)).fetchone()['n'], 1)

    def test_two_workers_and_empty_receipt_has_independent_execution_state(self):
        self.fake_runtime(); FakeRuntime.payload = b''
        job = self.create(engine_kind='opencode')
        errors = []
        def run():
            try: self.ws.run_job(job)
            except Exception as error: errors.append(error)
        workers = [threading.Thread(target=run) for _ in range(2)]
        for w in workers: w.start()
        for w in workers: w.join(10); self.assertFalse(w.is_alive())
        self.assertFalse(errors, errors)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(store.read_document(self.config, row['business_id'], row['engine_run_id'])['raw'], b'')

    def test_unknown_usage_is_preserved_and_web_never_enqueues_a_retry(self):
        import secrets
        from decision_room.engine.export import folder, snapshot
        self.fake_runtime()
        job = self.create(engine_kind='opencode')
        self.ws.ingest_job(self.ws.row(job)); row = self.ws.row(job); settings = row['engine_config']
        run, token = api.prepare_report(self.config, row['business_id'], row['analysis_id'],
                                        request_key='web:'+job, owner_context=settings['owner_context'],
                                        engine_config=settings['profile'], limits=settings['limits'])
        self.ws.update(job, engine_run_id=run)
        store.receive_document(self.config, run, token, request_key='partial', html=b'<h1>Partial')
        call = admission.begin_call(self.config, run, token, 'uncertain')
        admission.reserve(self.config, run, token, call, 100, 20)
        api._save(folder(self.config, row['business_id'], run)/'control.json',
                  {'run_id': str(run), 'instance_id': str(uuid4()), 'image': settings['profile']['image_id'],
                   'password': secrets.token_urlsafe(32), 'token': token, 'model': settings['profile']['model'], 'initialized': True})
        self.ws.run_job(job)
        state = admission.inspect_run(self.config, row['business_id'], run)
        self.assertEqual(state['status'], 'aborted')
        self.assertEqual(state['model_calls'][0]['state'], 'uncertain')
        self.assertEqual((state['charged_input'], state['charged_output']), (100, 20))
        self.assertEqual(store.read_document(self.config, row['business_id'], run)['raw'], b'<h1>Partial')
        self.assertTrue(snapshot(self.config, row['business_id'], run)['usage']['incomplete'])
        self.assertEqual(self.ws.row(job)['status'], 'blocked')
        self.assertFalse(self.ws.detail(job)['can_retry'])
        with self.assertRaises(WebError): self.ws.retry(job)
        self.ws.run_job(job)
        self.assertEqual(len(admission.inspect_run(self.config, row['business_id'], run)['model_calls']), 1)


    def test_registry_delete_restore_preserves_history_and_retirement(self):
        from decision_room.web.report_access import read_job
        from decision_room.reports.reading import metadata
        from decision_room.memory import service as memory
        from tests.test_memory import content
        self.fake_runtime(); job=self.create(engine_kind='opencode'); self.ws.run_job(job)
        row=self.ws.row(job); document=row['report_document_id']
        with read_job(self.ws,job) as (db,_,pair):
            self.assertTrue(metadata(db,*pair)['is_current'])
        body={'business_id':str(row['business_id'])}
        self.ws.delete_report(job,body)
        with self.assertRaises(WebError):
            with read_job(self.ws,job): pass
        with read_job(self.ws,job,deleted=True) as (db,_,pair):
            self.assertTrue(metadata(db,*pair)['deleted'])
        memory.change(self.config,row['business_id'],action='declare',request_key=uuid4().hex,content=content())
        self.ws.delete_report(job,body,restore=True)
        with read_job(self.ws,job) as (db,_,pair):
            value=metadata(db,*pair)
            self.assertFalse(value['is_current']); self.assertEqual(value['state'],'withdrawn')
        self.assertEqual(self.ws.row(job)['report_document_id'],document)
        self.assertIsNotNone(store.read_document(self.config,row['business_id'],row['engine_run_id']))


class ChatEngineCreationTests(unittest.TestCase):
    # Independent fixtures: no report engine or real model is invoked by chat.
    from tests import test_conversations as chat_fixtures
    setUpClass = classmethod(chat_fixtures.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(chat_fixtures.ConversationTests.tearDownClass.__func__)
    setUp = chat_fixtures.ConversationTests.setUp
    batch = chat_fixtures.ConversationTests.batch
    chat = chat_fixtures.ConversationTests.chat
    send = chat_fixtures.ConversationTests.send

    def test_chat_investigation_snapshots_default_engine(self):
        from decision_room.conversations import Conversations
        self.ws.config = replace(self.config, report_engine='opencode')
        self.chats = Conversations(self.ws.scoped(self.b))
        dataset = self.batch()
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': 'sha256:'+'b'*64}):
            turn = self.send(self.chat(dataset), 'Calculate the total')
        self.assertIsNotNone(turn['job_id'], turn)
        row = self.ws.row(turn['job_id'])
        self.assertEqual(row['engine_kind'], 'opencode')
        self.assertEqual(row['origin'], 'chat')
        self.assertEqual(row['engine_config']['profile']['image_id'], 'sha256:'+'b'*64)

    def test_completed_chat_engine_delivery_is_metadata_only_and_later_stale(self):
        from decision_room.conversations import Conversations
        from decision_room.memory import service as memory
        from tests.test_memory import content
        self.ws.config=replace(self.config,report_engine='opencode')
        self.chats=Conversations(self.ws.scoped(self.b))
        dataset=self.batch(); chat=self.chat(dataset)
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID':'sha256:'+'b'*64}):
            turn=self.send(chat,'Calculate the total',entry_intent='analysis')
        self.pinned=EngineJobTests.pinned.__get__(self)
        EngineJobTests.fake_runtime(self)
        self.ws.run_job(turn['job_id'])
        self.chats.run(turn['id'])
        delivered=self.chats.detail(chat)['turns'][-1]
        self.assertEqual(delivered['status'],'completed')
        self.assertEqual(delivered['response']['kind'],'report_status')
        self.assertNotIn('report_id',delivered['response'])
        self.assertNotIn('claims',delivered['response'])
        self.assertEqual(self.ws.listing()[0]['report_document_id'],self.ws.row(turn['job_id'])['report_document_id'])
        self.assertEqual(self.chats.report(chat,turn['id'],structured=True)['origin'],'engine_html')
        with self.assertRaises(WebError): self.chats.report(chat,turn['id'],structured=True,purpose='pdf')
        memory.change(self.config,self.b,action='declare',request_key=uuid4().hex,content=content())
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'],'stale')
