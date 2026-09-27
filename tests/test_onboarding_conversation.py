"""Integrated setup boundaries against PostgreSQL; model doubles are not quality evidence."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect, migrate
from decision_room.conversations import Conversations
from decision_room.web.service import Workspace, WebError
from decision_room.web import onboarding
from decision_room.web.preview import dataset_page
from decision_room.agent.model import ModelRequestUncertain
from decision_room.service import import_batch
import test_web
from test_web import WebModel, SETTINGS


def answer(text='Seguimos con tu primer análisis.', guide=None):
    return dict(action='answer', retrieval=None, analysis_id='', sources=[], text=text, onboarding=guide)


class SetupModel(WebModel):
    def generate_chat(self, context, correction=None):
        state = context.get('onboarding')
        if not state:
            return answer('Seguimos en la misma conversación.'), {}
        if state['stage'] == 'scope':
            tables = [t for t in context['chat_context']['catalog']['items']
                      if t['analysis_id'] == state['analysis_id']]
            if not context['retrievals']:
                return dict(action='retrieve', retrieval=dict(tool='inspect_dataset', id=tables[0]['id'], query='', limit=5),
                            analysis_id='', sources=[], text='', onboarding=None), {}
            q = None
            if context['message'].get('onboarding_event') == 'data':
                q = dict(text='¿Hubo una campaña?', reason='Puede ayudar a interpretar cambios.', optional=True, references=[])
            brief = dict(objective='Entender las ventas disponibles', business_summary='Negocio de prueba.',
                         questions=['¿Cuál es el importe total de las filas?'], limitations=['No representa beneficio neto.'])
            return answer('¿Hubo una campaña?' if q else 'Podemos analizar los importes disponibles.', dict(question=q, brief=brief)), {}
        return answer('Elige qué quieres conseguir o cuéntamelo con tus palabras.'), {}

    def review_chat_answer(self, context):
        return dict(approved=True, issues=[]), {}


class SetupTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-setup-')
        self.addCleanup(self.temp.cleanup)
        self.config = replace(self.base, dsn=self.dsn, storage=Path(self.temp.name), semantic_search=False)
        with connect(self.config) as db:
            db.execute('UPDATE web_workspace SET active_business_id=NULL')
        self.ws = Workspace(self.config, SETTINGS, SetupModel)
        self.b = self.ws.save_business(dict(request_key=str(uuid4()), name='Synthetic shop', description='A fictional shop.'))['id']
        self.ws = self.ws.scoped(self.b)
        self.chats = Conversations(self.ws)

    def run_last(self):
        state = onboarding.read(self.ws)
        turns = self.chats.detail(state['conversation_id'])['turns']
        self.chats.run(turns[-1]['id'])
        result = self.chats.detail(state['conversation_id'])['turns'][-1]
        self.assertNotEqual(result['status'], 'failed', result.get('issue'))
        return result

    def change(self, action, **kwargs):
        state = onboarding.read(self.ws)
        return onboarding.change(self.ws, dict(business_id=str(self.b), request_key=str(uuid4()), revision=state['revision'], action=action, **kwargs))

    def setup_scope(self):
        onboarding.start(self.ws, dict(business_id=str(self.b)))
        self.run_last()
        self.change('goal', text='Entender las ventas', choices=['discover', 'organize'])
        self.run_last()
        path = Path(self.temp.name) / 'sales.csv'
        path.write_text('quantity,amount\n2,10\n3,20\n')
        analysis = import_batch(self.config, self.b, [path], title='Synthetic sales')['analysis']['id']
        self.change('data', analysis_id=str(analysis))
        self.run_last()
        return onboarding.read(self.ws)

    def test_start_and_confirm_are_idempotent_and_scope_is_versioned(self):
        state = self.setup_scope()
        repeated = onboarding.start(self.ws, dict(business_id=str(self.b)))
        self.assertEqual(state['conversation_id'], repeated['conversation_id'])
        data = dict(business_id=str(self.b), request_key=str(uuid4()), revision=state['revision'], action='confirm')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: onboarding.change(self.ws, data), range(2)))
        self.assertEqual(results[0]['job_id'], results[1]['job_id'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM web_jobs WHERE business_id=%s', (self.b,)).fetchone()['n'], 1)
            import json
            context = json.loads(db.execute('SELECT context FROM web_jobs WHERE business_id=%s', (self.b,)).fetchone()['context'])
            self.assertEqual(context['dependencies'][0]['id'], str(state['proposal_turn_id']))
            self.assertEqual(context['dependencies'][0]['kind'], 'chat')
        self.assertEqual(results[0]['confirmed']['goal']['choices'], ['discover', 'organize'])
        self.assertEqual(results[0]['confirmed']['brief'], state['brief'])
        with self.assertRaises(WebError):
            onboarding.change(self.ws, {**data, 'action': 'complete'})

    def test_unknown_has_question_context_and_allows_bounded_scope(self):
        state = self.setup_scope()
        chat = state['conversation_id']
        turn = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='No lo sé', disposition='unknown'))
        self.assertIsNone(onboarding.read(self.ws)['brief'])
        self.chats.run(turn['id'])
        with connect(self.config) as db:
            row = db.execute('SELECT payload,memory_source_id FROM chat_turns WHERE id=%s', (turn['id'],)).fetchone()
            self.assertEqual(row['payload']['question'], '¿Hubo una campaña?')
            question = row['payload']['onboarding_question']
            self.assertEqual(question['text'], row['payload']['question'])
            self.assertTrue(question['optional'])
            self.assertTrue(question['source_turn_id'])
            source = db.execute('SELECT payload FROM memory_sources WHERE id=%s', (row['memory_source_id'],)).fetchone()['payload']
            self.assertEqual(source['disposition'], 'unknown')
            facts = db.execute('SELECT status,content FROM memory_revisions WHERE source_id=%s', (row['memory_source_id'],)).fetchall()
            self.assertTrue(all(f['content']['kind'] == 'open_question' for f in facts))
        self.assertIsNotNone(onboarding.read(self.ws)['brief'])

    def test_profile_memory_is_resolved_before_first_chat_snapshot(self):
        state = onboarding.start(self.ws, dict(business_id=str(self.b)))
        self.run_last()
        with connect(self.config) as db:
            turn = db.execute('SELECT * FROM chat_turns WHERE conversation_id=%s', (state['conversation_id'],)).fetchone()
            source = db.execute('SELECT * FROM memory_sources WHERE id=%s', (turn['memory_source_id'],)).fetchone()
            self.assertEqual(source['origin_key'], 'profile:1')
            self.assertEqual(source['status'], 'applied')
            from decision_room.conversations import fresh
            self.assertTrue(fresh(db, turn['snapshot']))

    def test_change_goal_invalidates_proposal_and_old_confirmation(self):
        state = self.setup_scope()
        changed = self.change('goal', text='Comparar periodos', choices=['evolution'])
        self.assertIsNone(changed['brief'])
        with self.assertRaises(WebError):
            onboarding.change(self.ws, dict(business_id=str(self.b), request_key=str(uuid4()), revision=state['revision'], action='confirm'))
        self.run_last()
        self.assertEqual(onboarding.read(self.ws)['goal']['text'], 'Comparar periodos')

    def test_no_model_can_start_first_report_without_confirmation(self):
        state = self.setup_scope()
        with patch.object(SetupModel, 'generate_chat', return_value=(dict(action='investigate', retrieval=None,
                analysis_id=str(state['analysis_id']), text='', sources=[]), {})):
            turn = self.chats.send(state['conversation_id'], dict(business_id=str(self.b), request_key=str(uuid4()), text='Hazlo'))
            self.chats.run(turn['id'])
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) AS n FROM web_jobs WHERE business_id=%s', (self.b,)).fetchone()['n'], 0)

    def test_cross_business_and_preview_boundaries(self):
        state = self.setup_scope()
        preview = dataset_page(self.ws, state['analysis_id'], {})
        self.assertEqual(preview['columns'], ['quantity', 'amount'])
        self.assertEqual(len(preview['rows']), 2)
        other = self.ws.save_business(dict(request_key=str(uuid4()), name='Other', description='Other fictional shop', expected_active_id=str(self.b)))['id']
        with self.assertRaises(WebError):
            self.change('confirm')
        with self.assertRaises(WebError):
            dataset_page(self.ws.scoped(other), state['analysis_id'], {})
        with self.assertRaises(WebError):
            onboarding.start(self.ws.scoped(other), dict(business_id=str(self.b)))

    def test_interrupt_resume_preserves_one_conversation_and_history(self):
        state = onboarding.start(self.ws, dict(business_id=str(self.b)))
        chat = state['conversation_id']
        turn = self.chats.detail(chat)['turns'][-1]['id']
        with patch.object(SetupModel, 'generate_chat', side_effect=ModelRequestUncertain('synthetic interruption')):
            self.chats.run(turn)
        recovered = Workspace(self.config, SETTINGS, SetupModel).scoped(self.b)
        self.assertEqual(onboarding.start(recovered, dict(business_id=str(self.b)))['conversation_id'], chat)
        chats = Conversations(recovered)
        chats.retry(chat, turn, dict(business_id=str(self.b)))
        chats.run(turn)
        self.assertEqual(len(chats.detail(chat)['turns']), 1)
        self.assertEqual(chats.detail(chat)['turns'][0]['status'], 'completed')

    def test_reviewed_report_and_followup_keep_same_chat(self):
        state = self.setup_scope()
        result = self.change('confirm')
        job = result['job_id']
        for _ in range(12):
            self.ws.run_job(job)
            detail = self.ws.detail(job)
            turns = self.chats.detail(state['conversation_id'])['turns']
            self.chats.run(turns[-1]['id'])
            if detail['publishable']:
                break
            if detail['status'] == 'waiting':
                q = detail['questions'][0]
                sent = self.chats.send(state['conversation_id'], dict(business_id=str(self.b), request_key=str(uuid4()),
                    text='row total', question_id=str(q['id'])))
                self.chats.run(sent['id'])
        self.assertTrue(self.ws.detail(job)['publishable'], self.ws.detail(job).get('issue'))
        finished = self.change('complete')
        self.assertEqual(finished['stage'], 'complete')
        with connect(self.config) as db:
            self.assertIsNone(onboarding.chat_state(db, self.b, state['conversation_id']))
        sent = self.chats.send(state['conversation_id'], dict(business_id=str(self.b), request_key=str(uuid4()), text='Gracias, seguimos aquí'))
        self.chats.run(sent['id'])
        self.assertEqual(self.chats.detail(state['conversation_id'])['turns'][-1]['response']['text'], 'Seguimos en la misma conversación.')

    def test_migration_reentrant_and_existing_chat_not_enrolled(self):
        migrate(self.config)
        migrate(self.config)
        self.assertIsNone(onboarding.read(self.ws))
        chat = self.chats.create(dict(business_id=str(self.b), request_key=str(uuid4())))
        with connect(self.config) as db:
            self.assertIsNone(onboarding.chat_state(db, self.b, chat['id']))

    def test_changed_profile_blocks_confirmation_and_active_chat_cannot_be_deleted(self):
        state = self.setup_scope()
        with connect(self.config) as db:
            db.execute('UPDATE businesses SET description=%s WHERE id=%s', ('Changed business', self.b))
        with self.assertRaises(WebError):
            self.change('confirm')
        with self.assertRaises(WebError):
            self.chats.delete(state['conversation_id'], dict(business_id=str(self.b)))

    def test_unknown_analytical_answer_sends_empty_text_to_report_worker(self):
        state = self.setup_scope()
        state = self.change('confirm')
        self.ws.run_job(state['job_id'])
        self.run_last()
        job = self.ws.detail(state['job_id'])
        self.assertEqual(job['status'], 'waiting')
        q = job['questions'][0]
        sent = self.chats.send(state['conversation_id'], dict(business_id=str(self.b), request_key=str(uuid4()),
            question_id=str(q['id']), text='No lo sé', disposition='unknown'))
        self.chats.run(sent['id'])
        with connect(self.config) as db:
            pending = db.execute('SELECT pending_answer FROM web_jobs WHERE id=%s', (state['job_id'],)).fetchone()['pending_answer']
        self.assertEqual(pending['text'], '')
        self.assertEqual(pending['disposition'], 'unknown')

    def test_references_must_be_inspected_in_selected_dataset(self):
        from decision_room.chat_agent import SetupGuide, setup_issues
        guide = SetupGuide.model_validate(dict(question=dict(text='¿Qué significa amount?', reason='Define cálculo', optional=False,
                    references=[dict(kind='column', id='a', column='amount')]), brief=None))
        context = dict(onboarding=dict(stage='scope', optional_questions_asked=0), retrievals=[])
        self.assertTrue(setup_issues(guide, context))
        context['retrievals'] = [dict(request=dict(tool='inspect_dataset', id='a'), response=dict(dataset=dict(
            authorized_for_current_execution=True, columns=[dict(name='amount')])))]
        self.assertEqual(setup_issues(guide, context), [])
        context['retrievals'][0]['response']['dataset']['authorized_for_current_execution'] = False
        self.assertTrue(setup_issues(guide, context))

    def test_declined_context_and_pending_reply_cannot_be_silently_overwritten(self):
        state = self.setup_scope()
        sent = self.chats.send(state['conversation_id'], dict(business_id=str(self.b), request_key=str(uuid4()),
            text='Prefiero omitir esta pregunta', disposition='declined'))
        with self.assertRaises(WebError):
            self.change('goal', text='Otro objetivo', choices=[])
        self.chats.run(sent['id'])
        with connect(self.config) as db:
            row = db.execute('SELECT payload FROM chat_turns WHERE id=%s', (sent['id'],)).fetchone()['payload']
        self.assertEqual(row['question'], '¿Hubo una campaña?')
        self.assertEqual(row['disposition'], 'declined')
        self.assertIsNotNone(onboarding.read(self.ws)['brief'])

    def test_http_setup_and_preview_require_authentication_and_active_business(self):
        client, _ = test_web.WebTests.http(self)
        self.assertEqual(client.get('/api/onboarding/session').status_code, 401)
        client.post('/api/login', json={'token': 'test-local-access'})
        self.assertIsNone(client.get('/api/onboarding/session').json())
        first = client.post('/api/onboarding/start', json=dict(business_id=str(self.b)))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(client.get('/api/onboarding/session').json()['conversation_id'], first.json()['conversation_id'])
        self.assertEqual(client.get('/api/onboarding/data').status_code, 409)
        self.assertEqual(client.post('/api/onboarding/change', json=dict(business_id=str(uuid4()))).status_code, 409)

    def test_provider_schema_requires_nullable_fields_and_disallows_early_investigation(self):
        from decision_room.agent.model import ModelClient
        from decision_room.chat_agent import Decision
        with patch.object(ModelClient, '_generate', return_value=({}, {})) as provider:
            ModelClient(SETTINGS).generate_chat({'onboarding': {'stage': 'goal'}})
        schema = provider.call_args.args[3]
        for node in [schema, *schema['$defs'].values()]:
            if node.get('type') == 'object':
                self.assertEqual(set(node['required']), set(node['properties']))
        self.assertEqual(schema['properties']['action']['enum'], ['retrieve', 'answer'])
        self.assertIsNone(Decision.model_validate(dict(action='answer', text='Legacy response', sources=[], analysis_id='', retrieval=None)).onboarding)
