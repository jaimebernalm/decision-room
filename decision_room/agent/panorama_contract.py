"""Mandatory panorama decisions, with context-bound keys and evidence references."""
from copy import deepcopy
from typing import Literal
from pydantic import Field
from .contracts import Strict
from .delivery_contract import MetricRef
from ..panorama_presentation import refs, material_gaps, focal_dimensions


class GapPriority(Strict):
    disposition: Literal['priority']
    claim_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    reason: str = Field(min_length=20, max_length=800, pattern=r'\S')


class GapEvidenceProof(Strict):
    kind: Literal['evidence']
    verified_fact: str = Field(min_length=20, max_length=800, pattern=r'\S')
    evidence: list[MetricRef] = Field(min_length=1, max_length=6)


class GapOwnerProof(Strict):
    kind: Literal['owner']
    verified_fact: str = Field(min_length=20, max_length=800, pattern=r'\S')
    source: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class GapDismissal(Strict):
    disposition: Literal['dismissed']
    claim_key: None
    proof: GapEvidenceProof | GapOwnerProof | None = None
    reason: str = Field(min_length=20, max_length=800, pattern=r'\S')


class PanoramaComparison(Strict):
    basis: Literal['panorama', 'none']


class CustomComparison(Strict):
    basis: Literal['custom']
    periods: str = Field(min_length=5, max_length=200, pattern=r'\S')
    reason: str = Field(min_length=20, max_length=500, pattern=r'\S')


class PanoramaPriority(Strict):
    comparison: PanoramaComparison | CustomComparison | None = None
    alternative: str = Field(min_length=20, max_length=800, pattern=r'\S', description='Larger or more serious alternative in the panorama, or explain why none is established.')
    why_first: str = Field(min_length=20, max_length=1000, pattern=r'\S', description='Why this finding merits attention relative to that alternative and the owner goal; descriptive findings may explain why no action priority is assigned.')
    evidence: list[MetricRef] = Field(min_length=1, max_length=6)


def enabled(context):
    budget = context.get('budgets', {})
    return bool(budget.get('sales_panorama') or budget.get('sales_panorama_contract', 0) >= 2)


def panorama(context):
    return context.get('sales_panorama') or {}


def gap_keys(context):
    return [item['key'] for item in material_gaps(panorama(context), context.get('observations', []))]


def metric_choices(context):
    # The compact view contains the same references, under 'reference'. Resolve
    # against current observations too so stale snapshots cannot grant citations.
    available = {(o['execution_id'], key) for o in context.get('observations', [])
                 if o.get('current') and o.get('status') == 'completed'
                 for key in (o.get('result') or {}).get('metrics', {})}
    return [r for r in refs(panorama(context)) if (r['execution_id'],r['metric']) in available]


def owner_sources(context):
    sources={}
    if isinstance(context.get('owner_context'), str) and context['owner_context'].strip():
        sources['owner_context']=context['owner_context']
    for index, answer in enumerate(context.get('owner_answers', [])):
        if answer.get('disposition') == 'answered' and answer.get('text'):
            sources[f'owner_answers/{index}']=answer['text']
    for event in context.get('conversation', []):
        answer=event.get('owner_answer') or {}
        if answer.get('disposition') == 'answered' and answer.get('text'):
            sources[f'review_answers/{event["step"]}']=answer['text']
    return sources


def supporting_metrics(context):
    # The absence itself does not verify a reason to ignore it. Require a separate
    # current calculation, or an exact statement from the owner.
    panorama_refs={(r['execution_id'],r['metric']) for r in refs(panorama(context))}
    return [dict(execution_id=o['execution_id'],metric=k) for o in context.get('observations', [])
        if o.get('current') and o.get('status') == 'completed' and not str(o.get('origin', '')).startswith('sales-panorama-')
        for k in (o.get('result') or {}).get('metrics', {})
        if (o['execution_id'],k) not in panorama_refs and any(e.get('metric')==k for e in (o.get('result') or {}).get('evidence', []))]


def reference_schema(choices):
    groups={}
    for ref in choices:groups.setdefault(ref['execution_id'],[]).append(ref['metric'])
    return {'anyOf':[dict(type='object',additionalProperties=False,
        properties=dict(execution_id=dict(type='string',enum=[execution]),metric=dict(type='string',enum=sorted(set(metrics)))),
        required=['execution_id','metric']) for execution,metrics in sorted(groups.items())]}


def matches(claim, gap):
    return any(scope['table_id']==gap['table_id'] and scope['product']==gap.get('product')
        and scope['channel']==gap.get('channel') for scope in claim.get('focal_combinations', []))


def constrain(schema, context):
    report = schema['$defs']['ReportDraft']['properties']
    claim = schema['$defs']['Claim']['properties']
    keys = gap_keys(context) if enabled(context) else []
    decision = {'anyOf':[{'$ref':'#/$defs/GapPriority'}]}
    if enabled(context):
        claim['focal_combinations']['minItems']=1
        scopes=[]
        for table_id, dimensions in focal_dimensions(panorama(context)).items():
            props={'table_id':{'type':'string','enum':[table_id]}}
            for name in ('product','channel'):
                values=dimensions[name]
                props[name]={'anyOf':[{'type':'string','enum':values,'minLength':1,'maxLength':500},{'type':'null'}]} if values else {'anyOf':[{'type':'string','minLength':1,'maxLength':500},{'type':'null'}]}
            scopes.append(dict(type='object',additionalProperties=False,properties=props,required=list(props)))
        if scopes:
            schema['$defs']['FocalCombination']={'anyOf':scopes}
        proofs=[]
        supporting=supporting_metrics(context)
        if supporting:
            schema['$defs']['GapSupportingMetric']=reference_schema(supporting)
            schema['$defs']['GapEvidenceProof']['properties']['evidence']['items']={'$ref':'#/$defs/GapSupportingMetric'}
            proofs.append({'$ref':'#/$defs/GapEvidenceProof'})
        owners=owner_sources(context)
        if owners:
            schema['$defs']['GapOwnerProof']={'anyOf':[
                dict(type='object',additionalProperties=False,properties=dict(
                    kind=dict(type='string',enum=['owner']),
                    verified_fact=dict(type='string',minLength=20,maxLength=800,pattern=r'\S'),
                    source=dict(type='string',enum=[source]),quote=dict(type='string',enum=[quote])),
                    required=['kind','verified_fact','source','quote']) for source,quote in owners.items()]}
            proofs.append({'$ref':'#/$defs/GapOwnerProof'})
        dismissal=schema['$defs']['GapDismissal']
        if proofs:
            dismissal['properties']['proof']={'anyOf':proofs}
            decision['anyOf'].append({'$ref':'#/$defs/GapDismissal'})

    dismissal=schema['$defs']['GapDismissal']
    dismissal['required']=list(dismissal['properties'])
    dismissal['properties']['proof'].pop('default',None)
    report['panorama_dispositions'] = dict(type='object', additionalProperties=False,
        properties={key:deepcopy(decision) for key in keys}, required=keys)
    choices = metric_choices(context) if enabled(context) else []
    priority=schema['$defs']['PanoramaPriority']
    priority['required']=list(priority['properties'])
    priority['properties']['comparison'].pop('default',None)
    if choices:
        priority['properties']['comparison']={'anyOf':[{'$ref':'#/$defs/PanoramaComparison'},{'$ref':'#/$defs/CustomComparison'}]}
        schema['$defs']['PanoramaMetric'] = reference_schema(choices)
        schema['$defs']['PanoramaPriority']['properties']['evidence']['items'] = {'$ref':'#/$defs/PanoramaMetric'}
        claim['panorama_priority'] = {'$ref':'#/$defs/PanoramaPriority'}
    elif enabled(context) and any(t.get('status', 'available') == 'available' for t in panorama(context).get('tables', [])):
        raise ValueError('Available panorama has no current evidence; refresh the frozen snapshot before writing.')
    else:
        claim['panorama_priority'] = {'type':'null'}


def validate(report, context):
    if not enabled(context): return
    decisions = report.get('panorama_dispositions', {})
    if set(decisions) != set(gap_keys(context)):
        raise ValueError('panorama_dispositions must address every material gap exactly once: ' + ', '.join(gap_keys(context)))
    claims = {c['key'] for c in report['claims']}
    gaps = {g['key']:g for g in material_gaps(panorama(context), context.get('observations', []))}
    supporting = {(r['execution_id'],r['metric']) for r in supporting_metrics(context)}
    owners = owner_sources(context)
    for key, decision in decisions.items():
        if decision['disposition'] == 'priority' and decision['claim_key'] not in claims:
            raise ValueError(f'Panorama gap {key}: priority must reference a finding in this report. Valid claim_keys: ' + ', '.join(sorted(claims)))
        linked=[c['key'] for c in report['claims'] if matches(c,gaps[key])]
        if linked and (decision['disposition'] != 'priority' or decision['claim_key'] not in linked):
            raise ValueError(f'Gap {key} must link to its existing focal finding: ' + ', '.join(linked))
        if decision['disposition'] == 'priority':
            GapPriority.model_validate(decision)
            target=next(c for c in report['claims'] if c['key']==decision['claim_key'])
            if not any(scope['table_id']==gaps[key]['table_id'] and all(scope[name] is None or scope[name]==gaps[key].get(name)
                       for name in ('product','channel')) for scope in target.get('focal_combinations', [])):
                raise ValueError(f'Gap {key}: linked finding must cover its source and combination.')
        else:
            proof=GapDismissal.model_validate(decision).proof
            if proof is None:
                raise ValueError('A material gap needs verifiable proof to dismiss it; lack of causality is not a reason.')
            if proof.kind=='owner':
                if owners.get(proof.source) != proof.quote:
                    raise ValueError('Dismissal must quote an exact current owner source.')
            elif any((r.execution_id,r.metric) not in supporting for r in proof.evidence):
                raise ValueError('Dismissal evidence must be a current separate calculation, not the gap itself.')
    choices = {(r['execution_id'],r['metric']) for r in metric_choices(context)}
    if not choices and any(t.get('status', 'available') == 'available' for t in panorama(context).get('tables', [])):
        raise ValueError('Available panorama has no current evidence.')
    for claim in report['claims']:
        if len(claim.get('focal_combinations', [])) != 1:
            raise ValueError('Each panorama claim must declare one focal combination; split distinct priorities.')
        for scope in claim['focal_combinations']:
            dimensions=focal_dimensions(panorama(context))
            if dimensions and scope['table_id'] not in dimensions:
                raise ValueError('Focal table must belong to the available panorama.')
            for name, values in dimensions.get(scope['table_id'], {}).items():
                if values and scope[name] is not None and scope[name] not in values:
                    raise ValueError(f'Focal {name} must be one recorded value, not mixed combinations: {values}')
        comparison = claim.get('panorama_priority')
        if choices and not comparison:
            raise ValueError('Every finding needs panorama_priority comparing attention with a panorama alternative.')
        if comparison:
            parsed=PanoramaPriority.model_validate(comparison)
            if parsed.comparison is None:
                raise ValueError('panorama_priority needs comparison basis; custom periods need a plain reason.')
        if comparison and (not choices or any((r['execution_id'],r['metric']) not in choices for r in comparison['evidence'])):
            raise ValueError('panorama_priority must cite current panorama metrics from the context.')
