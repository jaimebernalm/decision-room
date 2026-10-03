"""Declarative layers resolve saved evidence; rendering never invents a measure."""
from .series import saved_series, evidence_value


def series_refs(chart):
    return ([chart['series']] if chart.get('series') else []) + [layer['series'] for layer in chart.get('layers', [])]


def resolve_chart(chart, observations):
    layers = chart.get('layers') or []
    if not layers:
        saved = saved_series(observations, chart['series']) if chart.get('series') else None
        points = saved['points'] if saved else [dict(label=p['label'], value=evidence_value(observations, p['value'])) for p in chart['points']]
        grain = saved['grain'] if saved and saved['grain'] != 'category' else chart.get('temporal_grain')
        return {**chart, 'temporal_grain': grain}, points
    if chart['kind'] != 'line' or chart['points'] or chart.get('series') or chart.get('encoding') or chart.get('temporal_grain'):
        raise ValueError('Layers require a line chart with points=[], series=null, encoding=null and temporal_grain=null.')
    keys = [layer['key'] for layer in layers]
    names = [layer['name'] for layer in layers]
    if len(set(keys)) != len(keys) or len(set(names)) != len(names):
        raise ValueError('Layer keys and names must be distinct.')
    rows, grains, styles = [], set(), {}
    for layer in layers:
        saved = saved_series(observations, layer['series'])
        grains.add(saved['grain'])
        if saved['unit'] != chart['unit'] or saved['grain'] == 'category':
            raise ValueError('Layers need the same saved unit and calendar grain; do not overlay unlike measures.')
        styles[layer['name']] = {k: layer[k] for k in ('role', 'style', 'weight', 'description')}
        for point in saved['points']:
            label = layer['key'] + ':' + point['label']
            rows.append((point['label'], layer['name'], label, point['value']))
    if len(grains) != 1 or len(rows) > 800:
        raise ValueError('Layers require one calendar grain and at most 800 saved points together.')
    rows.sort(key=lambda row: (row[0], names.index(row[1])))
    points = [dict(label=label, value=value) for _, _, label, value in rows]
    encoding = dict(temporal_grain=next(iter(grains)), category_title='Periodo', series_title='Medida',
                    measure='level', series_order=names, styles=styles,
                    coordinates=[dict(label=label, category=period, series=name) for period, name, label, _ in rows])
    return {**chart, 'encoding': encoding}, points
