"""Build a larger public-source CSV and separate independent references.

Requires the existing WWI CSV exports. Generated data stays in ignored .local.
No customer identifiers, names or contact information are selected.
"""
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/wide-world-importers/exports/csv'
OUT = ROOT / '.local/visual-case'
START, END = '2015-07-01', '2015-12-31'


def read(name):
    with (SOURCE / (name + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def main():
    invoices = {r['InvoiceID']: r for r in read('Sales.Invoices')}
    names = {r['StockItemID']: r['StockItemName'] for r in read('Warehouse.StockItems')}
    rows = []
    source_total = Decimal(0)
    for r in read('Sales.InvoiceLines'):
        invoice = invoices[r['InvoiceID']]
        if not START <= invoice['InvoiceDate'] <= END or invoice['IsCreditNote'] != '0':
            continue
        amount = Decimal(r['ExtendedPrice']) - Decimal(r['TaxAmount'])
        assert amount == Decimal(r['Quantity']) * Decimal(r['UnitPrice'])
        source_total += amount
        rows.append([invoice['InvoiceDate'], r['InvoiceID'], r['InvoiceLineID'], r['StockItemID'],
                     names[r['StockItemID']], int(r['Quantity']), f'{amount:.2f}'])
    rows.sort(key=lambda r: (r[0], int(r[2])))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'ventas_wwi_2015_semestre.csv'
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['date', 'invoice_id', 'line_id', 'product_id', 'product_name', 'quantity', 'sales_ex_tax'])
        writer.writerows(rows)
    # Independent aggregation via SQLite and integer cents, over the saved CSV.
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE sales(day TEXT, invoice TEXT, line TEXT, product TEXT, name TEXT, units INTEGER, cents INTEGER)')
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        db.executemany('INSERT INTO sales VALUES (?,?,?,?,?,?,?)',
                       ((r['date'], r['invoice_id'], r['line_id'], r['product_id'], r['product_name'],
                         int(r['quantity']), int(Decimal(r['sales_ex_tax']) * 100)) for r in reader))
    total = db.execute('SELECT count(*),sum(units),sum(cents),count(DISTINCT product),count(DISTINCT day),count(DISTINCT invoice) FROM sales').fetchone()
    assert Decimal(total[2]) / 100 == source_total
    money = lambda cents: f'{Decimal(cents)/100:.2f}'
    reference = {'rows':total[0], 'units':total[1], 'sales_ex_tax':money(total[2]), 'products':total[3], 'recorded_days':total[4], 'invoices':total[5],
                 'monthly': {month:money(cents) for month,cents in db.execute('SELECT substr(day,1,7),sum(cents) FROM sales GROUP BY 1 ORDER BY 1')},
                 'daily': {day:money(cents) for day,cents in db.execute('SELECT day,sum(cents) FROM sales GROUP BY day ORDER BY day')},
                 'products_by_sales': [{'id':p,'name':n,'sales_ex_tax':money(c),'units':u} for p,n,c,u in db.execute('SELECT product,name,sum(cents),sum(units) FROM sales GROUP BY product,name ORDER BY sum(cents) DESC,product')]}
    (OUT / 'expected.json').write_text(json.dumps(reference, indent=2, ensure_ascii=False) + '\n')
    provenance = {'source':'Microsoft Wide World Importers v1.0, fictional wholesale sample',
                  'source_url':'https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0',
                  'period':[START,END], 'credit_notes':'excluded',
                  'sources': {name:hashlib.sha256((SOURCE / (name+'.csv')).read_bytes()).hexdigest() for name in ['Sales.Invoices','Sales.InvoiceLines','Warehouse.StockItems']},
                  'csv_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'transformation':'Join invoice date and product name to invoice lines; sales_ex_tax = ExtendedPrice - TaxAmount. Preserve line IDs, quantities and all products in the selected period.',
                  'limitations':['Fictional wholesale sample, not real retail results.', 'Currency is not established.', 'An absent date is not assumed to have zero sales.']}
    (OUT / 'provenance.json').write_text(json.dumps(provenance,indent=2) + '\n')
    print(json.dumps({'csv':str(path.relative_to(ROOT)), **{k:v for k,v in reference.items() if k not in ('monthly','daily','products_by_sales')}, 'bytes':path.stat().st_size},indent=2))


if __name__ == '__main__':
    main()
