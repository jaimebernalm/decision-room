"""P1b planning coverage and freedom to calculate, entirely offline."""
from copy import deepcopy
from dataclasses import replace
import csv
from datetime import date, timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import jsonschema

from decision_room.agent import service, research, review
from decision_room.agent.context import model_context, fingerprint
from decision_room.agent.contracts import Action, validate_action
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.panorama_research import validate, view
from decision_room.agent.research_context import prompt_context
from decision_room.config import Config
from decision_room.database import connect
from decision_room.service import create_business, import_batch
from test_panorama_contract_v2 import frozen_fixture
from test_model_strict_schemas import assert_strict_objects
from test_research import ResearchModel, ResearchTests


def plan_decisions(context, key='sales'):
    return {item['key']:dict(disposition='investigate',investigation_key=key,
        question='¿El producto mantiene registros en otros canales durante el hueco y cuándo termina exactamente?',
        reason='Distinguir ausencia de registros del canal y caída general antes de proponer una reacción.')
        for item in context['sales_panorama']['signals']}


class PanoramaPlanner(ResearchModel):
    def __init__(self):
        super().__init__()
        self.contexts=[]

    def generate(self, context, correction=None):
        self.contexts.append(('planning',deepcopy(context)))
        action, usage=super().generate(context, correction)
        if context.get('sales_panorama_research'):
            action['proposal']['panorama_plan']=plan_decisions(context)
            action['proposal']['investigations'][0]['question']='Comprobar los cambios y huecos frente a los otros canales.'
        return action,usage

    def generate_business_planner(self, context, correction=None):
        self.contexts.append(('business_planner',deepcopy(context)))
        return super().generate_business_planner(context, correction)

    def generate_research(self, context, correction=None):
        self.contexts.append(('research',deepcopy(context)))
        if context['findings']:
            return dict(action='finish',investigation_key='',code='',table_ids=[],metric_keys=[],summary='Cálculo guardado; no se atribuye una causa.'),{}
        if context['observations']:
            result=context['observations'][-1]
            if result['status'] != 'completed': raise AssertionError(result)
            return dict(action='record_candidate',investigation_key='sales',code='',table_ids=[],metric_keys=list(result['result']['metrics']),
                summary='Se conserva el hueco y la actividad de los otros canales.',
                closure=dict(reason='sufficient',pending_calculation='Contrastar el origen de los registros con el responsable del canal.',decision_if_different='Si faltó captura, reparar la comparación; si no, comprobar disponibilidad.',explanation='Fechas y contraste entre canales calculados.')) ,{}
        table=context['table_catalog'][0]
        gap=next(s for s in context['sales_panorama']['signals'] if s['kind']=='gap' and 'product' not in s)
        query=f"SELECT count(*) FROM {table['alias']} WHERE CAST(fecha AS DATE) BETWEEN ? AND ? AND canal_id <> ?"
        code=f'''from dr_runtime import connect, write_result
with connect() as db:
    other=db.execute({query!r}, [{gap['start']!r},{gap['end']!r},{gap['channel']!r}]).fetchone()[0]
    days=db.execute('SELECT DISTINCT CAST(fecha AS DATE) FROM {table['alias']} WHERE canal_id=? ORDER BY 1', [{gap['channel']!r}]).fetchall()
    from datetime import timedelta
    observed={{r[0] for r in days}}
    missing=[]
    current=min(observed)
    while current<=max(observed):
        if current not in observed: missing.append(current)
        current+=timedelta(days=1)
    metrics={{'other_channel_rows':str(other),'gap_start':str(min(missing)),'gap_end':str(max(missing))}}
write_result(metrics,evidence=[{{'metric':k,'tables':[{table['alias']!r}],'operation':'Días ausentes entre el primero y último registro; contraste de filas en otros canales en ese tramo.'}} for k in metrics],notes=['Ausencia de registros, no una causa confirmada.'])
'''
        return dict(action='execute',investigation_key='sales',code=code,table_ids=[table['id']],metric_keys=[],summary='Comprobar fechas exactas y actividad de los otros canales.'),{}


class PanoramaResearchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.frozen=frozen_fixture()

    def source(self):
        table=self.frozen['tables'][0]['table_id']
        return dict(research_panorama=deepcopy(self.frozen),owner_context='Comparar cantidades, no euros.',unavailable_sources=[],
            tables=[dict(id=table,names=['sales.csv'],row_count=300,column_names=['date','product','channel','quantity'])])

    def test_every_gap_and_change_has_a_decision_schema_and_controller(self):
        source=self.source(); table=source['tables'][0]['id']
        context=model_context(source,[table],[],None)
        self.assertTrue(context['sales_panorama_research'])
        self.assertEqual(set(s['kind'] for s in context['sales_panorama']['signals']),{'gap','change'})
        self.assertTrue(ModelClient._prompt_context(context).startswith('{"sales_panorama":'))
        model=PanoramaPlanner(); raw,_=model.generate(context)
        action=Action.model_validate(raw).model_dump()
        captured=[]
        client=ModelClient(ModelSettings('offline'))
        with patch.object(client,'_generate',side_effect=lambda c,r,s,sc:captured.append(sc)):
            client.generate(context)
        schema=captured[0]
        assert_strict_objects(self,schema)
        jsonschema.validate(action,schema)
        validate_action(action,source,[table],[])
        for key in action['proposal']['panorama_plan']:
            bad=deepcopy(action);del bad['proposal']['panorama_plan'][key]
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad,schema)
            with self.assertRaisesRegex(ValueError,'every gap and major change'): validate_action(bad,source,[table],[])
        key=next(iter(action['proposal']['panorama_plan']))
        bad=deepcopy(action);bad['proposal']['panorama_plan'][key]['investigation_key']='invented'
        with self.assertRaisesRegex(ValueError,'real investigation_key'): validate_action(bad,source,[table],[])
        bad['proposal']['panorama_plan'][key]['investigation_key']='sales'
        bad['proposal']['investigations'][0]['table_ids']=['another_table']
        with self.assertRaisesRegex(ValueError,'access to the signal source'): validate_action(bad,source,[table],[])
        excluded=deepcopy(action)
        excluded['proposal']['panorama_plan'][key]=dict(disposition='dismissed',investigation_key=None,question=None,
            reason='Comparación fuera del objetivo pedido; se conserva para ampliar si cambia el encargo.')
        jsonschema.validate(excluded,schema)
        validate_action(excluded,source,[table],[])
        excluded['proposal']['panorama_plan'][key]['reason']=' '
        with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(excluded,schema)

    def test_research_and_worker_get_same_panorama_without_counting_it_as_execution(self):
        source=self.source()
        context=model_context(source,[source['tables'][0]['id']],[],None)
        raw,_=PanoramaPlanner().generate(context)
        snapshot=dict(source=source,answers=[],proposal=raw['proposal'],tables=source['tables'])
        for opts in ({}, {'research_continuity':True}, {'worker_assignment':{'investigation_key':'sales'}}):
            actual=prompt_context(snapshot,[],[],opts,0)
            self.assertEqual(actual['sales_panorama'],context['sales_panorama'])
            self.assertEqual(actual['observations'],[])
            self.assertEqual(actual['budgets']['attempts_used'],{})
            client=ModelClient(ModelSettings('offline'))
            for method in ('generate_research', 'generate_business_planner'):
                captured=[]
                candidate={**actual, 'stage':'initial', 'owner_replies':[]}
                with patch.object(client,'_generate',side_effect=lambda c,r,s,sc:captured.append(sc)):
                    getattr(client,method)(candidate)
                assert_strict_objects(self,captured[0])
        source.pop('research_panorama')
        self.assertNotIn('sales_panorama',model_context(source,[source['tables'][0]['id']],[],None))


class PanoramaResearchIntegrationTests(unittest.TestCase):
    setUpClass=classmethod(ResearchTests.setUpClass.__func__)
    tearDownClass=classmethod(ResearchTests.tearDownClass.__func__)

    def test_real_import_plan_execution_resume_and_flag_isolation(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            config=replace(self.base,dsn=self.dsn,storage=root/'storage',sales_panorama_research=True)
            business=create_business(config,'Synthetic retailer')['id']
            path=root/'daily.csv'
            with path.open('w',newline='') as f:
                writer=csv.writer(f,quoting=csv.QUOTE_ALL)
                writer.writerow(['fecha','canal_id','producto_id','unidades'])
                for i in range(120):
                    day=date(2025,1,1)+timedelta(days=i)
                    for channel in ('Local','Web'):
                        if channel=='Local' and 75<=i<=81: continue
                        writer.writerow([str(day)+' 00:00:00',channel,'Artículo',2 if i<60 else 3])
            analysis=import_batch(config,business,[path])['analysis']['id']
            model=PanoramaPlanner()
            with patch.object(ModelClient,'_generate',side_effect=AssertionError('No real calls')):
                planned=service.start(config,business,analysis,owner_context='Comparar unidades y comprobar huecos.',request_key='p1b',model=model)
                self.assertIn(planned['status'],('ready','limited'),planned.get('issue'))
                run=research.start(config,business,planned['id'],request_key='r',delegation=False,business_planner=True,
                                   research_continuity=True,model=model)
                self.assertEqual(run['status'],'completed',run.get('issue'))
                self.assertTrue(run['options']['sales_panorama_research'])
                self.assertEqual(len(run['findings']),1)
                # Turning the environment option off must not rewrite a frozen run.
                off=replace(config,sales_panorama_research=False)
                resumed=research.resume(off,business,run['id'],model=model)
                self.assertEqual(resumed['status'],'completed')
                planned_again=service.resume(off,business,planned['id'],model=model)
                self.assertEqual(planned_again['status'],planned['status'])
                control=service.start(off,business,analysis,owner_context='Comparar unidades.',request_key='control',model=ResearchModel())
                # Rebased P1b feeds the corrected review chain with every new
                # option enabled; wire adapter, panorama obligations and replay.
                from test_sales_panorama_integration import PanoramaDialogue
                class CombinedDialogue(PanoramaDialogue):
                    def generate_analyst_review(inner,context,correction=None):
                        output,usage=super().generate_analyst_review(context,correction)
                        output['report']['panorama_dispositions']=[dict(signal_key=k,decision=v)
                            for k,v in output['report']['panorama_dispositions'].items()]
                        return output,usage
                roles=CombinedDialogue('simple')
                delivered=review.start(config,business,run['id'],request_key='combined',sales_panorama=True,
                    owner_presentation=True,review_loop_guard=True,panorama_obligation_guard=True,
                    review_context_budget=True,review_stable_prefix=True,analyst=roles,reviewer=roles)
                self.assertTrue(delivered['publishable'],delivered.get('issue'))
                self.assertTrue(delivered['report']['panorama_dispositions'])
                self.assertTrue(all(c['panorama_obligations']['required_count']>0 for c in roles.contexts))
                again=review.resume(off,business,delivered['id'],analyst=roles,reviewer=roles)
                self.assertEqual(again['approved_sha256'],delivered['approved_sha256'])
                self.assertEqual(len(roles.contexts),2)

            phases={phase for phase,context in model.contexts if context.get('sales_panorama_research')}
            self.assertEqual(phases,{'planning','research','business_planner'})
            research_contexts=[context for phase,context in model.contexts if phase=='research' and context['observations']]
            metrics=research_contexts[0]['observations'][0]['result']['metrics']
            self.assertEqual(metrics,{'other_channel_rows':'7','gap_start':'2025-03-17','gap_end':'2025-03-23'})
            with connect(config) as db:
                saved=db.execute('SELECT source_snapshot FROM agent_sessions WHERE id=%s',(control['id'],)).fetchone()['source_snapshot']
                self.assertNotIn('research_panorama',saved)
                versions=db.execute("SELECT prompt_version FROM agent_calls WHERE session_id=%s AND phase IN ('planning','research','business_planner')",(planned['id'],)).fetchall()
                self.assertTrue(all('panorama-research-v1' in row['prompt_version'] for row in versions))
