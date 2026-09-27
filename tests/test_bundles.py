"""Folder transfer, worksheet preparation and dataset reuse over the local HTTP API."""
import io
import json
import unittest
from uuid import uuid4

import duckdb
from openpyxl import Workbook

from test_web import WebTests as Fixture
from decision_room.database import connect
from decision_room.storage import Storage
from decision_room.web import bundles, dossier


class BundleTests(unittest.TestCase):
    setUpClass = classmethod(Fixture.setUpClass.__func__)
    tearDownClass = classmethod(Fixture.tearDownClass.__func__)
    setUp = Fixture.setUp
    http = Fixture.http

    def workbook(self):
        book = Workbook()
        first = book.active
        first.title = 'Productos'
        first.append(['sku', 'precio'])
        first.append(['001', 12.5])
        second = book.create_sheet('Existencias')
        second.append(['sku', 'unidades'])
        second.append(['001', 4])
        stream = io.BytesIO()
        book.save(stream)
        return stream.getvalue()

    def test_folder_csv_excel_resume_originals_and_report_job(self):
        client, _ = self.http()
        self.assertEqual(client.post('/api/login', json={'token': 'test-local-access'}).status_code, 200)
        raw = [
            ('tienda/ventas.csv', b'id,importe\n1,20\n'),
            ('tienda/sub/otras.csv', b'id,importe\n2,30\n'),
            ('tienda/catalogo.xlsx', self.workbook()),
        ]
        request_key = str(uuid4())
        payload = dict(business_id=str(self.business['id']), request_key=request_key,
                       title='Carpeta de prueba', mode='separate',
                       files=[dict(path=name, size=len(content)) for name, content in raw])
        started = client.post('/api/datasets/bundles', json=payload)
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()['files'][0]['path'], 'tienda/catalogo.xlsx')
        listed = sorted(raw)
        for index, (_, content) in enumerate(listed):
            first = content[:5]
            url = f'/api/datasets/bundles/{request_key}/files/{index}'
            headers = {'Content-Type': 'application/octet-stream', 'X-Upload-Offset': '0'}
            self.assertEqual(client.post(url, content=first, headers=headers).status_code, 200)
            self.assertEqual(client.post(url, content=first, headers=headers).status_code, 200)
            self.assertEqual(client.get(f'/api/datasets/bundles/{request_key}').json()['files'][index]['uploaded'], len(first))
            self.assertEqual(client.post(url, content=content[5:],
                                         headers={**headers, 'X-Upload-Offset': str(len(first))}).status_code, 200)
        completed = client.post(f'/api/datasets/bundles/{request_key}/finish', json={})
        self.assertEqual(completed.status_code, 200, completed.text)
        result = completed.json()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(client.post(f'/api/datasets/bundles/{request_key}/finish', json={}).json(), result)
        data = dossier.listing(self.ws)
        self.assertEqual(len(data['datasets']), 1)
        self.assertEqual(len(data['datasets'][0]['original_files']), 3)
        self.assertEqual(len(data['datasets'][0]['files']), 4)
        self.assertEqual(sum(f['rows'] for f in data['datasets'][0]['files']), 4)
        original = client.get(f'/api/datasets/original/{result["analysis_id"]}', params={'path': 'tienda/catalogo.xlsx'})
        self.assertEqual(original.content, raw[-1][1])
        with connect(self.config) as db:
            rows = db.execute('''SELECT s.original_names,p.parquet_key FROM sources s JOIN prepared_tables p ON p.source_id=s.id
                WHERE s.business_id=%s AND s.analysis_id=%s''', (self.business['id'], result['analysis_id'])).fetchall()
        product = next(r for r in rows if 'Productos' in r['original_names'][0])
        parquet = Storage(self.config.storage).path(self.business['id'], product['parquet_key'])
        with duckdb.connect() as db:
            self.assertEqual(db.read_parquet(str(parquet)).project('sku,precio').fetchall(), [('001', '12.5')])
        job = client.post('/api/jobs/from-dataset', json=dict(business_id=str(self.business['id']),
            profile_revision=1, request_key=request_key, analysis_id=result['analysis_id'],
            title='Informe de carpeta', goal='Ventas y existencias'))
        self.assertEqual(job.status_code, 202, job.text)
        self.assertEqual(client.post('/api/jobs/from-dataset', json=dict(business_id=str(self.business['id']),
            profile_revision=1, request_key=request_key, analysis_id=result['analysis_id'],
            title='Informe de carpeta', goal='Ventas y existencias')).json(), job.json())

    def test_total_size_and_paths_are_checked_before_upload(self):
        from dataclasses import replace
        from decision_room.web.errors import WebError
        self.ws.config = replace(self.config, max_batch_bytes=10)
        common = dict(business_id=str(self.business['id']), request_key=str(uuid4()), title='Test', mode='separate')
        with self.assertRaises(WebError):
            bundles.start(self.ws, {**common, 'files': [{'path': 'a.csv', 'size': 6}, {'path': 'b.xlsx', 'size': 5}]})
        with self.assertRaises(WebError):
            bundles.start(self.ws, {**common, 'files': [{'path': '../escape.csv', 'size': 1}]})
        with self.assertRaises(WebError):
            bundles.start(self.ws, {**common, 'files': [{'path': 'a.csv', 'size': 1}, {'path': 'A.csv', 'size': 1}]})

    def test_unreadable_excel_keeps_valid_csv_available(self):
        raw = [('ventas.csv', b'id,total\n1,20\n'), ('roto.xlsx', b'not an Excel workbook')]
        key = str(uuid4())
        data = dict(business_id=str(self.business['id']), request_key=key, title='Mi carpeta',
                    mode='separate', files=[dict(path=name, size=len(content)) for name, content in raw])
        bundles.start(self.ws, data)
        for index, (name, content) in enumerate(sorted(raw)):
            bundles.chunk(self.ws, key, index, 0, content)
        result = bundles.finish(self.ws, key)
        self.assertEqual(result['status'], 'partial')
        dataset = dossier.listing(self.ws)['datasets'][0]
        self.assertEqual([file['status'] for file in dataset['files']].count('ready'), 1)
        self.assertEqual([file['status'] for file in dataset['files']].count('failed'), 1)
        with connect(self.config) as db:
            self.assertTrue(dossier.available(db, self.business['id'], result['analysis_id']))
        job = self.ws.create_from_dataset(dict(business_id=str(self.business['id']),
            profile_revision=1, request_key=str(uuid4()), analysis_id=result['analysis_id'],
            title='Informe parcial', goal='Ventas'))
        self.assertIn('id', job)


if __name__ == '__main__':
    unittest.main()


del Fixture
