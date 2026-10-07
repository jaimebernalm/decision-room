"""Export occurrence identities and conservative labels, without model calls."""
from copy import deepcopy
import hashlib
import unittest

from decision_room.reports.verification_contract import canonical, figure_id, validate


class VerificationContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = b'{"unfinished":'
        self.document = {'summary': '🧾 Cantidad: 12; comparación: 12.'}
        self.ledger = {'contract_version': 1, 'draft_sha256': hashlib.sha256(self.raw).hexdigest(),
                       'verified_sha256': hashlib.sha256(canonical(self.document)).hexdigest(),
                       'renderer_version': 'fixture-v1', 'figures': [],
                       'summary': {'verified': 0, 'unverified': 0, 'uncertain': 0, 'corrected': 0}, 'issues': []}

    def figure(self, start=None, *, path='/summary', text='12'):
        start = self.document['summary'].index(text) if start is None else start
        end = start + len(text)
        return {'id': figure_id(self.ledger['verified_sha256'], path, start, end), 'path': path,
                'span': {'start': start, 'end': end}, 'text': text, 'value': '12', 'unit': None,
                'status': 'unverified', 'verified': False, 'corrected_from': None,
                'evidence': [], 'recommendation_id': None}

    def check(self, figures):
        ledger = deepcopy(self.ledger); ledger['figures'] = figures
        for figure in figures:
            ledger['summary'][figure['status']] += 1
        return validate(ledger, self.document, self.raw)

    def test_raw_malformed_document_survives_and_repeated_unicode_occurrences_differ(self):
        a = self.figure(); b = self.figure(self.document['summary'].rindex('12'))
        self.assertNotEqual(a['id'], b['id'])
        self.assertLess(a['span']['start'], len(self.document['summary'][:a['span']['start']].encode()))
        self.assertEqual(len(self.check([a, b])['figures']), 2)
        with self.assertRaises(ValueError):
            self.check([a, a])
        overlapping = self.figure(a['span']['start'] + 1, text='2')
        with self.assertRaises(ValueError):
            self.check([a, overlapping])

    def test_correction_does_not_imply_verified(self):
        corrected = {**self.figure(), 'status': 'corrected', 'corrected_from': '99'}
        result = self.check([corrected])
        self.assertEqual(result['summary']['corrected'], 1)
        self.assertEqual(result['summary']['verified'], 0)
        self.assertFalse(result['figures'][0]['verified'])
        corrected['verified'] = True
        with self.assertRaises(ValueError):
            self.check([corrected])
        corrected['evidence'] = [{'kind': 'observation', 'id': 'fixture', 'metric': 'total'}]
        self.assertTrue(self.check([corrected])['figures'][0]['verified'])

    def test_labels_values_and_evidence_cannot_contradict_each_other(self):
        for change in [{'status': 'verified'}, {'verified': True}, {'status': 'corrected'},
                       {'value': 12}, {'value': 'NaN'}, {'corrected_from': '99'},
                       {'evidence': [{'kind': 'url', 'id': 'fixture'}]}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check([{**self.figure(), **change}])
        valid = {**self.figure(), 'status': 'verified', 'verified': True,
                 'evidence': [{'kind': 'execution', 'id': 'fixture'}]}
        self.assertTrue(self.check([valid]))

    def test_raw_verified_document_text_and_hashes_are_bound(self):
        ledger = self.check([self.figure()])
        for raw, document in [(self.raw + b' ', self.document), (self.raw, {'summary': 'Different 12'})]:
            with self.assertRaises(ValueError):
                validate(ledger, document, raw)
        for change in [{'id': 'invented'}, {'text': '13'}, {'path': '/missing'},
                       {'span': {'start': True, 'end': 2}}, {'span': {'start': -1, 'end': 2}}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check([{**self.figure(), **change}])

    def test_json_pointer_escapes_and_arrays_are_unambiguous(self):
        self.document = {'a/b': [{'~': '12'}]}
        self.ledger['verified_sha256'] = hashlib.sha256(canonical(self.document)).hexdigest()
        figure = self.figure(0, path='/a~1b/0/~0')
        self.assertTrue(self.check([figure]))
        for path in ['/a~1b/00/~0', '/a~1b/1/~0', '/a~2b/0/~0', '/a~1b/-1/~0']:
            changed = {**figure, 'path': path, 'id': figure_id(self.ledger['verified_sha256'], path, 0, 2)}
            with self.assertRaises(ValueError):
                self.check([changed])

    def test_summary_is_partition_of_statuses_not_verification_gate(self):
        ledger = self.check([self.figure()])
        ledger['summary']['verified'] = 1
        with self.assertRaises(ValueError):
            validate(ledger, self.document, self.raw)
        ledger['summary']['verified'] = False
        with self.assertRaises(ValueError):
            validate(ledger, self.document, self.raw)


if __name__ == '__main__':
    unittest.main()
