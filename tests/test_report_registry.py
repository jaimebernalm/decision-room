"""Real PostgreSQL registry identity, raw provenance and immutable history."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from uuid import uuid4

from decision_room.database import connect, migrate
from decision_room.engine import api, store as receipts
from decision_room.reports import store
from tests import test_engine_admission as fixtures


class RegistryTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create

    def test_all_raw_revisions_adopt_exact_identity_concurrently(self):
        run, token = self.create()
        first = receipts.receive_document(self.config, run, token, request_key='one', html=b'\xff<h1>cut')
        second = receipts.receive_document(self.config, run, token, request_key='two', html=b'<script>private</script>')
        api._finish(self.config, self.business, run, 'delivered')
        with ThreadPoolExecutor(max_workers=3) as pool:
            ids = list(pool.map(lambda _: store.adopt(self.config,self.business,run), range(3)))
        self.assertEqual(set(map(str,ids)), {first['document_id']})
        with connect(self.config) as db:
            document = db.execute('SELECT * FROM report_documents WHERE id=%s', (ids[0],)).fetchone()
            rows = db.execute('SELECT * FROM report_document_revisions WHERE document_id=%s ORDER BY ordinal', (ids[0],)).fetchall()
            self.assertEqual(str(document['current_revision_id']), second['revision_id'])
            self.assertEqual([str(r['id']) for r in rows], [first['revision_id'], second['revision_id']])
            self.assertEqual([r['raw_sha256'] for r in rows], [first['raw_sha256'],second['raw_sha256']])
            self.assertTrue(all(r['canonical_text'] is None and r['canonical_sha256'] is None and r['derived_version']==0 for r in rows))
            self.assertTrue(all(r['presentation_state']=='not_evaluated' and r['verification_state']=='not_requested' for r in rows))
            for table, column, value in [('report_document_revisions','raw_sha256','0'*64), ('engine_document_revisions','raw',b'changed')]:
                with self.assertRaises(Exception):
                    db.execute(f'UPDATE {table} SET {column}=%s WHERE id=%s', (value,second['revision_id']))
            with self.assertRaises(Exception):
                db.execute('DELETE FROM report_document_revisions WHERE id=%s',(second['revision_id'],))
        migrate(self.config); migrate(self.config)
        self.assertEqual(receipts.read_document(self.config,self.business,run)['raw'],b'<script>private</script>')

    def test_incomplete_empty_and_foreign_receipts_cannot_be_current(self):
        for state,raw in [('failed',b'<h1>cut'),('aborted',b'partial'),('running',b''),('delivered',b'')]:
            run, token = self.create()
            receipt=receipts.receive_document(self.config,run,token,request_key='one',html=raw)
            if state!='running': api._finish(self.config,self.business,run,state)
            self.assertIsNone(store.adopt(self.config,uuid4(),run))
            document=store.adopt(self.config,self.business,run)
            self.assertEqual(str(document),receipt['document_id'])
            with connect(self.config) as db:
                self.assertIsNone(db.execute('SELECT current_revision_id FROM report_documents WHERE id=%s',(document,)).fetchone()['current_revision_id'])

    def test_baseline_is_immutable_on_replay_and_never_retrofitted(self):
        run, _ = self.create(request_key='stable')
        with connect(self.config) as db:
            saved=db.execute('SELECT * FROM engine_report_contexts WHERE run_id=%s',(run,)).fetchone()
        self.assertEqual(self.create(request_key='stable'),(run,None))
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT * FROM engine_report_contexts WHERE run_id=%s',(run,)).fetchone(),saved)
            with self.assertRaises(Exception): db.execute("UPDATE engine_report_contexts SET memories='[]' WHERE run_id=%s",(run,))
            with self.assertRaises(Exception): db.execute('DELETE FROM engine_report_contexts WHERE run_id=%s',(run,))

    def test_upgrade_f0_receipt_keeps_bytes_and_stays_non_current(self):
        import subprocess
        from dataclasses import replace
        from unittest.mock import patch
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        from decision_room.service import create_business, import_batch
        name='dr_f1_upgrade_'+uuid4().hex
        with connect(self.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            config=replace(self.config,dsn=make_conninfo(self.base.dsn,dbname=name))
            old=subprocess.run(['git','show','60360df:decision_room/schema.sql'],check=True,capture_output=True).stdout.decode()
            with connect(config) as db:
                db.execute(old)
                # The current writer records brief provenance (migration 35, additive and idempotent).
                db.execute("ALTER TABLE engine_runs ADD COLUMN IF NOT EXISTS brief jsonb NOT NULL DEFAULT '{}'")
            business=create_business(config,'Upgrade fixture')['id']
            csv=self.root/'upgrade.csv'; csv.write_text('quantity\n4\n')
            # Emulate the pre-F1 writer while building old-schema fixtures.
            with patch('decision_room.reports.store.invalidate'):
                imported=import_batch(config,business,[csv])
            with patch('decision_room.reports.store.capture'):
                run,token=receipts.admission.create_run(config,business,imported['analysis']['id'],
                    table_ids=[imported['files'][0]['table_id']],owner_context='Fixture',request_key='old',model='test')
            receipt=receipts.receive_document(config,run,token,request_key='old',html=b'\xffF0 receipt')
            api._finish(config,business,run,'delivered')
            migrate(config); migrate(config)
            document=store.adopt(config,business,run)
            self.assertEqual(str(document),receipt['document_id'])
            self.assertEqual(receipts.read_document(config,business,run)['raw'],b'\xffF0 receipt')
            with connect(config) as db:
                row=db.execute('SELECT * FROM report_documents WHERE id=%s',(document,)).fetchone()
                self.assertIsNone(row['current_revision_id']); self.assertEqual(row['stale_reason'],'missing_context')
        finally:
            with connect(self.base) as db:
                db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
