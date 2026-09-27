"""Bounded explicit 503 retries; no retry of ambiguous read failures."""
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
        for status,count in ((503,3),(400,1),(401,1),(429,1)):
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
