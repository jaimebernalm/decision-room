"""Account for missing usage and workers killed before their finally block."""
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from decision_room.agent.model import ModelSettings
from decision_room.evaluation.assess import summary, token_accounting
from decision_room.evaluation.runner import run_batch, write


class EvaluationResourceTests(unittest.TestCase):
    def test_missing_usage_is_unknown_not_zero(self):
        result = token_accounting([{'usage': {'prompt_tokens': 10, 'completion_tokens': 2}}, {'usage': None}])
        self.assertEqual((result['known_input_tokens'], result['known_output_tokens']), (10, 2))
        self.assertEqual(result['missing_input_usage_calls'], 1)
        self.assertEqual(result['missing_output_usage_calls'], 1)
        self.assertIsNone(result['input_tokens'])
        self.assertIsNone(result['output_tokens'])
        self.assertFalse(result['token_usage_complete'])

    def test_zero_native_and_partial_usage(self):
        result = token_accounting([{'usage': {'total_input_tokens': 5, 'total_output_tokens': 0}}])
        self.assertEqual((result['input_tokens'], result['output_tokens']), (5, 0))
        self.assertTrue(result['token_usage_complete'])
        result = token_accounting([{'usage': {'prompt_tokens': 5, 'completion_tokens': None}}])
        self.assertEqual(result['input_tokens'], 5)
        self.assertIsNone(result['output_tokens'])
        self.assertFalse(token_accounting([], snapshot_complete=False)['token_usage_complete'])
        self.assertIsNone(token_accounting([], snapshot_complete=False)['input_tokens'])

    def test_invalid_counters_are_not_reported_as_usage(self):
        result = token_accounting([{'usage': {'prompt_tokens': True, 'completion_tokens': -1}}])
        self.assertIsNone(result['input_tokens'])
        self.assertIsNone(result['output_tokens'])

    def test_summary_preserves_known_usage_without_claiming_an_exact_total(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary); job = directory/'daily-1'; job.mkdir()
            write(directory/'manifest.json', {'jobs': ['daily-1']})
            write(job/'state.json', {'status': 'failed', 'scenario': 'daily', 'source_stable': True,
                                      'timings': {'review': 1200}, 'timings_lower_bound': ['review']})
            write(job/'resources.json', {'calls': [
                {'usage': {'prompt_tokens': 10, 'completion_tokens': 2}}, {'usage': None}]})
            row = summary(directory)['runs'][0]
            self.assertEqual(row['model_calls'], 2)
            self.assertTrue(row['seconds_is_lower_bound'])
            self.assertEqual(row['seconds'], 1200)
            self.assertEqual(row['known_input_tokens'], 10)
            self.assertEqual(row['known_output_tokens'], 2)
            self.assertIsNone(row['input_tokens'])
            self.assertIsNone(row['output_tokens'])
            self.assertFalse(row['token_usage_complete'])

    def interrupted_batch(self, outcome, collection_failure=False):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            def collect(config, state, job):
                state['research_id'] = 'durable-research-recovered'
                if collection_failure:
                    raise RuntimeError('database unavailable while collecting')
                write(job/'resources.json', {'calls': [{'phase': 'research', 'usage': None}], 'executions': []})
            with patch('decision_room.evaluation.runner.source_version', return_value='version'), \
                 patch('decision_room.evaluation.runner.subprocess.check_output', return_value='test-head\n'), \
                 patch('decision_room.evaluation.runner.subprocess.run', side_effect=outcome), \
                 patch('decision_room.evaluation.runner.time.monotonic', side_effect=[10, 1250]), \
                 patch('decision_room.evaluation.runner.collect', side_effect=collect):
                run_batch(directory, ['daily'], 1, ModelSettings('test'))
            job = directory/'daily-1'
            state = json.loads((job/'state.json').read_text())
            self.assertEqual(state['status'], 'interrupted')
            self.assertEqual(state['research_id'], 'durable-research-recovered')
            self.assertEqual(state['timings']['import'], 1240)
            self.assertEqual(state['completed_phases'], [])
            self.assertTrue(state['source_stable'])
            if collection_failure:
                self.assertIn('database unavailable', state['collection_issue'])
            else:
                self.assertIsNone(json.loads((job/'resources.json').read_text())['calls'][0]['usage'])
            return state

    def test_timeout_collects_durable_state_and_elapsed_phase_time(self):
        state = self.interrupted_batch(subprocess.TimeoutExpired('worker', 1200))
        self.assertIn('1200 seconds', state['issue'])

    def test_unexpected_exit_preserves_original_issue_when_collection_fails(self):
        state = self.interrupted_batch([subprocess.CompletedProcess('worker', 137)], collection_failure=True)
        self.assertIn('exited unexpectedly', state['issue'])


if __name__ == '__main__':
    unittest.main()
