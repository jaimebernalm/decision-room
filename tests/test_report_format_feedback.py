import json
import unittest

from decision_room.reports import contract


class FormatFeedbackTests(unittest.TestCase):
    def test_shape_error_paths_are_specific_bounded_and_do_not_echo_values(self):
        cases = [({'limitations': ['private-value']}, '/limitations'),
                 ({'summary': {'private-value': 1}}, '/summary'),
                 ({'findings': [{'key': 'x', 'next_step': ['private-value']}]}, '/findings/0/next_step'),
                 ({'findings': [{'key': 'x', 'facts': [{'private-value': 1}]}]}, '/findings/0/facts'),
                 ({'findings': [{'key': 'x'}, {'key': 'x'}]}, '/findings'),
                 ({'numbers': {}}, '/numbers'), ({'charts': [{}]}, '/charts'),
                 ({'private-value': 'private-value'}, '')]
        for changes, path in cases:
            with self.subTest(path=path):
                raw = json.dumps({'schema_version': 1, **changes}).encode()
                feedback = contract.format_feedback(raw)
                self.assertFalse(feedback['valid'])
                self.assertEqual(feedback['errors'][0]['path'], path)
                self.assertNotIn('private-value', json.dumps(feedback))
                self.assertLess(len(json.dumps(feedback)), 1024)
                self.assertEqual(contract.load(raw)[0]['summary'], raw.decode())
        for raw in (b'{', b'', b'[]', b'{"schema_version":NaN}', b'['*1100):
            self.assertFalse(contract.format_feedback(raw)['valid'])
            self.assertIn('report_format_fallback', contract.load(raw)[2])

    def test_valid_shape_does_not_change_or_certify_number_references(self):
        raw = b'{"schema_version":1,"limitations":"","numbers":[{"key":"unresolved"}]}'
        self.assertEqual(contract.format_feedback(raw), {'valid': True, 'errors': []})
        self.assertEqual(contract.load(raw)[1], [{'key': 'unresolved'}])
