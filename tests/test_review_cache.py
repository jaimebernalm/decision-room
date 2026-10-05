"""Stable wire prefixes, contextual rejection and measured (not assumed) usage."""
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch
import httpx
from decision_room.agent.model import ModelClient,ModelSettings,record_request
from decision_room.agent.review_cache import schema,normalize,usage_summary
from decision_room.agent.review_contract import validate
from test_review_budget import large_context
from test_model_strict_schemas import assert_strict_objects


class ReviewCacheTests(unittest.TestCase):
    def test_schema_and_prefix_stable_across_roles_evidence_and_corrections(self):
        contexts=[large_context(),large_context()]
        for context in contexts:context['budgets']['review_stable_prefix']=True
        contexts[0]['role']='analyst';contexts[1]['role']='reviewer'
        contexts[1]['observations'][0]['result']['metrics']['new_metric']='99'
        contexts[1]['report']['summary']='Un borrador corregido.'
        requests=[]
        for i,context in enumerate(contexts):
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={
                'choices':[{'finish_reason':'stop','message':{'content':'{}'}}],
                'usage':{'prompt_tokens':1000,'prompt_tokens_details':{'cached_tokens':i*800}}})))
            with patch('decision_room.agent.model.httpx.AsyncClient',return_value=client),patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),record_request(requests.append):
                model=ModelClient(ModelSettings('offline',base_url='https://api.openai.com/v1',protocol='openai',tokens_per_minute=0))
                method=model.generate_analyst_review if i==0 else model.generate_reviewer
                method(context,correction='Corrige la referencia inexistente.' if i else None)
        a,b=[r['payload'] for r in requests]
        self.assertEqual(a['response_format'],b['response_format'])
        self.assertEqual(a['messages'][:2],b['messages'][:2])
        self.assertNotEqual(a['messages'][2:],b['messages'][2:])
        self.assertEqual(a['prompt_cache_key'],b['prompt_cache_key'])
        self.assertEqual(requests[0]['cache_prefix']['visible_prefix_sha256'],requests[1]['cache_prefix']['visible_prefix_sha256'])
        self.assertNotEqual(requests[0]['cache_prefix']['evidence_prefix_sha256'],requests[1]['cache_prefix']['evidence_prefix_sha256'])
        assert_strict_objects(self,a['response_format']['json_schema']['schema'])
        self.assertLessEqual(requests[1]['context_budget']['total_reserved'],70000)

    def test_evidence_prefix_precedes_changing_turns_and_keys_are_review_scoped(self):
        from decision_room.agent.review_cache import messages
        context=large_context();context['review_id']='review-1'
        context['budgets']['review_stable_prefix']=True
        before=messages(context,'system',None)
        changed=deepcopy(context);changed['role']='analyst'
        changed['budgets']['calls_used']=3;changed['report']['summary']='Texto corregido.'
        changed['conversation']=[]
        after=messages(changed,'system','Corregir estilo.')
        self.assertEqual(before[:3],after[:3])
        self.assertNotEqual(before[3:],after[3:])
        self.assertIn('observations',json.loads(before[2]['content'])['review_evidence'])
        self.assertNotIn('observations',json.loads(before[3]['content']))
        keys=[]
        for review_id in ('review-1','review-1','review-2'):
            changed['review_id']=review_id;captured=[]
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={
                'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]})))
            with patch('decision_room.agent.model.httpx.AsyncClient',return_value=client),patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),record_request(captured.append):
                ModelClient(ModelSettings('offline',base_url='https://api.openai.com/v1',protocol='openai',tokens_per_minute=0)).generate_reviewer(changed)
            keys.append(captured[0]['payload']['prompt_cache_key'])
            self.assertEqual(captured[0]['cache_prefix']['cache_key_scope'],'review')
        self.assertEqual(keys[0],keys[1]);self.assertNotEqual(keys[0],keys[2])

    def test_dynamic_evidence_ids_are_not_embedded_in_schema(self):
        context=large_context();context['budgets']['review_stable_prefix']=True
        before=schema(context)
        context['observations'][0]['result']['metrics'].update({f'extra_{i}':str(i) for i in range(1500)})
        self.assertEqual(schema(context),before)
        self.assertNotIn(context.get('owner_context'),json.dumps(before))
        from decision_room.agent.schema_limits import validate_enum_limits
        validate_enum_limits(schema(context))
        assert_strict_objects(self,before)

    def test_all_flag_combinations_keep_strict_objects(self):
        from itertools import product
        from test_panorama_contract_v2 import PanoramaContractTests, frozen_fixture
        fixture=PanoramaContractTests();fixture.frozen=frozen_fixture()
        for budget,guard,panorama in product((False,True),repeat=3):
            context=fixture.context()
            context['budgets'].update(review_context_budget=budget,review_loop_guard=guard,
                sales_panorama=panorama,sales_panorama_contract=2 if panorama else 0)
            with self.subTest(budget=budget,guard=guard,panorama=panorama):
                assert_strict_objects(self,schema(context))

    def test_panorama_list_adapter_rejects_duplicate_keys(self):
        report={'panorama_dispositions':[dict(signal_key='gap_a',decision={'disposition':'priority'})]}
        self.assertEqual(normalize({'report':report})['report']['panorama_dispositions'],{'gap_a':{'disposition':'priority'}})
        report['panorama_dispositions']*=2
        with self.assertRaises(ValueError):normalize({'report':report})

    def test_aggregation_distinguishes_missing_cached_usage_from_zero(self):
        calls=[{'usage':{'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':0}}},
               {'usage':{'prompt_tokens':900,'prompt_tokens_details':{'cached_tokens':800}}},
               {'usage':{'prompt_tokens':500}}, {'status':'failed'}]
        result=usage_summary(calls)
        self.assertEqual(result['cached_fraction'],.8)
        self.assertEqual(result['input_tokens'],1500)
        self.assertEqual(result['unknown_usage_calls'],1)
        self.assertEqual(result['cached_usage_reported_calls'],2)
        self.assertIsNone(usage_summary(calls[2:])['cached_tokens'])


class StableReviewPersistenceTests(unittest.TestCase):
    import test_review as fixtures
    setUpClass=classmethod(fixtures.ReviewTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.ReviewTests.tearDownClass.__func__)
    setUp=fixtures.ReviewTests.setUp

    def test_invalid_reference_gets_contextual_repair_and_wire_array_is_normalized(self):
        from decision_room.agent import review
        from test_review import DialogueModel
        class Writer(DialogueModel):
            def generate_analyst_review(self,context,correction=None):
                output,usage=super().generate_analyst_review(context,correction)
                output['report']['panorama_dispositions']=[]
                if correction is None:output['report']['claims'][0]['evidence'][0]['metric']='invented'
                else:
                    assert 'Valid current references' in correction
                    assert 'total' in correction
                return output,usage
        roles=Writer('plain')
        result=review.start(self.config,self.business,self.research['id'],request_key='cache-wire',
            review_stable_prefix=True,review_context_budget=True,analyst=roles,reviewer=roles)
        self.assertTrue(result['publishable'])
        self.assertEqual(result['report']['panorama_dispositions'],{})
        self.assertEqual(len(result['model_calls']),3)
