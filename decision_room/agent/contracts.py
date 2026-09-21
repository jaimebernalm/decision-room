"""Untrusted model output: structure and referential checks, not factual approval."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Reference(Strict):
    kind: Literal['table', 'column', 'owner_context', 'answer']
    id: str = Field(max_length=100)
    column: str = Field(max_length=256)


class Interpretation(Strict):
    aspect: Literal['meaning', 'granularity', 'coverage', 'quality', 'relationship', 'business', 'missing']
    statement: str = Field(min_length=1, max_length=1200)
    status: Literal['observed', 'inferred', 'confirmed', 'unresolved']
    references: list[Reference] = Field(min_length=1, max_length=12)


class Question(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    text: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=1000)
    references: list[Reference] = Field(min_length=1, max_length=8)
    options: list[str] = Field(max_length=4)


class Investigation(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    question: str = Field(min_length=1, max_length=1000)
    business_value: str = Field(min_length=1, max_length=1000)
    table_ids: list[str] = Field(min_length=1, max_length=12)
    definitions_needed: list[str] = Field(max_length=12)
    depends_on: list[str] = Field(max_length=12)
    proposed_operation: str = Field(min_length=1, max_length=1500)
    validation_needed: list[str] = Field(min_length=1, max_length=12)
    status: Literal['ready', 'blocked', 'not_possible']


class Proposal(Strict):
    interpretations: list[Interpretation] = Field(min_length=1, max_length=24)
    investigations: list[Investigation] = Field(min_length=1, max_length=8)
    questions: list[Question] = Field(max_length=3)
    limitations: list[str] = Field(min_length=1, max_length=16)


class Action(Strict):
    action: Literal['inspect', 'propose']
    table_ids: list[str] = Field(max_length=8)
    proposal: Proposal | None


def validate_action(raw, snapshot, inspected, answers, previous=None):
    action = Action.model_validate(raw)
    tables = {t['id']: t for t in snapshot['tables']}
    if action.action == 'inspect':
        if action.proposal is not None or not action.table_ids:
            raise ValueError('inspect requires table_ids and a null proposal.')
        if len(set(inspected) | set(action.table_ids)) > 8:
            raise ValueError('At most eight table profiles per session.')
        if not set(action.table_ids) <= tables.keys() or set(action.table_ids) <= set(inspected):
            raise ValueError('Inspect existing, previously unseen table IDs.')
        return action.model_dump()
    if action.proposal is None or action.table_ids:
        raise ValueError('propose requires a proposal and empty table_ids.')
    proposal = action.proposal
    answered = {a['key']: a for a in answers}
    answer_ids = {a['id']: a for a in answers}
    question_keys = [q.key for q in proposal.questions]
    investigation_keys = [i.key for i in proposal.investigations]
    if len(question_keys) != len(set(question_keys)) or len(investigation_keys) != len(set(investigation_keys)):
        raise ValueError('Duplicate question or investigation keys.')
    if set(question_keys) & answered.keys():
        raise ValueError('Do not repeat answered, unknown or declined questions.')

    def references(refs):
        for ref in refs:
            if ref.kind in ('table', 'column'):
                if ref.id not in tables or ref.id not in inspected:
                    raise ValueError('Interpret only tables whose profiles have been inspected.')
                if ref.kind == 'column' and ref.column not in tables[ref.id]['column_names']:
                    raise ValueError('Unknown column reference.')
            elif ref.kind == 'owner_context':
                if ref.id != 'owner_context' or not snapshot['owner_context']:
                    raise ValueError('No owner context available.')
            elif ref.id not in answer_ids:
                raise ValueError('Unknown answer reference.')

    for item in proposal.interpretations:
        references(item.references)
        if item.status == 'confirmed' and not any(
            r.kind == 'owner_context' or (r.kind == 'answer' and answer_ids[r.id]['disposition'] == 'answered')
            for r in item.references
        ):
            raise ValueError('Confirmed definitions require owner context or an actual answer.')
    for question in proposal.questions:
        references(question.references)
        if not any(question.key in i.depends_on for i in proposal.investigations):
            raise ValueError('Ask only questions with a material investigation dependency.')
    for investigation in proposal.investigations:
        # A declined answer cannot silently disappear from an existing investigation.
        prior = next((i for i in (previous or {}).get('investigations', []) if i['key'] == investigation.key), None)
        if prior:
            retained = [key for key in prior['depends_on'] if key in answered and answered[key]['disposition'] != 'answered']
            investigation.depends_on = sorted(set(investigation.depends_on) | set(retained))
        if not set(investigation.table_ids) <= set(inspected):
            raise ValueError('Investigations require inspected tables.')
        if not set(investigation.depends_on) <= (set(question_keys) | answered.keys()):
            raise ValueError('Unknown question dependency.')
        unresolved = any(k in question_keys or answered[k]['disposition'] != 'answered'
                         for k in investigation.depends_on)
        if unresolved and investigation.status == 'ready':
            investigation.status = 'blocked'
    return action.model_dump()
