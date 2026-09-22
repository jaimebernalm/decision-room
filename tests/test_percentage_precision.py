"""Percent prose follows its displayed precision without double rounding."""
import unittest
from decision_room.agent.review_contract import checks


class PercentagePrecisionTests(unittest.TestCase):
    def check(self, displayed, after='116.149'):
        ref = lambda key: {'execution_id': 'e', 'metric': key}
        observation = {'execution_id': 'e', 'status': 'completed', 'current': True,
                       'result': {'metrics': {'before': '100', 'after': after, 'growth': '16.149'},
                                  'evidence': [{'metric': key} for key in ['before', 'after', 'growth']]}}
        report = {'summary': displayed, 'claims': [{'key': 'growth', 'evidence': [ref('growth')]}],
                  'checks': [{'key': 'growth', 'operation': 'percent_change', 'actual': ref('growth'),
                              'operands': [ref('before'), ref('after')], 'tolerance': '0.01'}]}
        return all(c['passed'] for c in checks(report, [observation]))

    def test_valid_display_precision_is_preserved(self):
        for text in ['16 %', '16.1 %', '16,15 %', '16.149 %']:
            with self.subTest(text=text): self.assertTrue(self.check(text))

    def test_wrong_value_or_claimed_precision_is_rejected(self):
        for text in ['17 %', '16.2 %', '16.13 %', '16.10 %', '16.150 %']:
            with self.subTest(text=text): self.assertFalse(self.check(text))

    def test_original_arithmetic_is_rounded_once(self):
        # 16.149 -> 16.1 at one decimal; rounding through 16.15 would give 16.2.
        self.assertTrue(self.check('16.1 %'))
        self.assertFalse(self.check('16.2 %'))


if __name__ == '__main__': unittest.main()
