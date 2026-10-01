"""Validated presentation coordinates, independent of numerical evidence.

Legacy adaptation only recognizes an unambiguous category | month grammar. It
never changes values, aggregates observations or rewrites the approved artifact.
"""
import re
import json
from pathlib import Path
from .periods import validate_periods

_palette = json.loads(Path(__file__).with_name("chart_palette.json").read_text())
CHART_SERIES_PALETTE = tuple(_palette["series"])
CHART_NEUTRALS = _palette["neutrals"]
CHART_PALETTE = CHART_SERIES_PALETTE + tuple(CHART_NEUTRALS.values())

MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def validate_encoding(chart, points):
    encoding = chart.get('encoding')
    if not encoding:
        return
    if chart['kind'] == 'line':
        grain = encoding.get('temporal_grain')
        if not grain:
            raise ValueError('Grouped lines require explicit temporal_grain and period categories.')
        validate_periods(list(dict.fromkeys(c['category'] for c in encoding['coordinates'])), grain)
        if chart.get('temporal_grain') and chart['temporal_grain'] != grain:
            raise ValueError('Incompatible temporal grains.')
    coords, order = encoding['coordinates'], encoding['series_order']
    labels = [p['label'] for p in points]
    if len(coords) != len(labels) or len({c['label'] for c in coords}) != len(coords) or {c['label'] for c in coords} != set(labels):
        raise ValueError('Coordinates must map every saved point exactly once.')
    if len({(c['category'], c['series']) for c in coords}) != len(coords):
        raise ValueError('Duplicate category/series cell.')
    if len(set(order)) != len(order) or set(order) != {c['series'] for c in coords}:
        raise ValueError('Series order must contain each used series exactly once.')
    if all(re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', s) for s in order) and order != sorted(order):
        raise ValueError('Monthly series must be in chronological order.')


def panels(chart, points):
    if chart.get('encoding'):
        validate_encoding(chart, points)
        return [dict(title='', **chart['encoding'])]
    if chart['kind'] != 'bar':
        return []
    # A terminal ISO month is also an explicit legacy category/period coordinate.
    iso = [re.fullmatch(r'(.+) (\d{4}-(?:0[1-9]|1[0-2]))', p['label']) for p in points]
    if iso and all(iso):
        order = sorted({m[2] for m in iso})
        coords = [dict(label=p['label'], category=m[1], series=m[2]) for p, m in zip(points, iso)]
        if len(order) <= 6 and len({(c['category'], c['series']) for c in coords}) == len(coords):
            return [dict(title='', category_title='Categoría', series_title='Mes', measure='level', series_order=order, coordinates=coords)]
    # Compatibility for old saved charts, not an inference engine for new ones.
    groups = {'level': [], 'change': []}
    for point in points:
        parts = point['label'].split(' | ')
        if len(parts) != 2 or not parts[0].strip():
            return []
        category, period = parts
        if period in MONTHS:
            kind = 'level'
        elif period.startswith('cambio ') and len(pair := period[7:].split('-')) == 2 and all(p in MONTHS for p in pair) and MONTHS.index(pair[1]) == MONTHS.index(pair[0]) + 1:
            kind = 'change'
        else:
            return []
        groups[kind].append(dict(label=point['label'], category=category, series=period))
    result = []
    for kind, coords in groups.items():
        if not coords:
            continue
        order = sorted({c['series'] for c in coords}, key=lambda s: MONTHS.index(s if kind == 'level' else s[7:].split('-')[0]))
        if len(order) > 6 or len({(c['category'], c['series']) for c in coords}) != len(coords):
            return []
        result.append(dict(title='Cantidades por mes' if kind == 'level' else 'Variación entre meses',
                           category_title='Categoría', series_title='Periodo', measure=kind,
                           series_order=order, coordinates=coords))
    return result


def series_colors(labels):
    """One report-wide legend using only the fixed product palette."""
    palette = CHART_SERIES_PALETTE
    result = {}
    for label in sorted(set(labels)):
        if label in MONTHS:
            index = MONTHS.index(label)
        else:
            index = 0
            for character in label:
                index = (index * 31 + ord(character)) & 0xffffffff
        color = palette[index % len(palette)]
        if color in result.values():
            color = next((c for c in palette if c not in result.values()), palette[index % len(palette)])
        result[label] = color
    return result


def temporal_cells(chart, points, values):
    """Resolve presentation coordinates only; never aggregate or impute values."""
    from .periods import infer_grain, validate_periods
    encoding = chart.get('encoding') or next(iter(chart.get('panels') or []), None)
    saved = dict(zip((p['label'] for p in points), values))
    if encoding:
        categories = list(dict.fromkeys(c['category'] for c in encoding['coordinates']))
        grain = encoding['temporal_grain']
        cells = {(c['category'], c['series']): saved[c['label']] for c in encoding['coordinates']}
        order = encoding['series_order']
    else:
        categories = [p['label'] for p in points]
        grain = chart.get('temporal_grain') or infer_grain(categories)
        order = ['Valor']
        cells = {(p['label'], 'Valor'): v for p, v in zip(points, values)}
    return grain, categories, validate_periods(categories, grain), order, cells


def comparison_tables(chart, points, formatted_values):
    layout = chart.get('panels') or panels(chart, points)
    if not layout:
        return [('', ['Periodo / categoría', chart['unit']], [[p['label'], v] for p, v in zip(points, formatted_values)])]
    saved = dict(zip((p['label'] for p in points), formatted_values))
    tables = []
    for panel in layout:
        categories = list(dict.fromkeys(c['category'] for c in panel['coordinates']))
        cells = {(c['category'], c['series']): saved[c['label']] for c in panel['coordinates']}
        tables.append((panel.get('title', ''), [panel['category_title'], *panel['series_order']],
                       [[category, *[cells.get((category, name), 'Sin dato') for name in panel['series_order']]] for category in categories]))
    return tables
