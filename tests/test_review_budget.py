"""Large-context review regressions: local tokenizer, mock HTTP, scoped originals."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import httpx
from decision_room.agent.model import ModelClient, ModelSettings, record_request
from decision_room.agent.review_budget import compact, read, tokens, fit
from decision_room.agent.review_context import model_context
from test_chart_layers import layered
from test_model_strict_schemas import assert_strict_objects


def large_context():
    context=layered()
    text='\n'.join(f'Comprobación {i}: conservar definición, dudas y periodo, no afirmar causas sin pruebas.' for i in range(4000))
    context.update(role='reviewer',review_policy=5,budgets={'review_context_budget':True},
        owner_context='Necesito decidir qué revisar primero.',owner_answers=[],
        review_issues=[dict(key='integrity',status='open',detail='No se ha verificado la definición del importe.')],
        conversation=[dict(step=i,role='analyst',action=dict(action='submit',report=dict(context['report'],summary=text),message='Borrador')) for i in range(1,8)],
        business_direction=dict(brief={'objective':'Comparar canales'},checkpoints=[{'instructions':[text]} for _ in range(5)]),
        business_context={'manifest_id':'synthetic-session','doubts':[{'text':'Importe por unidad o por fila sin confirmar.'}],'retrievals':[]})
    context['business_direction']['checkpoints'][-1]={'instructions':['Comprobar el canal con menos registros.']}
    context['conversation'][-1]['action']['report']=context['report']
    for o in context['observations']:
        o['code']=text; o['logs']={'stdout':text}
    return context


class ReviewBudgetTests(unittest.TestCase):
    def test_large_wire_request_compacts_and_preserves_decision_inputs(self):
        context=large_context();original=deepcopy(context);saved=[]
        transport=httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={
            'choices':[{'finish_reason':'stop','message':{'content':'{"action":"revise"}'}}],
            'usage':{'prompt_tokens':100,'prompt_tokens_details':{'cached_tokens':20}}})))
        with patch('decision_room.agent.model.httpx.AsyncClient',return_value=transport), record_request(saved.append):
            _,usage=ModelClient(ModelSettings('offline',protocol='chat_completions')).generate_reviewer(context)
        audit=saved[0]['context_budget'];self.assertGreater(audit['input_before'],70000)
        self.assertLessEqual(audit['total_reserved'],70000)
        packed=json.loads(saved[0]['payload']['messages'][1]['content'])
        self.assertEqual(packed['report'],context['report'])
        self.assertEqual(packed['review_issues'],context['review_issues'])
        self.assertEqual(packed['business_context']['doubts'],context['business_context']['doubts'])
        self.assertEqual(context,original)
        self.assertEqual(usage['context_budget'],audit)
        assert_strict_objects(self,saved[0]['payload']['response_format']['json_schema']['schema'])

    def test_byte_ceiling_is_bypassed_only_with_option(self):
        context=large_context()
        self.assertTrue(model_context(context,'reviewer')['observations'][0]['result'])
        context['budgets']['review_context_budget']=False
        with self.assertRaisesRegex(ValueError,'KB'):model_context(context,'reviewer')

    def test_reference_reads_original_and_rejects_foreign_paths(self):
        context=large_context();packed=compact(context)
        path=packed['observations'][0]['code']['read_review_context']
        page=read(context,dict(tool='read_review_context',path=path,offset=0,limit=2))
        self.assertEqual(page['value'],context['observations'][0]['code'][:64])
        self.assertEqual(page['next_offset'],64)
        for path in ('/etc/passwd','/budgets','/observations/9999','/../owner_context'):
            with self.assertRaises((ValueError,KeyError,IndexError,TypeError)):
                read(context,dict(tool='read_review_context',path=path,offset=0,limit=5))

    def test_long_series_is_marked_as_sample_and_every_original_point_is_readable(self):
        context=large_context(); index=next(i for i,o in enumerate(context['observations']) if o['result'].get('series')); key=next(iter(context['observations'][index]['result']['series']))
        points=[dict(label=f'2025-{i:03}',value=str(i)) for i in range(366)]
        context['observations'][index]['result']['series'][key]['points']=points
        series=compact(context)['observations'][index]['result']['series'][key]
        self.assertEqual(series['points_summary']['total'],366)
        self.assertEqual(len(series['points']),24)
        path=series['points_summary']['detail']['read_review_context']
        result=[];offset=0
        while offset is not None:
            page=read(context,dict(tool='read_review_context',path=path,offset=offset,limit=100))
            result += [item['value'] for item in page['value']]; offset=page['next_offset']
        self.assertEqual(result,points)

    def test_protected_material_is_never_silently_dropped(self):
        context=large_context();context['report']['summary']=' '.join(str(i) for i in range(100000))
        payload={'messages':[], 'max_tokens':8000}
        with self.assertRaisesRegex(ValueError,'Protected review material'):
            fit(context,payload,lambda view:[{'role':'user','content':json.dumps(view)}])


class ReviewReadPersistenceTests(unittest.TestCase):
    import test_review as fixtures
    setUpClass=classmethod(fixtures.ReviewTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.ReviewTests.tearDownClass.__func__)
    setUp=fixtures.ReviewTests.setUp

    def test_read_is_scoped_audited_replayed_and_not_a_python_execution(self):
        from decision_room.agent import review
        from test_review import DialogueModel
        class Reader(DialogueModel):
            def generate_reviewer(self,context,correction=None):
                reads=[r for r in context['business_context']['retrievals'] if r['request'].get('tool')=='read_review_context']
                if not reads:
                    return dict(action='retrieve',message='Leer el cálculo guardado.',retrieval=dict(
                        tool='read_review_context',path='/observations/0/code',offset=0,limit=100)),{}
                assert reads[-1]['response']['value']==context['observations'][0]['code']
                return super().generate_reviewer(context,correction)
        roles=Reader('plain')
        result=review.start(self.config,self.business,self.research['id'],request_key='read-budget',
            review_context_budget=True,analyst=roles,reviewer=roles)
        self.assertTrue(result['publishable'])
        self.assertEqual(len(result['model_calls']),3)
        self.assertEqual(len(result['context_retrievals']),1)
        self.assertEqual(len(result['observations']),1)
        resumed=review.resume(self.config,self.business,result['id'],analyst=roles,reviewer=roles)
        self.assertEqual(resumed['approved_sha256'],result['approved_sha256'])
        self.assertEqual(len(resumed['model_calls']),3)
