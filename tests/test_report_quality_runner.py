"""Frozen paired experiment must preserve failures and avoid billable redispatch."""
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from decision_room.evaluation import report_quality_runner as runner
from decision_room.evaluation.runner import write


class PairedVersionTests(unittest.TestCase):
    def test_reserved_but_never_started_attempt_keeps_identity_on_dispatch(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp);folder=directory/'new';folder.mkdir()
            name='bruma-discover-1-new';job=folder/name;job.mkdir()
            initial=dict(case='bruma-discover',dataset='bruma',repetition=1,mode='new',status='not_run',key='original-identity')
            write(job/'state.json',initial)
            write(folder/'manifest.json',dict(source_root=tmp,source_sha256='frozen',jobs={name:initial}))
            def finish(*args, **kwargs):
                state=runner.read(job/'state.json')
                self.assertEqual(state['key'],'original-identity')
                write(job/'state.json',{**state,'status':'failed','issue':'Original attempt retained'})
                return subprocess.CompletedProcess([],0)
            with patch.object(runner,'prepare',return_value=dict(order=[('bruma-discover',1,'new')])), \
                 patch.object(runner,'source_hash',return_value='frozen'), \
                 patch.object(runner,'summary',return_value={}), patch.object(runner,'child',side_effect=finish) as child:
                runner.run(directory,'base','new',{})
                runner.run(directory,'base','new',{})
                self.assertEqual(child.call_count,1)
                self.assertEqual(runner.read(job/'state.json')['issue'],'Original attempt retained')

    def test_followup_cannot_replace_an_unfinished_original_experiment(self):
        with TemporaryDirectory() as tmp:
            directory=Path(tmp);origin=directory/'original';origin.mkdir()
            for version in ('base', 'new'):
                folder=origin/version;folder.mkdir();write(folder/'manifest.json',dict(jobs={'job':{}}))
                (folder/'job').mkdir();write(folder/'job/state.json',dict(status='running'))
            write(origin/'manifest.json',dict(model={}))
            with patch.object(runner,'child') as child, patch.object(runner,'freeze') as freeze:
                with self.assertRaisesRegex(ValueError,'Finish the original'):
                    runner.followup(directory/'followup',origin,'new')
                child.assert_not_called();freeze.assert_not_called()
                self.assertFalse((directory/'followup').exists())

    def test_matrix_contains_each_case_twice_per_version_and_alternates_order(self):
        jobs = runner.order()
        self.assertEqual(len(jobs), 12)
        self.assertEqual(len(set(jobs)), 12)
        for case in runner.SELECTED:
            self.assertEqual([v for c, r, v in jobs if c == case and r == 1], ['base', 'new'])
            self.assertEqual([v for c, r, v in jobs if c == case and r == 2], ['new', 'base'])

    def test_interrupted_job_is_preserved_and_second_run_cannot_replace_it(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); folder = directory / 'new'; folder.mkdir()
            name = 'bruma-discover-1-new'
            initial = dict(case='bruma-discover', dataset='bruma', repetition=1, mode='new', status='not_run', key='same-attempt')
            write(folder / 'manifest.json', dict(source_root=tmp, source_sha256='frozen', jobs={name: initial}, fixtures={'bruma': {}}))
            batch = dict(order=[('bruma-discover', 1, 'new')])
            with patch.object(runner, 'prepare', return_value=batch), \
                 patch.object(runner, 'source_hash', return_value='frozen'), \
                 patch.object(runner, 'summary', return_value={}), \
                 patch.object(runner, 'child', side_effect=[subprocess.TimeoutExpired('worker', 7200), None]) as child:
                runner.run(directory, 'base', 'new', {})
                state = runner.read(folder / name / 'state.json')
                self.assertEqual(state['status'], 'interrupted')
                self.assertEqual(state['key'], 'same-attempt')
                self.assertIsInstance(state['seconds'], float)
                self.assertTrue(state['source_stable'])
                self.assertEqual(child.call_count, 2)  # Original worker and evidence collection.
                runner.run(directory, 'base', 'new', {})
                self.assertEqual(child.call_count, 2)
                self.assertEqual(runner.read(folder / name / 'state.json'), state)

    def test_changed_frozen_source_prevents_dispatch_without_starting_attempt(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp); folder = directory / 'new'; folder.mkdir()
            name = 'bruma-discover-1-new'
            write(folder / 'manifest.json', dict(source_root=tmp, source_sha256='frozen', jobs={name: {}}))
            with patch.object(runner, 'prepare', return_value=dict(order=[('bruma-discover', 1, 'new')])), \
                 patch.object(runner, 'source_hash', return_value='changed'), patch.object(runner, 'child') as child:
                with self.assertRaisesRegex(ValueError, 'source changed'):
                    runner.run(directory, 'base', 'new', {})
                child.assert_not_called()
                self.assertFalse((folder / name / 'state.json').exists())
