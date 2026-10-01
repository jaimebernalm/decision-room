"""Versioned decision orientation and owner coverage, independent of agenda size.

Structure and links are mechanically checked; usefulness remains a reviewer task.
Historical drafts and planner events retain their original payload and digest.
"""
from typing import Literal
from pydantic import Field
from .contracts import Strict

VERSION = 'delivery-quality-v1'


class MetricRef(Strict):
    execution_id: str = Field(max_length=36)
    metric: str = Field(min_length=1, max_length=120)


class SeriesPointRef(Strict):
    execution_id: str = Field(max_length=36)
    series: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=100)


class ConditionalReaction(Strict):
    condition: str = Field(min_length=1, max_length=600)
    reaction: str = Field(min_length=1, max_length=800)


class DecisionOrientation(Strict):
    segment: str = Field(min_length=1, max_length=200)
    period: str = Field(min_length=1, max_length=200)
    signal: str = Field(min_length=1, max_length=800)
    evidence: list[MetricRef | SeriesPointRef] = Field(min_length=1, max_length=12)
    relative_priority: str = Field(min_length=1, max_length=1000)
    knowledge: Literal['calculated', 'owner_confirmed', 'hypothesis']
    next_check: str = Field(max_length=1000)
    decision_value: str = Field(min_length=1, max_length=1000)
    reactions: list[ConditionalReaction] = Field(max_length=4)
    limitation: str = Field(max_length=800)


class OwnerCoverage(Strict):
    deliverable_index: int = Field(ge=0, le=11)
    status: Literal['complete', 'partial', 'unavailable', 'deferred']
    claim_keys: list[str] = Field(max_length=6)
    explanation: str = Field(min_length=1, max_length=800)


def owner_deliverables(context):
    brief = (context.get('business_direction') or {}).get('brief') or {}
    return brief.get('deliverables') or [context.get('owner_context') or 'Responder al encargo confirmado del propietario.']


def validate_owner_coverage(report, context):
    if context.get('review_policy', 0) < 4:
        return
    if report.get('contract_version') != 2:
        raise ValueError('New reviews require report contract_version=2; historical drafts remain unchanged.')
    entries = report.get('owner_coverage', [])
    indices = [e['deliverable_index'] for e in entries]
    if len(set(indices)) != len(indices) or set(indices) != set(range(len(owner_deliverables(context)))):
        raise ValueError('owner_coverage must address each owner deliverable exactly once, separately from investigations.')
    claims = {c['key'] for c in report['claims']}
    for entry in entries:
        if not set(entry['claim_keys']) <= claims:
            raise ValueError('Owner coverage references unknown claims.')
        if (entry['status'] in ('complete', 'partial')) != bool(entry['claim_keys']):
            raise ValueError('Complete/partial owner answers need claims; unavailable/deferred answers cannot claim delivery.')


AUTONOMY = '''
DELIVERY QUALITY AND AUTONOMY:
The planner chooses business priorities, the principal chooses investigation methods,
evidence-linked followups and presentation, and the reviewer independently judges
usefulness. Code validates integrity, not commercial priorities. Choose the scope,
contrast and representation that best answer the owner's goal within real capabilities.
For discovery, preserve decision orientation: segment, focal period, saved signal
and evidence, relative_priority compared with alternatives, knowledge status,
next_check, decision_value, conditional reactions and material limitation. A check
must say what fact to check where/when and what interpretation or decision it changes.
Use reactions only for explicit conditions; an arithmetic contribution is not a
cause. A directly supported action may have an evidence-based condition. If action
cannot yet be chosen, explain that limit. Do not manufacture recommendations for
factual questions or organizing views. Unknown/refused context stays unknown.
Cover the owner's deliverables separately from internal investigation branches;
partial is useful but never complete. Compute feasible answers now, rather than
asking the owner to compute them. Preserve the source/measure of each uncertainty:
currency, quantity unit, row grain and per-unit/row-total basis are distinct. A
missing sales definition does not automatically invalidate marketing or quantities.
Never drop a required view on correction without a legible valid replacement or
an actual source/definition limitation. Review semantic quality, not field presence.
'''
