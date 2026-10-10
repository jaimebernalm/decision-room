"""Durable owner questions and answer outbox, without a running HTTP request.

Only request() is an agent tool. Trusted controller code must stop the server,
settle in-flight calls, reconcile messages and retain work files before marking
waiting. Activation follows restoring that runtime; this module does not manage
containers. A valid SQLite receipt alone does not prove runtime quiescence.
"""
import hmac
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from ..storage import Storage
from ..memory import service as memory
from . import admission, checkpoint, control


def _key(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError('Invalid owner interaction request key.')


def _question(db, run_id, question_id):
    row = db.execute('SELECT * FROM engine_owner_questions WHERE run_id=%s AND id=%s',
                     (run_id, question_id)).fetchone()
    if not row:
        raise admission.Denied('Question not found for this job.')
    if admission.sha(admission.canonical(row['body'])) != row['request_sha256']:
        raise ValueError('Stored question failed its integrity check.')
    return row


def _receipt(row):
    return {'question_id': str(row['id']), 'state': row['state'],
            'pending': row['state'] != 'resumed', **row['body']}


def context_reason(db, config, run, question=None):
    """Run dependencies, not a published document: works before any HTML exists.

    Caller holds memory head before the run row. Answers belong to this run only
    and never edit business memory or replace the captured dependency baseline.
    """
    if question and question['expires_at'] and question['expires_at'] <= run['checked_at']:
        return 'owner_question_expired'
    from ..reports.store import reason
    return reason(db, dict(source_run_id=run['id'], business_id=run['business_id'],
                           analysis_id=run['analysis_id'], stale_reason=None), config=config, deep=True)


def check_resume(config, business_id, run_id, question_id):
    """Before restoring: refuse expired/revoked context without running a model."""
    with connect(config) as db, db.transaction():
        memory.lock(db, business_id)
        run = control._run(db, business_id, run_id)
        q = _question(db, run_id, question_id)
        if run['status'] != 'waiting' or run['credential_revoked'] or q['state'] != 'waiting':
            raise admission.Denied('Job is not waiting for this answer.')
        problem = context_reason(db, config, run, q)
        if problem:
            admission._abort(db, run_id, problem)
    if problem:
        raise admission.Aborted('Owner wait expired or its context is no longer current.')


def request(config, run_id, token, *, request_key, text, reason, options=None):
    """Commit the question and close admission before returning its receipt.

    A lost receipt can be fetched by an identical retry even while pausing or
    waiting. No other tool gains that exception, and revoked tokens never do.
    """
    _key(request_key)
    options = [] if options is None else options
    if (not isinstance(text, str) or not text.strip() or len(text.encode()) > 4096
            or not isinstance(reason, str) or not reason.strip() or len(reason.encode()) > 4096
            or not isinstance(options, list) or len(options) > 8
            or any(not isinstance(v, str) or not v.strip() or len(v.encode()) > 512 for v in options)):
        raise ValueError('Invalid or oversized owner question.')
    body = {'text': text, 'reason': reason, 'options': options}
    fingerprint = admission.sha(admission.canonical(body))
    with connect(config) as db, db.transaction():
        with_scope = db.execute('SELECT business_id FROM engine_runs WHERE id=%s', (run_id,)).fetchone()
        if not with_scope:
            raise admission.Denied('Invalid job credential.')
        memory.lock(db, with_scope['business_id'])
        run = admission._locked(db, run_id, token)
        if not run['profile'].get('questions'):
            raise admission.Denied('Owner questions are disabled for this profile.')
        previous = db.execute('SELECT * FROM engine_owner_questions WHERE run_id=%s AND request_key=%s',
                              (run_id, request_key)).fetchone()
        if previous:
            if previous['request_sha256'] != fingerprint or previous['body'] != body:
                raise ValueError('Question key already used with different content.')
            return _receipt(previous)
        if db.execute('SELECT 1 FROM engine_owner_questions WHERE run_id=%s', (run_id,)).fetchone():
            raise admission.Denied('Only one owner question is permitted per run.')
        error = admission._active(db, run)
        if not error and context_reason(db, config, run):
            admission._abort(db, run_id, 'context_revoked')
            error = 'Run context is no longer current.'
        if not error:
            try:
                snapshot = admission._snapshot(db, config, run['business_id'], run['analysis_id'],
                                               [UUID(t['id']) for t in run['snapshot']])
                if admission.sha(admission.canonical(snapshot)) != run['snapshot_sha256']:
                    raise ValueError('Snapshot changed.')
            except (ValueError, OSError):
                admission._abort(db, run_id, 'snapshot_changed')
                error = 'Snapshot changed or is unavailable.'
        if not error:
            row = db.execute('''INSERT INTO engine_owner_questions
                (id,business_id,run_id,request_key,request_sha256,body)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *''',
                             (uuid4(), run['business_id'], run_id, request_key, fingerprint, Jsonb(body))).fetchone()
            # Keep counting active time while the controller stops generation.
            db.execute("UPDATE engine_runs SET status='pausing' WHERE id=%s", (run_id,))
            admission._event(db, run_id, 'owner_question_requested', {'question_id': str(row['id'])})
    if error:
        raise admission.Aborted(error)
    return _receipt(row)


def _checkpoint(config, run, key):
    prefix = f"{run['business_id']}/engine/{run['id']}/checkpoints/"
    if not isinstance(key, str) or not key.startswith(prefix):
        raise ValueError('Checkpoint is outside this job.')
    store = Storage(config.storage)
    path = store.path(run['business_id'], key)
    if not path.is_relative_to(store.path(run['business_id'], prefix)):
        raise ValueError('Checkpoint escapes this job.')
    manifest = checkpoint.inspect(path)
    return admission.sha(admission.canonical(manifest))


def confirm_waiting(config, business_id, run_id, question_id, *, checkpoint_key):
    """Publish the checkpoint receipt after the trusted driver stops the runtime.

    The driver owns quiescence/work-file preservation. This transaction verifies
    SQLite integrity and excludes unsettled model calls and unconfirmed prompts.
    A retry cannot replace the confirmed checkpoint or reset the seven-day clock.
    """
    with connect(config) as db, db.transaction():
        run = control._run(db, business_id, run_id)
        question = _question(db, run_id, question_id)
        digest = _checkpoint(config, run, checkpoint_key)
        if question['state'] != 'pausing':
            if question['checkpoint_key'] != checkpoint_key or question['checkpoint_sha256'] != digest:
                raise ValueError('Question already pinned to another checkpoint.')
            return _receipt(question)
        if run['status'] != 'pausing' or run['credential_revoked']:
            raise admission.Denied('Job is not available to finish pausing.')
        if db.execute("SELECT id FROM engine_model_calls WHERE run_id=%s AND state<>'settled'", (run_id,)).fetchone():
            raise admission.Denied('Reconcile model reservations before waiting.')
        if db.execute("SELECT id FROM engine_prompt_outbox WHERE run_id=%s AND state<>'confirmed'", (run_id,)).fetchone():
            raise admission.Denied('Reconcile prompt delivery before waiting.')
        if run['elapsed'] >= run['limits']['active_seconds']:
            admission._abort(db, run_id, 'active_time_limit')
            error = True
        else:
            error = False
            db.execute('''UPDATE engine_runs SET status='waiting',active_seconds=%s,
                active_started_at=NULL WHERE id=%s''', (run['elapsed'], run_id))
            question = db.execute('''UPDATE engine_owner_questions SET state='waiting',
                checkpoint_key=%s,checkpoint_sha256=%s,waiting_at=clock_timestamp(),
                expires_at=clock_timestamp()+interval '7 days' WHERE id=%s RETURNING *''',
                                  (checkpoint_key, digest, question_id)).fetchone()
            admission._event(db, run_id, 'waiting_for_owner', {'question_id': str(question_id), 'checkpoint_sha256': digest})
    if error:
        raise admission.Aborted('Active time limit reached while pausing.')
    return _receipt(question)


def answer(config, business_id, run_id, *, question_id, disposition, text, request_key):
    """Record an explicit owner answer, including after the waiting deadline.

    Receipt does not restart generation, rotate credentials or reset budgets.
    Unknown/declined are data for the next turn, not fabricated owner answers.
    """
    _key(request_key)
    question_id = UUID(str(question_id))
    if (not isinstance(disposition, str) or disposition not in {'answered', 'unknown', 'declined'}
            or not isinstance(text, str) or len(text.encode()) > 64 * 1024
            or (disposition == 'answered' and not text.strip())):
        raise ValueError('Invalid owner answer.')
    body = {'question_id': str(question_id), 'disposition': disposition, 'text': text}
    fingerprint = admission.sha(admission.canonical(body))
    with connect(config) as db, db.transaction():
        run = control._run(db, business_id, run_id)
        question = _question(db, run_id, question_id)
        previous = db.execute('''SELECT * FROM engine_owner_answers
            WHERE run_id=%s AND (question_id=%s OR request_key=%s)''', (run_id, question_id, request_key)).fetchall()
        if previous:
            if (len(previous) != 1 or previous[0]['request_key'] != request_key
                    or previous[0]['request_sha256'] != fingerprint or previous[0]['body'] != body):
                raise ValueError('Owner answer already received with different content or key.')
            return previous[0]
        if question['state'] != 'waiting' or run['status'] != 'waiting' or run['credential_revoked']:
            raise admission.Denied('Job is not waiting for this answer.')
        row = db.execute('''INSERT INTO engine_owner_answers
            (question_id,run_id,request_key,request_sha256,body) VALUES (%s,%s,%s,%s,%s) RETURNING *''',
                         (question_id, run_id, request_key, fingerprint, Jsonb(body))).fetchone()
        admission._event(db, run_id, 'owner_answer_received', {'question_id': str(question_id), 'disposition': disposition})
    return row


def activate_answer(config, business_id, run_id, question_id, *, new_token):
    """Trusted driver: restored runtime -> rotate token and queue one answer.

    Persist a new private token before this transaction; retry with that same
    token. Old in-flight requests cannot enter the resumed turn. Returns only
    the outbox message ID; dispatch still reconciles exact OpenCode persistence.
    """
    if not isinstance(new_token, str) or not 32 <= len(new_token) <= 256:
        raise ValueError('A new private job credential is required.')
    token_hash = admission.sha(new_token.encode())
    with connect(config) as db, db.transaction():
        memory.lock(db, business_id)
        run = control._run(db, business_id, run_id)
        question = _question(db, run_id, question_id)
        received = db.execute('SELECT * FROM engine_owner_answers WHERE run_id=%s AND question_id=%s',
                              (run_id, question_id)).fetchone()
        if not received:
            raise admission.Denied('No explicit owner answer received.')
        if admission.sha(admission.canonical(received['body'])) != received['request_sha256']:
            raise ValueError('Stored answer failed its integrity check.')
        if received['message_id']:
            if not hmac.compare_digest(received['resumed_credential_sha256'], token_hash):
                raise ValueError('Resume already activated with another credential.')
            return received['message_id']
        if run['status'] != 'waiting' or question['state'] != 'waiting' or run['credential_revoked']:
            raise admission.Denied('Job is not waiting for activation.')
        if hmac.compare_digest(run['credential_sha256'], token_hash):
            raise ValueError('Resume must rotate the previous credential.')
        if _checkpoint(config, run, question['checkpoint_key']) != question['checkpoint_sha256']:
            raise ValueError('Confirmed checkpoint changed.')
        problem = context_reason(db, config, run, question)
        if problem:
            admission._abort(db, run_id, problem)
            error = 'Owner wait expired or its context is no longer current.'
        elif run['active_seconds'] >= run['limits']['active_seconds']:
            admission._abort(db, run_id, 'active_time_limit')
            error = 'Active time limit reached.'
        else:
            error = None
            try:
                snapshot = admission._snapshot(db, config, business_id, run['analysis_id'],
                                               [UUID(t['id']) for t in run['snapshot']])
                if admission.sha(admission.canonical(snapshot)) != run['snapshot_sha256']:
                    raise ValueError('Snapshot changed.')
            except (ValueError, OSError):
                admission._abort(db, run_id, 'snapshot_changed')
                error = 'Snapshot changed or is unavailable.'
        if not error:
            run = db.execute('''UPDATE engine_runs SET status='running',active_started_at=clock_timestamp(),
                credential_sha256=%s,credential_expires_at=clock_timestamp()+interval '7 days'
                WHERE id=%s RETURNING *''', (token_hash, run_id)).fetchone()
            text = 'Owner response (preserve unknown/declined as a limitation):\n' + admission.canonical(received['body']).decode()
            queued = control._enqueue_prompt(db, run, request_key='owner-answer:' + str(question['id']),
                                             text=text, fingerprint=admission.sha(admission.canonical(text)))
            db.execute('UPDATE engine_owner_answers SET message_id=%s,resumed_credential_sha256=%s WHERE question_id=%s',
                       (queued['message_id'], token_hash, question_id))
            db.execute("UPDATE engine_owner_questions SET state='resumed',resumed_at=clock_timestamp() WHERE id=%s", (question_id,))
            admission._event(db, run_id, 'owner_answer_queued', {'question_id': str(question_id), 'message_id': queued['message_id']})
    if error:
        raise admission.Aborted(error)
    return queued['message_id']


def read(config, business_id, run_id):
    """Read the current question; expiry never restarts a job automatically."""
    with connect(config) as db, db.transaction():
        run = control._run(db, business_id, run_id)
        question = db.execute('''SELECT * FROM engine_owner_questions
            WHERE run_id=%s AND state<>'resumed' ORDER BY created_at DESC LIMIT 1''', (run_id,)).fetchone()
        if not question:
            return None
        return {**_receipt(question), 'expires_at': question['expires_at'],
                'expired': bool(question['expires_at'] and question['expires_at'] <= run['checked_at'])}
