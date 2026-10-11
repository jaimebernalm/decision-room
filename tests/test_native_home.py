"""Home cards from current native v1 reports: currency rechecked, disputes and incomplete checks visible."""
import unittest
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


if __name__ == '__main__':
    unittest.main()
