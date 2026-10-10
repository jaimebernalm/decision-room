"""Immutable creation paths, with fake agents and an isolated PostgreSQL DB."""
import io
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.engine import admission
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
            self.assertEqual(settings['prompt_sha256'], admission.sha(settings['prompt'].encode()))
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
