"""Domain records and private LangGraph checkpoints in the existing PostgreSQL."""
from ..observability.runtime import notify, call_context, transport, reused
from contextlib import contextmanager
from uuid import UUID, uuid4, uuid5

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.types.json import Jsonb

from ..database import connect
from .context import fingerprint, encoded
from .prompts import PROMPT_VERSION
from .model import ModelRequestUncertain, record_transport, record_request
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


def _model_call(db, session_id, model, context, correction, retry_uncertain, *, phase='planning', scope='', max_calls=20, before_call=None):
    from .business_planner import VERSION as BUSINESS_VERSION
    version = {'planning': PROMPT_VERSION, 'research': RESEARCH_PROMPT_VERSION,
               'business_planner': BUSINESS_VERSION, 'analyst_review': REVIEW_PROMPT_VERSION, 'reviewer': REVIEW_PROMPT_VERSION}[phase]
    if phase == 'research' and context.get('budgets', {}).get('research_continuity'):
        from .research_continuity import VERSION
        version = VERSION
    if phase in ('analyst_review', 'reviewer') and context.get('budgets', {}).get('owner_presentation'):
        from .owner_presentation import VERSION
        version = VERSION
    identity = {'context': context, 'correction': correction, 'prompt': version}
    if phase != 'planning':
        identity.update(phase=phase, scope=scope)
    key = fingerprint(identity)
    prior = db.execute('''SELECT * FROM agent_calls WHERE session_id=%s AND call_key=%s
        ORDER BY created_at DESC''', (session_id, key)).fetchall()
    for row in prior:
        if row['status'] == 'completed':
            reused(db,'call',row['id'])
            return row['output']
    if any(r['status'] == 'running' for r in prior):
        if not retry_uncertain:
            raise ValueError('Interrupted model request may have been processed. Resume with --retry-model to retry it.')
        db.execute("UPDATE agent_calls SET status='interrupted',finished_at=now() WHERE session_id=%s AND call_key=%s AND status='running'",
                   (session_id, key))
    count = db.execute('SELECT count(*) AS n FROM agent_calls WHERE session_id=%s AND phase=%s AND scope=%s',
                       (session_id, phase, scope)).fetchone()['n']
    if before_call:
        before_call()
    if count >= max_calls:
        raise ValueError(f'Model-call budget exhausted for phase={phase}, scope={scope!r} ({count}/{max_calls}). This is the phase/scope allowance, not a global execution limit.')
    call_id = uuid4()
    db.execute('''INSERT INTO agent_calls(id,session_id,call_key,status,prompt_version,phase,scope,context_payload)
        VALUES (%s,%s,%s,'running',%s,%s,%s,%s)''', (call_id, session_id, key, version, phase, scope, Jsonb(context)))
    notify(db)
    try:
        method = {'planning': 'generate', 'research': 'generate_research', 'business_planner': 'generate_business_planner',
                  'analyst_review': 'generate_analyst_review', 'reviewer': 'generate_reviewer'}[phase]
        def save_attempts(attempts):
            transport(attempts)
            db.execute('UPDATE agent_calls SET usage=%s WHERE id=%s',
                       (Jsonb({'transport_attempts': attempts,
                               'rejected_attempt_usage_unknown': any(a['status'] != 200 for a in attempts)}), call_id))
        def save_request(request):
            db.execute('UPDATE agent_calls SET effective_request=%s, request_sha256=%s WHERE id=%s',
                       (Jsonb(request), fingerprint(request), call_id))
        with call_context(call_id), record_transport(save_attempts), record_request(save_request):
            output, usage = getattr(model, method)(context, correction)
        recorded=db.execute('SELECT usage FROM agent_calls WHERE id=%s',(call_id,)).fetchone()['usage'] or {}
        usage={**recorded,**usage}
        db.execute("UPDATE agent_calls SET status='completed',output=%s,usage=%s,finished_at=now() WHERE id=%s",
                   (Jsonb(output), Jsonb(usage), call_id))
        notify(db)
        return output
    except ModelRequestUncertain as error:
        db.execute('UPDATE agent_calls SET issue=%s WHERE id=%s', (type(error).__name__, call_id))
        notify(db)
        raise
    except Exception as error:
        attempts = getattr(error, 'transport_attempts', None)
        db.execute("UPDATE agent_calls SET status='failed',issue=%s,usage=COALESCE(%s,usage),finished_at=now() WHERE id=%s",
                   (type(error).__name__, Jsonb({'transport_attempts': attempts, 'rejected_attempt_usage_unknown': True}) if attempts else None, call_id))
        notify(db)
        raise


def model_call(db, session_id, model, context, correction, retry_uncertain, *, config=None,
               phase='planning', scope='', max_calls=20, before_call=None):
    from ..memory import context as memory_context, retrieval
    from ..memory.service import lock
    decision = fingerprint(dict(context=context, correction=correction, phase=phase, scope=scope))
    # Replay from the decision's original context, including exactly the events it saw.
    # Later phase retrievals must not change the key of an already completed decision.
    ordinal = 1
    existing = db.execute("SELECT context_payload FROM agent_calls WHERE session_id=%s AND context_payload->>'decision_key'=%s ORDER BY created_at LIMIT 1",
                          (session_id, decision)).fetchone()
    baseline = existing['context_payload']['business_context'] if existing else None
    while True:
        with db.transaction():
            m = memory_context.manifest(db, session_id)
            if not m:
                raise memory_context.StaleContext('Legacy checkpoint requires agent-replan.')
            lock(db, m['business_id'])
            memory_context.ensure(db, session_id)
            if baseline is None:
                baseline = memory_context.delivered(db, session_id)
            business_context = dict(baseline)
            additions = db.execute("SELECT decision_key,ordinal,request,response FROM context_retrievals WHERE session_id=%s AND decision_key=%s AND ordinal<%s ORDER BY ordinal",
                                   (session_id, decision, ordinal)).fetchall()
            business_context['retrievals'] = baseline['retrievals'] + additions
            payload = {**context, 'business_context': business_context, 'decision_key': decision}
            limit = context.get('budgets', {}).get('max_context_bytes', memory_context.CONTEXT_BYTES)
            if len(encoded(payload).encode()) > limit:
                if phase == 'research':
                    from .research_agenda import ResearchBudgetReached
                    raise ResearchBudgetReached(f'Presupuesto de contexto de investigación alcanzado ({limit // 1000} KB).')
                raise ValueError(f'Model context exceeds {limit // 1000} KB. Narrow the investigation; no material context was silently dropped.')
        output = _model_call(db, session_id, model, payload, correction, retry_uncertain,
                             phase=phase, scope=scope, max_calls=max_calls, before_call=before_call)
        memory_context.ensure(db, session_id)
        # Raw response (including the envelope) remains in agent_calls.output.
        # Dispatch changes shape only; it never repairs an invalid decision.
        if phase == 'research' and context.get('budgets', {}).get('research_continuity') and 'decision' in output:
            if set(output) != {'decision'} or not isinstance(output['decision'], dict):
                return {'invalid_model_output': 'Expected exactly one decision object.'}
            output = output['decision']
        if output.get('action') != 'retrieve':
            if output.get('retrieval') is not None:
                return {'invalid_model_output': 'Only retrieve may contain a retrieval request.'}
            return {k: v for k, v in output.items() if k != 'retrieval'}
        if config is None:
            raise ValueError('Retrieval requires application configuration.')
        if any(output.get(k) for k in ('proposal', 'code', 'table_ids', 'report', 'metric_keys', 'question', 'investigation_key', 'followups', 'assignments', 'synthesis', 'assessment')):
            return {'invalid_model_output': 'retrieve requires empty action fields and a retrieval request.'}
        try:
            retrieval.save(config, db, session_id, decision, ordinal, output.get('retrieval'))
        except memory_context.StaleContext:
            raise
        except ValueError:
            return {'invalid_model_output': 'Invalid or unavailable retrieval. Supply tool/query/id/limit with a discovered UUID for inspect_dataset/open_report/open_evidence. Never open the current draft as a historical report; it is already in context. Respect the remaining retrieval budget.'}
        ordinal += 1
