"""Private trial bookkeeping on PostgreSQL, without provider or browser calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from decision_room.config import ROOT
from decision_room.database import connect
from tests import test_web as fixtures

spec=importlib.util.spec_from_file_location('product_trial',ROOT/'scripts/checks/product_trial.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


class ProductTrialTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.WebTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.WebTests.tearDownClass.__func__)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'trial'
        (self.root/'units.csv').write_text('quantity,amount\n2,10\n3,20\n')
        self.spec={'version':1,'repetitions':1,'cap_micro_usd':1000000,'scope_cap_micro_usd':500000,
            'businesses':[{'key':'units','name':'Synthetic workshop','description':'quantity records units per row.',
                'goal':'Sum the units.','files':['units.csv'],
                'meanings':[{'file':'units.csv','description':'Units registered per row.',
                    'grain':'one measurement','columns':[{'name':'quantity','meaning':'registered units','unit':'units'}]}]}]}
        self.source=self.root/'spec.json';self.source.write_text(json.dumps(self.spec))
        self.environment=patch.dict('os.environ',{'DECISION_ROOM_ENGINE_IMAGE_ID':'sha256:'+'a'*64,'OPENAI_API_KEY':''})
        self.environment.start();self.addCleanup(self.environment.stop)

    def initialize(self):
        with patch.object(trial.Config,'load',return_value=self.base):trial.initialize(self.source,self.output)
        manifest=json.loads((self.output/'manifest.json').read_text())
        database=conninfo_to_dict(manifest['config']['dsn'])['dbname']
        def cleanup():
            with connect(self.base) as db:db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        self.addCleanup(cleanup)
        return manifest

    def test_prepared_jobs_are_independent_and_share_declared_inputs_without_api(self):
        manifest=self.initialize()
        self.assertEqual(len(manifest['jobs']),2)
        first,second=manifest['jobs']
        self.assertNotEqual(first['business_id'],second['business_id'])
        self.assertEqual(first['inputs'],second['inputs'])
        config=trial.Config(**{**manifest['config'],'storage':Path(manifest['config']['storage'])})
        with connect(config) as db:
            definitions=db.execute('SELECT body FROM data_model_revisions ORDER BY revision').fetchall()
            self.assertEqual(sum(r['body']['tables'][0]['semantic_status']=='owner_declared' for r in definitions),2)
        self.assertEqual(trial.api_budget.Ledger(manifest['budget_path']).snapshot()['calls'],[])
        self.assertEqual(manifest['settings']['model'],'gpt-6-luna')
        self.assertEqual(manifest['settings']['reasoning'],'low')

    def test_legacy_questions_get_bounded_stand_in_answers_and_are_never_retried(self):
        manifest=self.initialize();code=next(j['code'] for j in manifest['jobs'] if j['arm']=='legacy')
        self.assertEqual(manifest['owners']['units'],{'description':'quantity records units per row.','goal':'Sum the units.'})
        real_workspace=trial.Workspace
        def workspace(config,settings):return real_workspace(config,settings,fixtures.WebModel)
        asked=[]
        def answer(owner,question):
            asked.append((owner,question['text']));return 'answered','Prefiero sumar todas las filas.'
        with patch.object(trial,'Workspace',side_effect=workspace),patch.object(trial,'owner_answer',side_effect=answer):
            trial.execute(self.output,code)
        result=json.loads((self.output/'runs'/code/'result.json').read_text())
        answers=json.loads((self.output/'runs'/code/'answers.json').read_text())
        self.assertGreaterEqual(len(answers),1);self.assertLessEqual(len(answers),trial.MAX_ANSWERS)
        self.assertEqual(result['owner_answers'],len(answers));self.assertEqual(len(asked),len(answers))
        self.assertTrue(all(owner==manifest['owners']['units'] for owner,_ in asked))
        self.assertEqual(answers[0]['answer'],'Prefiero sumar todas las filas.')
        self.assertTrue(all(a['state']=='replied' and a['disposition']=='answered' and len(a['question_sha256'])==64 for a in answers))
        self.assertEqual(len({(a['question_id'],a['phase']) for a in answers}),len(answers))
        with self.assertRaises(ValueError):trial.execute(self.output,code)

    def test_stand_in_sends_only_through_the_job_budget_scope(self):
        import httpx
        manifest=self.initialize()
        seen=[]
        replies=[('stop',json.dumps({'disposition':'answered','text':' Comparo con el año pasado. '})),
                 ('stop',json.dumps({'disposition':'unknown','text':''})),
                 ('length','{"disposition":"answ'),
                 ('stop',json.dumps({'disposition':'answered','text':''}))]
        def provider(request):
            body=json.loads(request.content);seen.append(body)
            content=replies.pop(0)
            return httpx.Response(200,json={'model':'gpt-6-luna','service_tier':'default',
                'choices':[{'finish_reason':content[0],'message':{'content':content[1]}}],
                'usage':{'prompt_tokens':900,'completion_tokens':40}})
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':manifest['budget_path'],'OPENAI_API_KEY':'test-only'}), \
                patch.object(trial.api_budget.httpx,'HTTPTransport',lambda **kw:httpx.MockTransport(provider)), \
                trial.api_budget.scope('web:job-1'):
            text=trial.owner_answer({'description':'Una tienda.','goal':'Cómo va el año.'},
                                    {'id':'q','phase':'planning','text':'¿Qué periodos comparo?','options':['año','mes']})
            owner={'description':'Una tienda.','goal':'Cómo va el año.'}
            self.assertEqual(trial.owner_answer(owner,{'text':'¿Margen?'}),('unknown',''))
            for _ in range(2):  # truncated, then answered without text: refused, never repaired
                with self.assertRaises(ValueError):trial.owner_answer(owner,{'text':'¿Margen?'})
        self.assertEqual(text,('answered','Comparo con el año pasado.'))
        self.assertEqual(seen[0]['response_format']['json_schema']['strict'],True)
        self.assertEqual(seen[0]['service_tier'],'default');self.assertEqual(seen[0]['max_completion_tokens'],2000)
        self.assertIn('Una tienda.',seen[0]['messages'][0]['content']);self.assertIn('¿Qué periodos comparo?',seen[0]['messages'][0]['content'])
        calls=trial.api_budget.Ledger(manifest['budget_path']).snapshot()['calls']
        self.assertEqual([(c['scope'],c['state']) for c in calls],[('web:job-1','settled')]*4)
        with patch.dict('os.environ',{'DECISION_ROOM_API_BUDGET_PATH':''}),self.assertRaises(trial.api_budget.BudgetStopped):
            trial.owner_answer({'description':'x','goal':'y'},{'text':'z'})

    def test_crash_is_preserved_and_over_cap_spec_is_rejected_before_preparation(self):
        manifest=self.initialize();code=manifest['jobs'][0]['code']
        real_workspace=trial.Workspace
        def workspace(config,settings):
            ws=real_workspace(config,settings)
            ws.scoped=lambda business:ws
            ws.run_job=lambda job:(_ for _ in ()).throw(RuntimeError('private diagnostic'))
            return ws
        with patch.object(trial,'Workspace',side_effect=workspace),self.assertRaises(RuntimeError):trial.execute(self.output,code)
        failed=json.loads((self.output/'runs'/code/'failure.json').read_text())
        self.assertEqual(failed,{'exception_type':'RuntimeError'})
        with self.assertRaises(ValueError):trial.execute(self.output,code)
        self.spec['cap_micro_usd']=25000001;self.source.write_text(json.dumps(self.spec))
        with self.assertRaises(ValueError):trial.initialize(self.source,self.root/'too-large')
        self.assertFalse((self.root/'too-large').exists())
