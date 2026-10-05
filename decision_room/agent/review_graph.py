"""Persistent reviewer-led conversation; all generated code stays in the sandbox."""
from ..observability.runtime import notify
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from psycopg.types.json import Jsonb

from ..execution import execute
from .context import fingerprint
from .persistence import model_call, answers
from .review_context import approval_digest, material, model_context
from .review_contract import validate
from .research_agenda import limitation

REVIEW_GRAPH_VERSION = 'review-v7'


class ReviewBudgetReached(ValueError):
    pass


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
        attempts = run['options'].get('max_validation_attempts', 2)
        for attempt in range(attempts):
            phase = 'analyst_review' if state['role'] == 'analyst' else 'reviewer'
            def guard():
                used = db.execute('SELECT count(*) n FROM agent_calls WHERE session_id=%s AND phase=%s AND scope=%s',
                                  (session['id'], phase, str(run['id']))).fetchone()['n']
                if used >= run['options']['max_calls_per_role']:
                    raise ReviewBudgetReached('Review model-call budget reached.')
            try:
                raw = model_call(db, session['id'], model, context, correction, retry_uncertain,
                                 config=config, phase=phase, scope=str(run['id']),
                                 max_calls=run['options']['max_calls_per_role'], before_call=guard)
            except ReviewBudgetReached:
                return {'outcome': 'limited'}
            try:
                action = validate(raw, state['role'], context)
                if action['action'] == 'submit':
                    report = action['report']
                    from .review_policy import prioritize_claims
                    if not context.get('budgets', {}).get('sales_panorama'):
                        prioritize_claims(report, context.get('research_synthesis'))
                    # Replace only reserved controller scope notes, preserving all
                    # substantive caveats. Computed candidates are not delivered answers.
                    prefixes = ()
                    controller_limits = []
                    if context.get('research_coverage'):
                        prefixes += ('Cobertura del informe:', 'Cobertura de investigación:', 'Cobertura del encargo:')
                        if not context['budgets'].get('owner_presentation'):
                            controller_limits.append(limitation(context['research_coverage'], report))
                    if context.get('review_policy', 0) >= 5:
                        from .delivery_selection import selection_notes
                        prefixes += ('Selección entregada:',)
                        if not context['budgets'].get('owner_presentation'):
                            controller_limits.extend(selection_notes(report, context['observations']))
                    limits = [l for l in report['limitations'] if not l.startswith(prefixes)]
                    report['limitations'] = [*limits, *controller_limits]
                    action = validate(action, state['role'], context)
                break
            except ValueError as error:
                correction = str(error)[:1800]
                if attempt + 1 == attempts:
                    count = 'twice' if attempts == 2 else f'{attempts} times'
                    raise ValueError(f'Review action failed validation {count}: ' + correction) from None
                if attempts > 2:
                    # A distinct correction key prevents replaying the same invalid
                    # cached repair forever. No invalid event is accepted or saved.
                    correction = f'Repair {attempt + 1}/{attempts}: {correction} Return complete corrected JSON; all evidence and approval requirements still apply.'
        step = state['turn'] + 1
        existing = db.execute('SELECT action FROM agent_review_events WHERE review_id=%s AND step=%s', (run['id'], step)).fetchone()
        if existing and fingerprint(existing['action']) != fingerprint(action):
            raise ValueError('Review replay changed a persisted action.')
        db.execute('''INSERT INTO agent_review_events(review_id,step,business_id,role,action,knowledge_sha256)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                   (run['id'], step, session['business_id'], state['role'], Jsonb(action), current['knowledge_sha256']))
        notify(db)
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
