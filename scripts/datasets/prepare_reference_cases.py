"""Prepare small source-backed evaluation inputs; never used by the analyst.

No packages required. Money uses Decimal. The separate verifier uses SQLite and
integer cents to cross-check against the original invoice lines.
"""
import csv
import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/wide-world-importers/exports/csv'
OUT = ROOT / 'data/reference-cases'
STAGING = ROOT / '.tools/reference-cases'
START, END = '2016-04-01', '2016-04-28'


def read(name):
    with (SOURCE / f'{name}.csv').open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def money(value):
    return f'{value:.2f}'


def main():
    invoices = {r['InvoiceID']: r for r in read('Sales.Invoices')}
    products = {r['StockItemID']: r['StockItemName'] for r in read('Warehouse.StockItems')}
    selected = sorted((r for r in read('Sales.InvoiceLines')
                       if START <= invoices[r['InvoiceID']]['InvoiceDate'] <= END
                       and invoices[r['InvoiceID']]['IsCreditNote'] == '0'
                       and 1 <= int(r['StockItemID']) <= 8),
                      key=lambda r: (invoices[r['InvoiceID']]['InvoiceDate'], int(r['InvoiceLineID'])))
    daily = defaultdict(Decimal)
    grouped = defaultdict(lambda: [0, Decimal(0)])
    for row in selected:
        date = invoices[row['InvoiceID']]['InvoiceDate']
        amount = Decimal(row['ExtendedPrice']) - Decimal(row['TaxAmount'])
        daily[date] += amount
        key = (date, row['StockItemID'])
        grouped[key][0] += int(row['Quantity'])
        grouped[key][1] += amount
    daily_rows = [[date, money(amount)] for date, amount in sorted(daily.items())]
    product_rows = [[date, sku, products[sku], qty, money(amount)]
                    for (date, sku), (qty, amount) in sorted(grouped.items())]
    ambiguous = [r for r in selected if r['StockItemID'] == '1'][:12]
    ambiguous_rows = [[invoices[r['InvoiceID']]['InvoiceDate'], r['StockItemID'],
                       int(r['Quantity']), r['UnitPrice']] for r in ambiguous]

    definitions = [
        ('01-daily-sales', ['date', 'sales_ex_tax'], daily_rows,
         ['sales_value', 'day'], [1, 0]),
        ('02-product-sales', ['date', 'product_id', 'product_name', 'quantity', 'sales_ex_tax'],
         product_rows, ['value_ex_tax', 'units', 'item_name', 'sku', 'day'], [4, 3, 2, 1, 0]),
        ('03-ambiguous-amount', ['date', 'product_id', 'quantity', 'amount'], ambiguous_rows,
         ['value', 'units', 'sku', 'day'], [3, 2, 1, 0]),
    ]
    staged = []
    for case, header, rows, variant_header, order in definitions:
        staged.append({'case': case, 'file': 'input/sales.csv', 'header': header, 'rows': rows})
        staged.append({'case': case, 'file': 'variants/renamed-columns/sales.csv',
                       'header': variant_header, 'rows': [[r[i] for i in order] for r in reversed(rows)]})
    save(STAGING / 'tables.json', staged)

    first = sum((amount for date, amount in daily.items() if date <= '2016-04-14'), Decimal(0))
    second = sum((amount for date, amount in daily.items() if date >= '2016-04-15'), Decimal(0))
    common = {'sales_ex_tax': money(sum(daily.values())),
              'first_period_sales_ex_tax': money(first),
              'second_period_sales_ex_tax': money(second),
              'change_amount': money(second - first),
              'change_percent': money((second - first) / first * 100),
              'observed_days': len(daily)}
    by_product = defaultdict(lambda: [0, Decimal(0)])
    for (_, sku), (qty, amount) in grouped.items():
        by_product[sku][0] += qty
        by_product[sku][1] += amount
    base_rules = ['Do not infer causes, profit, stock levels or customer behaviour.',
                  'Do not treat absent dates as zero-sales days or assume opening days.',
                  'Describe these as recorded sales within the supplied scope.']
    expectations = {
        '01-daily-sales': {
            'metrics': common,
            'daily_sales_ex_tax': dict(daily_rows),
            'must_not_claim': base_rules + ['No product rankings, ticket count or average ticket value.'],
            'expected_behaviour': 'Proceed using the context; no mandatory clarification is needed.',
        },
        '02-product-sales': {
            'metrics': dict(common, quantity=sum(v[0] for v in by_product.values()),
                            product_count=len(by_product)),
            'by_product': {sku: {'quantity': qty, 'sales_ex_tax': money(amount)}
                           for sku, (qty, amount) in sorted(by_product.items())},
            'top_product_by_sales': max(by_product, key=lambda sku: by_product[sku][1]),
            'must_not_claim': base_rules + ['No ticket count or average ticket value; rows aggregate multiple sales.'],
            'expected_behaviour': 'Analyse product sales; do not request tickets unless needed for an optional question.',
        },
        '03-ambiguous-amount': {
            'before_answer': {'status': 'needs_clarification',
                              'required_question': 'Does amount mean unit price or the total for that row?',
                              'blocked_metrics': ['sales_ex_tax', 'average_selling_price'],
                              'allowed_metrics': {'quantity': sum(int(r['Quantity']) for r in ambiguous)}},
            'after_unit_price_answer': {'sales_ex_tax': money(sum(Decimal(r['UnitPrice']) * int(r['Quantity']) for r in ambiguous))},
            'after_line_total_answer': {'sales_ex_tax': money(sum(Decimal(r['UnitPrice']) for r in ambiguous))},
            'if_owner_does_not_know': 'Leave sales totals unresolved. Report supported quantities and explain the limitation without repeating the question.',
            'must_not_claim': base_rules + ['No final sales total before clarification.', 'No average ticket value.'],
        },
    }
    for case, expected in expectations.items():
        save(OUT / case / 'evaluation/expected.json', expected)
    save(OUT / '03-ambiguous-amount/evaluation/owner-responses.json', {
        'unit_price': 'The amount is the price per unit, after any discount and excluding tax. Multiply it by quantity.',
        'line_total': 'The amount is the whole row total, after any discount and excluding tax. Do not multiply it again.',
        'unknown': "I don't know. Continue with what you can safely analyse.",
        'note': 'unit_price matches the original source. line_total is a deliberately different hypothetical interpretation of the same upload, used to test adaptation.',
    })
    save(OUT / 'provenance.json', {
        'source': 'Microsoft Wide World Importers v1.0, fictional wholesale sample',
        'source_url': 'https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0',
        'source_files_sha256': {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                                for name in ['Sales.Invoices.csv', 'Sales.InvoiceLines.csv', 'Warehouse.StockItems.csv']},
        'selection': {'start': START, 'end': END, 'stock_item_ids': list(range(1, 9)), 'is_credit_note': '0'},
        'selected_invoice_line_ids': [r['InvoiceLineID'] for r in selected],
        'ambiguous_invoice_line_ids': [r['InvoiceLineID'] for r in ambiguous],
        'transformations': ['Join InvoiceLines to Invoices using InvoiceID.',
                            'Sales excluding tax = ExtendedPrice minus TaxAmount.',
                            'Daily case groups by date; product case groups by date and StockItemID.',
                            'Product names come from StockItems. Invoice identifiers are deliberately omitted.',
                            'Ambiguous case takes the first 12 date/line-ID sorted rows for product 1 and labels UnitPrice as amount.',
                            'Variants rename and reorder columns and reverse rows; values remain unchanged.'],
        'limitations': ['Selected wholesale activity is not a complete small-store export.',
                        'No real customer or shop outcomes are represented.',
                        'Context and owner answers are authored scenario instructions.']
    })
    print(f'Prepared {len(selected)} source lines, {len(daily_rows)} daily rows, '
          f'{len(product_rows)} product/day rows and {len(ambiguous_rows)} ambiguous rows.')


if __name__ == '__main__':
    main()
