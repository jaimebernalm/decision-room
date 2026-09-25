"""Business chat boundaries against PostgreSQL and the real analytical worker."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.conversations import Conversations, memory_reply, search_history, snapshot, direct_question
from decision_room.greetings import is_greeting
from decision_room.database import connect
from decision_room.service import import_batch
from decision_room.memory import service as memory, retrieval, extraction
from decision_room.agent.model import ModelRequestUncertain
from decision_room.web.service import Workspace, WebError
import test_web
from test_web import WebModel, SETTINGS
from test_memory import MemoryModel, candidate, content


def action(kind, **values):
    if kind == 'answer':
        return dict(action=kind, retrieval=None, analysis_id='', text='', sources=[]) | values
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
        if is_greeting(text):
            return action('answer', text='¡Hola, buenos días! ¿Qué te gustaría averiguar?', sources=[]), {}
        return action('remember' if 'domingo' in text or text == 'Memory?' else 'missing'), {}


    def review_chat_answer(self, context):
        return dict(approved=True, issues=[]), {}


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

    def test_messages_queue_in_order_and_keep_prior_dialogue(self):
        chat = self.chat()
        first = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='hola'))
        second = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='¿Y ahora?'))
        self.chats.run(second['id'])
        self.assertEqual([t['status'] for t in self.chats.detail(chat)['turns']], ['queued', 'queued'])
        self.chats.run(first['id'])
        self.chats.run(second['id'])
        turns = self.chats.detail(chat)['turns']
        self.assertEqual([t['status'] for t in turns], ['completed', 'completed'])
        self.assertEqual([t['ordinal'] for t in turns], [1, 2])

    def test_queued_declaration_waits_to_enter_memory_until_its_turn(self):
        chat = self.chat()
        first = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='hola'))
        second = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Cerramos los domingos.'))
        with connect(self.config) as db:
            self.assertIsNone(db.execute('SELECT memory_source_id FROM chat_turns WHERE id=%s', (second['id'],)).fetchone()['memory_source_id'])
        self.chats.run(first['id'])
        self.chats.run(second['id'])
        with connect(self.config) as db:
            self.assertIsNotNone(db.execute('SELECT memory_source_id FROM chat_turns WHERE id=%s', (second['id'],)).fetchone()['memory_source_id'])

    def test_failed_first_message_can_be_retried_with_a_queued_successor(self):
        chat = self.chat()
        first = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='hola'))
        second = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='¿Y ahora?'))
        with patch.object(ChatModel, 'generate_chat', side_effect=ModelRequestUncertain('test')):
            self.chats.run(first['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][0]['status'], 'failed')
        self.chats.run(second['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][1]['status'], 'queued')
        self.chats.retry(chat, first['id'], dict(business_id=str(self.b)))
        self.chats.run(first['id'])
        self.chats.run(second['id'])
        self.assertEqual([t['status'] for t in self.chats.detail(chat)['turns']], ['completed', 'completed'])

    def test_clarification_is_inserted_before_queued_followups(self):
        chat = self.chat(self.batch())
        first = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Calculate sales'))
        follow = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='What happened next?'))
        self.chats.run(first['id'])
        job = self.chats.detail(chat)['turns'][0]['job_id']
        self.ws.run_job(job)
        self.chats.run(first['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][0]['status'], 'waiting')
        self.chats.run(follow['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][1]['status'], 'queued')
        question = self.chats.detail(chat)['turns'][0]['questions'][0]
        reply = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='unit price', question_id=question['id']))
        turns = self.chats.detail(chat)['turns']
        self.assertEqual([t['id'] for t in turns], [first['id'], reply['id'], follow['id']])
        self.chats.run(follow['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][2]['status'], 'queued')
        self.chats.run(reply['id'])

    def test_deleted_chat_is_hidden_and_can_be_recovered(self):
        chat = self.chat()
        turn = self.send(chat, 'hola')
        self.chats.delete(chat, dict(business_id=str(self.b)))
        self.assertNotIn(chat, [c['id'] for c in self.chats.listing()['conversations']])
        self.assertIn(chat, [c['id'] for c in self.chats.listing()['deleted_conversations']])
        with self.assertRaises(WebError):
            self.chats.detail(chat)
        with connect(self.config) as db:
            req = retrieval.Request(tool='search_chats', query='', id='', limit=10)
            result, _ = search_history(self.config, db, snapshot(db, self.b, None, 'hola'), req)
            self.assertNotIn(str(turn['id']), [item['message_id'] for item in result['items']])
        self.chats.restore(chat, dict(business_id=str(self.b)))
        self.assertEqual(self.chats.detail(chat)['turns'][0]['id'], turn['id'])

    def test_chat_order_changes_only_when_owner_sends_a_message(self):
        older = self.chat()
        newer = self.chat()
        self.assertEqual([item['id'] for item in self.chats.listing()['conversations'][:2]],
                         [newer, older])
        self.chats.detail(older)
        self.assertEqual(self.chats.listing()['conversations'][0]['id'], newer)
        self.chats.send(older, dict(business_id=str(self.b), request_key=str(uuid4()), text='Primero'))
        self.assertEqual(self.chats.listing()['conversations'][0]['id'], older)
        self.chats.detail(newer)
        self.assertEqual(self.chats.listing()['conversations'][0]['id'], older)
        self.chats.send(newer, dict(business_id=str(self.b), request_key=str(uuid4()), text='Después'))
        self.assertEqual(self.chats.listing()['conversations'][0]['id'], newer)

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

    def test_finding_reference_is_scoped_durable_and_rechecked(self):
        from decision_room.agent import review
        chat, turn = self.complete()
        response = turn['response']
        reference = {k: response[k] for k in ('report_id', 'report_version')}
        reference['claim_key'] = response['claims'][0]['key']
        other = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Explain this finding', finding_reference=reference)
        saved = self.chats.send(other, payload)
        self.assertEqual(saved, self.chats.send(other, payload))
        with self.assertRaises(WebError):
            self.chats.send(other, {**payload, 'finding_reference': {**reference, 'claim_key': 'different'}})
        item = self.chats.detail(other)
        selected = item['turns'][0]['payload']['finding_reference']
        self.assertTrue(selected['source_ids'])
        self.assertEqual(str(item['conversation']['analysis_id']), selected['analysis_id'])
        self.assertEqual(item['dataset']['version'], 1)
        seen = []
        def explain(model, context, correction=None):
            seen.append(context)
            opened = next((e for e in context['retrievals'] if e['request']['tool'] == 'open_report'), None)
            if opened:
                # Even an empty model selection cannot broaden an explicit finding.
                return action('explain', report_id=reference['report_id'], claim_keys=[]), {}
            return action('retrieve', retrieval=dict(tool='open_report', query='', id=reference['report_id'], limit=1)), {}
        with patch.object(ChatModel, 'generate_chat', explain):
            self.chats.run(saved['id'])
        detail = self.chats.detail(other)['turns'][0]
        self.assertEqual(detail['status'], 'completed', detail)
        self.assertEqual(seen[0]['chat_context']['finding_reference'], selected)
        self.assertEqual(detail['response']['claims'][0]['key'], reference['claim_key'])
        self.assertEqual(len(detail['response']['claims']), 1)
        self.assertIn('charts', detail['response'])
        self.assertIn('highlights', detail['response'])
        different = Path(self.temp.name) / 'other.csv'
        different.write_text('quantity,amount\n1,99\n')
        batch = import_batch(self.config, self.b, [different], title='Different data')['analysis']['id']
        with self.assertRaises(WebError):
            self.chats.send(self.chat(batch), {**payload, 'request_key': str(uuid4())})
        for bad in ({**reference, 'report_version': 'changed'}, {**reference, 'claim_key': 'missing'}, {**reference, 'source_ids': ['injected']}):
            with self.assertRaises(WebError):
                self.chats.send(self.chat(), {**payload, 'request_key': str(uuid4()), 'finding_reference': bad})
        # Another business cannot attach this review, even with its exact version.
        business = self.ws.save_business(dict(request_key=str(uuid4()), name='Other synthetic shop', description='Independent', expected_active_id=str(self.b)))
        isolated = Conversations(self.ws.scoped(business['id']))
        isolated_chat = isolated.create(dict(business_id=str(business['id']), request_key=str(uuid4())))
        with self.assertRaises(WebError):
            isolated.send(isolated_chat['id'], {**payload, 'business_id': str(business['id'])})
        # A new investigation carries the selected finding into the analyst manifest.
        follow = self.send(other, 'Calculate from this finding', finding_reference=reference)
        self.assertEqual(follow['status'], 'processing')
        import json
        context = json.loads(self.ws.scoped(self.b).row(follow['job_id'])['context'])
        self.assertEqual(context['context']['finding_reference'], selected)
        self.assertIn(dict(kind='report', id=reference['report_id'], version=reference['report_version']), context['dependencies'])
        review.hold(self.config, self.b, response['report_id'], reason='Controlled withdrawal.')
        self.assertEqual(self.chats.detail(other)['turns'][0]['status'], 'stale')
        with self.assertRaises(WebError):
            self.chats.send(self.chat(), {**payload, 'request_key': str(uuid4())})
        self.assertEqual(saved, self.chats.send(other, payload))  # lost response remains recoverable

    def test_daily_activity_distinguishes_unpublished_pending_and_withdrawn(self):
        chat = self.chat(self.batch())
        saved = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Calculate sales'))
        dashboard = self.ws.dashboard()
        self.assertEqual(dashboard['activity'][0]['status'], 'queued')
        self.assertEqual(dashboard['activity'][0]['href'], '#chat/' + str(chat))
        self.assertFalse(self.ws.listing())
        self.chats.run(saved['id'])
        self.assertEqual(self.ws.dashboard()['activity'][0]['status'], 'running')
        self.ws.run_job(self.chats.detail(chat)['turns'][0]['job_id'])
        self.chats.run(saved['id'])
        self.assertEqual(self.ws.dashboard()['activity'][0]['status'], 'waiting')
        finished, turn = self.complete()
        activity = self.ws.dashboard()['activity']
        self.assertEqual(activity[0]['status'], 'waiting')
        self.assertEqual(next(x for x in activity if x['href'] == '#chat/' + str(finished))['status'], 'ready')
        self.chats.report(finished, turn['id'], dict(business_id=str(self.b)))
        dashboard = self.ws.dashboard()
        self.assertEqual(dashboard['report_id'], turn['response']['report_id'])
        self.assertEqual(dashboard['report_version'], turn['response']['report_version'])
        from decision_room.agent import review
        review.hold(self.config, self.b, turn['response']['report_id'], reason='Controlled withdrawal.')
        dashboard = self.ws.dashboard()
        self.assertIsNone(dashboard['report'])
        self.assertEqual(next(x for x in dashboard['activity'] if x['href'] == '#chat/' + str(finished))['status'], 'withdrawn')
        self.assertEqual(self.ws.listing()[0]['presentation_status'], 'withdrawn')

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

    def test_context_change_keeps_prior_replies_and_marks_the_transition(self):
        chat = self.chat()
        first = self.send(chat, 'Cerramos los domingos.')
        original = first['response']
        fact = memory.read(self.config, self.b)[0]
        memory.change(self.config, self.b, request_key=str(uuid4()), action='correct',
                      fact_id=str(fact['fact_id']), expected_revision=fact['revision'],
                      content=content('Abrimos los domingos.'))
        changed = self.chats.detail(chat)
        self.assertEqual(changed['turns'][0]['status'], 'stale')
        self.assertEqual(changed['turns'][0]['response'], original)
        self.assertTrue(changed['turns'][0]['historical'])
        self.assertIsNone(changed['turns'][0]['issue'])
        self.assertTrue(changed['context_changed_after'])

        self.send(chat, 'Memory?')
        updated = self.chats.detail(chat)
        self.assertFalse(updated['context_changed_after'])
        self.assertTrue(updated['turns'][1]['context_changed_before'])
        self.assertEqual(updated['turns'][0]['response'], original)
        self.assertEqual(updated['turns'][1]['response']['items'][0]['content']['statement'],
                         'Abrimos los domingos.')

    def test_explicit_chat_correction_is_saved_before_the_agent_confirms_it(self):
        profile = self.ws.save_business(dict(business_id=str(self.b),
                                             profile_revision=self.business['profile_revision'],
                                             name='Fictional chat shop',
                                             description='Es una papelería ficticia de Valencia.'))
        with connect(self.config) as db:
            origin = db.execute('SELECT id FROM memory_sources WHERE business_id=%s AND origin_key=%s',
                                (self.b, f"profile:{profile['profile_revision']}")).fetchone()
        extraction.process(self.config, self.b, origin['id'],
                           MemoryModel([candidate('Es una papelería ficticia de Valencia.',
                                                  topic='business_location')]))
        first = memory.read(self.config, self.b)[0]
        text = '¿Puedes cambiar que la papelería está en Valencia por Vila-real?'
        observed = []

        def extract(context, correction=None):
            return {'candidates': [candidate('Es una papelería ficticia de Vila-real.',
                                             topic='business_location', quote=text,
                                             conflicts=[str(first['fact_id'])], correction_of=str(first['fact_id']))]}, {}

        def answer(context, correction=None):
            receipt = context['chat_context']['saved_corrections']
            observed.extend(receipt)
            self.assertEqual(receipt[0]['statement'], 'Es una papelería ficticia de Vila-real.')
            self.assertIn('saved_corrections', context['available_sources'])
            return action('answer', text='He actualizado la ubicación a Vila-real.',
                          sources=['saved_corrections']), {}

        with patch.object(ChatModel, 'generate_memory', side_effect=extract), \
             patch.object(ChatModel, 'generate_chat', side_effect=answer):
            turn = self.send(self.chat(), text)
        self.assertEqual(turn['status'], 'completed')
        self.assertEqual(turn['response']['text'], 'He actualizado la ubicación a Vila-real.')
        self.assertEqual(len(observed), 1)
        self.assertEqual(memory.read(self.config, self.b)[0]['status'], 'declared')
        self.assertEqual(memory.status(self.config, self.b)['needs_review'], 0)
        with connect(self.config) as db:
            updated = db.execute('SELECT description FROM businesses WHERE id=%s', (self.b,)).fetchone()
        self.assertEqual(updated['description'], 'Es una papelería ficticia de Vila-real.')

    def test_profile_only_location_correction_keeps_unrelated_memory(self):
        profile = self.ws.save_business(dict(business_id=str(self.b),
                                             profile_revision=self.business['profile_revision'],
                                             name='Fictional chat shop',
                                             description='Somos una papelería ficticia de Valencia. Vendemos cuadernos.'))
        self.assertGreater(profile['profile_revision'], self.business['profile_revision'])
        memory.change(self.config, self.b, request_key=str(uuid4()), action='declare',
                      content=content('Es una papelería de barrio.', topic='business_type'))
        text = '¿Puedes cambiar Valencia por Vila-real en la descripción del negocio?'

        def extract(context, correction=None):
            self.assertIn('Valencia', context['profile']['description'])
            return {'candidates': [candidate('La papelería está en Vila-real.',
                topic='business_location', quote=text,
                profile_replacement={'old_text': 'Valencia', 'new_text': 'Vila-real'})]}, {}

        def answer(context, correction=None):
            self.assertEqual(context['chat_context']['saved_corrections'][0]['statement'],
                             'La papelería está en Vila-real.')
            return action('answer', text='He cambiado la ubicación a Vila-real.',
                          sources=['saved_corrections']), {}

        with patch.object(ChatModel, 'generate_memory', side_effect=extract), \
             patch.object(ChatModel, 'generate_chat', side_effect=answer):
            turn = self.send(self.chat(), text)
        self.assertEqual(turn['status'], 'completed')
        statements = [item['content']['statement'] for item in memory.read(self.config, self.b)]
        self.assertIn('Es una papelería de barrio.', statements)
        self.assertIn('La papelería está en Vila-real.', statements)
        with connect(self.config) as db:
            updated = db.execute('SELECT description FROM businesses WHERE id=%s', (self.b,)).fetchone()
        self.assertEqual(updated['description'],
                         'Somos una papelería ficticia de Vila-real. Vendemos cuadernos.')

    def test_profile_correction_receipt_when_memory_already_has_new_value(self):
        self.ws.save_business(dict(business_id=str(self.b),
                                   profile_revision=self.business['profile_revision'],
                                   name='Fictional chat shop',
                                   description='Somos una papelería de Valencia.'))
        memory.change(self.config, self.b, request_key=str(uuid4()), action='declare',
                      content=content('La papelería está en Vila-real.', topic='business_location'))
        text = 'Cambia Valencia por Vila-real en Mi negocio.'

        def extract(context, correction=None):
            return {'candidates': [candidate('La papelería está en Vila-real.',
                topic='business_location', quote=text,
                profile_replacement={'old_text': 'Valencia', 'new_text': 'Vila-real'})]}, {}

        def answer(context, correction=None):
            self.assertEqual(context['chat_context']['saved_corrections'],
                             [{'statement': 'La papelería está en Vila-real.', 'profile_updated': True}])
            return action('answer', text='He actualizado Mi negocio.',
                          sources=['saved_corrections']), {}

        with patch.object(ChatModel, 'generate_memory', side_effect=extract), \
             patch.object(ChatModel, 'generate_chat', side_effect=answer):
            turn = self.send(self.chat(), text)
        self.assertEqual(turn['status'], 'completed')
        self.assertEqual(len(memory.read(self.config, self.b)), 1)
        with connect(self.config) as db:
            updated = db.execute('SELECT description FROM businesses WHERE id=%s', (self.b,)).fetchone()
        self.assertEqual(updated['description'], 'Somos una papelería de Vila-real.')

    def test_memory_answer_uses_current_facts_and_plain_language(self):
        chat = self.chat()
        empty = self.send(chat, 'Memory?')
        self.assertEqual(empty['response']['kind'], 'memory')
        self.assertNotIn('recuerdos aplicables', empty['response']['text'])
        self.assertNotIn('hechos declarados', empty['response']['text'])
        self.send(chat, 'Cerramos los domingos.')
        answer = self.send(chat, 'Memory?')
        self.assertIn('Fictional chat shop', answer['response']['text'])
        self.assertEqual(answer['response']['items'][0]['content']['statement'], 'Cerramos los domingos.')
        self.assertIn('todavía no encuentro', memory_reply({'name': 'Tienda'}, [],
            {'pending': 0, 'failed': 0, 'uncertain': 0}))

    def test_greeting_is_model_authored_and_sees_business_context(self):
        self.send(self.chat(), 'Cerramos los domingos.')
        def greet(model, context, correction=None):
            self.assertEqual(context['chat_context']['profile']['name'], 'Fictional chat shop')
            return action('answer', text='¡Buenos días! ¿En qué te ayudo hoy?', sources=[]), {}
        with patch.object(ChatModel, 'generate_chat', greet):
            turn = self.send(self.chat(), 'hola buenos dias')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['response']['text'], '¡Buenos días! ¿En qué te ayudo hoy?')
        self.assertEqual(turn['response']['kind'], 'grounded_answer')
        with connect(self.config) as db:
            self.assertTrue(db.execute('SELECT 1 FROM chat_calls WHERE turn_id=%s', (turn['id'],)).fetchone())
            self.assertTrue(db.execute('SELECT 1 FROM chat_answer_reviews WHERE turn_id=%s', (turn['id'],)).fetchone())

    def test_router_sees_both_sides_and_can_repair_a_missed_greeting(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', return_value=(action('respond', reply_kind='help'), {})):
            first = self.send(chat, 'Can you help me?')
        # Stored v3 behavior: an incorrect thanks reply is still in the conversation.
        with patch.object(ChatModel, 'generate_chat', return_value=(action('respond', reply_kind='thanks'), {})):
            second = self.send(chat, 'dime buenos dias al menos tmb no? jajaj')
        seen = []
        def repair(model, context, correction=None):
            seen.append(context)
            return action('respond', reply_kind='greeting_repair'), {}
        with patch.object(ChatModel, 'generate_chat', repair):
            third = self.send(chat, 'como?')
        dialogue = seen[0]['recent_dialogue']
        self.assertEqual([d['assistant']['text'] for d in dialogue], [first['response']['text'], second['response']['text']])
        self.assertEqual(dialogue[-1]['owner'], 'dime buenos dias al menos tmb no? jajaj')
        self.assertEqual(third['status'], 'completed', third)
        self.assertIn('¡Buenos días! Perdona', third['response']['text'])
        self.assertNotIn('De nada', third['response']['text'])

    def test_dialogue_does_not_restore_withdrawn_business_facts(self):
        chat = self.chat()
        first = self.send(chat, 'Cerramos los domingos.')
        fact = first['response']['items'][0]
        memory.change(self.config, self.b, action='withdraw', request_key='withdraw-dialogue-fact',
                      fact_id=fact['id'], expected_revision=fact['revision'])
        seen = []
        def answer(model, context, correction=None):
            seen.append(context)
            return action('missing'), {}
        with patch.object(ChatModel, 'generate_chat', answer):
            self.send(chat, '¿Qué dijiste antes?')
        self.assertEqual(seen[0]['recent_dialogue'][0]['owner'], 'Cerramos los domingos.')
        self.assertEqual(seen[0]['recent_dialogue'][0]['assistant']['kind'], 'stale')
        self.assertNotIn('Cerramos', seen[0]['recent_dialogue'][0]['assistant']['text'])
        self.assertEqual(seen[0]['recent_owner_messages'], [])

    def test_inspected_csv_answer_and_reference_survive_followup_and_refresh(self):
        analysis = self.batch()
        chat = self.chat(analysis)
        seen = []
        def respond(model, context, correction=None):
            seen.append(context)
            table = context['chat_context']['catalog']['items'][0]
            if not context['retrievals']:
                return dict(action='retrieve', retrieval=dict(tool='inspect_dataset', id=table['id'], query='', limit=5),
                            text='', analysis_id='', sources=[]), {}
            self.assertEqual(context['retrievals'][0]['response']['dataset']['row_count'], 2)
            return action('answer', text='El CSV contiene dos filas y las columnas quantity y amount.', sources=['tool/0']), {}
        with patch.object(ChatModel, 'generate_chat', respond):
            first = self.send(chat, 'What files do I have?')
            second = self.send(chat, 'And what is in them?')
        self.assertEqual(first['status'], 'completed', first)
        self.assertEqual(second['status'], 'completed', second)
        self.assertEqual(seen[2]['recent_dialogue'][-1]['assistant']['text'], first['response']['text'])
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['response'], second['response'])
        self.assertIsNone(second['job_id'])
        memory.change(self.config, self.b, action='declare', request_key='changed-definition', content=content())
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'stale')

    def test_duplicate_tool_is_not_executed_twice(self):
        chat = self.chat(self.batch())
        def respond(model, context, correction=None):
            if len(context['retrievals']) < 2:
                return dict(action='retrieve', retrieval=dict(tool='inspect_dataset', id=context['chat_context']['catalog']['items'][0]['id'], query='', limit=5),
                            text='', analysis_id='', sources=[]), {}
            self.assertIn('Identical lookup', context['retrievals'][-1]['response']['error'])
            return action('answer', text='Hay dos filas en el CSV.', sources=['tool/0']), {}
        with patch.object(ChatModel, 'generate_chat', respond), patch.object(retrieval, 'retrieve', wraps=retrieval.retrieve) as tool:
            turn = self.send(chat, 'Describe the CSV')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(tool.call_count, 1)

    def test_unknown_source_and_reviewer_rejection_correct_before_publication(self):
        count = 0
        def respond(model, context, correction=None):
            nonlocal count
            count += 1
            if count == 1:
                return action('answer', text='Ventas: 999 euros.', sources=['invented']), {}
            self.assertTrue(context['validation_feedback'])
            if count == 2:
                return action('answer', text='Ventas: 999 euros.', sources=['profile']), {}
            return action('answer', text='Todavía no tengo datos para comprobar las ventas.', sources=[]), {}
        def check(model, context):
            if '999' in context['draft']:
                return dict(approved=False, issues=['Sales figure unsupported; retrieve reviewed evidence.']), {}
            return dict(approved=True, issues=[]), {}
        with patch.object(ChatModel, 'generate_chat', respond), patch.object(ChatModel, 'review_chat_answer', check):
            turn = self.send(self.chat(), 'What are sales?')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertNotIn('999', turn['response']['text'])
        with connect(self.config) as db:
            reviews = db.execute('SELECT response FROM chat_answer_reviews WHERE turn_id=%s ORDER BY ordinal', (turn['id'],)).fetchall()
        self.assertEqual([r['response']['approved'] for r in reviews], [False, False, True])

    def test_review_uncertainty_is_durable_and_requires_explicit_retry(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', return_value=(action('answer', text='Hola, ¿cómo estás?', sources=[]), {})), \
             patch.object(ChatModel, 'review_chat_answer', side_effect=ModelRequestUncertain('test review')) as reviewer:
            turn = self.send(chat, 'Hello again')
            self.chats.run(turn['id'])
        self.assertEqual(turn['status'], 'failed')
        self.assertIsNone(turn['response'])
        self.assertEqual(reviewer.call_count, 1)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT status FROM chat_answer_reviews WHERE turn_id=%s', (turn['id'],)).fetchone()['status'], 'uncertain')

    def test_model_authored_report_explanation_exports_and_stales(self):
        chat, original = self.complete()
        report_id = original['response']['report_id']
        def respond(model, context, correction=None):
            if not context['retrievals']:
                return dict(action='retrieve', retrieval=dict(tool='open_report', id=report_id, query='', limit=5),
                            text='', analysis_id='', sources=[]), {}
            return action('answer', text='El resultado procede de sumar los importes de cada fila.', sources=['tool/0']), {}
        with patch.object(ChatModel, 'generate_chat', respond):
            turn = self.send(chat, 'Where does this come from?')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['response']['report_id'], report_id)
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['response']['text'], turn['response']['text'])
        self.chats.report(chat, turn['id'], dict(business_id=str(self.b)))
        self.assertIn('Ventas', self.chats.report(chat, turn['id']))
        memory.change(self.config, self.b, action='declare', request_key='report-new-definition', content=content())
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['status'], 'stale')
        with self.assertRaises(WebError):
            self.chats.report(chat, turn['id'])

    def test_completed_prose_and_review_replay_without_provider_calls(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', return_value=(action('answer', text='¡Hola!', sources=[]), {})):
            turn = self.send(chat, 'Hola')
        with connect(self.config) as db:
            db.execute("UPDATE chat_turns SET status='routing',response=NULL WHERE id=%s", (turn['id'],))
        with patch.object(ChatModel, 'generate_chat', side_effect=AssertionError('No duplicate author call')), \
             patch.object(ChatModel, 'review_chat_answer', side_effect=AssertionError('No duplicate review')):
            self.chats.run(turn['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][-1]['response'], turn['response'])

    def test_finding_answer_must_open_and_cite_selected_report_after_rejected_draft(self):
        chat, original = self.complete()
        evidence = original['response']
        reference = {k: evidence[k] for k in ('report_id', 'report_version')}
        reference['claim_key'] = evidence['claims'][0]['key']
        def respond(model, context, correction=None):
            if not context['validation_feedback']:
                return action('answer', text='La cifra procede de sumar importes.', sources=[]), {}
            if not context['retrievals']:
                return dict(action='retrieve', retrieval=dict(tool='open_report', id=reference['report_id'], query='', limit=5),
                            text='', analysis_id='', sources=[]), {}
            self.assertIn('tool/1', context['available_sources'])
            return action('answer', text='La cifra procede de sumar los importes de cada fila.', sources=['tool/1']), {}
        with patch.object(ChatModel, 'generate_chat', respond):
            turn = self.send(self.chat(), 'Explain that finding', finding_reference=reference)
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['response']['report_version'], reference['report_version'])
        self.assertEqual([c['key'] for c in turn['response']['evidence']['claims']], [reference['claim_key']])

    def test_send_is_persisted_idempotent_and_queued(self):
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Hello')
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.chats.send(chat, payload), range(2)))
        self.assertEqual(results[0], results[1])
        with self.assertRaises(WebError):
            self.chats.send(chat, {**payload, 'text': 'Changed'})
        queued = self.chats.send(chat, {**payload, 'request_key': str(uuid4())})
        self.assertEqual([t['status'] for t in self.chats.detail(chat)['turns']], ['queued', 'queued'])
        self.chats.run(results[0]['id'])
        self.chats.run(queued['id'])
        self.assertEqual(self.chats.detail(chat)['turns'][0]['response']['kind'], 'grounded_answer')

    def test_reviewed_calculation_explanation_and_explicit_report(self):
        chat, t = self.complete()
        self.assertFalse(self.ws.listing())
        self.assertIsNone(self.ws.dashboard()["report"])
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'])
        self.chats.report(chat, t['id'], dict(business_id=str(self.b)))
        self.assertIn('Ventas', self.chats.report(chat, t['id']))
        self.assertEqual(len(self.ws.listing()), 1)
        listed = self.ws.listing()[0]
        self.assertEqual(listed['origin'], 'chat')
        self.assertEqual(str(listed['conversation_id']), str(chat))
        self.assertEqual(self.ws.dashboard()['selected_id'], str(listed['id']))
        detail = self.ws.detail(listed['id'])
        self.assertEqual(str(detail['conversation_id']), str(chat))
        self.assertEqual(detail['origin'], 'chat')
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
        self.assertIsNone(self.ws.dashboard()['report'])
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'])

    def test_clock_answer_uses_supplied_runtime_and_no_analytical_job(self):
        chat = self.chat()
        clock = dict(server_time='2026-09-24T10:42:00+02:00', timezone='CEST', web_access=False)
        def answer(model, context, correction=None):
            self.assertEqual(context['available_sources']['runtime']['content'], clock)
            return action('answer', text='Hoy es 24 de septiembre de 2026, según el reloj del servidor.', sources=['runtime']), {}
        with patch('decision_room.conversations.runtime_context', return_value=clock), patch.object(ChatModel, 'generate_chat', answer):
            turn = self.send(chat, '¿Qué día es hoy?')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertIn('24 de septiembre de 2026', turn['response']['text'])
        with connect(self.config) as db:
            row = db.execute('SELECT memory_source_id,job_id FROM chat_turns WHERE id=%s', (turn['id'],)).fetchone()
            self.assertIsNone(row['memory_source_id'])
            self.assertIsNone(row['job_id'])
        self.assertEqual(self.chats.detail(chat)['turns'][0]['response'], turn['response'])

    def test_conversational_fallback_and_capabilities_do_not_dump_memory(self):
        for kind in ('capabilities', 'unavailable'):
            with patch.object(ChatModel, 'generate_chat', return_value=(action('respond', reply_kind=kind), {})):
                turn = self.send(self.chat(), '¿Puedes buscar las noticias de hoy?')
            self.assertEqual(turn['status'], 'completed', turn)
            self.assertEqual(turn['response']['kind'], 'answer')
            self.assertIn('internet', turn['response']['text'])
            self.assertNotIn('items', turn['response'])

    def test_method_and_recency_answers_survive_refresh_without_new_jobs(self):
        chat, original = self.complete()
        report_id = original['response']['report_id']
        def explain(mode):
            def generate(model, context, correction=None):
                if context['retrievals']:
                    return action('explain', report_id=report_id, answer_mode=mode), {}
                # A copied question is unused in a lookup and must not abort it.
                return action('retrieve', retrieval=dict(tool='open_report', query='', id=report_id, limit=1), question=context['message']['text']), {}
            return generate
        for mode, question in (('method', '¿Cómo se ha calculado?'), ('recency', '¿Qué es lo último que ha pasado?')):
            with patch.object(ChatModel, 'generate_chat', explain(mode)):
                turn = self.send(chat, question)
            response = turn['response']
            self.assertEqual(turn['status'], 'completed', turn)
            self.assertEqual(response['answer_mode'], mode)
            self.assertIsNone(turn['job_id'])
            if mode == 'method':
                self.assertIn(original['response']['claims'][0]['method'], response['paragraphs'])
            else:
                self.assertIn(original['response']['scope']['period'], response['paragraphs'][0])
                self.assertIn('No me permite confirmar', response['paragraphs'][1])
            self.assertEqual(self.chats.detail(chat)['turns'][-1]['response'], response)

    def test_recency_without_review_does_not_invent_coverage_from_samples(self):
        self.batch()
        with patch.object(ChatModel, 'generate_chat', return_value=(action('catalog', answer_mode='recency'), {})):
            turn = self.send(self.chat(), '¿Qué es lo último que ha pasado?')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertIsNone(turn['job_id'])
        self.assertIn('todavía no tengo un resultado revisado', turn['response']['text'])

    def test_uncertain_request_never_automatically_repeated(self):
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', side_effect=ModelRequestUncertain('test')) as model:
            t = self.send(chat, 'Can you help me?')
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
        self.assertEqual(client.post('/api/chats/' + chat + '/delete', json={'business_id': str(self.b)}).status_code, 202)
        self.assertEqual(client.get('/api/chats/' + chat).status_code, 404)
        self.assertEqual(client.post('/api/chats/' + chat + '/restore', json={'business_id': str(self.b)}).status_code, 202)
        self.assertEqual(client.get('/api/chats/' + chat).status_code, 200)
        self.assertEqual(
            client.post('/api/chats', json={}, headers={'Origin': 'https://evil.test'}).status_code, 403
        )
        self.assertEqual(client.get('/api/chats/' + str(uuid4())).status_code, 404)

    def test_cached_model_output_recovers_without_second_request(self):
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Can you help me?')
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
            t = self.send(chat, 'Can you help me?')

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
            self.assertEqual(self.chats.detail(chat)['turns'][-1]['response']['report_id'],
                             turn['response']['report_id'])
            self.assertTrue(self.chats.detail(chat)['turns'][-1]['report_outdated'])
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
