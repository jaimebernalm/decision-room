"""Native reports are the default engine job; machines without the pinned engine keep working with legacy."""
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from decision_room.config import Config
from decision_room.engine import job_profile

IMAGE = {'DECISION_ROOM_ENGINE_IMAGE_ID': 'sha256:' + 'a' * 64}


class NativeDefaultTests(unittest.TestCase):
    def setUp(self):
        self.config = Config('dbname=unused', Path('/nonexistent'))

    def test_defaults_are_native_blocks_with_room_for_two_check_passes(self):
        names = ('DECISION_ROOM_REPORT_ENGINE', 'DECISION_ROOM_REPORT_FORMAT', 'DECISION_ROOM_ENGINE_CALLS')
        with patch.dict('os.environ', {k: v for k, v in os.environ.items() if k not in names}, clear=True):
            loaded = Config.load()
        for config in (self.config, loaded):
            self.assertEqual((config.report_engine, config.report_format, config.engine_calls), ('opencode', 'blocks', 90))
        with patch.dict('os.environ', IMAGE):
            kind, settings = job_profile.selection(self.config, {})
        self.assertEqual(kind, 'opencode')
        self.assertEqual(settings['profile']['format'], 'blocks')
        self.assertEqual(settings['limits']['calls'], 90)

    def test_missing_engine_image_falls_back_to_legacy_only_for_the_default(self):
        with patch.dict('os.environ', {'DECISION_ROOM_ENGINE_IMAGE_ID': ''}):
            self.assertEqual(job_profile.selection(self.config, {}), ('legacy', {}))
            with self.assertRaises(ValueError):
                job_profile.selection(self.config, {'engine_kind': 'opencode'})
            with self.assertRaises(ValueError):
                job_profile.selection(self.config, {'engine_format': 'blocks'})

    def test_owner_can_keep_legacy_or_html_through_configuration(self):
        with patch.dict('os.environ', {**IMAGE, 'DECISION_ROOM_REPORT_ENGINE': 'legacy'}):
            self.assertEqual(job_profile.selection(Config.load(), {}), ('legacy', {}))
        with patch.dict('os.environ', IMAGE):
            _, settings = job_profile.selection(replace(self.config, report_format='html'), {})
        self.assertEqual(settings['profile']['version'], 'html-v1-budget-1')
        with patch.dict('os.environ', {'DECISION_ROOM_REPORT_FORMAT': 'pdf'}), self.assertRaises(ValueError):
            Config.load()


if __name__ == '__main__':
    unittest.main()
