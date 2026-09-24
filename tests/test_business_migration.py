"""Transactional transition from schema 7, using isolated databases and fixtures."""
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from psycopg import sql
from psycopg.errors import DivisionByZero
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.web.service import Workspace


SCHEMA = Path(__file__).resolve().parents[1] / 'decision_room/schema.sql'


class BusinessMigrationTests(unittest.TestCase):
    def setUp(self):
        self.base = Config.load()
        self.name = 'dr_business_migration_' + uuid4().hex
        with connect(self.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.name)))
        self.addCleanup(self.drop_database)
        self.storage = tempfile.TemporaryDirectory(prefix='dr-migration-test-')
        self.addCleanup(self.storage.cleanup)
        self.config = replace(self.base, dsn=make_conninfo(self.base.dsn, dbname=self.name), storage=Path(self.storage.name))
        self.schema = SCHEMA.read_text()

    def drop_database(self):
        with connect(self.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(self.name)))

    def old_schema(self):
        with connect(self.config) as db:
            db.execute(self.schema.split('-- A local owner')[0])

    def legacy_job(self):
        business, job, request = uuid4(), uuid4(), uuid4()
        content = b'date,amount\n2026-01-01,12\n'
        name, context, goal, title, filename = 'Same name', 'Historical context', 'Old question', 'Old analysis', 'sales.csv'
        signature = hashlib.sha256(json.dumps([name, context, goal, title, filename], ensure_ascii=False).encode() + content).hexdigest()
        key = f'{business}/web/{job}/{filename}'
        path = self.config.storage / key
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        with connect(self.config) as db:
            db.execute('INSERT INTO businesses(id,name,description) VALUES (%s,%s,%s)', (business, name, context))
            db.execute('''INSERT INTO web_jobs(id,request_key,request_sha256,business_id,title,context,goal,
                filename,upload_key,byte_count,model_settings,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')''',
                       (job, request, signature, business, title, context, goal, filename, key, len(content), Jsonb({})))
        return business, job, content

    def test_empty_migration_and_repeat(self):
        migrate(self.config)
        migrate(self.config)
        self.assertEqual(Workspace(self.config).state()['businesses'], [])
        self.assertIsNone(Workspace(self.config).state()['business'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM schema_versions WHERE version=8').fetchone()['n'], 1)

    def test_single_legacy_business_is_selected_without_enrolling_cli_cases(self):
        self.old_schema()
        business, job, content = self.legacy_job()
        with connect(self.config) as db:
            db.execute('INSERT INTO businesses(id,name) VALUES (%s,%s)', (uuid4(), 'CLI-only example'))
        migrate(self.config)
        ws = Workspace(self.config)
        self.assertEqual(ws.state()['business']['id'], business)
        self.assertEqual(len(ws.state()['businesses']), 1)
        self.assertEqual(ws.upload(job), ('sales.csv', content))
        original = ws.row(job)
        migrate(self.config)
        self.assertEqual(ws.row(job), original)

    def test_same_named_legacy_businesses_require_selection_and_keep_files(self):
        self.old_schema()
        a, aj, ac = self.legacy_job()
        b, bj, bc = self.legacy_job()
        migrate(self.config)
        ws = Workspace(self.config)
        self.assertIsNone(ws.state()['business'])
        self.assertEqual(ws.listing(), [])
        self.assertEqual(len(ws.state()['businesses']), 2)
        ws.select_business({'business_id': str(a)})
        self.assertEqual(ws.upload(aj)[1], ac)
        migrate(self.config)
        self.assertEqual(ws.state()['business']['id'], a)
        ws.select_business({'business_id': str(b)})
        self.assertEqual(ws.upload(bj)[1], bc)
        self.assertEqual([j['id'] for j in ws.listing()], [bj])

    def test_failure_rolls_back_schema_and_backfill_then_retry_succeeds(self):
        self.old_schema()
        business, job, content = self.legacy_job()
        with patch('decision_room.database.Path.read_text', return_value=self.schema + '\nSELECT 1 / 0;'):
            with self.assertRaises(DivisionByZero):
                migrate(self.config)
        with connect(self.config) as db:
            self.assertIsNone(db.execute("SELECT to_regclass('web_businesses') AS table_name").fetchone()['table_name'])
            self.assertFalse(db.execute('SELECT 1 FROM schema_versions WHERE version=8').fetchone())
            self.assertIsNone(db.execute("SELECT to_regclass('memory_sources') AS table_name").fetchone()['table_name'])
            self.assertEqual(db.execute('SELECT business_id FROM web_jobs WHERE id=%s', (job,)).fetchone()['business_id'], business)
        migrate(self.config)
        self.assertEqual(Workspace(self.config).upload(job)[1], content)

    def test_schema_nine_preserves_profile_as_pending_original_without_old_answers(self):
        self.old_schema()
        business, job, content = self.legacy_job()
        schema_eight = self.schema.split('-- Durable original text')[0]
        with connect(self.config) as db:
            db.execute(schema_eight)
        migrate(self.config)
        migrate(self.config)
        with connect(self.config) as db:
            sources = db.execute('SELECT * FROM memory_sources').fetchall()
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]['business_id'], business)
            self.assertEqual(sources[0]['status'], 'pending')
            self.assertEqual(sources[0]['payload']['text'], 'Historical context')
            self.assertEqual(db.execute('SELECT count(*) AS n FROM memory_facts').fetchone()['n'], 0)
        self.assertEqual(Workspace(self.config).upload(job)[1], content)

    def test_context_migration_failure_rolls_back_and_retry_preserves_legacy(self):
        self.old_schema()
        self.legacy_job()
        with connect(self.config) as db:
            db.execute(self.schema.split('-- Shared, immutable starting context')[0])
        with patch('decision_room.database.Path.read_text', return_value=self.schema + '\nSELECT 1/0;'), self.assertRaises(DivisionByZero):
            migrate(self.config)
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM schema_versions WHERE version=10').fetchone())
            self.assertIsNone(db.execute("SELECT to_regclass('context_manifests') AS t").fetchone()['t'])
        migrate(self.config)
        migrate(self.config)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM schema_versions WHERE version=10').fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT count(*) n FROM web_jobs').fetchone()['n'],1)

    def test_semantic_migration_rolls_back_extension_and_retry_is_idempotent(self):
        with connect(self.config) as db:
            db.execute(self.schema.split('-- Derived semantic cache.')[0])
        with patch('decision_room.database.Path.read_text', return_value=self.schema + '\nSELECT 1/0;'), self.assertRaises(DivisionByZero):
            migrate(self.config)
        with connect(self.config) as db:
            self.assertIsNone(db.execute("SELECT to_regclass('semantic_chunks') AS t").fetchone()['t'])
            self.assertFalse(db.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone())
            self.assertFalse(db.execute('SELECT 1 FROM schema_versions WHERE version=11').fetchone())
        migrate(self.config)
        migrate(self.config)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM schema_versions WHERE version=11').fetchone()['n'], 1)
            self.assertTrue(db.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone())

    def test_conversation_migration_rolls_back_and_preserves_legacy_jobs(self):
        self.old_schema()
        business, job, original = self.legacy_job()
        with connect(self.config) as db:
            db.execute(self.schema.split('-- Durable business conversations.')[0])
        with patch('decision_room.database.Path.read_text', return_value=self.schema + '\nSELECT 1/0;'), self.assertRaises(DivisionByZero):
            migrate(self.config)
        with connect(self.config) as db:
            self.assertIsNone(db.execute("SELECT to_regclass('chat_turns') AS t").fetchone()['t'])
            self.assertFalse(db.execute('SELECT 1 FROM schema_versions WHERE version=12').fetchone())
        migrate(self.config)
        migrate(self.config)
        self.assertEqual(Workspace(self.config).upload(job), ('sales.csv', original))
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM schema_versions WHERE version=12').fetchone()['n'], 1)
            self.assertEqual(db.execute('SELECT origin FROM web_jobs WHERE id=%s', (job,)).fetchone()['origin'], 'upload')
