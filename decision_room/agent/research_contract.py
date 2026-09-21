"""Agent-selected Python actions. These checks do not approve business meaning."""
from typing import Literal

from pydantic import Field

from .contracts import Strict


class ResearchAction(Strict):
    action: Literal['execute', 'record_candidate', 'block', 'finish']
    investigation_key: str = Field(max_length=64)
    table_ids: list[str] = Field(max_length=8)
    code: str = Field(max_length=48000)
    summary: str = Field(min_length=1, max_length=1600)
    metric_keys: list[str] = Field(max_length=64)


def validate_research_action(raw, snapshot, observations, findings, options):
    action = ResearchAction.model_validate(raw)
    work = {i['key']: i for i in snapshot['proposal']['investigations']}
    finished = {f['investigation_key'] for f in findings}
    if action.action == 'finish':
        if action.investigation_key or action.table_ids or action.code or action.metric_keys:
            raise ValueError('finish requires empty investigation_key, table_ids, code and metric_keys.')
        pending = {o['investigation_key'] for o in observations} - finished
        if pending:
            raise ValueError('Before finish, record a supported candidate or block each attempted investigation: ' + ', '.join(sorted(pending)))
        return action.model_dump()
    if action.investigation_key not in work or action.investigation_key in finished:
        raise ValueError('Choose an unfinished investigation from this plan.')
    investigation = work[action.investigation_key]
    resolved = {a['key'] for a in snapshot['answers'] if a['disposition'] == 'answered'}
    if investigation['status'] != 'ready' or not set(investigation['depends_on']) <= resolved:
        raise ValueError('This investigation has unresolved dependencies or is not ready.')
    attempts = [o for o in observations if o['investigation_key'] == action.investigation_key]
    latest = attempts[-1] if attempts else None
    if action.action == 'execute':
        if not action.code.strip() or not action.table_ids or action.metric_keys:
            raise ValueError('execute requires Python code, table_ids and empty metric_keys.')
        if len(action.table_ids) != len(set(action.table_ids)) or not set(action.table_ids) <= set(investigation['table_ids']):
            raise ValueError('Use only unique table IDs authorized for this investigation.')
        if len(attempts) >= options['max_attempts_per_investigation']:
            raise ValueError('Python attempt budget reached for this investigation. Record a supported candidate or block it.')
        attempted = {o['investigation_key'] for o in observations} | finished
        if action.investigation_key not in attempted and len(attempted) >= options['max_investigations']:
            raise ValueError('Investigation budget reached; finish or address an already attempted investigation.')
    else:
        if action.table_ids or action.code:
            raise ValueError('Only execute may contain code or table_ids.')
        if action.action == 'record_candidate':
            if not latest or latest['status'] != 'completed' or not action.metric_keys:
                raise ValueError('A candidate requires the latest execution to succeed, with named metrics.')
            if not set(action.metric_keys) <= set(latest['result']['metrics']):
                raise ValueError('Candidate refers to missing metrics in the latest execution.')
        elif action.metric_keys:
            raise ValueError('block requires empty metric_keys.')
    return action.model_dump()
