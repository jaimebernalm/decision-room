"""Hard per-run dollar ceiling (P4): token limits priced at the catalogue's worst rates."""
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from decision_room.config import Config
from decision_room.engine import costs, job_profile

BASE = dict(input_tokens=6_000_000, output_tokens=128_000, output_per_call=16_000, calls=60, active_seconds=1_200)


class CeilingTests(unittest.TestCase):
    def config(self, **changes):
        return replace(Config('dbname=unused', Path('/nonexistent')), **changes)

    def test_bound_prices_every_token_at_the_worst_rate(self):
        self.assertEqual(costs.ceiling(BASE), Decimal('1.596'))
        worst = max(Decimal(r) for r in ('0.20', '0.25'))  # long input, long cache write
        self.assertEqual(costs.WORST_INPUT, worst)
        self.assertEqual(costs.WORST_OUTPUT, Decimal('0.75'))

    def test_fit_reduces_input_until_the_bound_is_within_the_cap(self):
        limits, ceiling = costs.fit(BASE, '1.00', 'gpt-6-luna')
        self.assertEqual(limits['input_tokens'], 3_616_000)
        self.assertEqual({k: limits[k] for k in BASE if k != 'input_tokens'}, {k: BASE[k] for k in BASE if k != 'input_tokens'})
        self.assertLessEqual(costs.ceiling(limits), Decimal('1.00'))
        self.assertEqual(ceiling['bound_usd'], str(costs.ceiling(limits)))
        self.assertEqual(ceiling['catalogue'], costs.VERSION)
        generous, _ = costs.fit(BASE, '5', 'gpt-6-luna')
        self.assertEqual(generous['input_tokens'], BASE['input_tokens'])

    def test_unpriced_model_impossible_or_invalid_caps_are_refused(self):
        with self.assertRaises(ValueError):
            costs.fit(BASE, '1.00', 'another-model')
        with self.assertRaises(ValueError):
            costs.fit(BASE, '0.05', 'gpt-6-luna')  # the output limit alone costs 0.096
        with self.assertRaises(ValueError):
            costs.fit(BASE, '0', 'gpt-6-luna')
        for value in ('0', '-1', 'mucho'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.config(engine_usd_cap=value)

    def test_engine_jobs_freeze_fitted_limits_and_the_ceiling(self):
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': 'sha256:' + 'a' * 64}):
            kind, settings = job_profile.selection(self.config(engine_usd_cap='0.50'), {'engine_kind': 'opencode'})
        self.assertEqual(kind, 'opencode')
        self.assertLessEqual(costs.ceiling(settings['limits']), Decimal('0.50'))
        self.assertEqual(settings['usd_ceiling']['cap_usd'], '0.50')
        self.assertEqual(settings['usd_ceiling']['model'], settings['profile']['model'])
        self.assertEqual(job_profile.selection(self.config(), {'engine_kind': 'legacy'}), ('legacy', {}))


if __name__ == '__main__':
    unittest.main()
