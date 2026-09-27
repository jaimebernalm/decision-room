"""Exact chart projections for context attachments, including invalid selections."""
import unittest
from uuid import uuid4
from decision_room.context_references import resolve, normalize
from decision_room.web.dashboard import presentation
from decision_room.web.errors import WebError
from test_client_report import sample

class ContextReferenceTests(unittest.TestCase):
    def test_chart_keeps_exact_values_and_full_series(self):
        data = sample() | dict(id=str(uuid4()), approved_sha256='approved', analysis_id=str(uuid4()))
        reference = dict(report_id=data['id'], report_version='approved', kind='chart', element_key='trend')
        item = resolve(reference, data)
        self.assertEqual(item['content'], presentation(data)['charts'][0])
        self.assertEqual([p['value'] for p in item['content']['points']], ['10.00', '20.005'])
        self.assertNotIn('code', item['content'])
        with self.assertRaises(WebError): resolve(reference, data | {'publishable': False})
        with self.assertRaises(WebError): resolve(reference | {'report_version': 'other'}, data)
        with self.assertRaises(WebError): resolve(reference | {'element_key': 'invented'}, data)

    def test_invalid_shapes_are_user_errors(self):
        reference = dict(report_id=str(uuid4()), report_version='approved', kind='chart', element_key='trend')
        for values in (None, {}, [None], [reference | {'kind': {}}], [reference | {'element_key': 4}], [reference | {'preview': 'injected'}]):
            with self.subTest(values=values), self.assertRaises(WebError): normalize(values)
