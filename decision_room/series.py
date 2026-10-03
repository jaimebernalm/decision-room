"""Bounded series saved by Python; shared validation and evidence resolution."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
import re
from .periods import GRAINS, period_index


def numeric(value):
    if type(value) not in (str, int, float) or len(str(value)) > 100:
        raise ValueError('Expected a finite numeric value.')
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('Expected a finite numeric value.') from error
    if not number.is_finite() or (number and abs(number.adjusted()) > 100):
        raise ValueError('Numeric value outside supported bounds.')
    return number


def validate_series(series, tables):
    if not isinstance(series, dict) or len(series) > 4:
        raise ValueError('At most four saved series per execution.')
    count = 0
    for key, item in series.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,99}', key):
            raise ValueError('Invalid series key.')
        if not isinstance(item, dict) or set(item) - {'derivation'} != {'unit', 'grain', 'points', 'evidence'}:
            raise ValueError('Series require unit, grain, points and evidence.')
        if not isinstance(item['unit'], str) or not 1 <= len(item['unit']) <= 80 or item['grain'] not in (*GRAINS, 'category'):
            raise ValueError('Invalid series unit or grain.')
        points = item['points']
        if not isinstance(points, list):
            raise ValueError('Series points must be a list.')
        if len(points) < 2:
            raise ValueError(f'Series {key} has {len(points)} points; omit this series and use scalar metrics for a single group. Do not invent points.')
        if len(points) > 366:
            raise ValueError(f'Series {key} has {len(points)} points; aggregate longer periods to at most 366 points.')
        count += len(points)
        labels = []
        for point in points:
            if not isinstance(point, dict) or set(point) != {'label', 'value'}:
                raise ValueError('Series points need label and value.')
            label = point['label']
            if not isinstance(label, str) or not 1 <= len(label) <= 100:
                raise ValueError('Invalid series label.')
            if item['grain'] != 'category':
                period_index(label, item['grain'])
            numeric(point['value'])
            labels.append(label)
        if len(set(labels)) != len(labels) or (item['grain'] != 'category' and labels != sorted(labels)):
            raise ValueError('Series labels must be unique; dates must be ordered.')
        evidence = item['evidence']
        if not isinstance(evidence, dict) or set(evidence) != {'tables', 'operation'}:
            raise ValueError('Series require source tables and an operation.')
        if not isinstance(evidence['tables'], list) or not evidence['tables'] or any(type(t) is not str or t not in tables for t in evidence['tables']):
            raise ValueError('Series reference an unauthorized table.')
        if not isinstance(evidence['operation'], str) or not 1 <= len(evidence['operation']) <= 4000:
            raise ValueError('Series must describe aggregation, filters and selection.')
    if count > 800:
        raise ValueError('At most 800 series points per execution.')
    for key, item in series.items():
        if 'derivation' in item:
            validate_derivation(key, item, series)


def validate_derivation(key, item, series):
    """Verify a declared trailing calendar mean against its saved source points."""
    definition = item['derivation']
    fields = {'kind', 'source_series', 'window', 'decimals', 'alignment', 'missing'}
    if not isinstance(definition, dict) or set(definition) != fields:
        raise ValueError('Derivation requires kind, source_series, window, decimals, alignment and missing.')
    if (type(definition['source_series']) is not str or definition['kind'] != 'rolling_mean' or definition['alignment'] != 'trailing'
            or definition['missing'] != 'require_full_window' or type(definition['window']) is not int
            or not 2 <= definition['window'] <= 90 or type(definition['decimals']) is not int
            or not 0 <= definition['decimals'] <= 4):
        raise ValueError('Rolling means use 2–90 trailing calendar days, complete windows and 0–4 decimals.')
    source = series.get(definition['source_series'])
    if not source or definition['source_series'] == key or source.get('derivation'):
        raise ValueError('Rolling mean source must be another saved observed series in this execution.')
    if item['grain'] != 'day' or source['grain'] != 'day' or item['unit'] != source['unit']:
        raise ValueError('A rolling mean needs the source daily grain and unit.')
    if set(item['evidence']['tables']) != set(source['evidence']['tables']):
        raise ValueError('Rolling mean and source must cite the same input tables.')
    observed = {date.fromisoformat(p['label']): numeric(p['value']) for p in source['points']}
    expected = {}
    with localcontext() as context:
        context.prec = 120
        for day in observed:
            days = [day - timedelta(days=offset) for offset in range(definition['window'])]
            if all(d in observed for d in days):
                expected[day.isoformat()] = (sum(observed[d] for d in days) / definition['window']).quantize(
                    Decimal(1).scaleb(-definition['decimals']), rounding=ROUND_HALF_UP)
    actual = {p['label']: numeric(p['value']) for p in item['points']}
    if actual != expected:
        raise ValueError('Rolling mean must match every complete trailing calendar window of the saved source; no zero imputation, lookahead or partial windows.')


def saved_series(observations, ref):
    item = next((o for o in observations if o['execution_id'] == ref['execution_id']), None)
    if not item or not item['current'] or item['status'] != 'completed' or not item.get('result') or item.get('result_omitted'):
        raise ValueError('Series evidence is missing, obsolete, failed or omitted.')
    value = item['result'].get('series', {}).get(ref['series'])
    if value is None:
        raise ValueError('Unknown saved series.')
    validate_series(item['result']['series'], item.get('inputs', {}))
    return value


def evidence_value(observations, ref):
    """Resolve a scalar or an exact saved series point without new computation."""
    if 'series' in ref:
        series = saved_series(observations, ref)
        point = next((p for p in series['points'] if p['label'] == ref.get('label')), None)
        if point is None:
            raise ValueError('Unknown saved series label.')
        return point['value']
    item = next((o for o in observations if o['execution_id'] == ref['execution_id']), None)
    if not item or not item['current'] or item['status'] != 'completed' or not item.get('result') or item.get('result_omitted'):
        raise ValueError('Evidence is missing, failed, obsolete or omitted.')
    payload = item['result']
    key = ref['metric']
    if key not in payload['metrics'] or not any(e['metric'] == key for e in payload['evidence']):
        raise ValueError('Metric or its source evidence does not exist.')
    return payload['metrics'][key]


def evidence_label(ref):
    return ref['label'] if 'series' in ref else ref['metric']


def evidence_key(ref):
    return (ref['execution_id'], ref.get('metric'), ref.get('series'), ref.get('label'))
