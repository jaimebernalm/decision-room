"""Business-scoped research runs tied to immutable planning knowledge."""
from ..observability.runtime import session_tracked
from uuid import uuid4

from langsmith import tracing_context
from langgraph.types import Command
from psycopg.types.json import Jsonb

from ..database import connect
from ..memory import context as memory_context
from ..memory.service import lock as memory_lock
from ..execution import execute, get_execution
from .context import fingerprint, snapshot as source_snapshot
from .model import ModelClient, ModelSettings
from .persistence import answers, session_lock, checkpointer
from .research_agenda import coverage
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


def start(config, business_id, session_id, *, request_key, max_investigations=None,
          investigation_keys=None, python_timeout=30, max_rounds=None, max_executions=None,
          max_model_calls=None, max_turns=None, max_seconds=None, max_parallel=3, delegation=True,
          business_planner=False, quality_first=False, research_continuity=None, research_validation_recovery=None, model=None, executor=execute):
    research_validation_recovery = config.research_validation_recovery if research_validation_recovery is None else research_validation_recovery
    if type(research_validation_recovery) is not bool:
        raise ValueError('Research validation recovery flag must be boolean.')
    research_continuity = config.research_continuity if research_continuity is None else research_continuity
    if type(research_continuity) is not bool:
        raise ValueError('Research continuity flag must be boolean.')
    if type(business_planner) is not bool or type(quality_first) is not bool:
        raise ValueError('Planner and quality profile flags must be boolean.')
    max_investigations = max_investigations if max_investigations is not None else (12 if quality_first else 6)
    max_rounds = max_rounds if max_rounds is not None else (8 if quality_first else 3)
    max_executions = max_executions if max_executions is not None else (48 if quality_first else 12)
    max_model_calls = max_model_calls if max_model_calls is not None else (128 if quality_first else 32)
    max_turns = max_turns if max_turns is not None else (192 if quality_first else 32)
    max_seconds = max_seconds if max_seconds is not None else (3600 if quality_first else 900)
    if not isinstance(request_key, str) or not request_key.strip() or len(request_key) > 160:
        raise ValueError('Research request key must contain 1–160 characters.')
    for name, value, cap in [('investigations', max_investigations, 24), ('rounds', max_rounds, 12),
                             ('executions', max_executions, 96), ('model calls', max_model_calls, 256),
                             ('turns', max_turns, 256), ('seconds', max_seconds, 7200)]:
        if type(value) is not int or not 1 <= value <= cap:
            raise ValueError(f'Research {name} must be between 1 and {cap}.')
    if type(python_timeout) is not int or not 1 <= python_timeout <= 120:
        raise ValueError('Python timeout must be 1–120 seconds.')
    if type(max_parallel) is not int or not 1 <= max_parallel <= 3 or type(delegation) is not bool:
        raise ValueError('Research concurrency must be 1–3; delegation must be boolean.')
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
        if session['source_snapshot'].get('research_panorama'):
            from .panorama_research import validate as validate_panorama
            validate_panorama(plan, session['source_snapshot'])
        allowed = set(revision['inspected_table_ids'])
        table_catalog = [{**t, 'alias': f't{n + 1}'} for n, t in enumerate(session['source_snapshot']['tables']) if t['id'] in allowed]
        saved = {'source': session['source_snapshot'], 'proposal': plan, 'answers': owner_answers, 'tables': table_catalog}
        options = {'max_parallel': max_parallel, 'delegation': delegation, 'max_investigations': max_investigations, 'max_attempts_per_investigation': 6 if quality_first else 3,
                   'max_turns': max_turns, 'max_model_calls': max_model_calls, 'python_timeout': python_timeout,
                   'max_rounds': max_rounds, 'max_executions': max_executions, 'max_seconds': max_seconds, 'max_agenda': 24}
        options.update(delivery_quality=1, business_planner=business_planner, quality_first=quality_first, max_planner_checkpoints=24,
                       max_context_bytes=512000 if quality_first else 200000)
        if session['source_snapshot'].get('research_panorama'):
            options['sales_panorama_research'] = True
        if research_validation_recovery:
            options['research_validation_recovery'] = True
        if research_continuity:
            options['research_continuity'] = True
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


@session_tracked
def _drive(config, db, session, run, *, model=None, executor=execute, retry_uncertain=False):
    try:
        memory_context.ensure(db, session['id'])
        _, _, current_key = knowledge(db, session)
        current_source = source_snapshot(config, session['business_id'], session['analysis_id'], session['source_snapshot']['owner_context'], research_panorama=session['source_snapshot'].get('research_panorama'))
        if session['superseded_by'] or current_key != run['knowledge_sha256'] or fingerprint(current_source) != fingerprint(session['source_snapshot']):
            raise StaleResearch('Knowledge or source changed. Start research from the current plan; previous results are stale.')
        if run['status'] == 'stale':
            raise StaleResearch('This research run is stale. Use the current planning session.')
        if run['graph_version'] not in (RESEARCH_GRAPH_VERSION, 'research-v5', 'research-v4'):
            raise ValueError('Research graph version needs migration.')
        model = model or ModelClient(ModelSettings(**session['model_settings']))
        if model.identity != session['model_settings']:
            raise ValueError('Research must use the planning model settings; replan to change model.')
        with checkpointer(config) as saver, tracing_context(enabled=False):
            graph = build(config, db, session, run, model, saver, executor=executor, retry_uncertain=retry_uncertain)
            run_config = {'configurable': {'thread_id': 'research:' + str(run['id'])}, 'recursion_limit': 1024}
            state = graph.get_state(run_config)
            waiting = any(task.interrupts for task in state.tasks)
            from .business_planner import pending
            if waiting and pending(db,run['id']):
                db.execute("UPDATE agent_research SET status='waiting',issue=NULL WHERE id=%s",(run['id'],))
                return
            db.execute("UPDATE agent_research SET status='running',issue=NULL,updated_at=now() WHERE id=%s", (run['id'],))
            if not state.values or state.next:
                graph.invoke(Command(resume=True) if waiting else None if state.values else {'turn': 0, 'action': {}, 'stop_reason': ''},
                             run_config, durability='sync')
            state = graph.get_state(run_config)
            summary = coverage(run['snapshot'], steps(db, run['id']), findings(db, run['id']), run['options'], state.values['stop_reason'])
            ready = summary['complete'] and (not run['options'].get('business_planner') or state.values.get('planner_ready'))
            status = 'waiting' if any(task.interrupts for task in state.tasks) else 'replan_required' if state.values.get('replan_required') else 'completed' if ready else 'partial'
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
        from .parallel_research import branches, calls, synthesis
        model_calls = calls(db, run['session_id'], research_id)
        branch_rows = branches(db, research_id)
        summary = coverage(run['snapshot'], history, recorded, run['options'], run['issue'] or '')
        progress = summary['investigations']
        if stale:
            progress = [{**i, 'research_status': 'stale'} for i in progress]
        from .business_planner import events, replies, pending
        return {k: v for k, v in {**run, 'status': 'stale' if stale else run['status'],
                'business_direction': events(db,research_id), 'business_answers': replies(db,research_id),
                'pending_questions': [dict(id=str(q['id']), **q['question']) for q in pending(db,research_id)],
                'verification': 'stale' if stale else 'pending_reviewer', 'publishable': False,
                'investigations': progress, 'coverage': summary, 'steps': history, 'findings': recorded, 'model_calls': [{k: c[k] for k in ('id', 'scope', 'status', 'usage', 'issue', 'created_at', 'finished_at', 'prompt_version')} for c in model_calls], 'branches': branch_rows, 'synthesis': synthesis(history)}.items()
                if k != 'snapshot'}


def answer(config, business_id, research_id, *, question_id, text='', disposition='answered', request_key, model=None, executor=execute, retry_uncertain=False):
    with connect(config) as db:
        parent=db.execute('SELECT session_id FROM agent_research WHERE id=%s AND business_id=%s',(research_id,business_id)).fetchone()
    if not parent: raise ValueError('Research does not belong to this business.')
    with session_lock(config,business_id,parent['session_id']) as (db,session):
        run=db.execute('SELECT * FROM agent_research WHERE id=%s',(research_id,)).fetchone()
        from .business_planner import save_answer
        save_answer(db,session,run,question_id,text,disposition,request_key)
        run=db.execute('SELECT * FROM agent_research WHERE id=%s',(research_id,)).fetchone()
        _drive(config,db,session,run,model=model,executor=executor,retry_uncertain=retry_uncertain)
    return show(config,business_id,research_id)
