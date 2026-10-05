"""Bounded tool observations; complete code and evidence stay in durable storage."""
from copy import deepcopy

from ..execution import get_execution
from .context import encoded
from .research_agenda import ResearchBudgetReached


def observations(config, business_id, steps):
    result = []
    for step in steps:
        if step['action']['action'] != 'execute' or not step['execution_id']:
            continue
        execution = get_execution(config, business_id, step['execution_id'])
        result.append({'step': step['step'], 'execution_id': str(execution['id']),
                       'investigation_key': step['action']['investigation_key'],
                       'status': execution['status'], 'code': step['action']['code'],
                       'result': execution['result'], 'logs': execution['logs'], 'issue': execution['issue'],
                       'artifacts': [{k: str(a[k]) if k == 'id' else a[k]
                                      for k in ('id', 'name', 'sha256', 'byte_count')} for a in execution['artifacts']]})
    return result


def prompt_context(snapshot, observations, findings, options, turns):
    # Baseline exposes latest attempts. Continuity also retains successful
    # earlier evidence; failed attempts still count in the unabridged budget.
    latest = {}
    for item in observations:
        latest[item['investigation_key']] = item
    feedback = []
    visible = ([o for o in observations if o['status'] == 'completed' or latest[o['investigation_key']] is o]
               if options.get('research_continuity') else latest.values())
    for value in visible:
        item = deepcopy(value)
        item['logs'] = {k: v[-4000:] if isinstance(v, str) else v for k, v in item['logs'].items()}
        item['logs_may_be_truncated'] = True
        if item['result'] and len(encoded(item['result']).encode()) > 64000:
            item['result'] = {'verification': 'pending', 'metrics': {}, 'evidence': [],
                              'notes': ['Result omitted from model context: exceeds 64 KB. Generate a more focused output.']}
            item['result_omitted'] = True
        if any(f['investigation_key'] == item['investigation_key'] for f in findings):
            item.pop('code', None)
            item['logs'] = {}
            item['code_omitted_after_registration'] = True
        feedback.append(item)
    result = {'phase': 'python_research', 'owner_context': snapshot['source']['owner_context'],
              'accepted_owner_request': {'text': snapshot['source']['owner_context']},
              'answers': snapshot['answers'], 'plan': snapshot['proposal'],
              'table_catalog': snapshot['tables'], 'observations': feedback, 'findings': findings,
              'coordination': snapshot.get('coordination'), 'delegations': snapshot.get('delegations', []),
              'business_direction': snapshot.get('business_direction'),
              'budgets': {**options, 'model_turns_used': turns,
                          'attempts_used': {key: sum(o['investigation_key'] == key for o in observations)
                                            for key in latest}}}
    from .panorama_research import expose
    result = expose(result, snapshot['source'])
    limit = options.get('max_context_bytes', 200000)
    if len(encoded(result).encode()) > limit:
        raise ResearchBudgetReached(f'Research context exceeds {limit // 1000} KB; automatic compaction is not implemented yet.')
    return result
