"""Choose → isolated Python → inspect/correct → candidate; never host exec()."""
from typing import TypedDict
from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph
from psycopg.types.json import Jsonb

from ..execution import execute
from .context import fingerprint
from .persistence import model_call
from .research_context import observations, prompt_context
from .research_contract import validate_research_action
from .research_agenda import agenda, ResearchBudgetReached

RESEARCH_GRAPH_VERSION = 'research-v4'


class ResearchState(TypedDict):
    turn: int
    action: dict
    stop_reason: str


def steps(db, run_id):
    return db.execute('SELECT * FROM agent_research_steps WHERE research_id=%s ORDER BY step', (run_id,)).fetchall()


def findings(db, run_id):
    rows = db.execute('''SELECT f.*,s.execution_id FROM agent_research_findings f
        JOIN agent_research_steps s ON s.research_id=f.research_id AND s.step=f.step
        WHERE f.research_id=%s ORDER BY f.step''', (run_id,)).fetchall()
    return [{**row, 'research_id': str(row['research_id']),
             'execution_id': str(row['execution_id']) if row['execution_id'] else None} for row in rows]


def build(config, db, session, run, model, saver, *, retry_uncertain=False, executor=execute):
    snapshot, options, run_id = run['snapshot'], run['options'], run['id']

    def guard():
        if (datetime.now(timezone.utc) - run['created_at']).total_seconds() >= options['max_seconds']:
            raise ResearchBudgetReached('Presupuesto de tiempo alcanzado; se conservan los resultados parciales.')
        count = db.execute("SELECT count(*) n FROM agent_calls WHERE session_id=%s AND phase='research' AND scope=%s",
                           (session['id'], str(run_id))).fetchone()['n']
        if count >= options['max_model_calls']:
            raise ResearchBudgetReached('Presupuesto de llamadas alcanzado; se conservan los resultados parciales.')

    def decide(state):
        prior_steps = steps(db, run_id)
        saved = next((s for s in prior_steps if s['step'] == state['turn'] + 1), None)
        if saved:
            return {'turn': saved['step'], 'action': saved['action']}
        if state['turn'] >= options['max_turns']:
            return {'stop_reason': 'Presupuesto de decisiones alcanzado.'}
        results = observations(config, session['business_id'], prior_steps)
        recorded = findings(db, run_id)
        current = agenda(snapshot, prior_steps)
        current_options = {**options, 'discarded_keys': [s['action']['investigation_key'] for s in prior_steps if s['action']['action'] == 'discard']}
        try:
            context = prompt_context(current, results, recorded, current_options, state['turn'])
        except ResearchBudgetReached as error:
            return {'stop_reason': str(error)}
        correction = None
        for attempt in range(2):
            try:
                raw = model_call(db, session['id'], model, context, correction, retry_uncertain,
                                 config=config, phase='research', scope=str(run_id), max_calls=options['max_model_calls'], before_call=guard)
            except ResearchBudgetReached as error:
                return {'stop_reason': str(error)}
            try:
                action = validate_research_action(raw, current, results, recorded, current_options)
                if action['action'] == 'record_candidate':
                    last = next(o for o in reversed(context['observations'])
                                if o['investigation_key'] == action['investigation_key'])
                    if last.get('result_omitted'):
                        raise ValueError('Cannot record a candidate whose result was omitted; generate focused metrics.')
                break
            except ResearchBudgetReached as error:
                return {'stop_reason': str(error)}
            except ValueError as error:
                correction = str(error)[:1500]
                if attempt:
                    raise ValueError('Research action failed validation twice: ' + correction) from None
        step = state['turn'] + 1
        # Write before the checkpoint or Python side effect. A replay must reuse
        # the cached model response and the exact same action for this step.
        existing = db.execute('SELECT action FROM agent_research_steps WHERE research_id=%s AND step=%s', (run_id, step)).fetchone()
        if existing and fingerprint(existing['action']) != fingerprint(action):
            raise ValueError('Research replay produced a different action for an existing step.')
        db.execute('''INSERT INTO agent_research_steps(research_id,step,business_id,action)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (run_id, step, session['business_id'], Jsonb(action)))
        return {'turn': step, 'action': action}

    def python(state):
        from ..memory.context import ensure
        ensure(db, session['id'])
        action = state['action']
        prior = db.execute('SELECT id FROM executions WHERE business_id=%s AND request_key=%s',
                           (session['business_id'], f'research:{run_id}:{state["turn"]}')).fetchone()
        if not prior and (datetime.now(timezone.utc) - run['created_at']).total_seconds() >= options['max_seconds']:
            return {'stop_reason': 'Presupuesto de tiempo alcanzado antes de ejecutar Python.'}
        selected = {t['alias']: t['id'] for t in snapshot['tables'] if t['id'] in action['table_ids']}
        definition = {'owner_context': snapshot['source']['owner_context'], 'answers': snapshot['answers'],
                      'provisional_interpretations': snapshot['proposal']['interpretations'],
                      'plan_revision': run['plan_revision'], 'knowledge_sha256': run['knowledge_sha256'], 'context_manifest_id': str(session['id'])}
        result = executor(config, session['business_id'], session['analysis_id'], code=action['code'], tables=selected,
                          definitions=definition, request_key=f'research:{run_id}:{state["turn"]}',
                          timeout=options['python_timeout'])
        db.execute('UPDATE agent_research_steps SET execution_id=%s WHERE research_id=%s AND step=%s',
                   (result['id'], run_id, state['turn']))
        if result['status'] in ('preparing', 'running'):
            raise ValueError('An unfinished sandbox execution needs recover-executions before research-resume.')
        return {}

    def record(state):
        action = state['action']
        execution_id = None
        if action['action'] == 'record_candidate':
            result = db.execute('''SELECT execution_id FROM agent_research_steps WHERE research_id=%s
                AND action->>'action'='execute' AND action->>'investigation_key'=%s
                ORDER BY step DESC LIMIT 1''', (run_id, action['investigation_key'])).fetchone()
            execution_id = result['execution_id']
        with db.transaction():
            db.execute('UPDATE agent_research_steps SET execution_id=%s WHERE research_id=%s AND step=%s',
                       (execution_id, run_id, state['turn']))
            db.execute('''INSERT INTO agent_research_findings(research_id,investigation_key,step,status,summary,metric_keys)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                       (run_id, action['investigation_key'], state['turn'],
                        'candidate' if execution_id else 'blocked', action['summary'], Jsonb(action['metric_keys'])))
        return {}

    def route(state):
        if state.get('stop_reason') or state['action'].get('action') == 'finish':
            return 'stop'
        recorded = findings(db, run_id)
        history = steps(db, run_id)
        work = agenda(snapshot, history)['proposal']['investigations']
        ready = {i['key'] for i in work if i['status'] == 'ready' and i['round'] <= options['max_rounds']}
        closed = {r['investigation_key'] for r in recorded} | {s['action']['investigation_key'] for s in history if s['action']['action'] == 'discard'}
        attempted = {s['action']['investigation_key'] for s in history if s['action']['action'] == 'execute'}
        if ready <= closed:
            return 'stop'
        # Always give an attempted investigation a chance to record its result.
        if attempted <= closed and (len(attempted) >= options['max_investigations'] or
                sum(s['action']['action'] == 'execute' for s in history) >= options['max_executions']):
            return 'stop'
        if state['turn'] >= options['max_turns']:
            return 'stop'
        return 'decide'

    def stop(state):
        if state.get('stop_reason'):
            return {}
        if state['action'].get('action') == 'finish':
            return {'stop_reason': state['action']['summary']}
        history = steps(db, run_id)
        closed = {r['investigation_key'] for r in findings(db, run_id)} | {s['action']['investigation_key'] for s in history if s['action']['action'] == 'discard'}
        work = agenda(snapshot, history)['proposal']['investigations']
        outstanding = [i for i in work if i['key'] not in closed and i['status'] == 'ready']
        if not outstanding:
            reason = 'Investigaciones disponibles resueltas; no queda trabajo independiente listo.'
        elif all(i['round'] > options['max_rounds'] for i in outstanding):
            reason = 'Límite de rondas alcanzado.'
        elif state['turn'] >= options['max_turns']:
            reason = 'Presupuesto de decisiones alcanzado.'
        elif sum(s['action']['action'] == 'execute' for s in history) >= options['max_executions']:
            reason = 'Presupuesto de ejecuciones Python alcanzado.'
        else:
            reason = 'Presupuesto de investigaciones alcanzado.'
        return {'stop_reason': reason}

    graph = StateGraph(ResearchState)
    graph.add_node('decide', decide)
    graph.add_node('python', python)
    graph.add_node('record', record)
    graph.add_node('stop', stop)
    graph.add_node('discard', lambda state: {})
    graph.add_edge(START, 'decide')
    graph.add_conditional_edges('decide', lambda s: 'stop' if s.get('stop_reason') else s['action']['action'],
                                {'execute': 'python', 'record_candidate': 'record', 'block': 'record', 'discard': 'discard', 'finish': 'stop', 'stop': 'stop'})
    graph.add_conditional_edges('python', route)
    graph.add_conditional_edges('record', route)
    graph.add_conditional_edges('discard', route)
    graph.add_edge('stop', END)
    return graph.compile(checkpointer=saver)
