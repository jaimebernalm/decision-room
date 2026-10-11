"""Offline service/restart tests; fake renderer has the exact contained receipt contract."""
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import base64
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
import time
import unittest
from uuid import uuid4
import zlib

from decision_room.database import connect
from decision_room.reports import derive, derive_policy as policy, derivative_store as ds, inventory, render_browser as rb
from tests import test_report_derivatives as fixtures


def inspection(raw):
    return dict(state='blocked' if b'<base' in raw else 'allowed',reason='element:base' if b'<base' in raw else None)


def snapshot():
    def chunk(tag,data): return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data))
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1280,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+b'\xff'*3840))+chunk(b'IEND',b'')
    return rb.SNAPSHOT_PREFIX+'<img alt="Página del informe" width="1280" height="1" style="display:block;max-width:100%;height:auto" src="data:image/png;base64,'+base64.b64encode(png).decode()+'">'+rb.SNAPSHOT_SUFFIX


class FakeRenderer:
    calls=0
    def render(self,raw,job_id):
        self.calls+=1
        return dict(inventory=inventory.from_snapshot(raw,{'nodes':[{'path':[0],'text':'Units 5'}]}),snapshot_html=snapshot())


class DeriveTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.DerivativeTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.DerivativeTests.tearDownClass.__func__)
    setUp=fixtures.DerivativeTests.setUp
    create=fixtures.DerivativeTests.create
    document=fixtures.DerivativeTests.document

    def derive(self,document,revision,**kwargs):
        return derive.derive(self.config,self.business,document,revision,inspector=inspection,**kwargs)

    def test_exact_revision_idempotency_read_never_runs_browser_and_failed_is_cached(self):
        _,document,revision,job=self.document();renderer=FakeRenderer()
        first=self.derive(document,revision,renderer=renderer)
        second=self.derive(document,revision,renderer=renderer)
        self.assertEqual(first,second);self.assertEqual(renderer.calls,1)
        with connect(self.config) as db, patch.object(rb.Renderer,'render',side_effect=AssertionError('read ran browser')):
            self.assertEqual(derive.derived(db,self.business,document,revision),first)
            self.assertIsNone(derive.derived(db,uuid4(),document,revision))
            self.assertIsNone(derive.derived(db,self.business,document,uuid4()))
        _,document,revision,job=self.document()
        with patch.object(renderer,'render',side_effect=RuntimeError('PRIVATE_DIAGNOSTIC')) as render:
            failure=self.derive(document,revision,renderer=renderer)
            self.assertEqual(self.derive(document,revision,renderer=renderer),failure)
            self.assertEqual(render.call_count,1)
            self.assertEqual(failure['status'],'failed');self.assertIsNone(failure['canonical_text'])
            self.assertNotIn('PRIVATE_DIAGNOSTIC',str(failure))

    def test_blocked_receipt_keeps_text_but_invalid_encoding_never_renders(self):
        _,document,revision,job=self.document(b'<base href="/"><h1>Units 5</h1>')
        output=self.derive(document,revision,renderer=FakeRenderer())
        self.assertEqual(output['status'],'ready')
        with connect(self.config) as db:
            self.assertEqual(ds.source(db,self.business,document,revision)['presentation_state'],'blocked')
        _,document,revision,job=self.document(b'\xff')
        renderer=FakeRenderer();self.assertEqual(self.derive(document,revision,renderer=renderer)['status'],'failed')
        self.assertEqual(renderer.calls,0)

    def test_unconfigured_renderer_reports_unavailable_with_scoped_read_and_preserves_queue(self):
        _,document,revision,job=self.document()
        with patch.object(policy,'renderer_version',return_value=policy.RENDERER_VERSION+':unconfigured'):
            with connect(self.config) as db, patch.object(ds,'source',side_effect=AssertionError('read checked raw')):
                self.assertEqual(derive.derived(db,self.business,document,revision)['status'],'unavailable')
                self.assertIsNone(derive.derived(db,uuid4(),document,revision))
                self.assertIsNone(derive.derived(db,self.business,document,uuid4()))
            with patch.object(rb.Renderer,'render',side_effect=AssertionError('unconfigured render')):
                self.assertEqual(self.derive(document,revision)['status'],'unavailable')
                self.assertFalse(derive.work_once(self.config))
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM report_derivation_jobs WHERE id=%s',(job['id'],)).fetchone()['status'],'pending')
            self.assertIsNone(ds.result(db,self.business,document,revision))

    def test_different_image_or_policy_needs_new_result_old_receipts_survive(self):
        _,document,revision,job=self.document();renderer=FakeRenderer()
        first=self.derive(document,revision,renderer=renderer)
        with patch.object(policy,'renderer_version',return_value='fixture-renderer-image-2'):
            with connect(self.config) as db: self.assertIsNone(derive.derived(db,self.business,document,revision))
            second=self.derive(document,revision,renderer=renderer)
            self.assertNotEqual(first['renderer_version'],second['renderer_version'])
        with patch.object(policy,'POLICY_VERSION','fixture-policy-2'):
            third=self.derive(document,revision,renderer=renderer)
            self.assertNotEqual(first['policy_version'],third['policy_version'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM report_derivatives WHERE revision_id=%s',(revision,)).fetchone()['n'],3)
        self.assertEqual(renderer.calls,3)

    def test_render_does_not_hold_memory_or_document_lock_and_deletion_is_rechecked(self):
        _,document,revision,job=self.document()
        entered,release=threading.Event(),threading.Event()
        renderer=FakeRenderer();render=renderer.render
        def blocked(raw,job_id):
            entered.set();release.wait(5);return render(raw,job_id)
        with patch.object(renderer,'render',side_effect=blocked), ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.derive,document,revision,renderer=renderer)
            self.assertTrue(entered.wait(5))
            with connect(self.config) as db, db.transaction():
                db.execute("SET LOCAL statement_timeout='2s'")
                from decision_room.memory import service as memory
                memory.lock(db,self.business)
                from decision_room.reports import store
                store.lock(db,document)
                db.execute('UPDATE report_documents SET deleted_at=now() WHERE id=%s',(document,))
            release.set()
            self.assertEqual(future.result(5)['status'],'failed')

    def test_sigkill_releases_global_and_job_locks_and_recovers_same_job(self):
        _,document,revision,job=self.document()
        ready=self.root/'render-started'
        script='''import os,sys,time
from pathlib import Path
from dataclasses import replace
from decision_room.config import Config
from decision_room.reports.derive import derive
class Render:
 def render(self,raw,job):
  Path(sys.argv[5]).write_text(str(job));time.sleep(60)
derive(replace(Config.load(),storage=Path(sys.argv[4])),sys.argv[1],sys.argv[2],sys.argv[3],renderer=Render(),inspector=lambda raw:dict(state='allowed',reason=None))
'''
        process=subprocess.Popen([sys.executable,'-c',script,str(self.business),str(document),str(revision),str(self.config.storage),str(ready)],
            env={**os.environ,'DECISION_ROOM_DATABASE_URL':self.config.dsn,'OPENAI_API_KEY':'','PYTHONDONTWRITEBYTECODE':'1'})
        def stop():
            if process.poll() is None: process.kill()
            process.wait(timeout=5)
        self.addCleanup(stop)
        deadline=time.monotonic()+8
        while not ready.exists() and time.monotonic()<deadline: time.sleep(.03)
        self.assertTrue(ready.exists());self.assertEqual(ready.read_text(),str(job['id']))
        process.send_signal(signal.SIGKILL);process.wait(timeout=5)
        output=self.derive(document,revision,renderer=FakeRenderer())
        self.assertEqual(output['status'],'ready')
        with connect(self.config) as db:
            row=db.execute('SELECT * FROM report_derivation_jobs WHERE id=%s',(job['id'],)).fetchone()
            self.assertEqual(row['attempts'],2)
            self.assertEqual(row['status'],'ready')

    @unittest.skipUnless((rb.ROOT/'.local/report-browser-runtime.json').is_file(),'Build the contained report browser for native tests.')
    def test_native_service_publishes_exact_text_pixels_and_version(self):
        _,document,revision,job=self.document(b'<h1>Units 5</h1><p>Delta -2</p>')
        output=self.derive(document,revision)
        self.assertEqual(output['status'],'ready')
        self.assertIn('Delta -2',output['canonical_text'])
        self.assertEqual(output['renderer_version'],policy.renderer_version())
        rb.validate_snapshot(output['snapshot_html'])
        with connect(self.config) as db:
            row=ds.source(db,self.business,document,revision)
            self.assertEqual(row['canonical_sha256'],output['canonical_sha256'])
            self.assertEqual(row['inventory_sha256'],output['inventory_sha256'])
            self.assertEqual(row['presentation_state'],'allowed')
            from decision_room.reports import reading
            from decision_room.memory import retrieval
            opened=reading.chat_document(db,self.business,document)
            self.assertEqual(opened['text'],output['canonical_text'])
            self.assertIn(str(revision),opened['version'])
            self.assertIn(output['canonical_sha256'],opened['version'])
            self.assertEqual(retrieval.engine_current(db,self.business,dict(id=str(document),version=opened['version'])),True)
            self.assertIsNone(reading.chat_document(db,uuid4(),document))
            shown=reading.view(db,dict(business_id=self.business,id=document),dict(id=revision,raw=row['raw']))
            self.assertEqual((shown['mode'],shown['canonical_text']),('snapshot',output['canonical_text']))
            self.assertNotIn('<h1>',shown['srcdoc'])
