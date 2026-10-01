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
                      f'product_id:{year}:{line["StockItemID"]}',
                      f'customer_id:{year}:{invoice["CustomerID"]}']
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
    # Zero here is an absent contribution to observed totals, not a fabricated
    # yearly level or evidence that the customer had no actual activity.
    by_category = defaultdict(list)
    observed = {k.rsplit(':', 1)[1] for k in groups if k.startswith('customer_id:')}
    for identity in observed:
        category = categories[customers[identity]['CustomerCategoryID']]['CustomerCategoryName']
        by_category[category].append(identity)
    def contribution(year, identity, measure):
        return groups.get(f'customer_id:{year}:{identity}', {}).get('sums', {}).get(measure, Decimal(0))
    for category, identities in by_category.items():
        prefix = f'detail:category_change:{category}:'
        result[prefix + 'customer_count'] = len(identities)
        for measure in ('gross_sales', 'net_sales', 'profit', 'quantity'):
            changes = [contribution('2015', identity, measure) - contribution('2014', identity, measure)
                       for identity in identities]
            magnitudes = sorted(map(abs, changes), reverse=True)
            result[prefix + measure + ':net_change'] = sum(changes, Decimal(0))
            result[prefix + measure + ':absolute_change_sum'] = sum(magnitudes, Decimal(0))
            result[prefix + measure + ':top5_absolute_change_sum'] = sum(magnitudes[:5], Decimal(0))
            result[prefix + measure + ':top12_absolute_change_sum'] = sum(magnitudes[:12], Decimal(0))
    return result
