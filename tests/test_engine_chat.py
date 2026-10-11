"""F4 chat phase 1: v1 reports are found and opened through their canonical text only."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from decision_room import chat_agent
from decision_room.database import connect
from decision_room.memory import retrieval, service as memory
from decision_room.reports import reading
from tests import test_engine_jobs as engine, test_web as web
from tests.test_engine_view import CLEAN
from tests.test_memory import content

DERIVED = dict(status='ready', canonical_text='Ventas por canal: Web propia crece 12 unidades.',
               canonical_sha256='c' * 64, policy_version='v1-snapshot-only-1',
               renderer_version='v1-container-raster-1:sha256:' + 'd' * 64, snapshot_html='<p>captura</p>')


class EngineChatTests(unittest.TestCase):
    setUpClass = classmethod(engine.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(engine.EngineJobTests.tearDownClass.__func__)
    setUp = engine.EngineJobTests.setUp
    create = engine.EngineJobTests.create
    pinned = engine.EngineJobTests.pinned
    fake_runtime = engine.EngineJobTests.fake_runtime
    http = web.WebTests.http

    def delivered(self):
        self.fake_runtime()
        from tests.engine_fakes import FakeRuntime
        FakeRuntime.payload = CLEAN
        job = self.create(engine_kind='opencode', title='Informe de ventas')
        self.ws.run_job(job)
        row = self.ws.row(job)
        self.derived = dict(DERIVED)
        patcher = patch.object(reading, 'derived_for', lambda db, document, revision: self.derived)
        patcher.start(); self.addCleanup(patcher.stop)
        return row

    def request(self, **values):
        return retrieval.Request.model_validate(dict(dict(tool='search_reports', query='', limit=5, id=''), **values))

    def test_search_and_open_return_canonical_text_with_an_exact_version(self):
        row = self.delivered(); business = row['business_id']; document = str(row['report_document_id'])
        with connect(self.config) as db:
            items, deps = retrieval._engine_reports(self.config, db, {'business_id': business}, {'analysis_id': None}, self.request())
            opened, open_deps = retrieval.retrieve(self.config, db, None, dict(tool='open_report', query='', limit=1, id=document),
                                                   manifest={'business_id': business, 'session_id': None})
        self.assertEqual([i['id'] for i in items], [document])
        self.assertEqual(items[0]['origin'], 'engine_html')
        version = items[0]['version']
        self.assertTrue(version.startswith('engine:') and 'c' * 64 in version and DERIVED['renderer_version'] in version)
        with connect(self.config) as db:
            current = db.execute('SELECT current_revision_id FROM report_documents WHERE id=%s', (document,)).fetchone()
        self.assertEqual(version.split(':')[1], str(current['current_revision_id']))
        self.assertEqual(opened['text'], DERIVED['canonical_text'])
        self.assertEqual(opened['evidence_ids'], [])
        self.assertIn('sin verificación', opened['evidence_class'].replace('verificación automática', 'sin verificación'))
        self.assertNotIn('Ventas</h1>', str(opened))  # never the raw markup
        self.assertEqual(open_deps, [dict(kind='engine_report', id=document, version=version)])
        self.assertEqual(deps, open_deps)

    def test_text_changes_and_withdrawal_invalidate_what_the_chat_read(self):
        row = self.delivered(); business = row['business_id']; document = str(row['report_document_id'])
        with connect(self.config) as db:
            dep = retrieval._engine_reports(self.config, db, {'business_id': business}, {'analysis_id': None}, self.request())[1][0]
            self.assertTrue(retrieval.engine_current(db, business, dep))
            self.derived = dict(DERIVED, canonical_sha256='e' * 64)  # another renderer produced other text
            self.assertFalse(retrieval.engine_current(db, business, dep))
            self.derived = dict(DERIVED)
        memory.change(self.config, business, action='declare', request_key=uuid4().hex, content=content())
        with connect(self.config) as db:
            self.assertFalse(retrieval.engine_current(db, business, dep))
            self.assertIsNone(reading.chat_document(db, business, document))

    def test_not_ready_or_scripted_without_text_is_not_offered(self):
        row = self.delivered(); business = row['business_id']
        for value in (None, dict(DERIVED, status='pending', canonical_text=None), dict(DERIVED, status='failed', canonical_text=None)):
            with self.subTest(value=value):
                self.derived = value
                with connect(self.config) as db:
                    self.assertEqual(reading.chat_documents(db, business), [])
                    with self.assertRaises(ValueError):
                        retrieval.retrieve(self.config, db, None, dict(tool='open_report', query='', limit=1,
                                                                       id=str(row['report_document_id'])),
                                           manifest={'business_id': business, 'session_id': None})

    def test_v1_sources_are_never_labelled_reviewed(self):
        context = dict(chat_context=dict(profile={}, memories=[], catalog=dict(items=[])),
                       retrievals=[dict(ordinal=0, request=dict(tool='open_report'), response=dict(origin='engine_html', id='x')),
                                   dict(ordinal=1, request=dict(tool='open_report'), response=dict(id='y'))])
        sources = chat_agent.sources_for(context)
        self.assertEqual(sources['tool/0']['label'], 'Informe')
        self.assertEqual(sources['tool/1']['label'], 'Informe revisado')

    def test_a_withdrawal_during_ranking_is_detected_after_it(self):
        row = self.delivered(); business = row['business_id']
        from decision_room.memory import context as ctx
        original = retrieval.semantic.rank

        def rank_then_change(*args, **kwargs):
            result = original(*args, **kwargs)
            self.derived = dict(DERIVED, canonical_sha256='f' * 64)  # rendered again while ranking
            return result
        with patch.object(retrieval.semantic, 'rank', rank_then_change), connect(self.config) as db:
            with self.assertRaises(ctx.StaleContext):
                retrieval._engine_reports(self.config, db, {'business_id': business}, {'analysis_id': None},
                                          self.request(query='ventas'))
