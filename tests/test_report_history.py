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


class CitationRuleTests(unittest.TestCase):
    def test_attributed_prior_figure_is_unverifiable_and_never_triggers_a_correction(self):
        from decision_room.engine import blocks, check_contract as contract
        raw = json.dumps(dict(version=blocks.VERSION, titulo='T', bloques=[dict(tipo='prioridad', titulo='P', bloques=[
            dict(tipo='texto', contenido='El informe de junio decía 100 pedidos; ahora hay 120.')])])).encode()
        projection = blocks.parse(raw)
        priority = blocks.priorities(projection)[0]
        text = priority['text']
        quote = 'decía 100 pedidos'
        start = text.index(quote)
        result = contract.parse(json.dumps(dict(version=contract.VERSION, revision_sha256='r', coverage_notes='', items=[
            dict(priority_id=priority['block_id'], quote=quote, start=start, end=start + len(quote), status='unverifiable',
                 independent_value=None, method='Contrastada con informes-anteriores/01.txt.',
                 message='cita del informe anterior; no recalculada con los datos actuales')])).encode(), projection, 'r')
        cited = [i for i in result['items'] if i['quote'] == quote][0]
        self.assertEqual((cited['status'], cited['independent_value']), ('unverifiable', None))
        self.assertEqual(json.loads(contract.correction(result)[len(contract.CORRECTION):]), [])
        self.assertIn('informes-anteriores', contract.PROMPT)
        self.assertIn('nunca porque coincida con el texto', contract.PROMPT)


class SummaryBoundTests(unittest.TestCase):
    def derived(self, priorities, warnings):
        from datetime import datetime, timezone
        from decision_room.engine import blocks
        raw = json.dumps(dict(version=blocks.VERSION, titulo='T', bloques=[
            dict(tipo='prioridad', titulo=f'Prioridad {n} ' + 'é' * 150, bloques=[
                dict(tipo='texto', contenido='Comprobación siguiente: revisar el canal ' + 'ü' * 250)])
            for n in range(priorities)])).encode()
        projection = blocks.parse(raw)
        checks = dict(state='complete', items=[dict(status='discrepancy', quote='5', message='€' * 200, coverage=None)
                                               for _ in range(warnings)])
        row = dict(origin='engine_blocks', title='Informe ' + 'ñ' * 200, goal='ñ' * 400, stale_reason=None,
                   delivered_at=datetime(2026, 9, 1, tzinfo=timezone.utc), period_from=None, period_until=None)
        return row, dict(document=projection, checks=checks, canonical_text='x')

    def test_unicode_warnings_and_many_sections_never_exceed_the_budget(self):
        row, derived = self.derived(priorities=12, warnings=5)
        budget = history.SUMMARY_BYTES // 3
        summary = history._summary(row, derived, 'complete', budget)
        self.assertLessEqual(history.size(summary), budget)
        self.assertIn('Avisos de su comprobación', summary)
        self.assertIn('apartado(s)', summary)

    def test_three_digit_omission_count_still_fits(self):
        from datetime import datetime, timezone
        from decision_room.engine import blocks
        raw = json.dumps(dict(version=blocks.VERSION, titulo='T', bloques=[
            dict(tipo='prioridad', titulo='p' * 200, bloques=[dict(tipo='texto', contenido='x' * 300)])
            for _ in range(150)])).encode()
        row = dict(origin='engine_blocks', title='T', goal='g' * 293, stale_reason=None, period_from=None,
                   period_until=None, delivered_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
        summary = history._summary(row, dict(document=blocks.parse(raw), canonical_text='x'), None, 2048)
        self.assertLessEqual(history.size(summary), 2048)
        self.assertIn('apartado(s)', summary)

    def test_priority_without_action_keeps_its_text(self):
        row, derived = self.derived(priorities=1, warnings=0)
        summary = history._summary(row, derived, 'complete', history.SUMMARY_BYTES)
        self.assertIn('Texto: Comprobación siguiente: revisar el canal', summary)

    def test_old_report_keeps_opening_diagnosis_and_final_next_check(self):
        from datetime import datetime, timezone
        from decision_room.engine import blocks
        raw = json.dumps(dict(version=blocks.VERSION, titulo='T', bloques=[
            dict(tipo='texto', contenido='Las ventas bajan desde marzo.'),
            dict(tipo='prioridad', titulo='Recogida', bloques=[
                dict(tipo='texto', contenido='La recogida cae un 12 %.'),
                dict(tipo='cifra', etiqueta='Pedidos', valor=88),
                dict(tipo='texto', contenido='Comprobación siguiente: revisar las conversiones del mes.')])])).encode()
        row = dict(origin='engine_blocks', title='T', goal='', stale_reason=None, period_from=None, period_until=None,
                   delivered_at=datetime(2026, 9, 1, tzinfo=timezone.utc))
        summary = history._summary(row, dict(document=blocks.parse(raw), canonical_text='x'), None, history.SUMMARY_BYTES)
        self.assertIn('Apertura: Las ventas bajan desde marzo.', summary)
        self.assertIn('Texto: La recogida cae un 12 %.', summary)
        self.assertIn('Texto final: Comprobación siguiente: revisar las conversiones del mes.', summary)


class FileLimitTests(unittest.TestCase):
    def test_short_text_is_whole_and_long_text_is_explicitly_truncated(self):
        self.assertEqual(history._file('corto'), ('corto', False))
        text = 'ñ' * history.FILE_BYTES
        clipped, truncated = history._file(text)
        self.assertTrue(truncated)
        self.assertLessEqual(history.size(clipped), history.FILE_BYTES)
        self.assertIn(history.sha(text), clipped)
        self.assertIn('Texto recortado', clipped)

    def test_truncated_file_keeps_every_check_warning_at_its_end(self):
        warnings = ''.join(f'Cifra en revisión: {n} unidades — discrepancia {n}\n' for n in range(6))
        text = 'cuerpo ' * 12000 + history.CHECK_MARKER + 'completada\n' + warnings
        clipped, truncated = history._file(text)
        self.assertTrue(truncated)
        self.assertLessEqual(history.size(clipped), history.FILE_BYTES)
        self.assertIn('se conserva su sección de comprobación', clipped)
        for n in range(6):
            self.assertIn(f'discrepancia {n}', clipped)
        huge = 'cuerpo ' * 12000 + history.CHECK_MARKER + 'completada\n' + 'Cifra en revisión: ' + 'x' * 300 + '\n' * 1
        many, _ = history._file('cuerpo ' * 12000 + history.CHECK_MARKER + 'completada\n' + ''.join(
            f'Cifra en revisión: {n} ' + 'x' * 300 + '\n' for n in range(200)))
        self.assertLessEqual(history.size(many), history.FILE_BYTES)
        self.assertIn('línea(s) de avisos no caben en este fichero', many)
        self.assertTrue(huge)


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
        # Actions live verbatim in the follow-up register with the owner's state, not as pending lines here.
        self.assertNotIn('Qué comprobar', summary)
        self.assertIn('están en el registro de seguimiento', summary)
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
        self.assertEqual(run['brief']['version'], 'blocks-brief-6')
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

    def test_checker_receives_frozen_prior_texts_and_the_same_summary(self):
        self.deliver()
        second = self.deliver()
        run = self.run_row(second['engine_run_id'])
        with connect(self.config) as db:
            check = db.execute('SELECT instance_id FROM engine_native_checks WHERE run_id=%s ORDER BY started_at LIMIT 1',
                               (second['engine_run_id'],)).fetchone()
        files = IndependentRuntime.sessions[str(check['instance_id'])]['files']
        self.assertEqual(files['contexto/informes-anteriores/01.txt'].decode(), run['input_context']['informes-anteriores/01.txt'])
        self.assertIn('contexto/informes-anteriores/manifest.json', files)
        self.assertNotIn('contexto/panorama.md', files)
        self.assertEqual(files['contexto/definiciones.txt'].decode(), run['brief']['checker_context'])
        self.assertIn(run['brief']['prior_reports'][0]['document_id'], files['contexto/informes-anteriores/manifest.json'].decode())

    def test_replaced_data_keeps_the_same_logical_dataset_first_and_labels_it_stale(self):
        from decision_room.service import import_batch
        first = self.deliver()
        self.csv = b'quantity,amount\n7,70\n8,80\n'
        unrelated = self.deliver()
        self.assertNotEqual(first['analysis_id'], unrelated['analysis_id'])
        path = Path(self.ws.config.storage) / 'nuevo.csv'
        path.write_bytes(b'quantity,amount\n9,90\n')
        newer = import_batch(self.config, self.business['id'], [path])['analysis']['id']
        with connect(self.config) as db:
            db.execute('''INSERT INTO dataset_versions(business_id,analysis_id,dataset_id,version,superseded_by)
                VALUES (%s,%s,%s,1,%s),(%s,%s,%s,2,NULL)''',
                (self.business['id'], first['analysis_id'], first['analysis_id'], newer,
                 self.business['id'], newer, first['analysis_id']))
        value, _, _ = self.select(newer)
        self.assertEqual([r['document_id'] for r in value['reports']],
                         [str(first['report_document_id']), str(unrelated['report_document_id'])])
        self.assertEqual([r['group'] for r in value['reports']], [1, 3])
        self.assertIn('caducado', value['reports'][0]['summary'])

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
