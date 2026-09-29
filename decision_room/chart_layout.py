"""Validated presentation coordinates, independent of numerical evidence.

Legacy adaptation only recognizes an unambiguous category | month grammar. It
never changes values, aggregates observations or rewrites the approved artifact.
"""
import re
import json
from pathlib import Path

CHART_PALETTE = tuple(json.loads(Path(__file__).with_name("chart_palette.json").read_text()))

MONTHS = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def validate_encoding(chart, points):
    encoding = chart.get('encoding')
    if not encoding:
        return
    if chart['kind'] not in ('bar', 'table'):
        raise ValueError('Grouped coordinates require bars or a table.')
    coords, order = encoding['coordinates'], encoding['series_order']
    labels = [p['label'] for p in points]
    if len(coords) != len(labels) or {c['label'] for c in coords} != set(labels):
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
    palette = CHART_PALETTE
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
