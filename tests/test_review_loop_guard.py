"""Regression of three editorial loops; no model/API, real persistence in integration."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import jsonschema

from decision_room.agent import review
from decision_room.agent.review_contract import Claim
from decision_room.agent.review_loops import resolution
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.web.dashboard import presentation
from decision_room.report import export
from pathlib import Path
import test_review
from test_model_strict_schemas import assert_strict_objects


class StalledModel(test_review.DialogueModel):
    def __init__(self, kind='completeness', scenario='unchanged'):
        super().__init__()
        self.kind,self.scenario=kind,scenario
    def generate_analyst_review(self,context,correction=None):
        self.contexts.append(deepcopy(context))
        report=test_review.draft(context)
        report['claims'][0]['focal_combinations']=[dict(table_id=context['tables'][0]['id'],product=None,channel=None)]
        if self.scenario=='coverage':
            report['owner_coverage'][0].update(status='partial',explanation='Faltan costes para decidir el margen.')
        if self.scenario=='reactions':
            report['claims'][0]['orientation']=dict(segment='Canal principal',period='Periodo disponible',signal='Cambio registrado',
                evidence=report['claims'][0]['evidence'],relative_priority='Comprobar primero la continuidad.',knowledge='calculated',
                next_check='Contrastar los registros con pedidos.',decision_value='Decidir si comparar periodos.',limitation='',
                reactions=[dict(condition=f'Condición observable {i}',reaction=f'Comprobación concreta {i}') for i in range(4)])
        return test_review.action('submit','He añadido el cambio solicitado.',report=report),{}
    def generate_reviewer(self,context,correction=None):
        self.contexts.append(deepcopy(context))
        response=test_review.assessed(test_review.action('revise','Falta una comprobación concreta.'),context)
        issue=response['assessment']['issues'][0]
        issue.update(key='same_issue',kind=self.kind,basis='evidence_integrity' if self.kind=='integrity' else 'owner_goal',
            owner_deliverable_index=0,owner_quote=context['accepted_owner_request']['text'],claim_keys=['sales'],
            detail='Retira Cobertura del encargo.' if self.scenario=='coverage' else 'Añade una quinta reacción.' if self.scenario=='reactions' else 'Falta una comprobación concreta.',
            owner_limitation='Queda pendiente una comprobación antes de decidir.' if self.kind=='completeness' else None,
            requested_change=dict(field='reactions',minimum_count=5) if self.scenario=='reactions' else None)
        return response,{}


class LoopPersistenceTests(unittest.TestCase):
    setUpClass=classmethod(test_review.ReviewTests.setUpClass.__func__)
    tearDownClass=classmethod(test_review.ReviewTests.tearDownClass.__func__)
    setUp=test_review.ReviewTests.setUp

    def test_three_loops_close_at_second_objection_and_preserve_audit(self):
        for scenario in ('coverage','reactions','unchanged'):
            model=StalledModel(scenario=scenario)
            result=review.start(self.config,self.business,self.research['id'],request_key='guard-'+scenario,
                review_loop_guard=True,owner_presentation=False,analyst=model,reviewer=model)
            self.assertTrue(result['publishable'],result.get('issue'))
            self.assertEqual(len(result['model_calls']),4)
            self.assertEqual(result['verification'],'controller_qualified_delivery')
            self.assertTrue(all(e['action']['action']!='approve' for e in result['conversation']))
            self.assertEqual(result['review_issues'][0]['status'],'open')
            self.assertEqual(result['controller_resolution']['disposition'],'publish_with_limitations')
            self.assertIn('Queda pendiente una comprobación antes de decidir.',presentation(result)['limitations'])
            path=export(self.config,self.business,result['id'])['path']
            self.assertIn('Queda pendiente una comprobación antes de decidir.',Path(path).read_text())
            self.assertTrue(any(c.get('unchanged_submission') for c in model.contexts))
            self.assertTrue(all(c['review_schema_limits']['reactions']==4 for c in model.contexts))
            resumed=review.resume(self.config,self.business,result['id'],analyst=model,reviewer=model)
            self.assertEqual(resumed['approved_sha256'],result['approved_sha256'])

    def test_integrity_remains_blocked_and_guard_off_retains_control(self):
        for enabled in (True,False):
            model=StalledModel(kind='integrity')
            result=review.start(self.config,self.business,self.research['id'],request_key='integrity-'+str(enabled),
                review_loop_guard=enabled,max_review_rounds=3,analyst=model,reviewer=model)
            self.assertFalse(result['publishable'])
            self.assertEqual(result['status'],'rejected' if enabled else 'limited')
            if enabled:
                self.assertEqual(result['controller_resolution']['disposition'],'blocked_integrity')
                self.assertEqual(len(result['model_calls']),4)

    def test_restart_after_saved_objection_closes_without_another_model_call(self):
        from decision_room.database import connect
        model=StalledModel()
        def interrupted(context):
            if sum(e['role']=='reviewer' for e in context['conversation']) >= 2:
                raise SystemExit(17)
            return resolution(context)
        with patch('decision_room.agent.review_loops.resolution',side_effect=interrupted), self.assertRaises(SystemExit):
            review.start(self.config,self.business,self.research['id'],request_key='closure-crash',
                review_loop_guard=True,analyst=model,reviewer=model)
        with connect(self.config) as db:
            run=db.execute('SELECT id FROM agent_reviews WHERE business_id=%s',(self.business,)).fetchone()
        resumed=review.resume(self.config,self.business,run['id'],analyst=model,reviewer=model)
        self.assertTrue(resumed['publishable'])
        self.assertEqual(len(resumed['model_calls']),4)
        self.assertEqual(len(model.contexts),4)
        self.assertEqual(resumed['verification'],'controller_qualified_delivery')

    def test_schema_closes_focus_and_exposes_review_classification(self):
        model=StalledModel()
        review.start(self.config,self.business,self.research['id'],request_key='schema',review_loop_guard=True,analyst=model,reviewer=model)
        context=next(c for c in model.contexts if c['role']=='reviewer')
        client=ModelClient(ModelSettings('offline'))
        captured=[]
        with patch.object(client,'_generate',side_effect=lambda c,r,s,sc:captured.append(sc)):
            client.generate_reviewer(context)
        assert_strict_objects(self,captured[0])
        issue=StalledModel().generate_reviewer(context)[0]
        from decision_room.agent.review_contract import ReviewAction
        payload=ReviewAction.model_validate(issue).model_dump()
        jsonschema.validate(payload,captured[0])
        payload['assessment']['issues'][0]['owner_limitation']=None
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(payload,captured[0])
        claim=deepcopy(context['report']['claims'][0]);claim['focal_combinations']*=2
        with self.assertRaises(ValueError):Claim.model_validate(claim)


class ResolutionSafetyTests(unittest.TestCase):
    def context(self):
        report={'title':'Same draft'}
        issue=dict(key='style',status='open',severity='blocker',kind='presentation',basis='optional_improvement',detail='Simplify the title.')
        assessment=dict(issues=[issue],delivery=dict(numbers='pass',meaning='pass',charts='pass'))
        return dict(budgets={'review_loop_guard':True},report=report,report_step=3,checks=[],review_issues=[issue],conversation=[
            dict(step=1,role='analyst',action=dict(action='submit',report=report)),
            dict(step=2,role='reviewer',action=dict(action='revise',assessment=assessment)),
            dict(step=3,role='analyst',action=dict(action='submit',report=report)),
            dict(step=4,role='reviewer',action=dict(action='revise',assessment=assessment))])

    def test_pure_presentation_kept_in_audit_without_owner_noise(self):
        result=resolution(self.context())
        self.assertEqual(result['disposition'],'publish_with_limitations')
        self.assertEqual(result['owner_limitations'],[])

    def test_progress_is_not_stalled(self):
        context=self.context();context['report']={'title':'Changed'}
        self.assertIsNone(resolution(context))

    def test_no_integrity_or_fresh_objection_is_waived(self):
        for fault in ('check','meaning','unsupported_reaction','new_issue','unclassified'):
            context=self.context()
            if fault=='check':context['checks']=[{'passed':False}]
            elif fault=='meaning':context['conversation'][-1]['action']['assessment']['delivery']['meaning']='fail'
            elif fault=='unsupported_reaction':context['conversation'][-1]['action']['assessment']['usefulness']={'decision_support':'fail'}
            elif fault=='new_issue':context['review_issues'].append(dict(context['review_issues'][0],key='new',kind='integrity',basis='evidence_integrity'))
            else:context['review_issues'][0]['kind']=None
            with self.subTest(fault=fault):self.assertEqual(resolution(context)['disposition'],'blocked_integrity')


    def test_unchanged_integrity_cannot_be_renamed_as_style(self):
        context=self.context()
        # Break fixture aliases: these are separate, persisted reviews.
        context['conversation'][1]=deepcopy(context['conversation'][1])
        issue=context['conversation'][1]['action']['assessment']['issues'][0]
        issue.update(kind='integrity',basis='evidence_integrity')
        self.assertEqual(resolution(context)['disposition'],'blocked_integrity')


    def test_new_editorial_note_is_retained_without_losing_stalled_report(self):
        context=self.context()
        context['review_issues'].append(dict(context['review_issues'][0],key='new_style'))
        result=resolution(context)
        self.assertEqual(result['disposition'],'publish_with_limitations')
        self.assertEqual({i['key'] for i in result['issues']},{'style','new_style'})
