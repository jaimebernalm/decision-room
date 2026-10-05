"""Exact disposition obligations and narrowly proved impossible review demands."""
from .panorama_contract import enabled as panorama_enabled, gap_keys, validate

VERSION = 'panorama-obligation-guard-v1'


def enabled(context):
    return bool(context.get('budgets', {}).get('panorama_obligation_guard'))


def obligations(context):
    keys = gap_keys(context) if panorama_enabled(context) else []
    return dict(field='report.panorama_dispositions', required_gap_keys=keys,
        allowed_gap_keys=keys, required_count=len(keys), other_signals_require_disposition=False,
        explanation=('Una disposición por cada hueco material listado; los mayores cambios no son huecos.' if keys else
                     'Ninguna disposición requerida: no hay huecos materiales. Los mayores cambios no requieren disposición.'))


def constrain(schema, context):
    # Flag-off wire contracts remain unchanged, including enum values.
    if not enabled(context):
        field = schema['$defs']['RequestedChange']['properties']['field']
        field['enum'] = [v for v in field['enum'] if v != 'panorama_dispositions']


def impossible_demand(issue, context):
    if not enabled(context) or not panorama_enabled(context):
        return None
    change = issue.get('requested_change') or {}
    if change.get('field') != 'panorama_dispositions' or type(change.get('minimum_count')) is not int:
        return None
    expected = obligations(context)
    if change['minimum_count'] <= expected['required_count']:
        return None
    # A demand for extra entries is not permission to waive missing/invalid real
    # obligations, unsupported dismissals or false priority evidence.
    try:
        validate(context['report'], context)
    except (ValueError, KeyError, TypeError):
        return None
    return dict(field=expected['field'], requested_minimum=change['minimum_count'],
        allowed_gap_keys=expected['allowed_gap_keys'], exact_count=expected['required_count'],
        reason='El contrato prohíbe añadir disposiciones para señales que no sean los huecos materiales enumerados.')


SYSTEM = '''
EXACT PANORAMA OBLIGATIONS:
Read panorama_obligations.required_gap_keys: exactly those MATERIAL GAPS need a
panorama_dispositions entry. Largest changes, totals and other signals NEVER need
such entries. If required_count is zero, the empty mapping (empty wire list with
stable-prefix mode) is correct. Do not count all panorama signals as required gaps.
For an issue demanding more dispositions use requested_change.field=
"panorama_dispositions" and minimum_count=the exact requested count. Do not mix
this request with claims about false numbers or evidence; use separate issues.
The controller independently verifies the exact contract and existing dispositions.
An impossible extra-entry request is inapplicable even if labelled integrity;
unsupported claims, bad citations and missing real dispositions remain blocking.
The original objection and controller proof remain in the audit, never disguised
as approval from the reviewer.
'''
