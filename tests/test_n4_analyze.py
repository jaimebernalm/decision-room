"""N4 conservative auditor-checker cross-match (frozen before the batch)."""
import importlib.util
import sys
import unittest

from decision_room.config import ROOT
from decision_room.engine import blocks
from tests.test_engine_blocks import doc, raw

sys.path.insert(0, str(ROOT / 'scripts/f5'))
spec = importlib.util.spec_from_file_location('n4_analyze', ROOT / 'scripts/f5/n4_analyze.py')
n4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(n4)

PROJECTION = blocks.parse(raw(doc(
    {'tipo': 'prioridad', 'titulo': 'Uno', 'bloques': [{'tipo': 'texto', 'contenido': 'Magnesio baja a 636 unidades. Web sube 50 unidades.'}]},
    {'tipo': 'prioridad', 'titulo': 'Dos', 'bloques': [{'tipo': 'texto', 'contenido': 'La web sube 50 unidades otra vez.'}]})))


class CrossMatchTests(unittest.TestCase):
    def setUp(self):
        self.priorities = n4.priority_texts(PROJECTION)

    def test_located_final_discrepancy_warns(self):
        items = [{'block_id': 'b1-1', 'quote': 'Magnesio baja a 636 unidades', 'status': 'discrepancy'}]
        self.assertTrue(n4.warned('636 unidades', self.priorities, items))

    def test_repeated_quote_is_never_warned(self):
        items = [{'block_id': 'b1-1', 'quote': 'Web sube 50 unidades', 'status': 'discrepancy'}]
        self.assertFalse(n4.warned('50 unidades', self.priorities, items))

    def test_coverage_and_other_priority_and_unverifiable_are_not_warnings(self):
        coverage = [{'block_id': 'b1', 'quote': '636 unidades', 'status': 'discrepancy', 'coverage': True}]
        other = [{'block_id': 'b2-1', 'quote': '636 unidades', 'status': 'discrepancy'}]
        unverifiable = [{'block_id': 'b1-1', 'quote': '636 unidades', 'status': 'unverifiable'}]
        for items in (coverage, other, unverifiable):
            self.assertFalse(n4.warned('636 unidades', self.priorities, items))
        self.assertFalse(n4.warned(None, self.priorities, unverifiable))

    def test_addressed_counts_confirmed_items_for_false_alarm_denominator(self):
        items = [{'block_id': 'b1-1', 'quote': '636 unidades', 'status': 'confirmed'}]
        self.assertEqual(len(n4.addressed('Magnesio baja a 636 unidades', self.priorities, items)), 1)


if __name__ == '__main__':
    unittest.main()
