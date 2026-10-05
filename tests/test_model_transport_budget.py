"""Offline transport regressions: deadlines, reset hints and shared admission."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx

from decision_room.agent.model import ModelClient, ModelSettings, ModelRequestUncertain
from decision_room.agent.model_pacing import estimate_tokens, reserve


class TransportBudgetTests(unittest.TestCase):
    def call(self, handler, settings=None):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with patch('decision_room.agent.model.httpx.AsyncClient', return_value=client):
            return ModelClient(settings or ModelSettings('test', protocol='chat_completions')).generate({})

    def test_nonzero_remaining_still_waits_full_token_reset(self):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1:
                return httpx.Response(429, headers={'Retry-After': '13',
                    'x-ratelimit-remaining-tokens': '1000', 'x-ratelimit-reset-tokens': '44s'},
                    json={'error': {'code': 'rate_limit_exceeded', 'type': 'tokens'}})
            return httpx.Response(200, json={'choices': [{'finish_reason':'stop', 'message':{'content':'{}'}}]})
        with patch('decision_room.agent.model.asyncio.sleep') as sleep:
            _, usage = self.call(handler)
        self.assertEqual(sleep.call_args.args, (44,))
        self.assertEqual(usage['transport_attempts'][0]['retry_delay_seconds'], 44)

    def test_rejection_then_connection_failure_retries_without_running_action_twice(self):
        calls = []
        def handler(request):
            calls.append(request)
            if len(calls) == 1: return httpx.Response(429)
            if len(calls) == 2: raise httpx.RemoteProtocolError('private')
            return httpx.Response(200, json={'choices': [{'finish_reason':'stop', 'message':{'content':'{}'}}]})
        with patch('decision_room.agent.model.asyncio.sleep'):
            _, usage = self.call(handler)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len({r.content for r in calls}), 1)
        self.assertTrue(usage['transport_attempts'][1]['retry_after_rejection'])
        self.assertNotIn('private', str(usage))

    def test_first_protocol_failure_and_accepted_interruption_remain_uncertain(self):
        class Broken(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{'
                raise httpx.RemoteProtocolError('private')
        for accepted in (False, True):
            calls = []
            def handler(request):
                calls.append(request)
                if accepted:
                    if len(calls) == 1: return httpx.Response(429)
                    return httpx.Response(200, stream=Broken())
                raise httpx.RemoteProtocolError('private')
            with self.subTest(accepted=accepted), patch('decision_room.agent.model.asyncio.sleep'), self.assertRaises(ModelRequestUncertain):
                self.call(handler)
            self.assertEqual(len(calls), 2 if accepted else 1)

    def test_hard_deadline_cancels_trickling_body_and_hung_response_headers(self):
        sleep = asyncio.sleep
        closed = []
        class Slow(httpx.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    yield b' '
                    await sleep(.05)
            async def aclose(self): closed.append(True)
        async def hung(request):
            await sleep(60)
        for handler in (lambda request: httpx.Response(200, stream=Slow()), hung):
            start = time.monotonic()
            with self.assertRaises(ModelRequestUncertain):
                self.call(handler, ModelSettings('test', protocol='chat_completions', timeout_seconds=1))
            self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(closed, [True])

    def test_estimate_counts_schema_correction_and_output(self):
        payload = {'messages':[{'content':'texto'}], 'response_format':{'schema':'x'*1000}, 'max_completion_tokens':500}
        self.assertGreater(estimate_tokens(payload), 800)
        longer = {**payload, 'messages':payload['messages'] + [{'content':'corrección'*1000}]}
        self.assertGreater(estimate_tokens(longer), estimate_tokens(payload))

    def test_shared_rolling_window_spaces_roles_and_reserves_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'rate.sqlite3'
            self.assertEqual(reserve(path, 'same-model', 120000, 200000, 100), 0)
            self.assertEqual(reserve(path, 'same-model', 120000, 200000, 110), 50)
            self.assertEqual(reserve(path, 'same-model', 120000, 200000, 160), 0)
            # Independent callers cannot both spend the remaining tokens.
            with ThreadPoolExecutor(2) as pool:
                waits = list(pool.map(lambda _: reserve(path, 'same-model', 60000, 200000, 170), range(2)))
            self.assertEqual(sorted(waits), [0, 50])
            self.assertEqual(reserve(path, 'different-model', 120000, 200000, 170), 0)

    def test_oversized_call_is_refused_locally(self):
        settings = ModelSettings('test', protocol='openai', base_url='https://api.openai.com/v1', tokens_per_minute=1)
        with patch.dict('os.environ', {'OPENAI_API_KEY':'offline-test'}), self.assertRaisesRegex(ValueError, 'exceeds configured TPM'):
            self.call(lambda request: self.fail('Must not send'), settings)
