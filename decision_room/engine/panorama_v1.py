"""Deterministic v1-style sales overview for the HTML engine. No model, no diagnostics to the agent.

The trial panorama files came from a script that was not saved. This renderer keeps
their layout and calculation (``sales_panorama``) and differs in one documented
sentence: the count of gaps not shown is the full detected count, without the trial
wording "breves anteriores a <año>", which was not true for every omitted gap.
"""
import re
from datetime import date
from decimal import Decimal

import duckdb

from .. import sales_panorama
from ..csv_ingest import identifier
from ..storage import Storage, digest

VERSION = 'panorama-v1-product-1'
HEADER = '# Panorama de ventas (calculado automáticamente)'
NOTE = 'Los huecos indican ausencia de registros, no ventas cero ni una causa confirmada.'
NAME_COLUMNS = {'nombre', 'name'}
VISIBLE_GAPS = 5
MAX_LABELS = 500
MAX_BYTES = 256 * 1024
MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
COMPARISON = {
    'year_to_date_same_months': 'Comparamos el año hasta el último mes completo con los mismos meses del año anterior para respetar la temporada.',
    'three_months_previous_three': 'Comparamos los últimos tres meses completos con los tres anteriores para ver el cambio reciente.',
    'month_previous_month': 'Comparamos el último mes completo con el anterior porque no hay dos periodos completos de tres meses; no ajusta la temporada.',
}


def unavailable(reason):
    # The reason stays in the run provenance; the agent never receives it.
    return dict(version=VERSION, status='unavailable', reason=reason)


def day(value):
    parsed = date.fromisoformat(value)
    return f'{parsed.day} de {MONTHS[parsed.month - 1]} de {parsed.year}'


def number(value):
    """Exact Spanish grouping; no arithmetic, so no context precision can round it."""
    text = format(Decimal(str(value)), 'f')
    sign, text = ('-', text[1:]) if text.startswith('-') else ('', text)
    whole, _, fraction = text.partition('.')
    fraction = fraction.rstrip('0')
    grouped = f'{int(whole):,}'.replace(',', '.')
    return ('' if grouped == '0' and not fraction else sign) + grouped + (',' + fraction if fraction else '')


def labels(db, path, key):
    """Code -> name from one catalog column pair; None unless it is unique and exact."""
    rows = db.execute(f'SELECT CAST({identifier(key[0])} AS VARCHAR), CAST({identifier(key[1])} AS VARCHAR) '
                      f'FROM read_parquet(?) LIMIT {MAX_LABELS + 1}', [str(path)]).fetchall()
    if not rows or len(rows) > MAX_LABELS:
        return None
    found = {}
    for code, name in rows:
        if code is None or name is None or not name.strip() or code in found:
            return None
        found[code] = name.strip()
    return found


def catalogs(config, business, sales, tables):
    """Names for product and channel codes when exactly one catalog covers every code.

    A catalog has the sales key column under the same name and one name column. This
    only names codes; it never joins quantities or adds measures.
    """
    storage = Storage(config.storage)
    selected = sales_panorama.mapping([c['name'] for c in sales['columns']])
    result, provenance = {}, {}
    with duckdb.connect(config={'threads': 2, 'memory_limit': '256MB', 'max_temp_directory_size': '0B'}) as db:
        source = storage.path(business, sales['parquet_key'])
        for role in ('product', 'channel'):
            column = selected[role]
            codes = {r[0] for r in db.execute(f'SELECT DISTINCT CAST({identifier(column)} AS VARCHAR) FROM read_parquet(?)',
                                              [str(source)]).fetchall()}
            matches = []
            for table in tables:
                if table['id'] == sales['id']:
                    continue
                names = [c['name'] for c in table['columns']]
                named = [n for n in names if sales_panorama.normalized(n) in NAME_COLUMNS]
                if column not in names or len(named) != 1:
                    continue
                path = storage.path(business, table['parquet_key'])
                if digest(path) != table['parquet_sha256']:
                    raise ValueError('Catalog changed while preparing the panorama.')
                found = labels(db, path, (column, named[0]))
                if found is not None and codes <= set(found):
                    matches.append((table, found))
            if len(matches) == 1:
                table, found = matches[0]
                result[role] = found
                provenance[role] = dict(table_id=str(table['id']), parquet_sha256=table['parquet_sha256'])
    return result, provenance


def material(gaps, end):
    """Open at the end, or recent and channel-wide / >=7 expected days / a whole month."""
    chosen = []
    for gap in gaps:
        stop = date.fromisoformat(gap['end'])
        opened = stop >= end
        recent = (end - stop).days <= 365
        expected = int(gap.get('absent_expected_days') or 0)
        months = int(gap.get('absent_months') or 0)
        if (opened or recent) and (opened or 'product' not in gap or expected >= 7 or months >= 1):
            chosen.append((-expected, -months, -int(opened), gap['start'], gap.get('product', ''), gap['channel'], gap))
    return [item[-1] for item in sorted(chosen, key=lambda item: item[:-1])]


def render(summary, metrics, names):
    def value(ref):
        return metrics[ref['metric']]

    def name(raw, role):
        if raw in names.get(role, {}):
            return names[role][raw]
        if re.fullmatch(r'(?:[A-Z]{1,5}[0-9]*|[0-9]+)', raw):
            # Keep distinct codes distinguishable without passing them off as names.
            return f'{raw} (código sin nombre verificado)'
        return raw

    def group(item):
        return ' / '.join(name(item[k], k) for k in ('product', 'channel') if k in item)

    lines = [HEADER, f"Del {day(summary['period'][0])} al {day(summary['period'][1])}: "
                     f"{number(value(summary['total']))} unidades registradas."]
    channels = summary['totals'].get('channel', [])
    if channels:
        lines.append('Por canal: ' + '; '.join(f"{group(i)}: {number(value(i['value']))}" for i in channels) + '.')
    comparison = summary['comparison']
    if comparison['status'] == 'available':
        lines.append(COMPARISON[comparison['rule']] +
                     f" Del {day(comparison['before'][0])} al {day(comparison['before'][1])}: {number(value(comparison['before_total']))};"
                     f" del {day(comparison['current'][0])} al {day(comparison['current'][1])}: {number(value(comparison['current_total']))}."
                     f" Cambio: {number(value(comparison['change']))}.")
    else:
        lines.append('No hay un periodo anterior comparable con registros suficientes.')
    for dimension, level in (('channel', 'por canal'), ('product_channel', 'por producto y canal')):
        section = summary['changes'].get(dimension, {})
        for kind, heading in (('increases', 'Mayor aumento'), ('decreases', 'Mayor descenso')):
            if section.get(kind):
                item = section[kind][0]
                lines.append(f"{heading} {level}: {group(item)}, {number(value(item['change']))} unidades registradas.")
    gaps = [{k: (value(v) if isinstance(v, dict) and set(v) == {'metric'} else v) for k, v in g.items()}
            for g in summary['gaps']]
    visible = material(gaps, date.fromisoformat(summary['period'][1]))[:VISIBLE_GAPS]
    detected = sum(int(value(summary[k])) for k in ('channel_gap_count', 'product_channel_gap_count') if k in summary)
    alerts = list(dict.fromkeys(f"- {group(g)}: sin registros del {day(g['start'])} al {day(g['end'])}." for g in visible))
    if alerts:
        lines.append('Huecos de registros relevantes:')
        lines.append('\n'.join(alerts))
    else:
        lines.append('No se detectan huecos de registros relevantes.')
    if detected - len(visible) > 0:
        lines.append(f'Hay otros {number(detected - len(visible))} huecos de registros no incluidos aquí.')
    if alerts:
        lines.append(NOTE)
    return '\n\n'.join(lines) + '\n'


def build(config, business, tables):
    """Return the frozen panorama for these exact prepared tables, or a closed unavailable."""
    candidates = [t for t in tables if sales_panorama.mapping([c['name'] for c in t['columns']])]
    if len(candidates) != 1:
        return unavailable('No hay exactamente una tabla con fecha, producto, canal y cantidad.')
    sales = candidates[0]
    path = Storage(config.storage).path(business, sales['parquet_key'])
    if digest(path) != sales['parquet_sha256']:
        raise ValueError('Sales table changed while preparing the panorama.')
    body = sales_panorama.calculate(path, [c['name'] for c in sales['columns']])
    if body['status'] != 'available':
        return unavailable(body.get('reason') or 'Panorama no disponible.')
    skipped = [l for l in body['summary']['limitations'] if l.startswith(('channel:', 'product:', 'product_channel:'))]
    if skipped:
        # A section over the group limit was not calculated; never present a partial panorama.
        return unavailable(' '.join(skipped))
    names, provenance = catalogs(config, business, sales, tables)
    markdown = render(body['summary'], body['result']['metrics'], names)
    if len(markdown.encode('utf-8')) > MAX_BYTES:
        # Same bound as the engine context input; the agent still has the CSVs.
        return unavailable('El panorama supera el límite de 256 KiB del contexto.')
    return dict(version=VERSION, status='available', markdown=markdown,
                sales=dict(table_id=str(sales['id']), parquet_sha256=sales['parquet_sha256']),
                catalogs=provenance, calculation=sales_panorama.VERSION)
