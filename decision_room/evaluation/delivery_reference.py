"""Additional source-side CSV/Decimal dimensions; never sent to product agents.

These extend the frozen quality oracle without changing its required answers.
Gross/net/tax, unit-price distributions and credit notes retain distinct meanings.
"""
from collections import defaultdict
from decimal import Decimal

from .substantial_data import TABLES, index, rows


def wwi_details(base):
    invoices = index(base, TABLES[0], 'InvoiceID')
    customers = index(base, TABLES[2], 'CustomerID')
    categories = index(base, TABLES[3], 'CustomerCategoryID')
    products = index(base, TABLES[4], 'StockItemID')
    groups = defaultdict(lambda: dict(sums=defaultdict(Decimal), prices=[], invoices=set()))
    line_ids = set()
    for line in rows(base, TABLES[1]):
        if line['InvoiceLineID'] in line_ids:
            raise ValueError('Duplicate line identity in independent reference')
        line_ids.add(line['InvoiceLineID'])
        invoice = invoices[line['InvoiceID']]
        customer = customers[invoice['CustomerID']]
        category = categories[customer['CustomerCategoryID']]['CustomerCategoryName']
        product = products[line['StockItemID']]
        year = invoice['InvoiceDate'][:4]
        if year not in ('2014', '2015'):
            continue
        raw_credit = invoice['IsCreditNote'].strip().lower()
        if raw_credit not in ('0', '1', 'true', 'false'):
            raise ValueError('Unknown credit-note definition')
        credit = raw_credit in ('1', 'true')
        quantity, price, gross, tax, profit = [Decimal(line[key]) for key in
            ('Quantity', 'UnitPrice', 'ExtendedPrice', 'TaxAmount', 'LineProfit')]
        if not all(v.is_finite() for v in (quantity, price, gross, tax, profit)):
            raise ValueError('Nonfinite independent amount')
        dimensions = [f'year:{year}', f'category:{year}:{category}',
                      f'cross:{year}:{category}:{line["StockItemID"]}',
                      f'product_id:{year}:{line["StockItemID"]}']
        for key in dimensions:
            group = groups[key]; totals = group['sums']
            values = dict(quantity=quantity, gross_sales=gross, net_sales=gross-tax,
                          tax=tax, profit=profit, lines=Decimal(1), unit_price_sum=price,
                          price_quantity=price*quantity)
            for name, value in values.items():
                totals[name] += value
                if credit and name in ('quantity', 'gross_sales', 'net_sales', 'profit', 'lines'):
                    totals['credit_' + name] += value
            group['prices'].append(price)
            group['invoices'].add(line['InvoiceID'])
    result = {}
    for identity, product in products.items():
        result['detail:stock_name:' + identity] = product['StockItemName']
        result['detail:stock_id:' + identity] = Decimal(identity)
    for key, group in groups.items():
        totals = group['sums']; count = totals['lines']; quantity = totals['quantity']
        values = {**totals, 'invoices': len(group['invoices']),
                  'avg_unit_price': totals['unit_price_sum']/count,
                  'min_unit_price': min(group['prices']), 'max_unit_price': max(group['prices'])}
        for name in ('quantity', 'gross_sales', 'net_sales', 'profit', 'lines'):
            values.setdefault('credit_' + name, Decimal(0))
        if quantity:
            values['weighted_unit_price'] = totals['price_quantity']/quantity
        if totals['net_sales']:
            values['net_margin_pct'] = totals['profit']/totals['net_sales']*100
        if totals['gross_sales']:
            values['gross_margin_pct'] = totals['profit']/totals['gross_sales']*100
        result.update({f'detail:{key}:{name}': value for name, value in values.items()})
    return result
