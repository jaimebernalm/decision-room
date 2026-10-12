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


def brief_module():
    from decision_room.engine import brief
    return brief


class ContextFileTests(unittest.TestCase):
    def test_exact_paths_limits_and_manifest_are_enforced(self):
        from decision_room.engine import profile
        ok = {'informes-anteriores/01.txt': 'x', 'informes-anteriores/manifest.json': '{}'}
        self.assertEqual(profile.context_files(ok), ok)
        for bad in ({'informes-anteriores/04.txt': 'x', 'informes-anteriores/manifest.json': '{}'},
                    {'../panorama.md': 'x'}, {'formato-informe.txt': 'x'}, {'/etc/passwd': 'x'},
                    {'informes-anteriores/01.txt': 'x'},
                    {'informes-anteriores/01.txt': 'a' * (64 * 1024 + 1), 'informes-anteriores/manifest.json': '{}'},
                    {'informes-anteriores/01.txt': 'x', 'informes-anteriores/manifest.json': 'm' * (8 * 1024 + 1)}):
            with self.assertRaises(ValueError):
                profile.context_files(bad)


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

    def prepare(self, job_id, key):
        from decision_room.web import engine_jobs
        job = self.ws.row(job_id)
        settings = job['engine_config']
        return api.prepare_report(self.config, job['business_id'], job['analysis_id'], owner_context=settings['owner_context'],
                                  request_key=key, limits=settings['limits'], engine_config=settings['profile'],
                                  **engine_jobs.creation(self.config, job))[0]

    def run_row(self, run):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM engine_runs WHERE id=%s', (run,)).fetchone()

    def test_next_brief_freezes_prior_summaries_files_and_checker_context(self):
        first = self.deliver()
        second = self.deliver()
        run = self.run_row(second['engine_run_id'])
        self.assertIn(brief_module().HISTORY, run['prompt'])
        self.assertIn('Prioridad: Revisar la recogida en local', run['prompt'])
        self.assertIn('Prioridad: Revisar la recogida en local', run['brief']['checker_context'])
        self.assertEqual(run['brief']['version'], 'blocks-brief-5')
        self.assertEqual([r['document_id'] for r in run['brief']['prior_reports']], [str(first['report_document_id'])])
        self.assertEqual(set(run['input_context']) - {'panorama.md'},
                         {'informes-anteriores/01.txt', 'informes-anteriores/manifest.json'})
        files = api._inputs(self.config, run)
        self.assertIn('contexto/informes-anteriores/01.txt', files)
        manifest = json.loads(files['contexto/informes-anteriores/manifest.json'])
        self.assertEqual(manifest['reports'][0]['file_sha256'], history.sha(run['input_context']['informes-anteriores/01.txt']))
        # The first report had no history: no paragraph and no files.
        opening = self.run_row(first['engine_run_id'])
        self.assertNotIn(brief_module().HISTORY, opening['prompt'])
        self.assertEqual(set(opening['input_context']) - {'panorama.md'}, set())

    def test_replayed_key_reuses_frozen_inputs_and_a_changed_request_still_fails(self):
        self.deliver()
        job = self.deliver()
        before = self.run_row(job['engine_run_id'])
        self.deliver()  # A newer report appears before a recovery of the second job.
        self.assertEqual(self.prepare(job['id'], 'web:' + str(job['id'])), job['engine_run_id'])
        after = self.run_row(job['engine_run_id'])
        self.assertEqual((after['prompt'], after['input_sha256']), (before['prompt'], before['input_sha256']))
        # The same key with another static request is still refused.
        from decision_room.web import engine_jobs
        row = self.ws.row(job['id'])
        created = engine_jobs.creation(self.config, row)
        created['builder'].request = {**created['builder'].request, 'goal': 'Otra pregunta'}
        settings = row['engine_config']
        with self.assertRaises(ValueError):
            api.prepare_report(self.config, row['business_id'], row['analysis_id'], owner_context=settings['owner_context'],
                               request_key='web:' + str(job['id']), limits=settings['limits'],
                               engine_config=settings['profile'], **created)

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
