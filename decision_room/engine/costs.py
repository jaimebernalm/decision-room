"""Versioned public-price estimates and the conservative per-run dollar ceiling.

Estimates are never invoices. The ceiling is a proven upper bound, not an estimate: every
token a run may be charged is priced at the most expensive rate of the catalogue.
"""
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


# Most expensive rate per token class in this catalogue (long context; cache writes cost
# more than plain input). Admission charges reservations, retries and uncertain calls
# against the token limits, so pricing those limits at these rates bounds a run in USD.
CEILING_MODELS = ('gpt-6-luna',)
WORST_INPUT, WORST_OUTPUT = Decimal('0.25'), Decimal('0.75')


def ceiling(limits):
    """USD upper bound of a run under its token limits."""
    return (Decimal(limits['input_tokens']) * WORST_INPUT + Decimal(limits['output_tokens']) * WORST_OUTPUT) / 1000000


def fit(limits, cap, model):
    """Token limits whose ceiling is within ``cap`` USD; input is reduced first. Raises if impossible."""
    cap = Decimal(str(cap))
    if model not in CEILING_MODELS:
        raise ValueError('The model has no versioned price for a dollar ceiling.')
    if cap <= 0:
        raise ValueError('The dollar ceiling must be positive.')
    limits = dict(limits)
    room = cap * 1000000 - Decimal(limits['output_tokens']) * WORST_OUTPUT
    if room <= 0:
        raise ValueError('The output limit alone exceeds the dollar ceiling.')
    limits['input_tokens'] = min(limits['input_tokens'], int(room / WORST_INPUT))
    if limits['input_tokens'] <= 0 or ceiling(limits) > cap:
        raise ValueError('No positive token limits fit the dollar ceiling.')
    return limits, {'cap_usd': str(cap), 'bound_usd': str(ceiling(limits)), 'catalogue': VERSION, 'model': model,
                    'worst_rates_per_million': {'input': str(WORST_INPUT), 'output': str(WORST_OUTPUT)}}
