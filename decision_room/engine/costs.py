"""Versioned public-price estimates, never invoices or automatic dollar caps."""
from decimal import Decimal

VERSION = 'openai-standard-2026-10-07'
SOURCES = ['https://developers.openai.com/api/docs/models/gpt-6-luna',
           'https://developers.openai.com/api/docs/pricing',
           'https://developers.openai.com/api/docs/guides/prompt-caching']


def capture(response, *, requested_model, requested_tier):
    response = response if isinstance(response, dict) else {}
    usage = response.get('usage') or {}
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get('input_tokens_details') or {}
    details = details if isinstance(details, dict) else {}
    def count(value):
        return value if type(value) is int and value >= 0 else None
    def label(value):
        return value if isinstance(value, str) and len(value) <= 128 else None
    return {'requested_model': requested_model, 'requested_tier': requested_tier,
            'effective_model': label(response.get('model')), 'effective_tier': label(response.get('service_tier')),
            'input': count(usage.get('input_tokens')), 'output': count(usage.get('output_tokens')),
            'cache_read': count(details.get('cached_tokens')), 'cache_write': count(details.get('cache_write_tokens'))}


def estimate(measured):
    result = {'version': VERSION, 'currency': 'USD', 'status': 'unavailable', 'cost': None,
              'sources': SOURCES, 'assumptions': ['Standard public catalogue; no regional or negotiated pricing.']}
    if not measured:
        return result
    model = measured.get('effective_model')
    if (measured.get('requested_model') != 'gpt-6-luna' or not isinstance(model, str)
            or not (model == 'gpt-6-luna' or model.startswith('gpt-6-luna-'))
            or measured.get('effective_tier') != 'default'):
        return result
    names = ('input', 'output', 'cache_read', 'cache_write')
    if any(type(measured.get(k)) is not int or measured[k] < 0 for k in names):
        return result
    total, output, read, written = (measured[k] for k in names)
    if read + written > total:
        return result
    long = total > 272000
    rates = dict(zip(('input', 'cache_read', 'cache_write', 'output'),
                     ('0.20', '0.02', '0.25', '0.75') if long else ('0.10', '0.01', '0.125', '0.50')))
    price = ((total-read-written)*Decimal(rates['input']) + read*Decimal(rates['cache_read'])
             + written*Decimal(rates['cache_write']) + output*Decimal(rates['output'])) / 1000000
    return {**result, 'status': 'estimated', 'cost': str(price), 'long_context': long, 'rates_per_million': rates}


def aggregate(calls):
    estimates = [c.get('cost_catalog') or estimate(None) for c in calls]
    known = [Decimal(e['cost']) for e in estimates if e['cost'] is not None]
    complete = len(known) == len(calls)
    return {'version': VERSION, 'currency': 'USD', 'status': 'estimated' if complete else 'incomplete',
            'cost': str(sum(known, Decimal(0))) if complete else None,
            'known_cost': str(sum(known, Decimal(0))), 'unpriced_calls': len(calls)-len(known),
            'sources': SOURCES, 'assumptions': ['Catalogue estimate, not an invoice or a dollar cap.']}
