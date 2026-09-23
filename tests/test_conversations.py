"""Business chat boundaries against PostgreSQL and the real analytical worker."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.conversations import Conversations, search_history, snapshot
from decision_room.database import connect
from decision_room.service import import_batch
from decision_room.memory import service as memory, retrieval
from decision_room.agent.model import ModelRequestUncertain
from decision_room.web.service import Workspace, WebError
import test_web
from test_web import WebModel, SETTINGS
from test_memory import candidate, content


def action(kind, **values):
    return {
        **dict(
            action=kind,
            retrieval=None,
            analysis_id='',
            report_id='',
            claim_keys=[],
            question='',
            message_ids=[],
        ),
        **values,
    }


class ChatModel(WebModel):
    def generate_memory(self, context, correction=None):
        text = context['source']['text']
        if text in ('Cerramos los domingos.', 'Abrimos los domingos.'):
            return {'candidates': [candidate(text)]}, {}
        return {'candidates': []}, {}

    def generate_chat(self, context, correction=None):
        text = context['message']['text']
        events = context['retrievals']
        if text.startswith('Calculate'):
            return action('investigate', analysis_id=context['chat_context']['selection']['analysis_id']), {}
        if text.startswith('Explain'):
            opened = next((e for e in events if e['request']['tool'] == 'open_report'), None)
            if opened:
                return action('explain', report_id=opened['response']['id']), {}
            found = next((e for e in events if e['request']['tool'] == 'search_reports'), None)
            req = dict(
                tool='open_report' if found else 'search_reports',
                query='',
                id=found['response']['items'][0]['id'] if found else '',
                limit=5,
            )
            return action('retrieve', retrieval=req), {}
        return action('remember' if 'domingo' in text or text == 'Memory?' else 'missing'), {}


class ConversationTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)
    http = test_web.WebTests.http

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dr-chat-test-')
        self.addCleanup(self.temp.cleanup)
        self.config = replace(self.base, dsn=self.dsn, storage=Path(self.temp.name), semantic_search=False)
        with connect(self.config) as db:
            db.execute('UPDATE web_workspace SET active_business_id=NULL')
        self.ws = Workspace(self.config, SETTINGS, ChatModel)
        self.business = self.ws.save_business(
            dict(request_key=str(uuid4()), name='Fictional chat shop', description='Synthetic test business.')
        )
        self.b = self.business['id']
        self.chats = Conversations(self.ws.scoped(self.b))

    def chat(self, analysis=None):
        return self.chats.create(
            dict(
                business_id=str(self.b),
                request_key=str(uuid4()),
                analysis_id=str(analysis) if analysis else None,
            )
        )['id']

    def send(self, chat, text, **values):
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text=text, **values)
        result = self.chats.send(chat, payload)
        self.chats.run(result['id'])
        return self.chats.detail(chat)['turns'][-1]

    def batch(self):
        path = Path(self.temp.name) / 'sales.csv'
        path.write_text('quantity,amount\n2,10\n3,20\n')
        return import_batch(self.config, self.b, [path], title='Synthetic sales')['analysis']['id']

    def complete(self):
        chat = self.chat(self.batch())
        turn = self.send(chat, 'Calculate sales')
        job = turn['job_id']
        for answer in ('unit price', 'Amount is row total.'):
            self.ws.run_job(job)
            self.chats.run(turn['id'])
            turn = self.chats.detail(chat)['turns'][-1]
            self.assertEqual(turn['status'], 'waiting', turn)
            turn = self.send(chat, answer, question_id=turn['questions'][0]['id'])
        self.ws.run_job(job)
        self.chats.run(turn['id'])
        turn = self.chats.detail(chat)['turns'][-1]
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['response']['kind'], 'evidence')
        return chat, turn

    def test_memory_shared_and_correction_hides_old_answers(self):
        chat = self.chat()
        first = self.send(chat, 'Cerramos los domingos.')
        self.assertEqual(first['response']['items'][0]['status'], 'declared')
        other = self.chat()
        second = self.send(other, 'Memory?')
        self.assertEqual(second['response']['items'][0]['content']['statement'], 'Cerramos los domingos.')
        self.send(other, 'Abrimos los domingos.')
        fact = self.chats.detail(other)['memory_items'][0]
        self.assertEqual(fact['status'], 'conflicted')
        alternative = next(
            i
            for i, a in enumerate(fact['alternatives'])
            if a['content']['statement'] == 'Abrimos los domingos.'
        )
        self.chats.resolve(
            other,
            dict(
                business_id=str(self.b),
                request_key=str(uuid4()),
                fact_id=fact['id'],
                revision=fact['revision'],
                alternative=alternative,
            ),
        )
        self.assertEqual(self.chats.detail(chat)['turns'][0]['status'], 'stale')
        final = self.send(chat, 'Memory?')
        self.assertEqual(final['response']['items'][0]['content']['statement'], 'Abrimos los domingos.')
        self.assertEqual(final['response']['items'][0]['status'], 'declared')

    def test_send_is_persisted_idempotent_and_serial(self):
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Hello')
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.chats.send(chat, payload), range(2)))
        self.assertEqual(results[0], results[1])
        with self.assertRaises(WebError):
            self.chats.send(chat, {**payload, 'text': 'Changed'})
        with self.assertRaises(WebError):
            self.chats.send(chat, {**payload, 'request_key': str(uuid4())})
        self.chats.run(results[0]['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][0]['response']['kind'], 'missing')

    def test_reviewed_calculation_explanation_and_explicit_report(self):
        chat, t = self.complete()
        self.assertFalse(self.ws.listing())
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'])
        self.chats.report(chat, t['id'], dict(business_id=str(self.b)))
        self.assertIn('Ventas', self.chats.report(chat, t['id']))
        self.assertEqual(len(self.ws.listing()), 1)
        explanation = self.send(chat, 'Explain the existing result')
        self.assertEqual(explanation['response']['claims'], t['response']['claims'])
        self.assertEqual(explanation['response']['report_id'], t['response']['report_id'])
        with connect(self.config) as db:
            self.assertEqual(
                db.execute('SELECT count(*) AS n FROM web_jobs WHERE business_id=%s', (self.b,)).fetchone()[
                    'n'
                ],
                1,
            )
        memory.change(
            self.config,
            self.b,
            action='declare',
            request_key='new-definition',
            content=content('Amount is not defined.', kind='open_question'),
        )
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'stale')
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'])

    def test_uncertain_request_never_automatically_repeated(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', side_effect=ModelRequestUncertain('test')) as model:
            t = self.send(chat, 'Hello')
            self.assertEqual(t['status'], 'failed')
            self.chats.run(t['id'])
            self.assertEqual(model.call_count, 1)
        self.chats.retry(chat, t['id'], dict(business_id=str(self.b)))
        self.chats.run(t['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'completed')
        with connect(self.config) as db:
            self.assertEqual(
                db.execute('SELECT count(*) AS n FROM chat_calls WHERE turn_id=%s', (t['id'],)).fetchone()[
                    'n'
                ],
                2,
            )

    def test_context_changes_during_provider_call_block_publication(self):
        chat = self.chat()

        def changing(model, context):
            memory.change(self.config, self.b, action='declare', request_key='concurrent', content=content())
            return action('remember'), {}

        with patch.object(ChatModel, 'generate_chat', changing):
            t = self.send(chat, 'Memory?')
        self.assertIsNone(t['response'])
        self.assertIn(t['status'], ('failed', 'stale'))

    def test_historical_quotes_scope_and_withdrawal(self):
        chat = self.chat()
        t = self.send(chat, 'Si cerrásemos los domingos, ¿qué pasaría?')
        self.assertFalse(self.chats.detail(chat)['memory_items'])
        request = retrieval.Request(tool='search_chats', query='', id='', limit=10)
        with connect(self.config) as db:
            m = snapshot(db, self.b, None, 'horarios')
            result, deps = search_history(self.config, db, m, request)
            self.assertEqual(result['items'][0]['message_id'], str(t['id']))
            self.assertIn('hypothesis', result['items'][0]['classification'])
        first = self.send(chat, 'Cerramos los domingos.')
        fact = first['response']['items'][0]
        memory.change(
            self.config,
            self.b,
            action='withdraw',
            request_key='withdraw',
            fact_id=fact['id'],
            expected_revision=fact['revision'],
        )
        with connect(self.config) as db:
            result, _ = search_history(self.config, db, snapshot(db, self.b, None, 'horarios'), request)
            self.assertFalse(result['items'])
        other = self.ws.save_business(
            dict(
                request_key=str(uuid4()),
                name='Other',
                expected_active_id=str(self.b),
                description='Synthetic test business.',
            )
        )
        with connect(self.config) as db:
            result, _ = search_history(self.config, db, snapshot(db, other['id'], None, 'horarios'), request)
            self.assertFalse(result['items'])
        with self.assertRaises(WebError):
            Conversations(self.ws.scoped(other['id'])).detail(chat)

    def test_http_auth_origin_scope_and_roundtrip(self):
        client, server = self.http()
        self.assertEqual(client.get('/api/chats').status_code, 401)
        client.post('/api/login', json={'token': server.token})
        created = client.post('/api/chats', json=dict(business_id=str(self.b), request_key=str(uuid4())))
        self.assertEqual(created.status_code, 202, created.text)
        chat = created.json()['id']
        response = client.post(
            '/api/chats/' + chat + '/messages',
            json=dict(business_id=str(self.b), request_key=str(uuid4()), text='Hello'),
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.chats.run(response.json()['id'])
        self.assertEqual(client.get('/api/chats/' + chat).json()['turns'][0]['status'], 'completed')
        self.assertEqual(
            client.post('/api/chats', json={}, headers={'Origin': 'https://evil.test'}).status_code, 403
        )
        self.assertEqual(client.get('/api/chats/' + str(uuid4())).status_code, 404)

    def test_cached_model_output_recovers_without_second_request(self):
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Hello')
        t = self.chats.send(chat, payload)['id']
        with patch.object(self.chats, '_save', side_effect=SystemExit('simulated process exit')):
            with self.assertRaises(SystemExit):
                self.chats.run(t)
        with patch.object(
            ChatModel, 'generate_chat', side_effect=AssertionError('Must replay completed call')
        ):
            Conversations(self.ws.scoped(self.b)).run(t)
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'completed')

    def test_selected_dataset_cannot_be_switched_by_model(self):
        selected = self.batch()
        file = Path(self.temp.name) / 'other.csv'
        file.write_text('stock\n1\n')
        other = import_batch(self.config, self.b, [file])['analysis']['id']
        chat = self.chat(selected)
        with patch.object(
            ChatModel, 'generate_chat', return_value=(action('investigate', analysis_id=str(other)), {})
        ):
            turn = self.send(chat, 'Calculate sales')
        self.assertEqual(turn['status'], 'failed')
        with connect(self.config) as db:
            self.assertFalse(db.execute('SELECT 1 FROM web_jobs WHERE business_id=%s', (self.b,)).fetchone())

    def test_source_scoped_history_not_leaked_to_other_dataset(self):
        a = self.batch()
        chat = self.chat(a)
        t = self.send(chat, 'Could this be a unit price?')
        file = Path(self.temp.name) / 'inventory.csv'
        file.write_text('stock\n8\n')
        b = import_batch(self.config, self.b, [file])['analysis']['id']
        with connect(self.config) as db:
            req = retrieval.Request(tool='search_chats', query='', id='', limit=10)
            result, _ = search_history(self.config, db, snapshot(db, self.b, b, 'inventory'), req)
            self.assertNotIn(str(t['id']), [r['message_id'] for r in result['items']])
            result, _ = search_history(self.config, db, snapshot(db, self.b, a, 'sales'), req)
            self.assertIn(str(t['id']), [r['message_id'] for r in result['items']])

    def test_question_cannot_turn_known_memory_into_conflict(self):
        chat = self.chat()
        self.send(chat, 'Cerramos los domingos.')
        question = '¿Cuál es el horario de los domingos?'
        invented = candidate('No se conoce el horario.', quote=question, evidence='uncertain')
        with patch.object(ChatModel, 'generate_memory', return_value=({'candidates': [invented]}, {})):
            self.send(chat, question)
        items = self.chats.detail(chat)['memory_items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['status'], 'declared')
        self.assertEqual(items[0]['revision'], 1)

    def test_two_retry_clicks_only_authorize_one_attempt(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', side_effect=ModelRequestUncertain('test')):
            t = self.send(chat, 'Hello')

        def retry(_):
            try:
                return self.chats.retry(chat, t['id'], dict(business_id=str(self.b)))
            except WebError:
                return None

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(retry, range(2)))
        self.assertEqual(sum(x is not None for x in results), 1)
        with connect(self.config) as db:
            self.assertEqual(
                db.execute('SELECT attempt FROM chat_turns WHERE id=%s', (t['id'],)).fetchone()['attempt'], 1
            )

    def test_history_tool_in_shared_analytical_selector_and_freshness(self):
        from decision_room.agent import service as planning
        from decision_room.memory import context as contexts

        analysis = self.batch()
        chat = self.chat(analysis)
        t = self.send(chat, 'I meant the net amount; this is a hypothetical example.')
        plan = planning.start(
            self.config, self.b, analysis, owner_context='Total', request_key=str(uuid4()), model=ChatModel()
        )
        with connect(self.config) as db:
            request = dict(tool='search_chats', query='', id='', limit=10)
            retrieval.save(self.config, db, plan['id'], 'test-history', 1, request)
            event = db.execute(
                'SELECT response FROM context_retrievals WHERE session_id=%s', (plan['id'],)
            ).fetchone()
            self.assertEqual(event['response']['items'][0]['message_id'], str(t['id']))
        memory.change(self.config, self.b, action='declare', request_key='changed', content=content())
        with connect(self.config) as db:
            self.assertTrue(contexts.reason(db, plan['id']))

    def test_continuation_reaches_planner_and_own_answer_does_not_stale_history(self):
        from decision_room.memory import context as contexts, extraction
        from test_memory import MemoryModel

        analysis = self.batch()
        chat = self.chat(analysis)
        first = self.send(chat, 'Quiero conocer las ventas netas del archivo, sin extrapolar.')
        turn = self.send(chat, 'Calculate sales')
        self.ws.run_job(turn['job_id'])
        self.chats.run(turn['id'])
        last = self.chats.detail(chat)['turns'][-1]
        with connect(self.config) as db:
            session = self.ws.row(turn['job_id'])['session_id']
            manifest = contexts.manifest(db, session)
            quotes = manifest['initial_context']['conversation_start']['historical_owner_quotes']
            self.assertEqual(quotes[0]['message_id'], str(first['id']))
            self.assertNotIn('conversation_dependencies', contexts.delivered(db, session))
        self.send(chat, 'unit price', question_id=last['questions'][0]['id'])
        self.ws.run_job(turn['job_id'])
        with connect(self.config) as db:
            source = db.execute(
                "SELECT * FROM memory_sources WHERE business_id=%s AND origin_key LIKE 'planning_answer:%%'",
                (self.b,),
            ).fetchone()
        p = source['payload']
        extraction.process(
            self.config,
            self.b,
            source['id'],
            MemoryModel(
                [
                    candidate(
                        'Amount is unit price.',
                        quote='unit price',
                        kind='definition',
                        topic='amount_basis',
                        scope=p['default_scope'],
                        scope_id=p['scope_id'],
                    )
                ]
            ),
        )
        with connect(self.config) as db:
            self.assertIsNone(contexts.reason(db, session))
            fact = memory.current(db, self.b)[0]
        memory.change(
            self.config,
            self.b,
            action='withdraw',
            request_key='withdraw-answer',
            fact_id=str(fact['fact_id']),
            expected_revision=fact['revision'],
        )
        with connect(self.config) as db:
            self.assertTrue(contexts.reason(db, session))

    def test_old_answer_cannot_adopt_new_revision_of_same_report(self):
        chat, turn = self.complete()
        with patch(
            'decision_room.conversations.reviewed',
            return_value={'publishable': True, 'approved_sha256': 'different-reviewed-version'},
        ):
            self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'stale')
            with self.assertRaises(WebError):
                self.chats.report(chat, turn['id'], dict(business_id=str(self.b)))

    def test_stale_analytical_retry_keeps_old_reply_and_replans_atomically(self):
        chat, turn = self.complete()
        old_report = turn['response']['report_id']
        memory.change(self.config, self.b, action='declare', request_key='changed-context', content=content())
        self.chats.retry(chat, turn['id'], dict(business_id=str(self.b)))
        with connect(self.config) as db:
            saved = db.execute('SELECT * FROM chat_turns WHERE id=%s', (turn['id'],)).fetchone()
            self.assertEqual(saved['response_history'][0]['response']['report_id'], old_report)
            self.assertEqual(saved['status'], 'processing')
            self.assertEqual(self.ws.row(turn['job_id'])['status'], 'queued')
        self.ws.run_job(turn['job_id'])
        self.chats.run(turn['id'])
        current = self.chats.detail(chat)['turns'][-1]
        self.assertEqual(current['status'], 'waiting')
        self.assertTrue(current['questions'])

    def test_new_chat_can_discover_reviewed_antecedent_before_selecting_data(self):
        _, original = self.complete()
        chat = self.chat()
        explanation = self.send(chat, 'Explain the existing result')
        self.assertEqual(explanation['response']['report_id'], original['response']['report_id'])
        self.assertEqual(explanation['response']['scope'], original['response']['scope'])
        self.assertEqual(explanation['response']['claims'], original['response']['claims'])
