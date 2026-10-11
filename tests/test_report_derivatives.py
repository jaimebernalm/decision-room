"""PostgreSQL recovery, exact revision authority and immutable render receipts."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from uuid import uuid4

from decision_room.database import connect, migrate
from decision_room.engine import api, store as receipts
from decision_room.reports import derivative_store as ds, store
from tests import test_engine_admission as fixtures


class DerivativeTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create

    def document(self, raw=b'<h1>Units 5</h1>'):
        run, token = self.create()
        receipt = receipts.receive_document(self.config,run,token,request_key='final',html=raw)
        api._finish(self.config,self.business,run,'delivered')
        document = store.adopt(self.config,self.business,run)
        with connect(self.config) as db:
            job = db.execute('SELECT * FROM report_derivation_jobs WHERE document_id=%s',(document,)).fetchone()
        return run, document, receipt['revision_id'], job

    def inventory(self, job, text='Units 5'):
        return dict(text=text,source_sha256=job['raw_sha256'],text_sha256=ds.sha(text.encode()))

    def test_queue_adoption_and_migration_twice_preserve_raw_and_run(self):
        run, document, revision, job = self.document()
        with connect(self.config) as db:
            saved = ds.source(db,self.business,document,revision)
        for _ in range(2):
            migrate(self.config); store.adopt(self.config,self.business,run)
        with connect(self.config) as db:
            self.assertEqual(ds.source(db,self.business,document,revision), saved)
            self.assertEqual(db.execute('SELECT count(*) AS n FROM report_derivation_jobs WHERE document_id=%s',(document,)).fetchone()['n'],1)
            self.assertEqual(db.execute('SELECT status FROM engine_runs WHERE id=%s',(run,)).fetchone()['status'],'delivered')
            self.assertIsNone(ds.result(db,self.business,document,revision))
            self.assertEqual(db.execute('SELECT status FROM report_derivation_jobs WHERE id=%s',(job['id'],)).fetchone()['status'],'pending')

    def test_foreign_business_document_revision_and_hash_rejected(self):
        _, document, revision, job = self.document()
        _, other, other_revision, _ = self.document()
        for business, doc, rev in [(uuid4(),document,revision),(self.business,other,revision),(self.business,document,other_revision)]:
            with connect(self.config) as db, db.transaction():
                self.assertIsNone(ds.result(db,business,doc,rev))
                with self.assertRaises(ValueError): ds.source(db,business,doc,rev)
        with connect(self.config) as db, db.transaction():
            with self.assertRaises(ValueError): ds.set_presentation(db,self.business,document,revision,'0'*64,'allowed',None)

    def test_assessment_idempotent_but_never_rewritten(self):
        _, document, revision, job = self.document()
        for _ in range(2):
            with connect(self.config) as db, db.transaction():
                ds.set_presentation(db,self.business,document,revision,job['raw_sha256'],'allowed',None)
        with self.assertRaises(ValueError):
            with connect(self.config) as db, db.transaction():
                ds.set_presentation(db,self.business,document,revision,job['raw_sha256'],'blocked','Blocked')
        with connect(self.config) as db:
            row=ds.source(db,self.business,document,revision)
            self.assertEqual(row['presentation_state'],'allowed')
            self.assertEqual(row['derived_version'],0)
            for change in ["raw_sha256='bad'", "canonical_text='invented'", "presentation_state='blocked'", "verification_state='verified'"]:
                with self.assertRaises(Exception):
                    db.execute('UPDATE report_document_revisions SET '+change+' WHERE id=%s',(revision,))

    def test_two_workers_and_recovery_retain_exact_identity(self):
        _, document, revision, job = self.document()
        started, release = threading.Event(), threading.Event()
        def first():
            with ds.claim(self.config,job['id']) as claimed:
                started.set(); release.wait(5)
                return claimed
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=pool.submit(first)
            self.assertTrue(started.wait(5))
            with ds.claim(self.config,job['id']) as second: self.assertIsNone(second)
            release.set(); old=future.result(5)
        # Simulate a controller dying before publication: running work can be
        # claimed under the same job/container identity with a new fence.
        with ds.claim(self.config,job['id']) as current:
            self.assertEqual(current['attempts'],2)
            self.assertNotEqual(current['claim_id'],old['claim_id'])
            with self.assertRaises(ValueError):
                with connect(self.config) as db, db.transaction(): ds.publish(db,old,status='ready',inventory=self.inventory(old))
            with connect(self.config) as db, db.transaction():
                ds.publish(db,current,status='ready',inventory=self.inventory(current))
        with connect(self.config) as db:
            saved=ds.result(db,self.business,document,revision)
            self.assertEqual(saved['canonical_text'],'Units 5')
            self.assertEqual(ds.source(db,self.business,document,revision)['derive_status'],'ready')
            for table in ('report_derivatives','report_presentation_checks'):
                if table=='report_presentation_checks': continue
                with self.assertRaises(Exception): db.execute('DELETE FROM '+table+' WHERE revision_id=%s',(revision,))

    def test_failed_render_preserves_completion_without_partial_text(self):
        run, document, revision, job = self.document()
        with ds.claim(self.config,job['id']) as claimed:
            with connect(self.config) as db, db.transaction():
                with self.assertRaises(ValueError): ds.publish(db,claimed,status='failed',inventory=self.inventory(claimed),issue='Unavailable')
                ds.publish(db,claimed,status='failed',issue='No podemos preparar la vista de esta revisión.')
        with connect(self.config) as db:
            result=ds.result(db,self.business,document,revision)
            self.assertIsNone(result['canonical_text'])
            self.assertEqual(result['status'],'failed')
            self.assertEqual(db.execute('SELECT status FROM engine_runs WHERE id=%s',(run,)).fetchone()['status'],'delivered')

    def test_publication_is_atomic_with_source_and_projection(self):
        _, document, revision, job = self.document()
        with ds.claim(self.config,job['id']) as claimed:
            with self.assertRaises(RuntimeError):
                with connect(self.config) as db, db.transaction():
                    ds.publish(db,claimed,status='ready',inventory=self.inventory(claimed))
                    raise RuntimeError('death before commit')
            with connect(self.config) as db:
                self.assertIsNone(ds.result(db,self.business,document,revision))
                self.assertEqual(ds.source(db,self.business,document,revision)['derive_status'],'pending')
                self.assertEqual(db.execute('SELECT status FROM report_derivation_jobs WHERE id=%s',(job['id'],)).fetchone()['status'],'running')
            with connect(self.config) as db, db.transaction():
                ds.publish(db,claimed,status='ready',inventory=self.inventory(claimed))
