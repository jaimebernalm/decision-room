"""Integration tests use a disposable PostgreSQL database and temporary files."""
import json
import tempfile
import unittest
import uuid
from dataclasses import replace
from pathlib import Path

import duckdb
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.service import create_business, describe, import_batch, resume
from decision_room.storage import Storage


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Config.load()
        cls.database = 'dr_test_' + uuid.uuid4().hex
        with connect(cls.base) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(cls.database)))
        cls.dsn = make_conninfo(cls.base.dsn, dbname=cls.database)
        migrate(replace(cls.base, dsn=cls.dsn))

    @classmethod
    def tearDownClass(cls):
        with connect(cls.base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(cls.database)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='decision-room-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = replace(self.base, dsn=self.dsn, storage=self.root / 'storage')
        self.business = create_business(self.config, 'Test business')['id']

    def csv(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8', newline='')
        return path

    def parquet(self, report):
        file = report['files'][0]
        return Storage(self.config.storage).path(self.business, file['parquet_key'])

    def test_lossless_values_nulls_empty_text_and_duplicates(self):
        path = self.csv('edge.csv', '\ufeffcode,amount,date,note\r\n'
                        '"001","-12.3400","9999-12-31 23:59:59.9999999",""\r\n'
                        '"002","0","2016-04-01",\r\n'
                        '"003","4.20","2016-04-02","café, \'quoted\'\nsecond line"\r\n'
                        '"003","4.20","2016-04-02","café, \'quoted\'\nsecond line"\r\n')
        result = import_batch(self.config, self.business, [path])
        self.assertEqual(result['analysis']['status'], 'ready', result)
        with duckdb.connect() as db:
            data = db.read_parquet(str(self.parquet(result))).order('__dr_source_record').fetchall()
        self.assertEqual(data, [(1, '001', '-12.3400', '9999-12-31 23:59:59.9999999', ''),
                                (2, '002', '0', '2016-04-01', None),
                                (3, '003', '4.20', '2016-04-02', "café, 'quoted'\nsecond line"),
                                (4, '003', '4.20', '2016-04-02', "café, 'quoted'\nsecond line")])
        details = describe(self.config, self.business, result['analysis']['id'], True)
        self.assertEqual(details['files'][0]['columns'][3]['null_count'], 1)
        self.assertEqual(details['files'][0]['columns'][3]['empty_string_count'], 1)

    def test_header_only_table_is_not_dropped(self):
        result = import_batch(self.config, self.business, [self.csv('empty.csv', 'id,name\n')])
        self.assertEqual((result['analysis']['status'], result['table_count'], result['total_rows']), ('ready', 1, 0))

    def test_repeated_batch_and_file_aliases(self):
        a = self.csv('first.csv', 'id,value\n001,5\n')
        b = self.csv('alias.csv', 'id,value\n001,5\n')
        first = import_batch(self.config, self.business, [a, b])
        second = import_batch(self.config, self.business, [b, a])
        self.assertEqual(first['analysis']['id'], second['analysis']['id'])
        self.assertTrue(second['reused_batch'])
        self.assertEqual(second['duplicate_inputs'], 1)
        self.assertEqual(second['total_rows'], 1)
        self.assertEqual(set(second['files'][0]['original_names']), {'first.csv', 'alias.csv'})

    def test_bad_file_does_not_discard_valid_table(self):
        good = self.csv('good.csv', 'id,value\n001,5\n')
        bad = self.csv('bad.csv', 'id,value\n001,5,extra\n')
        result = import_batch(self.config, self.business, [good, bad])
        self.assertEqual(result['analysis']['status'], 'partial')
        self.assertEqual(result['table_count'], 1)
        failure = next(f for f in result['files'] if f['status'] == 'failed')
        self.assertIsNotNone(failure['issue'])
        self.assertTrue(Storage(self.config.storage).path(self.business, failure['original_key']).exists())

    def test_resume_after_interruption_without_original_upload_paths(self):
        a = self.csv('a.csv', 'id,value\n001,5\n')
        b = self.csv('b.csv', 'id,value\n002,6\n')

        def interrupt(*args):
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            import_batch(self.config, self.business, [a, b], progress=interrupt)
        a.unlink()
        b.unlink()
        with connect(self.config) as db:
            analysis = db.execute('SELECT id FROM analyses WHERE business_id=%s', (self.business,)).fetchone()['id']
        before = describe(self.config, self.business, analysis)
        self.assertEqual(before['analysis']['status'], 'importing')
        self.assertEqual(before['table_count'], 1)
        result = resume(self.config, self.business, analysis)
        self.assertEqual((result['analysis']['status'], result['table_count'], result['total_rows']), ('ready', 2, 2))

    def test_missing_parquet_rebuilt_and_corrupt_original_rejected(self):
        path = self.csv('data.csv', 'id,value\n001,5\n')
        first = import_batch(self.config, self.business, [path])
        self.parquet(first).unlink()
        rebuilt = resume(self.config, self.business, first['analysis']['id'])
        self.assertEqual(rebuilt['analysis']['status'], 'ready')
        source = Storage(self.config.storage).path(self.business, rebuilt['files'][0]['original_key'])
        source.chmod(0o600)
        source.write_text('corrupted')
        broken = resume(self.config, self.business, first['analysis']['id'])
        self.assertEqual(broken['analysis']['status'], 'failed')
        self.assertEqual(broken['table_count'], 0)

    def test_business_scoping_in_service_files_and_database(self):
        a = self.csv('data.csv', 'id,value\n001,5\n')
        first = import_batch(self.config, self.business, [a])
        other = create_business(self.config, 'Other business')['id']
        with self.assertRaises(ValueError):
            describe(self.config, other, first['analysis']['id'])
        with self.assertRaises(ValueError):
            resume(self.config, other, first['analysis']['id'])
        with self.assertRaises(ValueError):
            Storage(self.config.storage).path(other, first['files'][0]['original_key'])
        with self.assertRaises(ValueError):
            Storage(self.config.storage).path(other, f'{other}/../../escape')
        with connect(self.config) as db:
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                db.execute('UPDATE sources SET business_id=%s WHERE id=%s', (other, first['files'][0]['source_id']))
        second = import_batch(self.config, other, [a])
        self.assertNotEqual(first['analysis']['id'], second['analysis']['id'])
        self.assertNotEqual(first['files'][0]['original_key'], second['files'][0]['original_key'])

    def test_same_name_changed_content_is_separate_analysis(self):
        a = self.csv('sales.csv', 'id,value\n001,5\n')
        first = import_batch(self.config, self.business, [a])
        a.write_text('id,value\n001,8\n')
        second = import_batch(self.config, self.business, [a])
        self.assertNotEqual(first['analysis']['id'], second['analysis']['id'])
        self.assertEqual(describe(self.config, self.business, first['analysis']['id'])['total_rows'], 1)

    def test_headers_dialect_and_reserved_lineage(self):
        good = self.csv('semi.csv', '__dr_source_record;SKU;value\n7;001;12,34\n')
        result = import_batch(self.config, self.business, [good])
        self.assertEqual(result['analysis']['status'], 'ready', result)
        self.assertNotEqual(result['files'][0]['lineage_column'], '__dr_source_record')
        bad = self.csv('duplicate.csv', 'SKU,sku\n001,002\n')
        result = import_batch(self.config, self.business, [bad])
        self.assertEqual(result['analysis']['status'], 'failed')

    def test_empty_invalid_encoding_and_limits(self):
        empty = self.csv('empty.csv', '')
        self.assertEqual(import_batch(self.config, self.business, [empty])['analysis']['status'], 'failed')
        bad = self.csv('encoding.csv', 'id\n')
        bad.write_bytes(b'id\n\xff\n')
        self.assertEqual(import_batch(self.config, self.business, [bad])['analysis']['status'], 'failed')
        large = self.csv('large.csv', 'id\n123456789\n')
        with self.assertRaises(ValueError):
            import_batch(replace(self.config, max_file_bytes=5), self.business, [large])
        limited = import_batch(replace(self.config, max_rows=1), self.business,
                               [self.csv('rows.csv', 'id\n1\n2\n')])
        self.assertEqual(limited['analysis']['status'], 'failed')

    def test_existing_reference_cases_and_variants(self):
        base = Path(__file__).resolve().parents[1] / 'data/reference-cases'
        for case, count in [('01-daily-sales',24), ('02-product-sales',116), ('03-ambiguous-amount',12)]:
            for variant in ['input/sales.csv', 'variants/renamed-columns/sales.csv']:
                with self.subTest(case=case, variant=variant):
                    result = import_batch(self.config, self.business, [base / case / variant])
                    self.assertEqual(result['analysis']['status'], 'ready')
                    self.assertEqual(result['total_rows'], count)
                    self.assertIsNone(result['files'][0]['issue'])


if __name__ == '__main__':
    unittest.main()
