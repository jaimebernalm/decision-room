"""Large real imports, bounded reads, search and integrity-cache invalidation."""
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from decision_room.database import connect
from decision_room.storage import digest
from decision_room.web import dossier, preview
from decision_room.web.errors import WebError
from test_web import WebTests as Fixture


class LargePreviewTests(unittest.TestCase):
    setUpClass = classmethod(Fixture.setUpClass.__func__)
    tearDownClass = classmethod(Fixture.tearDownClass.__func__)
    setUp = Fixture.setUp

    def upload(self, raw=None, path=None):
        data = dict(business_id=str(self.business['id']), request_key=str(uuid4()), title='Public synthetic table', mode='separate')
        if path:
            dossier.upload_paths(self.ws, data, [path])
        else:
            dossier.upload(self.ws, data, 'synthetic.csv', raw)
        return str(dossier.listing(self.ws)['datasets'][0]['files'][0]['id'])

    def test_million_rows_random_access_and_warm_integrity_check(self):
        path = Path(self.temp.name) / 'synthetic.csv'
        with path.open('w') as stream:
            stream.write('id,product,category,amount,note\n')
            for n in range(1_000_000):
                stream.write(f'{n},product-{n % 1000},category-{n % 12},{n % 500},Synthetic reference row {n}\n')
        source = self.upload(path=path)
        preview._VERIFIED.clear()
        durations = []
        with patch.object(preview, 'digest', wraps=digest) as hashing:
            for offset in (0, 500_000, 999_950, 50, 999_999):
                started = time.perf_counter()
                result = preview.source_page(self.ws, source, {'offset': [str(offset)]})
                durations.append(round((time.perf_counter() - started) * 1000, 2))
                self.assertLessEqual(len(result['rows']), 50)
                self.assertEqual(result['rows'][0]['number'], offset + 1)
                self.assertEqual(result['rows'][0]['values'][0], str(offset))
                self.assertEqual(result['tables'][0]['row_count'], 1_000_000)
            self.assertEqual(hashing.call_count, 1)
            searched = time.perf_counter()
            result = preview.source_page(self.ws, source, {'q': ['product-999'], 'filter_column': ['category'], 'filter_op': ['equals'], 'filter_value': ['category-3']})
            self.assertTrue(all(r['values'][1] == 'product-999' and r['values'][2] == 'category-3' for r in result['rows']))
            next_page = preview.source_page(self.ws, source, {'q': ['product-999'], 'filter_column': ['category'], 'filter_op': ['equals'], 'filter_value': ['category-3'], 'after': [str(result['next_after'])]})
            self.assertGreater(next_page['rows'][0]['number'], result['rows'][-1]['number'])
            self.assertFalse({r['number'] for r in result['rows']} & {r['number'] for r in next_page['rows']})
            self.assertEqual(hashing.call_count, 1)
            search_ms = round((time.perf_counter() - searched) * 1000, 2)
        print(f'CSV bytes: {path.stat().st_size}; search plus continuation milliseconds: {search_ms}', flush=True)
        print(f'\n1,000,000-row real import; preview milliseconds cold/middle/last/next/final: {durations}', flush=True)

    def test_search_filter_cursor_literals_nulls_and_invalid_inputs(self):
        raw = ('id,name,category\n' + '\n'.join(f'{n},Cuaderno,{n % 2}' for n in range(120)) + '\n120,100%_real,\n121,"",other\n122,,other\n123,"O\'Reilly",other\n').encode()
        source = self.upload(raw)
        def read(**query):
            return preview.source_page(self.ws, source, {k: [str(v)] for k, v in query.items()})
        first = read(q='CUADERNO', filter_column='category', filter_op='equals', filter_value='1')
        self.assertEqual(len(first['rows']), 50)
        self.assertTrue(first['has_more'])
        last = read(q='CUADERNO', filter_column='category', filter_op='equals', filter_value='1', after=first['next_after'])
        self.assertEqual(len(last['rows']), 10)
        self.assertFalse(last['has_more'])
        self.assertEqual(read(q='%_')['rows'][0]['values'][1], '100%_real')
        self.assertEqual(read(filter_column='name', filter_op='empty')['rows'][0]['number'], 122)
        self.assertEqual(len(read(filter_column='name', filter_op='empty')['rows']), 2)
        self.assertEqual(len(read(filter_column='name', filter_op='equals', filter_value="O'Reilly")['rows']), 1)
        self.assertEqual(read(q="' OR 1=1 --")['rows'], [])
        self.assertEqual(read(q='missing')['rows'], [])
        for params in [dict(q='x' * 201), dict(filter_column='wrong'), dict(filter_op='injected'), dict(after=-1), dict(after='bad'), dict(after=999), dict(q='x', offset=50), dict(filter_column='name', filter_value='x' * 201)]:
            with self.assertRaises(WebError):
                read(**params)

    def test_cached_file_verification_detects_modified_and_replaced_files(self):
        source = self.upload(b'id,name\n1,Cuaderno\n')
        preview._VERIFIED.clear()
        with connect(self.config) as db:
            row = db.execute('SELECT parquet_key,parquet_sha256 FROM prepared_tables WHERE business_id=%s', (self.business['id'],)).fetchone()
        path = self.config.storage / row['parquet_key']
        original = path.read_bytes()
        stamp = path.stat()
        with patch.object(preview, 'digest', wraps=digest) as hashing:
            preview.source_page(self.ws, source, {})
            preview.source_page(self.ws, source, {})
            self.assertEqual(hashing.call_count, 1)
            path.chmod(0o600)
            changed = bytearray(original)
            changed[8] ^= 1
            path.write_bytes(changed)
            os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaises(WebError) as caught:
                preview.source_page(self.ws, source, {})
            self.assertEqual(caught.exception.status, 409)
            replacement = path.with_suffix('.replacement')
            replacement.write_bytes(original)
            replacement.replace(path)
            preview.source_page(self.ws, source, {})
            self.assertEqual(hashing.call_count, 3)
            with connect(self.config) as db:
                db.execute('UPDATE prepared_tables SET parquet_sha256=%s WHERE business_id=%s', ('0' * 64, self.business['id']))
            with self.assertRaises(WebError):
                preview.source_page(self.ws, source, {})
        self.assertLessEqual(len(preview._VERIFIED), preview._VERIFY_LIMIT)
