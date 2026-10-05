"""Mandatory panorama decisions, with context-bound keys and evidence references."""
from copy import deepcopy
from typing import Literal
from pydantic import Field
from .contracts import Strict
from .delivery_contract import MetricRef
from ..panorama_presentation import refs, signals


class GapPriority(Strict):
    disposition: Literal['priority']
    claim_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    reason: str = Field(min_length=20, max_length=800, pattern=r'\S')


class GapDismissal(Strict):
    disposition: Literal['dismissed']
    claim_key: None
    reason: str = Field(min_length=20, max_length=800, pattern=r'\S')


class PanoramaPriority(Strict):
    alternative: str = Field(min_length=20, max_length=800, pattern=r'\S', description='Larger or more serious alternative in the panorama, or explain why none is established.')
    why_first: str = Field(min_length=20, max_length=1000, pattern=r'\S', description='Why this finding merits attention relative to that alternative and the owner goal; descriptive findings may explain why no action priority is assigned.')
    evidence: list[MetricRef] = Field(min_length=1, max_length=6)


def enabled(context):
    return context.get('budgets', {}).get('sales_panorama_contract') == 2


def panorama(context):
    return context.get('sales_panorama') or {}


def gap_keys(context):
    view = panorama(context)
    return [item['key'] for item in view.get('signals', []) if item['kind'] == 'gap'] if 'signals' in view else [item['key'] for item in signals(view)]


def metric_choices(context):
    # The compact view contains the same references, under 'reference'. Resolve
    # against current observations too so stale snapshots cannot grant citations.
    available = {(o['execution_id'], key) for o in context.get('observations', [])
                 if o.get('current') and o.get('status') == 'completed'
                 for key in (o.get('result') or {}).get('metrics', {})}
    return [r for r in refs(panorama(context)) if (r['execution_id'],r['metric']) in available]


def constrain(schema, context):
    report = schema['$defs']['ReportDraft']['properties']
    claim = schema['$defs']['Claim']['properties']
    keys = gap_keys(context) if enabled(context) else []
    decision = {'anyOf':[{'$ref':'#/$defs/GapPriority'}, {'$ref':'#/$defs/GapDismissal'}]}
    report['panorama_dispositions'] = dict(type='object', additionalProperties=False,
        properties={key:deepcopy(decision) for key in keys}, required=keys)
    choices = metric_choices(context) if enabled(context) else []
    if choices:
        branches = []
        by_execution = {}
        for ref in choices: by_execution.setdefault(ref['execution_id'], []).append(ref['metric'])
        for execution, metrics in sorted(by_execution.items()):
            branches.append(dict(type='object',additionalProperties=False,
                properties=dict(execution_id=dict(type='string',enum=[execution]),metric=dict(type='string',enum=sorted(set(metrics)))),
                required=['execution_id','metric']))
        schema['$defs']['PanoramaMetric'] = {'anyOf':branches}
        schema['$defs']['PanoramaPriority']['properties']['evidence']['items'] = {'$ref':'#/$defs/PanoramaMetric'}
        claim['panorama_priority'] = {'$ref':'#/$defs/PanoramaPriority'}
    else:
        claim['panorama_priority'] = {'type':'null'}


def validate(report, context):
    if not enabled(context): return
    decisions = report.get('panorama_dispositions', {})
    if set(decisions) != set(gap_keys(context)):
        raise ValueError('panorama_dispositions must address every detected gap exactly once: ' + ', '.join(gap_keys(context)))
    claims = {c['key'] for c in report['claims']}
    for key, decision in decisions.items():
        if decision['disposition'] == 'priority' and decision['claim_key'] not in claims:
            raise ValueError(f'Panorama gap {key}: priority must reference a finding in this report. Valid claim_keys: ' + ', '.join(sorted(claims)))
    choices = {(r['execution_id'],r['metric']) for r in metric_choices(context)}
    for claim in report['claims']:
        comparison = claim.get('panorama_priority')
        if choices and not comparison:
            raise ValueError('Every finding needs panorama_priority comparing attention with a panorama alternative.')
        if comparison and (not choices or any((r['execution_id'],r['metric']) not in choices for r in comparison['evidence'])):
            raise ValueError('panorama_priority must cite current panorama metrics from the context.')
