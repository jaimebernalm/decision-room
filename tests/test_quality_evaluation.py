import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from decision_room.evaluation.quality import assess, compare, digest, ref_key, resources, RUBRIC, RUBRIC_39, delivered_values, expected_value
from decision_room.evaluation.quality_cases import bruma_reference
from decision_room.evaluation.quality_runner import summary, evaluation_reference
from decision_room.evaluation.runner import write


class QualityTests(unittest.TestCase):
    def fixture(self):
        ref = {'execution_id': 'e', 'metric': 'sales'}
        report = {'claims': [{'evidence': [ref]}], 'charts': [], 'highlights': [], 'question_coverage': []}
        review = dict(publishable=True, status='approved', checks=[{'passed': True}], report=report,
                      observations=[dict(execution_id='e', status='completed', current=True,
                                         result={'metrics': {'sales': '120'}})])
        state = dict(status='completed', source_stable=True, resume_idempotent=True, intent='discover')
        oracle = dict(required=['sales'], metrics={'sales': '120'})
        assessment = dict(reviewer='development_review', notes='Inspected source definition and delivered scope',
            report_sha256=digest(report), rubric={k: dict(score=2, reason='Reviewed against source and owner request') for k in RUBRIC},
            bindings={ref_key(ref): {'reference': 'sales', 'meaning': 'Same period and tax-free sales definition'}})
        return state, review, oracle, assessment

    def test_approval_is_not_independent_acceptance(self):
        state, review, oracle, _ = self.fixture()
        got = assess(state, review, oracle)
        self.assertFalse(got['accepted']); self.assertEqual(got['status'], 'needs_independent_review')

    def test_delivery_rubric_rejects_unsupported_reaction_and_false_visual(self):
        state, review, oracle, assessment = self.fixture()
        assessment['rubric_version'] = 2
        assessment['rubric'] = {k: dict(score=2, reason='Independent semantic review') for k in RUBRIC_39}
        self.assertTrue(assess(state, review, oracle, assessment)['accepted'])
        for criterion in ('decision_support', 'visual_integrity', 'source_uncertainty'):
            with self.subTest(criterion=criterion):
                invalid = copy.deepcopy(assessment)
                invalid['rubric'][criterion] = dict(score=1, reason='Observed material limitation in delivered explanation')
                self.assertFalse(assess(state, review, oracle, invalid)['accepted'])
        assessment['rubric_version'] = 99
        self.assertFalse(assess(state, review, oracle, assessment)['accepted'])

    def test_orientation_and_tooltip_values_require_independent_bindings(self):
        state, review, oracle, assessment = self.fixture()
        ref = dict(execution_id='e', metric='change')
        review['observations'][0]['result']['metrics']['change'] = 5
        review['report']['claims'][0]['orientation'] = dict(evidence=[ref])
        review['report']['charts'] = [dict(points=[], details=[dict(values=[dict(value=ref)])])]
        assessment['report_sha256'] = digest(review['report'])
        self.assertEqual(len(delivered_values(review)), 2)
        self.assertFalse(assess(state, review, oracle, assessment)['accepted'])
        oracle['metrics']['change'] = 5
        assessment['bindings'][ref_key(ref)] = dict(reference='change', meaning='Same focal period and units')
        self.assertTrue(assess(state, review, oracle, assessment)['accepted'])
        review['observations'][0]['result']['metrics']['change'] = 6
        self.assertFalse(assess(state, review, oracle, assessment)['accepted'])

    def test_discovery_selection_is_judged_against_goal_not_fixed_global_totals(self):
        state, review, oracle, assessment = self.fixture()
        assessment['rubric_version'] = 2
        assessment['rubric'] = {k: dict(score=2, reason='Source-backed selection answers the original goal and periods') for k in RUBRIC_39}
        oracle['required'] = ['different_global_total']
        self.assertTrue(assess(state, review, oracle, assessment)['accepted'])
        for criterion, score in [('coverage', 0), ('comparability', 1)]:
            invalid = copy.deepcopy(assessment)
            invalid['rubric'][criterion]['score'] = score
            self.assertFalse(assess(state, review, oracle, invalid)['accepted'])
        state['intent'] = 'organize'
        self.assertFalse(assess(state, review, oracle, assessment)['checks']['required_results'])

    def test_partial_uses_owner_delivery_instead_of_internal_branches(self):
        state, review, oracle, assessment = self.fixture()
        review['report']['owner_coverage'] = [dict(status='partial')]
        assessment['report_sha256'] = digest(review['report'])
        self.assertTrue(assess(state, review, oracle, assessment)['partial'])
        review['report']['owner_coverage'] = [dict(status='complete')]
        review['report']['question_coverage'] = [dict(status='unavailable')]
        assessment['report_sha256'] = digest(review['report'])
        self.assertFalse(assess(state, review, oracle, assessment)['partial'])

    def test_valid_and_wrong_number(self):
        state, review, oracle, a = self.fixture()
        self.assertTrue(assess(state, review, oracle, a)['accepted'])
        review['observations'][0]['result']['metrics']['sales'] = '121'
        self.assertFalse(assess(state, review, oracle, a)['accepted'])

    def test_stale_review_assessment_is_rejected(self):
        state, review, oracle, a = self.fixture()
        review['report']['summary'] = 'A new unsupported statement'
        self.assertFalse(assess(state, review, oracle, a)['checks']['exact_delivery'])

    def test_text_identity_must_match_an_independent_source_value(self):
        state, review, oracle, a = self.fixture()
        oracle['metrics']['sales'] = '165 | Original name'
        review['observations'][0]['result']['metrics']['sales'] = '165 | Original name'
        next(iter(a['bindings'].values()))['reference'] = dict(op='text', args=['sales'])
        self.assertTrue(assess(state, review, oracle, a)['accepted'])
        review['observations'][0]['result']['metrics']['sales'] = '166 | Original name'
        self.assertFalse(assess(state, review, oracle, a)['accepted'])
        next(iter(a['bindings'].values()))['reference'] = dict(op='text', args=['166 | Original name'])
        self.assertFalse(assess(state, review, oracle, a)['accepted'])

    def test_missing_binding_and_wrong_semantics_fail(self):
        state, review, oracle, a = self.fixture()
        a['bindings'] = {}
        self.assertFalse(assess(state, review, oracle, a)['accepted'])
        a = self.fixture()[3]
        next(iter(a['bindings'].values()))['meaning'] = ''
        self.assertFalse(assess(state, review, oracle, a)['accepted'])

    def test_compound_citation_checks_each_source_value(self):
        state, review, oracle, a = self.fixture()
        oracle['metrics'].update(label='165 | Original product', earlier='100', later='120')
        expression = dict(op='format', template='{0} ({1:.6f})', args=[
            dict(op='text', args=['label']), dict(op='difference', args=['earlier', 'later'])])
        oracle['required'] = ['earlier', 'later']
        next(iter(a['bindings'].values()))['reference'] = expression
        review['observations'][0]['result']['metrics']['sales'] = '165 | Original product (20.000000)'
        self.assertTrue(assess(state, review, oracle, a)['accepted'])
        review['observations'][0]['result']['metrics']['sales'] = '165 | Original product (21.000000)'
        self.assertFalse(assess(state, review, oracle, a)['accepted'])

    def test_compound_reference_cannot_embed_numbers_or_access_objects(self):
        metrics = dict(x='10', y='20')
        for template, args in [('100 {0}', ['x']), ('{0.real}', ['x']),
                               ('{0!r}', ['x']), ('{0:.13f}', ['x']),
                               ('{0}', ['x', 'y']), ('{1}', ['x'])]:
            with self.subTest(template=template), self.assertRaises(ValueError):
                expected_value(dict(op='format', template=template, args=args), metrics)
    def test_every_chart_point_must_be_bound_and_correct_unit(self):
        state, review, oracle, a = self.fixture()
        review['observations'][0]['result']['series'] = {'daily': {'unit': 'units', 'points': [{'label': 'x', 'value': 1}, {'label': 'y', 'value': 2}]}}
        review['report']['charts'] = [{'series': {'execution_id': 'e', 'series': 'daily'}, 'unit': 'units'}]
        a['report_sha256'] = digest(review['report'])
        self.assertEqual(len(delivered_values(review)), 3)
        self.assertFalse(assess(state, review, oracle, a)['checks']['all_delivered_values_bound'])
        review['report']['charts'][0]['unit'] = 'EUR'
        with self.assertRaisesRegex(ValueError, 'unit'):
            delivered_values(review)

    def test_stale_evidence_and_duplicate_labels_fail(self):
        state, review, oracle, a = self.fixture()
        review['observations'][0]['current'] = False
        self.assertFalse(assess(state, review, oracle, a)['accepted'])
        review['observations'][0]['current'] = True
        review['observations'][0]['result']['series'] = {'s': {'unit': 'u', 'points': [{'label': 'x', 'value': 1}] * 2}}
        review['report']['charts'] = [{'series': {'execution_id': 'e', 'series': 's'}, 'unit': 'u'}]
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            delivered_values(review)

    def test_usefulness_depends_on_intent(self):
        state, review, oracle, a = self.fixture()
        a['rubric']['depth']['score'] = 1
        self.assertFalse(assess(state, review, oracle, a)['accepted'])
        state['intent'] = 'organize'
        self.assertTrue(assess(state, review, oracle, a)['accepted'])
        a['rubric']['coverage']['score'] = 0
        self.assertFalse(assess(state, review, oracle, a)['accepted'])

    def test_partial_does_not_claim_complete(self):
        state, review, oracle, a = self.fixture()
        review['report']['question_coverage'] = [{'status': 'unavailable'}]
        a['report_sha256'] = digest(review['report'])
        a['rubric']['coverage'] = dict(score=1, reason='Useful quantities delivered; monetary definition explicitly unresolved')
        got = assess(state, review, oracle, a)
        self.assertTrue(got['accepted']); self.assertTrue(got['partial'])

    def test_failed_run_kept_in_denominator_and_not_speedup(self):
        rows = [dict(case='c', repetition=1, mode='serial', accepted=True, publishable=True, seconds=50),
                dict(case='c', repetition=1, mode='parallel', accepted=False, publishable=False, seconds=10),
                dict(case='c', repetition=2, mode='parallel', accepted=False)]
        got = compare(rows)
        self.assertEqual(got['modes']['parallel']['total'], 2)
        self.assertIsNone(got['modes']['parallel']['median_accepted_seconds'])
        self.assertIsNone(got['pairs'][0]['parallel_minus_serial_seconds'])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            compare(rows + [rows[0]])

    def test_cost_is_unknown_without_complete_usage_and_cache(self):
        rates = dict(source='operator supplied', as_of='2026-09-27', input_per_million=2,
                     cached_input_per_million=1, output_per_million=10)
        calls = [{'usage': {'prompt_tokens': 100, 'completion_tokens': 10, 'prompt_tokens_details': {'cached_tokens': 20}}}]
        self.assertEqual(resources(calls, rates=rates)['estimated_cost'], '0.00028')
        self.assertIsNone(resources(calls)['estimated_cost'])
        self.assertIsNone(resources(calls + [{'usage': None}], rates=rates)['estimated_cost'])
        calls[0]['usage'].pop('prompt_tokens_details')
        self.assertIsNone(resources(calls, rates=rates)['estimated_cost'])

    def test_planner_comparison_uses_explicit_modes_and_accepted_pairs(self):
        rows = [dict(case='c', repetition=1, mode='control', accepted=True, seconds=20),
                dict(case='c', repetition=1, mode='planner', accepted=True, seconds=30),
                dict(case='c', repetition=2, mode='control', accepted=True, seconds=20),
                dict(case='c', repetition=2, mode='planner', accepted=False, seconds=5)]
        got = compare(rows, ('control', 'planner'))
        self.assertEqual(got['pairs'][0]['planner_minus_control_seconds'], 10)
        self.assertIsNone(got['pairs'][1]['planner_minus_control_seconds'])
        self.assertEqual(got['modes']['planner']['total'], 2)
        renamed = [{**r, 'mode': {'control':'base', 'planner':'new'}[r['mode']]} for r in rows]
        self.assertEqual(compare(renamed, ('base','new'))['pairs'][0]['new_minus_base_seconds'], 10)

    def test_batch_cannot_accept_a_report_assessed_with_another_rubric(self):
        state, review, oracle, assessment = self.fixture()
        state.update(case='bruma-discover', dataset='bruma', repetition=1, mode='new', fixtures_stable=True)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'job').mkdir()
            write(root/'manifest.json',dict(jobs={'job':state}, rubric_version=2,
                comparison_modes=['base','new'], reference_sha256={'bruma':digest(oracle)}))
            write(root/'bruma-reference.json',oracle)
            for filename, value in [('state',state), ('review',review), ('assessment',assessment)]:
                write(root/'job'/(filename+'.json'),value)
            row = summary(root)['runs'][0]
            self.assertFalse(row['accepted'])
            self.assertFalse(row['checks']['rubric_comparable'])
            self.assertEqual(row['assessment_status'],'failed')
            assessment.update(rubric_version=2,rubric={k:dict(score=2,reason='Same independent source and goal review') for k in RUBRIC_39})
            write(root/'job/assessment.json',assessment)
            self.assertTrue(summary(root)['runs'][0]['accepted'])

    def test_supplement_adds_dimensions_without_overriding_frozen_answers(self):
        oracle = dict(metrics={'total': 5}, required=['total'])
        manifest = dict(fixtures={'wwi': {'source.csv': 'source-digest'}})
        supplement = dict(metrics={'cross': 3}, base_reference_sha256=digest(oracle),
                          fixtures=manifest['fixtures']['wwi'], producer_sha256='a' * 64)
        got = evaluation_reference(oracle, supplement, manifest, 'wwi')
        self.assertEqual(got['metrics'], dict(total=5, cross=3))
        self.assertEqual(got['required'], ['total'])
        self.assertEqual(oracle['metrics'], {'total': 5})
        for change in [dict(metrics={'total': 3}), dict(fixtures={'other.csv': 'changed'}),
                       dict(base_reference_sha256='changed'), dict(producer_sha256='')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                evaluation_reference(oracle, {**supplement, **change}, manifest, 'wwi')

    def test_missing_jobs_remain_in_summary(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = dict(case='bruma-discover', dataset='bruma', repetition=1, intent='discover', mode='parallel', status='not_run')
            write(root / 'manifest.json', dict(jobs={'missing': state}))
            write(root / 'bruma-reference.json', {'metrics': {'a': 1}, 'required': ['a']})
            got = summary(root)
            self.assertEqual(got['modes']['parallel']['total'], 1)
            self.assertEqual(got['modes']['parallel']['accepted'], 0)
            self.assertFalse(got['modes']['parallel']['usage_complete'])

class BrumaOracleTests(unittest.TestCase):
    def save(self, folder, name, rows):
        import csv
        path = folder / (name + '.csv')
        with path.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        return path

    def fixture(self, root):
        p = self.save(root, 'renamed dimension', [dict(producto_id='p', nombre='Coffee', categoria='c')])
        c = self.save(root, 'other', [dict(canal_id='s', nombre='Store', mercado='local')])
        s = self.save(root, 'arbitrary filename', [dict(fecha='2026-06-01', producto_id='p', canal_id='s', unidades='6'),
            dict(fecha='2026-06-02', producto_id='p', canal_id='s', unidades='4'),
            dict(fecha='2026-07-01', producto_id='p', canal_id='s', unidades='8')])
        return [p,c,s]

    def test_unequal_exposure_changes_interpretation_and_reconciles(self):
        with TemporaryDirectory() as temp:
            paths = self.fixture(Path(temp)); got = bruma_reference(paths)['metrics']
            self.assertEqual(got['change'], -2)
            self.assertEqual(got['channel_daily|Store|2026-06'], 5)
            self.assertEqual(got['channel_daily|Store|2026-07'], 8)
            self.assertEqual(got['product_channel_change|Coffee|Store'], got['change'])

    def test_duplicate_dimension_rejected(self):
        with TemporaryDirectory() as temp:
            root=Path(temp); paths=self.fixture(root)
            self.save(root,'renamed dimension',[dict(producto_id='p', nombre='Coffee', categoria='c')]*2)
            with self.assertRaisesRegex(ValueError,'Non-unique'):
                bruma_reference(paths)

    def test_orphan_and_invalid_quantity_are_not_silently_dropped(self):
        with TemporaryDirectory() as temp:
            root=Path(temp); paths=self.fixture(root)
            self.save(root,'arbitrary filename',[dict(fecha='2026-06-01',producto_id='missing',canal_id='s',unidades='1')])
            with self.assertRaises(KeyError):
                bruma_reference(paths)
            self.save(root,'arbitrary filename',[dict(fecha='2026-06-01',producto_id='p',canal_id='s',unidades='NaN')])
            with self.assertRaisesRegex(ValueError,'Non-finite'):
                bruma_reference(paths)

class DurableQualityRunnerTests(unittest.TestCase):
    def test_timeout_retains_attempt_and_unknown_usage(self):
        import hashlib
        import subprocess
        from decision_room.agent.model import ModelSettings
        from decision_room.evaluation.quality_runner import run
        from decision_room.evaluation.quality_cases import CASES
        with TemporaryDirectory() as temp:
            root=Path(temp); source=root/'csv'; source.mkdir(); f=source/'fixture.csv'; f.write_text('x\n1\n')
            output=root/'batch'; output.mkdir()
            oracle=dict(metrics={'x':1},required=['x'])
            initial=dict(case='bruma-discover',dataset='bruma',intent='discover',mode='serial',repetition=1,status='not_run',key='test')
            manifest=dict(source_sha256='v',model=ModelSettings('test').__dict__,repeats=1,
                cases={'bruma-discover':CASES['bruma-discover']},
                fixtures={'bruma':{str(f):hashlib.sha256(f.read_bytes()).hexdigest()}},
                jobs={'job':initial},database='test',storage=str(output/'storage'),reference_sha256={'bruma':digest(oracle)})
            write(output/'manifest.json',manifest); write(output/'bruma-reference.json',oracle)
            def collect(config,state,job):
                state['research_id']='durable'
                write(job/'resources.json',{'calls':[{'usage':None}], 'executions':[]})
            with patch('decision_room.evaluation.quality_runner.source_version',return_value='v'), \
                 patch('decision_room.evaluation.quality_runner.ModelSettings.load',return_value=ModelSettings('test')), \
                 patch('decision_room.evaluation.quality_runner.configuration',return_value=None), \
                 patch('decision_room.evaluation.quality_runner.migrate'), \
                 patch('decision_room.evaluation.quality_runner.preflight'), \
                 patch('decision_room.evaluation.quality_runner.collect',side_effect=collect), \
                 patch('decision_room.evaluation.quality_runner.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',1800)), \
                 patch('decision_room.evaluation.quality_runner.time.monotonic',side_effect=[10,1810]):
                got=run(output,{'bruma':source},1,['bruma-discover'])
            state=json.loads((output/'job/state.json').read_text())
            self.assertEqual(state['status'],'interrupted')
            self.assertEqual(state['seconds'],1800)
            self.assertEqual(state['research_id'],'durable')
            self.assertFalse(got['runs'][0]['accepted'])
            self.assertFalse(got['runs'][0]['token_usage_complete'])

    def test_oracle_expressions_use_only_reference_values(self):
        from decision_room.evaluation.quality import expected_value
        self.assertEqual(expected_value({'op':'percent_change','args':['a','b']},{'a':100,'b':120}),20)
        with self.assertRaises((KeyError,TypeError)):
            expected_value({'op':'sum','args':[123]}, {'a':100})
        with self.assertRaises(ValueError):
            expected_value({'op':'eval','args':['a','b']},{'a':100,'b':120})

class TextReferenceTests(unittest.TestCase):
    def test_discovery_failure_is_counted_before_session_creation(self):
        from decision_room.evaluation.quality_runner import collect_discovery_resources
        with TemporaryDirectory() as temp, patch('decision_room.evaluation.quality_runner.connect') as connect:
            root=Path(temp)
            connect.return_value.__enter__.return_value.execute.return_value.fetchall.side_effect=[
                [dict(phase='data_discovery',status='running',usage=None)], [],
                [dict(phase='data_discovery',status='running',usage=None)], []]
            for _ in range(2):
                collect_discovery_resources(None,{'business_id':'b'},root)
            data=json.loads((root/'resources.json').read_text())
            self.assertEqual(len(data['calls']),1)
            self.assertTrue(data['includes_data_discovery'])
            got=resources(data['calls'])
            self.assertEqual(got['calls'],1)
            self.assertFalse(got['token_usage_complete'])

    def test_derived_change_and_boolean_use_independent_source_anchors(self):
        from decision_room.evaluation.quality import expected_value, reference_keys
        binding={'op':'difference','args':['before','after']}
        self.assertEqual(reference_keys(binding),{'before','after'})
        self.assertTrue(expected_value({'op':'equal','args':[binding,'change']},
                                       {'before':100,'after':120,'change':20}))
        state,report,oracle,a=QualityTests().fixture()
        ref=next(iter(a['bindings']))
        report['observations'][0]['result']['metrics']['sales']=True
        oracle['metrics']['other']='120'
        a['bindings'][ref]['reference']={'op':'equal','args':['sales','other']}
        self.assertTrue(assess(state,report,oracle,a)['accepted'])
        report['observations'][0]['result']['metrics']['sales']=1
        self.assertFalse(assess(state,report,oracle,a)['accepted'])

    def test_names_are_source_bound_not_accepted_from_the_model(self):
        from decision_room.evaluation.quality import expected_value
        oracle={'product|Coffee':12,'channel|Store':20}
        name={'op':'name','args':['product|Coffee']}
        self.assertEqual(expected_value(name,oracle),'Coffee')
        with self.assertRaises(ValueError):
            expected_value({'op':'name','args':['product|Wrong']},oracle)
        self.assertEqual(expected_value({'op':'join_names','args':[name,{'op':'name','args':['channel|Store']}]},oracle),'Coffee × Store')

    def test_unknown_reference_hash_prevents_summary_acceptance(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);job=root/'j';job.mkdir()
            state,report,oracle,assessment=QualityTests().fixture()
            state.update(case='c',dataset='bruma',mode='serial',repetition=1,fixtures_stable=True)
            write(root/'manifest.json',{'jobs':{'j':state},'reference_sha256':{'bruma':'changed'}})
            write(root/'bruma-reference.json',oracle)
            write(job/'state.json',state);write(job/'review.json',report);write(job/'assessment.json',assessment)
            got=summary(root)['runs'][0]
            self.assertFalse(got['accepted']); self.assertFalse(got['checks']['reference_unchanged'])
            self.assertEqual(got['assessment_status'], 'failed')

class EvidencePreservationTests(unittest.TestCase):
    def test_success_survives_until_registration_but_failed_code_can_be_fixed(self):
        from decision_room.agent.research_contract import validate_research_action
        task=dict(key='work',status='ready',depends_on=[],table_ids=['t'])
        snapshot=dict(proposal={'investigations':[task],'questions':[]},answers=[])
        observation=dict(investigation_key='work',status='completed',result={'metrics':{'total':3}})
        action=dict(action='execute',investigation_key='work',table_ids=['t'],code='additional work',summary='Expand scope',metric_keys=[])
        options=dict(max_attempts_per_investigation=3,max_investigations=2)
        with self.assertRaisesRegex(ValueError,'Preserve the completed result'):
            validate_research_action(action,snapshot,[observation],[],options)
        saved=validate_research_action({**action,'action':'record_candidate','table_ids':[],'code':'','metric_keys':['total']},snapshot,[observation],[],options)
        self.assertEqual(saved['metric_keys'],['total'])
        observation['status']='failed'
        self.assertEqual(validate_research_action(action,snapshot,[observation],[],options)['action'],'execute')

    def test_preflight_failure_stops_before_models(self):
        from decision_room.evaluation.quality_runner import preflight
        with TemporaryDirectory() as temp, \
             patch('decision_room.evaluation.quality_runner.create_business',return_value={'id':'b'}), \
             patch('decision_room.evaluation.quality_runner.import_batch',return_value={'analysis':{'id':'a'}}), \
             patch('decision_room.service.describe',return_value={'files':[{'table_id':'t'}]}), \
             patch('decision_room.execution.execute',return_value=dict(id='e',status='failed',issue='bad bind mount',result=None,environment={})), \
             patch('decision_room.evaluation.quality_runner.ModelClient') as model:
            with self.assertRaisesRegex(ValueError,'no model calls made'):
                preflight(None,Path(temp))
            model.assert_not_called()
            self.assertEqual(json.loads((Path(temp)/'preflight.json').read_text())['status'],'failed')

class PartialDeliveryPolicyTests(unittest.TestCase):
    def test_only_secondary_followups_can_be_deferred(self):
        from decision_room.agent.review_contract import validate_coverage
        report=dict(claims=[dict(key='answer')],question_coverage=[
            dict(investigation_key='root',status='answered',claim_keys=['answer']),
            dict(investigation_key='extra',status='deferred',claim_keys=[])])
        context=dict(review_policy=3,plan={'investigations':[dict(key='root',status='ready'),dict(key='extra',status='ready',parent_key='root')]})
        validate_coverage(report,context)
        context['review_policy']=2
        with self.assertRaisesRegex(ValueError,'policy 3'):validate_coverage(report,context)
        context['review_policy']=3;context['plan']['investigations'][1].pop('parent_key')
        with self.assertRaisesRegex(ValueError,'followup'):validate_coverage(report,context)
        context['plan']['investigations'][1]['parent_key']='root'
        report['question_coverage'][1]['claim_keys']=['answer']
        with self.assertRaisesRegex(ValueError,'not answer claims'):validate_coverage(report,context)

    def test_reviewer_cannot_pass_deferred_work_as_an_answer(self):
        from decision_room.agent.review_contract import ReviewAction
        from decision_room.agent.review_policy import validate_assessment
        context=dict(review_policy=3,report_step=1,conversation=[],report={'charts':[], 'question_coverage':[
            dict(investigation_key='extra',status='deferred',claim_keys=[])]})
        raw=dict(action='approve',message='Useful partial goal; this followup is secondary',report=None,code='',table_ids=[],question='',
            assessment=dict(report_step=1,issues=[],delivery=dict(numbers='pass',meaning='pass',charts='not_applicable',coverage='pass',files='pass'),
                usefulness=dict(goal_alignment='pass',reason='Original goal answered; optional followup pending',questions=[
                    dict(investigation_key='extra',verdict='deferred',claim_keys=[],reason='Secondary view not delivered')])) )
        validate_assessment(ReviewAction.model_validate(raw),'reviewer',context)
        raw['assessment']['usefulness']['questions'][0]['verdict']='pass'
        with self.assertRaisesRegex(ValueError,'Undelivered'):validate_assessment(ReviewAction.model_validate(raw),'reviewer',context)
        raw['assessment']['usefulness']['questions'][0]['verdict']='deferred'
        raw['assessment']['usefulness']['goal_alignment']='fail'
        with self.assertRaisesRegex(ValueError,'Cannot approve failed usefulness'):
            validate_assessment(ReviewAction.model_validate(raw),'reviewer',context)
        # The reviewer must also be able to reject an inappropriate deferral.
        raw['action']='revise'
        raw['assessment']['usefulness']['questions'][0]['verdict']='fail'
        raw['assessment']['issues']=[dict(key='core',severity='blocker',status='open',
            target='coverage',detail='This followup is necessary to answer the accepted goal',
            resolution='',introduced_because='')]
        validate_assessment(ReviewAction.model_validate(raw),'reviewer',context)


if __name__ == '__main__':
    unittest.main()
