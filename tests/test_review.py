"""Real PostgreSQL/Docker, explicitly scripted roles to verify dialogue mechanics."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from copy import deepcopy
from uuid import uuid4

from decision_room.agent import review, research, service
from decision_room.agent.review_contract import checks, validate
from decision_room.agent.review_context import model_context
from decision_room.database import connect
from decision_room.execution import execute
from decision_room.report import export, render
from test_research import ResearchModel
import test_research as research_tests


def action(kind, message='Explicación apoyada en la evidencia.', **kwargs):
    return {'action': kind, 'message': message, 'report': None, 'code': '', 'table_ids': [], 'question': '', **kwargs}


def draft(context, text='Total registrado en este extracto.'):
    available = [o for o in context['observations'] if o['current'] and o['status'] == 'completed']
    ref = {'execution_id': available[-1]['execution_id'], 'metric': 'total'}
    return {'title': 'Ventas seleccionadas', 'summary': text,
            'scope': {'business': 'Negocio de prueba', 'question': 'Conocer ventas', 'period': 'No consta', 'coverage': 'Solo este extracto.'},
            'charts': [], 'no_chart_reason': 'Un total aislado no requiere gráfico.',
            'claims': [{'key': 'sales', 'title': 'Ventas', 'statement': text, 'evidence': [ref],
                        'interpretation': 'Actividad registrada, no beneficio.', 'next_step': '', 'method': 'Suma de cantidad por precio unitario.'}],
            'limitations': ['No representa todo el negocio.'], 'checks': []}


class DialogueModel(ResearchModel):
    """Stateless decisions from persisted conversation, also usable in a new process."""
    def __init__(self, scenario='defense'):
        super().__init__()
        self.scenario = scenario
        self.contexts = []

    def calculation(self, context):
        table = context['tables'][0]
        row_total = any('row total' in a['text'] for a in context['owner_answers'])
        expr = 'CAST(amount AS DECIMAL(18,2))' if row_total else 'CAST(quantity AS DECIMAL(18,2))*CAST(amount AS DECIMAL(18,2))'
        query = f'SELECT SUM({expr}) FROM {table["alias"]}'
        code = f'''from dr_runtime import connect,write_result
with connect() as db: total=db.execute({query!r}).fetchone()[0]
write_result({{'total':str(total)}},evidence=[{{'metric':'total','tables':[{table['alias']!r}],'operation':{query!r}}}])
'''
        return action('execute', code=code, table_ids=[table['id']])

    def generate_analyst_review(self, context, correction=None):
        self.contexts.append(deepcopy(context))
        conversation = context['conversation']
        if self.scenario == 'owner' and conversation:
            if not context['owner_answers']:
                return action('ask_owner', question='¿Es amount precio unitario o total de fila?'), {}
            if context['owner_answers'][-1]['disposition'] != 'answered':
                return action('withdraw', 'La definición sigue pendiente; retiro la conclusión monetaria.'), {}
            if not any(o['current'] and o['status'] == 'completed' for o in context['observations']):
                return self.calculation(context), {}
        if self.scenario == 'fix' and any(e['role'] == 'reviewer' for e in conversation) and not any(e['role'] == 'analyst' and e['action']['action'] == 'execute' for e in conversation):
            return self.calculation(context), {}
        report = draft(context)
        if self.scenario == 'xss':
            report['title'] = '<script>alert(1)</script>'
            report['summary'] = '<img src=x onerror=alert(2)>'
        if self.scenario == 'bad_check':
            ref = report['claims'][0]['evidence'][0]
            report['checks'] = [{'key': 'bad_sum', 'operation': 'sum', 'actual': ref, 'operands': [ref, ref], 'tolerance': '0'}]
        if self.scenario == 'independent' and len(context['observations']) > 1:
            report['checks'] = [{'key': 'independent_total', 'operation': 'equal',
                                 'actual': report['claims'][0]['evidence'][0],
                                 'operands': [{'execution_id': context['observations'][0]['execution_id'], 'metric': 'total'}],
                                 'tolerance': '0.01'}]
        message = 'Mantengo la conclusión: cantidad por precio unitario, según la respuesta original; adjunto la evidencia.' if conversation else 'Presento el borrador.'
        return action('submit', message, report=report), {}

    def generate_reviewer(self, context, correction=None):
        self.contexts.append(deepcopy(context))
        own = [e for e in context['conversation'] if e['role'] == 'reviewer']
        if self.scenario in ('defense', 'fix', 'owner') and not own:
            return action('revise', 'Justifica la base monetaria con el contexto del propietario; corrige o pregunta si falta.',
                          question='¿Qué evidencia sostiene la definición utilizada?'), {}
        if self.scenario == 'independent':
            if not own:
                return self.calculation(context), {}
            if own[-1]['action']['action'] == 'execute':
                return action('revise', 'Incluye la comprobación independiente y compara los dos totales.'), {}
        if self.scenario == 'reject_defense':
            return action('revise' if not own else 'reject', 'La justificación no resuelve el reparo.'), {}
        if self.scenario == 'loop':
            return action('revise', 'Sigue pendiente explicar el alcance.'), {}
        return action('approve', 'Revisado el contexto, el código y las referencias de esta versión.'), {}


class ReviewTests(unittest.TestCase):
    setUpClass = classmethod(research_tests.ResearchTests.setUpClass.__func__)
    tearDownClass = classmethod(research_tests.ResearchTests.tearDownClass.__func__)

    def setUp(self):
        research_tests.ResearchTests.setUp(self)
        self.research = research.start(self.config, self.business, self.plan['id'], request_key='source', model=self.model)

    def run_review(self, scenario='defense', **kwargs):
        self.roles = DialogueModel(scenario)
        return review.start(self.config, self.business, self.research['id'], request_key=scenario,
                            analyst=self.roles, reviewer=self.roles, **kwargs)

    def test_reviewer_objection_analyst_defense_and_exact_approval_keep_context(self):
        r = self.run_review()
        self.assertTrue(r['publishable'])
        self.assertEqual([e['action']['action'] for e in r['conversation']], ['submit', 'revise', 'submit', 'approve'])
        returned = [c for c in self.roles.contexts if c['role'] == 'analyst'][-1]
        self.assertIn('unit price', returned['owner_context'])
        self.assertEqual(returned['plan']['investigations'][0]['key'], 'sales')
        self.assertEqual(returned['conversation'][-1]['role'], 'reviewer')
        self.assertIn('evidencia', returned['conversation'][-1]['action']['question'])
        self.assertEqual(returned['observations'][0]['result']['metrics']['total'], '80.0000')
        self.assertEqual(len(returned['planning_history']), 1)
        again = review.resume(self.config, self.business, r['id'], analyst=self.roles, reviewer=self.roles)
        self.assertEqual(len(again['model_calls']), 4)
        self.assertEqual(again['approved_sha256'], r['approved_sha256'])

    def test_reviewer_can_reject_an_analyst_defense(self):
        r = self.run_review('reject_defense')
        self.assertEqual(r['status'], 'rejected')
        self.assertFalse(r['publishable'])
        self.assertEqual(r['conversation'][-2]['role'], 'analyst')

    def test_independent_reviewer_python_then_analyst_integrates_check(self):
        r = self.run_review('independent')
        self.assertTrue(r['publishable'])
        self.assertEqual([e['action']['action'] for e in r['conversation']], ['submit', 'execute', 'revise', 'submit', 'approve'])
        self.assertEqual(len(r['observations']), 2)
        self.assertTrue(next(c for c in r['checks'] if c['check'] == 'independent_total')['passed'])

    def test_wrong_operation_is_recalculated_after_reviewer_feedback(self):
        class WrongResearch(ResearchModel):
            def generate_research(self, context, correction=None):
                response, usage = super().generate_research(context, correction)
                if response['action'] == 'execute':
                    response['code'] = response['code'].replace('CAST(quantity AS DECIMAL(18,2))*', '')
                return response, usage
        self.research = research.start(self.config, self.business, self.plan['id'], request_key='wrong-operation', model=WrongResearch())
        r = self.run_review('fix')
        self.assertEqual([o['result']['metrics']['total'] for o in r['observations']], ['30.00', '80.0000'])
        self.assertTrue(r['publishable'])
        self.assertEqual(r['report']['claims'][0]['evidence'][0]['execution_id'], r['observations'][-1]['execution_id'])

    def test_owner_question_pause_new_process_answer_recalculate_and_share_knowledge(self):
        r = self.run_review('owner')
        self.assertEqual(r['status'], 'waiting')
        self.assertFalse(r['publishable'])
        count = len(r['model_calls'])
        same = review.resume(self.config, self.business, r['id'], analyst=self.roles, reviewer=self.roles)
        self.assertEqual(len(same['model_calls']), count)
        step = r['pending_questions'][0]['step']
        script = f'''import sys,json
sys.path.insert(0,'tests')
from test_review import DialogueModel
from decision_room.config import Config
from decision_room.agent import review
r=review.answer(Config.load(),{str(self.business)!r},{str(r['id'])!r},step={step},text='Amount is row total.',request_key='owner-definition',analyst=DialogueModel('owner'),reviewer=DialogueModel('owner'))
print(json.dumps(r,default=str))
'''
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn, 'DECISION_ROOM_STORAGE': str(self.config.storage)}
        result = json.loads(subprocess.check_output([sys.executable, '-c', script], env=env, text=True))
        self.assertTrue(result['publishable'])
        self.assertEqual([o['current'] for o in result['observations']], [False, True])
        self.assertEqual(result['observations'][-1]['result']['metrics']['total'], '30.00')
        self.assertIn('row total', service.show(self.config, self.business, self.plan['id'])['answers'][-1]['text'])
        self.assertEqual(research.show(self.config, self.business, self.research['id'])['status'], 'stale')
        again = review.answer(self.config, self.business, r['id'], step=step, text='Amount is row total.', request_key='owner-definition', analyst=self.roles, reviewer=self.roles)
        self.assertEqual(len(again['model_calls']), len(result['model_calls']))
        with self.assertRaisesRegex(ValueError, 'already answered differently'):
            review.answer(self.config, self.business, r['id'], step=step, text='Something different.', request_key='change', analyst=self.roles, reviewer=self.roles)

    def test_unknown_owner_answer_never_becomes_a_definition(self):
        r = self.run_review('owner')
        r = review.answer(self.config, self.business, r['id'], step=r['pending_questions'][0]['step'], disposition='unknown',
                          request_key='unknown', analyst=self.roles, reviewer=self.roles)
        self.assertEqual(r['status'], 'withdrawn')
        self.assertFalse(r['publishable'])
        self.assertIsNone(r['report'])

    def test_failed_numeric_check_cannot_be_overridden_by_reviewer(self):
        with self.assertRaisesRegex(ValueError, 'failed mechanical checks'):
            self.run_review('bad_check')
        with connect(self.config) as db:
            r = db.execute('SELECT id FROM agent_reviews WHERE business_id=%s', (self.business,)).fetchone()
        self.assertFalse(review.show(self.config, self.business, r['id'])['publishable'])

    def test_review_budget_stops_conversation_without_approval(self):
        r = self.run_review('loop', max_review_rounds=2)
        self.assertEqual(r['status'], 'limited')
        self.assertFalse(r['publishable'])
        self.assertEqual(sum(e['role']=='reviewer' for e in r['conversation']), 2)

    def test_scope_fabricated_evidence_and_role_permissions(self):
        r = self.run_review()
        for method in (review.show, review.resume):
            with self.assertRaisesRegex(ValueError, 'does not belong'):
                method(self.config, uuid4(), r['id'])
        context = self.roles.contexts[-1]
        with self.assertRaisesRegex(ValueError, 'Only the reviewer'):
            validate(action('approve'), 'analyst', context)
        bad = deepcopy(context['report'])
        bad['claims'][0]['evidence'][0]['execution_id'] = str(uuid4())
        with self.assertRaisesRegex(ValueError, 'unavailable evidence'):
            validate(action('submit', report=bad), 'analyst', context)
        with self.assertRaisesRegex(ValueError, 'authorized'):
            validate(action('execute', code='pass', table_ids=[str(uuid4())]), 'reviewer', context)
        harmless = validate({'action': 'revise', 'message': 'Justifica el alcance.'}, 'reviewer', context)
        self.assertIsNone(harmless['report'])
        self.assertEqual(harmless['code'], '')
        with self.assertRaisesRegex(ValueError, 'requires code'):
            validate({'action': 'execute', 'message': 'No code provided.'}, 'reviewer', context)

    def test_replan_invalidates_approval_and_html_escapes_all_model_prose(self):
        from html.parser import HTMLParser
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.links, self.unsafe = set(), [], []
            def handle_starttag(self, tag, attributes):
                attrs = dict(attributes)
                if 'id' in attrs:
                    self.ids.add(attrs['id'])
                if 'href' in attrs:
                    self.links.append(attrs['href'])
                if tag in ('script', 'iframe', 'object') or any(k.startswith('on') for k in attrs):
                    self.unsafe.append(tag)
        r = self.run_review('xss')
        page = render(r, '2026-09-21')
        self.assertNotIn('<script>', page)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Content-Security-Policy', page)
        self.assertIn('Amount is unit price.', page)
        parsed = Tags()
        parsed.feed(page)
        self.assertFalse(parsed.unsafe)
        self.assertTrue(all(link.startswith('#') and link[1:] in parsed.ids for link in parsed.links))
        exported = export(self.config, self.business, r['id'])
        self.assertTrue(Path(exported['path']).is_file())
        client = Path(exported['path']).read_text()
        internal = Path(exported['internal_path']).read_text()
        self.assertIn('La pregunta de negocio', client)
        self.assertNotIn('Conversación entre analista', client)
        self.assertIn('Conversación entre analista', internal)
        self.assertEqual(Path(exported['path']).stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(exported['internal_path']).stat().st_mode & 0o777, 0o600)
        service.replan(self.config, self.business, self.plan['id'], owner_context='Amount is row total.', request_key='new-context', model=self.model)
        r = review.show(self.config, self.business, r['id'])
        self.assertEqual(r['status'], 'stale')
        self.assertFalse(r['publishable'])
        page = render(r, '2026-09-22')
        self.assertIn('Obsoleto', page)
        self.assertIn('todavía no está aprobado', page)
        with self.assertRaisesRegex(ValueError, 'stale'):
            review.resume(self.config, self.business, r['id'], analyst=self.roles, reviewer=self.roles)

    def test_crash_after_reviewer_python_before_checkpoint_does_not_repeat_execution(self):
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn, 'DECISION_ROOM_STORAGE': str(self.config.storage)}
        script = f'''import sys
sys.path.insert(0,'tests')
from test_review import DialogueModel
from decision_room.agent import review
from decision_room.config import Config
from decision_room.execution import execute
def crash(*args,**kwargs):
 result=execute(*args,**kwargs)
 raise SystemExit(17)
review.start(Config.load(),{str(self.business)!r},{str(self.research['id'])!r},request_key='crash',analyst=DialogueModel('independent'),reviewer=DialogueModel('independent'),executor=crash)
'''
        p = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 17, p.stderr)
        with connect(self.config) as db:
            run = db.execute("SELECT id FROM agent_reviews WHERE business_id=%s AND request_key='crash'", (self.business,)).fetchone()
            before = db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n']
        r = review.resume(self.config, self.business, run['id'], analyst=DialogueModel('independent'), reviewer=DialogueModel('independent'))
        self.assertTrue(r['publishable'])
        with connect(self.config) as db:
            self.assertEqual(before, db.execute('SELECT count(*) n FROM executions WHERE business_id=%s', (self.business,)).fetchone()['n'])

    def test_context_budget_keeps_objections_instead_of_silently_truncating(self):
        r = self.run_review()
        context = deepcopy(self.roles.contexts[-1])
        context['conversation'][0]['action']['message'] = 'x' * 200001
        with self.assertRaisesRegex(ValueError, '200 KB'):
            model_context(context, 'analyst')

    def test_owner_answer_invalidates_a_sibling_approval_immediately(self):
        approved = self.run_review('defense')
        pending = self.run_review('owner')
        review.answer(self.config, self.business, pending['id'], step=pending['pending_questions'][0]['step'],
                      text='Amount is row total.', request_key='changed', analyst=self.roles, reviewer=self.roles)
        sibling = review.show(self.config, self.business, approved['id'])
        self.assertEqual(sibling['status'], 'stale')
        self.assertFalse(sibling['publishable'])

    def test_tampered_code_cannot_be_exported_with_valid_approval(self):
        from decision_room.execution import get_execution
        from decision_room.storage import Storage
        r = self.run_review()
        execution = get_execution(self.config, self.business, r['observations'][0]['execution_id'])
        path = Storage(self.config.storage).path(self.business, execution['code_key'])
        path.chmod(0o600)  # Deliberate corruption of this test's read-only fixture.
        path.write_text('print("changed after approval")')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            export(self.config, self.business, r['id'])

    def test_new_reviewer_execution_requires_an_updated_analyst_draft(self):
        self.run_review('independent')
        context = next(c for c in self.roles.contexts if c['role'] == 'reviewer' and
                       any(e['action']['action'] == 'execute' for e in c['conversation']))
        with self.assertRaisesRegex(ValueError, 'updated draft'):
            validate(action('approve'), 'reviewer', context)

    def test_numerical_checks_reject_self_comparison_and_test_real_predicates(self):
        r = self.run_review()
        report = deepcopy(r['report'])
        ref = report['claims'][0]['evidence'][0]
        report['checks'] = [{'key': 'tautology', 'operation': 'equal', 'actual': ref, 'operands': [ref], 'tolerance': '0'},
                            {'key': 'is_zero', 'operation': 'zero', 'actual': ref, 'operands': [], 'tolerance': '0'},
                            {'key': 'positive', 'operation': 'nonnegative', 'actual': ref, 'operands': [], 'tolerance': '0'}]
        results = {c['check']: c for c in checks(report, r['observations'])}
        self.assertFalse(results['tautology']['passed'])
        self.assertIn('itself', results['tautology']['detail'])
        self.assertFalse(results['is_zero']['passed'])  # The actual stored total is 80.
        self.assertTrue(results['positive']['passed'])

    def test_independent_hold_blocks_release_without_erasing_the_model_decision(self):
        r = self.run_review()
        held = review.hold(self.config, self.business, r['id'], reason='Independent check found an unsupported conclusion.')
        self.assertEqual(held['status'], 'held')
        self.assertFalse(held['publishable'])
        self.assertEqual(held['model_decision_status'], 'approved')
        self.assertEqual(held['conversation'][-1]['action']['action'], 'approve')
        self.assertIn('Bloqueado por comprobación independiente', render(held, '2026-09-21'))
        self.assertFalse(export(self.config, self.business, r['id'])['publishable'])
        with self.assertRaisesRegex(ValueError, 'independent validation hold'):
            review.resume(self.config, self.business, r['id'], analyst=self.roles, reviewer=self.roles)
        repeated = review.hold(self.config, self.business, r['id'], reason=held['independent_hold']['reason'])
        self.assertEqual(repeated['independent_hold'], held['independent_hold'])

    def test_crash_after_persisted_decision_replays_without_another_model_call(self):
        env = {**os.environ, 'DECISION_ROOM_DATABASE_URL': self.config.dsn, 'DECISION_ROOM_STORAGE': str(self.config.storage)}
        script = f'''import sys
sys.path.insert(0,'tests')
from unittest.mock import patch
from test_review import DialogueModel
from decision_room.agent import review
from decision_room.config import Config
from langgraph.graph import StateGraph
original=StateGraph.add_node
def add(self,name,node,*args,**kwargs):
 if name=='decide':
  saved=node
  def node(state):
   saved(state)
   raise SystemExit(17)
 return original(self,name,node,*args,**kwargs)
with patch.object(StateGraph,'add_node',add):
 review.start(Config.load(),{str(self.business)!r},{str(self.research['id'])!r},request_key='decision-crash',analyst=DialogueModel(),reviewer=DialogueModel())
'''
        p = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 17, p.stderr)
        with connect(self.config) as db:
            row = db.execute("SELECT id FROM agent_reviews WHERE business_id=%s AND request_key='decision-crash'", (self.business,)).fetchone()
        r = review.resume(self.config, self.business, row['id'], analyst=DialogueModel(), reviewer=DialogueModel())
        self.assertTrue(r['publishable'])
        self.assertEqual(len(r['model_calls']), 4)
        self.assertEqual(len(r['conversation']), 4)


if __name__ == '__main__':
    unittest.main()
