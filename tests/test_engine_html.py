"""HTML receipt, isolated-file collection and product-independent recovery."""
import hashlib
import json
import subprocess
import sys
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room import engine
from decision_room.database import connect, migrate
from decision_room.engine import admission, api, file_delivery, gateway, profile, store
from tests import test_engine_admission as fixtures
from tests.engine_fakes import FakeClient, FakeRuntime, FakeTunnel


class HtmlTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create

    def test_raw_revisions_limits_and_business_scope(self):
        run, token = self.create()
        for n, raw in enumerate((b'', b'\xff<html>cut', b'<script>window.top.location="bad"</script>', b'x' * store.MAX_DRAFT_BYTES)):
            receipt = store.receive_document(self.config, run, token, request_key=str(n), html=raw)
            self.assertEqual(receipt, store.receive_document(self.config, run, token, request_key=str(n), html=raw))
            self.assertEqual(store.read_document(self.config, self.business, run)['raw'], raw)
            self.assertEqual(receipt['presentation'], 'not_evaluated')
            self.assertEqual(receipt['verification'], 'not_requested')
        with self.assertRaises(ValueError):
            store.receive_document(self.config, run, token, request_key='3', html='changed')
        huge = b'z' * (store.MAX_DRAFT_BYTES + 1)
        with self.assertRaises(ValueError):
            store.receive_document(self.config, run, token, request_key='large', html=huge)
        self.assertEqual(store.read_document(self.config, self.business, run)['raw'], b'x' * store.MAX_DRAFT_BYTES)
        with connect(self.config) as db:
            rejected = db.execute("SELECT payload,created_at FROM engine_events WHERE run_id=%s AND kind='delivery_rejected'", (run,)).fetchone()
        self.assertEqual(rejected['payload']['sha256'], hashlib.sha256(huge).hexdigest())
        self.assertEqual(rejected['payload']['bytes'], len(huge))
        self.assertEqual(rejected['payload']['via'], 'mcp')
        self.assertIsNotNone(rejected['created_at'])
        with self.assertRaises(admission.Denied):
            store.receive_file(self.config, uuid4(), run, {'status': 'received', 'raw': b'a', 'bytes': 1, 'sha256': admission.sha(b'a')})

    def test_database_byte_limit_and_repeat_migration_on_master(self):
        run, token = self.create()
        receipt = store.receive_document(self.config, run, token, request_key='one', html=b'a')
        with connect(self.config) as db:
            with self.assertRaises(Exception):
                db.execute('UPDATE engine_document_revisions SET raw=%s WHERE id=%s', (b'x' * (store.MAX_DRAFT_BYTES+1), receipt['revision_id']))
        migrate(self.config); migrate(self.config)
        self.assertEqual(store.read_document(self.config, self.business, run)['raw'], b'a')
        with connect(self.config) as db:
            cols = db.execute("SELECT column_name FROM information_schema.columns WHERE table_name='analyses'").fetchall()
        self.assertIn('library_hidden', [r['column_name'] for r in cols])

    def test_profile_input_prompt_hashes_and_mcp_surface(self):
        run, token = self.create(context={'panorama.md': 'Only units.'})
        row = api._row(self.config, self.business, run)
        self.assertEqual(row['profile']['variant'], 'low')
        self.assertFalse(row['profile']['questions'])
        self.assertEqual(row['prompt_sha256'], admission.sha(row['prompt'].encode()))
        files = api._inputs(self.config, row)
        self.assertEqual(files['contexto/panorama.md'], b'Only units.')
        self.assertTrue(any(n.startswith('datos/') for n in files))
        response = gateway.dispatch(self.config, run, token, {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
        self.assertEqual([t['name'] for t in response['result']['tools']], ['entregar_informe'])
        for kwargs in ({'context': {'../secret': 'x'}}, {'engine_config': {}}, {'owner_context': None}):
            with self.assertRaises(ValueError): self.create(**kwargs)

    def test_file_delivery_two_controllers_and_bootstrap_restart(self):
        FakeRuntime.sessions = {}; FakeRuntime.mode = 'deliver'; FakeClient.config = self.config
        FakeRuntime.payload = b'<!doctype html><h1>Resultado</h1><p>5 unidades.</p>'
        patches = [('Runtime', FakeRuntime), ('DockerBackend', lambda: object()), ('JobTunnel', FakeTunnel),
                   ('_service', lambda *args: SimpleNamespace(origin='http://127.0.0.1:1'))]
        for target, value in patches:
            p = patch.object(api, target, value); p.start(); self.addCleanup(p.stop)
        # The bootstrap process died after create, before retaining its token.
        run, _ = self.create(request_key='bootstrap')
        failures = []
        def resume():
            try: engine.resume_report(self.config, self.business, run)
            except Exception as error: failures.append(error)
        workers = [threading.Thread(target=resume) for _ in range(2)]
        for w in workers: w.start()
        for w in workers: w.join(10); self.assertFalse(w.is_alive())
        self.assertLessEqual(len(failures), 1)
        self.assertTrue(all(isinstance(e, admission.Denied) for e in failures), failures)
        result = engine.export_run(self.config, self.business, run, self.root/'export')
        self.assertEqual(result['status'], 'delivered', result)
        self.assertEqual((self.root/'export/informe.raw.html').read_bytes(), b'<!doctype html><h1>Resultado</h1><p>5 unidades.</p>')
        self.assertEqual(store.read_document(self.config, self.business, run)['delivery_via'], 'file')
        self.assertEqual(sum(m['info']['role'] == 'user' for m in FakeRuntime.sessions[str(run)]['messages']), 1)
        self.assertEqual(result['presentation'], 'not_evaluated')


class FileCollectorTests(unittest.TestCase):
    def test_regular_empty_oversized_and_symlink_without_interpreting_html(self):
        import tempfile
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'informe.html'
            script = file_delivery.SCRIPT.replace("p='/work/informe.html'", 'p='+repr(str(path)))
            def collect():
                output = subprocess.run([sys.executable, '-I', '-S', '-c', script], capture_output=True, timeout=10, check=True)
                return file_delivery.decode(output.stdout)
            self.assertEqual(collect(), {'status': 'missing'})
            for raw in (b'', b'\xff<script>cut', b'z'*(store.MAX_DRAFT_BYTES+1)):
                path.write_bytes(raw); result = collect()
                self.assertEqual(result['bytes'], len(raw))
                self.assertEqual(result['sha256'], admission.sha(raw))
                self.assertEqual(result['status'], 'oversized' if len(raw)>store.MAX_DRAFT_BYTES else 'received')
            path.unlink(); path.symlink_to(Path(root)/'missing')
            with self.assertRaises(subprocess.CalledProcessError): collect()


class MasterMigrationTests(unittest.TestCase):
    def test_populated_master_upgrade_twice_preserves_existing_data(self):
        import tempfile
        from decision_room.config import Config
        from decision_room.service import create_business, import_batch
        base = Config.load(); name = 'dr_f0_migration_' + uuid4().hex
        with connect(base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            with tempfile.TemporaryDirectory() as root:
                config = replace(base, dsn=make_conninfo(base.dsn, dbname=name), storage=Path(root)/'storage')
                master = subprocess.run(['git', 'show', '5b11154:decision_room/schema.sql'], check=True, capture_output=True).stdout.decode()
                with connect(config) as db: db.execute(master)
                business = create_business(config, 'Migration fixture')['id']
                csv = Path(root)/'units.csv'; csv.write_text('quantity\n2\n3\n')
                # Bootstrap pre-F1 data using the old writer's lack of a registry hook.
                with patch('decision_room.reports.store.invalidate'):
                    analysis = import_batch(config, business, [csv])['analysis']['id']
                with connect(config) as db:
                    db.execute('UPDATE analyses SET library_hidden=true WHERE id=%s', (analysis,))
                    before = db.execute('SELECT * FROM analyses WHERE id=%s', (analysis,)).fetchone()
                migrate(config); migrate(config)
                with connect(config) as db:
                    self.assertEqual(before, db.execute('SELECT * FROM analyses WHERE id=%s', (analysis,)).fetchone())
                    self.assertEqual(db.execute('SELECT max(version) AS v FROM schema_versions').fetchone()['v'], 38)
                    self.assertEqual(db.execute('SELECT count(*) AS n FROM engine_runs').fetchone()['n'], 0)
        finally:
            with connect(base) as db:
                db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
