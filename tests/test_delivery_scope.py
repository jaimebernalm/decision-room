"""Source authority and review integrity; scripted audits are not utility evidence."""
from copy import deepcopy
import unittest
from decision_room.agent.review_contract import ReviewAction, validate_coverage
from decision_room.agent.review_policy import validate_assessment


class BlockerBasisTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(review_policy=5, report_step=1, conversation=[], review_issues=[],
            owner_context='Prioriza señales y explica la evolución.',
            accepted_owner_request={'text': 'Prioriza señales y explica la evolución.'},
            owner_confirmed_answers=[], owner_deliverables=['Prioriza señales y explica la evolución.'],
            report=dict(claims=[dict(key='result')], charts=[], question_coverage=[],
                owner_coverage=[dict(deliverable_index=0,status='complete',claim_keys=['result'])]))

    def action(self, kind='revise', **issue_changes):
        issue=dict(key='gap',severity='blocker',status='open',target='claims.result',
            detail='Falta responder la evolución solicitada.',resolution='',introduced_because='',
            basis='owner_goal',owner_quote='explica la evolución',owner_deliverable_index=0,
            claim_keys=[],chart_keys=[])
        issue.update(issue_changes)
        return ReviewAction.model_validate(dict(action=kind,message='Revisar el componente material.',
            report=None,code='',table_ids=[],question='',assessment=dict(report_step=1,issues=[issue],
                delivery=dict(numbers='pass',meaning='pass',charts='not_applicable',coverage='pass',files='pass'),
                usefulness=dict(goal_alignment='pass',reason='Evaluación de protocolo.',questions=[],
                    decision_support='not_applicable',owner_deliverables=[dict(deliverable_index=0,
                    verdict='pass',claim_keys=['result'],reason='Respuesta de protocolo.')]))))

    def test_real_owner_obligation_has_source_quote_and_index(self):
        validate_assessment(self.action(), 'reviewer', self.context)
        for mutation in ({'owner_quote':'Entrega las 18 combinaciones'}, {'owner_deliverable_index':1}):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError,'exact source quote'):
                validate_assessment(self.action(**mutation),'reviewer',self.context)

    def test_optional_improvement_cannot_block_an_adequate_selection(self):
        with self.assertRaisesRegex(ValueError,'never approval blockers'):
            validate_assessment(self.action(basis='optional_improvement'),'reviewer',self.context)
        validate_assessment(self.action('approve',basis='optional_improvement',severity='suggestion'),
                            'reviewer',self.context)

    def test_integrity_blocker_must_point_at_actual_current_delivery(self):
        validate_assessment(self.action(basis='evidence_integrity',claim_keys=['result']),'reviewer',self.context)
        for changes in ({'claim_keys':[]}, {'claim_keys':['removed']}, {'chart_keys':['missing']}):
            with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'current delivered'):
                validate_assessment(self.action(basis='evidence_integrity',**changes),'reviewer',self.context)

    def test_missing_core_owner_answer_still_fails_approval(self):
        action=self.action('approve',severity='suggestion',basis='optional_improvement')
        action.assessment.usefulness.owner_deliverables[0].verdict='fail'
        with self.assertRaisesRegex(ValueError,'failed owner deliverables'):
            validate_assessment(action,'reviewer',self.context)

    def test_internal_initial_view_can_be_deferred_without_inventing_owner_scope(self):
        context=deepcopy(self.context)
        context['plan']={'investigations':[dict(key='focus',status='ready'),dict(key='inventory',status='ready')]}
        report=dict(contract_version=2,claims=[dict(key='result')],
            owner_coverage=[dict(deliverable_index=0,status='complete',claim_keys=['result'])],
            question_coverage=[dict(investigation_key='focus',status='answered',claim_keys=['result']),
                               dict(investigation_key='inventory',status='deferred',claim_keys=[])])
        validate_coverage(report,context)
        context.update(review_policy=4,business_direction={'brief':{'deliverables':['Goal']}})
        with self.assertRaisesRegex(ValueError,'followup'):
            validate_coverage(report,context)

if __name__ == '__main__': unittest.main()
