"""Rebuild the bounded research agenda from immutable, write-ahead actions."""
from copy import deepcopy


class ResearchBudgetReached(ValueError):
    """A normal stopping condition, not a failed model request."""


def score(item):
    priority = item.get('priority')
    if not priority:
        return 0
    return round(priority['relevance'] * priority['magnitude'] * priority['reliability'] / priority['cost'], 3)


def agenda(snapshot, history):
    result = deepcopy(snapshot)
    work = result['proposal']['investigations']
    for item in work:
        item.update(round=1, stage='explore', parent_key=None, basis_metric_keys=[])
    by_key = {item['key']: item for item in work}
    for step in history:
        action = step['action']
        for child in action.get('followups', []):
            if child['key'] in by_key:
                continue
            dependency_rounds = [by_key[key]['round'] for key in child.get('depends_on', []) if key in by_key]
            depth = max([by_key[action['investigation_key']]['round'], *dependency_rounds]) + 1
            item = {**child, 'round': depth,
                    'parent_key': action['investigation_key']}
            work.append(item)
            by_key[item['key']] = item
    # Python's stable sort keeps planning order for equal/missing priorities.
    work.sort(key=lambda i: -score(i))
    return result


def coverage(snapshot, history, recorded, options, reason=''):
    work = agenda(snapshot, history)['proposal']['investigations']
    by_key = {f['investigation_key']: f['status'] for f in recorded}
    discarded = {s['action']['investigation_key']: s['action']['summary'] for s in history
                 if s['action']['action'] == 'discard'}
    attempted = {s['action']['investigation_key'] for s in history if s['action']['action'] == 'execute'}
    items = []
    for item in work:
        key = item['key']
        status = by_key.get(key) or ('discarded' if key in discarded else
                  'awaiting_result' if key in attempted else
                  'pending_definition' if item['status'] == 'blocked' else
                  'not_possible' if item['status'] == 'not_possible' else 'pending')
        closure = next((s['action'].get('closure') for s in reversed(history)
                        if s['action'].get('investigation_key') == key and s['action'].get('closure')), None)
        extra = {'closure': closure, 'closure_status': 'recorded' if closure else 'not_recorded'} if options.get('research_continuity') else {}
        items.append({**item, **extra, 'research_status': status, 'priority_score': score(item),
                      'resolution': discarded.get(key) or next((f['summary'] for f in recorded if f['investigation_key'] == key), '')})
    from .research_recovery import REASON
    recovered = options.get('research_validation_recovery') and (reason == REASON or any(s['action'].get('system_recovery') for s in history))
    extra = {'validation_recovery': True, 'interpretation': 'pending_independent_review'} if recovered else {}
    return {'investigations': items, 'stop_reason': reason, **extra,
            'complete': not recovered and all(i['research_status'] == 'candidate' for i in items),
            'rounds_used': max((i['round'] for i in items if i['key'] in attempted), default=0),
            'executions_requested': sum(s['action']['action'] == 'execute' for s in history),
            'options': options}


def limitation(summary, report):
    """Describe delivered answers, not merely computations that finished."""
    owner = report.get('owner_coverage')
    if owner:
        complete = sum(e['status'] == 'complete' for e in owner)
        partial = sum(e['status'] == 'partial' for e in owner)
        limits = [e['explanation'] for e in owner if e['status'] != 'complete']
        return (f'Cobertura del encargo: {complete} de {len(owner)} entregables completos'
                + (f'; {partial} parciales' if partial else '') + '.'
                + (' Pendiente: ' + '; '.join(limits) if limits else ''))[:1600]
    items = summary['investigations']
    answered = {i['investigation_key'] for i in report['question_coverage'] if i['status'] == 'answered'}
    pending = [i['question'] for i in items if i['key'] not in answered]
    text = f'Cobertura del informe: {len(answered)} de {len(items)} preguntas respondidas.'
    if pending:
        text += ' Sin completar en esta entrega: ' + '; '.join(pending) + '.'
    # The stopping decision belongs to the execution trace, not the delivered
    # report. In particular, 'no useful work remains' is not a customer limitation.
    return text[:1600]
