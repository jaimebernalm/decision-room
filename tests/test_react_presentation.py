"""React receives the complete approved report, with exact values and no internal logs."""
import json
import unittest
from copy import deepcopy
from test_client_report import sample
from decision_room.web.dashboard import presentation
from decision_room.web.errors import WebError


class ReactPresentationTests(unittest.TestCase):
    def test_complete_claims_exact_values_and_public_evidence(self):
        data = sample()
        for index in range(4):
            claim = deepcopy(data['report']['claims'][0])
            claim['key'] = f'extra_{index}'
            data['report']['claims'].append(claim)
        result = presentation(data)
        self.assertEqual(len(result['claims']), 5)
        self.assertEqual(result['charts'][0]['points'][1]['value'], '20.005')
        self.assertEqual(result['charts'][0]['points'][1]['formatted'], '20,01')
        self.assertEqual(result['claims'][0]['evidence_details']['files'], ['ventas.csv'])
        self.assertIn('next_step', result['claims'][0])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('calculation-a', json.dumps(result))

    def test_invalid_and_held_reports_are_not_projected(self):
        data = sample()
        data['observations'][0]['current'] = False
        with self.assertRaises(WebError):
            presentation(data)
        data = sample()
        data['publishable'] = False
        with self.assertRaises(WebError):
            presentation(data)

    def test_table_contract_does_not_turn_into_a_chart(self):
        data = sample()
        data['report']['charts'][0]['kind'] = 'table'
        result = presentation(data)
        self.assertEqual(result['charts'][0]['kind'], 'table')
        self.assertEqual(len(result['charts'][0]['points']), 2)
