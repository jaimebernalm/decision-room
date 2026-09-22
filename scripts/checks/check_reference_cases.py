"""Check fixture values against source using SQLite, independently of the builder.

This checks reference data, not agent behaviour. See the manual review checklist
in data/reference-cases/README.md until the analysis runner is implemented.
"""
import argparse
import csv
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/wide-world-importers/exports/csv'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def cents(value):
    whole, dot, fraction = value.partition('.')
    if dot and len(fraction) > 2:
        raise ValueError(f'Unexpected monetary precision: {value}')
    return (-1 if value.startswith('-') else 1) * (abs(int(whole)) * 100 + int(fraction.ljust(2, '0') or '0'))


def cash(value):
    return f'{"-" if value < 0 else ""}{abs(value) // 100}.{abs(value) % 100:02d}'


def equal(actual, expected, label):
    if actual != expected:
        raise ValueError(f'{label}: expected {str(expected)[:300]}, got {str(actual)[:300]}')


def check(directory):
    provenance = json.loads((directory / 'provenance.json').read_text())
    for name, expected in provenance['source_files_sha256'].items():
        equal(hashlib.sha256((SOURCE / name).read_bytes()).hexdigest(), expected, name + ' source hash')
    db = sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE invoices(id TEXT PRIMARY KEY, day TEXT, credit TEXT);
        CREATE TABLE lines(id INTEGER PRIMARY KEY, invoice TEXT, sku INTEGER, quantity INTEGER,
                           price INTEGER, extended INTEGER, tax INTEGER);
        CREATE TABLE products(sku INTEGER PRIMARY KEY, name TEXT);
    ''')
    db.executemany('INSERT INTO invoices VALUES (?,?,?)',
                   ((r['InvoiceID'], r['InvoiceDate'], r['IsCreditNote']) for r in rows(SOURCE / 'Sales.Invoices.csv')))
    db.executemany('INSERT INTO lines VALUES (?,?,?,?,?,?,?)',
                   ((int(r['InvoiceLineID']), r['InvoiceID'], int(r['StockItemID']), int(r['Quantity']),
                     cents(r['UnitPrice']), cents(r['ExtendedPrice']), cents(r['TaxAmount']))
                    for r in rows(SOURCE / 'Sales.InvoiceLines.csv')))
    db.executemany('INSERT INTO products VALUES (?,?)',
                   ((int(r['StockItemID']), r['StockItemName']) for r in rows(SOURCE / 'Warehouse.StockItems.csv')))
    db.executescript('''
        CREATE VIEW selected AS
        SELECT l.*, i.day, p.name, l.extended-l.tax AS sales
        FROM lines l JOIN invoices i ON l.invoice=i.id JOIN products p ON l.sku=p.sku
        WHERE i.day BETWEEN '2016-04-01' AND '2016-04-28' AND i.credit='0' AND l.sku BETWEEN 1 AND 8;
        CREATE VIEW ambiguous AS SELECT * FROM selected WHERE sku=1 ORDER BY day,id LIMIT 12;
    ''')
    equal([str(r[0]) for r in db.execute('SELECT id FROM selected ORDER BY day,id')],
          provenance['selected_invoice_line_ids'], 'selected source lines')
    equal([str(r[0]) for r in db.execute('SELECT id FROM ambiguous ORDER BY day,id')],
          provenance['ambiguous_invoice_line_ids'], 'ambiguous source lines')
    daily = [(day, cash(total)) for day, total in db.execute('SELECT day,SUM(sales) FROM selected GROUP BY day ORDER BY day')]
    product = [(day, str(sku), name, str(qty), cash(total)) for day, sku, name, qty, total in db.execute(
        'SELECT day,sku,name,SUM(quantity),SUM(sales) FROM selected GROUP BY day,sku ORDER BY day,sku')]
    ambiguous = [(day, str(sku), str(qty), cash(price)) for day, sku, qty, price in db.execute(
        'SELECT day,sku,quantity,price FROM ambiguous ORDER BY day,id')]
    cases = [
        ('01-daily-sales', ['date','sales_ex_tax'], ['sales_value','day'], [1,0], daily),
        ('02-product-sales', ['date','product_id','product_name','quantity','sales_ex_tax'],
         ['value_ex_tax','units','item_name','sku','day'], [4,3,2,1,0], product),
        ('03-ambiguous-amount', ['date','product_id','quantity','amount'],
         ['value','units','sku','day'], [3,2,1,0], ambiguous),
    ]
    for case, headers, renamed, order, expected in cases:
        actual = rows(directory / case / 'input/sales.csv')
        equal(list(actual[0]), headers, case + ' headers')
        equal([tuple(r[h] for h in headers) for r in actual], expected, case + ' source values')
        variant = rows(directory / case / 'variants/renamed-columns/sales.csv')
        equal(list(variant[0]), renamed, case + ' variant headers')
        equal([tuple(r[h] for h in renamed) for r in variant],
              [tuple(row[i] for i in order) for row in reversed(expected)], case + ' variant values')
    total, first, second, days, quantity, count = db.execute('''
        SELECT SUM(sales), SUM(CASE WHEN day<='2016-04-14' THEN sales ELSE 0 END),
        SUM(CASE WHEN day>='2016-04-15' THEN sales ELSE 0 END), COUNT(DISTINCT day),
        SUM(quantity), COUNT(DISTINCT sku) FROM selected
    ''').fetchone()
    metrics = {'sales_ex_tax': cash(total), 'first_period_sales_ex_tax': cash(first),
               'second_period_sales_ex_tax': cash(second), 'change_amount': cash(second-first),
               'change_percent': f'{(second-first)/first*100:.2f}', 'observed_days': days}
    e1, e2, e3 = [json.loads((directory / c[0] / 'evaluation/expected.json').read_text()) for c in cases]
    equal(e1['metrics'], metrics, 'daily expected metrics')
    equal(e1['daily_sales_ex_tax'], dict(daily), 'daily expected breakdown')
    equal(e2['metrics'], dict(metrics, quantity=quantity, product_count=count), 'product expected metrics')
    equal(e2['by_product'], {str(sku): {'quantity': qty, 'sales_ex_tax': cash(sales)}
                            for sku, qty, sales in db.execute('SELECT sku,SUM(quantity),SUM(sales) FROM selected GROUP BY sku')},
          'product expected breakdown')
    equal(e2['top_product_by_sales'], str(db.execute('SELECT sku FROM selected GROUP BY sku ORDER BY SUM(sales) DESC,sku LIMIT 1').fetchone()[0]), 'top product')
    unit_total, row_total, units = db.execute('SELECT SUM(price*quantity),SUM(price),SUM(quantity) FROM ambiguous').fetchone()
    equal(e3['after_unit_price_answer'], {'sales_ex_tax': cash(unit_total)}, 'unit price branch')
    equal(e3['after_line_total_answer'], {'sales_ex_tax': cash(row_total)}, 'line total branch')
    equal(e3['before_answer']['allowed_metrics'], {'quantity': units}, 'unambiguous quantities')
    db.close()
    print(f'PASS: 3 reference cases, 3 variants, source provenance and all numerical answer keys.')
    print(f'Recorded sales excluding tax: {cash(total)}; ambiguous amount: {cash(unit_total)} or {cash(row_total)} depending on the answer.')
    print('This command checks fixture data only. Run decision_room.evaluation.runner and independently assess its reports to evaluate agent behaviour.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases-dir', type=Path, default=ROOT / 'data/reference-cases')
    check(parser.parse_args().cases_dir)
