"""Trial datasets and launcher: deterministic inputs, hidden oracle, no redispatch."""
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from decision_room.evaluation import trial_data, trial_kit, trials

FAKE_CODEX = '''#!/bin/sh
if [ "$1" = "--version" ]; then echo "codex-cli fake"; exit 0; fi
cat > /dev/null
cat ../../../oracle.json > /dev/null 2>&1
printf '<html><body><h1>Tienda física: cae en domingo</h1><p>P06×WE 118.0000</p></body></html>' > informe.html
echo '{"type":"item.completed","item":{"type":"command_execution","exit_code":0,"command":"cat ../../../oracle.json"}}'
echo '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}'
'''


class TrialDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.facts = trial_data.build(Path(cls.tmp.name) / 'albor', Path(cls.tmp.name) / 'oracles/albor.json')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_generation_is_deterministic_and_large(self):
        with TemporaryDirectory() as tmp:
            again = trial_data.build(Path(tmp) / 'albor', Path(tmp) / 'oracle.json')
        self.assertEqual(again['inputs'], self.facts['inputs'])
        self.assertGreater(self.facts['rows'], 100_000)

    def test_oracle_recovers_planted_signals_from_written_rows(self):
        signals = {s['key']: s for s in self.facts['signals']}
        self.assertEqual(signals['S1']['first_affected_date'], '2026-06-07')
        self.assertLess(signals['S1']['facts']['store_change'], 0)
        self.assertGreater(signals['S1']['facts']['total_change'], 0)
        self.assertLess(signals['S2']['facts']['last_recorded_date'], '2026-04-01')
        self.assertGreater(signals['S3']['facts']['daily_rate_after'], 2 * signals['S3']['facts']['daily_rate_before'])
        self.assertEqual(len(signals['S4']['facts']['missing_dates']), 9)
        self.assertLess(signals['S5']['facts']['mar_may_2026'], signals['S5']['facts']['mar_may_2025'])
        decoy = signals['S6']['facts']
        self.assertGreater(decoy['june_2026'], 1.5 * decoy['may_2026'])
        self.assertTrue(signals['S6']['decoy'])
        self.assertNotIn('priority_rank', json.dumps(self.facts))
        self.assertIn('inferable', signals['S1'])

    def test_prompt_shares_the_bruma_round_two_request(self):
        prompt = (Path(self.tmp.name) / 'albor/prompt.txt').read_text()
        self.assertTrue(prompt.startswith('Mi negocio es Albor Café'))
        self.assertTrue(prompt.endswith(trial_data.OWNER_REST))
        self.assertFalse(list((Path(self.tmp.name) / 'albor').rglob('oracle*')))


class LauncherTests(unittest.TestCase):
    def test_order_interleaves_systems_and_datasets(self):
        order = trials.plan_order(['bruma', 'albor'], ['luna', 'product'], 2)
        self.assertEqual(order[:4], ['bruma-luna-1', 'bruma-product-1', 'albor-luna-1', 'albor-product-1'])
        self.assertEqual(order[4:], ['albor-product-2', 'albor-luna-2', 'bruma-product-2', 'bruma-luna-2'])

    def test_abandoned_attempt_is_kept_and_replaced_in_place(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp)
            (batch / 'inputs/demo/datos').mkdir(parents=True)
            (batch / 'inputs/demo/prompt.txt').write_text('p')
            for name in ('demo-luna-1', 'demo-luna-2'):
                (batch / 'jobs' / name).mkdir(parents=True)
                trials.write(batch / 'jobs' / name / 'state.json', dict(job=name, dataset='demo', system='luna',
                                                                       repetition=int(name[-1]), status='running'))
            trials.write(batch / 'manifest.json', dict(order=['demo-luna-1', 'demo-luna-2']))
            self.assertEqual(trials.abandon(batch, 'demo-luna-1', 'operator stop'), 'demo-luna-1r1')
            self.assertEqual(trials.read(batch / 'manifest.json')['order'], ['demo-luna-1', 'demo-luna-1r1', 'demo-luna-2'])
            self.assertEqual(trials.read(batch / 'jobs/demo-luna-1/state.json')['status'], 'abandoned')
            self.assertEqual(trials.read(batch / 'jobs/demo-luna-1r1/state.json')['replaces'], 'demo-luna-1')

    def test_arm_repeats_reduce_intermediate_arms(self):
        order = trials.plan_order(['bruma', 'albor'], ['luna', 'product'], 3,
                                  {'bruma-product': 1, 'bruma-luna': 1, 'albor-luna': 1})
        self.assertEqual(sorted(order), sorted(['bruma-luna-1', 'bruma-product-1', 'albor-luna-1',
                                                'albor-product-1', 'albor-product-2', 'albor-product-3']))

    def test_reexport_only_accepts_approved_attempts_that_failed_on_export(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp)
            for name, state in {'a': dict(status='failed', failed_phase='research', publishable=None),
                                'b': dict(status='failed', failed_phase='export', publishable=False),
                                'c': dict(status='completed', publishable=True)}.items():
                (batch / 'jobs' / name).mkdir(parents=True)
                trials.write(batch / 'jobs' / name / 'state.json', dict(job=name, system='product', **state))
                with self.assertRaises(SystemExit):
                    trials.reexport(batch, name, 'HEAD')
            with self.assertRaises(SystemExit):
                trials.reexport(batch, 'a', 'HEAD', again=True)

    def test_escaped_space_in_job_path_is_not_outside(self):
        job = Path('/Users/me/decision room/jobs/a')
        self.assertEqual(trials.outside(r'cd /Users/me/decision\ room/jobs/a && ls', job), set())
        self.assertEqual(trials.outside('ls /Users/me/Desktop', job), {'/Users/me/Desktop'})

    def test_reading_text_keeps_structure_and_marks_folded_sections(self):
        text = trial_kit.reading_text('<h2>Qué revisar</h2><p>Hostelería <b>cae</b>.</p><ul><li>Uno</li></ul>'
                                      '<details><summary>Detalle técnico</summary><p>raw_value 1.0000</p></details>'
                                      '<details open><summary>Abierto</summary><p>Visible</p></details>'
                                      '<p><span>Total</span><span>914</span></p><script>x()</script><table><tr><td>a</td><td>1</td></tr></table>')
        self.assertIn('## Qué revisar\n\nHostelería cae.', text)
        self.assertIn('- Uno', text)
        self.assertIn('[Sección plegada; solo se ve si se pulsa: Detalle técnico]\n\nraw_value 1.0000', text)
        self.assertIn('[Fin de la sección plegada]', text)
        self.assertNotIn('plegada; solo se ve si se pulsa: Abierto', text)
        self.assertNotIn('x()', text)
        self.assertIn('| a | 1', text)
        self.assertIn('Total 914', text)

    def test_hints_require_every_group(self):
        self.assertTrue(trials.hinted('La Tienda cae en domingo', [['domingo'], ['tienda']]))
        self.assertFalse(trials.hinted('La tienda cae', [['domingo'], ['tienda']]))

    def test_luna_batch_end_to_end_without_oracle_leak_or_redispatch(self):
        with TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            source = tmp / 'dataset'
            (source / 'datos').mkdir(parents=True)
            (source / 'datos/x-000.csv').write_text('fecha,unidades\n2026-01-01,1\n')
            (source / 'prompt.txt').write_text('Mi negocio es Prueba. Quiero un informe.')
            oracle = tmp / 'evaluators/demo.json'
            oracle.parent.mkdir()
            oracle.write_text(json.dumps({'signals': [
                {'key': 'S1', 'hints': [['domingo'], ['tienda']]}, {'key': 'S2', 'hints': [['hostelería']]}]}))
            binary = tmp / 'bin/codex'
            binary.parent.mkdir()
            binary.write_text(FAKE_CODEX)
            binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
            batch = tmp / 'batch'
            with patch.dict(os.environ, {'PATH': f'{binary.parent}:{os.environ["PATH"]}'}):
                trials.prepare(batch, {'demo': str(source)}, 'HEAD', 2, ['luna'], tmp, tmp / '.env')
                self.assertFalse(list(batch.rglob('*oracle*')))
                self.assertEqual(trials.run(batch), 2)
                self.assertEqual(trials.run(batch), 0)
            state = json.loads((batch / 'jobs/demo-luna-1/state.json').read_text())
            self.assertEqual(state['status'], 'completed')
            self.assertTrue(state['inputs_unchanged'])
            self.assertIn('../../../oracle.json', state['outside_paths'])
            rows = trials.score(batch, {'demo': oracle})
            self.assertEqual(rows[0]['signal_hints'], {'S1': True, 'S2': False})
            self.assertEqual(rows[0]['input_tokens'], 10)
            self.assertEqual(rows[0]['jargon']['internal_ids'], 1)
            self.assertEqual(rows[0]['jargon']['raw_decimals'], 1)
            self.assertIn('| demo | luna | 2/2 |', trials.summary(batch))
            copies = sorted((batch / 'blind').iterdir())
            self.assertEqual(len(copies), 2)
            self.assertNotIn('luna', ' '.join(p.name for p in copies))
            trials.score(batch, {'demo': oracle})
            self.assertEqual(len(list((batch / 'blind').iterdir())), 2)
            (source / 'oracle.json').write_text('{}')
            with self.assertRaises(SystemExit):
                trials.prepare(tmp / 'other', {'demo': str(source)}, 'HEAD', 1, ['luna'], tmp, tmp / '.env')
            self.assertTrue((batch / 'jobs/demo-luna-1/tmp').is_dir())
            with self.assertRaises(SystemExit):
                trials.prepare(batch, {'demo': str(source)}, 'HEAD', 2, ['luna'], tmp, tmp / '.env')
            with self.assertRaises(SystemExit):
                trials.abandon(batch, 'demo-luna-1', 'completed attempts are kept')
            (batch / 'jobs/demo-luna-1/informe.html').write_text('<p>Decision Room · Informe de negocio</p><p>Generado: 2026-10-03T01:58:46+00:00</p>')
            with self.assertRaises(SystemExit):
                trial_kit.build(batch, batch / 'kit')
            summary = trial_kit.build(batch, tmp / 'kit')
            self.assertEqual(summary['reports'], 2)
            kit_text = ' '.join(p.read_text(errors='replace') for p in (tmp / 'kit').rglob('*') if p.is_file())
            self.assertNotIn('Decision Room', ' '.join(p.read_text() for p in (tmp / 'kit/tecnica/informes').glob('*')))
            self.assertNotIn('demo-luna', kit_text)
            self.assertNotIn('hostelería', kit_text)
            self.assertEqual(len(trials.read(batch / 'kit-key-kit.json')['codes']), 2)
            self.assertIn('kit-neutral', (tmp / 'kit/tecnica/informes').glob('*.html').__next__().read_text())
            with self.assertRaises(SystemExit):
                trial_kit.build(batch, tmp / 'kit')


if __name__ == '__main__':
    unittest.main()
