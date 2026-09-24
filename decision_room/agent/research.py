"""Business-scoped research runs tied to immutable planning knowledge."""
from uuid import uuid4

from langsmith import tracing_context
from psycopg.types.json import Jsonb

from ..database import connect
from ..memory import context as memory_context
from ..memory.service import lock as memory_lock
from ..execution import execute, get_execution
from .context import fingerprint, snapshot as source_snapshot
from .model import ModelClient, ModelSettings
from .persistence import answers, session_lock, checkpointer
from .research_graph import RESEARCH_GRAPH_VERSION, build, findings, steps


class StaleResearch(ValueError):
    pass


def knowledge(db, session):
    revision = db.execute('SELECT * FROM agent_revisions WHERE session_id=%s ORDER BY revision DESC LIMIT 1',
                          (session['id'],)).fetchone()
    if not revision:
        raise ValueError('The agent must save a provisional plan before researching.')
    owner_answers = answers(db, session['id'])
    shared = memory_context.manifest(db, session['id'])
    identity = {'revision': revision['revision'], 'proposal': revision['proposal'],
                'answers': owner_answers, 'source': session['source_snapshot']}
    if shared:
        identity['business_context'] = shared['initial_context']
    key = fingerprint(identity)
    return revision, owner_answers, key


def mark_stale(db, session):
    """Called after owner answers/planning updates, including before model retries."""
    revision = db.execute('SELECT 1 FROM agent_revisions WHERE session_id=%s LIMIT 1', (session['id'],)).fetchone()
    if revision:
        _, _, key = knowledge(db, session)
        db.execute("""UPDATE agent_research SET status='stale',issue='Owner knowledge or plan changed.',updated_at=now()
            WHERE session_id=%s AND knowledge_sha256<>%s AND status<>'stale'""", (session['id'], key))
        db.execute("""UPDATE agent_reviews SET status='stale',issue='Owner knowledge or plan changed.',updated_at=now()
            WHERE session_id=%s AND knowledge_sha256<>%s AND status<>'stale'""", (session['id'], key))


def start(config, business_id, session_id, *, request_key, max_investigations=2,
          investigation_keys=None, python_timeout=30, model=None, executor=execute):
    if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 160:
        raise ValueError('Research request key must contain 1–160 characters.')
    if type(max_investigations) is not int or not 1 <= max_investigations <= 3:
        raise ValueError('Select 1–3 investigations per research run.')
    if type(python_timeout) is not int or not 1 <= python_timeout <= 120:
        raise ValueError('Python timeout must be 1–120 seconds.')
    keys = sorted(set(investigation_keys or []))
    with session_lock(config, business_id, session_id) as (db, session):
        if session['superseded_by']:
            raise ValueError('This planning session was superseded; use the new session.')
        memory_context.ensure(db, session['id'])
        revision, owner_answers, key = knowledge(db, session)
        plan = {**revision['proposal'], 'investigations': [i for i in revision['proposal']['investigations']
                                                       if not keys or i['key'] in keys]}
        if keys and set(keys) != {i['key'] for i in plan['investigations']}:
            raise ValueError('Unknown investigation key for this plan.')
        if not any(i['status'] == 'ready' for i in plan['investigations']):
            raise ValueError('No investigation is ready; resolve required definitions first.')
        allowed = set(revision['inspected_table_ids'])
        table_catalog = [{**t, 'alias': f't{n + 1}'} for n, t in enumerate(session['source_snapshot']['tables']) if t['id'] in allowed]
        saved = {'source': session['source_snapshot'], 'proposal': plan, 'answers': owner_answers, 'tables': table_catalog}
        options = {'max_investigations': max_investigations, 'max_attempts_per_investigation': 3,
                   'max_turns': 12, 'max_model_calls': 16, 'python_timeout': python_timeout}
        request_hash = fingerprint({'knowledge': key, 'options': options, 'keys': keys, 'version': RESEARCH_GRAPH_VERSION})
        row = db.execute('''INSERT INTO agent_research(id,business_id,session_id,analysis_id,plan_revision,
            request_key,request_sha256,knowledge_sha256,snapshot,options,graph_version,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'new') ON CONFLICT (session_id,request_key) DO NOTHING RETURNING *''',
                         (uuid4(), business_id, session_id, session['analysis_id'], revision['revision'], request_key,
                          request_hash, key, Jsonb(saved), Jsonb(options), RESEARCH_GRAPH_VERSION)).fetchone()
        if not row:
            row = db.execute('SELECT * FROM agent_research WHERE session_id=%s AND request_key=%s', (session_id, request_key)).fetchone()
        if row['request_sha256'] != request_hash:
            raise ValueError('Research request key already used with different knowledge or options.')
        _drive(config, db, session, row, model=model, executor=executor)
    return show(config, business_id, row['id'])


def _drive(config, db, session, run, *, model=None, executor=execute, retry_uncertain=False):
    try:
        memory_context.ensure(db, session['id'])
        _, _, current_key = knowledge(db, session)
        current_source = source_snapshot(config, session['business_id'], session['analysis_id'], session['source_snapshot']['owner_context'])
        if session['superseded_by'] or current_key != run['knowledge_sha256'] or fingerprint(current_source) != fingerprint(session['source_snapshot']):
            raise StaleResearch('Knowledge or source changed. Start research from the current plan; previous results are stale.')
        if run['status'] == 'stale':
            raise StaleResearch('This research run is stale. Use the current planning session.')
        if run['graph_version'] != RESEARCH_GRAPH_VERSION:
            raise ValueError('Research graph version needs migration.')
        model = model or ModelClient(ModelSettings(**session['model_settings']))
        if model.identity != session['model_settings']:
            raise ValueError('Research must use the planning model settings; replan to change model.')
        with checkpointer(config) as saver, tracing_context(enabled=False):
            graph = build(config, db, session, run, model, saver, executor=executor, retry_uncertain=retry_uncertain)
            run_config = {'configurable': {'thread_id': 'research:' + str(run['id'])}, 'recursion_limit': 64}
            state = graph.get_state(run_config)
            db.execute("UPDATE agent_research SET status='running',issue=NULL,updated_at=now() WHERE id=%s", (run['id'],))
            if not state.values or state.next:
                graph.invoke(None if state.values else {'turn': 0, 'action': {}, 'stop_reason': ''},
                             run_config, durability='sync')
            state = graph.get_state(run_config)
            candidates = {f['investigation_key'] for f in findings(db, run['id']) if f['status'] == 'candidate'}
            all_work = {i['key'] for i in run['snapshot']['proposal']['investigations']}
            status = 'completed' if all_work <= candidates else 'partial'
            with db.transaction():
                memory_lock(db, session['business_id'])
                memory_context.ensure(db, session['id'])
                db.execute('UPDATE agent_research SET status=%s,issue=%s,updated_at=now() WHERE id=%s',
                           (status, state.values['stop_reason'], run['id']))
    except Exception as error:
        status = 'stale' if isinstance(error, (StaleResearch, memory_context.StaleContext)) else 'failed'
        issue = str(error)[:2000] if isinstance(error, ValueError) else type(error).__name__
        db.execute('UPDATE agent_research SET status=%s,issue=%s,updated_at=now() WHERE id=%s', (status, issue, run['id']))
        raise ValueError(f'Research {run["id"]} {status}: {issue}') from None


def resume(config, business_id, research_id, *, model=None, executor=execute, retry_uncertain=False):
    with connect(config) as db:
        row = db.execute('SELECT session_id FROM agent_research WHERE business_id=%s AND id=%s', (business_id, research_id)).fetchone()
    if not row:
        raise ValueError('Research does not belong to this business.')
    with session_lock(config, business_id, row['session_id']) as (db, session):
        run = db.execute('SELECT * FROM agent_research WHERE id=%s', (research_id,)).fetchone()
        _drive(config, db, session, run, model=model, executor=executor, retry_uncertain=retry_uncertain)
    return show(config, business_id, research_id)


def show(config, business_id, research_id):
    with connect(config) as db:
        run = db.execute('SELECT * FROM agent_research WHERE business_id=%s AND id=%s', (business_id, research_id)).fetchone()
        if not run:
            raise ValueError('Research does not belong to this business.')
        session = db.execute('SELECT * FROM agent_sessions WHERE id=%s', (run['session_id'],)).fetchone()
        _, _, current_key = knowledge(db, session)
        stale = bool(memory_context.reason(db, session['id']) or session['superseded_by'] or current_key != run['knowledge_sha256'] or run['status'] == 'stale')
        history, recorded = steps(db, research_id), findings(db, research_id)
        for item in history:
            if item['execution_id']:
                execution = get_execution(config, business_id, item['execution_id'])
                item['execution'] = {k: execution[k] for k in ('id', 'status', 'result', 'logs', 'issue', 'code_key',
                                                               'code_sha256', 'environment', 'artifacts', 'duration_seconds')}
        calls = db.execute('''SELECT id,status,usage,issue,created_at,finished_at,prompt_version
            FROM agent_calls WHERE session_id=%s AND phase='research' AND scope=%s ORDER BY created_at''',
                           (run['session_id'], str(research_id))).fetchall()
        by_key = {f['investigation_key']: f['status'] for f in recorded}
        for item in history:
            key = item['action']['investigation_key']
            if item['action']['action'] == 'execute' and key not in {f['investigation_key'] for f in recorded}:
                execution = item.get('execution')
                by_key[key] = ('awaiting_candidate' if execution and execution['status'] == 'completed'
                               else 'execution_failed' if execution and execution['status'] not in ('preparing', 'running')
                               else 'in_progress')
        progress = [{**i, 'research_status': 'stale' if stale else by_key.get(i['key'],
                          'not_started' if i['status'] == 'ready' else 'pending_definition')}
                    for i in run['snapshot']['proposal']['investigations']]
        return {k: v for k, v in {**run, 'status': 'stale' if stale else run['status'],
                'verification': 'stale' if stale else 'pending_reviewer', 'publishable': False,
                'investigations': progress, 'steps': history, 'findings': recorded, 'model_calls': calls}.items()
                if k != 'snapshot'}
