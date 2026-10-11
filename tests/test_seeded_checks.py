"""Seeded-error helpers: number choice, Spanish formatting and a single in-place change."""
import importlib.util
import json
import random
import sys
import unittest

from decision_room.config import ROOT
from decision_room.engine import blocks
from tests.test_engine_blocks import doc, raw

sys.path.insert(0, str(ROOT / 'scripts/f5'))
spec = importlib.util.spec_from_file_location('seeded_checks', ROOT / 'scripts/checks/seeded_checks.py')
seeded = importlib.util.module_from_spec(spec); spec.loader.exec_module(seeded)
import n4_analyze  # noqa: E402


class SeededTests(unittest.TestCase):
    def test_spanish_format_keeps_the_original_shape(self):
        self.assertEqual(seeded.es_format(1234.5, '985,00'), '1234,50')
        self.assertEqual(seeded.es_format(16144.15 * 1.3, '16.144,15'), '20.987,40')
        self.assertEqual(seeded.es_format(419 * 0.5, '419'), '210')

    def test_one_correct_priority_figure_changes_once(self):
        source = raw(doc({'tipo': 'prioridad', 'titulo': 'Uno', 'bloques': [
            {'tipo': 'texto', 'contenido': 'Magnesio baja de 985 a 419 unidades en 2026.'}]}))
        priorities = n4_analyze.priority_texts(blocks.parse(source))
        audit = dict(claims=[dict(seccion='prioridad', calculable=True, veredicto='correcta',
                                  cita='Magnesio baja de 985 a 419 unidades')])
        (cita, token), = list(seeded.candidates(audit, priorities))
        self.assertEqual(token.group(), '985')
        new, original, value = seeded.seed_document(source, cita, token, random.Random(1))
        self.assertEqual(original, '985')
        self.assertNotEqual(value, '985')
        text = n4_analyze.priority_texts(blocks.parse(new))['b1'][0]
        self.assertIn(f'de {value} a 419', text)
        self.assertNotIn('de 985', text)


if __name__ == '__main__':
    unittest.main()
