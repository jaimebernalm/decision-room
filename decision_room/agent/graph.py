"""A bounded interpretation loop with a durable human-in-the-loop interrupt."""
from typing import TypedDict
from copy import deepcopy

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .context import model_context
from .contracts import validate_action
from .persistence import model_call, pending, save_revision


class State(TypedDict):
    inspected: list[str]
    answers: list[dict]
    proposal: dict | None
    action: dict
    revision: int
    turns: int


def build(db, session, model, saver, retry_uncertain=False, config=None):
    source, session_id = session['source_snapshot'], session['id']

    def reason(state):
        if state['turns'] >= 16:
            raise ValueError('Planning turn budget exhausted (16).')
        context = model_context(source, state['inspected'], state['answers'], state['proposal'])
        correction = None
        for attempt in range(2):
            raw = model_call(db, session_id, model, context, correction, retry_uncertain, config=config)
            try:
                from ..memory.context import delivered
                action = validate_action(raw, {**source, 'business_context': delivered(db, session_id)}, state['inspected'], state['answers'], state['proposal'])
                if state['revision'] >= 3 and (action.get('proposal') or {}).get('questions'):
                    raise ValueError('Question budget exhausted; express remaining unknowns as limitations and blocked work.')
                return {'action': action, 'turns': state['turns'] + 1}
            except ValueError as error:
                correction = str(error)[:1500]
                if attempt:
                    raise ValueError('Model output failed validation twice: ' + correction) from None

    def inspect(state):
        return {'inspected': sorted(set(state['inspected']) | set(state['action']['table_ids']))}

    def record(state):
        revision, proposal = state['revision'] + 1, deepcopy(state['action']['proposal'])
        missing = [t['id'] for t in source['tables'] if t['id'] not in state['inspected']]
        if missing:
            proposal['limitations'].append(f'Application: {len(missing)} table profiles remain uninspected.')
        save_revision(db, session_id, revision, proposal, state['inspected'])
        from .research import mark_stale
        mark_stale(db, session)
        return {'revision': revision, 'proposal': proposal}

    def ask(state):
        # No writes before interrupt: this entire node runs again after resume.
        questions = [{'id': str(q['id']), **q['question']} for q in pending(db, session_id)]
        return {'answers': interrupt({'type': 'owner_questions', 'questions': questions})}

    graph = StateGraph(State)
    graph.add_node('reason', reason)
    graph.add_node('inspect', inspect)
    graph.add_node('record', record)
    graph.add_node('ask', ask)
    graph.add_edge(START, 'reason')
    graph.add_conditional_edges('reason', lambda s: s['action']['action'], {'inspect': 'inspect', 'propose': 'record'})
    graph.add_edge('inspect', 'reason')
    graph.add_conditional_edges('record', lambda s: 'ask' if s['proposal']['questions'] else END)
    graph.add_edge('ask', 'reason')
    return graph.compile(checkpointer=saver)
