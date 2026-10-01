"""Independent owner coverage and decision links; no fixture-specific agent answers."""
from copy import deepcopy
import unittest
from pydantic import ValidationError
from decision_room.agent.delivery_contract import validate_owner_coverage, DecisionOrientation
from decision_room.agent.review_contract import ReportDraft, checks


class DeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.context = {'review_policy': 4, 'business_direction': {'brief': {'deliverables': ['Evolución', 'Prioridades']}}}
        self.report = {'contract_version': 2, 'claims': [{'key': 'trend'}], 'owner_coverage': [
            {'deliverable_index': 0, 'status': 'complete', 'claim_keys': ['trend'], 'explanation': 'Evolución entregada.'},
            {'deliverable_index': 1, 'status': 'partial', 'claim_keys': ['trend'], 'explanation': 'Falta contexto operativo.'}]}
    def test_partial_is_distinct_from_complete_and_internal_branches(self):
        validate_owner_coverage(self.report, self.context)
        self.report['question_coverage'] = [{'investigation_key': str(n)} for n in range(4)]
        validate_owner_coverage(self.report, self.context)
        self.report['owner_coverage'].append(deepcopy(self.report['owner_coverage'][0]))
        with self.assertRaisesRegex(ValueError, 'exactly once'): validate_owner_coverage(self.report, self.context)
    def test_unknown_claim_or_fabricated_delivery_rejected(self):
        for status, claims in [('complete', []), ('unavailable', ['trend']), ('partial', ['missing'])]:
            report = deepcopy(self.report); report['owner_coverage'][1].update(status=status, claim_keys=claims)
            with self.assertRaises(ValueError): validate_owner_coverage(report, self.context)
    def test_historical_contract_is_not_upgraded_silently(self):
        validate_owner_coverage({}, {'review_policy': 3})
        self.report['contract_version'] = 1
        with self.assertRaisesRegex(ValueError, 'historical'): validate_owner_coverage(self.report, self.context)
    def test_orientation_requires_scope_and_evidence_without_forcing_action(self):
        value = dict(segment='Canal físico', period='Julio–agosto', signal='Descenso registrado',
            evidence=[{'execution_id': 'saved', 'metric': 'delta'}], relative_priority='Diverge del agregado.',
            knowledge='calculated', next_check='Disponibilidad durante agosto en el canal físico.',
            decision_value='Distinguir falta de disponibilidad de menor actividad.', reactions=[],
            limitation='No consta disponibilidad.')
        DecisionOrientation.model_validate(value)
        value['evidence'] = []
        with self.assertRaises(ValidationError): DecisionOrientation.model_validate(value)
    def test_orientation_cannot_cite_stale_evidence(self):
        report = {'claims': [{'key': 'x', 'evidence': [{'execution_id': 'ok', 'metric': 'total'}],
                             'orientation': {'evidence': [{'execution_id': 'stale', 'metric': 'total'}]}}], 'checks': []}
        observed = [dict(execution_id=k, current=current, status='completed', result={'metrics': {'total': 1}, 'evidence': [{'metric': 'total'}]})
                    for k, current in [('ok', True), ('stale', False)]]
        self.assertFalse(checks(report, observed)[0]['passed'])

if __name__ == '__main__': unittest.main()
