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
For a discovery decision, make the check executable: name the observable fact,
segment, period and record or comparison to inspect; distinguish plausible outcomes
and say what specific next operation, adjustment, investigation or proportionate
operational review each outcome warrants. A conditional reaction does not assert
that the condition occurred or prove a cause. Use only conditions relevant to the
saved signal, and do not promise gains. Merely 'interpret cautiously', 'reconsider
priority', 'consider other explanations' or 'this would change interpretation'
does not complete decision support. Say what would actually be reconsidered or
checked next and why. For example, a confirmed capture difference may warrant
repairing that comparison; a confirmed availability constraint may warrant a
focused availability review. These are illustrations, not mandatory business
actions. Choose appropriate alternatives; do not import these facts into a case.
If a useful reaction cannot be selected, identify the precise missing fact and
preserve a partial delivery instead of declaring this component complete. Do
computable internal checks now; do not defer them to the owner or future work.
The reviewer must assess the actual condition-to-reaction reasoning and the
original goal, not approve because the orientation fields or reactions exist.
Cover the owner's deliverables separately from internal investigation branches;
partial is useful but never complete. Compute feasible answers now, rather than
asking the owner to compute them. Preserve the source/measure of each uncertainty:
currency, quantity unit, row grain and per-unit/row-total basis are distinct. A
missing sales definition does not automatically invalidate marketing or quantities.
Never drop a required view on correction without a legible valid replacement or
an actual source/definition limitation. Review semantic quality, not field presence.
Check both omissions and expansion against the original owner request. An agent's
brief, drilldown or optional view is not an owner-confirmed requirement. For a
request to prioritize a few findings, a justified selection may provide complete
owner coverage even when an exhaustive internal listing is not delivered. Keep
that internal listing's status honest and separate. Do not repeatedly demand
optional percentages or full inventories merely because they are computable;
require them when material to the actual requested answer or its validity. For
organizing views, preserve every requested measure and breakdown instead of
using a discovery selection to excuse an omission.
'''


def validate_orientation(report, context):
    if context.get('review_policy', 0) < 4:
        return
    brief = (context.get('business_direction') or {}).get('brief') or {}
    oriented = [c['orientation'] for c in report['claims'] if c.get('orientation')]
    if brief.get('intent') == 'discover' and not oriented:
        raise ValueError('Discovery delivery needs an evidence-linked priority and decision orientation, including partial limits.')
    for item in oriented:
        if not item['next_check'].strip() and not item['reactions'] and not item['limitation'].strip():
            raise ValueError('Explain a concrete next check, a supported conditional reaction or why a decision is not yet possible.')


def orientation_sections(value):
    """Exact reviewed prose for static delivery; never generated advice."""
    if not value:
        return []
    sections = [('Dónde y cuándo', value['segment'] + ' · ' + value['period']),
                ('Señal', value['signal']), ('Por qué merece atención', value['relative_priority'])]
    if value['next_check']:
        sections.append(('Siguiente comprobación', value['next_check']))
    sections.append(('Qué permite decidir', value['decision_value']))
    sections += [('Si ' + r['condition'], r['reaction']) for r in value['reactions']]
    if value['limitation']:
        sections.append(('Límite de esta decisión', value['limitation']))
    return sections
