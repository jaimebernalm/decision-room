"""Bounded series saved by Python; shared validation and evidence resolution."""
from datetime import date
from decimal import Decimal, InvalidOperation
import re


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
        if not isinstance(item, dict) or set(item) != {'unit', 'grain', 'points', 'evidence'}:
            raise ValueError('Series require unit, grain, points and evidence.')
        if not isinstance(item['unit'], str) or not 1 <= len(item['unit']) <= 80 or item['grain'] not in ('day', 'month', 'category'):
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
            if item['grain'] == 'day' and date.fromisoformat(label).isoformat() != label:
                raise ValueError('Daily series require ISO dates.')
            if item['grain'] == 'month' and (not re.fullmatch(r'\d{4}-\d{2}', label) or date.fromisoformat(label + '-01').strftime('%Y-%m') != label):
                raise ValueError('Monthly series require YYYY-MM.')
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


def saved_series(observations, ref):
    item = next((o for o in observations if o['execution_id'] == ref['execution_id']), None)
    if not item or not item['current'] or item['status'] != 'completed' or not item.get('result') or item.get('result_omitted'):
        raise ValueError('Series evidence is missing, obsolete, failed or omitted.')
    value = item['result'].get('series', {}).get(ref['series'])
    if value is None:
        raise ValueError('Unknown saved series.')
    validate_series({ref['series']: value}, item.get('inputs', {}))
    return value
