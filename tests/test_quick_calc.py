"""Quick chat calculations: durable intent, bounded projection, never relabelled or rerun."""
import base64
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room import conversations, execution, quick_calc
from decision_room.conversations import Conversations
from decision_room.database import connect
from decision_room.memory import service as memory
from decision_room.service import import_batch
from tests import test_web as fixtures
from test_memory import content

CODE = '''from dr_runtime import connect, write_result
sql = 'SELECT sum(CAST(unidades AS INTEGER)) FROM ventas'
with connect() as db:
    total = db.execute(sql).fetchone()[0]
write_result({'unidades': total}, evidence=[{'metric': 'unidades', 'tables': ['ventas'], 'operation': sql}])
'''


def result(metrics=None, evidence=None, notes=()):
    metrics = metrics or {'unidades': 180}
    evidence = evidence or [dict(metric=m, tables=['ventas'], operation='SELECT 1') for m in metrics]
    return dict(schema_version=1, metrics=metrics, evidence=evidence, notes=list(notes))


class FakeBackend:
    """Stands in for Docker: returns a worker payload without running code."""
    manifest = {'image': 'sha256:' + 'f' * 64, 'context': 'fake'}

    def __init__(self, payload=None, status='completed', stderr=''):
        self.payload, self.status, self.stderr, self.runs, self.removed = payload or result(), status, stderr, [], []

    def run(self, execution_id, stage, timeout):
        self.runs.append(execution_id)
        files = ([dict(name='result.json', base64=base64.b64encode(json.dumps(self.payload).encode()).decode())]
                 if self.status == 'completed' else [])
        payload = dict(protocol=1, status=self.status, exit_code=0 if self.status == 'completed' else 1, files=files,
                       logs=dict(stdout='', stderr=self.stderr, stdout_truncated=False, stderr_truncated=False))
        return dict(forced_status=None, payload=json.dumps(payload).encode(), transport_stderr='', runtime={})

    def remove(self, execution_id):
        self.removed.append(execution_id)


class ObservationTests(unittest.TestCase):
    row = dict(id=uuid4(), refusal=None, request=dict(purpose='Unidades «vendidas» en \\"enero\\"\n' * 8))

    def execution(self, status='completed', data=None, stderr=''):
        return dict(id=uuid4(), status=status, result=data, issue=None if status == 'completed' else 'Program failed.',
                    logs=dict(stdout='', stderr=stderr))

    def test_completed_projection_is_labelled_and_bounded_in_real_bytes(self):
        evidence = [dict(metric='unidades', tables=['ventas'], operation='SELECT "ñ\\\\"\t' * 400) for _ in range(30)]
        notes = ['nota «ñ» "x"\n' * 30 for _ in range(20)]
        shown = quick_calc.observation(self.row, self.execution(data=result({'unidades': 180}, evidence, notes)))
        self.assertEqual(shown['metrics'], {'unidades': 180})
        self.assertEqual(shown['label'], quick_calc.LABEL)
        self.assertEqual(shown['independent_check'], 'none')
        self.assertLessEqual(quick_calc.size(shown), quick_calc.OBSERVATION_BYTES)
        self.assertLessEqual(quick_calc.size(shown['notes']), quick_calc.NOTES_BYTES)
        self.assertGreater(shown['evidence_omitted'], 0)
        self.assertGreater(shown['notes_omitted'], 0)
        self.assertTrue(all(len(e['operation']) <= quick_calc.OPERATION_CHARS for e in shown['evidence']))
        self.assertTrue(quick_calc.citable(shown))

    def test_metrics_stay_whole_or_the_result_is_not_citable(self):
        metrics = {f'métrica «{i}»': 'x' * 100 for i in range(80)}
        shown = quick_calc.observation(self.row, self.execution(data=result(metrics)))
        self.assertEqual(shown['status'], 'output_too_large')
        self.assertNotIn('metrics', shown)
        self.assertFalse(quick_calc.citable(shown))

    def test_failure_keeps_a_bounded_log_tail_and_refusal_explains_itself(self):
        shown = quick_calc.observation(self.row, self.execution('failed', stderr='línea\n' * 2000 + 'ZeroDivisionError'))
        self.assertTrue(shown['stderr'].endswith('ZeroDivisionError'))
        self.assertLessEqual(len(shown['stderr'].encode()), quick_calc.LOG_BYTES)
        self.assertFalse(quick_calc.citable(shown))
        refused = quick_calc.observation({**self.row, 'refusal': 'context_full'}, None)
        self.assertIn('error', refused)
        self.assertFalse(quick_calc.citable(refused))


class CalculationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.WebTests.tearDownClass.__func__)

    def setUp(self):
        fixtures.WebTests.setUp(self)
        path = Path(self.temp.name) / 'ventas.csv'
        path.write_text('fecha,producto_id,unidades\n' + ''.join(
            f'{(date(2025, 1, 1) + timedelta(days=i)).isoformat()},P{i % 2},{1 + i % 3}\n' for i in range(90)))
        imported = import_batch(self.config, self.business['id'], [path])
        self.analysis, self.table = str(imported['analysis']['id']), str(imported['files'][0]['table_id'])
        other = Path(self.temp.name) / 'visitas.csv'
        other.write_text('mes,visitas\n2025-01-01,10\n')
        imported = import_batch(self.config, self.business['id'], [other])
        self.other_analysis, self.other_table = str(imported['analysis']['id']), str(imported['files'][0]['table_id'])
        chats = Conversations(self.ws.scoped(self.business['id']))
        chat = chats.create(dict(business_id=str(self.business['id']), request_key=str(uuid4())))['id']
        turn = chats.send(chat, dict(business_id=str(self.business['id']), request_key=str(uuid4()), text='¿Cuántas unidades?'))
        with connect(self.config) as db:
            self.turn = db.execute('SELECT * FROM chat_turns WHERE id=%s', (turn['id'],)).fetchone()
            self.snapshot = conversations.snapshot(db, self.business['id'], None, 'objetivo')
        patcher = patch.object(quick_calc, 'available', lambda: True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def calculation(self, code=CODE, tables=None, purpose='Unidades vendidas en total'):
        return dict(purpose=purpose, code=code, tables=tables or [dict(alias='ventas', id=self.table)])

    def reserve(self, ordinal=0, calculation=None, analysis=None, events=(), context_bytes=1000, turn=None):
        with connect(self.config) as db, db.transaction():
            return quick_calc.reserve(db, self.business['id'], turn=turn or self.turn, ordinal=ordinal, chat_analysis=None,
                                      snapshot=self.snapshot, events=list(events), calculation=calculation or self.calculation(),
                                      analysis_id=analysis or self.analysis, context_bytes=context_bytes)

    def rows(self):
        with connect(self.config) as db:
            return db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s ORDER BY attempt,ordinal',
                              (self.turn['id'],)).fetchall()

    def test_scope_is_one_analysis_of_delivered_tables_and_errors_record_nothing(self):
        bad = [
            (self.calculation(tables=[dict(alias='ventas', id=self.table), dict(alias='ventas', id=self.other_table)]), self.analysis),
            (self.calculation(tables=[dict(alias='a', id=self.table), dict(alias='b', id=self.table)]), self.analysis),
            (self.calculation(tables=[dict(alias='ventas', id=self.other_table)]), self.analysis),
            (self.calculation(tables=[dict(alias='ventas', id=str(uuid4()))]), self.analysis),
        ]
        for calculation, analysis in bad:
            with self.assertRaises(ValueError):
                self.reserve(calculation=calculation, analysis=analysis)
        with connect(self.config) as db, db.transaction(), self.assertRaises(ValueError):
            quick_calc.reserve(db, self.business['id'], turn=self.turn, ordinal=0, chat_analysis=self.other_analysis,
                               snapshot=self.snapshot, events=[], calculation=self.calculation(),
                               analysis_id=self.analysis, context_bytes=0)
        self.assertEqual(self.rows(), [])
        # A table shown by a tool in this attempt is delivered even outside the snapshot catalogue.
        self.snapshot['catalog']['items'] = []
        with self.assertRaises(ValueError):
            self.reserve()
        row = self.reserve(events=[dict(dependencies=[dict(kind='table', id=self.table, metadata_version='v')])])
        self.assertEqual(row['admission'], 'reserved')
        self.assertEqual(row['request']['tables'][0]['alias'], 'ventas')

    def test_definitions_are_declared_meanings_only(self):
        business = self.business['id']
        memory.change(self.config, business, action='declare', request_key=str(uuid4()),
                      content=content('Las unidades son paquetes de seis.', topic='packs'))
        memory.change(self.config, business, action='propose', request_key=str(uuid4()),
                      content=content('Quizá las unidades sean cajas.', topic='boxes', kind='open_question'))
        row = self.reserve()
        statements = [m['statement'] for m in row['definitions']['memory']]
        self.assertIn('Las unidades son paquetes de seis.', statements)
        self.assertNotIn('Quizá las unidades sean cajas.', statements)
        self.assertLessEqual(quick_calc.size(row['definitions']), quick_calc.DEFINITIONS_BYTES)
        self.assertEqual([d['kind'] for d in row['dependencies']][0], 'table')

    def test_budget_duplicates_and_refusals_are_recorded_before_any_run(self):
        first = self.reserve(0)
        self.assertEqual(self.reserve(0)['id'], first['id'])  # Replay of the same ordinal.
        with self.assertRaises(quick_calc.Duplicate) as raised:
            self.reserve(1)
        self.assertEqual(raised.exception.ordinal, 0)
        full = self.reserve(1, self.calculation(code=CODE + '\n# otra'), context_bytes=200000)
        self.assertEqual((full['admission'], full['refusal']), ('refused', 'context_full'))
        with patch.object(quick_calc, 'available', lambda: False):
            off = self.reserve(2, self.calculation(code=CODE + '\n# tercera'))
        self.assertEqual(off['refusal'], 'sandbox_unavailable')
        with self.assertRaises(ValueError):
            self.reserve(3, self.calculation(code=CODE + '\n# cuarta'))
        self.assertEqual([r['admission'] for r in self.rows()], ['reserved', 'refused', 'refused'])
        too_long = self.calculation(code='#' + 'ñ' * 5000)
        with self.assertRaises(ValueError):
            self.reserve(4, too_long, turn={**self.turn, 'attempt': 1})

    def test_resolve_runs_once_and_replays_read_the_finished_execution(self):
        row = self.reserve()
        backend = FakeBackend()
        done = quick_calc.resolve(self.config, self.business['id'], row, backend=backend)
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(done['request_key'], quick_calc.PREFIX + str(row['id']))
        self.assertEqual(len(backend.runs), 1)
        linked = self.rows()[0]
        self.assertEqual((linked['admission'], linked['execution_id']), ('admitted', done['id']))
        # Neither a linked nor an unlinked admission runs again, even with Docker unavailable.
        with patch.object(execution, 'execute', side_effect=AssertionError('must not run')):
            self.assertEqual(quick_calc.resolve(self.config, self.business['id'], linked)['id'], done['id'])
            self.assertEqual(quick_calc.resolve(self.config, self.business['id'], row)['id'], done['id'])
        shown = quick_calc.observation(linked, done)
        self.assertEqual(shown['metrics'], {'unidades': 180})

    def test_busy_before_admission_is_refused_and_an_open_run_is_never_relabelled(self):
        row = self.reserve()
        with patch.object(execution, 'execute', side_effect=ValueError('Local sandbox is busy. Retry later.')):
            self.assertIsNone(quick_calc.resolve(self.config, self.business['id'], row))
        self.assertEqual((self.rows()[0]['admission'], self.rows()[0]['refusal']), ('refused', 'busy'))
        # An admitted run left open (cleanup pending or a dead controller) stays open.
        second = self.reserve(1, self.calculation(code=CODE + '\n# otra'))
        done = quick_calc.resolve(self.config, self.business['id'], second, backend=FakeBackend())
        with connect(self.config) as db:
            db.execute("UPDATE executions SET status='running',finished_at=NULL WHERE id=%s", (done['id'],))
        with self.assertRaises(quick_calc.Unresolved):
            quick_calc.resolve(self.config, self.business['id'], self.rows()[1])
        with connect(self.config) as db:
            self.assertEqual(quick_calc.unresolved(db, self.business['id'], self.turn['id']), [done['id']])
        blocked = self.reserve(2, self.calculation(code=CODE + '\n# tercera'))
        self.assertEqual(blocked['refusal'], 'previous_unresolved')
        # Scoped recovery removes the container first; with the lock busy it changes nothing.
        backend = FakeBackend()
        with connect(self.config) as holder:
            holder.execute('SELECT pg_advisory_lock_shared(%s)', (execution.LOCK,))
            self.assertIsNone(execution.recover_execution(self.config, self.business['id'], done['id'], backend))
        self.assertEqual(backend.removed, [])
        self.assertEqual(execution.recover_execution(self.config, self.business['id'], done['id'], backend), 'interrupted')
        self.assertEqual(backend.removed, [done['id']])
        self.assertTrue(quick_calc.recover(self.config, self.business['id'], self.turn['id']))

    def test_input_budget_is_checked_before_admission(self):
        with self.assertRaises(ValueError):
            execution.execute(self.config, self.business['id'], self.analysis, code=CODE, tables={'ventas': self.table},
                              request_key='budget-' + uuid4().hex, backend=FakeBackend(), max_input_bytes=1)
        with connect(self.config) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM executions WHERE request_key LIKE 'budget-%%'").fetchone())


if __name__ == '__main__':
    unittest.main()
