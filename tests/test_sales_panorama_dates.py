"""Generic ISO date/time parsing; no customer data or real model calls."""
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import duckdb

import test_sales_panorama as base
from decision_room.sales_panorama import calculate, summarize


class PanoramaDateTests(unittest.TestCase):
    compute = base.PanoramaTests.compute

    def test_iso_variants_keep_all_rows_and_aggregate_written_day(self):
        stamps = ['2021-09-01', '2021-09-01 00:00:00', '2021-09-01T00:00:00',
                  '2021-09-01 13:45:12.123456789', '2021-09-01T23:59:59.987654Z',
                  '2021-09-01T00:15:00+02:00', '2021-09-01 23:30:00-04:00',
                  '2021-09-01T04:05:06.123+0230', '2021-09-01T04:05:06-04',
                  ' 2021-09-01 12:00:00 ']
        rows = [[s,'Notebook','Web',str(i+1)] for i,s in enumerate(stamps)]
        with patch('decision_room.sales_panorama.summarize', wraps=summarize) as summary:
            result = self.compute(rows)
        grouped = summary.call_args.args[0]
        self.assertEqual(grouped, [(date(2021,9,1),'Notebook','Web',Decimal('55'),10)])
        self.assertEqual(result['status'],'available')
        self.assertEqual(result['summary']['period'],['2021-09-01','2021-09-01'])
        self.assertEqual(result['result']['metrics']['rows'],'10')
        self.assertEqual(result['diagnostics']['invalid_rows'],0)
        self.assertEqual(result, self.compute(list(reversed(rows))))

    def test_timestamp_totals_windows_and_gaps_equal_date_only_source(self):
        rows = base.fixture()
        expected = self.compute(rows)
        for suffix in (' 00:00:00','T17:30:20.123456','T00:10:00+02:00',' 23:50:00-0500'):
            with self.subTest(suffix=suffix):
                actual = self.compute([[r[0]+suffix,*r[1:]] for r in rows])
                self.assertEqual(actual, expected)

    def test_invalid_values_have_disjoint_date_reasons_and_overlapping_row_counts(self):
        stamps = [None, '', '01/09/2021', '2021-09-01junk', '2021-09-01 24:00:00',
                  '2021-09-01T10:60:00', '2021-09-01T10:00:60',
                  '2021-09-01T10:00:00+25:00', '2021-09-01T10:00:00+02:60',
                  '2021-09-01T10:00:00Zjunk', '2021-09-01T10:00:00.',
                  '2021-02-29 00:00:00', '2021-13-01T12:00:00',
                  '0001-12-31 00:00:00', '9999-01-01T12:00:00']
        rows = [[s,'Notebook','Web','1'] for s in stamps]
        rows += [['2021-09-01','',None,'not a number'],
                 ['2021-09-01','P'*501,'C'*501,'1'],
                 ['2021-09-01','Notebook','Web','2']]
        result = self.compute(rows)
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('result',result)  # no partial total conceals the rejected rows
        self.assertEqual(result['row_count'],18)
        self.assertEqual(result['invalid_rows'],17)
        self.assertEqual(result['invalid_rows_by_rule'],dict(missing_date=2,
            invalid_date_format=9,invalid_calendar_date=2,date_out_of_range=2,
            invalid_quantity=1,missing_product=1,product_too_long=1,
            missing_channel=1,channel_too_long=1))
        self.assertEqual(set(result['validation_rules']),set(result['invalid_rows_by_rule']))
        self.assertIn('17 de 18',result['reason'])
        self.assertIn('varias reglas',result['counting_rule'])
        self.assertEqual(result,self.compute(list(reversed(rows))))

    def test_typed_parquet_dates_timestamps_and_numeric_quantities(self):
        for kind in ('DATE','TIMESTAMP','TIMESTAMP_MS','TIMESTAMP_NS','TIMESTAMPTZ'):
            with self.subTest(kind=kind), TemporaryDirectory() as folder:
                path = Path(folder)/'typed.parquet'
                with duckdb.connect() as db:
                    db.execute(f'CREATE TABLE sales(fecha {kind}, canal_id VARCHAR, producto_id VARCHAR, unidades INTEGER)')
                    # Same written date for DATE/TIMESTAMP; UTC date for typed
                    # TIMESTAMPTZ, whose source offset is not stored in parquet.
                    stamps = ['2021-09-01 00:30:00','2021-09-01 12:00:00.123456789']
                    if kind == 'TIMESTAMPTZ':
                        stamps = [stamp+'+02:00' for stamp in stamps]
                    db.execute("INSERT INTO sales VALUES (?, 'C1', 'P1', 2), (?, 'C1', 'P1', 3)", stamps)
                    db.sql('SELECT * FROM sales').write_parquet(str(path))
                value = calculate(path,['fecha','canal_id','producto_id','unidades'])
                self.assertEqual(value['status'],'available')
                self.assertEqual(Decimal(value['result']['metrics']['total']),5)
                self.assertEqual(value['result']['metrics']['rows'],'2')
                self.assertEqual(value['summary']['period'],
                                 ['2021-08-31','2021-09-01'] if kind=='TIMESTAMPTZ' else ['2021-09-01','2021-09-01'])
                self.assertIn('UTC',value['summary']['date_rule'])

    def test_leap_day_bounds_and_empty_file(self):
        rows = [['2024-02-29T12:00:00Z','P','C','1'],['0002-01-01 00:00:00','P','C','1'],
                ['9998-12-31 23:59:59','P','C','1']]
        # Avoid running cadence scans over 10,000 years: inspect parsed rows.
        with patch('decision_room.sales_panorama.summarize',return_value={}) as summary:
            result = self.compute(rows)
        self.assertEqual(result['diagnostics']['invalid_rows'],0)
        self.assertEqual([r[0] for r in summary.call_args.args[0]],
                         [date(2,1,1),date(2024,2,29),date(9998,12,31)])
        empty = self.compute([])
        self.assertEqual(empty['status'],'unavailable')
        self.assertEqual(empty['row_count'],0)
        self.assertEqual(empty['invalid_rows'],0)
        self.assertIn('no contiene filas',empty['reason'])
