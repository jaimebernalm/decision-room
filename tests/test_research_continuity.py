"""Generic protocol fixtures. No real model, trial reports or business-specific signals."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from decision_room.agent import research
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.research_context import prompt_context
from decision_room.agent.research_contract import validate_research_action
from decision_room.agent.research_agenda import ResearchBudgetReached, coverage
from decision_room.agent.research_continuity import ContinuityAction
from decision_room.agent.research_prompts import RESEARCH_SYSTEM
from decision_room.database import connect
from decision_room.execution import execute
import test_research as base


def ref(execution='e1', metrics=None, series=None):
    return dict(execution_id=execution, metric_keys=metrics or [], series_keys=series or [])


def closure(reason='sufficient'):
    return dict(reason=reason, pending_calculation=None if reason == 'sufficient' else 'Comparar la dispersión entre grupos.',
                decision_if_different='Una dispersión mayor cambiaría el grupo que revisamos primero.',
                explanation='Se conserva la evidencia; el alcance y los límites quedan explícitos.')


def action(kind='execute', **extra):
    return dict(action=kind, investigation_key='sales', table_ids=['t'] if kind == 'execute' else [],
                code='print(1)' if kind == 'execute' else '', summary='Comparar los grupos del extracto.',
                metric_keys=[], followups=[], **extra)


def fixtures():
    snapshot = dict(source={'owner_context': 'Comparar cantidades registradas.'}, answers=[], tables=[{'id': 't', 'alias': 't1'}],
                    proposal={'questions': [], 'investigations': [dict(key='sales', question='Comparar cantidades',
                    business_value='Elegir siguiente comprobación', table_ids=['t'], definitions_needed=[], depends_on=[],
                    proposed_operation='Sumar cantidades', validation_needed=['Tipos'], status='ready')]})
    obs = [dict(investigation_key='sales', execution_id='e1', step=1, status='completed', code='code', logs={},
                result={'metrics': {'total': 5}, 'series': {'groups': {'unit': 'units', 'grain': 'category',
                        'points': [{'label': 'a', 'value': 2}, {'label': 'b', 'value': 3}],
                        'evidence': {'tables': ['t1'], 'operation': 'Group by label'}}}})]
    options = dict(research_continuity=True, max_attempts_per_investigation=3, max_executions=3,
                   max_rounds=3, max_investigations=3, max_agenda=24)
    return snapshot, obs, options


class ContinuityContractTests(unittest.TestCase):
    def test_success_can_continue_only_with_explicit_evidence_and_decision(self):
        s,o,b = fixtures()
        a = action(continuation=dict(evidence=[ref(series=['groups'])], next_calculation='Calcular dispersión.', decision_if_different='Elegir otro grupo.'))
        accepted = validate_research_action(a,s,o,[],b)
        self.assertEqual(accepted['continuation']['evidence'][0]['series_keys'], ['groups'])
        with self.assertRaises(ValueError): validate_research_action(a,s,o,[],{**b,'research_continuity':False})
        with self.assertRaisesRegex(ValueError,'requires continuation'): validate_research_action(action(),s,o,[],b)
        for changes in ({'max_executions':1},{'max_attempts_per_investigation':1},{'max_rounds':0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_research_action(a,s,o,[],{**b,**changes})

    def test_closure_retains_series_and_earlier_success_after_later_failure(self):
        s,o,b = fixtures();o.append(dict(o[0],execution_id='e2',step=2,status='failed',result=None))
        a = action('record_candidate',evidence_refs=[ref(series=['groups'])],closure=closure('budget'))
        result = validate_research_action(a,s,o,[],b)
        self.assertEqual(result['evidence_refs'], [ref(series=['groups'])])
        for field in ('closure','evidence_refs'):
            bad=deepcopy(a);bad.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):validate_research_action(bad,s,o,[],b)
        bad=deepcopy(a);bad['closure']['pending_calculation']=None
        with self.assertRaisesRegex(ValueError,'pending calculation'):validate_research_action(bad,s,o,[],b)

    def test_invalid_stale_cross_task_or_omitted_references_rejected(self):
        for fault in ('unknown_execution','unknown_metric','unknown_series','other_task','stale','omitted','failed','empty'):
            s,o,b=fixtures();r=ref(series=['groups'])
            if fault=='unknown_execution':r['execution_id']='not-saved'
            elif fault=='unknown_metric':r['metric_keys']=['invented']
            elif fault=='unknown_series':r['series_keys']=['invented']
            elif fault=='other_task':o[0]['investigation_key']='other'
            elif fault=='stale':o[0]['current']=False
            elif fault=='omitted':o[0]['result_omitted']=True
            elif fault=='failed':o[0]['status']='failed'
            else:r['series_keys']=[]
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                validate_research_action(action('record_candidate',evidence_refs=[r],closure=closure()),s,o,[],b)

    def test_expansion_uses_registered_series_not_any_metric_in_same_execution(self):
        s,o,b=fixtures();b['delegation']=True
        parent=dict(investigation_key='sales',status='candidate',metric_keys=[],execution_id='e1',evidence_refs=[ref(series=['groups'])])
        child=dict(s['proposal']['investigations'][0],key='detail',question='Qué grupo explica la dispersión',stage='breakdown',
                   priority=dict(relevance=3,magnitude=3,reliability=3,cost=1,reason='Puede cambiar la siguiente comprobación.'),
                   basis_metric_keys=[],basis_evidence=[ref(series=['groups'])])
        a=action('expand',evidence_refs=[ref(series=['groups'])]);a['followups']=[child]
        self.assertEqual(validate_research_action(a,s,o,[parent],b)['followups'][0]['basis_evidence'],[ref(series=['groups'])])
        bad=deepcopy(a);bad['evidence_refs']=[ref(metrics=['total'])]
        with self.assertRaisesRegex(ValueError,'registered parent candidate evidence'):validate_research_action(bad,s,o,[parent],b)
        bad=deepcopy(a);bad['followups'][0]['basis_evidence']=[ref(metrics=['total'])]
        with self.assertRaisesRegex(ValueError,'registered/selected'):validate_research_action(bad,s,o,[parent],b)

    def test_context_retains_all_successes_and_latest_failure_but_off_is_unchanged(self):
        s,o,b=fixtures();o += [dict(o[0],execution_id='e2',step=2),dict(o[0],execution_id='e3',step=3,status='failed',result=None)]
        self.assertEqual([x['execution_id'] for x in prompt_context(s,o,[],b,3)['observations']],['e1','e2','e3'])
        self.assertEqual([x['execution_id'] for x in prompt_context(s,o,[],{**b,'research_continuity':False},3)['observations']],['e3'])
        with self.assertRaises(ResearchBudgetReached):prompt_context(s,o,[],{**b,'max_context_bytes':10},3)
        summary=coverage(s,[{'action':action()}],[],b,'Time budget')
        self.assertEqual(summary['investigations'][0]['closure_status'],'not_recorded')
        self.assertIsNone(summary['investigations'][0]['closure'])

    def test_actual_producer_schema_matches_continuation_and_series_only_candidate(self):
        s,o,b=fixtures();c=prompt_context(s,o,[],b,1);client=ModelClient(ModelSettings('test'))
        with patch.object(client,'_generate',return_value=({},{})) as call:client.generate_research(c)
        system=call.call_args.args[2];schema=client._wire_schema(call.call_args.args[3]);v=Draft202012Validator(schema)
        self.assertIn('execute',[b['properties']['action']['enum'][0] for b in schema['properties']['decision']['anyOf']])
        self.assertNotIn('save it as an UNVERIFIED candidate before any',system)
        self.assertNotIn('BEFORE expanding the scope with another program',system)
        a=ContinuityAction.model_validate(action('record_candidate',evidence_refs=[ref(series=['groups'])],closure=closure())).model_dump()
        v.validate({'decision': a})
        a['evidence_refs'][0]['series_keys']=['invented'];self.assertFalse(v.is_valid({'decision': a}))
        with patch.object(client,'_generate',return_value=({},{})) as call:
            client.generate_research(prompt_context(s,o,[],{**b,'research_continuity':False},1))
        self.assertTrue(call.call_args.args[2].endswith(RESEARCH_SYSTEM))
        self.assertNotIn('execute',call.call_args.args[3]['properties']['action']['enum'])
        self.assertNotIn('closure',call.call_args.args[3]['properties'])

    def test_hidden_failed_attempts_still_consume_budget(self):
        s,o,b=fixtures()
        o.insert(0,dict(o[0],execution_id='failed-old',status='failed',result=None))
        o.append(dict(o[-1],execution_id='failed-new',status='failed',result=None))
        b['visible_execution_ids']=['e1','failed-new']
        with self.assertRaises(ResearchBudgetReached):validate_research_action(action(),s,o,[],b)
        b['max_executions']=9
        with self.assertRaisesRegex(ValueError,'attempt budget'):validate_research_action(action(),s,o,[],b)
        b['visible_execution_ids']=[]
        with self.assertRaisesRegex(ValueError,'visible'):
            validate_research_action(action('record_candidate',evidence_refs=[ref(series=['groups'])],closure=closure()),s,o,[],b)

    def test_schema_keeps_closing_actions_after_execution_budget_is_spent(self):
        s,o,b=fixtures();b['max_executions']=1
        c=prompt_context(s,o,[],b,1);client=ModelClient(ModelSettings('test'))
        with patch.object(client,'_generate',return_value=({},{})) as call:client.generate_research(c)
        allowed=[v['properties']['action']['enum'][0] for v in call.call_args.args[3]['properties']['decision']['anyOf']]
        self.assertNotIn('execute',allowed)
        self.assertIn('record_candidate',allowed)
        self.assertIn('block',allowed)

    def test_default_flag_and_old_action_contract(self):
        from decision_room.config import Config
        from pathlib import Path
        self.assertFalse(Config('',Path('.')).research_continuity)
        s,o,b=fixtures()
        with self.assertRaisesRegex(ValueError,'Preserve the completed result'):
            validate_research_action(action(),s,o,[],{**b,'research_continuity':False})
        old=action('record_candidate');old['metric_keys']=['total']
        accepted=validate_research_action(old,s,o,[],{**b,'research_continuity':False})
        self.assertNotIn('closure',accepted)
        self.assertNotIn('evidence_refs',accepted)


class ContinuingModel(base.ResearchModel):
    def __init__(self,fail_last=False,delegated=False):
        super().__init__();self.fail_last=fail_last;self.delegated=delegated;self.contexts=[]

    def generate_research(self,context,correction=None):
        self.contexts.append(deepcopy(context));self.calls+=1
        if self.delegated and not context['budgets'].get('worker_assignment'):
            if not context['findings']:
                a=action('delegate');a['investigation_key']='';a['assignments']=[dict(investigation_key='sales',instruction='Seguir la señal dentro de esta tarea.')]
            else:
                a=action('finish');a['investigation_key']='';a['synthesis']=dict(priorities=[dict(investigation_key='sales',reason='Evidencia acumulada en la misma tarea.',next_check='Comprobar el dato operativo ausente.')],excluded=[],disagreements=[])
            return a,{}
        if context['findings']:
            a=action('finish');a['investigation_key']='';return a,{}
        obs=context['observations'];table=context['table_catalog'][0]
        if len(obs)>= (3 if self.fail_last else 2):
            refs=[ref(o['execution_id'],list(o['result']['metrics']),list(o['result'].get('series',{}))) for o in obs if o['status']=='completed']
            a=action('record_candidate',evidence_refs=refs,closure=closure('budget' if self.fail_last else 'sufficient'))
            return a,{}
        query='SELECT SUM(CAST(quantity AS INTEGER)) FROM '+table['alias'] if not obs else 'SELECT MAX(CAST(quantity AS INTEGER))-MIN(CAST(quantity AS INTEGER)) FROM '+table['alias']
        metric='quantity_sum' if not obs else 'spread'
        code=f'''from dr_runtime import connect,write_result
with connect() as db:
    value=db.execute({query!r}).fetchone()[0]
    groups=db.execute('SELECT quantity, SUM(CAST(quantity AS INTEGER)) FROM {table['alias']} GROUP BY quantity ORDER BY quantity').fetchall()
write_result({{{metric!r}:value}},evidence=[{{'metric':{metric!r},'tables':[{table['alias']!r}],'operation':{query!r}}}],series={{'groups':{{'unit':'units','grain':'category','points':[{{'label':r[0],'value':r[1]}} for r in groups],'evidence':{{'tables':[{table['alias']!r}],'operation':'GROUP BY quantity ORDER BY quantity'}}}}}})
'''
        if len(obs)==2:code='raise ValueError("controlled failure")'
        a=action();a.update(table_ids=[table['id']],code=code)
        if obs:a['continuation']=dict(evidence=[ref(obs[0]['execution_id'],series=['groups'])],next_calculation='Medir dispersión entre grupos.',decision_if_different='Cambiar la revisión según la dispersión.')
        return a,{}


class EnvelopedModel(ContinuingModel):
    def generate_research(self, context, correction=None):
        output, usage = super().generate_research(context, correction)
        return {'decision': output}, usage


class ContinuityIntegrationTests(unittest.TestCase):
    setUpClass=classmethod(base.ResearchTests.setUpClass.__func__)
    tearDownClass=classmethod(base.ResearchTests.tearDownClass.__func__)
    setUp=base.ResearchTests.setUp
    start=base.ResearchTests.start

    def test_wire_envelope_is_saved_unchanged_and_unwrapped_for_dispatch(self):
        m = EnvelopedModel()
        run = self.start(model=m, research_continuity=True)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(len(run['findings'][0]['evidence_refs']), 2)
        with connect(self.config) as db:
            outputs = db.execute("SELECT output FROM agent_calls WHERE scope=%s AND phase='research' ORDER BY created_at",
                                 (str(run['id']),)).fetchall()
        self.assertTrue(all(set(row['output']) == {'decision'} for row in outputs))
        calls = m.calls
        research.resume(self.config, self.business, run['id'], model=m)
        self.assertEqual(m.calls, calls)

    def test_same_task_keeps_two_executions_and_closure_and_replay_is_idempotent(self):
        m=ContinuingModel();run=self.start(model=m,research_continuity=True,business_planner=True)
        self.assertEqual(run['status'],'completed')
        self.assertEqual([s['action']['action'] for s in run['steps']],['execute','execute','record_candidate','finish'])
        self.assertEqual(len(run['business_direction']),3)
        self.assertEqual(len(run['investigations']),1)
        self.assertEqual(len(run['findings'][0]['evidence_refs']),2)
        self.assertEqual(run['steps'][0]['execution']['result']['metrics']['quantity_sum'],5)
        self.assertEqual(run['steps'][1]['execution']['result']['metrics']['spread'],1)
        self.assertEqual(run['findings'][0]['closure']['reason'],'sufficient')
        self.assertEqual(len(m.contexts[-1]['observations']),2)
        again=research.resume(self.config,self.business,run['id'],model=m)
        self.assertEqual(len(again['steps']),4);self.assertEqual(m.calls,4)
        with connect(self.config) as db:
            versions=db.execute("SELECT DISTINCT prompt_version FROM agent_calls WHERE scope=%s AND phase='research'",(str(run['id']),)).fetchall()
        self.assertEqual([v['prompt_version'] for v in versions],['research-continuity-v2'])

    def test_later_failure_preserves_earlier_reviewable_evidence(self):
        run=self.start(model=ContinuingModel(fail_last=True),research_continuity=True)
        self.assertEqual(run['status'],'completed')
        self.assertEqual([s['execution']['status'] for s in run['steps'] if s['action']['action']=='execute'],['completed','completed','failed'])
        self.assertEqual(len(run['findings'][0]['evidence_refs']),2)
        self.assertEqual(run['findings'][0]['closure']['reason'],'budget')

    def test_worker_continues_without_coordinator_reopening_and_imports_all_evidence(self):
        m=ContinuingModel(delegated=True);run=self.start(model=m,research_continuity=True,delegation=True,max_parallel=1)
        self.assertEqual(run['status'],'completed')
        self.assertEqual(len(run['branches']),1)
        self.assertEqual([s['action']['action'] for s in run['steps']],['delegate','execute','execute','record_candidate','finish'])
        self.assertEqual(len(run['findings'][0]['evidence_refs']),2)
        self.assertEqual(len(run['investigations']),1)
        self.assertEqual(run['investigations'][0]['closure_status'],'recorded')
        parent_final=m.contexts[-1]
        self.assertEqual(len(parent_final['observations']),2)
        self.assertEqual(parent_final['findings'][0]['closure']['reason'],'sufficient')

    def test_crash_after_second_execution_recovers_without_duplicate_evidence(self):
        n=0
        def crash(*args,**kwargs):
            nonlocal n
            value=execute(*args,**kwargs);n+=1
            if n==2:raise SystemExit(17)
            return value
        m=ContinuingModel()
        with self.assertRaises(SystemExit):self.start(model=m,research_continuity=True,executor=crash)
        with connect(self.config) as db:run=db.execute('SELECT id FROM agent_research WHERE session_id=%s',(self.plan['id'],)).fetchone()
        value=research.resume(self.config,self.business,run['id'],model=m)
        self.assertEqual(len(value['findings'][0]['evidence_refs']),2)
        with connect(self.config) as db:self.assertEqual(db.execute('SELECT count(*) n FROM executions WHERE business_id=%s',(self.business,)).fetchone()['n'],2)

    def test_review_receives_every_execution_and_closure_without_recomputing(self):
        from decision_room.agent import review
        m=ContinuingModel();run=self.start(model=m,research_continuity=True)
        with patch('decision_room.agent.review._drive') as drive:
            review.start(self.config,self.business,run['id'],request_key='review-handoff',analyst=m,reviewer=m)
        snapshot=drive.call_args.args[3]['snapshot']
        self.assertEqual(len(snapshot['executions']),2)
        self.assertEqual(len(snapshot['findings'][0]['evidence_refs']),2)
        self.assertEqual(snapshot['findings'][0]['closure']['reason'],'sufficient')

    def test_exhausted_decision_budget_preserves_results_without_fabricated_closure(self):
        run=self.start(model=ContinuingModel(),research_continuity=True,max_turns=2)
        self.assertEqual(run['status'],'partial')
        self.assertEqual(len([s for s in run['steps'] if s['execution_id']]),2)
        self.assertFalse(run['findings'])
        self.assertEqual(run['investigations'][0]['closure_status'],'not_recorded')

    def test_flag_is_persisted_and_request_key_cannot_switch_arms(self):
        m=ContinuingModel();run=self.start(model=m,research_continuity=True)
        self.assertTrue(run['options']['research_continuity'])
        with self.assertRaisesRegex(ValueError,'different knowledge or options'):
            self.start(model=m,research_continuity=False)

    def test_coordinator_expands_registered_series_and_delegates_once_per_task(self):
        class ExpandSeries(ContinuingModel):
            def generate_research(self,context,correction=None):
                assignment=context['budgets'].get('worker_assignment')
                if assignment:
                    result,usage=super().generate_research(context,correction)
                    if result['investigation_key']:
                        result['investigation_key']=assignment['investigation_key']
                    return result,usage
                saved=context['findings']
                if not saved:return super().generate_research(context,correction)
                task='sales__detail'
                if not any(i['key']==task for i in context['plan']['investigations']):
                    basis=ref(saved[0]['evidence_refs'][0]['execution_id'],series=['groups'])
                    child={**context['plan']['investigations'][0], 'key':task,
                        'question':'Contrastar dispersión de la distribución registrada',
                        'proposed_operation':'Contrastar rango y total', 'depends_on':['sales'],
                        'stage':'verify','basis_metric_keys':[], 'basis_evidence':[basis],
                        'focus':dict(segment='Grupos observados',period='Extracto',comparison='Rango frente a total',decision_value='Comprobar concentración.'),
                        'priority':dict(relevance=3,magnitude=3,reliability=3,cost=1,reason='Verificar la interpretación de la serie.')}
                    child={k:v for k,v in child.items() if k not in ('round','parent_key')}
                    result=action('expand',evidence_refs=[basis]);result['followups']=[child]
                    return result,{}
                if not any(f['investigation_key']==task for f in saved):
                    result=action('delegate');result['investigation_key']=''
                    result['assignments']=[dict(investigation_key=task,instruction='Contrastar la serie registrada.')]
                    return result,{}
                result=action('finish');result['investigation_key']=''
                result['synthesis']=dict(priorities=[dict(investigation_key=f['investigation_key'],reason='Evidencia de la distribución.',next_check='Contrastar registros operativos.') for f in saved],excluded=[],disagreements=[])
                return result,{}
        run=self.start(model=ExpandSeries(delegated=True),research_continuity=True,delegation=True,max_parallel=1)
        self.assertEqual(run['status'],'completed')
        self.assertEqual(len(run['branches']),2)
        self.assertEqual(len(run['findings']),2)
        expansion=next(s['action'] for s in run['steps'] if s['action']['action']=='expand')
        self.assertEqual(expansion['metric_keys'],[])
        self.assertEqual(expansion['followups'][0]['basis_evidence'][0]['series_keys'],['groups'])
        self.assertEqual(expansion['evidence_refs'][0]['execution_id'],run['findings'][0]['evidence_refs'][0]['execution_id'])
