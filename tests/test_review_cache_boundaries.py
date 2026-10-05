from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import httpx
from decision_room.agent.model import ModelClient,ModelSettings,record_request
from test_review_budget import large_context


class CacheBoundaryTests(unittest.TestCase):
    def test_http_key_and_reusable_boundaries_and_usage_are_audited(self):
        recorded=[]
        for enabled,model in ((True,'gpt-6-luna'),(True,'gpt-5.4'),(False,'gpt-6-luna')):
            context=large_context();context['review_id']='synthetic-review'
            context['budgets'].update(review_stable_prefix=True,review_explicit_cache=enabled)
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={
                'choices':[{'finish_reason':'stop','message':{'content':'{}'}}],
                'usage':{'prompt_tokens':40000,'prompt_tokens_details':{'cached_tokens':9500,'cache_write_tokens':30000}}})))
            with patch('decision_room.agent.model.httpx.AsyncClient',return_value=client),patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),record_request(recorded.append):
                _,usage=ModelClient(ModelSettings(model,protocol='openai',base_url='https://api.openai.com/v1',tokens_per_minute=0)).generate_reviewer(context)
            sent=recorded[-1]['payload'];audit=recorded[-1]['cache_prefix']
            self.assertTrue(sent['prompt_cache_key'].startswith('dr-review-'))
            self.assertTrue(audit['cache_key_sent'])
            self.assertEqual(usage['prompt_tokens_details']['cached_tokens'],9500)
            self.assertEqual(usage['prompt_tokens_details']['cache_write_tokens'],30000)
            if enabled and model=='gpt-6-luna':
                self.assertEqual(sent['prompt_cache_options'],dict(mode='explicit',ttl='30m'))
                self.assertEqual(audit['breakpoint_messages'],[1,2])
                for index in (1,2):
                    block=sent['messages'][index]['content'][0]
                    self.assertEqual(block['prompt_cache_breakpoint'],{'mode':'explicit'})
                    json.loads(block['text'])
                self.assertIsInstance(sent['messages'][3]['content'],str)
            else:self.assertNotIn('prompt_cache_options',sent)
