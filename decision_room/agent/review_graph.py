"""Persistent reviewer-led conversation; all generated code stays in the sandbox."""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from psycopg.types.json import Jsonb

from ..execution import execute
from .context import fingerprint
from .persistence import model_call, answers
from .review_context import approval_digest, material, model_context
from .review_contract import validate

REVIEW_GRAPH_VERSION = 'review-v7'


class ReviewState(TypedDict):
    turn: int
    role: str
    action: dict
    outcome: str


def build(config, db, session, run, analyst, reviewer, saver, *, executor=execute, retry_uncertain=False):
    def fresh():
        return db.execute('SELECT * FROM agent_reviews WHERE id=%s', (run['id'],)).fetchone()

    def decide(state):
        current = fresh()
        saved = db.execute('SELECT * FROM agent_review_events WHERE review_id=%s AND step=%s',
                           (run['id'], state['turn'] + 1)).fetchone()
        if saved:
            if saved['role'] != state['role'] or saved['knowledge_sha256'] != current['knowledge_sha256']:
                raise ValueError('Persisted decision no longer matches this review state.')
            return {'turn': saved['step'], 'action': saved['action']}
        context = model_context(material(config, db, session, current), state['role'])
        budget = context['budgets']
        if state['turn'] >= budget['max_turns'] or (state['role'] == 'reviewer' and budget['review_rounds_used'] >= budget['max_review_rounds']):
            return {'outcome': 'limited'}
        model = analyst if state['role'] == 'analyst' else reviewer
        correction = None
        for attempt in range(2):
            raw = model_call(db, session['id'], model, context, correction, retry_uncertain,
                             config=config, phase='analyst_review' if state['role'] == 'analyst' else 'reviewer',
                             scope=str(run['id']), max_calls=run['options']['max_calls_per_role'])
            try:
                action = validate(raw, state['role'], context)
                break
            except ValueError as error:
                correction = str(error)[:1800]
                if attempt:
                    raise ValueError('Review action failed validation twice: ' + correction) from None
        step = state['turn'] + 1
        existing = db.execute('SELECT action FROM agent_review_events WHERE review_id=%s AND step=%s', (run['id'], step)).fetchone()
        if existing and fingerprint(existing['action']) != fingerprint(action):
            raise ValueError('Review replay changed a persisted action.')
        db.execute('''INSERT INTO agent_review_events(review_id,step,business_id,role,action,knowledge_sha256)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                   (run['id'], step, session['business_id'], state['role'], Jsonb(action), current['knowledge_sha256']))
        return {'turn': step, 'action': action}

    def python(state):
        from ..memory.context import ensure
        ensure(db, session['id'])
        current = fresh()
        action = state['action']
        tables = {t['alias']: t['id'] for t in run['snapshot']['tables'] if t['id'] in action['table_ids']}
        result = executor(config, session['business_id'], session['analysis_id'], code=action['code'], tables=tables,
                          definitions={'owner_context': run['snapshot']['source']['owner_context'],
                                       'answers': answers(db, session['id']), 'knowledge_sha256': current['knowledge_sha256'],
                                       'context_manifest_id': str(session['id']), 'review_id': str(run['id']), 'role': state['role']},
                          request_key=f'review:{run["id"]}:{state["turn"]}', timeout=run['options']['python_timeout'])
        db.execute('UPDATE agent_review_events SET execution_id=%s WHERE review_id=%s AND step=%s',
                   (result['id'], run['id'], state['turn']))
        if result['status'] in ('preparing', 'running'):
            raise ValueError('Unfinished Python needs recover-executions before review-resume.')
        return {}

    def owner(state):
        # The question is already durable; this node's restart has no side effects.
        interrupt({'review_id': str(run['id']), 'step': state['turn'], 'question': state['action']['question']})
        reply = db.execute('SELECT 1 FROM agent_review_answers WHERE review_id=%s AND step=%s', (run['id'], state['turn'])).fetchone()
        if not reply:
            raise ValueError('Persist the owner answer before resuming the review.')
        return {'role': 'analyst'}

    def handoff(state):
        return {'role': 'reviewer' if state['action']['action'] == 'submit' else 'analyst'}

    def finish(state):
        if state['outcome']:
            return {}
        status = {'approve': 'approved', 'reject': 'rejected', 'withdraw': 'withdrawn'}[state['action']['action']]
        if status == 'approved':
            from ..memory.context import ensure
            ensure(db, session['id'])
            current = fresh()
            context = material(config, db, session, current)
            # Revalidate on replay before storing approval of this exact content.
            validate(state['action'], 'reviewer', model_context(context, 'reviewer'))
            db.execute('UPDATE agent_reviews SET approved_sha256=%s WHERE id=%s',
                       (approval_digest(context, current['knowledge_sha256']), run['id']))
        return {'outcome': status}

    graph = StateGraph(ReviewState)
    for name, node in [('decide', decide), ('python', python), ('owner', owner), ('handoff', handoff), ('finish', finish)]:
        graph.add_node(name, node)
    graph.add_edge(START, 'decide')
    graph.add_conditional_edges('decide', lambda s: 'finish' if s['outcome'] else
        {'execute': 'python', 'ask_owner': 'owner', 'submit': 'handoff', 'revise': 'handoff',
         'approve': 'finish', 'reject': 'finish', 'withdraw': 'finish'}[s['action']['action']])
    for node in ('python', 'owner', 'handoff'):
        graph.add_edge(node, 'decide')
    graph.add_edge('finish', END)
    return graph.compile(checkpointer=saver)
