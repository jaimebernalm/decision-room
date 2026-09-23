"""Scenarios and independent Decimal references from public fixture CSVs."""
import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / 'data/reference-cases'
SCENARIOS = {
    'daily': ('01-daily-sales', False, None),
    'daily-renamed': ('01-daily-sales', True, None),
    'products': ('02-product-sales', False, None),
    'products-renamed': ('02-product-sales', True, None),
    'unit-price': ('03-ambiguous-amount', False, 'unit_price'),
    'line-total': ('03-ambiguous-amount', True, 'line_total'),
    'unknown': ('03-ambiguous-amount', False, 'unknown'),
    'declined': ('03-ambiguous-amount', True, 'declined'),
    'duplicates': ('04-data-quality/duplicates', False, None),
    'missing-values': ('04-data-quality/missing-values', False, None),
    'returns': ('04-data-quality/returns', False, None),
    'invalid-dates': ('04-data-quality/invalid-dates', False, None),
}


def inputs(scenario):
    case, variant, _ = SCENARIOS[scenario]
    folder = CASES / case
    return folder / ('variants/renamed-columns' if variant else 'input') / 'sales.csv', (folder / 'input/context.md').read_text()


def money(value):
    return str(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def reference(scenario):
    """Read canonical evaluator data independently; never a production calculation."""
    case, _, answer = SCENARIOS[scenario]
    with (CASES / case / 'input/sales.csv').open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    if case.startswith('04-data-quality/'):
        original_count = len(rows)
        if scenario == 'duplicates':
            rows = list({r['line_id']: r for r in rows}.values())
        valid = []
        for row in rows:
            try:
                date.fromisoformat(row['date'])
                value = Decimal(row['sales_ex_tax'])
                if not value.is_finite(): continue
                valid.append(value)
            except (ValueError, ArithmeticError):
                pass
        metrics = {'sales': money(sum(valid)), 'input_rows': str(original_count),
                   'included_amount_rows': str(len(valid)), 'excluded_amount_rows': str(len(rows)-len(valid)),
                   'duplicate_rows': str(original_count-len(rows))}
        required = ['sales']
        if scenario != 'invalid-dates':
            metrics['quantity'] = str(sum(Decimal(r['quantity']) for r in rows))
            required.append('quantity')
        return {'required': required, 'metrics': metrics, 'basis': 'explicit_line_total_or_daily_total'}
    if case == '03-ambiguous-amount':
        result = {'quantity': str(sum(Decimal(r['quantity']) for r in rows))}
        if answer in ('unit_price', 'line_total'):
            result['sales'] = money(sum(Decimal(r['amount']) * (Decimal(r['quantity']) if answer == 'unit_price' else 1) for r in rows))
        return {'required': list(result), 'metrics': result, 'basis': answer}
    daily = {}
    products = {}
    for row in rows:
        d = row['date']
        value = Decimal(row['sales_ex_tax'])
        daily[d] = daily.get(d, Decimal(0)) + value
        if case == '02-product-sales':
            key = row['product_id']
            item = products.setdefault(key, {'sales': Decimal(0), 'quantity': Decimal(0), 'first': Decimal(0), 'second': Decimal(0)})
            item['sales'] += value
            item['quantity'] += Decimal(row['quantity'])
            item['first' if int(d[-2:]) <= 14 else 'second'] += value
    values = [sum(v for d,v in daily.items() if lo <= int(d[-2:]) <= hi) for lo,hi in ((1,14),(15,28))]
    result = {'sales': money(sum(values)), 'first_sales':money(values[0]), 'second_sales':money(values[1]),
              'change':money(values[1]-values[0]), 'change_percent':money((values[1]/values[0]-1)*100),
              'observed_days':str(len(daily)), 'missing_days':str(28-len(daily))}
    for prefix,lo,hi in [('first',1,14),('second',15,28)]:
        vals=[v for d,v in daily.items() if lo<=int(d[-2:])<=hi]
        result.update({prefix+'_mean':money(sum(vals)/len(vals)),prefix+'_median':money(median(vals)),
                       prefix+'_days':str(len(vals)),prefix+'_min':money(min(vals)),prefix+'_max':money(max(vals))})
    result.update({'daily:'+d:money(v) for d,v in daily.items()})
    for key,item in products.items():
        result.update({'product:'+key+':'+k:money(v) for k,v in item.items()})
        result['product:'+key+':change']=money(item['second']-item['first'])
        result['product:'+key+':share']=money(item['sales']/sum(values)*100)
    required=['first_sales','second_sales']
    if products:
        top=max(products,key=lambda k:products[k]['sales'])
        required+=['product:'+top+':sales']
        result['quantity']=str(sum(p['quantity'] for p in products.values()))
    return {'required':required,'metrics':result,'basis':None}
