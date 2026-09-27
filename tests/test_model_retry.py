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
            return (httpx.Response(503,headers={'Retry-After':'999'}) if len(seen)<3 else
                    httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':'{"action":"inspect"}'}}],'usage':{'total_tokens':10}}))
        (output,usage),sleep=self.run_model(handler)
        self.assertEqual(len(seen),3)
        self.assertEqual(output['action'],'inspect')
        self.assertEqual([a['status'] for a in usage['transport_attempts']],[503,503,200])
        self.assertEqual([a.args[0] for a in sleep.call_args_list],[5,5])
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
        for delay in ('31', '999', 'inf', 'nan'):
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
