"""Stray raster work cannot change an already published native revision."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.reports import derivative_store as ds, derive_policy, reading
from tests import test_native_home as home_fixtures


class NativeRasterBoundaryTests(unittest.TestCase):
    from tests import test_engine_jobs as product
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime
    deliver = home_fixtures.NativeHomeTests.deliver

    def test_stray_claim_and_direct_writers_preserve_native_revision(self):
        entry = self.deliver()
        business, document = entry['business_id'], entry['report_document_id']
        revision = entry['engine_report']['revision_id']
        renderer = 'v1-container-raster-2:sha256:' + 'a' * 64
        with connect(self.config) as db:
            before = ds.source(db, business, document, revision)
            job = dict(id=uuid4(), business_id=business, document_id=document, revision_id=revision,
                       raw_sha256=before['raw_sha256'], policy_version=derive_policy.POLICY_VERSION,
                       renderer_version=renderer, claim_id=uuid4())
            # Reproduce a queue entry left by a former worker, without executing HTML.
            db.execute('''INSERT INTO report_derivation_jobs
                (id,business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                tuple(job[k] for k in ('id', 'business_id', 'document_id', 'revision_id',
                                      'raw_sha256', 'policy_version', 'renderer_version')))
        with patch.object(derive_policy, 'renderer_version', return_value=renderer):
            with ds.claim(self.config, job['id']) as claimed:
                self.assertIsNone(claimed)
            for operation in (
                lambda db: ds.set_presentation(db, business, document, revision,
                                               job['raw_sha256'], 'allowed', None),
                lambda db: ds.publish(db, job, status='failed', issue='Synthetic renderer failure'),
            ):
                with self.assertRaisesRegex(ValueError, 'Only HTML engine reports'):
                    with connect(self.config) as db, db.transaction():
                        operation(db)
        with connect(self.config) as db:
            self.assertEqual(ds.source(db, business, document, revision), before)
            saved = db.execute('SELECT * FROM report_derivation_jobs WHERE id=%s', (job['id'],)).fetchone()
            self.assertEqual((saved['status'], saved['attempts'], saved['claim_id']), ('pending', 0, None))
        with reading.read(self.config, business, document) as (db, doc, rev):
            self.assertEqual(reading.view(db, doc, rev)['mode'], 'blocks')
