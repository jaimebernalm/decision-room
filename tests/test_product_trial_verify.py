"""Reject evaluation arithmetic and coverage errors without knowing the arms."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/checks/product_trial_verify.py'
SPEC = importlib.util.spec_from_file_location('product_trial_verify', SCRIPT)
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


class ProductTrialVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.kits = root / 'kits'; self.kits.mkdir()
        self.results = root / 'results'; self.results.mkdir()
        (self.kits / 'index.json').write_text(json.dumps({'reports': {'R123': 'units'}, 'pairs': ['units-1']}))
        p = self.kits / 'index.json'
        (self.kits / 'SEALED.sha256').write_text(hashlib.sha256(p.read_bytes()).hexdigest() + '  index.json\n')
        self.audit = {'report': 'R123', 'claims': [
            {'texto': 'Units rose by 10.', 'seccion': 'prioridad', 'tipo': 'comparacion', 'calculable': True, 'veredicto': 'critico'},
            {'texto': 'The same rise.', 'seccion': 'resto', 'tipo': 'cifra', 'calculable': True, 'veredicto': 'material'},
            {'texto': 'Total 20.', 'seccion': 'resto', 'tipo': 'cifra', 'calculable': True, 'veredicto': 'correcta'},
            {'texto': 'Consider a promotion.', 'seccion': 'resto', 'tipo': 'recomendacion', 'calculable': False, 'veredicto': 'no_comprobable'}],
            'denominadores': {'prioridad_calculables': 1, 'prioridad_correctas': 0, 'resto_calculables': 2, 'resto_correctas': 1}}
        self.group = {'report': 'R123', 'material_distintos': 1, 'criticos_distintos': 1,
                      'grupos': [{'nivel': 'critico', 'afirmaciones': [0, 1]}]}
        self.write('audit-R123.json', self.audit)
        self.write('group-R123.json', self.group)
        self.write('judge-R123.json', {'report': 'R123', **{'S' + str(n): 0 for n in range(1, 7)}})
        for role in ('owner', 'advisor'):
            self.write(role + '-units-1.json', {'pair': 'units-1', 'eleccion': 'empate', 'motivo': 'Both explain the same result.'})

    def write(self, name, value):
        (self.results / name).write_text(json.dumps(value))

    def test_complete_blinded_evaluations_and_critical_subset_are_valid(self):
        result = verify.verify(self.kits, self.results)
        self.assertTrue(result['valid'], result)
        self.assertEqual((result['reports'], result['pairs']), (1, 1))

    def test_coverage_duplicates_omissions_and_downgraded_groups_are_rejected(self):
        for indices, level in (([0], 'critico'), ([0, 1, 1], 'critico'), ([0, 1, 2], 'critico'), ([0, 1], 'material')):
            with self.subTest(indices=indices, level=level):
                value = copy.deepcopy(self.group)
                value['grupos'][0].update(afirmaciones=indices, nivel=level)
                self.write('group-R123.json', value)
                self.assertFalse(verify.verify(self.kits, self.results)['valid'])

    def test_denominators_are_recomputed_and_non_numeric_claims_excluded(self):
        self.audit['denominadores']['resto_calculables'] = 3
        self.write('audit-R123.json', self.audit)
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])
        self.audit['denominadores']['resto_calculables'] = 2
        self.audit['claims'][3]['calculable'] = True
        self.write('audit-R123.json', self.audit)
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])

    def test_missing_reader_or_invalid_choice_is_incomplete_not_a_tie(self):
        self.write('owner-units-1.json', {'pair': 'units-1', 'eleccion': 'abstencion', 'motivo': 'Unsure.'})
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])
        (self.results / 'owner-units-1.json').unlink()
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])

    def test_judge_booleans_float_scores_and_wrong_id_are_invalid(self):
        base = {'report': 'R123', **{'S' + str(n): 0 for n in range(1, 7)}}
        for change in ({'S1': True}, {'S1': 1.0}, {'S6': 2}, {'report': 'R999'}):
            self.write('judge-R123.json', {**base, **change})
            self.assertFalse(verify.verify(self.kits, self.results)['valid'])

    def test_changed_and_unsealed_files_fail_before_evaluations(self):
        (self.kits / 'extra.txt').write_text('Not in the frozen material.')
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])
        (self.kits / 'extra.txt').unlink()
        (self.kits / 'index.json').write_text('{}')
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])

    def test_duplicate_json_keys_cannot_overwrite_a_verdict(self):
        (self.results / 'owner-units-1.json').write_text('{"pair":"units-1","eleccion":"A","eleccion":"B","motivo":"x"}')
        self.assertFalse(verify.verify(self.kits, self.results)['valid'])
