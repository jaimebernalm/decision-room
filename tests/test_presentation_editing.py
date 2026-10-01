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
