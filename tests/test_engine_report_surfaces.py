"""F1 metadata surfaces cannot expose agent HTML or invent a legacy approval."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.engine import admission, store
from decision_room.memory import service as memory
from decision_room.web import home
from decision_room.web.errors import WebError
from tests import test_engine_jobs as engine, test_web as web
from tests.test_memory import content


class HtmlSurfaceTests(unittest.TestCase):
    setUpClass=classmethod(engine.EngineJobTests.setUpClass.__func__)
    tearDownClass=classmethod(engine.EngineJobTests.tearDownClass.__func__)
    setUp=engine.EngineJobTests.setUp
    create=engine.EngineJobTests.create
    pinned=engine.EngineJobTests.pinned
    fake_runtime=engine.EngineJobTests.fake_runtime
    http=web.WebTests.http

    def delivered(self):
        self.fake_runtime()
        from tests.engine_fakes import FakeRuntime
        FakeRuntime.payload=b'<script>PRIVATE_AGENT_ONLY</script>'
        job=self.create(engine_kind='opencode',title='<b>Owner title</b>')
        self.ws.run_job(job)
        return job

    def test_metadata_list_detail_home_search_and_exact_history(self):
        job=self.delivered(); row=self.ws.row(job)
        client,server=self.http(); client.post('/api/login',json={'token':server.token})
        with patch('decision_room.engine.admission._snapshot',side_effect=AssertionError('dataset recalculation on read')), \
             patch('decision_room.storage.digest',side_effect=AssertionError('dataset hash on read')):
            detail=client.get(f'/api/jobs/{job}').json()
            display=client.get(f'/api/jobs/{job}/presentation').json()
            listed=client.get('/api/reports?q=Owner').json()['items']
            front=home.view(self.ws)
            self.assertTrue(detail['engine_report']['is_current'])
            self.assertFalse(detail['publishable']); self.assertFalse(detail['can_retry'])
            self.assertEqual(display['origin'],'engine_html'); self.assertFalse(display['claims'])
            self.assertEqual(len(listed),1); self.assertEqual(listed[0]['presentation_status'],'saved')
            self.assertEqual(listed[0]['engine_report']['history'],[])
            self.assertEqual([r['id'] for r in front['report_accesses']],[str(job)])
            self.assertEqual(front['items'],[]); self.assertEqual(front['sources'],[])
            exact=client.get(f'/api/jobs/{job}/presentation?revision={display["engine_report"]["revision_id"]}')
            self.assertEqual(exact.status_code,200)
        for action in ('report','pdf'):
            self.assertEqual(client.get(f'/api/jobs/{job}/{action}').status_code,409)
        self.assertEqual(client.get(f'/api/jobs/{job}/presentation?revision={uuid4()}').status_code,404)
        self.assertEqual(client.get(f'/api/presentation/{row["report_document_id"]}').status_code,409)
        self.assertIsNone(row['review_id']); self.assertIsNone(row['session_id'])
        self.assertNotIn('PRIVATE_AGENT_ONLY',json.dumps(display))
        self.assertEqual(client.get('/api/reports?q=private agent content').json()['items'],[])
        memory.change(self.config,row['business_id'],action='declare',request_key=uuid4().hex,content=content())
        self.assertEqual(home.view(self.ws)['report_accesses'],[])
        self.assertEqual(client.get(f'/api/jobs/{job}/presentation').json()['engine_report']['state'],'withdrawn')

    def test_sources_delete_and_cross_business_guard_every_surface(self):
        job=self.delivered(); row=self.ws.row(job)
        client,server=self.http(); client.post('/api/login',json={'token':server.token})
        receipt=store.read_document(self.config,row['business_id'],row['engine_run_id'])
        sources=client.get(f'/api/jobs/{job}/sources').json()
        self.assertEqual(sources['revision_id'],receipt['revision_id'])
        self.assertNotIn('sample',json.dumps(sources)); self.assertNotIn('/Users/',json.dumps(sources))
        self.assertEqual(client.get(f'/api/jobs/{job}/sources?revision={uuid4()}').status_code,404)
        body={'business_id':str(row['business_id'])}
        client.post(f'/api/jobs/{job}/delete',json=body)
        for action in ('sources','presentation','report','pdf'):
            self.assertEqual(client.get(f'/api/jobs/{job}/{action}').status_code,404)
        client.post(f'/api/jobs/{job}/restore',json=body)
        self.ws.save_business({'request_key':uuid4().hex,'name':'Foreign','description':'Other data','expected_active_id':str(self.business['id'])})
        for action in ('sources','presentation','report','pdf'):
            self.assertEqual(client.get(f'/api/jobs/{job}/{action}').status_code,404)
        self.assertEqual(client.get('/api/reports').json()['items'],[])

    def test_analysis_identity_is_bound_and_concurrent_visibility_is_atomic(self):
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path
        from decision_room.service import import_batch
        job=self.delivered(); row=self.ws.row(job)
        another=Path(self.temp.name)/'different.csv'; another.write_text('quantity\n8\n')
        analysis=import_batch(self.config,row['business_id'],[another])['analysis']['id']
        with connect(self.config) as db:
            for wrong in (analysis,None):
                with self.assertRaises(Exception):
                    db.execute('UPDATE web_jobs SET analysis_id=%s WHERE id=%s',(wrong,job))
            with self.assertRaises(Exception):
                db.execute('UPDATE engine_runs SET analysis_id=%s WHERE id=%s',(analysis,row['engine_run_id']))
        def mutate(_):
            self.ws.delete_report(job,{'business_id':str(row['business_id'])})
            self.ws.delete_report(job,{'business_id':str(row['business_id'])},restore=True)
        def observe(_):
            from decision_room.web.report_access import read_job
            from decision_room.reports import reading
            try:
                with read_job(self.ws,job,deleted=True) as (db,current,pair):
                    meta=reading.metadata(db,*pair)
                    stored=db.execute('SELECT deleted_at FROM web_jobs WHERE id=%s',(job,)).fetchone()['deleted_at']
                    self.assertEqual(meta['deleted'],bool(stored))
                    self.assertEqual(meta['document_id'],str(current['report_document_id']))
            except WebError as error:
                self.fail(str(error))
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda i: mutate(i) if i%3==0 else observe(i),range(12)))
