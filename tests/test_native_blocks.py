"""N1 format, receipt identity and deterministic native projection without a renderer."""
import copy
import json
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from decision_room.reports import store, native_store, reading
from decision_room.engine import blocks
from decision_room.reports.derivative_store import canonical as encode, sha
from decision_room.engine import profile, api, file_delivery, store as receipts
from decision_room.database import connect, migrate
from tests import test_engine_admission as fixtures


def example():
    return dict(version=blocks.VERSION,titulo='Fixture',bloques=[dict(tipo='prioridad',titulo='Prioridad',bloques=[
        dict(tipo='texto',contenido='Texto libre con una cifra: 5 unidades.'),
        dict(tipo='grafico',grafico='tipo_nuevo',titulo='Serie',categorias=['Enero','Febrero'],
             series=[dict(nombre='Unidades',valores=[5,None])]),
        dict(tipo='cifra',etiqueta='Total',valor=5,anterior=dict(valor=2))])])


class FormatTests(unittest.TestCase):
    def test_collection_paths_are_only_profile_constants(self):
        self.assertIn("p='/work/informe.json'", file_delivery.script('informe.json'))
        self.assertIn("p='/work/informe.html'", file_delivery.script())
        with self.assertRaises(ValueError): file_delivery.script('../../secret')

    def test_native_brief_keeps_analytic_instructions(self):
        from decision_room.engine.brief import compose, FIXED
        kwargs=dict(name='Fixture',description='Data',goal='Compare',model=None,memory=[],panorama=False)
        native=compose(**kwargs,format='blocks'); html=compose(**kwargs)
        self.assertIn('informe.json',native); self.assertNotIn('informe.html',native)
        # blocks-brief-2 keeps the analytic paragraph but names data dimensions generically, not sales ones.
        analytic=FIXED.read_text().split('\n\n')[1]
        self.assertIn(analytic.replace('producto, canal y fechas','las dimensiones de los datos y de fechas'),native)
        self.assertIn('informe.html',html)


class NativeRegistryTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp=fixtures.EngineTests.setUp
    create=fixtures.EngineTests.create

    def native(self, raw):
        run,token=self.create(engine_config=profile.configuration(model='test-model',format='blocks'))
        received=receipts.receive_document(self.config,run,token,request_key='file',html=raw,via='file')
        api._finish(self.config,self.business,run,'delivered')
        return run, received

    def test_atomic_idempotent_native_derivative_and_raw_export_no_browser(self):
        raw=encode(example()); run,received=self.native(raw)
        with patch('decision_room.reports.derive_policy.renderer_version',side_effect=AssertionError('browser')), ThreadPoolExecutor(max_workers=2) as pool:
            documents=list(pool.map(lambda _:store.adopt(self.config,self.business,run), range(2)))
        self.assertEqual(str(documents[0]),received['document_id'])
        self.assertEqual(documents[0],documents[1])
        with reading.read(self.config,self.business,documents[0]) as (db,document,revision):
            self.assertEqual(document['origin'],'engine_blocks')
            self.assertIsNone(document['current_revision_id']) # N3 check required before publication.
            self.assertEqual(reading.view(db,document,revision)['mode'],'blocks')
            result=native_store.result(db,self.business,document['id'],revision['id'])
            self.assertEqual(result['document'],blocks.parse(raw))
            self.assertEqual(db.execute('SELECT count(*) AS n FROM report_derivation_jobs WHERE document_id=%s',(document['id'],)).fetchone()['n'],0)
        exported=api.export_run(self.config,self.business,run,self.root/'export')
        self.assertEqual(exported['mime_type'],'application/json')
        self.assertEqual((self.root/'export/informe.raw.json').read_bytes(),raw)
        self.assertFalse((self.root/'export/informe.raw.html').exists())
        migrate(self.config); migrate(self.config)
        self.assertEqual(receipts.read_document(self.config,self.business,run)['raw'],raw)

    def test_invalid_receipt_preserved_without_current_revision_and_foreign_access(self):
        raw=b'{"cut":';run,receipt=self.native(raw)
        doc=store.adopt(self.config,self.business,run)
        with reading.read(self.config,self.business,doc) as (db,document,revision):
            self.assertEqual(revision['raw'],raw)
            self.assertEqual(reading.view(db,document,revision)['mode'],'blocked')
            self.assertIsNone(document['current_revision_id'])
        with self.assertRaises(Exception):
            with reading.read(self.config,uuid4(),doc): pass
        with self.assertRaises(Exception):
            with reading.read(self.config,self.business,doc,revision=uuid4()): pass
        self.assertEqual(receipts.read_document(self.config,self.business,run)['raw_sha256'],receipt['raw_sha256'])

    def test_historical_projection_is_not_recomputed_after_projector_upgrade(self):
        raw=encode(example());run,receipt=self.native(raw)
        doc=store.adopt(self.config,self.business,run)
        with reading.read(self.config,self.business,doc) as (db,document,revision):
            original=native_store.result(db,self.business,doc,revision['id'])
        with patch.object(blocks,'PROJECTOR_VERSION','future-projector'), patch.object(blocks,'parse',side_effect=AssertionError('reprojected')):
            store.adopt(self.config,self.business,run)
            with reading.read(self.config,self.business,doc) as (db,document,revision):
                saved=native_store.result(db,self.business,doc,revision['id'])
                self.assertEqual(saved['document'],original['document'])
                self.assertEqual(saved['canonical_sha256'],original['canonical_sha256'])
                self.assertEqual(saved['projector_version'],original['projector_version'])
                self.assertEqual(reading.view(db,document,revision)['mode'],'blocks')


class NativeProductTests(unittest.TestCase):
    from tests import test_engine_jobs as product_fixtures
    setUpClass = classmethod(product_fixtures.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product_fixtures.EngineJobTests.tearDownClass.__func__)
    setUp = product_fixtures.EngineJobTests.setUp
    create = product_fixtures.EngineJobTests.create
    pinned = product_fixtures.EngineJobTests.pinned
    fake_runtime = product_fixtures.EngineJobTests.fake_runtime

    def test_product_receipt_snapshot_tools_and_recovery_without_legacy_or_renderer(self):
        from tests.engine_fakes import FakeRuntime
        self.fake_runtime(); raw = encode(example()); FakeRuntime.payload = raw
        job = self.create(engine_kind='opencode', engine_format='blocks')
        with patch('decision_room.engine.native_checks.draft',return_value='delivered'):
            self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'completed', row['issue'])
        self.assertIsNone(row['review_id'])
        self.assertEqual(receipts.read_document(self.config, row['business_id'], row['engine_run_id'])['raw'], raw)
        files = FakeRuntime.sessions[str(row['engine_run_id'])]['files']
        self.assertEqual(files['herramientas/comprobar_informe.py'], __import__('pathlib').Path(blocks.__file__).read_bytes())
        self.assertEqual(files['contexto/formato-informe.txt'], blocks.FORMAT_GUIDE.encode())
        with reading.read(self.config, row['business_id'], row['report_document_id']) as (db, document, revision):
            self.assertEqual(document['origin'], 'engine_blocks')
            self.assertIsNone(document['current_revision_id'])
            self.assertEqual(reading.view(db, document, revision)['checks']['state'], 'unknown')
        self.ws.run_job(job)
        self.assertEqual(self.ws.row(job)['engine_run_id'], row['engine_run_id'])
        pdf = self.ws.report(job, structured=True, purpose='pdf')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        attachment = self.ws.report(job, structured=True, purpose='raw')
        self.assertEqual(attachment, raw)
        self.assertTrue(attachment.native)
        self.assertEqual(len([m for m in FakeRuntime.sessions[str(row['engine_run_id'])]['messages'] if m['info']['role']=='user']), 1)

    def test_format_immutable_on_all_creation_paths_and_legacy_unchanged(self):
        import io
        from pathlib import Path
        from decision_room.service import import_batch
        from decision_room.web.service import WebError
        self.pinned(); self.assertEqual(self.ws.row(self.create())['engine_kind'], 'legacy')
        for format in ('wrong', 'blocks'):
            with self.assertRaises(WebError): self.create(request_key=uuid4().hex, engine_format=format)
        staged = self.ws.stage_upload('fixture.csv', io.BytesIO(self.csv), len(self.csv))
        batch_data = {**self.metadata, 'request_key': uuid4().hex, 'files':[staged['id']], 'engine_kind':'opencode', 'engine_format':'blocks'}
        batch = self.ws.create_batch(batch_data)['id']
        csv = Path(self.temp.name)/'fixture.csv'; csv.write_bytes(self.csv)
        dataset = import_batch(self.config, self.business['id'], [csv])['analysis']['id']
        data = {**self.metadata, 'request_key': uuid4().hex, 'analysis_id':str(dataset), 'engine_kind':'opencode', 'engine_format':'blocks'}
        prepared = self.ws.create_from_dataset(data)['id']
        for job in (batch, prepared): self.assertEqual(self.ws.row(job)['engine_config']['profile']['format'], 'blocks')
        with self.assertRaises(WebError): self.ws.create_batch({**batch_data, 'engine_format':'html'})
        with self.assertRaises(WebError): self.ws.create_from_dataset({**data, 'engine_format':'html'})
