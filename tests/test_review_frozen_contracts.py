from copy import deepcopy
import unittest
import jsonschema
from decision_room.agent.review_cache import schema
from decision_room.agent.review_requirements import inventories
from decision_room.agent.panorama_contract import metric_choices
from test_panorama_contract_v2 import PanoramaContractTests,frozen_fixture
from test_model_strict_schemas import assert_strict_objects


class FrozenContractTests(unittest.TestCase):
    def pair(self):
        fixture=PanoramaContractTests();fixture.frozen=frozen_fixture()
        context=fixture.context()
        context.update(review_policy=5,plan={'investigations':[
            dict(key='total',status='ready'),dict(key='channels',status='ready'),dict(key='costs',status='blocked')]})
        return context,fixture.report(context)

    def test_complete_inventories_survive_new_reviewer_calculation(self):
        context,_=self.pair();before=schema(context);listing=inventories(context)
        self.assertEqual(listing['required_coverage_keys'],['channels','total'])
        self.assertEqual(listing['allowed_coverage_keys'],['channels','costs','total'])
        self.assertEqual(len(listing['citable_panorama_metrics']),len(metric_choices(context)))
        context['observations'].append(dict(execution_id='new-reviewer',status='completed',current=True,
            result={'metrics':{'fresh':'1'},'series':{}}))
        context['role']='reviewer';context['report']={'summary':'Changed'}
        self.assertEqual(schema(context),before)
        self.assertEqual(inventories(context),listing)
        assert_strict_objects(self,before)

    def test_schema_rejects_invented_coverage_and_nonpanorama_metric(self):
        context,report=self.pair();s=schema(context)
        coverage=jsonschema.Draft202012Validator({'$defs':s['$defs'],'$ref':'#/$defs/QuestionCoverage'})
        entry=dict(investigation_key='total',status='answered',claim_keys=['finding'],explanation='Total calculado.')
        self.assertTrue(coverage.is_valid(entry))
        self.assertFalse(coverage.is_valid({**entry,'investigation_key':'invented_followup'}))
        self.assertFalse(coverage.is_valid({**entry,'investigation_key':'costs'}))
        priority=jsonschema.Draft202012Validator({'$defs':s['$defs'],'$ref':'#/$defs/PanoramaPriority'})
        valid=report['claims'][0]['panorama_priority'];self.assertTrue(priority.is_valid(valid))
        invalid=deepcopy(valid);invalid['evidence']=[{'execution_id':'new-reviewer','metric':'fresh'}]
        self.assertFalse(priority.is_valid(invalid))


class ExactCorrectionTests(FrozenContractTests):
    def test_missing_unknown_and_duplicate_coverage_are_explicit(self):
        from decision_room.agent.review_contract import validate_coverage
        from decision_room.agent.review_requirements import ReviewContractError
        context,report=self.pair()
        context['review_policy']=0;context['budgets']={};context['sales_panorama']={}
        report['question_coverage']=[dict(investigation_key=k,status='unavailable',claim_keys=[],explanation='Sin respuesta') for k in ('total','total','invented')]
        with self.assertRaises(ReviewContractError) as failure:validate_coverage(report,context)
        self.assertEqual(failure.exception.repair,dict(field='question_coverage',missing=['channels'],invalid=['invented'],valid=['channels','costs','total'],duplicates=['total']))

    def test_panorama_correction_lists_every_reference_without_1800_character_cut(self):
        from decision_room.agent.panorama_contract import validate
        from decision_room.agent.review_requirements import ReviewContractError
        from decision_room.agent.review_cache import diagnostics
        context,report=self.pair()
        report['claims'][0]['panorama_priority']['evidence']=[dict(execution_id='invented',metric='total')]
        with self.assertRaises(ReviewContractError) as failure:validate(report,context)
        text=diagnostics(failure.exception,context)
        self.assertGreater(len(text),1800)
        self.assertEqual(failure.exception.repair['valid'],inventories(context)['citable_panorama_metrics'])
        self.assertIn(failure.exception.repair['valid'][-1]['metric'],text)
        self.assertNotIn('sample',text)
