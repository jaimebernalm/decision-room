"""Real PostgreSQL checks for the owner dossier and immutable data versions."""
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import httpx

from test_web import WebTests as Fixture
from test_memory import content
from decision_room.database import connect, migrate
from decision_room.web import dossier
from decision_room.web.server import Server
from decision_room.web.errors import WebError
from decision_room.memory import service as memory, context, retrieval
from decision_room.conversations import Conversations, snapshot, fresh
from decision_room.agent import service as planning
from test_agent import ScriptedModel


class DossierTests(unittest.TestCase):
    setUpClass = classmethod(Fixture.setUpClass.__func__)
    tearDownClass = classmethod(Fixture.tearDownClass.__func__)
    setUp = Fixture.setUp
    create = Fixture.create
    answer = Fixture.answer
    complete = Fixture.complete

    def upload(self, raw=b'quantity,amount\n2,10\n3,20\n', **changes):
        data = dict(business_id=str(self.business['id']), request_key=str(uuid4()),
                    title='Ventas', mode='separate', period_from='2026-09-01', period_until='2026-09-30')
        data.update(changes)
        return dossier.upload(self.ws, data, 'sales.csv', raw)

    def change(self, **changes):
        return dossier.change(self.ws, dict(business_id=str(self.business['id']), request_key=str(uuid4()), **changes))

    def test_dossier_correction_withdrawal_and_concurrent_edits_share_chat_memory(self):
        fact = self.change(action='declare', content=content())
        data = dossier.listing(self.ws)
        self.assertEqual(data['facts'][0]['original_text'], 'Cerramos los domingos.')
        self.assertNotIn('model_settings', json.dumps(data, default=str))
        with connect(self.config) as db:
            before = snapshot(db, self.business['id'], None, 'horarios')
        barrier = threading.Barrier(2)
        def edit(statement):
            barrier.wait()
            try:
                return self.change(action='correct', fact_id=fact['fact_id'], expected_revision=1, content=content(statement))
            except WebError as error:
                return error.status
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(edit, ['Abrimos los domingos.', 'Solo abrimos los lunes.']))
        self.assertEqual(results.count(409), 1)
        with connect(self.config) as db:
            self.assertFalse(fresh(db, before))
            self.assertNotEqual(snapshot(db, self.business['id'], None, 'horarios')['memories'][0]['content']['statement'], 'Cerramos los domingos.')
        self.change(action='withdraw', fact_id=fact['fact_id'], expected_revision=2)
        with connect(self.config) as db:
            self.assertEqual(snapshot(db, self.business['id'], None, 'horarios')['memories'], [])
        self.assertEqual(len(dossier.listing(self.ws)['history']), 3)
        with self.assertRaises(WebError):
            self.change(action='confirm', fact_id=fact['fact_id'], expected_revision=3)

    def test_confirm_dates_scope_and_other_business(self):
        proposal = self.change(action='propose', content=content())
        self.change(action='confirm', fact_id=proposal['fact_id'], expected_revision=1)
        self.assertEqual(memory.read(self.config, self.business['id'])[0]['status'], 'declared')
        with self.assertRaises(WebError):
            self.change(action='correct', fact_id=proposal['fact_id'], expected_revision=2,
                        content=content(valid_from='2026-10-01', valid_until='2026-09-01'))
        other = self.ws.save_business({'request_key': str(uuid4()), 'name': 'Other', 'description': 'Other shop', 'expected_active_id': str(self.business['id'])})
        with self.assertRaises(WebError):
            dossier.change(self.ws.scoped(other['id']), dict(business_id=str(other['id']), request_key=str(uuid4()), action='withdraw', fact_id=proposal['fact_id'], expected_revision=2))

    def test_independent_upload_no_jobs_or_model_duplicate_download_and_reuse(self):
        self.ws.settings = None
        key = str(uuid4())
        first = self.upload(request_key=key)
        self.assertEqual(first, self.upload(request_key=key))
        duplicate = self.upload(title='Renamed')
        self.assertTrue(duplicate['reused'])
        self.assertEqual(first['analysis_id'], duplicate['analysis_id'])
        with self.assertRaises(WebError):
            self.upload(request_key=key, title='Changed')
        data = dossier.listing(self.ws)
        self.assertEqual(len(data['datasets']), 1)
        self.assertEqual(dossier.download(self.ws, data['datasets'][0]['files'][0]['id'])[1], self.csv)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM web_jobs WHERE business_id=%s', (self.business['id'],)).fetchone()['n'], 0)
            catalog = context.datasets(db, self.business['id'])['items']
            self.assertEqual(catalog[0]['period']['from'], '2026-09-01')
        chat = Conversations(self.ws).create(dict(business_id=str(self.business['id']), request_key=str(uuid4()), analysis_id=first['analysis_id']))
        self.assertEqual(str(chat['analysis_id']), first['analysis_id'])

    def test_version_update_preserves_report_dependencies_correction_invalidates(self):
        first = self.upload()
        b = self.business['id']
        plan = planning.start(self.config, b, first['analysis_id'], owner_context='sales', request_key='dossier-first', model=ScriptedModel())
        with connect(self.config) as db:
            table = context.datasets(db, b)['items'][0]
            original_version = context.table_version(db, b, table['id'])
            self.assertIsNone(context.reason(db, plan['id']))
        second = self.upload(b'quantity,amount\n4,40\n', mode='update', previous_id=first['analysis_id'], period_from='2026-10-01', period_until='2026-10-31')
        with connect(self.config) as db:
            self.assertIsNone(context.reason(db, plan['id']))
            self.assertEqual(context.table_version(db, b, table['id']), original_version)
            self.assertEqual([r['analysis_id'] for r in context.datasets(db,b)['items']], [second['analysis_id']])
            self.assertTrue(dossier.available(db,b,first['analysis_id']))
        second_plan = planning.start(self.config,b,second['analysis_id'],owner_context='sales',request_key='dossier-second',model=ScriptedModel())
        third = self.upload(b'quantity,amount\n4,35\n', mode='correction', previous_id=second['analysis_id'])
        with connect(self.config) as db:
            self.assertIsNotNone(context.reason(db, second_plan['id']))
            self.assertIsNone(context.reason(db, plan['id']))
            self.assertFalse(dossier.available(db,b,second['analysis_id']))
            self.assertEqual([r['analysis_id'] for r in context.datasets(db,b)['items']], [third['analysis_id']])
            results = retrieval._datasets(self.config,db,dict(business_id=b),'amount',10)
            self.assertEqual([r['analysis_id'] for r in results['items']], [third['analysis_id']])
        versions = sorted(dossier.listing(self.ws)['datasets'],key=lambda d:d['version'])
        self.assertEqual([v['version'] for v in versions], [1,2,3])
        self.assertEqual(len({v['dataset_id'] for v in versions}), 1)
        with self.assertRaises(WebError):
            self.upload(b'quantity,amount\n4,50\n', mode='update', previous_id=first['analysis_id'])

    def test_failed_csv_preserves_current_version_and_separate_files_never_merge(self):
        first = self.upload()
        broken = self.upload(b'quantity,amount\n1,2,3\n', mode='correction', previous_id=first['analysis_id'])
        self.assertEqual(broken['status'], 'failed')
        self.upload(b'quantity,amount\n2,10\n4,30\n')
        with connect(self.config) as db:
            items = context.datasets(db,self.business['id'])['items']
            self.assertEqual(len(items),2)
            self.assertEqual(len({i['analysis_id'] for i in items}), 2)
            self.assertTrue(dossier.available(db,self.business['id'],first['analysis_id']))

    def test_interruption_after_import_recovers_relationship_without_duplicates(self):
        first = self.upload()
        key = str(uuid4())
        original = dossier.ingestion.import_batch
        def interrupted(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('simulated crash after preparation')
        changes = dict(request_key=key, mode='correction', previous_id=first['analysis_id'])
        raw = b'quantity,amount\n2,99\n'
        with patch.object(dossier.ingestion,'import_batch',side_effect=interrupted), self.assertRaises(RuntimeError):
            self.upload(raw, **changes)
        with connect(self.config) as db:
            self.assertEqual([i['analysis_id'] for i in context.datasets(db,self.business['id'])['items']], [first['analysis_id']])
        recovered = self.upload(raw, **changes)
        self.assertEqual(recovered, self.upload(raw, **changes))
        data = dossier.listing(self.ws)
        self.assertEqual(len(data['datasets']), 2)
        self.assertEqual(sorted(d['version'] for d in data['datasets']), [1,2])

    def test_actual_approved_report_survives_update_but_not_source_correction(self):
        job = self.complete()
        original = self.ws.report(job)
        old = self.ws.row(job)['analysis_id']
        # Importing another period does not mutate the approved historical report.
        self.upload(b'quantity,amount\n2,80\n', mode='update', previous_id=str(old))
        self.assertEqual(self.ws.report(job), original)
        self.assertTrue(self.ws.dashboard()['data_version']['superseded_by'])
        self.assertFalse(self.ws.detail(job)['data_version']['corrected'])

    def test_correcting_approved_source_hides_dashboard_and_export(self):
        job = self.complete()
        old = self.ws.row(job)['analysis_id']
        self.upload(b'quantity,amount\n2,99\n', mode='correction', previous_id=str(old))
        self.assertFalse(self.ws.detail(job)['publishable'])
        self.assertEqual(self.ws.detail(job)['status'], 'blocked')
        self.assertIsNone(self.ws.dashboard()['report'])
        with self.assertRaises(WebError):
            self.ws.report(job)
        with self.assertRaises(WebError):
            self.ws.retry(job)

    def test_http_auth_validation_download_and_schema_reentry(self):
        migrate(self.config)
        server = Server(self.ws,0,token='dossier-test-only')
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        with httpx.Client(base_url=server.origin) as client:
            self.assertEqual(client.get('/api/business/dossier').status_code,401)
            client.headers.update({'Origin':server.origin,'X-Decision-Room':'1'})
            self.assertEqual(client.post('/api/login',json={'token':'dossier-test-only'}).status_code,200)
            self.assertEqual(client.get('/api/business/dossier').status_code,200)
            metadata = dict(business_id=str(self.business['id']), request_key=str(uuid4()),title='HTTP CSV')
            response = client.post('/api/datasets',files={'metadata':(None,json.dumps(metadata)),'file':('http.csv',self.csv,'text/csv')})
            self.assertEqual(response.status_code,200,response.text)
            data = client.get('/api/business/dossier').json()
            source = data['datasets'][0]['files'][0]['id']
            self.assertEqual(client.get('/api/datasets/file/'+source).content,self.csv)
            invalid = client.post('/api/business/memory',json=dict(business_id=str(self.business['id']),action='declare',request_key='bad',content={}))
            self.assertEqual(invalid.status_code,400)
            self.assertEqual(client.get('/dossier.js').status_code,200)

# Do not collect the imported fixture's test methods a second time.
del Fixture
