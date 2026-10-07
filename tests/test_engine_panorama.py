"""Engine panorama scope, exact fixture values and paged immutable observations."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from psycopg import sql
from psycopg.types.json import Jsonb
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.engine import admission, gateway, panorama, numbers
from decision_room.service import create_business, import_batch


class PanoramaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_engine_panorama_' + uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='dr-engine-panorama-')
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Panorama fixture')['id']
        source = self.root / 'sales.csv'
        source.write_text('date,product,channel,quantity\n2025-01-01,Item,Local,2\n2025-01-31,Item,Local,3\n2025-02-01,Item,Local,4\n2025-02-28,Item,Local,6\n')
        auxiliary = self.root / 'catalog.csv'; auxiliary.write_text('code,name\nA,Item\n')
        batch = import_batch(self.config, self.business, [source, auxiliary])
        self.analysis = batch['analysis']['id']
        by_name = {f['original_names'][0]: f['table_id'] for f in batch['files']}
        self.table, self.aux = by_name['sales.csv'], by_name['catalog.csv']
        self.run, self.token = self.create()

    def create(self):
        return admission.create_run(self.config, self.business, self.analysis,
            table_ids=[self.table, self.aux], owner_context='Describe units', request_key=uuid4().hex, model='test-model')

    def calculate(self, **kwargs):
        return panorama.calculate(self.config, self.run, self.token, table_id=self.table, request_key='overview', **kwargs)

    def tool(self, name, args, *, run=None, token=None):
        result = gateway.dispatch(self.config, run or self.run, token or self.token,
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}})
        self.assertNotIn('isError', result['result'])
        self.assertLess(len(admission.canonical(result)), 64 * 1024)
        return json.loads(result['result']['content'][0]['text'])

    def test_calculator_values_trace_and_idempotent_snapshot(self):
        first = self.calculate(); second = self.calculate()
        self.assertEqual(first, second)
        observations = first['body']['observations']
        metrics = {k: v for o in observations for k, v in o['result']['metrics'].items()}
        self.assertEqual({k: metrics[k] for k in ['total', 'rows', 'period_before', 'period_current', 'period_change']},
                         {'total': '15.00000000', 'rows': '4', 'period_before': '5.00000000',
                          'period_current': '10.00000000', 'period_change': '5.00000000'})
        self.assertEqual(metrics['before_days'], '31'); self.assertEqual(metrics['current_days'], '28')
        for o in observations:
            self.assertEqual(panorama.observation(self.config, self.business, self.run, o['execution_id']), o)
            self.assertEqual(o['inputs']['source']['id'], str(self.table))
            self.assertEqual(o['knowledge_sha256'], admission.authenticate(self.config, self.run, self.token)['snapshot_sha256'])
        with self.assertRaises(ValueError):
            self.calculate(mapping={'date': 'date', 'product': 'product', 'channel': 'channel', 'quantity': 'quantity'})
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM engine_panoramas WHERE run_id=%s', (self.run,)).fetchone()['n'], 1)

    def test_mcp_summary_pagination_and_observations_use_same_job(self):
        args = {'table_id': str(self.table), 'request_key': 'pages'}
        page = self.tool('panorama', args); rows = page['rows']; ids = page['observation_ids']
        while page['cursor'] is not None:
            page = self.tool('panorama', {**args, 'cursor': page['cursor']}); rows.extend(page['rows'])
        self.assertEqual(len(rows), page['total_rows'])
        self.assertTrue(ids)
        self.assertTrue(any(r['path'].endswith('/period/0') and r['value'] == '2025-01-01' for r in rows))
        evidence = self.tool('resultado', {'execution_id': ids[0]})
        self.assertEqual(evidence['origin'], 'deterministic_panorama')
        self.assertEqual(evidence['verification'], 'pending')
        self.assertEqual(evidence['table_ids'], [str(self.table)])
        other, token = self.create()
        with self.assertRaises(admission.Denied):
            self.tool('resultado', {'execution_id': ids[0]}, run=other, token=token)
        with self.assertRaises(admission.Denied):
            panorama.calculate(self.config, other, self.token, **args)
        with self.assertRaises(admission.Denied):
            panorama.calculate(self.config, self.run, self.token, table_id=uuid4(), request_key='outside')

    def test_unsupported_catalog_is_unavailable_without_fake_zero_or_observation(self):
        row = panorama.calculate(self.config, self.run, self.token, table_id=self.aux, request_key='auxiliary')
        self.assertEqual(row['body']['observations'], [])
        table = row['body']['tables'][0]
        self.assertEqual(table['status'], 'unavailable')
        self.assertNotIn('total', table)

    def test_corrupt_cache_is_rejected_and_pausing_prevents_late_registration(self):
        row = self.calculate()
        with connect(self.config) as db:
            db.execute("UPDATE engine_panoramas SET body='{}'::jsonb WHERE id=%s", (row['id'],))
        with self.assertRaises(ValueError):
            self.calculate()
        prepare = panorama.sales_panorama_store.prepare
        def pause(*args, **kwargs):
            result = prepare(*args, **kwargs)
            with connect(self.config) as db:
                db.execute("UPDATE engine_runs SET status='pausing' WHERE id=%s", (self.run,))
            return result
        with patch.object(panorama.sales_panorama_store, 'prepare', side_effect=pause):
            with self.assertRaises(admission.Denied):
                panorama.calculate(self.config, self.run, self.token, table_id=self.aux, request_key='late')
        with connect(self.config) as db:
            self.assertIsNone(db.execute("SELECT id FROM engine_panoramas WHERE run_id=%s AND request_key='late'", (self.run,)).fetchone())

    def reference(self):
        row = self.calculate()
        observation = next(o for o in row['body']['observations'] if 'total' in o['result']['metrics'])
        return {'key': 'units', 'execution_id': observation['execution_id'], 'metric': 'total'}

    def test_verify_recalculates_the_source_and_freezes_exact_scope(self):
        ref = self.reference()
        calculate = panorama.sales_panorama.calculate
        with patch.object(panorama.sales_panorama, 'calculate', wraps=calculate) as recalculate:
            first = numbers.verify(self.config, self.run, self.token, request_key='check', numbers=[ref])
            second = numbers.verify(self.config, self.run, self.token, request_key='check', numbers=[ref])
        self.assertEqual(first, second)
        self.assertEqual(recalculate.call_count, 1)
        check = first['body']['checks'][0]
        self.assertEqual(check['status'], 'verified_in_scope')
        self.assertEqual(check['value'], '15.00000000')
        self.assertEqual(check['scope']['table_id'], str(self.table))
        self.assertIn('not_checked', check['scope']['semantic_status'])
        page = self.tool('verify_numbers', {'request_key': 'check', 'numbers': [ref]})
        self.assertEqual(page['verification_id'], str(first['id']))
        with self.assertRaises(ValueError):
            numbers.verify(self.config, self.run, self.token, request_key='check', numbers=[{**ref, 'metric': 'rows'}])

    def test_verify_corrects_value_but_does_not_rewrite_ambiguous_scope(self):
        ref = self.reference()
        with connect(self.config) as db:
            row = db.execute('SELECT * FROM engine_panoramas WHERE run_id=%s', (self.run,)).fetchone()
            observation = next(o for o in row['body']['observations'] if o['execution_id'] == ref['execution_id'])
            observation['result']['metrics']['total'] = '999'
            db.execute('UPDATE engine_panoramas SET body=%s,body_sha256=%s WHERE id=%s',
                       (Jsonb(row['body']), admission.sha(admission.canonical(row['body'])), row['id']))
        checked = numbers.verify(self.config, self.run, self.token, request_key='correct', numbers=[ref])['body']['checks'][0]
        self.assertEqual((checked['status'], checked['original_value'], checked['value']),
                         ('corrected_in_scope', '999', '15.00000000'))
        with connect(self.config) as db:
            operation = next(e for e in observation['result']['evidence'] if e['metric'] == 'total')
            operation['operation'] = 'A different subset and a different quantity.'
            db.execute('UPDATE engine_panoramas SET body=%s,body_sha256=%s WHERE id=%s',
                       (Jsonb(row['body']), admission.sha(admission.canonical(row['body'])), row['id']))
        check = numbers.verify(self.config, self.run, self.token, request_key='ambiguous', numbers=[ref])['body']['checks'][0]
        self.assertEqual((check['status'], check['reason'], check['value']), ('unverified', 'scope_mismatch', '999'))

    def test_verify_missing_or_foreign_references_remain_unavailable(self):
        ref = self.reference(); other, token = self.create()
        denied = numbers.verify(self.config, other, token, request_key='foreign', numbers=[ref])['body']['checks'][0]
        self.assertEqual(denied['status'], 'unavailable'); self.assertIsNone(denied['value'])
        missing = numbers.verify(self.config, self.run, self.token, request_key='missing',
                                 numbers=[{**ref, 'metric': 'absent'}])['body']['checks'][0]
        self.assertEqual(missing['status'], 'unavailable')
        with self.assertRaises(ValueError):
            numbers.verify(self.config, self.run, self.token, request_key='duplicates', numbers=[ref, ref])
        with connect(self.config) as db:
            db.execute("UPDATE engine_number_checks SET body='{}'::jsonb WHERE run_id=%s", (self.run,))
        with self.assertRaises(ValueError):
            numbers.verify(self.config, self.run, self.token, request_key='missing', numbers=[{**ref, 'metric': 'absent'}])

    def test_arbitrary_agent_calculation_is_traced_but_never_certified(self):
        code = """import json
from pathlib import Path
result={'schema_version':1,'metrics':{'chosen':999},'evidence':[{'metric':'chosen','tables':['source'],'operation':'The agent says this is the total.'}],'notes':[],'series':{}}
Path('/output/result.json').write_text(json.dumps(result))
"""
        calculation = self.tool('consulta', {'code': code, 'tables': {'source': str(self.table)}, 'request_key': 'arbitrary'})
        ref = {'key': 'candidate', 'execution_id': calculation['execution_id'], 'metric': 'chosen'}
        check = numbers.verify(self.config, self.run, self.token, request_key='agent', numbers=[ref])['body']['checks'][0]
        self.assertEqual((check['status'], check['reason'], check['value']), ('unverified', 'no_server_recipe', '999'))


if __name__ == '__main__':
    unittest.main()
