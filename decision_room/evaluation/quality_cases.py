"""Source-side references. These values are never passed to a model."""
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from .substantial_data import TABLES, OWNER, GOALS, reference as wwi_reference

BRUMA_OWNER = '''Bruma Café es una tienda de café de especialidad y accesorios en
Valencia, con tienda física, web y marketplace. Estos datos son sintéticos.
Unidades es la cantidad registrada en cada fila por fecha, producto y canal.
No sabemos si los importes son por unidad o por fila: excluye importes, márgenes
y retorno de marketing. Aceptamos comparar unidades registradas, sin confirmar
cobertura completa, días de apertura, disponibilidad ni causas externas.
No disponemos de información adicional ni queremos predicciones en este informe.'''
BRUMA_GOAL = '''Identificar qué productos y canales conviene revisar primero y
cómo evolucionan durante el periodo disponible. Profundiza en las señales
relevantes con los datos disponibles y ofrece siguientes comprobaciones concretas.'''
CASES = {**{'wwi-' + key: dict(dataset='wwi', intent=key, owner=OWNER, goal=value)
            for key, value in GOALS.items()},
         'bruma-discover': dict(dataset='bruma', intent='discover', owner=BRUMA_OWNER, goal=BRUMA_GOAL)}


def files(dataset, directory):
    directory = Path(directory)
    return [directory / (n + '.csv') for n in TABLES] if dataset == 'wwi' else sorted(directory.glob('*.csv'))


def bruma_reference(paths):
    tables = []
    for path in paths:
        with path.open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
            if rows:
                tables.append(rows)
    sales = next(t for t in tables if 'unidades' in t[0])
    products = next(t for t in tables if 'categoria' in t[0])
    channels = next(t for t in tables if 'mercado' in t[0])
    def index(rows, key):
        result = {r[key]: r['nombre'] for r in rows}
        if len(result) != len(rows) or '' in result:
            raise ValueError('Non-unique or empty dimension key')
        return result
    pn, cn = index(products, 'producto_id'), index(channels, 'canal_id')
    groups = defaultdict(Decimal)
    days = defaultdict(set)
    for row in sales:
        observed = date.fromisoformat(row['fecha'][:10]).isoformat()
        month = observed[:7]
        product, channel = pn[row['producto_id']], cn[row['canal_id']]
        units = Decimal(row['unidades'])
        if not units.is_finite():
            raise ValueError('Non-finite quantity')
        for key in ('total', f'month|{month}', f'product|{product}', f'channel|{channel}',
                    f'product_month|{product}|{month}', f'channel_month|{channel}|{month}',
                    f'product_channel_month|{product}|{channel}|{month}'):
            groups[key] += units
        days[month].add(observed)
    months = sorted(days)
    first, last = months[0], months[-1]
    for month in months:
        groups[f'days|{month}'] = Decimal(len(days[month]))
        groups[f'daily|{month}'] = groups[f'month|{month}'] / len(days[month])
        for channel in cn.values():
            groups[f'channel_daily|{channel}|{month}'] = groups[f'channel_month|{channel}|{month}'] / len(days[month])
    for dimension, names in [('product', pn.values()), ('channel', cn.values())]:
        for name in names:
            groups[f'{dimension}_change|{name}'] = groups[f'{dimension}_month|{name}|{last}'] - groups[f'{dimension}_month|{name}|{first}']
    for product in pn.values():
        for channel in cn.values():
            groups[f'product_channel_change|{product}|{channel}'] = groups[f'product_channel_month|{product}|{channel}|{last}'] - groups[f'product_channel_month|{product}|{channel}|{first}']
    groups['change'] = groups[f'month|{last}'] - groups[f'month|{first}']
    return {'metrics': dict(groups), 'counts': {'sales': len(sales), 'products': len(pn), 'channels': len(cn)},
            'months': months, 'required': ['month|' + first, 'month|' + last],
            'meaning': 'Quantities only; observed dates, not certified opening days. Join keys validated independently.'}


def reference(dataset, directory):
    if dataset == 'bruma':
        return bruma_reference(files(dataset, directory))
    raw = wwi_reference(Path(directory))
    metrics = {group + ':' + key: value for group, values in raw['groups'].items()
               for key, value in values.items() if value is not None}
    for dimension, values in raw['changes'].items():
        for name, measures in values.items():
            for metric, value in measures.items():
                metrics[f'change:{dimension}:{name}:{metric}'] = value
    for metric in ('sales', 'profit', 'margin_pct', 'invoices', 'average_invoice'):
        a, b = (raw['groups']['year:' + year][metric] for year in ('2014', '2015'))
        metrics['change:year:' + metric] = b - a
        metrics['percent:year:' + metric] = (b - a) / Decimal(a) * 100
    with (Path(directory) / 'Warehouse.StockItems.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            metrics['product_label:' + row['StockItemID']] = row['StockItemID'] + ' | ' + row['StockItemName']
    return {'metrics': metrics, 'counts': raw['counts'], 'required': [f'year:{year}:{metric}'
            for year in ('2014', '2015') for metric in ('sales', 'profit')], 'meaning': raw['scope']}
