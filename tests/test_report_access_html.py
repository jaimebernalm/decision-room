"""HTML read authority, dependency retirement and immutable historical views."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from decision_room.database import connect
from decision_room.engine import api, store as receipts
from decision_room.memory import service as memory
from decision_room.reports import store, reading
from decision_room.storage import Storage
from decision_room.service import create_business, import_batch
from decision_room.web.errors import WebError
from tests import test_engine_admission as fixtures
from tests.test_memory import content


class HtmlAccessTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.EngineTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.EngineTests.tearDownClass.__func__)
    setUp = fixtures.EngineTests.setUp
    create = fixtures.EngineTests.create

    def delivered(self):
        run, token = self.create()
        receipt = receipts.receive_document(self.config,run,token,request_key='one',html=b'<h1>Example</h1>')
        api._finish(self.config,self.business,run,'delivered')
        store.adopt(self.config,self.business,run)
        return run,receipt

    def view(self, receipt, **args):
        with reading.read(self.config,self.business,receipt['document_id'],**args) as (db,doc,rev):
            return reading.metadata(db,doc,rev)

    def test_exact_business_document_revision_and_no_job_token_authority(self):
        _,one=self.delivered(); _,two=self.delivered()
        self.assertTrue(self.view(one)['is_current'])
        self.assertEqual(self.view(one)['revision_id'],one['revision_id'])
        foreign=create_business(self.config,'Different business')['id']
        for b,d,r in [(foreign,one['document_id'],one['revision_id']), (self.business,one['document_id'],two['revision_id']),
                      (self.business,two['document_id'],one['revision_id']), ('job-token',one['document_id'],None)]:
            with self.assertRaises(WebError):
                with reading.read(self.config,b,d,revision=r): pass
        self.assertNotIn('raw', self.view(one))
        with self.assertRaises(WebError) as error: reading.blocked_content()
        self.assertEqual(error.exception.status,409)

    def test_changed_or_missing_files_retire_permanently_without_rewriting_snapshot(self):
        for kind in ('parquet','original'):
            run,receipt=self.delivered()
            with connect(self.config) as db:
                frozen=db.execute('SELECT snapshot FROM engine_runs WHERE id=%s',(run,)).fetchone()['snapshot']
                row=db.execute('SELECT p.parquet_key,s.original_key FROM prepared_tables p JOIN sources s ON s.id=p.source_id WHERE p.id=%s',(self.table,)).fetchone()
            path=Storage(self.config.storage).path(self.business,row[kind+'_key'])
            saved=path.read_bytes(); path.unlink()
            stale=self.view(receipt)
            self.assertFalse(stale['is_current'])
            store.audit(self.config,self.business,receipt['document_id'])
            stale=self.view(receipt)
            self.assertFalse(stale['is_current']); self.assertEqual(stale['state'],'withdrawn')
            path.write_bytes(saved)
            self.assertFalse(self.view(receipt)['is_current'])
            with connect(self.config) as db:
                self.assertEqual(db.execute('SELECT snapshot FROM engine_runs WHERE id=%s',(run,)).fetchone()['snapshot'],frozen)
            self.assertEqual(receipts.read_document(self.config,self.business,run)['raw'],b'<h1>Example</h1>')

    def test_scoped_memory_retirement_and_active_run_snapshot_unchanged(self):
        fact=memory.change(self.config,self.business,action='declare',request_key=uuid4().hex,content=content())
        run,receipt=self.delivered(); active,_=self.create()
        with connect(self.config) as db:
            baseline=db.execute('SELECT * FROM engine_report_contexts WHERE run_id=%s',(active,)).fetchone()
        other_file=self.root/'other.csv'; other_file.write_text('quantity\n9\n')
        other=import_batch(self.config,self.business,[other_file])['analysis']['id']
        memory.change(self.config,self.business,action='declare',request_key=uuid4().hex,
                      content=content(topic='other_analysis',scope='analysis',scope_id=str(other)))
        self.assertTrue(self.view(receipt)['is_current'])
        memory.change(self.config,self.business,action='withdraw',request_key=uuid4().hex,
                      fact_id=fact['fact_id'],expected_revision=1)
        self.assertFalse(self.view(receipt)['is_current'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT * FROM engine_report_contexts WHERE run_id=%s',(active,)).fetchone(),baseline)
            self.assertEqual(db.execute('SELECT status FROM engine_runs WHERE id=%s',(active,)).fetchone()['status'],'running')

    def test_history_exact_revision_and_last_durable_ordinal(self):
        run,token=self.create()
        first=receipts.receive_document(self.config,run,token,request_key='mcp',html=b'MCP',via='mcp')
        last=receipts.receive_document(self.config,run,token,request_key='file',html=b'FILE',via='file')
        api._finish(self.config,self.business,run,'delivered'); store.adopt(self.config,self.business,run)
        self.assertTrue(self.view(last)['is_current'])
        previous=self.view(first,revision=first['revision_id'])
        self.assertFalse(previous['is_current']); self.assertEqual(previous['state'],'historical')
        self.assertEqual([r['raw_sha256'] for r in previous['history']],[first['raw_sha256'],last['raw_sha256']])
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda i: store.adopt(self.config,self.business,run) if i else self.view(last),range(3)))
        self.assertEqual(self.view(last)['revision_id'],last['revision_id'])

    def test_definition_writer_retires_without_a_metadata_read(self):
        from decision_room.data_knowledge import service as knowledge
        original=knowledge.ensure(self.config,self.business,self.analysis)
        run,receipt=self.delivered()
        knowledge.change(self.config,self.business,self.analysis,original['revision'],'table',
                         {'id':str(self.table),'columns':[{'name':'quantity','meaning':'Recorded units'}]})
        with connect(self.config) as db:
            document=db.execute('SELECT * FROM report_documents WHERE id=%s',(receipt['document_id'],)).fetchone()
            self.assertEqual(document['stale_reason'],'definitions_changed')
        self.assertFalse(self.view(receipt)['is_current'])
