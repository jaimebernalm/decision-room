"""Opt-in continuity contracts; references name immutable executions, never values."""
from typing import Literal

from pydantic import Field

from .contracts import Strict
from .research_contract import Followup, ResearchAction

VERSION = 'research-continuity-v1'


class EvidenceRef(Strict):
    execution_id: str = Field(min_length=1, max_length=64)
    metric_keys: list[str] = Field(default_factory=list, max_length=64)
    series_keys: list[str] = Field(default_factory=list, max_length=4)


class Continuation(Strict):
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=12)
    next_calculation: str = Field(min_length=1, max_length=1600)
    decision_if_different: str = Field(min_length=1, max_length=1600)


class Closure(Strict):
    reason: Literal['sufficient', 'budget', 'missing_data', 'unusable']
    pending_calculation: str | None = Field(max_length=1600)
    decision_if_different: str = Field(min_length=1, max_length=1600)
    explanation: str = Field(min_length=1, max_length=1600)


class ContinuityFollowup(Followup):
    basis_metric_keys: list[str] = Field(default_factory=list, max_length=8)
    basis_evidence: list[EvidenceRef] = Field(default_factory=list, max_length=12)


class ContinuityAction(ResearchAction):
    followups: list[ContinuityFollowup] = Field(default_factory=list, max_length=3)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list, max_length=12)
    continuation: Continuation | None = None
    closure: Closure | None = None


def atoms(refs):
    return {(r.execution_id, kind, key) for r in refs
            for kind in ('metric_keys', 'series_keys') for key in getattr(r, kind)}


def validate_refs(refs, observations, investigation_key):
    by_id = {o['execution_id']: o for o in observations}
    if len({r.execution_id for r in refs}) != len(refs):
        raise ValueError('Use one evidence reference per execution, with its metric and series keys.')
    for ref in refs:
        o = by_id.get(ref.execution_id)
        if (not o or o['investigation_key'] != investigation_key or o['status'] != 'completed'
                or o.get('current') is False or o.get('result_omitted')):
            raise ValueError('Evidence must use a visible, current successful execution of this investigation.')
        if not ref.metric_keys and not ref.series_keys:
            raise ValueError('An evidence reference needs metric_keys or series_keys, not an empty execution reference.')
        for field, result_field in [('metric_keys', 'metrics'), ('series_keys', 'series')]:
            keys = getattr(ref, field)
            if len(keys) != len(set(keys)) or not set(keys) <= set((o.get('result') or {}).get(result_field, {})):
                raise ValueError(f'Unknown or duplicate {field} for execution {ref.execution_id}. Copy keys from that execution.')


def validate(action, observations, findings):
    """Normalize legacy latest-metric shorthand, then enforce execution-scoped links."""
    attempts = [o for o in observations if o['investigation_key'] == action.investigation_key]
    latest = attempts[-1] if attempts else None
    if action.continuation:
        if action.action != 'execute':
            raise ValueError('Only execute can carry continuation.')
        validate_refs(action.continuation.evidence, observations, action.investigation_key)
    if action.action == 'execute' and latest and latest['status'] == 'completed' and not latest.get('result_omitted'):
        if not action.continuation:
            raise ValueError('Continuing a successful investigation requires continuation: evidence, next_calculation and decision_if_different.')
    if action.closure and action.action not in ('record_candidate', 'block', 'discard', 'finish'):
        raise ValueError('Only a closing action can carry closure.')
    if action.action in ('record_candidate', 'block', 'discard') and not action.closure:
        raise ValueError('Closing an investigation requires closure: pending_calculation (or null), decision_if_different and explanation.')
    if action.closure:
        for text in (action.closure.decision_if_different, action.closure.explanation):
            if not text.strip():
                raise ValueError('Closure must explain the pending decision, not whitespace.')
        if action.closure.pending_calculation is not None and not action.closure.pending_calculation.strip():
            raise ValueError('Use null for no material pending calculation, with an explanation.')
        if action.closure.reason in ('budget', 'missing_data') and not action.closure.pending_calculation:
            raise ValueError('Budget/missing-data closure must name the pending calculation that could change the decision.')
    if action.action not in ('record_candidate', 'expand'):
        if action.evidence_refs:
            raise ValueError('Only record_candidate or expand can register/select evidence_refs.')
        return
    if action.metric_keys:
        if not latest or latest['status'] != 'completed':
            raise ValueError('metric_keys shorthand requires the latest execution to succeed; use evidence_refs for earlier evidence.')
        existing = next((r for r in action.evidence_refs if r.execution_id == latest['execution_id']), None)
        if existing:
            existing.metric_keys = list(dict.fromkeys([*existing.metric_keys, *action.metric_keys]))
        else:
            action.evidence_refs.append(EvidenceRef(execution_id=latest['execution_id'], metric_keys=action.metric_keys))
    if not action.evidence_refs:
        raise ValueError('A candidate or expansion needs registered metrics or series in evidence_refs.')
    validate_refs(action.evidence_refs, observations, action.investigation_key)
    if action.action == 'expand':
        parent = next((f for f in findings if f['investigation_key'] == action.investigation_key and f['status'] == 'candidate'), None)
        registered = (parent or {}).get('evidence_refs') or ([dict(execution_id=parent['execution_id'], metric_keys=parent['metric_keys'])] if parent else [])
        if not atoms(action.evidence_refs) <= atoms([EvidenceRef.model_validate(r) for r in registered]):
            raise ValueError('Expansion must use registered parent candidate evidence (execution-scoped metrics or series).')
    for child in action.followups:
        if not child.basis_metric_keys and not child.basis_evidence:
            raise ValueError('Followup needs basis_metric_keys or basis_evidence (metrics or series).')
        validate_refs(child.basis_evidence, observations, action.investigation_key)
        if not atoms(child.basis_evidence) <= atoms(action.evidence_refs):
            raise ValueError('Followup basis must use evidence registered/selected in this parent candidate.')


SYSTEM = '''
CONTINUITY EXPERIMENT (budgets.research_continuity=true):
You may execute again within the SAME unfinished investigation after success.
Do not close, request coordinator reopening or create another task just to follow
that signal. Provide continuation with execution-scoped evidence references,
next_calculation, and decision_if_different. Existing observations stay immutable;
all successful observations remain visible, subject to the existing context limit.
Keep the same authorized tables and budgets. This is NOT provisional exploration:
every calculation still uses the existing write_result evidence contract.
Close only when useful work is complete, blocked, or the supplied budget requires
it. record_candidate/block/discard require closure: reason, pending_calculation,
decision_if_different, explanation. If no material calculation remains, use null
and explain why. Do not invent a pending calculation or a causal conclusion.
record_candidate can retain metrics AND series from multiple successful executions
of this task through evidence_refs (execution_id, metric_keys, series_keys). It can
retain earlier evidence after a later failure; never call the failed result evidence.
metric_keys remains shorthand for scalar keys in the latest successful attempt only.
For expand and followups, series use evidence_refs and basis_evidence respectively;
never put a series key in metric_keys. Select only evidence registered in the parent
candidate, with its original execution ID. The closure and evidence survive handoff.
Unrelated agenda tasks still belong to the coordinator. Do not delegate recursively.
'''


def constrain_schema(schema, context):
    """Offer real execution/key pairs, with validation still enforcing task scope."""
    from copy import deepcopy
    original = schema['$defs']['EvidenceRef']
    choices = []
    for o in context.get('observations', []):
        if o['status'] != 'completed' or o.get('result_omitted') or o.get('current') is False:
            continue
        result = o.get('result') or {}
        if not result.get('metrics') and not result.get('series'):
            continue
        branch = deepcopy(original)
        branch['properties']['execution_id']['enum'] = [o['execution_id']]
        for field, result_field in [('metric_keys', 'metrics'), ('series_keys', 'series')]:
            keys = sorted(result.get(result_field, {}))
            if keys:
                branch['properties'][field]['items']['enum'] = keys
            else:
                branch['properties'][field]['maxItems'] = 0
        choices.append(branch)
    if choices:
        schema['$defs']['EvidenceRef'] = {'anyOf': choices}
    else:
        schema['properties']['evidence_refs']['maxItems'] = 0
        schema['properties']['continuation'] = {'type': 'null'}
        schema['$defs']['ContinuityFollowup']['properties']['basis_evidence']['maxItems'] = 0


def system_prompt(base):
    """Replace only the legacy close-before-calculating rules in this experiment."""
    start = base.index('Keep each round focused. After a successful execution,')
    end = base.index('\nAsk narrow followup questions', start)
    base = base[:start] + 'Keep the task focused; continue with linked calculations when they can change a decision.\n' + base[end:]
    start = base.index('After a successful bounded result, save it as an UNVERIFIED candidate')
    end = base.index('SQL identifiers may be reserved words:', start)
    base = base[:start] + 'Preserve every execution and its evidence; final candidates remain UNVERIFIED. ' + base[end:]
    base = base.replace("three NEW investigations grounded in that candidate's metric_keys.",
                        "three NEW investigations grounded in that candidate's registered metrics or series.")
    base = base.replace('recorded metrics. Use NEW stable keys',
                        'recorded metrics, or basis_evidence for execution-scoped metrics/series. Use NEW stable keys')
    base = base.replace('If so, enqueue it NOW; this is the point at which the next round is\ncreated.',
                        'Continue it within this task before closing when feasible; enqueue a separate followup only when a new task is needed.')
    return base + SYSTEM
