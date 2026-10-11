"""Home cards from current native v1 reports: currency rechecked, disputes and incomplete checks visible."""
import unittest
import unittest.mock
from unittest.mock import patch

from decision_room.database import connect
from decision_room.engine import api, check_contract as contract
from decision_room.web import home
from tests.test_native_checks import IndependentClient, IndependentRuntime


def unlocated(data):
    p = data['priorities'][0]
    return dict(version=contract.VERSION, revision_sha256=data['revision_sha256'], coverage_notes='', items=[
        dict(priority_id=p['block_id'], quote='5 unidades', start=None, end=None, status='discrepancy',
             independent_value='4 unidades', method='Sumar CSV; caso simulado.', message='Discrepancia simulada.')])


class NativeHomeTests(unittest.TestCase):
    from tests import test_engine_jobs as product
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime

    def deliver(self, *checker):
        self.fake_runtime(); IndependentRuntime.payloads = []; IndependentClient.checker_results = list(checker)
        p = patch.object(api, 'Runtime', IndependentRuntime); p.start(); self.addCleanup(p.stop)
        job = self.create(engine_kind='opencode', engine_format='blocks'); self.ws.run_job(job)
        row = self.ws.row(job)
        self.assertEqual(row['status'], 'completed', row['issue'])
        return next(x for x in self.ws.listing() if str(x['id']) == str(job))

    def test_unlocated_discrepancy_marks_figures_of_its_priority(self):
        entry = self.deliver(unlocated, unlocated)
        cards = home.engine_figures(self.ws, [entry])
        self.assertEqual([c['title'] for c in cards], ['Total'])
        card = cards[0]
        self.assertEqual(card['source']['origin'], 'engine_blocks')
        self.assertFalse(card['source']['reviewed'])
        self.assertTrue(card['content']['disputed'])
        self.assertFalse(card['content']['check_incomplete'])
        self.assertEqual(card['content']['value'], '5')

    def test_incomplete_check_is_visible_on_the_card(self):
        entry = self.deliver(lambda _: dict(invalid=True))
        cards = home.engine_figures(self.ws, [entry])
        self.assertTrue(cards and cards[0]['content']['check_incomplete'])

    def test_report_withdrawn_after_listing_yields_no_cards(self):
        entry = self.deliver()
        with connect(self.config) as db:
            db.execute("UPDATE report_documents SET stale_reason='data_changed' WHERE id=%s",
                       (entry['report_document_id'],))
        self.assertEqual(home.engine_figures(self.ws, [entry]), [])


class RendererIsolationTests(unittest.TestCase):
    """The HTML renderer worker never touches native block reports (found on a real smoke copy)."""
    from tests import test_engine_jobs as product
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime
    deliver = NativeHomeTests.deliver

    def test_worker_refresh_and_derive_skip_native_documents(self):
        from decision_room.reports import derive, derive_policy, reading
        entry = self.deliver()
        with patch.object(derive_policy, 'renderer_version', return_value='v1-container-raster-2:sha256:' + 'a' * 64):
            derive.refresh(self.config)
            self.assertFalse(derive.work_once(self.config))
            renderer = unittest.mock.Mock(side_effect=AssertionError('renderer called'))
            with self.assertRaises(ValueError):
                derive.derive(self.config, entry['business_id'], entry['report_document_id'],
                              entry['engine_report']['revision_id'], renderer=renderer)
            renderer.assert_not_called()
            from decision_room.reports import derivative_store
            with connect(self.config) as db, self.assertRaises(ValueError):
                derivative_store.enqueue(db, entry['business_id'], entry['report_document_id'],
                                         entry['engine_report']['revision_id'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM report_derivation_jobs WHERE document_id=%s',
                                        (entry['report_document_id'],)).fetchone()['n'], 0)
        with reading.read(self.config, entry['business_id'], entry['report_document_id']) as (db, doc, rev):
            self.assertEqual(reading.view(db, doc, rev)['mode'], 'blocks')
        self.assertEqual(len(home.engine_figures(self.ws, [entry])), 1)


class BlockSelectionTests(unittest.TestCase):
    """Chat selection of a native block reads the stored projection and carries its notices."""
    from tests import test_engine_jobs as product
    setUpClass = classmethod(product.EngineJobTests.setUpClass.__func__)
    tearDownClass = classmethod(product.EngineJobTests.tearDownClass.__func__)
    setUp = product.EngineJobTests.setUp
    create = product.EngineJobTests.create
    pinned = product.EngineJobTests.pinned
    fake_runtime = product.EngineJobTests.fake_runtime
    deliver = NativeHomeTests.deliver

    def resolve(self, entry, key):
        from decision_room import context_references
        reference = dict(source_id=entry['report_document_id'], source_version=entry['engine_report']['revision_id'],
                         kind='engine_block', element_key=key)
        with connect(self.config) as db:
            return context_references.resolve_source(context_references.normalize([reference])[0], db, self.business['id'])

    def test_figure_under_priority_discrepancy_carries_the_notice(self):
        entry = self.deliver(unlocated, unlocated)
        selected = self.resolve(entry, 'b1-3')
        self.assertEqual(selected['authority'], 'engine_report')
        self.assertIn('Total: 5', selected['content']['statement'])
        self.assertIn('Cifra en revisión', selected['content']['statement'])
        self.assertIn('4 unidades', selected['content']['statement'])

    def test_incomplete_check_is_stated_and_stored_projection_survives_a_new_projector(self):
        from decision_room.engine import blocks
        entry = self.deliver(lambda _: dict(invalid=True))
        before = self.resolve(entry, 'b1-3')['content']['statement']
        self.assertIn('no se completó', before)
        with patch.object(blocks, 'parse', side_effect=AssertionError('must not reparse')), \
                patch.object(blocks, 'PROJECTOR_VERSION', 'bloques-proyector-99'):
            self.assertEqual(self.resolve(entry, 'b1-3')['content']['statement'], before)


class SelectionScopeTests(BlockSelectionTests):
    def test_priority_selection_includes_descendant_discrepancies_and_withdrawal_is_refused(self):
        entry = self.deliver(self.located, self.located)
        statement = self.resolve(entry, 'b1')['content']['statement']
        self.assertIn('Cifra en revisión', statement)
        with connect(self.config) as db:
            db.execute("UPDATE report_documents SET stale_reason='data_changed' WHERE id=%s", (entry['report_document_id'],))
        from decision_room.web.errors import WebError
        with self.assertRaises(WebError):
            self.resolve(entry, 'b1')

    @staticmethod
    def located(data):
        p = data['priorities'][0]; start = p['text'].index('5 unidades')
        return dict(version=contract.VERSION, revision_sha256=data['revision_sha256'], coverage_notes='', items=[
            dict(priority_id=p['block_id'], quote='5 unidades', start=start, end=start + 10, status='discrepancy',
                 independent_value='4 unidades', method='Sumar CSV; caso simulado.', message='Discrepancia simulada.')])
