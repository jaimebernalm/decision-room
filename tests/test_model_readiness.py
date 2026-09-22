"""Readiness probes must not generate text or trigger local model loading."""
import unittest
from unittest.mock import patch

import httpx

from decision_room.agent.model import ModelClient, ModelNotReady, ModelSettings


class ModelReadinessTests(unittest.TestCase):
    def check(self, payload, status=200):
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(status, json=payload)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        model = ModelClient(ModelSettings('test-model', protocol='lmstudio_structured'))
        try:
            with patch('decision_room.agent.model.httpx.Client', return_value=client):
                model.check_ready()
        finally:
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0].method, 'GET')
            self.assertEqual(requests[0].url.path, '/api/v1/models')
            self.assertEqual(requests[0].content, b'')

    def test_unloaded_or_other_model_does_not_pass(self):
        for models in ([], [{'key': 'test-model', 'loaded_instances': []}],
                       [{'key': 'another-model', 'loaded_instances': [{'id': 'another-model'}]}]):
            with self.subTest(models=models), self.assertRaisesRegex(ModelNotReady, 'no está cargado'):
                self.check({'models': models})

    def test_loaded_model_key_or_instance_identifier_passes(self):
        self.check({'models': [{'key': 'test-model', 'loaded_instances': [{'id': 'instance'}]}]})
        self.check({'models': [{'key': 'original-key', 'loaded_instances': [{'id': 'test-model'}]}]})

    def test_unavailable_or_invalid_server_is_safe(self):
        for status, body in ((503, {'secret': 'private server detail'}), (200, {}),
                             (200, {'models': [None]}), (200, {'models': None}),
                             (200, {'models': [{'key': 'test-model', 'loaded_instances': 'invalid'}]})):
            with self.subTest(status=status, body=body), self.assertRaises(ModelNotReady) as caught:
                self.check(body, status)
            self.assertNotIn('private', str(caught.exception))
        def disconnected(request):
            raise httpx.ConnectError('private detail')

        client = httpx.Client(transport=httpx.MockTransport(disconnected))
        with patch('decision_room.agent.model.httpx.Client', return_value=client), self.assertRaisesRegex(ModelNotReady, 'Abre LM Studio'):
            ModelClient(ModelSettings('test-model')).check_ready()

    def test_other_providers_do_not_receive_lmstudio_probe(self):
        with patch('decision_room.agent.model.httpx.Client') as client:
            ModelClient(ModelSettings('remote', protocol='chat_completions', base_url='https://example.com/v1')).check_ready()
            ModelClient(ModelSettings('local-other', protocol='chat_completions')).check_ready()
            client.assert_not_called()
