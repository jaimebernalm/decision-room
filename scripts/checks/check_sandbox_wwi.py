"""Compare the actual sandbox with an independent CSV/Decimal calculation."""
import argparse
import csv
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.config import Config
from decision_room.execution import execute, get_execution
from decision_room.service import describe
from decision_room.storage import Storage, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business', default='3fdd7db1-26d5-453d-829e-70b34acb6452')
    parser.add_argument('--analysis', default='d708470f-35dc-4f9b-a79c-c1a279ba803b')
    parser.add_argument('--request-key', default='sandbox-wwi-acceptance-v2')
    args = parser.parse_args()
    config = Config.load()
    description = describe(config, args.business, args.analysis, detailed=True)
    tables, expected_counts = {}, {}
    for file in description['files']:
        alias = re.sub('[^a-z0-9_]', '_', Path(file['original_names'][0]).stem.lower())
        tables[alias] = file['table_id']
        expected_counts[alias + '_rows'] = file['row_count']
    code = (ROOT / 'examples/wwi_calculation.py').read_text()
    result = execute(config, args.business, args.analysis, code=code, tables=tables,
                     definitions={'dataset':'Microsoft fictional WWI', 'amount':'ExtendedPrice includes tax'},
                     request_key=args.request_key)
    if result['status'] != 'completed':
        raise ValueError(json.dumps(result, default=str))
    metrics = result['result']['metrics']
    assert len(tables) == 48 and sum(expected_counts.values()) == 4_713_833
    assert all(metrics[key] == count for key, count in expected_counts.items())
    base = ROOT / 'data/wide-world-importers/exports/csv'
    invoice_ids = set()
    with (base / 'Sales.Invoices.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            assert row['InvoiceID'] not in invoice_ids
            invoice_ids.add(row['InvoiceID'])
    count, total, tax = 0, Decimal('0'), Decimal('0')
    with (base / 'Sales.InvoiceLines.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            count += 1
            assert row['InvoiceID'] in invoice_ids
            total += Decimal(row['ExtendedPrice'])
            tax += Decimal(row['TaxAmount'])
    assert metrics['invoice_lines'] == metrics['joined_invoice_lines'] == count
    assert Decimal(metrics['extended_price_total']) == total
    assert Decimal(metrics['tax_total']) == tax
    assert Decimal(metrics['amount_excluding_tax']) == total-tax
    recovered = get_execution(config, args.business, result['id'])
    storage = Storage(config.storage)
    assert recovered['result'] == result['result']
    assert digest(storage.path(args.business, recovered['code_key'])) == recovered['code_sha256']
    for artifact in recovered['artifacts']:
        assert digest(storage.path(args.business, artifact['storage_key'])) == artifact['sha256']
    report = {'execution_id': str(result['id']), 'status': result['status'],
              'table_count':len(tables), 'total_rows':sum(expected_counts.values()),
              'invoice_lines': count, 'extended_price_total':str(total), 'tax_total':str(tax),
              'amount_excluding_tax':str(total-tax), 'independent_csv_comparison':True,
              'stored_evidence_recovered':True, 'duration_seconds':result['duration_seconds'],
              'environment':result['environment'], 'limits':result['limits']}
    (ROOT / '.local/sandbox-wwi-check.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
