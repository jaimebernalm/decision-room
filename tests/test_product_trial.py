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

    def test_waiting_is_recorded_once_and_not_replied_to_or_retried(self):
        manifest=self.initialize();code=manifest['jobs'][0]['code']
        real_workspace=trial.Workspace
        def workspace(config,settings):return real_workspace(config,settings,fixtures.WebModel)
        with patch.object(trial,'Workspace',side_effect=workspace):trial.execute(self.output,code)
        result=json.loads((self.output/'runs'/code/'result.json').read_text())
        self.assertEqual(result['status'],'waiting')
        self.assertFalse(result['delivery']);self.assertFalse(result['snapshot'])
        with self.assertRaises(ValueError):trial.execute(self.output,code)

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
