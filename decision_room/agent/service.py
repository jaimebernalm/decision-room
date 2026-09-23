"""Scoped CLI/application entry points; provider and checkpoint IDs stay internal."""
from uuid import UUID, uuid4

from langgraph.types import Command
from langsmith import tracing_context
from psycopg.types.json import Jsonb

from ..database import connect
from .context import fingerprint, snapshot
from .graph import build
from .model import ModelClient, ModelSettings
from .persistence import GRAPH_VERSION, answers, checkpointer, pending, session_lock


def _key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError('Request key must contain 1–200 characters.')


def _create_session(config, business_id, analysis_id, *, owner_context, request_key, model, supersedes=None):
    _key(request_key)
    source = snapshot(config, business_id, analysis_id, owner_context)
    identity = {'source': source, 'model': model.identity, 'graph': GRAPH_VERSION}
    if supersedes:
        identity['supersedes'] = str(supersedes)
    request_hash = fingerprint(identity)
    with connect(config) as db, db.transaction():
        row = db.execute('''INSERT INTO agent_sessions(id,business_id,analysis_id,request_key,
            request_sha256,source_snapshot,model_settings,graph_version,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'new')
            ON CONFLICT (business_id,analysis_id,request_key) DO NOTHING RETURNING *''',
                         (uuid4(), business_id, analysis_id, request_key, request_hash,
                          Jsonb(source), Jsonb(model.identity), GRAPH_VERSION)).fetchone()
        if not row:
            row = db.execute('''SELECT * FROM agent_sessions
                WHERE business_id=%s AND analysis_id=%s AND request_key=%s''',
                             (business_id, analysis_id, request_key)).fetchone()
        if row['request_sha256'] != request_hash:
            raise ValueError('Request key already used with different data, context or model.')
        if supersedes:
            old = db.execute('SELECT * FROM agent_sessions WHERE id=%s AND business_id=%s AND analysis_id=%s FOR UPDATE',
                             (supersedes, business_id, analysis_id)).fetchone()
            if not old or old['id'] == row['id']:
                raise ValueError('Replanning requires a different session in the same business and analysis.')
            if row['superseded_by']:
                raise ValueError('Cannot replace a session with one that was already superseded.')
            if old['superseded_by'] and old['superseded_by'] != row['id']:
                raise ValueError('This session was already superseded; replan from its successor.')
            if row['supersedes_session_id'] and row['supersedes_session_id'] != supersedes:
                raise ValueError('New session already supersedes another session.')
            db.execute('UPDATE agent_sessions SET superseded_by=%s WHERE id=%s', (row['id'], supersedes))
            db.execute('UPDATE agent_sessions SET supersedes_session_id=%s WHERE id=%s', (supersedes, row['id']))
            db.execute("UPDATE agent_research SET status='stale',issue='Owner context superseded.',updated_at=now() WHERE session_id=%s", (supersedes,))
            db.execute("UPDATE agent_reviews SET status='stale',issue='Owner context superseded.',updated_at=now() WHERE session_id=%s", (supersedes,))
    return row


def start(config, business_id, analysis_id, *, owner_context, request_key, model):
    row = _create_session(config, business_id, analysis_id, owner_context=owner_context, request_key=request_key, model=model)
    return resume(config, business_id, row['id'], model=model)


def replan(config, business_id, session_id, *, owner_context, request_key, model=None):
    with session_lock(config, business_id, session_id) as (_, session):
        model = model or ModelClient(ModelSettings(**session['model_settings']))
        row = _create_session(config, business_id, session['analysis_id'], owner_context=owner_context,
                              request_key=request_key, model=model, supersedes=session['id'])
    return resume(config, business_id, row['id'], model=model)


def show(config, business_id, session_id):
    with connect(config) as db:
        row = db.execute('''SELECT id,business_id,analysis_id,status,issue,model_settings,graph_version,
            created_at,updated_at,supersedes_session_id,superseded_by FROM agent_sessions WHERE business_id=%s AND id=%s''',
                         (business_id, session_id)).fetchone()
        if not row:
            raise ValueError('Agent session does not belong to this business.')
        revisions = db.execute('''SELECT * FROM agent_revisions WHERE session_id=%s
            ORDER BY revision''', (session_id,)).fetchall()
        calls = db.execute('''SELECT id,status,prompt_version,phase,scope,usage,issue,created_at,finished_at
            FROM agent_calls WHERE session_id=%s ORDER BY created_at''', (session_id,)).fetchall()
        return {**row, 'verification': 'provisional_not_computed', 'revisions': revisions,
                'questions': [{'id': str(q['id']), **q['question']} for q in pending(db, session_id)],
                'answers': answers(db, session_id), 'model_calls': calls,
                'cost': {'amount': None, 'note': 'Tokens recorded when supplied; no provider pricing assumed.'}}


def _drive(config, db, session, model=None, retry_uncertain=False):
    session_id = session['id']
    if session['superseded_by']:
        raise ValueError('This session was superseded; use its successor.')
    try:
        from .research import mark_stale
        mark_stale(db, session)
        if session['graph_version'] != GRAPH_VERSION:
            raise ValueError('Session graph version needs migration before resuming.')
        current = snapshot(config, session['business_id'], session['analysis_id'],
                           session['source_snapshot']['owner_context'])
        if fingerprint(current) != fingerprint(session['source_snapshot']):
            raise ValueError('Source metadata changed. Start a new session to reinterpret this batch.')
        if model is None:
            model = ModelClient(ModelSettings(**session['model_settings']))
        if model.identity != session['model_settings']:
            raise ValueError('Resume must use the original model settings; start a new session to compare models.')
        with checkpointer(config) as saver, tracing_context(enabled=False):
            graph = build(db, session, model, saver, retry_uncertain)
            run_config = {'configurable': {'thread_id': str(session_id)}, 'recursion_limit': 64}
            state = graph.get_state(run_config)
            waiting = any(task.interrupts for task in state.tasks)
            if waiting and pending(db, session_id):
                db.execute("UPDATE agent_sessions SET status='waiting',issue=NULL,updated_at=now() WHERE id=%s", (session_id,))
                return
            if not state.values:
                tables = session['source_snapshot']['tables']
                initial = {'inspected': [t['id'] for t in tables] if len(tables) <= 3 else [],
                           'answers': [], 'proposal': None, 'action': {}, 'revision': 0, 'turns': 0}
            elif waiting:
                initial = Command(resume=answers(db, session_id))
            elif state.next:
                initial = None
            else:
                # Checkpoint already finished, possibly before a process crash updated status.
                initial = None
            db.execute("UPDATE agent_sessions SET status='running',issue=NULL,updated_at=now() WHERE id=%s", (session_id,))
            if not state.values or state.next:
                graph.invoke(initial, run_config, durability='sync')
            state = graph.get_state(run_config)
            if any(task.interrupts for task in state.tasks):
                status = 'waiting'
            else:
                proposal = state.values['proposal']
                status = 'limited' if any(i['status'] != 'ready' for i in proposal['investigations']) else 'ready'
            db.execute('UPDATE agent_sessions SET status=%s,issue=NULL,updated_at=now() WHERE id=%s', (status, session_id))
    except Exception as error:
        # Known validation errors are useful, unexpected errors get a safe class name.
        issue = str(error)[:2000] if isinstance(error, ValueError) else type(error).__name__
        db.execute("UPDATE agent_sessions SET status='failed',issue=%s,updated_at=now() WHERE id=%s", (issue, session_id))
        raise ValueError(f'Agent session {session_id} failed: {issue}') from None


def resume(config, business_id, session_id, *, model=None, retry_uncertain=False):
    with session_lock(config, business_id, session_id) as (db, session):
        _drive(config, db, session, model, retry_uncertain)
    return show(config, business_id, session_id)


def answer(config, business_id, session_id, *, question_id, text='', disposition='answered',
           request_key, model=None, retry_uncertain=False):
    _key(request_key)
    if disposition not in ('answered', 'unknown', 'declined') or len(text) > 6000:
        raise ValueError('Invalid answer disposition or answer exceeds 6,000 characters.')
    if disposition == 'answered' and not text.strip():
        raise ValueError('An answered question requires text; otherwise choose unknown or declined.')
    with session_lock(config, business_id, session_id) as (db, session):
        question = db.execute('SELECT * FROM agent_questions WHERE session_id=%s AND id=%s',
                              (session_id, question_id)).fetchone()
        if not question:
            raise ValueError('Question does not belong to this session.')
        prior = db.execute('SELECT * FROM agent_answers WHERE question_id=%s', (question_id,)).fetchone()
        if prior:
            if (prior['request_key'], prior['text'], prior['disposition']) != (request_key, text, disposition):
                raise ValueError('Question already answered differently. Start a new session for revised owner context.')
        else:
            if session['superseded_by']:
                raise ValueError('This session was superseded; answer in its successor.')
            db.execute('''INSERT INTO agent_answers(id,question_id,disposition,text,request_key)
                VALUES (%s,%s,%s,%s,%s)''', (uuid4(), question_id, disposition, text, request_key))
        _drive(config, db, session, model, retry_uncertain)
    return show(config, business_id, session_id)
