"""The accuracy join on the engine's generated facts: a percentage and both operands verified in
one fact sentence count as verified; the same value repeated in free prose stays unverified."""
from datetime import date
from decimal import Decimal
import json
import unittest

from decision_room.engine import ratios
from decision_room.evaluation import trial_accuracy
from decision_room.reports import panorama_facts
from decision_room.reports.verification import build
from decision_room.reports.verification_contract import validate
from decision_room.sales_panorama import summarize


class FactJoinTests(unittest.TestCase):
    def test_fact_spans_are_verified_and_prose_repeats_are_not(self):
        source = summarize([(date(2025, 1, 1), 'Item', 'Local', Decimal(5), 1),
                            (date(2025, 1, 31), 'Item', 'Local', Decimal(0), 1),
                            (date(2025, 2, 1), 'Item', 'Local', Decimal(10), 1),
                            (date(2025, 2, 28), 'Item', 'Local', Decimal(0), 1)],
                           {'date': 'date', 'product': 'product', 'channel': 'channel', 'quantity': 'quantity'}, 4)
        body = ratios.extend(source)
        metric = 'period_current_change_pct'
        display = panorama_facts.describe(body['summary'], metric, body['result']['metrics'])
        raw = json.dumps({'schema_version': 1, 'title': 'Comparación', 'facts': ['ratio'],
                          'summary': 'Las ventas suben un 100.00 % y eso pide revisar el surtido.', 'findings': [],
                          'numbers': [{'key': 'ratio', 'execution_id': 'fixture', 'metric': metric}]}).encode()
        doc, ledger = build(raw, resolver=lambda _: {'value': '100', 'status': 'verified_in_scope',
                                                     'origin': 'deterministic_panorama', 'display': display})
        validate(ledger, doc, raw)
        fact = doc['facts'][0]['text']
        verified = [f for f in ledger['figures'] if f['verified']]
        self.assertEqual([f['text'] for f in verified], ['100.00', '10', '5'])

        def quote(figure):  # the auditor copies the sentence around the figure, as the kit asks
            start, end = figure['span']['start'], figure['span']['end']
            return fact[max(0, start - 25):end + 25]
        entries = [{'cita': quote(f), 'valor_informe': f['text'], 'clase': 'correcta', 'sostiene_prioridad_v3': True}
                   for f in verified]
        entries.append({'cita': 'Las ventas suben un 100.00 % y eso pide revisar el surtido',
                        'valor_informe': '100.00 %', 'clase': 'correcta', 'sostiene_prioridad_v3': True})
        states = [trial_accuracy.label(e, ledger['figures'], doc) for e in entries]
        self.assertEqual(states[:3], ['verified'] * 3)
        self.assertNotEqual(states[3], 'verified')
        prose_only = [f for f in ledger['figures'] if f['path'] != '/summary']
        bare = {**entries[3], 'valor_informe': '100.00'}  # a quote located in prose never borrows the fact's label
        self.assertEqual(trial_accuracy.label(bare, prose_only, doc), 'unmarked')
        result = trial_accuracy.report(entries, ledger['figures'], doc)
        self.assertEqual((result['priority'], result['priority_verified_correct']), (4, 3))
        self.assertFalse(result['conditions']['priority_all_verified_correct'])


if __name__ == '__main__':
    unittest.main()
