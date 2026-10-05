"""Do not ask a writer to remove a counter the controller keeps reinserting."""
from copy import deepcopy
import unittest

from decision_room.agent import review
from decision_room.agent.owner_presentation import feedback, SYSTEM
from decision_room.web.dashboard import presentation
import test_review


class OwnershipTests(unittest.TestCase):
    def test_editorial_exemption_is_exact_and_keeps_business_caveats(self):
        note='Cobertura del encargo: 0 de 1 entregables completos; earlier_window parcial.'
        report={'limitations':[note,note+' Falta calcular earlier_window_units.'], 'claims':[], 'charts':[]}
        before=deepcopy(report)
        hints=feedback(report,{'coverage_note':note,'selection_notes':[]})
        self.assertFalse(any(x['path']=='limitations[0]' for x in hints['locations']))
        self.assertTrue(any(x['path']=='limitations[1]' for x in hints['locations']))
        self.assertEqual(report,before)
        self.assertIn('NEVER revise/reject solely',SYSTEM)
        self.assertIn('false completeness',SYSTEM)


class OwnershipPersistenceTests(unittest.TestCase):
    setUpClass = classmethod(test_review.ReviewTests.setUpClass.__func__)
    tearDownClass = classmethod(test_review.ReviewTests.tearDownClass.__func__)
    setUp = test_review.ReviewTests.setUp

    def test_partial_report_finishes_without_reinserting_counter_and_keeps_audit(self):
        class Model(test_review.DialogueModel):
            def generate_analyst_review(self,context,correction=None):
                report=test_review.draft(context)
                report['owner_coverage'][0].update(status='partial',explanation='Faltan costes para comparar el beneficio.')
                report['limitations'].append('Faltan costes para comparar el beneficio.')
                return test_review.action('submit',report=report),{}
            def generate_reviewer(self,context,correction=None):
                self.contexts.append(deepcopy(context))
                if any(s.startswith('Cobertura del encargo:') for s in context['report']['limitations']):
                    response=test_review.action('revise','Retira el contador interno que aparece en límites.')
                else:
                    response=test_review.action('approve')
                return test_review.assessed(response,context),{}
        model=Model()
        result=review.start(self.config,self.business,self.research['id'],request_key='controller-p3',
                            owner_presentation=True,max_review_rounds=2,analyst=model,reviewer=model)
        self.assertTrue(result['publishable'])
        self.assertEqual(len(result['model_calls']),2)
        self.assertEqual(result['report']['owner_coverage'][0]['status'],'partial')
        self.assertTrue(presentation(result)['partial'])
        self.assertIn('Faltan costes para comparar el beneficio.',presentation(result)['limitations'])
        note=result['controller_annotations']['coverage_note']
        self.assertIn('0 de 1',note)
        self.assertNotIn(note,result['report']['limitations'])
        self.assertEqual(model.contexts[0]['controller_annotations'],result['controller_annotations'])
        control=review.start(self.config,self.business,self.research['id'],request_key='controller-control',
                             owner_presentation=False,max_review_rounds=2,analyst=Model(),reviewer=Model())
        self.assertEqual(control['status'],'limited') # reproduces the old loop, no automatic approval
        self.assertTrue(any(s.startswith('Cobertura del encargo:') for s in control['report']['limitations']))
        self.assertNotIn('controller_annotations',control)
