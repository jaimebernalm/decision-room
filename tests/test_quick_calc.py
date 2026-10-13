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

    def __init__(self, payload=None, status='completed', stderr='', stdout=''):
        self.payload, self.status, self.stderr, self.runs, self.removed = payload or result(), status, stderr, [], []
        self.stdout = stdout

    def run(self, execution_id, stage, timeout):
        self.runs.append(execution_id)
        files = ([dict(name='result.json', base64=base64.b64encode(json.dumps(self.payload).encode()).decode())]
                 if self.status == 'completed' else [])
        payload = dict(protocol=1, status=self.status, exit_code=0 if self.status == 'completed' else 1, files=files,
                       logs=dict(stdout=self.stdout, stderr=self.stderr, stdout_truncated=False, stderr_truncated=False))
        return dict(forced_status=None, payload=json.dumps(payload).encode(), transport_stderr='', runtime={})

    def remove(self, execution_id):
        self.removed.append(execution_id)


class ObservationTests(unittest.TestCase):
    row = dict(id=uuid4(), refusal=None, request=dict(purpose='Unidades «vendidas» en \\"enero\\"\n' * 8))

    def execution(self, status='completed', data=None, stderr='', stdout='', stdout_truncated=False):
        return dict(id=uuid4(), status=status, result=data, issue=None if status == 'completed' else 'Program failed.',
                    logs=dict(stdout=stdout, stderr=stderr, stdout_truncated=stdout_truncated, stderr_truncated=False))

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

    def test_the_bound_is_exact_for_every_size_near_the_limit(self):
        evidence = [dict(metric='m', tables=['ventas'], operation='SELECT "x"') for _ in range(40)]
        for length in range(5600, 6200, 7):
            shown = quick_calc.observation(self.row, self.execution(data=result({'m': 'ñ' * (length // 2)}, evidence, ['n' * 90] * 12)))
            self.assertLessEqual(quick_calc.size(shown), quick_calc.OBSERVATION_BYTES, length)
            self.assertTrue(shown.get('metrics') == {'m': 'ñ' * (length // 2)} or shown['status'] == 'output_too_large')

    def test_a_completed_run_returns_what_it_printed_with_its_completeness(self):
        values = "[('cancelada',), ('no_presentado',), ('realizada',)]"
        shown = quick_calc.observation(self.row, self.execution(data=result({'pct': 0.0}), stdout=values))
        self.assertEqual((shown['stdout'], shown['stdout_state']), (values, 'complete'))
        # Cut by the 1 KiB tail: the first printed value is gone, and the state says so.
        cut = quick_calc.observation(self.row, self.execution(data=result({'pct': 0.0}), stdout="('no_presentado',)\n" + 'ruido\n' * 2000))
        self.assertNotIn('no_presentado', cut['stdout'])
        self.assertEqual(cut['stdout_state'], 'partial')
        self.assertLessEqual(len(cut['stdout'].encode()), quick_calc.LOG_BYTES)
        # Cut by the worker even though the excerpt itself is short.
        worker = quick_calc.observation(self.row, self.execution(data=result({'pct': 0.0}), stdout=values, stdout_truncated=True))
        self.assertEqual(worker['stdout_state'], 'partial')
        # No room left by evidence and notes: no excerpt, explicitly omitted, and still within the bound.
        evidence = [dict(metric='m', tables=['ventas'], operation='SELECT "x" ' * 50) for _ in range(40)]
        full = quick_calc.observation(self.row, self.execution(data=result({'m': 1}, evidence, ['n' * 90] * 12), stdout=values * 20))
        self.assertNotIn('stdout', full)
        self.assertEqual(full['stdout_state'], 'omitted')
        self.assertLessEqual(quick_calc.size(full), quick_calc.OBSERVATION_BYTES)
        silent = quick_calc.observation(self.row, self.execution(data=result({'pct': 0.0})))
        self.assertEqual((silent.get('stdout'), silent['stdout_state']), (None, 'empty'))

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
    create = fixtures.WebTests.create

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

    def test_successive_declarations_keep_their_own_periods(self):
        business = self.business['id']
        memory.change(self.config, business, action='declare', request_key=str(uuid4()),
                      content=content('amount es el total de la fila.', topic='amount_until_june',
                                      valid_from='2025-01-01', valid_until='2025-06-30'))
        memory.change(self.config, business, action='declare', request_key=str(uuid4()),
                      content=content('amount es el precio unitario.', topic='amount_from_july',
                                      valid_from='2025-07-01', valid_until='2025-12-31'))
        items = {m['statement']: m for m in self.reserve()['definitions']['memory']}
        self.assertEqual(items['amount es el total de la fila.']['period'], {'from': '2025-01-01', 'until': '2025-06-30'})
        self.assertEqual(items['amount es el precio unitario.']['period'], {'from': '2025-07-01', 'until': '2025-12-31'})
        self.assertEqual(items['amount es el precio unitario.']['temporal_scope'], 'dated')
        self.assertEqual(items['amount es el precio unitario.']['scope'], 'business')

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



def answer(text, sources):
    return dict(action='answer', retrieval=None, analysis_id='', text=text, sources=sources, calculation=None,
                include_report=False, onboarding=None, presentation_edit=None, investigation_brief=None)


def calculate(analysis, table, code=CODE, alias='ventas'):
    return dict(action='calculate', retrieval=None, analysis_id=analysis, text='', sources=[], include_report=False,
                onboarding=None, presentation_edit=None, investigation_brief=None,
                calculation=dict(purpose='Unidades vendidas en total', code=code, tables=[dict(alias=alias, id=table)]))


class ChatCalculationTests(CalculationTests):
    """A whole chat turn: calculate, observe, answer; replays never run the program again."""
    test_scope_is_one_analysis_of_delivered_tables_and_errors_record_nothing = None
    test_definitions_are_declared_meanings_only = None
    test_budget_duplicates_and_refusals_are_recorded_before_any_run = None
    test_resolve_runs_once_and_replays_read_the_finished_execution = None
    test_busy_before_admission_is_refused_and_an_open_run_is_never_relabelled = None
    test_input_budget_is_checked_before_admission = None

    def setUp(self):
        super().setUp()
        self.backend = FakeBackend()
        patcher = patch.object(execution, 'DockerBackend', lambda: self.backend)
        patcher.start()
        self.addCleanup(patcher.stop)
        test = self

        class Model(fixtures.WebModel):
            def generate_chat(model, context, correction=None):
                test.contexts.append(context)
                return test.script(context), {}

            def review_chat_answer(model, context):
                test.reviews.append(context)
                return dict(approved=True, issues=[]), {}

        self.contexts, self.reviews = [], []
        self.ws.model_factory = Model
        self.chats = Conversations(self.ws.scoped(self.business['id']))
        self.chat_id = self.chats.create(dict(business_id=str(self.business['id']), request_key=str(uuid4())))['id']

    def script(self, context):
        done = [e for e in context['retrievals'] if e['request']['tool'] == 'calculate']
        if not done:
            return calculate(self.analysis, self.table)
        return answer('Se vendieron 180 unidades en total.', [f"tool/{done[-1]['ordinal']}"])

    def send(self, text='¿Cuántas unidades vendimos?'):
        turn = self.chats.send(self.chat_id, dict(business_id=str(self.business['id']), request_key=str(uuid4()), text=text))
        self.chats.run(turn['id'])
        return turn['id'], self.chats.detail(self.chat_id)['turns'][-1]

    def test_a_turn_calculates_once_and_cites_a_labelled_source(self):
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(len(self.backend.runs), 1)
        with connect(self.config) as db:
            event = db.execute("SELECT * FROM chat_retrievals WHERE turn_id=%s AND request->>'tool'='calculate'", (turn,)).fetchone()
            row = db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone()
        self.assertEqual(event['response']['metrics'], {'unidades': 180})
        self.assertEqual(event['response']['independent_check'], 'none')
        self.assertEqual(event['request']['code'], CODE)
        self.assertEqual(row['admission'], 'admitted')
        self.assertEqual(event['dependencies'], row['dependencies'])
        self.assertEqual(event['dependencies'][0], dict(kind='table', id=self.table,
                                                        metadata_version=row['request']['tables'][0]['metadata_version']))
        source = self.contexts[-1]['available_sources'][f"tool/{event['ordinal']}"]
        self.assertEqual(source['label'], 'Cálculo rápido (sin comprobación independiente)')
        self.assertTrue(self.contexts[0]['chat_context']['runtime']['can_quick_calculate'])

    def test_a_refusal_for_lack_of_room_never_puts_the_code_in_the_next_prompt(self):
        code = CODE + '#' + 'x' * 7600 + '\n'
        sizes = []

        def script(context):
            sizes.append(len(memory.encoded(context).encode()))
            if not context['retrievals']:
                # Leave less room than one calculation needs, but more than a refusal costs.
                patcher = patch.object(conversations.ctx, 'CONTEXT_BYTES', sizes[0] + 4000)
                patcher.start()
                self.addCleanup(patcher.stop)
                return calculate(self.analysis, self.table, code=code)
            self.assertEqual(context['retrievals'][0]['response']['refusal'], 'context_full')
            return answer('No me queda espacio para calcularlo aquí; te propongo un informe.', [])
        self.script = script
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(self.backend.runs, [])
        with connect(self.config) as db:
            event = db.execute('SELECT * FROM chat_retrievals WHERE turn_id=%s', (turn,)).fetchone()
            row = db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone()
        self.assertNotIn('code', event['request'])
        self.assertTrue(event['request']['code_omitted'])
        self.assertEqual(row['request']['code'], code)  # Kept for audit, outside the prompt.
        self.assertLess(sizes[1] - sizes[0], 4000)

    def test_when_not_even_the_refusal_fits_the_owner_gets_a_fixed_reply_without_figures(self):
        code = CODE + '#' + 'x' * 7600 + '\n'
        calls = []

        def script(context):
            calls.append(context)
            # Less room than the refusal itself needs (Codex's 199846/200000 case).
            patcher = patch.object(conversations.ctx, 'CONTEXT_BYTES', len(memory.encoded(context).encode()) + 150)
            patcher.start()
            self.addCleanup(patcher.stop)
            return calculate(self.analysis, self.table, code=code)
        self.script = script
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(shown['response'], dict(kind='answer', text=quick_calc.NO_ROOM))
        self.assertEqual(len(calls), 1)  # No further model call.
        self.assertEqual(self.backend.runs, [])
        with connect(self.config) as db:
            event = db.execute('SELECT * FROM chat_retrievals WHERE turn_id=%s', (turn,)).fetchone()
        self.assertEqual(event['response']['refusal'], 'context_full')  # Still recorded.

    def test_scope_errors_are_tool_errors_and_record_nothing(self):
        def script(context):
            if not context['retrievals']:
                return calculate(self.analysis, self.other_table)
            self.assertIn('error', context['retrievals'][0]['response'])
            return answer('No puedo calcularlo con esos datos.', [])
        self.script = script
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(self.backend.runs, [])
        with connect(self.config) as db:
            self.assertIsNone(db.execute('SELECT 1 FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone())

    def test_a_crash_after_running_replays_without_running_again(self):
        real = quick_calc.observation
        with patch.object(quick_calc, 'observation', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                self.send()
        turn = self.chats.detail(self.chat_id)['turns'][-1]['id']
        with patch.object(quick_calc, 'observation', real):
            self.chats.run(turn)
        shown = self.chats.detail(self.chat_id)['turns'][-1]
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(len(self.backend.runs), 1)

    def test_an_open_calculation_fails_the_turn_and_blocks_retry_until_recovered(self):
        def script(context):
            return calculate(self.analysis, self.table)
        self.script = script
        with patch.object(quick_calc, 'TERMINAL', ('failed',)):
            turn, shown = self.send()
        self.assertEqual(shown['status'], 'failed')
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone()
            db.execute("UPDATE executions SET status='running',finished_at=NULL WHERE id=%s", (row['execution_id'],))
        with connect(self.config) as holder:
            holder.execute('SELECT pg_advisory_lock_shared(%s)', (execution.LOCK,))
            with self.assertRaises(fixtures.WebError):
                self.chats.retry(self.chat_id, turn, dict(business_id=str(self.business['id'])))
        self.chats.retry(self.chat_id, turn, dict(business_id=str(self.business['id'])))
        self.assertEqual(self.backend.removed, [row['execution_id']])
        with connect(self.config) as db:
            status = db.execute('SELECT status FROM executions WHERE id=%s', (row['execution_id'],)).fetchone()['status']
        self.assertEqual(status, 'interrupted')


    def test_the_answer_records_the_labelled_formula_and_the_reviewer_sees_code_and_meanings(self):
        turn, shown = self.send()
        record = shown['response']['calculations'][0]
        self.assertEqual(record['label'], quick_calc.LABEL)
        self.assertEqual((record['code'], record['metrics']), (CODE, {'unidades': 180}))
        self.assertEqual(record['tables'][0]['alias'], 'ventas')
        self.assertTrue(record['tables'][0]['names'])
        cited = next(v for v in self.reviews[-1]['cited_sources'].values() if v['label'] == quick_calc.SOURCE_LABEL)
        self.assertEqual(cited['content']['code'], CODE)
        self.assertEqual(cited['content']['independent_check'], 'none')
        self.assertIn('declared_meanings', cited['content'])
        self.assertLessEqual(quick_calc.size(cited['content']), quick_calc.REVIEW_BYTES)
        # The next message sees the earlier calculation only as historical dialogue.
        self.script = lambda context: answer('De nada.', [])
        self.send('Gracias')
        earlier = self.contexts[-1]['recent_dialogue'][-1]['assistant']['text']
        self.assertIn('Cálculo rápido de entonces, sin comprobación independiente', earlier)
        self.assertIn('unidades = 180', earlier)
        from decision_room.conversation_context import assistant_text
        self.assertIn('Operación: SELECT 1', assistant_text(shown['response']))

    def test_the_model_and_the_reviewer_see_what_the_program_printed(self):
        self.backend.stdout = "[('cancelada',), ('no_presentado',), ('realizada',)]"
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertIn('no_presentado', self.contexts[-1]['retrievals'][0]['response']['stdout'])
        cited = next(v for v in self.reviews[-1]['cited_sources'].values() if v['label'] == quick_calc.SOURCE_LABEL)
        self.assertIn('no_presentado', cited['content']['observation']['stdout'])
        self.assertEqual(cited['content']['observation']['stdout_state'], 'complete')  # The reviewer gets the same qualification.
        self.assertNotIn('stdout', shown['response']['calculations'][0])  # Not shown to the owner as a result.

    def test_an_incomplete_report_offer_is_fed_back_instead_of_failing_the_turn(self):
        def script(context):
            if not context['validation_feedback']:
                return dict(action='offer_report', retrieval=None, analysis_id=str(self.analysis), text='Puedo preparar un informe.',
                            sources=[], calculation=None, include_report=False, onboarding=None, presentation_edit=None,
                            investigation_brief=None)
            return answer('Te lo explico sin informe.', [])
        self.script = script
        turn, shown = self.send('¿Me haces un informe?')
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertIn('Your previous decision was invalid', str(self.contexts[-1]['validation_feedback']))
        with connect(self.config) as db:
            rejected = db.execute("SELECT response FROM chat_answer_reviews WHERE turn_id=%s AND context ? 'decision_validation'",
                                  (turn,)).fetchone()
        self.assertFalse(rejected['response']['approved'])
        self.assertEqual(len(self.reviews), 1)  # The rejection itself made no review call.

    def test_a_failed_calculation_is_never_recorded_as_a_result(self):
        self.backend.status, self.backend.stderr = 'failed', 'Traceback: ZeroDivisionError'
        def script(context):
            done = [e for e in context['retrievals'] if e['request']['tool'] == 'calculate']
            if not done:
                return calculate(self.analysis, self.table)
            self.assertIn('ZeroDivisionError', done[0]['response']['stderr'])
            return answer('No he podido calcularlo.', [f"tool/{done[0]['ordinal']}"])
        self.script = script
        turn, shown = self.send()
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertNotIn('calculations', shown['response'])

    def test_an_oversized_review_is_rejected_without_calling_the_reviewer(self):
        with patch.object(quick_calc, 'review_projection', lambda row, response: dict(code='x' * 210000)), \
                patch.object(conversations.ctx, 'MAX_RETRIEVALS', 3):
            turn, shown = self.send()
        self.assertEqual(shown['status'], 'failed')
        self.assertEqual(self.reviews, [])
        with connect(self.config) as db:
            review = db.execute('SELECT response FROM chat_answer_reviews WHERE turn_id=%s ORDER BY ordinal LIMIT 1',
                                (turn,)).fetchone()['response']
        self.assertEqual(review['issues'], ['The review context is too large: cite fewer or smaller sources.'])


    def test_activity_monitor_evaluation_and_legacy_recovery_treat_it_as_a_chat_calculation(self):
        from decision_room.observability import collector, store
        from decision_room.web import internal_monitor
        turn, shown = self.send()
        with connect(self.config) as db:
            trace = store.linked(db, self.business['id'], 'turn', turn)
            collector.reconcile(db, self.business['id'], trace, reconstructed=True)
            tasks = {t['kind']: t for t in db.execute('SELECT * FROM activity_tasks WHERE trace_id=%s', (trace,)).fetchall()
                     if t['kind'] in ('turn', 'execution', 'retrieval')}
            row = db.execute('SELECT * FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone()
        self.assertEqual(tasks['execution']['public_text'], 'Cálculo rápido terminado')
        self.assertEqual(tasks['execution']['role'], 'chat')
        self.assertEqual(tasks['execution']['parent_task_id'], tasks['turn']['id'])
        self.assertEqual(tasks['retrieval']['public_text'], 'Cálculo rápido terminado')
        content = internal_monitor.detail(self.ws.scoped(self.business['id']), trace, 'tasks', tasks['execution']['id'])['content']
        self.assertEqual(content['provenance']['kind'], 'quick_chat_calculation')
        self.assertEqual(content['provenance']['independent_check'], 'none')
        # A legacy report run never tries to recover (and fail on) a live chat calculation.
        with connect(self.config) as db:
            db.execute("UPDATE executions SET status='running',finished_at=NULL WHERE id=%s", (row['execution_id'],))
            self.assertFalse(execution.open_report_runs(db, self.business['id']))
            db.execute("UPDATE executions SET request_key='research:x' WHERE id=%s", (row['execution_id'],))
            self.assertTrue(execution.open_report_runs(db, self.business['id']))



    def test_a_legacy_report_waits_for_a_live_calculation_and_never_recovers_chat_runs(self):
        from decision_room.web import service
        turn, shown = self.send()
        with connect(self.config) as db:
            calc = db.execute('SELECT execution_id FROM chat_calculations WHERE turn_id=%s', (turn,)).fetchone()['execution_id']
            db.execute("UPDATE executions SET status='running',finished_at=NULL WHERE id=%s", (calc,))
            stale = db.execute("""INSERT INTO executions(id,business_id,analysis_id,request_key,request_sha256,code_sha256,code_key,
                inputs,definitions,limits,environment,status) SELECT gen_random_uuid(),business_id,analysis_id,'research:abandoned',
                request_sha256,code_sha256,code_key,inputs,definitions,limits,environment,'running' FROM executions WHERE id=%s
                RETURNING id""", (calc,)).fetchone()['id']
        job = self.create()
        statuses = lambda: {r['id']: r['status'] for r in connect(self.config).execute(
            'SELECT id,status FROM executions WHERE id=ANY(%s)', ([calc, stale],)).fetchall()}
        with patch.object(service.Workspace, 'ingest_job', lambda ws, j: None):
            with connect(self.config) as holder:
                holder.execute('SELECT pg_advisory_lock_shared(%s)', (execution.LOCK,))  # The live calculation.
                self.assertEqual(self.ws.scoped(self.business['id']).run_job(job), 'deferred')
                self.assertNotEqual(self.ws.row(job)['status'], 'failed')
                self.assertEqual(statuses(), {calc: 'running', stale: 'running'})
            self.ws.scoped(self.business['id']).run_job(job)
        self.assertEqual(statuses(), {calc: 'running', stale: 'interrupted'})  # Only the report's own run.
        self.assertEqual(self.backend.removed, [stale])


@unittest.skipUnless(quick_calc.available(), 'The local sandbox runtime is not built.')
class RealSandboxTests(ChatCalculationTests):
    """End to end with real Docker and a scripted model: the program really runs, once."""
    for name in [n for n in dir(ChatCalculationTests) if n.startswith('test_')]:
        locals()[name] = None
    del name

    def setUp(self):
        CalculationTests.setUp(self)
        test = self

        class Model(fixtures.WebModel):
            def generate_chat(model, context, correction=None):
                test.contexts.append(context)
                return test.script(context), {}

            def review_chat_answer(model, context):
                return dict(approved=True, issues=[]), {}

        self.contexts = []
        self.ws.model_factory = Model
        self.chats = Conversations(self.ws.scoped(self.business['id']))
        self.chat_id = self.chats.create(dict(business_id=str(self.business['id']), request_key=str(uuid4())))['id']

    def test_a_real_calculation_returns_the_exact_total_in_seconds(self):
        import time
        expected = sum(1 + i % 3 for i in range(90))
        started = time.monotonic()
        turn, shown = self.send()
        elapsed = time.monotonic() - started
        self.assertEqual(shown['status'], 'completed', shown)
        self.assertEqual(shown['response']['calculations'][0]['metrics'], {'unidades': expected})
        self.assertLess(elapsed, quick_calc.TIMEOUT)
        with connect(self.config) as db:
            done = db.execute("SELECT e.status,e.runtime FROM chat_calculations c JOIN executions e ON e.id=c.execution_id "
                              "WHERE c.turn_id=%s", (turn,)).fetchone()
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(done['runtime']['host_config']['NetworkMode'], 'none')
        self.assertTrue(done['runtime']['host_config']['ReadonlyRootfs'])


if __name__ == '__main__':
    unittest.main()
