"""OpenAI transport and private local configuration, without live API calls."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.local_env import load_env


class OpenAITests(unittest.TestCase):
    def test_openai_payload_credentials_and_usage(self):
        settings = ModelSettings('gpt-6-luna', protocol='openai', base_url='https://api.openai.com/v1', reasoning='low')
        def handler(request):
            self.assertEqual(str(request.url), 'https://api.openai.com/v1/chat/completions')
            self.assertEqual(request.headers['Authorization'], 'Bearer openai-test-only')
            payload = json.loads(request.content)
            self.assertEqual(payload['reasoning_effort'], 'low')
            self.assertEqual(payload['max_completion_tokens'], 8192)
            self.assertNotIn('max_tokens', payload)
            self.assertNotIn('temperature', payload)
            self.assertFalse(payload['store'])
            self.assertTrue(payload['response_format']['json_schema']['strict'])
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{"action":"inspect"}'}}],
                                            'usage': {'completion_tokens': 100, 'completion_tokens_details': {'reasoning_tokens': 50}}})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'openai-test-only', 'DECISION_ROOM_AGENT_API_KEY': 'local-test-only'}), patch('decision_room.agent.model.httpx.Client', return_value=client):
            action, usage = ModelClient(settings).generate({})
        self.assertEqual(action['action'], 'inspect')
        self.assertEqual(usage['completion_tokens_details']['reasoning_tokens'], 50)
        self.assertNotIn('openai-test-only', json.dumps(asdict(settings)))

    def test_openai_key_never_goes_to_local_server(self):
        def handler(request):
            self.assertNotIn('Authorization', request.headers)
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'openai-test-only'}, clear=True), patch('decision_room.agent.model.httpx.Client', return_value=client):
            ModelClient(ModelSettings('local', protocol='lmstudio_structured')).generate({})

    def test_missing_key_and_wrong_destination_fail_before_request(self):
        with self.assertRaises(ValueError):
            ModelSettings('remote', protocol='openai', base_url='https://example.com/v1')
        with patch.dict(os.environ, {'DECISION_ROOM_AGENT_PROTOCOL': 'openai', 'DECISION_ROOM_AGENT_MODEL': 'gpt-6-luna'}, clear=True), patch('decision_room.agent.model.httpx.Client') as client:
            settings = ModelSettings.load()
            self.assertEqual(settings.base_url, 'https://api.openai.com/v1')
            with self.assertRaisesRegex(ValueError, 'OPENAI_API_KEY'):
                ModelClient(settings).generate({})
            client.assert_not_called()

    def test_env_precedence_and_no_shell_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'DECISION_ROOM_AGENT_MODEL': 'shell-choice'}, clear=True):
            path = Path(tmp) / '.env'
            path.write_text('DECISION_ROOM_AGENT_MODEL=file-choice\nOPENAI_API_KEY="literal-$(whoami)" # comment\nDECISION_ROOM_STORAGE="a path"\n')
            load_env(path)
            self.assertEqual(os.environ['DECISION_ROOM_AGENT_MODEL'], 'shell-choice')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'literal-$(whoami)')
            self.assertEqual(os.environ['DECISION_ROOM_STORAGE'], 'a path')

    def test_invalid_env_never_exposes_value_or_partially_loads(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            path = Path(tmp) / '.env'
            path.write_text('OPENAI_API_KEY=private-test-only\nHOME=private-path\n')
            with self.assertRaises(ValueError) as error:
                load_env(path)
            self.assertNotIn('private', str(error.exception))
            self.assertNotIn('OPENAI_API_KEY', os.environ)
