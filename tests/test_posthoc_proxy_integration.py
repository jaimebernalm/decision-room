"""Real database/admission/proxy; all provider HTTP is simulated and unbilled."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from psycopg import sql
from psycopg.conninfo import make_conninfo
from decision_room.config import Config
from decision_room.database import connect,migrate
from decision_room.service import create_business,import_batch
from decision_room.engine import admission
from decision_room.reports.posthoc.provider import Budget, BudgetStop, ProxyInterpreter


class ProxyIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Config.load();cls.name='dr_posthoc_'+uuid4().hex
        with connect(cls.base) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.name)))
        cls.config=replace(cls.base,dsn=make_conninfo(cls.base.dsn,dbname=cls.name))
        migrate(cls.config)

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.name)))

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.config=replace(self.config,storage=self.root/'storage')
        business=create_business(self.config,'Posthoc fixture')['id'];self.business=business
        csv=self.root/'fixture.csv';csv.write_text('unidades\n2\n3\n')
        batch=import_batch(self.config,business,[csv])
        self.run,self.token=admission.create_run(self.config,business,batch['analysis']['id'],
            table_ids=[batch['files'][0]['table_id']],owner_context='Offline verification fixture',
            request_key=uuid4().hex,model='gpt-6-luna')
        self.budget=Budget(self.root/'budget.sqlite')

    def test_real_proxy_captures_cost_and_keeps_credentials_out_of_artifacts(self):
        def provider(request):
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':100})
            body=json.loads(request.content);self.assertEqual(body['service_tier'],'default')
            return httpx.Response(200,json={'status':'completed','model':'gpt-6-luna','service_tier':'default',
                'usage':{'input_tokens':100,'output_tokens':10,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}},
                'output':[{'type':'message','content':[{'type':'output_text','text':'{"status":"uncertain","reason":"fixture","recipe":null}'}]}]})
        ask=ProxyInterpreter(self.config,self.business,self.run,self.token,api_key='offline-fixture-secret',
            budget=self.budget,report='fixture',dest=self.root/'provider',transport=httpx.MockTransport(provider))
        result=ask('Return a JSON interpretation',{'masked_text':'Total ██'},'one')
        self.assertEqual(result['status'],'uncertain')
        self.assertEqual(self.budget.inspect()['unresolved'],0)
        self.assertGreater(float(self.budget.inspect()['known_cost']),0)
        for path in (self.root/'provider').rglob('*'):
            if path.is_file():
                self.assertNotIn('offline-fixture-secret',path.read_text())
                self.assertNotIn(self.token,path.read_text())

    def test_complete_export_with_real_database_and_simulated_model(self):
        from decision_room.reports.posthoc import api
        source=self.root/'report.html';source.write_text('<h1>Informe</h1><p>Total 5 unidades.</p>')
        csv=self.root/'numbers.csv';csv.write_text('unidades\n2\n3\n')
        api.prepare(source,[csv],self.root/'run')
        calls=[]
        def provider(request):
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':100})
            body=json.loads(request.content);data=json.loads(body['input']);self.assertEqual(data['response_format'],'json');calls.append(data)
            readings=[{'occurrence_id':target['occurrence_id'],'status':'uncertain','reason':'No explicit period','recipe':None} for target in data['targets']]
            return httpx.Response(200,json={'status':'completed','model':'gpt-6-luna','service_tier':'default',
                'usage':{'input_tokens':100,'output_tokens':20,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}},
                'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'readings':readings})}]}]})
        result=api.run(self.config,self.root/'run',self.root/'all-budget.sqlite',api_key='offline-test-only',transport=httpx.MockTransport(provider))
        self.assertEqual(result['status'],'completed');self.assertEqual(len(calls),2)
        self.assertEqual(calls[0],calls[1]);self.assertTrue(result['checks']['invariants_passed'])
        for filename in ['original.html','derived.html','inventory.json','verification/ledger.json','run.json','checks.json']:
            self.assertTrue((self.root/'run'/filename).is_file(),filename)
        with self.assertRaises(FileExistsError):api.run(self.config,self.root/'run',self.root/'all-budget.sqlite',api_key='offline-test-only')

        api.prepare(source,[csv],self.root/'qa-failure')
        with patch('decision_room.reports.posthoc.presentation.check',side_effect=OSError(9,'sensitive diagnostic text')):
            with self.assertRaises(OSError):api.run(self.config,self.root/'qa-failure',self.root/'all-budget.sqlite',api_key='offline-test-only',transport=httpx.MockTransport(provider))
        failure=json.loads((self.root/'qa-failure/run.json').read_text())
        self.assertEqual(failure['stage'],'presentation_check');self.assertEqual(failure['errno'],9)
        self.assertNotIn('sensitive diagnostic text',json.dumps(failure))
        started=json.loads((self.root/'qa-failure/started.json').read_text())
        self.assertIn('interpretation.py',started['code_sha256'])

    def test_unknown_cost_stops_without_replaying_generation(self):
        calls=[]
        def provider(request):
            calls.append(request.url.path)
            if request.url.path.endswith('input_tokens'):return httpx.Response(200,json={'input_tokens':100})
            raise httpx.ReadError('simulated disconnect')
        ask=ProxyInterpreter(self.config,self.business,self.run,self.token,api_key='offline-fixture-secret',
            budget=self.budget,report='fixture',dest=self.root/'provider',transport=httpx.MockTransport(provider))
        with self.assertRaises(BudgetStop):ask('Return JSON',{'masked_text':'██'},'one')
        self.assertEqual(len(calls),2)
        self.assertEqual(self.budget.inspect()['unresolved'],1)
        self.assertTrue((self.root/'provider/one/response.raw').exists())

if __name__=='__main__':unittest.main()
