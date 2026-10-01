"""Explicit calendar coordinates shared by evidence, renderers and exports."""
from datetime import date
import re

GRAINS = ('day', 'month', 'quarter', 'year')


def period_index(label, grain):
    if grain == 'day':
        value = date.fromisoformat(label)
        if value.isoformat() == label:
            return value.toordinal()
    elif grain == 'month' and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', label):
        date.fromisoformat(label + '-01')
        return int(label[:4]) * 12 + int(label[5:]) - 1
    elif grain == 'quarter' and re.fullmatch(r'\d{4}-Q[1-4]', label):
        date(int(label[:4]), 1, 1)
        return int(label[:4]) * 4 + int(label[-1]) - 1
    elif grain == 'year' and re.fullmatch(r'\d{4}', label):
        date(int(label), 1, 1)
        return int(label)
    raise ValueError(f'Invalid {grain} period: {label}.')


def infer_grain(labels):
    for grain in GRAINS:
        try:
            for label in labels:
                period_index(label, grain)
            return grain
        except ValueError:
            continue
    raise ValueError('Line charts require explicit ordered calendar periods, not arbitrary categories.')


def validate_periods(labels, grain):
    if grain not in GRAINS:
        raise ValueError('Unsupported temporal grain.')
    indices = [period_index(label, grain) for label in labels]
    if indices != sorted(set(indices)):
        raise ValueError('Calendar periods must be unique and chronologically ordered.')
    return indices
