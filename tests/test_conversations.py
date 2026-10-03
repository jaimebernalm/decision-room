"""Business chat boundaries against PostgreSQL and the real analytical worker."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from psycopg.types.json import Jsonb

from decision_room.conversations import Conversations, memory_reply, search_history, snapshot, direct_question, library_query
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

    def test_public_chat_process_and_real_finish_times_survive_reconciliation(self):
        import time
        from decision_room.observability import collector, store, projection
        class Slow(ChatModel):
            def generate_chat(self, *args, **kwargs):
                time.sleep(.03)
                return super().generate_chat(*args, **kwargs)
        self.ws.model_factory = Slow
        turn = self.send(self.chat(), 'Hola')
        with connect(self.config) as db:
            trace = store.linked(db, self.b, 'turn', turn['id'])
            page = projection.page(db, self.b, trace, {})
            kinds = {t['kind'] for t in page['task_updates']}
            self.assertTrue({'chat_call', 'chat_review'} <= kinds)
            for table in ('chat_calls', 'chat_answer_reviews'):
                rows = db.execute(f'SELECT created_at,finished_at FROM {table} WHERE turn_id=%s', (turn['id'],)).fetchall()
                self.assertTrue(rows)
                self.assertTrue(all(r['finished_at'] > r['created_at'] for r in rows))
            db.execute('UPDATE chat_calls SET finished_at=NULL WHERE turn_id=%s', (turn['id'],))
            collector.reconcile(db, self.b, trace, reconstructed=True)
            saved = db.execute("SELECT finished_at FROM activity_tasks WHERE trace_id=%s AND kind='chat_call'", (trace,)).fetchall()
            self.assertTrue(all(r['finished_at'] is None for r in saved))
            count = db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s', (trace,)).fetchone()['last_sequence']
            collector.reconcile(db, self.b, trace, reconstructed=True)
            self.assertEqual(count, db.execute('SELECT last_sequence FROM activity_traces WHERE id=%s', (trace,)).fetchone()['last_sequence'])

    def test_http_string_scoped_business_accepts_chat_and_rejects_other_business(self):
        # Preview/worker manifests deserialize UUIDs as strings. Keep the same
        # identity representation as requests and database rows.
        self.ws = self.ws.scoped(str(self.b))
        client, server = self.http()
        client.post('/api/login', json={'token': server.token})
        payload = dict(business_id=str(self.b), request_key=str(uuid4()))
        created = client.post('/api/chats', json=payload)
        self.assertEqual(created.status_code, 202, created.text)
        self.assertEqual(client.post('/api/chats', json=payload).json(), created.json())
        chat = created.json()['id']
        sent = client.post(f'/api/chats/{chat}/messages', json=dict(
            business_id=str(self.b), request_key=str(uuid4()), text='hola'))
        self.assertEqual(sent.status_code, 202, sent.text)
        Conversations(self.ws).run(sent.json()['id'])
        detail = client.get(f'/api/chats/{chat}').json()
        self.assertEqual(detail['turns'][-1]['status'], 'completed')
        rejected = client.post('/api/chats', json=dict(
            business_id=str(uuid4()), request_key=str(uuid4())))
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.ws.business_id(), self.b)
        self.assertIsNone(self.ws.scoped(None).business_id())

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

    def test_deleted_chat_is_no_longer_accessible(self):
        chat = self.chat()
        turn = self.send(chat, 'hola')
        self.chats.delete(chat, dict(business_id=str(self.b)))
        listing = self.chats.listing()
        self.assertNotIn(chat, [c['id'] for c in listing['conversations']])
        self.assertNotIn('deleted_conversations', listing)
        with self.assertRaises(WebError):
            self.chats.detail(chat)
        with connect(self.config) as db:
            req = retrieval.Request(tool='search_chats', query='', id='', limit=10)
            result, _ = search_history(self.config, db, snapshot(db, self.b, None, 'hola'), req)
            self.assertNotIn(str(turn['id']), [item['message_id'] for item in result['items']])
        with self.assertRaises(WebError):
            self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Another message'))

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

    def test_pinned_chats_survive_reopening_and_unpin_restores_recency(self):
        older, newer = self.chat(), self.chat()
        payload = dict(business_id=str(self.b), pinned=True)
        pinned = self.chats.pin(older, payload)['pinned_at']
        self.assertIsNotNone(pinned)
        self.assertEqual(self.chats.pin(older, payload)['pinned_at'], pinned)
        reopened = Conversations(Workspace(self.config, SETTINGS, ChatModel).scoped(self.b))
        self.assertEqual(reopened.listing()['conversations'][0]['id'], older)
        self.chats.send(newer, dict(business_id=str(self.b), request_key=str(uuid4()), text='Después'))
        self.assertEqual(reopened.listing()['conversations'][0]['id'], older)
        self.chats.pin(newer, payload)
        self.assertEqual([c['id'] for c in reopened.listing()['conversations'][:2]], [newer, older])
        self.assertEqual(self.chats.pin(older, payload)['pinned_at'], pinned)
        self.assertEqual(reopened.listing()['conversations'][0]['id'], newer)
        self.assertIsNone(self.chats.pin(newer, {**payload, 'pinned': False})['pinned_at'])
        self.assertEqual(reopened.listing()['conversations'][0]['id'], older)
        self.chats.pin(older, {**payload, 'pinned': False})
        self.assertEqual(reopened.listing()['conversations'][0]['id'], newer)
        self.assertEqual(reopened.detail(older)['turns'], [])

    def test_library_search_finds_titles_owner_messages_and_visible_responses(self):
        chat = self.chat()
        turn = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()),
                                         text='Introducción. ' * 350 + 'El inventario contiene 100%_literal.'))
        response = dict(kind='grounded_answer', text='Revisamos los márgenes.',
                        paragraphs=['La campaña de verano funciona.'],
                        evidence=dict(kind='evidence', claims=[dict(statement='Las mochilas aumentaron.')]),
                        snapshot=dict(text='secret-search-token'), tool_payload=dict(text='internal-tool-token'))
        with connect(self.config) as db:
            db.execute('UPDATE chat_conversations SET title=%s WHERE id=%s', ('Notas de Cafetería', chat))
            db.execute("UPDATE chat_turns SET response=%s,status='completed' WHERE id=%s", (Jsonb(response), turn['id']))
        for query in ('CAFETERIA', 'inventario', '100%_literal', 'MARGENES', 'campaña de verano', 'mochilas'):
            found = self.chats.listing(query)['conversations']
            self.assertEqual([c['id'] for c in found], [chat], query)
            if query != 'CAFETERIA':
                self.assertIn(library_query(query), library_query(found[0]['search_match']['text']))
                self.assertLess(len(found[0]['search_match']['text']), 400)
        for query in ('sin coincidencias', 'secret-search-token', 'internal-tool-token'):
            self.assertEqual(self.chats.listing(query)['conversations'], [], query)
        self.assertNotIn('search_match', self.chats.listing()['conversations'][0])

    def test_library_search_preserves_pins_and_excludes_deleted_and_foreign_chats(self):
        older, newer = self.chat(), self.chat()
        for chat in (older, newer):
            self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Búsqueda de productos.'))
        self.chats.pin(older, dict(business_id=str(self.b), pinned=True))
        self.assertEqual([c['id'] for c in self.chats.listing('productos')['conversations']], [older, newer])
        other = self.ws.save_business(dict(request_key=str(uuid4()), expected_active_id=str(self.b), name='Other shop', description='Other context'))
        foreign_chats = Conversations(self.ws.scoped(other['id']))
        foreign = foreign_chats.create(dict(business_id=str(other['id']), request_key=str(uuid4())))['id']
        foreign_chats.send(foreign, dict(business_id=str(other['id']), request_key=str(uuid4()), text='Búsqueda de productos.'))
        self.assertNotIn(foreign, [c['id'] for c in self.chats.listing('productos')['conversations']])
        self.chats.delete(older, dict(business_id=str(self.b)))
        self.assertEqual([c['id'] for c in self.chats.listing('productos')['conversations']], [newer])

    def test_library_search_http_is_authenticated_literal_and_bounded(self):
        chat = self.chat()
        self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='Oferta 100%_literal y C++ & café.'))
        client, server = self.http()
        self.assertEqual(client.get('/api/chats', params={'query': '100%_literal'}).status_code, 401)
        client.post('/api/login', json={'token': server.token})
        found = client.get('/api/chats', params={'query': 'C++ & cafe'})
        self.assertEqual(found.status_code, 200, found.text)
        self.assertEqual(found.json()['conversations'][0]['id'], str(chat))
        self.assertEqual(client.get('/api/chats', params={'query': 'x' * 301}).status_code, 400)
        self.assertEqual(client.get('/api/chats', params={'query': "' OR 1=1 --"}).json()['conversations'], [])

    def test_pin_http_validates_authentication_business_and_deleted_chats(self):
        chat = self.chat()
        client, server = self.http()
        path = f'/api/chats/{chat}/pin'
        payload = dict(business_id=str(self.b), pinned=True)
        self.assertEqual(client.post(path, json=payload).status_code, 401)
        client.post('/api/login', json={'token': server.token})
        saved = client.post(path, json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertIsNotNone(saved.json()['pinned_at'])
        self.assertEqual(client.get('/api/chats').json()['conversations'][0]['id'], str(chat))
        for value in (None, 1, 'true'):
            self.assertEqual(client.post(path, json={**payload, 'pinned': value}).status_code, 400)
        self.assertEqual(client.post(path, json={**payload, 'business_id': str(uuid4())}).status_code, 409)
        other = self.ws.save_business(dict(request_key=str(uuid4()), expected_active_id=str(self.b), name='Other shop', description='Other context'))
        foreign = Conversations(self.ws.scoped(other['id'])).create(dict(business_id=str(other['id']), request_key=str(uuid4())))['id']
        self.ws.select_business(dict(business_id=str(self.b)))
        self.assertEqual(client.post(f'/api/chats/{foreign}/pin', json=payload).status_code, 404)
        self.chats.delete(chat, dict(business_id=str(self.b)))
        self.assertEqual(client.post(path, json=payload).status_code, 404)

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

    def test_context_selections_survive_reload_and_validate_every_reference(self):
        from decision_room.agent import review
        from decision_room.context_references import normalize
        _, turn = self.complete()
        response = turn['response']
        base = {k: response[k] for k in ('report_id', 'report_version')}
        refs = [dict(**base, kind='insight', element_key=response['claims'][0]['key']),
                dict(**base, kind='section', element_key='summary')]
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='Explain selected content', context_references=refs)
        saved = self.chats.send(chat, payload)
        self.assertEqual(saved, self.chats.send(chat, payload))
        self.assertIsNone(self.chats.detail(chat)['conversation']['analysis_id'])
        reloaded = Conversations(self.ws.scoped(self.b)).detail(chat)['turns'][0]
        self.assertEqual(len(reloaded['attachments']), 2)
        self.assertEqual(reloaded['attachments'][0]['content']['statement'], response['claims'][0]['statement'])
        self.assertEqual(normalize(refs + [refs[0]]), refs)
        for bad in ([{**refs[0], 'element_key': 'missing'}], [{**refs[0], 'report_version': 'wrong'}],
                    [{**refs[0], 'content': {'value': 'invented'}}], refs * 5):
            with self.assertRaises(WebError):
                self.chats.send(chat, {**payload, 'request_key': str(uuid4()), 'context_references': bad})
        with self.assertRaises(WebError):
            self.chats.send(chat, {**payload, 'context_references': refs[:1]})
        other = self.ws.save_business(dict(request_key=str(uuid4()), name='Other context shop', description='Independent', expected_active_id=str(self.b)))
        isolated = Conversations(self.ws.scoped(other['id']))
        isolated_chat = isolated.create(dict(business_id=str(other['id']), request_key=str(uuid4())))
        with self.assertRaises(WebError):
            isolated.send(isolated_chat['id'], {**payload, 'business_id': str(other['id'])})
        review.hold(self.config, self.b, base['report_id'], reason='Controlled withdrawal.')
        attachments = self.chats.detail(chat)['turns'][0]['attachments']
        self.assertTrue(all(a['status'] == 'withdrawn' and 'content' not in a for a in attachments))
        self.assertEqual(saved, self.chats.send(chat, payload))
        with self.assertRaises(WebError):
            self.chats.send(chat, {**payload, 'request_key': str(uuid4())})

    def test_full_report_and_memory_selections_keep_identity_and_provenance(self):
        memory.change(self.config, self.b, action='declare', request_key=str(uuid4()), content=content())
        _, prior = self.complete()
        report = prior['response']
        with connect(self.config) as db:
            fact = memory.current(db, self.b)[0]
        refs = [dict(kind='memory', source_id=str(fact['fact_id']), source_version=str(fact['revision']), element_key='fact'),
                dict(kind='report', report_id=report['report_id'], report_version=report['report_version'], element_key='report')]
        seen = []
        def compare(model, context, correction=None):
            seen.append(context)
            if not context['retrievals']:
                return action('retrieve', retrieval=dict(tool='open_report', query='', id=report['report_id'], limit=1)), {}
            sources = list(context['available_sources'])
            return action('answer', text='El dato seleccionado procede del contexto del propietario.', sources=[s for s in sources if s.startswith(('selection/', 'tool/'))]), {}
        with patch.object(ChatModel, 'generate_chat', compare):
            turn = self.send(self.chat(), '¿Esta información procede del informe seleccionado?', context_references=refs)
        self.assertEqual(turn['status'], 'completed', turn)
        selected_report = turn['attachments'][1]
        self.assertEqual(selected_report['kind'], 'report')
        self.assertEqual(selected_report['title'], selected_report['report_title'])
        self.assertNotEqual(selected_report['title'], 'Resumen')
        self.assertEqual(selected_report['selection_scope'], 'whole_report')
        selected_fact = seen[-1]['available_sources']['selection/0']['content']
        self.assertIn('provenance', selected_fact)
        self.assertTrue(selected_fact['provenance']['origin_key'])
        self.assertEqual([e['request']['tool'] for e in seen[-1]['retrievals']], ['open_report'])
        self.assertEqual(seen[-1]['retrievals'][0]['response']['id'], report['report_id'])

    def test_business_selections_are_scoped_versioned_and_available_to_answers(self):
        from decision_room.context_references import normalize
        ref = dict(kind='business', source_id=str(self.b), source_version=str(self.business['profile_revision']), element_key='profile')
        seen = []
        def answer_selected(model, context, correction=None):
            seen.append(context)
            return action('answer', text='Synthetic test business.', sources=['selection/0']), {}
        chat = self.chat()
        with patch.object(ChatModel, 'generate_chat', answer_selected):
            turn = self.send(chat, 'Explain my selected profile', context_references=[ref])
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(turn['attachments'][0]['content']['statement'], self.business['description'])
        self.assertEqual(turn['attachments'][0]['href'], '#my-business')
        source = seen[-1]['available_sources']['selection/0']['content']
        self.assertEqual(source['authority'], 'owner_declared')
        self.assertEqual(seen[-1]['retrievals'], [])
        self.assertEqual(normalize([ref]), [ref])
        for invalid in (ref | {'source_id': str(uuid4())}, ref | {'source_version': '0'}, ref | {'element_key': 'invented'}, ref | {'content': 'injected'}):
            with self.assertRaises(WebError):
                self.send(chat, 'Explain this', context_references=[invalid])
        self.ws.save_business(dict(business_id=str(self.b), name=self.business['name'], description='Updated synthetic profile.', profile_revision=self.business['profile_revision']))
        attachment = Conversations(self.ws.scoped(self.b)).detail(chat)['turns'][0]['attachments'][0]
        self.assertEqual(attachment['status'], 'withdrawn')
        self.assertNotIn('content', attachment)
        with self.assertRaises(WebError):
            self.send(chat, 'Explain this', context_references=[ref])

    def test_selected_memory_can_change_before_routing_without_reviving_old_content(self):
        saved = memory.change(self.config, self.b, action='declare', request_key=str(uuid4()), content=content())
        with connect(self.config) as db:
            fact = memory.current(db, self.b)[0]
        ref = dict(kind='memory', source_id=str(fact['fact_id']), source_version=str(fact['revision']), element_key='fact')
        chat = self.chat()
        pending = self.chats.send(chat, dict(business_id=str(self.b), request_key=str(uuid4()), text='What about this?', context_references=[ref]))
        with connect(self.config) as db:
            payload = db.execute('SELECT payload FROM memory_sources WHERE id=(SELECT memory_source_id FROM chat_turns WHERE id=%s)', (pending['id'],)).fetchone()['payload']
            self.assertIn(fact['content']['statement'], payload['question'])
        memory.change(self.config, self.b, action='withdraw', request_key=str(uuid4()), fact_id=str(fact['fact_id']), expected_revision=fact['revision'])
        seen = []
        def answer_changed(model, context, correction=None):
            seen.append(context)
            return action('answer', text='La información seleccionada ha cambiado.', sources=['selection/0']), {}
        with patch.object(ChatModel, 'generate_chat', answer_changed):
            self.chats.run(pending['id'])
        turn = self.chats.detail(chat)['turns'][0]
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(seen[-1]['available_sources']['selection/0']['content']['status'], 'withdrawn')
        self.assertNotIn('content', turn['attachments'][0])
        with self.assertRaises(WebError):
            self.send(chat, 'What about this?', context_references=[ref])

    def test_multiple_reports_are_opened_cited_and_carried_into_investigation(self):
        _, first = self.complete()
        _, second = self.complete()
        refs = [dict(report_id=t['response']['report_id'], report_version=t['response']['report_version'],
                     kind='insight', element_key=t['response']['claims'][0]['key']) for t in (first, second)]
        chat = self.chat()
        seen = []
        def answer_selected(model, context, correction=None):
            seen.append(context)
            opened = {e['response'].get('id') for e in context['retrievals']}
            missing = next((r for r in refs if r['report_id'] not in opened), None)
            if missing:
                return action('retrieve', retrieval=dict(tool='open_report', query='', id=missing['report_id'], limit=1)), {}
            return action('answer', text='Ambos informes describen ventas registradas.', sources=['selection/0', 'selection/1', 'tool/0', 'tool/1']), {}
        with patch.object(ChatModel, 'generate_chat', answer_selected):
            turn = self.send(chat, 'Explain both selected reports', context_references=refs)
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertEqual(len(turn['attachments']), 2)
        self.assertEqual(len(seen[-1]['available_sources']['selection/0']['content']['claim_keys']), 1)
        self.assertIn('statement', seen[-1]['available_sources']['selection/1']['content']['content'])
        self.assertIsNone(self.chats.detail(chat)['conversation']['analysis_id'])
        selected_analysis = turn['attachments'][0]['analysis_id']
        with patch.object(ChatModel, 'generate_chat', return_value=(action('investigate', analysis_id=selected_analysis), {})):
            follow = self.send(chat, 'Investigate these reports', context_references=refs)
        self.assertEqual(follow['status'], 'processing', follow)
        import json
        continuation = json.loads(self.ws.row(follow['job_id'])['context'])
        self.assertEqual(continuation['context']['context_references'], refs)
        for ref in refs:
            self.assertIn(dict(kind='report', id=ref['report_id'], version=ref['report_version']), continuation['dependencies'])

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

    def test_report_metadata_answer_can_omit_full_report_attachment(self):
        chat, original = self.complete()
        report_id = original['response']['report_id']
        def respond(model, context, correction=None):
            if not context['retrievals']:
                return dict(action='retrieve', retrieval=dict(tool='open_report', id=report_id, query='', limit=5),
                            text='', analysis_id='', sources=[], include_report=False), {}
            result = context['retrievals'][0]['response']
            self.assertTrue(result['approved_at'])
            self.assertTrue(result['review_started_at'])
            self.assertIn('not the period', result['date_meaning'])
            return dict(action='answer', retrieval=None, analysis_id='', text='El informe ya está aprobado.',
                        sources=['tool/0'], include_report=False), {}
        with patch.object(ChatModel, 'generate_chat', respond):
            turn = self.send(chat, 'When was the report made?')
        self.assertEqual(turn['status'], 'completed', turn)
        self.assertTrue(turn['response']['sources'])
        self.assertNotIn('evidence', turn['response'])

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
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'], structured=True)
        self.chats.report(chat, t['id'], dict(business_id=str(self.b)))
        self.assertIn('Ventas', self.chats.report(chat, t['id']))
        presentation = self.chats.report(chat, t['id'], structured=True)
        self.assertIn('Ventas', presentation['title'])
        self.assertTrue(presentation['claims'][0]['evidence_details']['metrics'])
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
        with self.assertRaises(WebError):
            self.chats.report(chat, t['id'], structured=True)

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
        self.assertNotIn('deleted_conversations', client.get('/api/chats').json())
        self.assertEqual(client.post('/api/chats/' + chat + '/restore', json={'business_id': str(self.b)}).status_code, 404)
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
