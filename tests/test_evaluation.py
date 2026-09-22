"""The evaluation itself must fail closed and keep answer keys outside agent input."""
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from copy import deepcopy
from decimal import Decimal
from decision_room.evaluation.cases import reference, inputs, SCENARIOS
from decision_room.evaluation.assess import assess, RUBRIC
from decision_room.evaluation.runner import owner_reply, run_batch, worker, write
from decision_room.agent.model import ModelSettings


class EvaluationTests(unittest.TestCase):
    def test_independent_references_cover_modes_and_even_medians(self):
        daily=reference('daily')['metrics']
        self.assertEqual(daily['first_sales'],'34137.85')
        self.assertEqual(daily['change_percent'],'16.14')
        self.assertEqual(daily['first_median'],'2491.30')
        self.assertEqual(daily['second_median'],'3185.13')
        self.assertEqual(reference('products')['metrics']['product:3:sales'],'32745.00')
        self.assertEqual(reference('unit-price')['metrics']['sales'],'1220.00')
        self.assertEqual(reference('line-total')['metrics']['sales'],'257.50')
        self.assertNotIn('sales',reference('unknown')['metrics'])
        self.assertNotIn('sales',reference('declined')['metrics'])
        self.assertEqual(reference('daily'),reference('daily-renamed'))
        self.assertEqual(reference('products'),reference('products-renamed'))

    def test_model_inputs_exclude_references_and_future_answers(self):
        for scenario in SCENARIOS:
            path,context=inputs(scenario)
            self.assertEqual(path.suffix,'.csv')
            self.assertNotIn('evaluation',str(path))
            for secret in ('expected.json','1220.00','257.50','73784.10'):
                self.assertNotIn(secret,context)
        self.assertEqual(owner_reply('unknown')[0],'unknown')
        self.assertEqual(owner_reply('declined')[0],'declined')
        self.assertEqual(owner_reply('unit-price',{'text':'¿Es precio unitario o total de fila?'})[0],'answered')
        self.assertEqual(owner_reply('unit-price',{'text':'¿Qué moneda usas?'})[0],'unknown')

    def case(self):
        ref={'execution_id':'exec','metric':'agent_chosen_name'}
        state={'status':'completed','resume_idempotent':True,'source_stable':True}
        report={'publishable':True,'status':'approved','checks':[{'passed':True}],
                'report':{'claims':[{'evidence':[ref]}],'charts':[]},
                'observations':[{'execution_id':'exec','current':True,'status':'completed','result':{'metrics':{'agent_chosen_name':'59'}}}]}
        oracle=reference('unknown')
        assessment={'reviewer':'development_review','notes':'Independently inspected code and narrative.',
                    'rubric':dict.fromkeys(RUBRIC,True),'bindings':{'quantity':ref}}
        return state,report,oracle,assessment

    def test_model_approval_without_independent_review_never_passes(self):
        state,report,oracle,_=self.case()
        result=assess(state,report,oracle)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['status'],'needs_independent_review')

    def test_accepts_only_explicit_correct_cited_current_result(self):
        args=self.case();self.assertTrue(assess(*args)['accepted'])
        for change in ('wrong','stale','not_cited','missing_binding','held','not_resumed','semantic_failure','bool','nonfinite','fractional_count'):
            state,report,oracle,assessment=deepcopy(args)
            obs=report['observations'][0]
            if change=='wrong':obs['result']['metrics']['agent_chosen_name']='58'
            elif change=='stale':obs['current']=False
            elif change=='not_cited':report['report']['claims']=[]
            elif change=='missing_binding':assessment['bindings']={}
            elif change=='held':report.update(publishable=False,status='held')
            elif change=='not_resumed':state['resume_idempotent']=False
            elif change=='semantic_failure':assessment['rubric']['usefulness']=False
            elif change=='fractional_count':obs['result']['metrics']['agent_chosen_name']='59.009'
            elif change=='bool':obs['result']['metrics']['agent_chosen_name']=True
            else:obs['result']['metrics']['agent_chosen_name']='NaN'
            with self.subTest(change=change):self.assertFalse(assess(state,report,oracle,assessment)['accepted'])

    def test_failed_runs_cannot_be_rescued_by_a_written_assessment(self):
        state,report,oracle,assessment=self.case();state['status']='failed'
        self.assertFalse(assess(state,report,oracle,assessment)['accepted'])

    def test_missing_reference_or_uninvalidated_correction_fails(self):
        state,report,oracle,assessment=self.case()
        self.assertFalse(assess(state,report,{'required':[]},assessment)['accepted'])
        state['supersedes_review_id']='old-review'
        self.assertFalse(assess(state,report,oracle,assessment)['accepted'])
        state['previous_approval_invalidated']=True
        self.assertTrue(assess(state,report,oracle,assessment)['accepted'])

    def test_batch_pause_preserves_identity_and_rejects_source_drift(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);(directory/'STOP').touch()
            settings=ModelSettings('test-model')
            with patch('decision_room.evaluation.runner.source_version',return_value='version-one'):
                run_batch(directory,['daily'],1,settings)
                first=json.loads((directory/'daily-1/state.json').read_text())
                run_batch(directory,['daily'],1,settings)
                self.assertEqual(first,json.loads((directory/'daily-1/state.json').read_text()))
            with patch('decision_room.evaluation.runner.source_version',return_value='version-two'):
                with self.assertRaisesRegex(ValueError,'Cannot mix'):
                    run_batch(directory,['daily'],1,settings)

    def test_database_failure_preserves_original_worker_error(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary)
            from dataclasses import asdict
            write(directory/'state.json',{'model':asdict(ModelSettings('test-model')),
                'key':'test','scenario':'daily','source_sha256':'version',
                'status':'running','completed_phases':[]})
            with patch('decision_room.evaluation.runner.source_version',return_value='version'), \
                 patch('decision_room.evaluation.runner.create_business',side_effect=RuntimeError('import database unavailable')), \
                 patch('decision_room.evaluation.runner.collect',side_effect=RuntimeError('collection database unavailable')):
                self.assertEqual(worker(directory,'import'),1)
            state=json.loads((directory/'state.json').read_text())
            self.assertEqual(state['issue'],'import database unavailable')
            self.assertEqual(state['collection_issue'],'collection database unavailable')
            self.assertEqual(state['failed_phase'],'import')


if __name__=='__main__':unittest.main()
