"""Independent scoped aggregates and visible evidence over public synthetic data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import duckdb
from psycopg.types.json import Jsonb

from decision_room.database import connect, migrate
from decision_room.engine import admission, calculations, gateway, numbers, store
from decision_room.engine.export import export_run
from decision_room.reports.verification_contract import validate
from tests import test_engine_panorama as fixtures


def recipe(key='total', operation='sum', column='amount', filters=None):
    return {'key':key, 'operation':operation, 'column':column, 'filters':filters or []}


def condition(column, operator, *values):
    return {'column':column, 'operator':operator, 'values':list(values)}


class AggregateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/'fixture.parquet'
        self.columns = ['day','group','amount']
        with duckdb.connect() as db:
            db.execute('CREATE TABLE fixture(day VARCHAR, "group" VARCHAR, amount VARCHAR)')
            db.executemany('INSERT INTO fixture VALUES (?,?,?)', [
                ('2025-01-01','A','2.5'), ('2025-01-02','A','7.5'), ('2025-01-03','B','-3'),
                ('2025-01-04','A',None), ('2025-01-05',None,'9')])
            db.execute('COPY fixture TO ?', [str(self.path)])

    def evaluate(self, *recipes): return calculations.evaluate(self.path,self.columns,list(recipes))

    def test_all_operations_filters_null_counts_and_mean_denominator(self):
        filters = [condition('group','in','A'),condition('day','date_between','2025-01-01','2025-01-04')]
        body = self.evaluate(*[recipe(operation,operation,None if operation=='count' else 'amount',filters) for operation in sorted(calculations.OPERATIONS)])
        self.assertEqual(body['metrics'], {'count':'3','max':'7.5','mean':'5','min':'2.5','sum':'10'})
        self.assertEqual(body['displays']['mean']['operands'], [
            {'label':'Filas seleccionadas','value':'3','unit':'filas'},
            {'label':'Registros no nulos usados','value':'2','unit':'registros'},
            {'label':'Suma (numerador)','value':'10','unit':'valor de la columna'}])
        self.assertIn('2025-01-04 inclusive',body['displays']['sum']['scope'])
        self.assertIn('«A»',body['displays']['sum']['scope'])
        self.assertIn('sin',body['displays']['sum']['scope'].lower())
        self.assertEqual(body['displays']['count']['operands'], [])

    def test_empty_numeric_selection_is_unavailable_but_row_count_is_zero(self):
        filters=[condition('group','in','absent')]
        body=self.evaluate(recipe(filters=filters),recipe('rows','count',None,filters))
        self.assertIsNone(body['metrics']['total']);self.assertEqual(body['issues']['total'],'no_non_null_values')
        self.assertEqual(body['metrics']['rows'],'0')
        only_null=self.evaluate(recipe(filters=[condition('day','date_between','2025-01-04','2025-01-04')]))
        self.assertIsNone(only_null['metrics']['total'])

    def test_bad_values_cannot_disappear_into_certified_aggregate(self):
        for column,value,filters,issue in [
            ('amount','NaN',[],'selected_value_not_supported_numeric'),
            ('amount','1,234',[],'selected_value_not_supported_numeric'),
            ('amount','0.0000000000001',[],'selected_value_not_supported_numeric'),
            ('amount','0'*100+'1',[],'selected_value_not_supported_numeric'),
            ('day','invalid',[condition('day','date_between','2025-01-01','2025-01-02')],'date_value_not_canonical_iso')]:
            with self.subTest(value=value), duckdb.connect() as db:
                db.execute('CREATE TABLE changed AS SELECT * FROM read_parquet(?)',[str(self.path)])
                db.execute(f'UPDATE changed SET "{column}"=?',[value])
                other=self.path.with_name('bad.parquet');db.execute('COPY changed TO ?',[str(other)])
                body=calculations.evaluate(other,self.columns,[recipe(filters=filters)])
                self.assertIsNone(body['metrics']['total']);self.assertEqual(body['issues']['total'],issue)

    def test_naive_timestamps_use_validated_calendar_day_inclusive(self):
        other=self.path.with_name('timestamps.parquet')
        with duckdb.connect() as db:
            db.execute('CREATE TABLE times(day VARCHAR, amount INTEGER)')
            db.executemany('INSERT INTO times VALUES (?,?)',[
                ('2024-02-28 23:59:59',100),('2024-02-29 00:00:00',2),
                ('2024-02-29T23:59:59.999999',3),('2024-03-01 00:00:00',100)])
            db.execute('COPY times TO ?',[str(other)])
        rules=[recipe(filters=[condition('day','date_between','2024-02-29','2024-02-29')])]
        body=calculations.evaluate(other,['day','amount'],rules)
        self.assertEqual(body['metrics']['total'],'5')
        self.assertIsNone(body['issues']['total'])
        self.assertIn('sin conversión de zona',body['displays']['total']['scope'])
        with duckdb.connect() as db:
            db.execute('CREATE TABLE typed AS SELECT CAST(day AS TIMESTAMP) AS day,amount FROM read_parquet(?)',[str(other)])
            db.execute('COPY typed TO ?',[str(other.with_name('typed.parquet'))])
        typed=calculations.evaluate(other.with_name('typed.parquet'),['day','amount'],rules)
        self.assertEqual(typed,body)

    def test_invalid_timestamp_suffix_cannot_be_certified_by_date_prefix(self):
        invalid=['2025-02-29 00:00:00','2024-02-29 24:00:00','2024-02-29 12:60:00',
                 '2024-02-29T00:00:60','2024-02-29 00:00:00 junk','2024-02-29T00:00:00Z',
                 '2024-02-29T00:00:00-05:00','2024-02-29 00:00:00.1234567',
                 '2024-02-29 00:00','20240229','2024-02-29 ']
        rules=[recipe(filters=[condition('day','date_between','2024-02-29','2024-02-29')])]
        for i,value in enumerate(invalid):
            with self.subTest(value=value),duckdb.connect() as db:
                other=self.path.with_name(f'invalid-{i}.parquet')
                db.execute('CREATE TABLE invalid AS SELECT ? AS day, 2 AS amount',[value])
                db.execute('COPY invalid TO ?',[str(other)])
                body=calculations.evaluate(other,['day','amount'],rules)
                self.assertIsNone(body['metrics']['total'])
                self.assertEqual(body['issues']['total'],'date_value_not_canonical_iso')

    def test_bounds_and_unknown_fields_reject_instead_of_truncate(self):
        for bound,value in [('MAX_ROWS',4),('MAX_FILE_BYTES',1),('SECONDS',0)]:
            with self.subTest(bound=bound),patch.object(calculations,bound,value),self.assertRaises((ValueError,duckdb.Error)):
                self.evaluate(recipe())
        invalid=[{**recipe(),'sql':'SELECT 1'},recipe(column='amount; DROP TABLE x'),recipe(operation='median'),
                 recipe(operation='count'),recipe(filters=[condition('day','date_between','2025-02-02','2025-01-01')]),
                 recipe(filters=[condition('day','date_between','20250101','20250102')]),
                 recipe(filters=[condition('group','sql','A')])]
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ValueError):self.evaluate(value)
        with self.assertRaises(ValueError):self.evaluate(recipe(),recipe())
        with self.assertRaises(ValueError):
            self.evaluate(recipe(filters=[condition('group','in',*['x'*490+str(i) for i in range(16)])]))

    def test_literals_and_quoted_column_names_are_data_not_sql(self):
        with duckdb.connect() as db:
            name='value"; SELECT 9; --'
            db.execute('CREATE TABLE fixture("'+name.replace('"','""')+'" VARCHAR)')
            db.execute('INSERT INTO fixture VALUES (?)',['3.25'])
            other=self.path.with_name('quoted.parquet');db.execute('COPY fixture TO ?',[str(other)])
        body=calculations.evaluate(other,[name],[recipe(column=name,filters=[condition(name,'in','3.25')])])
        self.assertEqual(body['metrics']['total'],'3.25')
        self.assertIn(name,body['displays']['total']['scope'])
        self.assertEqual(self.evaluate(recipe(filters=[condition('group','in',"A' OR 1=1 --")]))['metrics']['total'],None)


class CalculationIntegrationTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PanoramaTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PanoramaTests.tearDownClass.__func__)
    setUp=fixtures.PanoramaTests.setUp
    create=fixtures.PanoramaTests.create
    tool=fixtures.PanoramaTests.tool

    def calc(self,**changes):
        return calculations.calculate(self.config,self.run,self.token,**{
            'table_id':self.table,'request_key':'sum','recipes':[recipe(column='quantity')],**changes})

    def test_mcp_paged_result_recalculation_and_both_exports_certify_only_fact(self):
        call=self.tool('calculo',{'table_id':str(self.table),'request_key':'mcp','recipes':[recipe(column='quantity')]})
        ref={'key':'total','metric':'total','execution_id':call['execution_id']}
        result=self.tool('resultado',{'execution_id':ref['execution_id']})
        self.assertEqual(result['origin'],'deterministic_calculation')
        checked=numbers.verify(self.config,self.run,self.token,request_key='verify',numbers=[ref])['body']['checks'][0]
        self.assertEqual((checked['status'],checked['value']),('verified_in_scope','15'))
        raw=json.dumps({'schema_version':1,'title':'Total','summary':'La suma es 15.',
                       'numbers':[ref],'findings':[{'key':'review','title':'Revisar registros','facts':['total']}]}).encode()
        store.receive_document(self.config,self.run,self.token,request_key='draft',draft_json=raw)
        target=self.root/'export';export_run(self.config,self.business,self.run,target)
        doc=json.loads((target/'draft.verified.json').read_text());ledger=json.loads((target/'verification.json').read_text())
        validate(ledger,doc,raw)
        self.assertEqual([f['value'] for f in ledger['figures'] if f['verified']],['15.00','4','4'])
        self.assertFalse(next(f for f in ledger['figures'] if f['path']=='/summary')['verified'])
        self.assertIn('Suma registrada', (target/'informe.contenido.html').read_text())
        self.assertIn('sales.csv', (target/'informe.contenido.html').read_text())
        self.assertEqual((target/'draft.raw').read_bytes(),raw)

    def test_calculation_continuation_reads_same_scoped_result_without_repeating_recipes(self):
        first = self.tool('calculo', {'table_id': str(self.table), 'request_key': 'many-recipes',
                                     'recipes': [recipe(key=f'total_{i}', column='quantity') for i in range(16)]})
        page = first; rows = list(page['rows'])
        self.assertIsNotNone(page['next_call'])
        while page['next_call']:
            call = page['next_call']
            self.assertEqual(call['name'], 'resultado')
            self.assertFalse(call['reuse_previous_arguments'])
            self.assertEqual(call['arguments']['execution_id'], first['execution_id'])
            page = self.tool(call['name'], call['arguments'])
            self.assertEqual(page['result_sha256'], first['result_sha256'])
            rows.extend(page['rows'])
        self.assertEqual(len(rows), first['total_rows'])
        self.assertEqual(len({(r['path'], r['part']) for r in rows}), len(rows))
        self.assertEqual(len([r for r in rows if r['path'].startswith('/metrics/')]), 16)

    def test_concurrent_idempotency_evaluates_once_and_changed_recipe_rejects(self):
        barrier=threading.Barrier(2);actual=calculations.evaluate
        def submit(_):barrier.wait();return self.calc()
        with patch.object(calculations,'evaluate',wraps=actual) as evaluate,ThreadPoolExecutor(2) as pool:
            rows=list(pool.map(submit,range(2)))
        self.assertEqual(rows[0],rows[1]);self.assertEqual(evaluate.call_count,1)
        with self.assertRaises(ValueError):self.calc(recipes=[recipe(operation='max',column='quantity')])
        self.assertEqual(self.calc()['id'],rows[0]['id'])

    def test_other_job_business_or_changed_snapshot_cannot_use_observation(self):
        row=self.calc();other,token=self.create()
        ref={'key':'v','metric':'total','execution_id':str(row['id'])}
        checked=numbers.verify(self.config,other,token,request_key='foreign',numbers=[ref])['body']['checks'][0]
        self.assertEqual(checked['status'],'unavailable')
        with self.assertRaises(admission.Denied):self.tool('resultado',{'execution_id':str(row['id'])},run=other,token=token)
        self.assertIsNone(calculations.observation(self.config,uuid4(),self.run,row['id']))
        with self.assertRaises(admission.Denied):self.calc(table_id=str(uuid4()))
        with connect(self.config) as db:db.execute('UPDATE prepared_tables SET parquet_sha256=%s WHERE id=%s',('0'*64,self.table))
        with self.assertRaises(admission.Denied):self.calc()

    def test_final_check_recomputes_and_corrects_saved_value_but_rejects_changed_scope(self):
        row=self.calc();body=row['body'];body['result']['metrics']['total']='999'
        def persist():
            with connect(self.config) as db:db.execute('UPDATE engine_calculations SET body=%s,body_sha256=%s WHERE id=%s',
                (Jsonb(body),admission.sha(admission.canonical(body)),row['id']))
        persist();ref={'key':'v','metric':'total','execution_id':str(row['id'])}
        job=admission.authenticate(self.config,self.run,self.token)
        checked=numbers._check(self.config,job,ref,{})
        self.assertEqual((checked['status'],checked['value'],checked['original_value']),('corrected_in_scope','15','999'))
        body['result']['displays']['total']['scope']='A different group';persist()
        self.assertEqual(numbers._check(self.config,job,ref,{})['status'],'unavailable')

    def test_changed_recipe_version_or_corrupt_body_is_never_recertified(self):
        row=self.calc();ref={'key':'v','metric':'total','execution_id':str(row['id'])}
        job=admission.authenticate(self.config,self.run,self.token)
        with patch.object(calculations,'identity',return_value={'version':'new'}):
            self.assertEqual(numbers._check(self.config,job,ref,{})['status'],'unavailable')
        with connect(self.config) as db:db.execute('UPDATE engine_calculations SET body_sha256=%s WHERE id=%s',('0'*64,row['id']))
        with self.assertRaises(ValueError):numbers._check(self.config,job,ref,{})

    def test_late_calculation_cannot_persist_after_pause_and_migration_is_idempotent(self):
        actual=calculations.evaluate
        def pause(*args):
            result=actual(*args)
            with connect(self.config) as db:db.execute("UPDATE engine_runs SET status='pausing' WHERE id=%s",(self.run,))
            return result
        with patch.object(calculations,'evaluate',side_effect=pause),self.assertRaises(admission.Denied):self.calc()
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM engine_calculations WHERE run_id=%s',(self.run,)).fetchone()['n'],0)
        migrate(self.config);migrate(self.config)
        with connect(self.config) as db:
            self.assertEqual(db.execute('SELECT count(*) n FROM schema_versions WHERE version=37').fetchone()['n'],1)


if __name__=='__main__':unittest.main()
