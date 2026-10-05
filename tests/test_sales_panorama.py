"""P1a arithmetic, calendars, absences and traceability on generic synthetic rows."""
import csv
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
from unittest.mock import patch

from decision_room.config import Config
from decision_room.csv_ingest import prepare
from decision_room.sales_panorama import calculate, period_rule, record_gaps
from decision_room.sales_panorama_store import review_snapshot
from decision_room.series import evidence_value
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.agent.sales_panorama import SYSTEM
from test_model_strict_schemas import assert_strict_objects
import test_model_strict_schemas as strict


def dates(start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    return [start+timedelta(days=i) for i in range((end-start).days+1)]


def fixture():
    rows = []
    for d in dates('2025-01-01','2025-06-30'):
        for product, channel in [('Cuaderno','Web'), ('Lápiz','Local')]:
            if channel == 'Local' and date(2025,5,5) <= d <= date(2025,5,18):
                continue
            quantity = (10 if d.month <= 3 else 15) if channel == 'Web' else (8 if d.month <= 3 else 6)
            rows.append([d.isoformat(), product, channel, str(quantity)])
    return rows


class PanoramaTests(unittest.TestCase):
    def compute(self, rows, header=None, mapping=None):
        header = header or ['date','product','channel','quantity']
        with TemporaryDirectory() as folder:
            path = Path(folder)/'input.csv'; parquet = Path(folder)/'input.parquet'
            with path.open('w', newline='') as f:
                writer = csv.writer(f); writer.writerow(header); writer.writerows(rows)
            prepare(path, parquet, Config('',Path(folder)))
            return calculate(parquet, header, mapping)

    def test_totals_changes_and_references_match_full_source(self):
        rows = fixture(); result = self.compute(rows)
        summary, metrics = result['summary'], result['result']['metrics']
        self.assertEqual(Decimal(metrics['total']),sum(Decimal(r[3]) for r in rows))
        self.assertEqual(summary['comparison']['rule'], 'three_months_previous_three')
        self.assertEqual(summary['comparison']['before'],['2025-01-01','2025-03-31'])
        self.assertEqual(summary['comparison']['current'],['2025-04-01','2025-06-30'])
        for group in summary['totals']['channel']:
            self.assertEqual(Decimal(metrics[group['value']['metric']]),sum(Decimal(r[3]) for r in rows if r[2]==group['channel']))
        up = summary['changes']['channel']['increases'][0]
        down = summary['changes']['product_channel']['decreases'][0]
        self.assertEqual(up['channel'],'Web'); self.assertEqual(down['product'],'Lápiz')
        self.assertEqual(Decimal(metrics[up['change']['metric']]), Decimal(15*91-10*90))
        self.assertEqual({e['metric'] for e in result['result']['evidence']},set(metrics))
        self.assertEqual(len(metrics),len(result['result']['evidence']))

    def test_gap_is_missing_rows_not_zero_sales_or_cause(self):
        result = self.compute(fixture()); summary=result['summary']
        channel = next(g for g in summary['gaps'] if 'product' not in g)
        self.assertEqual((channel['start'],channel['end']),('2025-05-05','2025-05-18'))
        values = result['result']['metrics']
        self.assertEqual(values[channel['absent_expected_days']['metric']], '14')
        self.assertEqual(values[channel['rows_in_gap']['metric']], '0')
        self.assertEqual(values[channel['habitual_active_days']['metric']], '56')
        self.assertIn('sin concluir', summary['gap_rule'])
        self.assertTrue(any(g.get('product')=='Lápiz' for g in summary['gaps']))

    def test_weekend_schedule_and_trailing_disappearance(self):
        all_days = dates('2025-01-01','2025-04-30')
        weekdays = {d for d in all_days if d.weekday()<5}
        self.assertEqual(record_gaps(weekdays, all_days[-1]), [])
        stopped = {d for d in weekdays if d < date(2025,4,14)}
        gaps = record_gaps(stopped,all_days[-1])
        self.assertEqual(len(gaps),1)
        self.assertEqual(gaps[0]['absent_expected_days'],13)
        self.assertEqual(gaps[0]['end'],'2025-04-30')

    def test_monthly_habitual_group_has_month_gap_and_no_prelaunch_gap(self):
        active = {date(2024,m,15) for m in range(1,7)} | {date(2024,9,15)}
        gaps = record_gaps(active,date(2024,9,30))
        self.assertEqual(gaps[0]['cadence'],'month')
        self.assertEqual(gaps[0]['absent_months'],2)
        self.assertEqual(gaps[0]['habitual_active_months'],6)
        self.assertEqual(record_gaps({date(2024,9,15)},date(2024,9,30)),[])

    def test_windows_explain_partial_months_and_leap_year(self):
        yearly = period_rule(date(2023,1,1),date(2024,3,15))
        self.assertEqual(yearly['current'],['2024-01-01','2024-02-29'])
        self.assertEqual(yearly['before'],['2023-01-01','2023-02-28'])
        self.assertEqual(yearly['rule'],'year_to_date_same_months')
        short = period_rule(date(2025,1,1),date(2025,3,15))
        self.assertEqual(short['rule'],'month_previous_month')
        self.assertEqual(period_rule(date(2025,1,15),date(2025,2,10))['status'],'unavailable')

    def test_missing_entire_window_or_month_is_not_imputed(self):
        rows = fixture()+[[d.isoformat(),'Nuevo','Web','2'] for d in dates('2025-04-01','2025-06-30')]
        value = self.compute(rows)
        absent = value['summary']['changes']['product_channel']['missing_window'][0]
        self.assertEqual(absent['product'],'Nuevo'); self.assertIsNone(absent['before'])
        self.assertNotIn('change',absent)
        rows = [r for r in rows if not r[0].startswith('2025-02')]
        value = self.compute(rows)
        self.assertEqual(value['summary']['comparison']['status'],'unavailable')
        self.assertEqual(value['summary']['comparison']['missing_months'],['2025-02'])
        self.assertEqual(value['summary']['changes'],{})

    def test_order_duplicates_signed_decimal_and_ambiguous_columns(self):
        rows=fixture()+[['2025-02-02','Cuaderno','Web','-0.125']]*2
        expected=self.compute(rows)
        self.assertEqual(expected,self.compute(list(reversed(rows))))
        self.assertEqual(Decimal(expected['result']['metrics']['total']),sum(Decimal(r[3]) for r in rows))
        renamed=['when','what','where','how_many']
        self.assertEqual(self.compute(rows,renamed)['status'],'unavailable')
        explicit=dict(zip(['date','product','channel','quantity'],renamed))
        self.assertEqual(self.compute(rows,renamed,explicit)['result']['metrics'],expected['result']['metrics'])
        self.assertEqual(self.compute(rows,['date','product','channel','amount'])['status'],'unavailable')
        with self.assertRaisesRegex(ValueError,'distinct existing'):
            self.compute(rows,renamed,{**explicit,'quantity':'what'})
        bad=rows+[['2025-02-30','Cuaderno','Web','1']]
        self.assertEqual(self.compute(bad)['invalid_rows'],1)
        bad=rows+[['2025-02-20','Cuaderno','Web','1,25']]
        self.assertEqual(self.compute(bad)['invalid_rows'],1)

    def test_explicit_zero_is_distinct_from_absence_and_ranking_has_both_signs(self):
        rows = [[d, f'Artículo {i:02}', f'Canal {i:02}', str(q)]
                for i in range(12) for d,q in [('2025-01-01',10), ('2025-02-28',i*2)]]
        result = self.compute(rows)
        section = result['summary']['changes']['channel']
        self.assertEqual(section['missing_window'], [])
        self.assertEqual(len(section['increases']),5)
        self.assertEqual(len(section['decreases']),5)
        self.assertEqual(section['decreases'][0]['channel'],'Canal 00')
        self.assertEqual(Decimal(result['result']['metrics'][section['decreases'][0]['current']['metric']]),0)
        self.assertEqual(section['increases'][0]['channel'],'Canal 11')
        self.assertEqual(result,self.compute(list(reversed(rows))))

    def test_over_thousand_panorama_metrics_still_emit_bounded_strict_schemas(self):
        from decision_room.agent.context import fingerprint
        rows = [[d,f'Product {i}',f'Channel {i}',q] for i in range(500)
                for d,q in [('2025-01-01','1'),('2025-02-28','2')]]
        body=self.compute(rows)
        self.assertGreater(len(body['result']['metrics']),1000)
        body['specification']={'code_sha256':'h','parquet_sha256':'source'}
        frozen=review_snapshot([dict(table_id=str(uuid4()),names=['synthetic.csv'],body=body,
            body_sha256=fingerprint(body),code='calculator')],'knowledge')
        for obs in frozen['observations']:
            self.assertLess(len(__import__('json').dumps(obs['result']).encode()),64000)
        context=dict(review_policy=5,observations=frozen['observations'],budgets={'sales_panorama':True,'owner_presentation':True})
        for method in ('generate_analyst_review','generate_reviewer'):
            assert_strict_objects(self,strict.StrictProviderSchemaTests.capture(self,method,context))

    def test_import_observations_are_citable_and_schema_accepts_both_roles(self):
        from decision_room.agent.context import fingerprint
        body=self.compute(fixture()); body['specification']={'code_sha256':'h','parquet_sha256':'source'}
        prepared=[dict(table_id=str(uuid4()),names=['sales.csv'],body=body,body_sha256=fingerprint(body),code='deterministic calculator')]
        frozen=review_snapshot(prepared,'knowledge')
        def refs(value):
            if isinstance(value,dict):
                if set(value)=={'execution_id','metric'}: yield value
                else:
                    for v in value.values(): yield from refs(v)
            if isinstance(value,list):
                for v in value: yield from refs(v)
        for ref in refs(frozen['tables']):
            self.assertIsNotNone(evidence_value(frozen['observations'],ref))
        client=ModelClient(ModelSettings('test'))
        context=dict(review_policy=5, observations=frozen['observations'],sales_panorama={'tables':frozen['tables']},budgets={'sales_panorama':True})
        for method in ('generate_analyst_review','generate_reviewer'):
            with patch.object(client,'_generate',return_value=({},{})) as generate:
                getattr(client,method)(context)
            self.assertIn(SYSTEM,generate.call_args.args[2])
            assert_strict_objects(self,strict.StrictProviderSchemaTests.capture(self,method,context))
        with patch.object(client,'_generate',return_value=({},{})) as generate:
            client.generate_analyst_review({})
        self.assertNotIn(SYSTEM,generate.call_args.args[2])
