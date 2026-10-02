"""Bounded explicit 429/503 retries; no retry of ambiguous read failures."""
import unittest
from unittest.mock import patch
import httpx
from decision_room.agent.model import ModelAPIError, ModelClient, ModelRequestUncertain, ModelSettings

class ModelRetryTests(unittest.TestCase):
    def run_model(self, handler):
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch('decision_room.agent.model.httpx.Client',return_value=client),patch('decision_room.agent.model.time.sleep') as sleep:
            result=ModelClient(ModelSettings('test',protocol='chat_completions')).generate({})
        return result,sleep

    def test_recovers_and_records_attempts(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return (httpx.Response(503,headers={'Retry-After':'3'}) if len(seen)<3 else
                    httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"action":"inspect"}'}}],'usage':{'total_tokens':10}}))
        (output,usage),sleep=self.run_model(handler)
        self.assertEqual(len(seen),3)
        self.assertEqual(output['action'],'inspect')
        self.assertEqual([a['status'] for a in usage['transport_attempts']],[503,503,200])
        self.assertEqual([a.args[0] for a in sleep.call_args_list],[3,3])
        self.assertTrue(usage['rejected_attempt_usage_unknown'])
        from decision_room.evaluation.assess import token_accounting
        accounted=token_accounting([{'usage':{**usage,'prompt_tokens':100,'completion_tokens':10}}])
        self.assertFalse(accounted['token_usage_complete'])
        self.assertEqual(accounted['rejected_attempts_with_unknown_usage'],2)
        self.assertEqual(accounted['known_input_tokens'],100)
        self.assertIsNone(accounted['input_tokens'])

    def test_exhaustion_and_permanent_errors(self):
        for status,count in ((503,3),(400,1),(401,1),(429,3)):
            with self.subTest(status=status), self.assertRaises(ModelAPIError) as caught:
                self.run_model(lambda request:httpx.Response(status))
            self.assertEqual(len(caught.exception.transport_attempts),count)

    def test_uncertain_read_not_retried(self):
        seen=[]
        def handler(request):
            seen.append(request)
            raise httpx.ReadTimeout('private diagnostic')
        with self.assertRaises(ModelRequestUncertain) as caught:
            self.run_model(handler)
        self.assertEqual(len(seen),1)
        self.assertNotIn('private',str(caught.exception))

    def test_429_honors_retry_after_and_uses_same_request(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return (httpx.Response(429,headers={'Retry-After':'3'}) if len(seen)<3 else
                    httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{}'}}],'usage':{}}))
        (_,usage),sleep=self.run_model(handler)
        self.assertEqual([a.args[0] for a in sleep.call_args_list],[3,3])
        self.assertEqual(len({r.content for r in seen}),1)
        self.assertEqual([a['status'] for a in usage['transport_attempts']],[429,429,200])

    def test_429_long_wait_is_not_shortened_or_retried(self):
        for delay in ('31', '999', 'inf', 'nan', '1e999'):
            seen=[]
            def handler(request):
                seen.append(request)
                return httpx.Response(429,headers={'Retry-After':delay})
            with self.subTest(delay=delay), self.assertRaises(ModelAPIError):
                self.run_model(handler)
            self.assertEqual(len(seen),1)

    def test_429_date_header_and_invalid_header(self):
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime
        from decision_room.agent.model import retry_delay
        response=httpx.Response(429,headers={'Retry-After':format_datetime(datetime.now(timezone.utc)+timedelta(seconds=20))})
        self.assertTrue(18 <= retry_delay(response,0) <= 20)
        self.assertEqual(retry_delay(httpx.Response(429,headers={'Retry-After':'invalid'}),1),4)

    def test_wait_cannot_exceed_request_budget(self):
        with patch('decision_room.agent.model.time.monotonic', side_effect=[0, 0, 179]), self.assertRaises(ModelAPIError) as caught:
            self.run_model(lambda request:httpx.Response(429,headers={'Retry-After':'3'}))
        self.assertEqual(len(caught.exception.transport_attempts),1)

    def test_quota_and_billing_rejections_are_not_retried(self):
        codes = ('insufficient_quota', 'credit_balance_exhausted',
                 'organization_spend_limit_exceeded', 'project_spend_limit_exceeded',
                 'organization_usage_limit_exceeded', 'billing_hard_limit_reached')
        for code in codes:
            seen = []
            def handler(request):
                seen.append(request)
                return httpx.Response(429, headers={'Retry-After': '2'}, json={
                    'error': {'code': code, 'type': 'insufficient_quota',
                              'message': 'do not retain customer or billing data'}})
            with self.subTest(code=code), self.assertRaises(ModelAPIError) as caught:
                self.run_model(handler)
            self.assertEqual(len(seen), 1)
            details = caught.exception.diagnostics
            self.assertEqual(details['error_code'], code)
            self.assertEqual(details['error_category'], 'account_limit')
            self.assertNotIn('message', details)

    def test_headers_and_error_code_explain_token_limit_and_minimum_wait(self):
        seen = []
        def handler(request):
            seen.append(request)
            if len(seen) == 1:
                return httpx.Response(429, headers={
                    'Retry-After': '2', 'x-request-id': 'req_' + 'a' * 32,
                    'x-ratelimit-limit-tokens': '200000',
                    'x-ratelimit-remaining-tokens': '0',
                    'x-ratelimit-remaining-requests': '499',
                    'x-ratelimit-reset-tokens': '20s',
                }, json={'error': {'code': 'rate_limit_exceeded', 'type': 'tokens'}})
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}], 'usage': {}})
        (_, usage), sleep = self.run_model(handler)
        self.assertEqual(sleep.call_args.args[0], 20)
        error = usage['transport_attempts'][0]
        self.assertEqual(error['error_category'], 'rate_limit')
        self.assertEqual(error['error_type'], 'tokens')
        self.assertEqual(error['rate_limits']['remaining_requests'], 499)
        self.assertEqual(error['rate_limits']['limit_tokens'], 200000)
        self.assertEqual(error['request_id'], 'req_' + 'a' * 32)

    def test_success_headers_are_preserved_without_unknown_usage(self):
        from decision_room.evaluation.assess import token_accounting
        (_, usage), sleep = self.run_model(lambda request: httpx.Response(200,
            headers={'x-ratelimit-limit-tokens': '200000', 'x-ratelimit-remaining-tokens': '180000'},
            json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
                  'usage': {'prompt_tokens': 10, 'completion_tokens': 1}}))
        self.assertFalse(sleep.called)
        self.assertFalse(usage['rejected_attempt_usage_unknown'])
        self.assertEqual(usage['transport_attempts'][0]['rate_limits']['limit_tokens'], 200000)
        self.assertTrue(token_accounting([{'usage': usage}])['token_usage_complete'])

    def test_untrusted_body_and_headers_never_enter_diagnostics(self):
        secret = 'sk-' + 'x' * 40
        def handler(request):
            return httpx.Response(400, headers={
                'Authorization': 'Bearer ' + secret, 'Set-Cookie': secret,
                'x-request-id': secret, 'x-ratelimit-limit-tokens': secret,
                'x-ratelimit-reset-tokens': secret,
            }, json={'error': {'message': secret, 'param': secret, 'code': secret, 'type': secret}})
        with self.assertRaises(ModelAPIError) as caught:
            self.run_model(handler)
        self.assertNotIn(secret, str(caught.exception.diagnostics))
        self.assertNotIn(secret, str(caught.exception))
        self.assertEqual(caught.exception.diagnostics, {'error_code': 'unrecognized', 'error_type': 'unrecognized'})

    def test_long_reset_and_503_wait_are_not_shortened(self):
        responses = [
            httpx.Response(503, headers={'Retry-After': '999'}),
            httpx.Response(429, headers={'Retry-After': '2', 'x-ratelimit-remaining-tokens': '0', 'x-ratelimit-reset-tokens': '1m0.5s'}),
        ]
        for response in responses:
            seen = []
            def handler(request):
                seen.append(request)
                return response
            with self.subTest(status=response.status_code), self.assertRaises(ModelAPIError):
                self.run_model(handler)
            self.assertEqual(len(seen), 1)

    def test_non_json_oversized_and_interrupted_error_body_still_reject_safely(self):
        from decision_room.agent.model_transport import diagnostics, MAX_ERROR_BYTES
        for content in (b'<html>upstream unavailable</html>', b'x' * (MAX_ERROR_BYTES + 1)):
            response = httpx.Response(429, headers={'x-ratelimit-limit-tokens': '200000'}, content=content)
            self.assertEqual(diagnostics(response), {'rate_limits': {'limit_tokens': 200000}})
        response = httpx.Response(429, headers={'Retry-After': '4'})
        with patch.object(response, 'iter_bytes', side_effect=httpx.ReadTimeout('private body')):
            self.assertEqual(diagnostics(response), {'retry_after_seconds': 4})

    def test_openai_adds_jitter_without_retrying_before_server_hint(self):
        seen = []
        def handler(request):
            seen.append(request)
            return httpx.Response(429, headers={'Retry-After': '3'}) if len(seen) == 1 else httpx.Response(200,
                json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}], 'usage': {}})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'}), patch('decision_room.agent.model.httpx.Client', return_value=client), \
             patch('decision_room.agent.model.random.uniform', return_value=.5), patch('decision_room.agent.model.time.sleep') as sleep:
            ModelClient(ModelSettings('test', protocol='openai', base_url='https://api.openai.com/v1')).generate({})
        self.assertEqual(sleep.call_args.args[0], 3.5)
