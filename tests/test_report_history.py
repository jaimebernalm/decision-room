"""Prior reports as frozen, labelled, bounded history (separate from the current-report reader)."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.engine import api
from decision_room.reports import history
from tests.test_native_checks import IndependentClient, IndependentRuntime

FIXTURE = Path(__file__).parent / 'fixtures/native-presentation/informe.json'


class FileLimitTests(unittest.TestCase):
    def test_short_text_is_whole_and_long_text_is_explicitly_truncated(self):
        self.assertEqual(history._file('corto'), ('corto', False))
        text = 'ñ' * history.FILE_BYTES
        clipped, truncated = history._file(text)
        self.assertTrue(truncated)
        self.assertLessEqual(history.size(clipped), history.FILE_BYTES)
        self.assertIn(history.sha(text), clipped)
        self.assertIn('Texto recortado', clipped)


class HistoryTests(unittest.TestCase):
    from tests import test_engine_jobs as product
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime

    def deliver(self, payload=None):
        self.fake_runtime()
        IndependentRuntime.payloads = [payload or FIXTURE.read_bytes()]
        IndependentClient.checker_results = []
        p = patch.object(api, 'Runtime', IndependentRuntime); p.start(); self.addCleanup(p.stop)
        job = self.create(engine_kind='opencode', engine_format='blocks', request_key=str(uuid4())); self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'completed', row['issue'])
        return row

    def select(self, analysis, **kwargs):
        with connect(self.config) as db, db.transaction():
            return history.select(db, self.business['id'], analysis, **kwargs)

    def test_summary_keeps_label_cover_priorities_and_proposed_actions(self):
        job = self.deliver()
        value, files, manifest = self.select(job['analysis_id'])
        self.assertEqual(len(value['reports']), 1)
        report = value['reports'][0]
        self.assertEqual(report['document_id'], str(job['report_document_id']))
        summary = report['summary']
        self.assertIn('vigente', summary)
        self.assertIn('Titular: Crece la tienda online', summary)
        self.assertIn('Prioridad: Revisar la recogida en local', summary)
        self.assertIn('Qué comprobar (propuesta de ese informe)', summary)
        self.assertIn('Qué revisar en abril (propuesta de ese informe)', summary)
        self.assertLessEqual(history.size(summary), history.SUMMARY_BYTES)
        self.assertEqual(list(files), ['informes-anteriores/01.txt'])
        self.assertEqual(report['file_sha256'], history.sha(files['informes-anteriores/01.txt']))
        self.assertNotIn('summary', manifest['reports'][0])
        self.assertLessEqual(len(json.dumps(manifest, ensure_ascii=False).encode()), history.META_BYTES)

    def test_stale_report_is_labelled_and_deleted_or_blocked_reports_are_excluded(self):
        job = self.deliver()
        document = job['report_document_id']
        with connect(self.config) as db:
            db.execute("UPDATE report_documents SET stale_reason='data_changed' WHERE id=%s", (document,))
        value, _, _ = self.select(job['analysis_id'])
        self.assertIn('caducado: los datos han cambiado', value['reports'][0]['summary'])
        with connect(self.config) as db, db.transaction():
            self.assertTrue(history.current(db, self.business['id'], value))
        # Blocked presentations are immutable assessments; the SQL filter excludes them.
        with connect(self.config) as db:
            db.execute('UPDATE report_documents SET deleted_at=now() WHERE id=%s', (document,))
        self.assertEqual(self.select(job['analysis_id'])[0]['reports'], [])
        with connect(self.config) as db, db.transaction():
            self.assertFalse(history.current(db, self.business['id'], value))

    def test_explicit_reference_comes_first_and_at_most_three_are_kept(self):
        jobs = [self.deliver() for _ in range(4)]
        oldest = str(jobs[0]['report_document_id'])
        value, files, _ = self.select(jobs[0]['analysis_id'])
        self.assertEqual(len(value['reports']), 3)
        self.assertNotIn(oldest, [r['document_id'] for r in value['reports']])
        value, files, _ = self.select(jobs[0]['analysis_id'], explicit=[oldest])
        self.assertEqual(value['reports'][0]['document_id'], oldest)
        self.assertEqual(value['reports'][0]['group'], 0)
        self.assertEqual(len(files), 3)
        self.assertLessEqual(sum(history.size(r['summary']) for r in value['reports']), history.SUMMARY_BYTES)

    def test_other_business_reports_never_appear(self):
        job = self.deliver()
        from decision_room.service import create_business
        other = create_business(self.config, 'Otro negocio')['id']
        with connect(self.config) as db, db.transaction():
            value, files, _ = history.select(db, other, None)
        self.assertEqual((value['reports'], files), ([], {}))
        self.assertTrue(job)


if __name__ == '__main__':
    unittest.main()
