"""Context-bound continuity actions. No analytical choices or evidence values added."""
from copy import deepcopy

from .research_contract import dependencies


def constrain_schema(schema, context):
    # A nested union is supported by strict structured output; a root union is not.
    # Keep the wire envelope in agent_calls.output; unwrap only at dispatch.
    original = deepcopy(schema)
    definitions = schema['$defs']
    evidence = definitions['EvidenceRef']
    evidence['required'] = list(evidence['properties'])
    observations = context.get('observations', [])
    findings = context.get('findings', [])
    budget = context.get('budgets', {})
    work = context.get('plan', {}).get('investigations', [])
    snapshot = dict(proposal=context.get('plan', {'questions': [], 'investigations': []}),
                    answers=context.get('answers', []), coordination=context.get('coordination'))
    _, resolved = dependencies(snapshot, findings)
    finished = {f['investigation_key'] for f in findings} | set(budget.get('discarded_keys', []))
    attempted = {o['investigation_key'] for o in observations} | set(budget.get('assigned_keys', []))
    used = budget.get('attempts_used', {})
    allowed = original['properties']['action']['enum']
    branches = []
    reference_cache = {}
    followup_cache = {}

    def references(key, parent=None):
        cache_key = (key, parent is not None)
        if cache_key in reference_cache:
            return reference_cache[cache_key]
        registered = None
        if parent:
            saved = parent.get('evidence_refs') or [dict(execution_id=parent['execution_id'],
                                                        metric_keys=parent['metric_keys'], series_keys=[])]
            registered = {r['execution_id']: r for r in saved}
        choices = []
        for o in observations:
            if (o['investigation_key'] != key or o['status'] != 'completed'
                    or o.get('result_omitted') or o.get('current') is False):
                continue
            if registered is not None and o['execution_id'] not in registered:
                continue
            r = deepcopy(evidence)
            r['properties']['execution_id']['enum'] = [o['execution_id']]
            available = []
            for field, source in [('metric_keys', 'metrics'), ('series_keys', 'series')]:
                keys = set((o.get('result') or {}).get(source, {}))
                if registered is not None:
                    keys &= set(registered[o['execution_id']].get(field, []))
                if keys:
                    r['properties'][field]['items']['enum'] = sorted(keys)
                    available.append(field)
                else:
                    r['properties'][field]['maxItems'] = 0
            # Each ref must name at least one key; do not offer empty refs.
            for field in available:
                variant = deepcopy(r)
                variant['properties'][field]['minItems'] = 1
                choices.append(variant)
        result = None
        if choices:
            name = f'ContextEvidence{len(reference_cache)}'
            definitions[name] = {'anyOf': choices}
            result = {'$ref': f'#/$defs/{name}'}
        reference_cache[cache_key] = result
        return result

    def base(kind, key=''):
        branch = {k: deepcopy(v) for k, v in original.items() if k != '$defs'}
        p = branch['properties']
        p['action']['enum'] = [kind]
        p['investigation_key']['enum'] = [key]
        for field in ('table_ids', 'metric_keys', 'followups', 'assignments', 'evidence_refs'):
            p[field]['maxItems'] = 0
        p['code']['enum'] = ['']
        for field in ('continuation', 'closure', 'synthesis'):
            p[field] = {'type': 'null'}
        return branch

    def close(p):
        # Encode the reason/pending-calculation dependency too.
        choices = []
        for reasons, pending in [(['sufficient', 'unusable'], True), (['budget', 'missing_data'], False)]:
            variant = deepcopy(definitions['Closure'])
            variant['properties']['reason']['enum'] = reasons
            if not pending:
                variant['properties']['pending_calculation'] = {'type': 'string', 'minLength': 1, 'maxLength': 1600, 'pattern': r'\S'}
            else:
                variant['properties']['pending_calculation'] = {'anyOf': [
                    {'type': 'string', 'minLength': 1, 'maxLength': 1600, 'pattern': r'\S'}, {'type': 'null'}]}
            for field in ('decision_if_different', 'explanation'):
                variant['properties'][field]['pattern'] = r'\S'
            choices.append(variant)
        definitions['ContextClosure'] = {'anyOf': choices}
        p['closure'] = {'$ref': '#/$defs/ContextClosure'}

    def followups(p, refs, key):
        child = deepcopy(definitions['ContinuityFollowup'])
        child['properties']['basis_metric_keys']['maxItems'] = 0
        child['properties']['basis_evidence'].update(minItems=1, items=deepcopy(refs))
        if budget.get('delivery_quality'):
            child['properties']['focus'] = {'$ref': '#/$defs/SignalFocus'}
        known, child_resolved = dependencies(snapshot, findings, recording=key)
        variants = []
        for state, keys in [('ready', child_resolved), ('blocked', known), ('not_possible', known)]:
            variant = deepcopy(child)
            variant['properties']['status']['enum'] = [state]
            dep = variant['properties']['depends_on']
            if keys:
                dep['items']['enum'] = sorted(keys)
            else:
                dep['maxItems'] = 0
            variants.append(variant)
        p['followups'] = deepcopy(original['properties']['followups'])
        cache_key = (key, refs['$ref'])
        if cache_key not in followup_cache:
            name = f'ContextFollowup{len(followup_cache)}'
            definitions[name] = {'anyOf': variants}
            followup_cache[cache_key] = {'$ref': f'#/$defs/{name}'}
        p['followups']['items'] = followup_cache[cache_key]

    for item in work:
        key = item['key']
        attempts = [o for o in observations if o['investigation_key'] == key]
        latest = attempts[-1] if attempts else None
        ready = item['status'] == 'ready' and set(item.get('depends_on', [])) <= resolved
        parent = next((f for f in findings if f['investigation_key'] == key and f['status'] == 'candidate'), None)
        for kind in allowed:
            if kind not in ('execute', 'record_candidate', 'block', 'discard', 'expand'):
                continue
            if kind == 'expand':
                if not parent or not budget.get('delegation') or budget.get('worker_assignment'):
                    continue
            elif key in finished:
                continue
            if kind != 'discard' and not ready:
                continue
            branch = base(kind, key)
            p = branch['properties']
            refs = references(key, parent if kind == 'expand' else None)
            if kind == 'execute':
                if (sum(used.values()) >= budget.get('max_executions', 100)
                        or used.get(key, len(attempts)) >= budget.get('max_attempts_per_investigation', 3)
                        or item.get('round', 1) > budget.get('max_rounds', 1)
                        or (key not in attempted and len(attempted) >= budget.get('max_investigations', 100))):
                    continue
                tables = set(item['table_ids']) & {t['id'] for t in context.get('table_catalog', [])}
                if not tables:
                    continue
                p['table_ids'].update(minItems=1, maxItems=min(8, len(tables)), items={'type': 'string', 'enum': sorted(tables)})
                p['code'] = {'type': 'string', 'minLength': 1, 'maxLength': 48000, 'pattern': r'\S'}
                if refs:
                    continuation = deepcopy(definitions['Continuation'])
                    continuation['properties']['evidence']['items'] = refs
                    p['continuation'] = (continuation if latest and latest['status'] == 'completed' and not latest.get('result_omitted')
                                         else {'anyOf': [continuation, {'type': 'null'}]})
                elif latest and latest['status'] == 'completed' and not latest.get('result_omitted'):
                    continue
            if kind in ('record_candidate', 'expand'):
                if not refs:
                    continue
                p['evidence_refs'].update(minItems=1, maxItems=12, items=refs)
                followups(p, refs, key)
                if kind == 'expand':
                    if p['followups']['maxItems'] == 0:
                        continue
                    p['followups']['minItems'] = 1
            if kind in ('record_candidate', 'block', 'discard'):
                close(p)
            branches.append(branch)

    for kind in allowed:
        if kind not in ('finish', 'delegate', 'consult_business'):
            continue
        if kind != 'finish' and budget.get('worker_assignment'):
            continue
        branch = base(kind)
        p = branch['properties']
        if kind == 'delegate':
            eligible = [i['key'] for i in work if i['key'] not in attempted | finished
                        and i['status'] == 'ready' and set(i.get('depends_on', [])) <= resolved
                        and i.get('round', 1) <= budget.get('max_rounds', 1)]
            capacity = min(3, len(eligible), budget.get('max_investigations', 100) - len(attempted))
            if capacity <= 0:
                continue
            assignment = deepcopy(definitions['Assignment'])
            assignment['properties']['investigation_key']['enum'] = eligible
            p['assignments'].update(minItems=1, maxItems=capacity, items=assignment)
        elif kind == 'finish':
            p['synthesis'] = ({'$ref': '#/$defs/Synthesis'} if budget.get('delegated') and any(f['status'] == 'candidate' for f in findings)
                              else deepcopy(original['properties']['synthesis']))
        branches.append(branch)
    if not branches:
        from .research_agenda import ResearchBudgetReached
        raise ResearchBudgetReached('No feasible research action remains in the current context; preserve existing evidence.')
    schema.clear()
    schema.update(type='object', additionalProperties=False, required=['decision'],
                  properties={'decision': {'anyOf': branches}}, **{'$defs': definitions})
