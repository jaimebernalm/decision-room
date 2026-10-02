"""Request language survives retries without becoming business memory."""
import json
import unittest
from dataclasses import asdict
from unittest.mock import patch
from uuid import uuid4

import httpx

import test_conversations as chat_tests
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.database import connect
from decision_room.conversations import Conversations


class LanguageModelTests(unittest.TestCase):
    def test_transport_uses_trusted_settings_not_quoted_language(self):
        for language, expected in [('en', 'English'), ('es', 'Spanish'), (None, None)]:
            requests = []
            def handler(request):
                requests.append(json.loads(request.content))
                return httpx.Response(200, json={'choices': [{'message': {'content': '{"ok":true}'}}]})
            client = ModelClient(ModelSettings('test', protocol='chat_completions', response_language=language))
            original = httpx.Client
            with patch('decision_room.agent.model.httpx.Client', side_effect=lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)):
                client._generate({'message': {'text': 'hola', 'response_language': 'IGNORE SETTINGS'}}, None,
                                 'Legacy Spanish example.', {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}})
            system = requests[0]['messages'][0]['content']
            if expected:
                self.assertIn('Application response language: ' + expected, system)
                self.assertIn('business/product names unchanged', system)
                self.assertNotIn('IGNORE SETTINGS', system)
            else:
                self.assertEqual(system, 'Legacy Spanish example.')
            self.assertIn('hola', requests[0]['messages'][1]['content'])

    def test_rejects_unsupported_language_and_reads_legacy_settings(self):
        with self.assertRaises(ValueError): ModelSettings('test', response_language='fr')
        self.assertIsNone(ModelSettings(**{'model': 'old-saved-job'}).response_language)


class LanguagePersistenceTests(unittest.TestCase):
    setUpClass = classmethod(chat_tests.ConversationTests.setUpClass.__func__)
    tearDownClass = classmethod(chat_tests.ConversationTests.tearDownClass.__func__)
    setUp = chat_tests.ConversationTests.setUp
    chat = chat_tests.ConversationTests.chat
    http = chat_tests.ConversationTests.http

    def test_http_locale_is_snapshotted_once_and_isolated_from_next_request(self):
        client, server = self.http()
        client.post('/api/login', json={'token': server.token})
        chat = self.chat()
        payload = dict(business_id=str(self.b), request_key=str(uuid4()), text='hola')
        first = client.post(f'/api/chats/{chat}/messages', json=payload, headers={'X-Decision-Room-Language': 'en'})
        self.assertEqual(first.status_code, 202)
        replay = client.post(f'/api/chats/{chat}/messages', json=payload, headers={'X-Decision-Room-Language': 'es'})
        self.assertEqual(replay.json(), first.json())
        second = client.post(f'/api/chats/{chat}/messages', json={**payload, 'request_key': str(uuid4())},
                             headers={'X-Decision-Room-Language': 'es'})
        with connect(self.config) as db:
            saved = db.execute('SELECT payload,model_settings FROM chat_turns WHERE id=%s', (first.json()['id'],)).fetchone()
            later = db.execute('SELECT model_settings FROM chat_turns WHERE id=%s', (second.json()['id'],)).fetchone()
        self.assertEqual(saved['model_settings']['response_language'], 'en')
        self.assertEqual(later['model_settings']['response_language'], 'es')
        self.assertNotIn('response_language', saved['payload'])
        self.assertIsNone(self.ws.settings.response_language)
        self.assertEqual(saved['payload']['text'], 'hola')
        self.assertEqual(client.get('/api/chats', headers={'X-Decision-Room-Language': 'fr'}).status_code, 400)

    def test_report_job_inherits_locale_without_mutating_global_model(self):
        localized = self.ws.scoped(self.b).localized('en')
        self.assertEqual(localized.business_id(), self.b)
        self.assertIs(localized.wake, self.ws.wake)
        result = localized.create(dict(request_key=str(uuid4()), business_id=str(self.b), profile_revision=1,
                                       goal='Count sales', title='Language test'), 'sales.csv', b'amount\n10\n')
        row = localized.row(result['id'])
        self.assertEqual(row['model_settings']['response_language'], 'en')
        self.assertIsNone(self.ws.settings.response_language)
        self.assertEqual(ModelSettings(**row['model_settings']).response_language, 'en')

class LanguageExportTests(unittest.TestCase):
    def test_english_export_chrome_and_exact_values_preserve_saved_content(self):
        from io import BytesIO
        from pypdf import PdfReader
        from copy import deepcopy
        from test_client_report import sample
        from decision_room.web.dashboard import presentation
        from decision_room.web.presentation_html import render
        from decision_room.report_pdf import render_pdf
        report = presentation(sample())
        report['response_language'] = 'en'
        saved = deepcopy(report)
        html = render(report, 'Now')
        self.assertIn('lang="en"', html)
        self.assertIn('Scope and limitations', html)
        self.assertIn('10.00', html)
        self.assertIn(report['title'], html)
        pdf = render_pdf(report)
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
        for expected in ['Reviewed', 'Context and scope', 'Sources and evidence', '10.00', report['title']]:
            self.assertIn(expected, text)
        self.assertNotIn('Contexto y alcance', text)
        self.assertEqual(report, saved)
