"""Empty gap inventory is not missing evidence; actual integrity still blocks."""
from copy import deepcopy
from datetime import date, timedelta
import unittest
from unittest.mock import patch
from decision_room.agent.panorama_obligations import obligations, impossible_demand
from decision_room.agent.review_loops import resolution
from decision_room.agent.review_context import model_context
from decision_room.agent.review_cache import schema
from test_model_strict_schemas import assert_strict_objects
from test_review_loop_guard import ResolutionSafetyTests
from test_panorama_contract_v2 import PanoramaContractTests, frozen_fixture


class ObligationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=PanoramaContractTests();cls.fixture.frozen=frozen_fixture()

    def context(self, gaps=False):
        context=self.fixture.context()
        if not gaps:
            context['sales_panorama']['signals']=[s for s in context['sales_panorama']['signals'] if s['kind']!='gap']
        report=self.fixture.report(context)
        events=ResolutionSafetyTests().context()
        for event in events['conversation']:
            if event['role']=='analyst':event['action']['report']=report
        context.update(events);context['report']=report
        context['budgets']=dict(sales_panorama=True,panorama_obligation_guard=True)
        issue=context['review_issues'][0]
        issue.update(key='panorama_dispositions_missing',kind='integrity',basis='evidence_integrity',
            requested_change=dict(field='panorama_dispositions',minimum_count=13))
        return context

    def test_no_gaps_with_changes_exact_obligations_and_controller_proof(self):
        context=self.context()
        self.assertTrue(context['sales_panorama']['signals'])
        self.assertTrue(all(s['kind']=='change' for s in context['sales_panorama']['signals']))
        expected=obligations(context)
        self.assertEqual(expected['required_gap_keys'],[])
        self.assertIn('Ninguna',expected['explanation'])
        result=resolution(context)
        self.assertEqual(result['disposition'],'publish_with_limitations')
        self.assertEqual(result['owner_limitations'],[])
        self.assertEqual(result['contract_proofs']['panorama_dispositions_missing']['exact_count'],0)
        self.assertEqual(result['issues'][0]['kind'],'integrity')

    def test_real_missing_gap_and_unstructured_text_cannot_be_waived(self):
        context=self.context(gaps=True)
        context['report']['panorama_dispositions']={}
        self.assertIsNone(impossible_demand(context['review_issues'][0],context))
        context=self.context();context['review_issues'][0]['requested_change']=None
        self.assertIsNone(resolution(context))
        context['budgets']['review_loop_guard']=True
        self.assertEqual(resolution(context)['disposition'],'blocked_integrity')

    def test_other_integrity_and_failed_calculations_still_block(self):
        for fault in ('new_integrity','old_integrity','check','numbers','priority'):
            context=self.context()
            if fault=='new_integrity':context['review_issues'].append(dict(context['review_issues'][0],key='false_number',requested_change=None))
            elif fault=='old_integrity':
                context['conversation'][1]=deepcopy(context['conversation'][1])
                context['conversation'][1]['action']['assessment']['issues'][0]['requested_change']=None
            elif fault=='check':context['checks']=[{'passed':False}]
            elif fault=='numbers':context['conversation'][-1]['action']['assessment']['delivery']['numbers']='fail'
            else:context['report']['claims'][0]['panorama_priority']=None
            with self.subTest(fault=fault):
                result=resolution(context)
                self.assertTrue(result is None or result['disposition']=='blocked_integrity')

    def test_flag_off_unchanged_and_both_schema_modes_strict(self):
        context=self.context()
        self.assertIn('panorama_dispositions',schema(context)['$defs']['RequestedChange']['properties']['field']['enum'])
        assert_strict_objects(self,schema(context))
        assert_strict_objects(self,self.fixture.schema(context))
        context['budgets']['panorama_obligation_guard']=False
        self.assertNotIn('panorama_dispositions',schema(context)['$defs']['RequestedChange']['properties']['field']['enum'])
        self.assertIsNone(resolution(context))

    def test_model_context_lists_material_gaps_before_compaction(self):
        context=self.context(gaps=True)
        context['sales_panorama']=deepcopy(self.fixture.frozen)
        context['budgets']['review_context_budget']=True
        view=model_context(context,'reviewer')
        self.assertEqual(view['panorama_obligations']['required_gap_keys'],obligations(context)['required_gap_keys'])
        self.assertGreater(view['panorama_obligations']['required_count'],0)


class ObligationPersistenceTests(unittest.TestCase):
    from test_sales_panorama_integration import PanoramaPersistenceTests as Base
    setUpClass=classmethod(Base.setUpClass.__func__)
    tearDownClass=classmethod(Base.tearDownClass.__func__)

    def setUp(self):
        rows=[[(date(2025,1,1)+timedelta(days=i)).isoformat()+' 00:00:00','Paper','Shop',1+i//30] for i in range(181)]
        with patch('test_sales_panorama_integration.fixture',return_value=rows):self.Base.setUp(self)

    def test_false_integrity_closes_on_second_review_and_replays_without_calls(self):
        from decision_room.agent import service,research,review
        from test_sales_panorama_integration import PanoramaDialogue
        from test_research import ResearchModel
        from test_review import assessed,action
        class ImpossibleReviewer(PanoramaDialogue):
            def generate_reviewer(inner,context,correction=None):
                inner.contexts.append(deepcopy(context))
                assert context['panorama_obligations']['required_gap_keys']==[]
                assert context['sales_panorama']['signals']
                response=assessed(action('revise','Se piden disposiciones de cambios.'),context)
                response['assessment']['issues'][0].update(key='panorama_dispositions_missing',kind='integrity',
                    target='report.panorama_dispositions',basis='evidence_integrity',
                    requested_change=dict(field='panorama_dispositions',minimum_count=13))
                return response,{}
        model=ResearchModel()
        parent=service.start(self.config,self.business,self.analysis,owner_context='Amount is unit price. Quantity is units.',request_key='plan',model=model)
        run=research.start(self.config,self.business,parent['id'],request_key='research',model=model,delegation=False)
        roles=ImpossibleReviewer('simple')
        result=review.start(self.config,self.business,run['id'],request_key='no-gap',sales_panorama=True,
            panorama_obligation_guard=True,review_context_budget=True,analyst=roles,reviewer=roles)
        self.assertTrue(result['publishable'],result.get('issue'))
        self.assertEqual(len(result['model_calls']),4)
        self.assertEqual(result['verification'],'controller_qualified_delivery')
        self.assertEqual(result['report']['panorama_dispositions'],{})
        self.assertEqual(result['controller_resolution']['owner_limitations'],[])
        self.assertEqual(result['review_issues'][0]['kind'],'integrity')
        self.assertTrue(all(e['action']['action']!='approve' for e in result['conversation']))
        resumed=review.resume(self.config,self.business,result['id'],analyst=roles,reviewer=roles)
        self.assertEqual(resumed['approved_sha256'],result['approved_sha256'])
        self.assertEqual(len(roles.contexts),4)
