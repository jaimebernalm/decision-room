"""Lossless model-context deduplication must preserve review decisions and evidence."""
from copy import deepcopy
import unittest

from decision_room.agent.review_context import model_context


class ReviewContextTests(unittest.TestCase):
    def test_deduplication_preserves_originals_and_distinct_history(self):
        draft = {'title': 'Current draft', 'claims': ['current claim']}
        previous = {'title': 'Old draft', 'claims': ['withdrawn claim']}
        context = {
            'report': draft,
            'observations': [{'execution_id': 'e1', 'code': 'print(1)', 'logs': {}, 'result': {}}],
            'conversation': [
                {'step': 1, 'execution_id': 'e1', 'action': {'action': 'execute', 'code': 'print(1)', 'report': None}},
                {'step': 2, 'execution_id': None, 'action': {'action': 'submit', 'code': '', 'report': previous}},
                {'step': 3, 'execution_id': None, 'action': {'action': 'revise', 'code': '', 'report': None, 'message': 'Unsupported definition'}},
                {'step': 4, 'execution_id': None, 'action': {'action': 'ask_owner', 'code': '', 'report': None}, 'owner_answer': {'text': 'Row total', 'disposition': 'answered'}},
                {'step': 5, 'execution_id': None, 'action': {'action': 'submit', 'code': '', 'report': draft}},
            ],
        }
        original = deepcopy(context)
        packed = model_context(context, 'reviewer')
        self.assertEqual(context, original)
        self.assertEqual(packed['observations'][0]['code'], 'print(1)')
        self.assertEqual(packed['conversation'][0]['code_reference']['execution_id'], 'e1')
        self.assertEqual(packed['conversation'][1]['action']['report'], previous)
        self.assertEqual(packed['conversation'][2], original['conversation'][2])
        self.assertEqual(packed['conversation'][3], original['conversation'][3])
        self.assertEqual(packed['conversation'][4]['report_reference'], 'report')
        self.assertEqual(packed['report'], draft)
        # A different program must never be replaced merely because IDs match.
        context['conversation'][0]['action']['code'] = 'print(2)'
        self.assertEqual(model_context(context, 'reviewer')['conversation'][0]['action']['code'], 'print(2)')


if __name__ == '__main__':
    unittest.main()
