"""Opt-in controller closure of stalled editorial reviews; integrity fails closed."""
from copy import deepcopy
from .context import fingerprint

VERSION = 'review-loop-guard-v1'


def enabled(context):
    return bool(context.get('budgets', {}).get('review_loop_guard'))


def limits():
    from .review_contract import ReportDraft
    from .delivery_contract import DecisionOrientation
    return {**{name:ReportDraft.model_json_schema()['properties'][name]['maxItems'] for name in ('claims','charts')},
            'reactions':DecisionOrientation.model_json_schema()['properties']['reactions']['maxItems']}


def draft(event, current):
    report = event['action'].get('report')
    return current if report == {'$ref':'#/report'} else report


def report_at(history, step, current):
    return next((draft(e,current) for e in reversed(history) if e['step'] <= step and e['action']['action']=='submit'), None)


def unchanged_feedback(context):
    submissions=[e for e in context['conversation'] if e['action']['action']=='submit']
    if len(submissions)<2: return None
    last, prior=submissions[-1],submissions[-2]
    if fingerprint(draft(last,context['report'])) != fingerprint(draft(prior,context['report'])): return None
    return dict(submitted_step=last['step'],previous_step=prior['step'],message=last['action']['message'],
        warning='El borrador no cambió respecto a la entrega anterior, aunque el mensaje describa cambios. No afirmes que añadiste algo sin modificar los campos. Si no es posible, explica el límite o divide el hallazgo.')


def resolution(context):
    if not enabled(context) or not context.get('report'): return None
    history=context['conversation']
    reviews=[e for e in history if e['role']=='reviewer' and e['action'].get('assessment')]
    if len(reviews)<2 or reviews[-1]['action']['action'] != 'revise': return None
    last=reviews[-1]
    assessment=last['action']['assessment']
    issues={i['key']:i for i in context.get('review_issues', []) if i['status']=='open' and i['severity']=='blocker'}
    stalled=[]
    for key,issue in issues.items():
        previous=next((e for e in reversed(reviews[:-1]) if any(i['key']==key and i['status']=='open' for i in e['action']['assessment']['issues'])),None)
        if previous is None: continue
        repair=issue.get('requested_change') or {}
        impossible=repair.get('minimum_count') is not None and repair.get('field') in limits() and repair['minimum_count']>limits()[repair['field']]
        unchanged=fingerprint(report_at(history,previous['step'],context['report'])) == fingerprint(context['report'])
        if impossible or unchanged:
            stalled.append(dict(key=key,reason='schema_limit' if impossible else 'unchanged_draft',first_review_step=previous['step'],last_review_step=last['step']))
    if not stalled: return None
    # An unknown classification is not permission to waive an integrity issue.
    unsafe=[i for i in issues.values() if i.get('kind') not in ('presentation','completeness') or i.get('basis')=='evidence_integrity']
    delivery=assessment['delivery']
    blocked=bool(unsafe or any(not c['passed'] for c in context['checks']) or delivery['numbers']=='fail' or delivery['meaning']=='fail' or delivery['charts']=='fail')
    # Do not waive a different, newly raised objection just because one stalled.
    if set(issues)-{i['key'] for i in stalled}: blocked=True
    notes=[]
    for issue in issues.values():
        if issue.get('kind')=='completeness':
            notes.append(issue.get('owner_limitation') or issue['detail'])
        elif issue.get('owner_limitation'):
            notes.append(issue['owner_limitation'])
    return dict(version=VERSION,disposition='blocked_integrity' if blocked else 'publish_with_limitations',
                report_step=context['report_step'],report_sha256=fingerprint(context['report']),
                stalled_issues=stalled,issues=deepcopy(list(issues.values())),
                owner_limitations=list(dict.fromkeys(notes)),
                explanation='El controlador detuvo la repetición; las objeciones originales permanecen abiertas en la auditoría. No es una aprobación del revisor.')


SYSTEM = '''
REVIEW LOOP GUARD:
Read review_schema_limits before asking for additions. If reactions are at their
limit, ask to split genuinely different focal combinations into separate claims
(one priority per claim), replace redundant reactions or state the unresolved
business check. Never demand a fifth reaction in a four-reaction field.
Every issue classifies kind=integrity (false/unsupported number, meaning, evidence,
reaction or claim), presentation, or completeness. evidence_integrity always
remains integrity. requested_change identifies the field and minimum_count only
when requesting a count; otherwise null. owner_limitation is plain owner-language
impact for completeness, and null for purely visual issues. Do not classify false
or unsupported statements as completeness to get them published.
The controller may stop a repeated unchanged editorial request with an audited
qualified delivery; it never treats that as reviewer approval. Integrity still
blocks. Analyst: consult unchanged_submission and change the actual JSON before
saying it was changed. Each claim has one structured focal combination; split
separate priorities. A whole-business description uses null product/channel.
'''
