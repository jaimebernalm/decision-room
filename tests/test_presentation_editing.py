"""Labels and presentation edits preserve analytical evidence and scope."""
import copy
import unittest
from unittest.mock import patch

from decision_room.web import presentation_editing as editing


class LabelTests(unittest.TestCase):
    def report(self):
        return dict(title='P01 y P010', summary='P01 registra 410 unidades en WE.',
                    highlights=[dict(key='stable', label='P01 en WE', value='410', unit='unidades')],
                    claims=[dict(title='P01', statement='P01 registra 410.', method='SUM P01')],
                    charts=[dict(title='P01', panels=[dict(coordinates=[dict(label='P01 | WE',category='P01',series='WE')],series_order=['WE'],colors={'WE':'blue'})],
                                 points=[dict(label='P01 | WE', value='410')])], limitations=['Cobertura parcial.'])

    def test_labels_preserve_values_keys_original_and_panel_alignment(self):
        original=self.report(); before=copy.deepcopy(original)
        result=editing.relabel(original,[dict(code='P01',name='Café'),dict(code='WE',name='Web propia')])
        self.assertEqual(original,before)
        self.assertEqual(result['title'],'Café y P010')
        self.assertEqual(result['highlights'][0]['key'],'stable')
        self.assertEqual(result['highlights'][0]['value'],'410')
        self.assertEqual(result['charts'][0]['points'][0]['value'],'410')
        self.assertEqual(result['charts'][0]['points'][0]['label'],result['charts'][0]['panels'][0]['coordinates'][0]['label'])
        self.assertEqual(result['highlights'][0]['original_label'],'P01 en WE')
        self.assertEqual(result['claims'][0]['method'],'SUM P01')
        self.assertEqual(result['limitations'],original['limitations'])

    def test_numeric_codes_do_not_rewrite_values_in_prose(self):
        report=self.report();report['summary']='410 unidades';report['charts'][0]['points'][0]['label']='410'
        result=editing.relabel(report,[dict(code='410',name='Producto numérico')])
        self.assertEqual(result['summary'],'410 unidades')
        self.assertEqual(result['charts'][0]['points'][0]['label'],'Producto numérico')

class CatalogTests(unittest.TestCase):
    def catalog(self, rows, *, rejected=False, duplicate_table=False, tamper=False):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock
        from dataclasses import replace
        import duckdb
        from decision_room.config import Config
        from decision_room.storage import digest
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        business='fixture-business';analysis='fixture-analysis'
        root=Path(tmp.name);path=root/business/'catalog.parquet';path.parent.mkdir()
        with duckdb.connect() as engine:
            engine.execute('CREATE TABLE catalog(k VARCHAR,name VARCHAR)')
            engine.executemany('INSERT INTO catalog VALUES (?,?)',rows)
            engine.execute('COPY catalog TO ? (FORMAT PARQUET)',[str(path)])
        table=dict(id='catalog',columns=[dict(name='k'),dict(name='name')],row_count=len(rows),parquet_key=f'{business}/catalog.parquet',parquet_sha256=digest(path))
        rel=dict(target='catalog',target_columns=['k'],verification='checked',semantic_status='rejected' if rejected else 'proposed',cardinality='many-to-one',evidence={'row_preserving':True})
        tables=[table];relations=[rel]
        if duplicate_table:
            tables.append({**table,'id':'other'});relations.append({**rel,'target':'other'})
        if tamper:path.write_bytes(b'changed')
        db=Mock();db.execute.return_value.fetchall.return_value=tables
        with patch.object(editing.knowledge,'latest',return_value=dict(revision=1,body={'relations':relations})),patch.object(editing.knowledge,'current',return_value=True):
            result=editing.catalog_labels(replace(Config.load(),storage=root),business,analysis,db)
        self.assertEqual(db.execute.call_args.args[1],(business,analysis))
        return result

    def test_complete_catalog_not_a_five_row_sample(self):
        labels=self.catalog([(f'P{i:02}',f'Nombre {i}') for i in range(1,7)])
        self.assertEqual(len(labels),6)
        self.assertEqual(labels[-1]['code'],'P06')

    def test_ambiguous_keys_codes_rejected_relations_and_changed_files(self):
        for options,rows in [({},[('P01','Uno'),('P01','Dos')]),({'duplicate_table':True},[('P01','Uno')]),({'rejected':True},[('P01','Uno')]),({'tamper':True},[('P01','Uno')])]:
            with self.subTest(options=options):self.assertEqual(self.catalog(rows,**options),[])

    def test_duplicate_names_keep_distinct_codes(self):
        labels=self.catalog([('P01','Café'),('P02','Café')])
        self.assertEqual([r['name'] for r in labels],['Café (P01)','Café (P02)'])

import test_web
from uuid import uuid4
from decision_room.database import connect
from decision_room.web.errors import WebError
from decision_room.web import home


class RevisionTests(unittest.TestCase):
    setUpClass = classmethod(test_web.WebTests.setUpClass.__func__)
    tearDownClass = classmethod(test_web.WebTests.tearDownClass.__func__)
    setUp = test_web.WebTests.setUp
    create, answer, complete, http = test_web.WebTests.create, test_web.WebTests.answer, test_web.WebTests.complete, test_web.WebTests.http

    def fixture(self):
        class HighlightModel(test_web.WebModel):
            def generate_analyst_review(self, context, correction=None):
                response, usage = super().generate_analyst_review(context, correction)
                if response.get('report'):
                    claim = response['report']['claims'][0]
                    response['report']['highlights'] = [dict(label='Total', value=claim['evidence'][0], unit='EUR', decimals=0, claim_key=claim['key'])]
                return response, usage
        self.ws.model_factory = HighlightModel
        job = self.complete()
        report = self.ws.report(job, structured=True)
        meta = report['presentation']
        return job, report, dict(business_id=str(self.business['id']), base_version=meta['base_version'],
                                revision=meta['revision'], request_key=str(uuid4()))

    def test_save_home_report_pdf_history_restore_and_idempotency(self):
        job, initial, body = self.fixture()
        change = dict(kind='metric', key=initial['highlights'][0]['key'], field='title', value='Nombre del propietario')
        body['changes'] = [change, dict(kind='report',key='title',field='title',value='Informe de mi café')]
        result = editing.save(self.ws, initial['report_id'], body)
        self.assertEqual(result['revision'], 1)
        self.assertTrue(editing.save(self.ws, initial['report_id'], body)['replayed'])
        displayed = self.ws.report(job, structured=True)
        self.assertEqual(displayed['title'], 'Informe de mi café')
        self.assertEqual(displayed['highlights'][0]['value'], initial['highlights'][0]['value'])
        self.assertEqual(home.view(self.ws)['items'][0]['title'], 'Nombre del propietario')
        self.assertEqual(displayed['report_version'], initial['report_version'])
        from decision_room.report_pdf import render_pdf
        self.assertTrue(render_pdf(displayed).startswith(b'%PDF'))
        self.assertEqual(editing.view(self.ws, initial['report_id'], 0)['title'], initial['title'])
        undo = {**body, 'request_key': str(uuid4()), 'revision': 1, 'changes': [], 'restore_revision': 0}
        restored = editing.save(self.ws, initial['report_id'], undo)
        self.assertEqual(restored['revision'], 2)
        self.assertEqual(restored['report']['title'], initial['title'])
        self.assertEqual([x['revision'] for x in restored['report']['presentation']['history']], [2,1,0])
        with self.assertRaises(WebError):
            editing.save(self.ws, initial['report_id'], {**body, 'changes':[dict(change,value='Different request')]})

    def test_stale_invalid_numeric_or_unit_edits_do_not_write(self):
        job, initial, body = self.fixture()
        metric = initial['highlights'][0]
        changes = [dict(kind='metric',key=metric['key'],field='decimals',value=2)]
        saved = editing.save(self.ws, initial['report_id'], {**body,'changes':changes})
        self.assertEqual(saved['report']['highlights'][0]['raw_value'], metric['raw_value'])
        for invalid in [dict(kind='metric',key=metric['key'],field='unit',value='kg'),
                        dict(kind='metric',key=metric['key'],field='value',value=99),
                        dict(kind='metric',key=metric['key'],field='decimals',value=True),
                        dict(kind='metric',key='alien',field='title',value='Alien'),
                        dict(kind='metric',key=metric['key'],field='decimals',value=7)]:
            with self.subTest(change=invalid), self.assertRaises(WebError):
                editing.save(self.ws, initial['report_id'], {**body,'revision':1,'request_key':str(uuid4()),'changes':[invalid]})
        with self.assertRaises(WebError):
            editing.save(self.ws, initial['report_id'], {**body,'request_key':str(uuid4()),'changes':changes})
        self.assertEqual(editing.view(self.ws, initial['report_id'])['presentation']['revision'],1)

    def test_http_auth_other_business_deleted_and_withdrawn(self):
        job, initial, body = self.fixture()
        client, server = self.http()
        path = f"/api/presentation/{initial['report_id']}"
        body['changes'] = [dict(kind='report',key='title',field='title',value='Nuevo título')]
        self.assertEqual(client.get(path).status_code,401)
        client.post('/api/login',json={'token':server.token})
        self.assertEqual(client.post(path,json=body).status_code,200)
        self.assertEqual(client.get(path+'?revision=0').status_code,200)
        self.assertEqual(client.get(path+'?revision=wrong').status_code,400)
        with connect(self.config) as db:
            db.execute('UPDATE web_jobs SET deleted_at=clock_timestamp() WHERE id=%s',(job,))
        self.assertEqual(client.get(path).status_code,409)
        with connect(self.config) as db:
            db.execute('UPDATE web_jobs SET deleted_at=NULL WHERE id=%s',(job,))
        from decision_room.agent import review
        review.hold(self.config, self.business['id'], initial['report_id'], reason='Independent test withdrawal')
        self.assertEqual(client.get(path).status_code,409)
        self.assertEqual(client.get(path+'?revision=0').status_code,409)
        self.ws.save_business({'request_key':str(uuid4()),'name':'Other','description':'Other business', 'expected_active_id':str(self.business['id'])})
        self.assertEqual(client.get(path).status_code,404)
