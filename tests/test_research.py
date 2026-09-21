"""Real Docker/PostgreSQL research flow with explicitly scripted LLM responses."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.execution import execute
from decision_room.service import create_business, import_batch
from decision_room.agent import research, service
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_context import prompt_context


class ResearchModel:
    identity = {'model': 'scripted-research-test-only'}

    def __init__(self, fail_first=False, invalid_table=False, invented_metric=False, always_fail=False):
        self.calls = 0
        self.fail_first = fail_first
        self.invalid_table = invalid_table
        self.invented_metric = invented_metric
        self.always_fail = always_fail
        self.saw_error = False

    def generate(self, context, correction=None):
        table = context['profiles'][0]['id']
        return {'action': 'propose', 'table_ids': [], 'proposal': {
            'interpretations': [{'aspect': 'meaning', 'statement': context['owner_context'], 'status': 'confirmed',
                                 'references': [{'kind': 'owner_context', 'id': 'owner_context', 'column': ''}]}],
            'investigations': [{'key': 'sales', 'question': 'Total vendido', 'business_value': 'Conocer ventas registradas',
                                'table_ids': [table], 'definitions_needed': ['Base monetaria'], 'depends_on': [],
                                'proposed_operation': 'Sumar respetando definición del propietario',
                                'validation_needed': ['Validar tipos y alcance'], 'status': 'ready'}],
            'questions': [], 'limitations': ['Solo este extracto.']}}, {}

    def generate_research(self, context, correction=None):
        self.calls += 1
        target = next(i['key'] for i in context['plan']['investigations'] if i['status'] == 'ready')
        base = {'action': 'execute', 'investigation_key': target, 'code': '', 'table_ids': [],
                'summary': 'Calcular el total con la definición indicada.', 'metric_keys': []}
        if context['observations']:
            last = context['observations'][-1]
            if last['status'] == 'completed':
                return {**base, 'action': 'record_candidate', 'metric_keys': ['invented' if self.invented_metric else 'total'],
                        'summary': 'Resultado candidato pendiente del revisor.'}, {}
            self.saw_error = bool(last['logs'] or last['issue'])
        table = context['table_catalog'][0]
        expression = 'CAST(quantity AS DECIMAL(18,2))*CAST(amount AS DECIMAL(18,2))' if 'unit price' in context['owner_context'] else 'CAST(amount AS DECIMAL(18,2))'
        if target == 'units':
            expression = 'CAST(quantity AS DECIMAL(18,2))'
        if self.always_fail or (self.fail_first and not context['observations']):
            expression = 'a_column_that_does_not_exist'
        query = f'SELECT sum({expression}) FROM {table["alias"]}'
        code = f'''from dr_runtime import connect, write_result
query = {query!r}
with connect() as db:
    total = db.execute(query).fetchone()[0]
write_result({{'total':str(total)}}, evidence=[{{'metric':'total','tables':[{table['alias']!r}],'operation':query}}], notes=['Selected activity only.'])
'''
        return {**base, 'table_ids': [str(uuid4()) if self.invalid_table else table['id']], 'code': code}, {}


class ResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_research_test_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-research-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Research test')['id']
        path = self.root / 'items.csv'
        path.write_text('quantity,amount\n2,10\n3,20\n')
        self.analysis = import_batch(self.config, self.business, [path])['analysis']['id']
        self.model = ResearchModel()
        self.plan = service.start(self.config, self.business, self.analysis, owner_context='Amount is unit price. Quantity is units.',
                                  request_key='planning', model=self.model)

    def start(self, **kwargs):
        return research.start(self.config, self.business, self.plan['id'], request_key='research',
                              model=kwargs.pop('model', self.model), **kwargs)

    def test_generated_program_candidate_evidence_and_idempotency(self):
        result = self.start()
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['verification'], 'pending_reviewer')
        self.assertFalse(result['publishable'])
        self.assertEqual(result['steps'][0]['execution']['result']['metrics']['total'], '80.0000')
        self.assertEqual(result['findings'][0]['metric_keys'], ['total'])
        execution = result['steps'][0]['execution']
        self.assertEqual(execution['result']['verification'], 'pending')
        self.assertTrue(execution['code_sha256'])
        self.assertTrue(execution['environment'])
        self.assertEqual(self.start()['id'], result['id'])
        self.assertEqual(self.model.calls, 2)
        with self.assertRaisesRegex(ValueError, 'different knowledge or options'):
            self.start(max_investigations=1)

    def test_actual_python_error_is_returned_and_corrected(self):
        model = ResearchModel(fail_first=True)
        result = self.start(model=model)
        runs = [s['execution'] for s in result['steps'] if s['action']['action'] == 'execute']
        self.assertEqual([r['status'] for r in runs], ['failed', 'completed'])
        self.assertTrue(model.saw_error)
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['execution_id'], str(runs[-1]['id']))

    def test_recovery_after_execution_before_checkpoint_in_new_process(self):
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn, 'DECISION_ROOM_STORAGE': str(self.config.storage)}
        common = """import sys,json
sys.path.insert(0,'tests')
from test_research import ResearchModel
from decision_room.agent import research
from decision_room.execution import execute
from decision_room.config import Config
"""
        first = common + f"""
def die_after_execute(*args,**kwargs):
    result=execute(*args,**kwargs)
    raise SystemExit(17)
research.start(Config.load(),{str(self.business)!r},{str(self.plan['id'])!r},request_key='restart',model=ResearchModel(),executor=die_after_execute)
"""
        process = subprocess.run([sys.executable, '-c', first], env=env, capture_output=True, text=True)
        self.assertEqual(process.returncode, 17, process.stderr)
        with connect(self.config) as db:
            run_id = db.execute('SELECT id FROM agent_research WHERE business_id=%s', (self.business,)).fetchone()['id']
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 1)
        second = common + f"r=research.resume(Config.load(),{str(self.business)!r},{str(run_id)!r},model=ResearchModel())\nprint(json.dumps(r,default=str))"
        result = json.loads(subprocess.check_output([sys.executable, '-c', second], env=env, text=True))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['model_calls']), 2)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 1)

    def test_changed_owner_definition_invalidates_old_candidate_and_recalculates(self):
        first = self.start()
        revised = service.replan(self.config, self.business, self.plan['id'], owner_context='Amount is whole row total. Quantity is units.',
                                 request_key='correct-definition', model=self.model)
        self.assertEqual(research.show(self.config, self.business, first['id'])['status'], 'stale')
        with self.assertRaisesRegex(ValueError, 'stale'):
            research.resume(self.config, self.business, first['id'], model=self.model)
        second = research.start(self.config, self.business, revised['id'], request_key='new-definition', model=self.model)
        self.assertEqual(second['steps'][0]['execution']['result']['metrics']['total'], '30.00')
        self.assertNotEqual(first['steps'][0]['execution']['id'], second['steps'][0]['execution']['id'])
        self.assertEqual(revised['supersedes_session_id'], self.plan['id'])
        self.assertEqual(service.show(self.config, self.business, self.plan['id'])['superseded_by'], revised['id'])

    def test_scope_and_unauthorized_tables_rejected_before_execution(self):
        with self.assertRaisesRegex(ValueError, 'authorized'):
            self.start(model=ResearchModel(invalid_table=True))
        with connect(self.config) as db:
            run_id = db.execute('SELECT id FROM agent_research WHERE business_id=%s', (self.business,)).fetchone()['id']
            self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'], 0)
        other = create_business(self.config, 'Other business')['id']
        for method in (research.show, research.resume):
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                method(self.config, other, run_id)

    def test_no_invented_metrics_or_infinite_python_retries(self):
        with self.assertRaisesRegex(ValueError, 'missing metrics'):
            self.start(model=ResearchModel(invented_metric=True))
        with self.assertRaisesRegex(ValueError, 'attempt budget'):
            research.start(self.config, self.business, self.plan['id'], request_key='broken-code', model=ResearchModel(always_fail=True))
        with connect(self.config) as db:
            run = db.execute("SELECT id FROM agent_research WHERE session_id=%s AND request_key='broken-code'", (self.plan['id'],)).fetchone()
        report = research.show(self.config, self.business, run['id'])
        self.assertEqual(sum(s['action']['action'] == 'execute' for s in report['steps']), 3)
        self.assertFalse(report['findings'])

    def test_blocked_dependencies_and_context_budget(self):
        from test_agent import ScriptedModel
        parent = service.start(self.config, self.business, self.analysis, owner_context='Quantities are units.',
                               request_key='ambiguous', model=ScriptedModel())
        with self.assertRaisesRegex(ValueError, 'No investigation is ready'):
            research.start(self.config, self.business, parent['id'], request_key='blocked', investigation_keys=['sales'], model=ScriptedModel())
        with connect(self.config) as db:
            session = db.execute('SELECT * FROM agent_sessions WHERE id=%s', (self.plan['id'],)).fetchone()
            rev, answers, key = research.knowledge(db, session)
        snap = {'proposal': rev['proposal'], 'answers': [], 'source': session['source_snapshot'], 'tables': []}
        snap['proposal']['investigations'][0]['status'] = 'blocked'
        raw = {'action': 'execute', 'investigation_key': 'sales', 'table_ids': ['fake'], 'code': 'pass', 'summary': 'bad', 'metric_keys': []}
        with self.assertRaisesRegex(ValueError, 'unresolved dependencies'):
            validate_research_action(raw, snap, [], [], {})
        snap['source']['owner_context'] = 'x' * 200001
        with self.assertRaisesRegex(ValueError, '200 KB'):
            prompt_context(snap, [], [], {}, 0)

    def test_independent_research_while_waiting_and_invalidation_after_answer(self):
        from test_agent import ScriptedModel
        class MixedModel(ResearchModel):
            identity = ScriptedModel.identity
            def generate(self, context, correction=None):
                return ScriptedModel().generate(context, correction)
        model = MixedModel()
        parent = service.start(self.config, self.business, self.analysis, owner_context='Quantities are units.',
                               request_key='waiting-independent', model=model)
        self.assertEqual(parent['status'], 'waiting')
        run = research.start(self.config, self.business, parent['id'], request_key='independent', model=model)
        self.assertEqual(run['status'], 'partial')
        self.assertEqual(run['steps'][0]['execution']['result']['metrics']['total'], '5.00')
        service.answer(self.config, self.business, parent['id'], question_id=parent['questions'][0]['id'],
                       text='Amount is unit price.', request_key='definition', model=model)
        self.assertEqual(research.show(self.config, self.business, run['id'])['status'], 'stale')

    def test_malformed_json_correction_is_bounded_before_any_execution(self):
        class MalformedOnce(ResearchModel):
            def generate_research(self, context, correction=None):
                if not context['observations'] and correction is None:
                    self.calls += 1
                    return {'invalid_model_output': 'Malformed JSON output.'}, {}
                return super().generate_research(context, correction)
        model = MalformedOnce()
        run = self.start(model=model)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(model.calls, 3)
        self.assertEqual(sum(s['action']['action'] == 'execute' for s in run['steps']), 1)

    def test_finish_cannot_silently_skip_candidate_registration(self):
        class PrematureFinish(ResearchModel):
            def generate_research(self, context, correction=None):
                if context['observations'] and correction is None:
                    self.calls += 1
                    return {'action': 'finish', 'investigation_key': '', 'table_ids': [], 'code': '',
                            'summary': 'Everything is complete.', 'metric_keys': []}, {}
                return super().generate_research(context, correction)
        model = PrematureFinish()
        run = self.start(model=model)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(len(run['findings']), 1)
        self.assertEqual(model.calls, 3)


if __name__ == '__main__':
    unittest.main()
