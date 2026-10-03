"""Reverse actual immutable input copies, run real Docker, publish only stable evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import duckdb

from decision_room.order_verification import reverse_inputs, signature, verify
from decision_room.storage import digest
import test_execution as execution_tests


class PermutationTests(unittest.TestCase):
    def test_preserves_rows_types_nulls_duplicates_and_explicit_sequence(self):
        with tempfile.TemporaryDirectory() as folder:
            stage = Path(folder); (stage/'tables').mkdir()
            path = stage/'tables/input.parquet'
            with duckdb.connect() as db:
                db.execute('CREATE TABLE sample (sequence INTEGER, "arbitrary name" VARCHAR, n DECIMAL(20,4))')
                db.execute("INSERT INTO sample VALUES (3, NULL, 1.0001), (1, 'x', NULL), (1, 'x', NULL)")
                db.execute('COPY sample TO ? (FORMAT PARQUET)', [str(path)])
                before = db.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
                reverse_inputs(stage)
                after = db.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchall()
                self.assertEqual(after, list(reversed(before)))
                reverse_inputs(stage)
                self.assertEqual(db.execute('SELECT * FROM read_parquet(?)', [str(path)]).fetchall(), before)

    def test_signature_ignores_enumeration_not_values_or_precision(self):
        first = dict(metrics={'total': '1.00', 'from': '2026-01-01'}, series={'s':dict(unit='u', grain='category', points=[
            dict(label='b', value='3'), dict(label='a', value='2')])})
        other = deepcopy(first); other['metrics']['total'] = '1'; other['series']['s']['points'].reverse()
        self.assertEqual(signature(first), signature(other))
        other['metrics']['total'] = '1.000000000000000000000000000000000000001'
        self.assertNotEqual(signature(first), signature(other))
        self.assertEqual(signature({'metrics': {'n': '1e1000000000'}}),
                         signature({'metrics': {'n': '10e999999999'}}))

    def test_incomplete_second_run_cannot_accept_the_original_candidate(self):
        from uuid import uuid4
        for forced, payload in [('resource_limit', ''), (None, '{'), (None, json.dumps({
            'protocol': 1, 'status': 'failed', 'exit_code': 1, 'files': [],
            'logs': {'stdout': '', 'stderr': 'failure', 'stdout_truncated': False, 'stderr_truncated': False}}))]:
            with self.subTest(forced=forced, payload=payload), tempfile.TemporaryDirectory() as folder:
                stage = Path(folder); (stage / 'tables').mkdir()
                (stage / 'program.py').write_text('pass')
                (stage / 'request.json').write_text(json.dumps({'tables': {}}))
                backend = Mock()
                backend.run.return_value = dict(forced_status=forced, payload=payload, runtime={})
                detail, issue = verify(backend, uuid4(), stage, 5, {}, {'metrics': {'total': 1}})
                self.assertEqual(detail['status'], 'unavailable')
                self.assertTrue(issue.startswith('row_order_unverified:'))
                self.assertNotIn('reordered_result_sha256', detail)


class OrderExecutionTests(unittest.TestCase):
    setUpClass = classmethod(execution_tests.ExecutionTests.setUpClass.__func__)
    tearDownClass = classmethod(execution_tests.ExecutionTests.tearDownClass.__func__)
    run_code = execution_tests.ExecutionTests.run_code
    assert_clean = execution_tests.ExecutionTests.assert_clean

    def code(self, expression):
        return f'''from dr_runtime import connect, write_result
with connect() as db:
    dates = [r[0] for r in db.execute('SELECT CAST(date AS DATE) FROM sales').fetchall()]
value = {expression}
write_result({{'window':value}}, evidence=[{{'metric':'window','tables':['sales'],'operation':'Range of observed dates.'}}])
'''

    def test_first_row_range_is_rejected_without_publishing_artifacts(self):
        report = self.run_code(self.code("str(dates[0]) + ' to ' + str(max(dates))"))
        self.assertEqual(report['status'], 'invalid_output', report.get('issue'))
        self.assertIn('row_order_dependent', report['issue'])
        self.assertIsNone(report['result'])
        self.assertEqual(report['artifacts'], [])
        self.assertEqual(report['runtime']['row_order_check']['status'], 'different')
        self.assertEqual(report['runtime']['row_order_check']['changed_metrics'], ['window'])
        self.assert_clean(report)

    def test_bounds_and_explicit_sequence_pass_without_changing_sources(self):
        for expression in ("str(min(dates)) + ' to ' + str(max(dates))", "str(sorted(dates)[0]) + ' to ' + str(sorted(dates)[-1])"):
            with self.subTest(expression=expression):
                report = self.run_code(self.code(expression))
                self.assertEqual(report['status'], 'completed', report.get('issue'))
                self.assertEqual(report['runtime']['row_order_check']['status'], 'passed')
                self.assertEqual(report['runtime']['row_order_check']['program_runs'], 2)
                for source in report['inputs'].values():
                    self.assertEqual(digest(self.config.storage/source['parquet_key']), source['parquet_sha256'])
                self.assert_clean(report)


if __name__ == '__main__': unittest.main()
