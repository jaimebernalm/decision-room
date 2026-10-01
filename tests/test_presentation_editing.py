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
    def catalog(self, rows, *, rejected=False, duplicate_table=False, tamper=False, numeric_keys=False):
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
            engine.execute('CREATE TABLE catalog(k BIGINT,name VARCHAR)' if numeric_keys else 'CREATE TABLE catalog(k VARCHAR,name VARCHAR)')
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

    def test_numeric_catalog_keys_include_zero_without_rewriting_quantities(self):
        labels=self.catalog([(0,'Cero'),(1,'Uno')],numeric_keys=True)
        self.assertEqual([r['code'] for r in labels],['0','1'])
        report=LabelTests().report();report['summary']='0 unidades';report['charts'][0]['points'][0]['label']='0'
        renamed=editing.relabel(report,labels)
        self.assertEqual(renamed['summary'],'0 unidades')
        self.assertEqual(renamed['charts'][0]['points'][0]['label'],'Cero')

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

    def fixture(self, unit='EUR'):
        class HighlightModel(test_web.WebModel):
            def generate_analyst_review(self, context, correction=None):
                response, usage = super().generate_analyst_review(context, correction)
                if response.get('report'):
                    claim = response['report']['claims'][0]
                    response['report']['highlights'] = [dict(label='Total', value=claim['evidence'][0], unit=unit, decimals=0, claim_key=claim['key'])]
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
        self.assertIn('Informe de mi café', self.ws.report(job))
        self.assertIn('Nombre del propietario', self.ws.report(job))
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

    def test_owner_clarifies_unspecified_unit_and_can_restore_without_conversion(self):
        from io import BytesIO
        from pypdf import PdfReader
        from decision_room.report_pdf import render_pdf
        original_unit='unidades registradas (unidad no especificada)'
        job,initial,body=self.fixture(original_unit)
        metric=initial['highlights'][0]
        self.assertTrue(metric['unit_customizable'])
        for revision,label in enumerate(['unidades registradas (paquete)','unidades registradas (bolsa)']):
            saved=editing.save(self.ws,initial['report_id'],{**body,'revision':revision,'request_key':str(uuid4()),
                'changes':[dict(kind='metric',key=metric['key'],field='unit',value=label)]})
            displayed=self.ws.report(job,structured=True)
            value=displayed['highlights'][0]
            self.assertEqual((value['raw_value'],value['value']),(metric['raw_value'],metric['value']))
            self.assertEqual(value['unit'],label)
            self.assertEqual(value['unit_origin'],'owner')
            self.assertEqual(value['original_unit'],original_unit)
            self.assertEqual(displayed['report_version'],initial['report_version'])
            self.assertEqual(home.view(self.ws)['items'][0]['content']['unit'],label)
            self.assertIn(label,self.ws.report(job))
            text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(displayed))).pages)
            self.assertIn(label,text)
            self.assertIn(original_unit,text)
        restored=editing.save(self.ws,initial['report_id'],{**body,'revision':2,'request_key':str(uuid4()),'restore_revision':0})
        self.assertEqual(restored['report']['highlights'][0]['unit'],original_unit)
        self.assertEqual(restored['report']['highlights'][0]['unit_origin'],'analysis')

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

    def test_simultaneous_writers_cannot_overwrite_each_other(self):
        from concurrent.futures import ThreadPoolExecutor
        job,report,body=self.fixture()
        def write(title):
            try:
                return editing.save(self.ws,report['report_id'],{**body,'request_key':str(uuid4()),'changes':[dict(kind='report',key='title',field='title',value=title)]})['revision']
            except WebError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(write,['Primera sesión','Segunda sesión']))
        self.assertCountEqual(statuses,[1,409])
        self.assertEqual(editing.view(self.ws,report['report_id'])['presentation']['revision'],1)

    def test_concurrent_report_readers_share_lock_but_writer_is_exclusive(self):
        from decision_room.web.report_access import read_lock
        from decision_room.agent.persistence import session_lock
        job,report,_=self.fixture()
        session=self.ws.row(job)['session_id']
        with read_lock(self.config,self.business['id'],session), read_lock(self.config,self.business['id'],session):
            self.assertEqual(self.ws.report(job,structured=True)['report_version'],report['report_version'])
            with self.assertRaises(ValueError):
                with session_lock(self.config,self.business['id'],session):
                    pass
        with session_lock(self.config,self.business['id'],session):
            with self.assertRaises(WebError) as issue:
                self.ws.report(job,structured=True)
            self.assertEqual(issue.exception.status,409)

    def test_html_export_escapes_owner_text_and_keeps_exact_values(self):
        from decision_room.web.dashboard import presentation
        from decision_room.web.presentation_html import render
        from test_client_report import sample
        report=presentation(sample())
        report['title']='<script>alert(1)</script>'
        report['claims'][0]['statement']='<img src=x onerror=alert(1)>'
        html=render(report,'Now')
        self.assertNotIn('<script>',html)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;script&gt;',html)
        self.assertIn('20,01',html)
        self.assertIn('No conocemos costes',html)
        report['charts'][0].update(kind='bar',panels=[],points=[dict(label='Café <grande>',value='20.005',formatted='20,01')])
        html=render(report,'Now')
        self.assertIn('<svg',html)
        self.assertIn('Café &lt;grande&gt;',html)
        self.assertIn('20,01',html)
