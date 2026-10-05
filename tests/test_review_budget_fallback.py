from copy import deepcopy
import unittest
from decision_room.agent.review_budget import fit,request_tokens,tokens,compact
from decision_room.agent.review_requirements import expose
from test_review_budget import large_context
from decision_room.agent.context import encoded


class BudgetFallbackTests(unittest.TestCase):
    def test_message_text_not_double_escaped(self):
        payload={'messages':[{'role':'user','content':'"\n'*5000}],'max_tokens':8000}
        self.assertLess(request_tokens(payload),tokens(payload))
        self.assertEqual(request_tokens(payload),tokens(payload['messages'][0]['content'])+8+tokens({}))

    def test_bulk_operations_use_deeper_compaction_without_losing_keys(self):
        context=expose(large_context());context['budgets']['review_context_tokens']=70000
        result=context['observations'][0]['result']
        result['notes']=[' '.join(str(i) for i in range(30000))]
        result['evidence']=[dict(metric='m'+str(i),operation='Aggregation over the original dated source.') for i in range(1000)]
        original=deepcopy(context)
        payload,audit=fit(context,{'messages':[],'max_tokens':8000},lambda v:[{'role':'user','content':encoded(v)}])
        self.assertEqual(audit['level'],2)
        self.assertLessEqual(audit['total_reserved'],70000)
        import json
        visible=json.loads(payload['messages'][0]['content'])
        self.assertEqual(visible['required_coverage_keys'],context['required_coverage_keys'])
        self.assertEqual(visible['citable_panorama_metrics'],context['citable_panorama_metrics'])
        self.assertEqual(visible['report'],context['report'])
        self.assertEqual(context,original)

    def test_protected_facts_expand_soft_budget_instead_of_losing_report(self):
        context=large_context();context['budgets']['review_context_tokens']=12000
        context['business_context']['doubts']=[' '.join(str(i) for i in range(7000))]
        payload,audit=fit(context,{'messages':[],'max_tokens':8000},lambda v:[{'role':'user','content':encoded(v)}])
        self.assertEqual(audit['strategy'],'expanded_budget')
        self.assertGreater(audit['total_reserved'],audit['target'])
        self.assertLessEqual(audit['total_reserved'],audit['hard_limit'])
        self.assertIn(context['business_context']['doubts'][0],payload['messages'][0]['content'])
        with self.assertRaisesRegex(ValueError,'hard limit'):
            fit(context,{'messages':[],'max_tokens':8000},lambda v:[{'role':'user','content':encoded(v)}],hard_limit=12000)
