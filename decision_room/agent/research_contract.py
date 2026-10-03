"""Agent-selected Python actions. These checks do not approve business meaning."""
from typing import Literal

from pydantic import Field

from .contracts import Strict, Investigation, ResearchPriority
from .research_agenda import ResearchBudgetReached


class SignalFocus(Strict):
    segment: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=200)
    comparison: str = Field(min_length=1, max_length=400)
    decision_value: str = Field(min_length=1, max_length=800)


class Followup(Investigation):
    focus: SignalFocus | None = None
    priority: ResearchPriority
    stage: Literal['verify', 'breakdown']
    basis_metric_keys: list[str] = Field(min_length=1, max_length=8)


class Assignment(Strict):
    investigation_key: str = Field(min_length=1, max_length=64)
    instruction: str = Field(min_length=1, max_length=1600)


class RankedFinding(Strict):
    investigation_key: str
    reason: str = Field(min_length=1, max_length=1000)
    next_check: str = Field(min_length=1, max_length=1000)


class Disagreement(Strict):
    investigation_keys: list[str] = Field(min_length=2, max_length=12)
    explanation: str = Field(min_length=1, max_length=1600)
    resolution: Literal['resolved', 'excluded', 'unresolved']


class Synthesis(Strict):
    priorities: list[RankedFinding] = Field(max_length=12)
    excluded: list[RankedFinding] = Field(max_length=12)
    disagreements: list[Disagreement] = Field(max_length=12)


class ResearchAction(Strict):
    action: Literal['execute', 'record_candidate', 'block', 'discard', 'finish', 'delegate', 'expand', 'consult_business']
    investigation_key: str = Field(max_length=64)
    table_ids: list[str] = Field(max_length=8)
    code: str = Field(max_length=48000)
    summary: str = Field(min_length=1, max_length=1600)
    metric_keys: list[str] = Field(max_length=64)
    followups: list[Followup] = Field(default_factory=list, max_length=3)
    assignments: list[Assignment] = Field(default_factory=list, max_length=3)
    synthesis: Synthesis | None = None


def dependencies(snapshot, findings, recording=None):
    """Owner questions and saved candidate dependencies have distinct authority.

    A parent's evidence can unlock followups, never answer an owner question with
    the same key. Workers also see the frozen candidates given by the principal.
    """
    owner = {q['key'] for q in snapshot['proposal']['questions']} | {a['key'] for a in snapshot['answers']}
    shared = (snapshot.get('coordination') or {}).get('findings', [])
    candidates = {f['investigation_key'] for f in [*findings, *shared] if f['status'] == 'candidate'}
    if recording:
        candidates.add(recording)
    known = owner | {i['key'] for i in snapshot['proposal']['investigations']} | candidates
    resolved = {a['key'] for a in snapshot['answers'] if a['disposition'] == 'answered'} | (candidates - owner)
    return known, resolved


def validate_research_action(raw, snapshot, observations, findings, options):
    action = ResearchAction.model_validate(raw)
    work = {i['key']: i for i in snapshot['proposal']['investigations']}
    finished = {f['investigation_key'] for f in findings} | set(options.get('discarded_keys', []))
    if action.assignments and action.action != 'delegate':
        raise ValueError('Only delegate may contain assignments.')
    if action.synthesis is not None and action.action != 'finish':
        raise ValueError('Only finish may contain synthesis.')
    if action.action == 'consult_business':
        if not options.get('business_planner') or options.get('worker_assignment'):
            raise ValueError('Only the principal can consult the business planner when enabled.')
        if action.investigation_key or action.code or action.table_ids or action.metric_keys or action.followups or action.assignments:
            raise ValueError('Consultation requires only a concrete summary and empty work fields.')
        return action.model_dump()
    if action.action == 'delegate':
        if options.get('worker_assignment') or not options.get('delegation'):
            raise ValueError('Workers cannot delegate; delegation is disabled for this run.')
        if action.investigation_key or action.code or action.table_ids or action.metric_keys or action.followups:
            raise ValueError('delegate requires empty action fields except assignments and summary.')
        keys = [a.investigation_key for a in action.assignments]
        if not 1 <= len(keys) <= 3 or len(set(keys)) != len(keys):
            raise ValueError('Delegate one to three distinct existing investigations.')
        attempted = {o['investigation_key'] for o in observations}
        _, resolved = dependencies(snapshot, findings)
        for key in keys:
            item = work.get(key)
            if not item or key in finished or key in attempted or item['status'] != 'ready':
                raise ValueError('Delegate only ready, unattempted, unfinished agenda items.')
            if not set(item['depends_on']) <= resolved or item.get('round', 1) > options['max_rounds']:
                raise ValueError('Delegated investigation has unresolved dependencies or exceeds rounds.')
        if len(attempted | set(keys) | set(options.get('assigned_keys', []))) > options['max_investigations']:
            raise ResearchBudgetReached('Presupuesto de investigaciones insuficiente para estas ramas.')
        return action.model_dump()
    if action.followups and action.action not in ('record_candidate', 'expand'):
        raise ValueError('Only record_candidate or coordinator expand can propose evidence-linked followups.')
    if action.action == 'finish':
        if action.investigation_key or action.table_ids or action.code or action.metric_keys:
            raise ValueError('finish requires empty investigation_key, table_ids, code and metric_keys.')
        pending = {o['investigation_key'] for o in observations} - finished
        if pending:
            raise ValueError('Before finish, record a supported candidate or block each attempted investigation: ' + ', '.join(sorted(pending)))
        if options.get('delegation') and any(i['key'] not in finished and i['status'] == 'ready'
                and i.get('round', 1) <= options['max_rounds'] for i in work.values()):
            raise ValueError('Resolve ready agenda tasks first: delegate for Python, or explicitly discard with a concrete reason. Worker Python is available through delegate.')
        candidates = {f['investigation_key'] for f in findings if f['status'] == 'candidate'}
        if options.get('delegated') and candidates and action.synthesis is None:
            raise ValueError('The coordinator must synthesize delegated candidates before finish.')
        if action.synthesis is not None:
            synth = action.synthesis
            ranked = [i.investigation_key for i in synth.priorities]
            excluded = [i.investigation_key for i in synth.excluded]
            if len(set(ranked + excluded)) != len(ranked + excluded) or set(ranked + excluded) != candidates:
                raise ValueError('Account for every candidate exactly once in priorities or excluded. Candidate keys: ' + ', '.join(sorted(candidates)) + '; blocked/discarded tasks are not candidates.')
            for conflict in synth.disagreements:
                keys = set(conflict.investigation_keys)
                if len(keys) < 2 or not keys <= candidates:
                    raise ValueError('Disagreements must reference distinct saved candidates.')
                if conflict.resolution != 'resolved' and keys & set(ranked):
                    raise ValueError('Unresolved/excluded disagreements cannot be prioritized as findings.')
        return action.model_dump()
    expanding = action.action == 'expand'
    if expanding and (options.get('worker_assignment') or not options.get('delegation') or not action.followups
                      or action.investigation_key not in {f['investigation_key'] for f in findings if f['status'] == 'candidate'}):
        raise ValueError('Only the coordinator can expand a saved candidate with evidence-linked followups.')
    if action.investigation_key not in work or (action.investigation_key in finished and not expanding):
        raise ValueError('Choose an unfinished investigation from this plan.')
    investigation = work[action.investigation_key]
    _, resolved = dependencies(snapshot, findings)
    if action.action != 'discard' and (investigation['status'] != 'ready' or not set(investigation['depends_on']) <= resolved):
        raise ValueError('This investigation has unresolved dependencies or is not ready.')
    attempts = [o for o in observations if o['investigation_key'] == action.investigation_key]
    latest = attempts[-1] if attempts else None
    if action.action == 'execute':
        from .context import encoded
        if latest and latest['status'] == 'completed' and len(encoded(latest.get('result')).encode()) <= 64000:
            raise ValueError('Preserve the completed result first: record_candidate (still pending independent review), or block if unusable. Expand through a new followup rather than overwriting successful evidence.')
        if not action.code.strip() or not action.table_ids or action.metric_keys:
            raise ValueError('execute requires Python code, table_ids and empty metric_keys.')
        if len(action.table_ids) != len(set(action.table_ids)) or not set(action.table_ids) <= set(investigation['table_ids']):
            raise ValueError('Use only unique table IDs authorized for this investigation.')
        if len(observations) >= options.get('max_executions', 100):
            scope = 'worker assignment' if options.get('worker_assignment') else 'research run'
            raise ResearchBudgetReached(f'Python execution budget reached for {scope} ({len(observations)}/{options.get("max_executions", 100)}). This does not exhaust allowances outside that scope. Record existing evidence, block, discard or finish.')
        if investigation.get('round', 1) > options.get('max_rounds', 1):
            raise ResearchBudgetReached('Round budget reached; discard or finish.')
        if len(attempts) >= options['max_attempts_per_investigation']:
            raise ValueError(f'Python attempt budget reached for investigation {action.investigation_key} ({len(attempts)}/{options["max_attempts_per_investigation"]}); not the global budget. Record a supported candidate or block it.')
        attempted = {o['investigation_key'] for o in observations} | set(options.get('assigned_keys', []))
        if action.investigation_key not in attempted and len(attempted) >= options['max_investigations']:
            raise ResearchBudgetReached('Investigation budget reached; finish or address an already attempted investigation.')
    else:
        if action.table_ids or action.code:
            raise ValueError('Only execute may contain code or table_ids.')
        if action.action in ('record_candidate', 'expand'):
            if not latest or latest['status'] != 'completed' or not action.metric_keys:
                raise ValueError('A candidate requires the latest execution to succeed, with named metrics.')
            if expanding and not set(action.metric_keys) <= set(next(f['metric_keys'] for f in findings if f['investigation_key'] == action.investigation_key)):
                raise ValueError('Expansion must use the registered parent candidate metrics.')
            if not set(action.metric_keys) <= set(latest['result']['metrics']):
                missing = sorted(set(action.metric_keys) - set(latest['result']['metrics']))
                raise ValueError('Candidate refers to missing metrics in the latest execution: ' + ', '.join(missing[:8]) + '. Copy exact keys from result.metrics, or remove unsupported references.')
        elif action.metric_keys:
            raise ValueError('block/discard requires empty metric_keys.')
    if action.followups:
        if len(work) + len(action.followups) > options.get('max_agenda', 24):
            raise ValueError('Agenda capacity reached; record the candidate without new followups.')
        keys = [i.key for i in action.followups]
        if len(set(keys)) != len(keys) or set(keys) & work.keys():
            raise ValueError('Followup keys must be new and unique.')
        allowed = {t['id'] for t in snapshot['tables']}
        known, child_resolved = dependencies(snapshot, findings, recording=action.investigation_key)
        for child in action.followups:
            if options.get('delivery_quality') and child.focus is None:
                raise ValueError('A new followup needs focus: segment, focal period/comparison and decision_value; use all segments/available period when appropriate.')
            if any(set(child.table_ids) == set(i['table_ids'])
                   and child.proposed_operation.strip().casefold() == i['proposed_operation'].strip().casefold()
                   and child.focus is not None and child.focus.model_dump() == i.get('focus')
                   for i in work.values()):
                raise ValueError('This focused operation is already on the agenda; reuse it or explain a different contrast.')
            assignment = options.get('worker_assignment')
            if assignment and not child.key.startswith(assignment['investigation_key'] + '__'):
                raise ValueError('Worker followup keys must start with the assigned key plus __.')
            if not set(child.table_ids) <= allowed or len(child.table_ids) != len(set(child.table_ids)):
                raise ValueError('Followups require unique authorized, inspected tables.')
            if not set(child.basis_metric_keys) <= set(action.metric_keys):
                raise ValueError('Followup basis must reference metrics recorded in this candidate.')
            if not set(child.depends_on) <= known:
                raise ValueError('Unknown followup dependency; use an owner-question key or a saved candidate key. Block and describe any new clarification in definitions_needed.')
            if child.status == 'ready' and not set(child.depends_on) <= child_resolved:
                raise ValueError('Followup has unresolved owner dependencies.')
            if child.question.strip().casefold() in ({i['question'].strip().casefold() for i in work.values()} | set(options.get('existing_questions', []))):
                raise ValueError('Duplicate followup question; deepen or verify the existing result.')
    return action.model_dump()
