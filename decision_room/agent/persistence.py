"""Domain records and private LangGraph checkpoints in the existing PostgreSQL."""
from contextlib import contextmanager
from uuid import UUID, uuid4, uuid5

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.types.json import Jsonb

from ..database import connect
from .context import fingerprint
from .prompts import PROMPT_VERSION
from .model import ModelRequestUncertain
from .research_prompts import RESEARCH_PROMPT_VERSION
from .review_prompts import REVIEW_PROMPT_VERSION

GRAPH_VERSION = 'planning-v2'


@contextmanager
def checkpointer(config):
    with connect(config) as db:
        db.execute('SELECT pg_advisory_lock(87120933)')
        try:
            db.execute('CREATE SCHEMA IF NOT EXISTS agent_checkpoints')
            db.execute('SET search_path TO agent_checkpoints')
            # Only primitive JSON state; never deserialize pickle from checkpoints.
            saver = PostgresSaver(db, serde=JsonPlusSerializer(pickle_fallback=False))
            saver.setup()
        finally:
            db.execute('SELECT pg_advisory_unlock(87120933)')
        yield saver


@contextmanager
def session_lock(config, business_id, session_id):
    session_id = UUID(str(session_id))
    with connect(config) as db:
        row = db.execute('SELECT * FROM agent_sessions WHERE business_id=%s AND id=%s',
                         (business_id, session_id)).fetchone()
        if not row:
            raise ValueError('Agent session does not belong to this business.')
        lock = int.from_bytes(session_id.bytes[:8], 'big', signed=True)
        if not db.execute('SELECT pg_try_advisory_lock(%s) AS locked', (lock,)).fetchone()['locked']:
            raise ValueError('This agent session is already running; retry after it finishes.')
        try:
            # Re-read after acquiring the lock, so concurrent answers cannot use stale state.
            yield db, db.execute('SELECT * FROM agent_sessions WHERE id=%s', (session_id,)).fetchone()
        finally:
            db.execute('SELECT pg_advisory_unlock(%s)', (lock,))


def answers(db, session_id):
    records = db.execute('''SELECT a.id, q.key, q.question, a.disposition, a.text
        FROM agent_answers a JOIN agent_questions q ON q.id=a.question_id
        WHERE q.session_id=%s ORDER BY q.revision,q.key''', (session_id,)).fetchall()
    review_records = db.execute('''SELECT a.id,a.disposition,a.text,e.action->>'question' AS question,
        a.review_id,a.step FROM agent_review_answers a
        JOIN agent_reviews r ON r.id=a.review_id
        JOIN agent_review_events e ON e.review_id=a.review_id AND e.step=a.step
        WHERE r.session_id=%s ORDER BY a.created_at,a.id''', (session_id,)).fetchall()
    records += [{'id': r['id'], 'key': f'review_{r["review_id"].hex}_{r["step"]}',
                 'question': {'text': r['question']}, 'disposition': r['disposition'], 'text': r['text']}
                for r in review_records]
    return [{**r, 'id': str(r['id'])} for r in records]


def pending(db, session_id):
    return db.execute('''SELECT q.* FROM agent_questions q
        LEFT JOIN agent_answers a ON a.question_id=q.id
        WHERE q.session_id=%s AND a.id IS NULL ORDER BY q.revision,q.key''', (session_id,)).fetchall()


def save_revision(db, session_id, revision, proposal, inspected):
    with db.transaction():
        db.execute('''INSERT INTO agent_revisions(session_id,revision,proposal,inspected_table_ids)
            VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                   (session_id, revision, Jsonb(proposal), Jsonb(inspected)))
        for question in proposal['questions']:
            db.execute('''INSERT INTO agent_questions(id,session_id,revision,key,question)
                VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                       (uuid5(UUID(str(session_id)), question['key']), session_id, revision,
                        question['key'], Jsonb(question)))


def model_call(db, session_id, model, context, correction, retry_uncertain, *, phase='planning', scope='', max_calls=20):
    version = {'planning': PROMPT_VERSION, 'research': RESEARCH_PROMPT_VERSION,
               'analyst_review': REVIEW_PROMPT_VERSION, 'reviewer': REVIEW_PROMPT_VERSION}[phase]
    identity = {'context': context, 'correction': correction, 'prompt': version}
    if phase != 'planning':
        identity.update(phase=phase, scope=scope)
    key = fingerprint(identity)
    prior = db.execute('''SELECT * FROM agent_calls WHERE session_id=%s AND call_key=%s
        ORDER BY created_at DESC''', (session_id, key)).fetchall()
    for row in prior:
        if row['status'] == 'completed':
            return row['output']
    if any(r['status'] == 'running' for r in prior):
        if not retry_uncertain:
            raise ValueError('Interrupted model request may have been processed. Resume with --retry-model to retry it.')
        db.execute("UPDATE agent_calls SET status='interrupted',finished_at=now() WHERE session_id=%s AND call_key=%s AND status='running'",
                   (session_id, key))
    count = db.execute('SELECT count(*) AS n FROM agent_calls WHERE session_id=%s AND phase=%s AND scope=%s',
                       (session_id, phase, scope)).fetchone()['n']
    if count >= max_calls:
        raise ValueError(f'Session model-call budget exhausted ({max_calls}). Inspect the saved state before starting another session.')
    call_id = uuid4()
    db.execute('''INSERT INTO agent_calls(id,session_id,call_key,status,prompt_version,phase,scope)
        VALUES (%s,%s,%s,'running',%s,%s,%s)''', (call_id, session_id, key, version, phase, scope))
    try:
        method = {'planning': 'generate', 'research': 'generate_research',
                  'analyst_review': 'generate_analyst_review', 'reviewer': 'generate_reviewer'}[phase]
        output, usage = getattr(model, method)(context, correction)
        db.execute("UPDATE agent_calls SET status='completed',output=%s,usage=%s,finished_at=now() WHERE id=%s",
                   (Jsonb(output), Jsonb(usage), call_id))
        return output
    except ModelRequestUncertain as error:
        db.execute('UPDATE agent_calls SET issue=%s WHERE id=%s', (type(error).__name__, call_id))
        raise
    except Exception as error:
        db.execute("UPDATE agent_calls SET status='failed',issue=%s,finished_at=now() WHERE id=%s",
                   (type(error).__name__, call_id))
        raise
