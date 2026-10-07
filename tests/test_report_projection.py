import json
import unittest
from copy import deepcopy

from decision_room.reports.verification import build
from decision_room.reports.verification_contract import validate
from decision_room.web.report_projection import project, render


class ReportTests(unittest.TestCase):
    def raw(self, **extra):
        return json.dumps({'schema_version': 1, 'title': 'Resumen', 'summary': '🧾 42 % y 42 %', 'findings': [], **extra}).encode()

    def test_two_occurrences_remain_distinct_and_content_keeps_text_without_marks(self):
        raw = self.raw(); doc, ledger = build(raw)
        self.assertEqual(len(ledger['figures']), 2)
        self.assertNotEqual(ledger['figures'][0]['id'], ledger['figures'][1]['id'])
        self.assertFalse(any(f['verified'] for f in ledger['figures']))
        before = deepcopy(doc); projected = project(doc)
        marked, plain = render(projected), render(projected, marks=False)
        self.assertIn('<mark', marked); self.assertNotIn('<mark', plain)
        self.assertIn('42 % y 42 %', plain)
        self.assertEqual(doc, before)
        validate(ledger, doc, raw)

    def test_malformed_unknown_shapes_and_html_are_retained_as_escaped_text(self):
        for raw in [b'{"unfinished":', b'<script>alert(2)</script>', self.raw(charts=[{'x': 7}]), self.raw(summary=['unexpected', 23])]:
            with self.subTest(raw=raw):
                doc, ledger = build(raw); html = render(project(doc), marks=False)
                self.assertEqual(doc['summary'], raw.decode())
                self.assertNotIn('<script>', html)
                self.assertIn('report_format_fallback', ledger['issues'])
                validate(ledger, doc, raw)

    def test_reference_correction_never_claims_semantic_verification(self):
        ref = {'key': 'qty', 'execution_id': 'fixture', 'metric': 'quantity', 'decimals': 1}
        raw = self.raw(summary='Cantidad {{n:qty}}.', numbers=[ref])
        doc, ledger = build(raw, resolver=lambda _: {'value': '12.25', 'original_value': '99',
                            'status': 'corrected_in_scope', 'origin': 'deterministic_panorama'})
        self.assertEqual(doc['summary'], 'Cantidad 12.2.')
        figure = ledger['figures'][0]
        self.assertEqual((figure['status'], figure['value'], figure['corrected_from']), ('corrected', '12.2', '99'))
        self.assertFalse(figure['verified'])
        self.assertIn('12.2', render(project(doc), marks=False))

    def test_missing_ambiguous_or_failed_references_remain_visible(self):
        ref = {'key': 'qty', 'execution_id': 'fixture', 'metric': 'quantity'}
        def fail(_):
            raise RuntimeError('Private provider detail')
        for refs in [[], [ref], [ref, ref]]:
            raw = self.raw(summary='{{n:qty}}', numbers=refs)
            doc, ledger = build(raw, resolver=fail)
            self.assertEqual(doc['summary'], '{{n:qty}}')
            self.assertEqual(ledger['figures'][0]['status'], 'uncertain')
            self.assertNotIn('Private', str(ledger))

    def test_invalid_display_precision_and_unbounded_numbers_cannot_expand_output(self):
        for value in ['NaN', '1e999999']:
            doc, ledger = build(self.raw(summary='{{n:q}}', numbers=[{'key': 'q', 'execution_id': 'fixture', 'metric': 'q'}]), resolver=lambda _: {'value': value})
            self.assertEqual(doc['summary'], '{{n:q}}')
            self.assertFalse(ledger['figures'][0]['verified'])


if __name__ == '__main__':
    unittest.main()
