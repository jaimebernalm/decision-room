"""Acceptance check for the imported WWI batch, not part of the CSV importer.

The test knows the original schema/NULL masks. The importer never reads them.
Compare every Parquet value and row ordinal with Python's independent CSV reader.
"""
import argparse
import csv
import gzip
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.config import Config
from decision_room.service import describe
from decision_room.storage import Storage, digest


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/wwi-verification.json')
    args = parser.parse_args()
    config = Config.load()
    storage = Storage(config.storage)
    imported = describe(config, args.business, args.analysis, detailed=True)
    base = ROOT / 'data/wide-world-importers/exports'
    manifest = json.loads((base / 'manifest.json').read_text())
    lookup = {f['original_names'][0]: f for f in imported['files']}
    check(imported['analysis']['status'] == 'ready', 'Import is not fully ready.')
    check(len(lookup) == len(manifest['tables']) == 48, 'Expected 48 source tables.')
    csv.field_size_limit(16 * 1024 * 1024)
    reports, total, cells = [], 0, 0
    with duckdb.connect(config={'threads': 1, 'memory_limit': '512MB'}) as db:
        for expected in manifest['tables']:
            name = Path(expected['csv']).name
            got = lookup[name]
            check(got['sha256'] == expected['sha256'], f'Source hash mismatch: {name}')
            original = storage.path(args.business, got['original_key'])
            check(digest(original) == expected['sha256'], f'Original bytes changed: {name}')
            parquet = storage.path(args.business, got['parquet_key'])
            check(digest(parquet) == got['parquet_sha256'], f'Parquet bytes changed: {name}')
            header = [c['name'] for c in expected['columns']]
            check([c['name'] for c in got['columns']] == header, f'Columns changed: {name}')
            for key, source_key in [('null_count','null_counts'), ('empty_string_count','empty_string_counts'), ('max_characters','max_characters')]:
                check([c[key] for c in got['columns']] == expected[source_key], f'{key} mismatch: {name}')
            cursor = db.execute('SELECT * FROM read_parquet(?)', [str(parquet)])
            check([c[0] for c in cursor.description] == [got['lineage_column'], *header], f'Parquet schema mismatch: {name}')
            width = (len(header) + 7) // 8
            count = 0
            with (base / expected['csv']).open(encoding='utf-8-sig', newline='') as stream, gzip.open(base / expected['null_mask'], 'rb') as masks:
                source = csv.reader(stream)
                check(next(source) == header, f'Source header mismatch: {name}')
                while batch := cursor.fetchmany(8192):
                    for actual in batch:
                        count += 1
                        row = next(source)
                        raw_mask = masks.read(width)
                        check(len(raw_mask) == width, f'Truncated NULL mask: {name}')
                        mask = int.from_bytes(raw_mask, 'little')
                        wanted = (count, *(None if mask & (1 << j) else v for j, v in enumerate(row)))
                        check(actual == wanted, f'Value/row-order mismatch in {name}, record {count}')
                check(next(source, None) is None, f'Parquet lost rows: {name}')
                check(not masks.read(1), f'Unused source NULL masks: {name}')
            check(count == expected['rows'] == got['row_count'], f'Row count mismatch: {name}')
            total += count
            cells += count * len(header)
            reports.append({'table': expected['table'], 'rows': count, 'columns': len(header),
                            'every_value_and_row_order_verified': True})
            print(f'Verified {name}: {count:,} rows', flush=True)
        for short in ['InvoiceLines', 'Invoices']:
            path = storage.path(args.business, lookup[f'Sales.{short}.csv']['parquet_key'])
            db.read_parquet(str(path)).create_view(short)
        joined, orphans = db.sql('''SELECT count(*), count(*) FILTER (WHERE i.InvoiceID IS NULL)
            FROM InvoiceLines l LEFT JOIN Invoices i ON l.InvoiceID=i.InvoiceID''').fetchone()
        check(joined == lookup['Sales.InvoiceLines.csv']['row_count'] and orphans == 0,
              'Known invoice join lost/multiplied rows or found orphan lines.')
        totals = db.sql('''SELECT SUM(CAST(Quantity AS BIGINT)),SUM(CAST(TaxAmount AS DECIMAL(18,2))),
            SUM(CAST(ExtendedPrice AS DECIMAL(18,2))),SUM(CAST(LineProfit AS DECIMAL(18,2))) FROM InvoiceLines''').fetchone()
        prior = json.loads((base / 'metadata/data-validation.json').read_text())['invoice_line_totals']
        check([str(x) for x in totals] == [prior[k] for k in ('Quantity','TaxAmount','ExtendedPrice','LineProfit')],
              'Known invoice totals differ from independently verified export totals.')
    check(total == manifest['total_rows'] == imported['total_rows'], 'Total row count mismatch.')
    report = {'business_id': args.business, 'analysis_id': args.analysis, 'status': 'passed',
              'tables': reports, 'total_rows': total, 'total_source_cells': cells,
              'all_original_hashes_verified': True, 'all_parquet_hashes_verified': True,
              'all_values_nulls_empty_strings_and_row_order_verified': True,
              'known_invoice_join': {'rows': joined, 'orphans': orphans},
              'known_invoice_totals_verified': True,
              'scope': 'CSV ingestion acceptance only; does not validate autonomous interpretation or reports.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(reports)} tables, {total:,} rows, {cells:,} values; known join and totals verified.')


if __name__ == '__main__':
    main()
