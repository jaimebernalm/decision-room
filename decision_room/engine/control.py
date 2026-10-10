"""Trusted, business-scoped session binding, prompt outbox and partial messages.

The agent credential cannot call this control plane. A durable dispatch marker is
committed before network I/O. Uncertain delivery is reconciled by message ID;
absence is not evidence that replay is safe. This module never resends a marked
prompt, and it retains every distinct observed message version after abortion.
"""
from contextlib import contextmanager
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from . import admission
from .client import DeliveryUncertain, ProtocolError, _identifier

MAX_PAGE_BYTES = 32 * 1024 * 1024


def _run(db, business_id, run_id):
    row = db.execute('''SELECT *,clock_timestamp() AS checked_at,
        active_seconds + CASE WHEN active_started_at IS NULL THEN 0
            ELSE EXTRACT(EPOCH FROM clock_timestamp()-active_started_at) END AS elapsed
        FROM engine_runs WHERE business_id=%s AND id=%s FOR UPDATE''',
                     (business_id, run_id)).fetchone()
    if not row:
        raise admission.Denied('Job not found for this business.')
    return row


def _running(row):
    if row['status'] != 'running' or row['credential_revoked']:
        raise admission.Denied('Job is not running.')


@contextmanager
def controller_lock(config, business_id, run_id):
    """One cooperative driver per run; PostgreSQL releases this on process death.

    Individual state mutations also serialize on the run row. This lock does not
    permit replay of an uncertain network operation after a driver dies.
    """
    business_id, run_id = UUID(str(business_id)), UUID(str(run_id))
    key = int.from_bytes(bytes.fromhex(admission.sha(('engine-controller:' + str(run_id)).encode()))[:8], 'big', signed=True)
    with connect(config) as db:
        with db.transaction():
            _run(db, business_id, run_id)
        if not db.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (key,)).fetchone()['acquired']:
            raise admission.Denied('Another controller owns this job.')
        try:
            yield
        finally:
            db.execute('SELECT pg_advisory_unlock(%s)', (key,))


def bind_session(config, business_id, run_id, session_id):
    """Bind once, after the driver creates or recovers the root OpenCode session."""
    _identifier(session_id, 'ses')
    with connect(config) as db, db.transaction():
        run = _run(db, business_id, run_id)
        previous = db.execute('SELECT session_id FROM engine_sessions WHERE run_id=%s', (run_id,)).fetchone()
        if previous:
            if previous['session_id'] != session_id:
                raise ValueError('Job is already bound to another OpenCode session.')
            return session_id
        _running(run)
        db.execute('INSERT INTO engine_sessions(run_id,business_id,session_id) VALUES (%s,%s,%s)',
                   (run_id, business_id, session_id))
        admission._event(db, run_id, 'session_bound', {'session_id': session_id})
    return session_id


def enqueue_prompt(config, business_id, run_id, *, request_key, text):
    """Persist identity and exact text before any submission; only one pending turn."""
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid prompt request key.')
    if not isinstance(text, str) or not text.strip() or len(text.encode()) > 256 * 1024:
        raise ValueError('Prompt must be nonempty and no larger than 256 KiB.')
    fingerprint = admission.sha(admission.canonical(text))
    with connect(config) as db, db.transaction():
        run = _run(db, business_id, run_id)
        return _enqueue_prompt(db, run, request_key=request_key, text=text, fingerprint=fingerprint)


def _enqueue_prompt(db, run, *, request_key, text, fingerprint):
    business_id, run_id = run['business_id'], run['id']
    previous = db.execute('SELECT * FROM engine_prompt_outbox WHERE run_id=%s AND request_key=%s',
                          (run_id, request_key)).fetchone()
    if previous:
        if previous['request_sha256'] != fingerprint or previous['prompt'] != text:
            raise ValueError('Prompt key already used with different content.')
        return previous
    _running(run)
    session = db.execute('SELECT session_id FROM engine_sessions WHERE run_id=%s', (run_id,)).fetchone()
    if not session:
        raise admission.Denied('Bind a session before queuing a prompt.')
    if db.execute("SELECT id FROM engine_prompt_outbox WHERE run_id=%s AND state<>'confirmed'", (run_id,)).fetchone():
        raise admission.Denied('Reconcile the pending prompt before queuing another.')
    row = db.execute('''INSERT INTO engine_prompt_outbox
        (id,business_id,run_id,session_id,request_key,request_sha256,message_id,prompt)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                     (uuid4(), business_id, run_id, session['session_id'], request_key,
                      fingerprint, 'msg_' + uuid4().hex, text)).fetchone()
    admission._event(db, run_id, 'prompt_queued', {'message_id': row['message_id']})
    return row


def _prompt(db, run_id, message_id):
    row = db.execute('SELECT * FROM engine_prompt_outbox WHERE run_id=%s AND message_id=%s',
                     (run_id, message_id)).fetchone()
    if not row:
        raise admission.Denied('Prompt not found for this job.')
    return row


def _validate_message(value, session_id):
    if not isinstance(value, dict) or not isinstance(value.get('info'), dict) or not isinstance(value.get('parts'), list):
        raise ProtocolError('Malformed OpenCode message.')
    info = value['info']
    _identifier(info.get('id'), 'msg')
    if info.get('sessionID') != session_id or info.get('role') not in ('user', 'assistant'):
        raise ProtocolError('Message is outside the bound session.')
    if any(not isinstance(part, dict) or part.get('messageID') != info['id'] or part.get('sessionID') != session_id for part in value['parts']):
        raise ProtocolError('Message parts are outside the bound message.')


def _record(db, business_id, run_id, session_id, value):
    raw = admission.canonical(value)
    if len(raw) > MAX_PAGE_BYTES:
        raise ProtocolError('OpenCode message exceeds the byte limit.')
    db.execute('''INSERT INTO engine_message_versions
        (business_id,run_id,session_id,message_id,content,content_sha256)
        VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
               (business_id, run_id, session_id, value['info']['id'], Jsonb(value), admission.sha(raw)))


def record_messages(config, business_id, run_id, messages):
    """Save each distinct partial version, including after the run was stopped."""
    if not isinstance(messages, list) or len(messages) > 100 or len(admission.canonical(messages)) > MAX_PAGE_BYTES:
        raise ProtocolError('Expected a bounded OpenCode message page.')
    with connect(config) as db, db.transaction():
        _run(db, business_id, run_id)
        session = db.execute('SELECT session_id FROM engine_sessions WHERE run_id=%s', (run_id,)).fetchone()
        if not session:
            raise admission.Denied('No session is bound to this job.')
        for value in messages:
            _validate_message(value, session['session_id'])
            _record(db, business_id, run_id, session['session_id'], value)


def confirm_prompt(config, business_id, run_id, message_id, message):
    """A 204 only acknowledges queueing; confirm the exact persisted user message."""
    with connect(config) as db, db.transaction():
        _run(db, business_id, run_id)
        row = _prompt(db, run_id, message_id)
        _validate_message(message, row['session_id'])
        text_parts = [p.get('text') for p in message['parts'] if p.get('type') == 'text' and not p.get('synthetic')]
        if (message['info']['id'] != message_id or message['info']['role'] != 'user'
                or text_parts != [row['prompt']] or row['state'] == 'queued'):
            raise ProtocolError('Persisted message does not match the dispatched prompt.')
        _record(db, business_id, run_id, row['session_id'], message)
        if row['state'] != 'confirmed':
            db.execute("UPDATE engine_prompt_outbox SET state='confirmed',confirmed_at=clock_timestamp() WHERE id=%s", (row['id'],))
            admission._event(db, run_id, 'prompt_confirmed', {'message_id': message_id})
        from ..web.engine_wait import acknowledge
        acknowledge(db, business_id, run_id)
    return 'confirmed'


def dispatch_prompt(config, business_id, run_id, message_id, client):
    """Submit a queued prompt once; subsequent invocations only read/reconcile.

    Missing messages after an uncertain submission remain dispatching. A future
    supervisor may prove a stopped server never accepted one, but a timeout or a
    404 from a running server is insufficient. Never infer successful generation
    from successful prompt submission.
    """
    with connect(config) as db, db.transaction():
        # A resumed owner turn must still have current context when it leaves
        # the durable queue. Lock memory before the run, as in activation.
        owner_turn = db.execute('SELECT question_id FROM engine_owner_answers WHERE run_id=%s AND message_id=%s',
                                (run_id, message_id)).fetchone()
        if owner_turn:
            from ..memory import service as memory
            memory.lock(db, business_id)
        run = _run(db, business_id, run_id)
        row = _prompt(db, run_id, message_id)
        if row['state'] == 'confirmed':
            return 'confirmed'
        should_send = row['state'] == 'queued'
        if should_send:
            _running(run)
            error = admission._active(db, run)
            if not error and owner_turn:
                from . import questions
                question = questions._question(db, run_id, owner_turn['question_id'])
                if questions.context_reason(db, config, run, question):
                    admission._abort(db, run_id, 'context_revoked')
                    error = 'Owner turn context is no longer current.'
            if not error and run['credential_expires_at'] <= run['checked_at']:
                admission._abort(db, run_id, 'credential_expired')
                error = 'Job credential expired.'
            if not error:
                try:
                    snapshot = admission._snapshot(db, config, run['business_id'], run['analysis_id'],
                                                   [UUID(t['id']) for t in run['snapshot']])
                    if admission.sha(admission.canonical(snapshot)) != run['snapshot_sha256']:
                        raise admission.Denied('Snapshot changed.')
                except (ValueError, OSError):
                    admission._abort(db, run_id, 'snapshot_changed')
                    error = 'Snapshot changed or is unavailable.'
        else:
            error = None
        if should_send and not error:
            db.execute("UPDATE engine_prompt_outbox SET state='dispatching',dispatched_at=clock_timestamp() WHERE id=%s", (row['id'],))
            admission._event(db, run_id, 'prompt_dispatching', {'message_id': message_id})
    if error:
        raise admission.Aborted(error)
    if should_send:
        try:
            client.submit(row['session_id'], message_id=message_id, text=row['prompt'], model=run['model'])
        except Exception:
            # This also covers a malformed/500 reply after server acceptance.
            # Do not retain a transport exception containing prompt or password.
            raise DeliveryUncertain('Prompt delivery is uncertain; reconcile the stored message ID.') from None
    message = client.message(row['session_id'], message_id)
    if message is None:
        return 'dispatching'
    return confirm_prompt(config, business_id, run_id, message_id, message)


def read_state(config, business_id, run_id):
    with connect(config) as db, db.transaction():
        _run(db, business_id, run_id)
        session = db.execute('SELECT session_id FROM engine_sessions WHERE run_id=%s', (run_id,)).fetchone()
        outbox = db.execute('''SELECT message_id,request_key,prompt,state,created_at,dispatched_at,confirmed_at
            FROM engine_prompt_outbox WHERE run_id=%s ORDER BY created_at,id''', (run_id,)).fetchall()
        versions = db.execute('''SELECT id,session_id,message_id,content,content_sha256,observed_at
            FROM engine_message_versions WHERE run_id=%s ORDER BY id''', (run_id,)).fetchall()
    for version in versions:
        if admission.sha(admission.canonical(version['content'])) != version['content_sha256']:
            raise ValueError('Stored message failed its integrity check.')
    return {'session_id': session['session_id'] if session else None, 'outbox': outbox, 'message_versions': versions}
