"""Job credentials and durable model reservations, independent of OpenCode.

Only trusted product code creates jobs. A job token never selects its business,
analysis or snapshot. Unknown provider usage keeps the reservation charged.
"""
import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from ..service import require_analysis
from ..storage import Storage, digest


class Denied(ValueError):
    """Credential, scope or job state does not permit this operation."""


class Aborted(Denied):
    """The job was stopped durably; existing artifacts remain intact."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class Limits:
    input_tokens: int = 3_000_000
    output_tokens: int = 64_000
    output_per_call: int = 8_000
    calls: int = 60
    active_seconds: int = 1_200

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in asdict(self).values()):
            raise ValueError('Engine limits must be positive integers.')
        if self.output_per_call > self.output_tokens:
            raise ValueError('Per-call output exceeds the job output budget.')


def _snapshot(db, config, business_id, analysis_id, table_ids):
    require_analysis(db, business_id, analysis_id)
    rows = db.execute('''SELECT t.id,t.parquet_key,t.parquet_sha256,s.sha256 AS source_sha256
        FROM prepared_tables t JOIN sources s ON s.id=t.source_id
        WHERE t.business_id=%s AND t.analysis_id=%s AND t.id=ANY(%s) AND s.status='ready'
        ORDER BY t.id''', (business_id, analysis_id, table_ids)).fetchall()
    if len(rows) != len(table_ids):
        raise Denied('Snapshot contains unavailable tables.')
    storage = Storage(config.storage)
    for row in rows:
        if digest(storage.path(business_id, row['parquet_key'])) != row['parquet_sha256']:
            raise Denied('Snapshot failed its integrity check.')
    return [{'id': str(r['id']), 'parquet_sha256': r['parquet_sha256'],
             'source_sha256': r['source_sha256']} for r in rows]


def create_run(config, business_id, analysis_id, *, table_ids, owner_context, request_key,
               model, limits=None):
    """Trusted bootstrap. Returns (run_id, token); replay returns (run_id, None).

    Tokens are never stored in cleartext. The controller must retain its private
    credential or explicitly rotate it; idempotent creation does not rotate it.
    """
    business_id, analysis_id = UUID(str(business_id)), UUID(str(analysis_id))
    table_ids = sorted({UUID(str(v)) for v in table_ids})
    limits = limits or Limits()
    if not 1 <= len(table_ids) <= 64 or not isinstance(limits, Limits):
        raise ValueError('Select 1–64 tables and valid limits.')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid engine request key.')
    if not isinstance(owner_context, str) or len(owner_context.encode()) > 256 * 1024:
        raise ValueError('Owner context exceeds 256 KiB.')
    if not isinstance(model, str) or not 1 <= len(model) <= 128:
        raise ValueError('A fixed model is required.')
    with connect(config) as db, db.transaction():
        lock = int.from_bytes(hashlib.sha256(canonical([str(business_id), request_key])).digest()[:8], 'big', signed=True)
        db.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
        snapshot = _snapshot(db, config, business_id, analysis_id, table_ids)
        fingerprint = sha(canonical([str(analysis_id), snapshot, owner_context, model, asdict(limits)]))
        previous = db.execute('SELECT id,request_sha256 FROM engine_runs WHERE business_id=%s AND request_key=%s',
                              (business_id, request_key)).fetchone()
        if previous:
            if previous['request_sha256'] != fingerprint:
                raise ValueError('Engine request key already used with different input.')
            return previous['id'], None
        run_id, token = uuid4(), secrets.token_urlsafe(32)
        db.execute('''INSERT INTO engine_runs
            (id,business_id,analysis_id,request_key,request_sha256,owner_context,model,
             snapshot,snapshot_sha256,limits,credential_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                   (run_id, business_id, analysis_id, request_key, fingerprint, owner_context,
                    model, Jsonb(snapshot), sha(canonical(snapshot)), Jsonb(asdict(limits)), sha(token.encode())))
        _event(db, run_id, 'created', {})
        return run_id, token


def _event(db, run_id, kind, payload):
    db.execute('INSERT INTO engine_events(run_id,kind,payload) VALUES (%s,%s,%s)',
               (run_id, kind, Jsonb(payload)))


def _locked(db, run_id, token):
    try:
        run_id = UUID(str(run_id))
    except (ValueError, TypeError, AttributeError):
        raise Denied('Invalid job credential.') from None
    row = db.execute('''SELECT *,clock_timestamp() AS checked_at,
        active_seconds + CASE WHEN active_started_at IS NULL THEN 0
            ELSE EXTRACT(EPOCH FROM clock_timestamp()-active_started_at) END AS elapsed
        FROM engine_runs WHERE id=%s FOR UPDATE''', (run_id,)).fetchone()
    if (not row or not isinstance(token, str) or len(token) > 256
            or not hmac.compare_digest(row['credential_sha256'], sha(token.encode()))
            or row['credential_revoked'] or row['credential_expires_at'] <= row['checked_at']):
        raise Denied('Invalid job credential.')
    return row


def _abort(db, run_id, reason):
    db.execute('''UPDATE engine_runs SET status='aborted',abort_reason=%s,
        active_seconds=active_seconds+CASE WHEN active_started_at IS NULL THEN 0
            ELSE EXTRACT(EPOCH FROM clock_timestamp()-active_started_at) END,
        active_started_at=NULL WHERE id=%s AND status<>'aborted' ''', (reason, run_id))
    _event(db, run_id, 'aborted', {'reason': reason})


def _active(db, row):
    if row['status'] != 'running':
        raise Denied('Job is not running.')
    if row['elapsed'] >= row['limits']['active_seconds']:
        _abort(db, row['id'], 'active_time_limit')
        return 'Active time limit reached.'
    return None


def authenticate(config, run_id, token, *, check_snapshot=True):
    """Validate every operation. Never allow a caller-supplied business override."""
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token)
        error = _active(db, row)
        if not error and check_snapshot:
            try:
                current = _snapshot(db, config, row['business_id'], row['analysis_id'],
                                    [UUID(t['id']) for t in row['snapshot']])
                if sha(canonical(current)) != row['snapshot_sha256']:
                    raise Denied('Snapshot changed.')
            except (Denied, ValueError, OSError):
                _abort(db, row['id'], 'snapshot_changed')
                error = 'Snapshot changed or is unavailable.'
    if error:
        raise Aborted(error)
    return {**{k: row[k] for k in ('id', 'business_id', 'analysis_id', 'snapshot', 'snapshot_sha256', 'model', 'limits')},
            'remaining_seconds': max(0.001, row['limits']['active_seconds'] - float(row['elapsed']))}


def revoke(config, business_id, run_id):
    """Trusted control plane; no raw token is accepted as business authority."""
    with connect(config) as db, db.transaction():
        row = db.execute('SELECT id FROM engine_runs WHERE business_id=%s AND id=%s FOR UPDATE',
                         (business_id, run_id)).fetchone()
        if not row:
            raise Denied('Job not found for this business.')
        db.execute('UPDATE engine_runs SET credential_revoked=true WHERE id=%s', (run_id,))
        _event(db, run_id, 'credential_revoked', {})


def begin_call(config, run_id, token, request_sha256):
    """Persist a counted attempt before token-count preflight; never auto-replay."""
    authenticate(config, run_id, token)
    call_id = uuid4()
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token)
        error = _active(db, row)
        if not error and row['calls'] >= row['limits']['calls']:
            _abort(db, row['id'], 'call_limit')
            error = 'Call limit reached.'
        if not error:
            db.execute('UPDATE engine_runs SET calls=calls+1 WHERE id=%s', (run_id,))
            db.execute('''INSERT INTO engine_model_calls(id,run_id,request_sha256,state)
                VALUES (%s,%s,%s,'counting')''', (call_id, run_id, request_sha256))
            _event(db, run_id, 'model_call_started', {'call_id': str(call_id)})
    if error:
        raise Aborted(error)
    return call_id


def reserve(config, run_id, token, call_id, input_tokens, output_tokens):
    """Serial admission includes all concurrent outstanding reservations."""
    if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)) or not output_tokens:
        raise ValueError('Invalid token reservation.')
    authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token)
        error = _active(db, row)
        call = db.execute('SELECT * FROM engine_model_calls WHERE run_id=%s AND id=%s FOR UPDATE',
                          (run_id, call_id)).fetchone()
        if not call or call['state'] != 'counting':
            raise Denied('Call is not available for admission.')
        limits = row['limits']
        if not error and (row['charged_input'] + input_tokens > limits['input_tokens']
                          or row['charged_output'] + output_tokens > limits['output_tokens']
                          or output_tokens > limits['output_per_call']):
            _abort(db, run_id, 'token_limit')
            error = 'Token limit reached.'
        if not error:
            db.execute('''UPDATE engine_runs SET charged_input=charged_input+%s,
                charged_output=charged_output+%s WHERE id=%s''', (input_tokens, output_tokens, run_id))
            db.execute('''UPDATE engine_model_calls SET state='admitted',reserved_input=%s,
                reserved_output=%s,admitted_at=clock_timestamp() WHERE id=%s''',
                       (input_tokens, output_tokens, call_id))
            _event(db, run_id, 'model_call_admitted', {'call_id': str(call_id), 'input': input_tokens, 'output': output_tokens})
    if error:
        raise Aborted(error)


def settle(config, run_id, call_id, *, usage=None, reason=None):
    """Trusted proxy completion, including after expiry/revocation/abort.

    Missing usage is never treated as zero. A retry with identical settlement is
    harmless; a different settlement cannot rewrite the ledger.
    """
    if usage is not None:
        if set(usage) != {'input', 'cached', 'output'} or any(type(v) is not int or v < 0 for v in usage.values()) or usage['cached'] > usage['input']:
            raise ValueError('Invalid provider usage.')
    fingerprint = sha(canonical([usage, reason]))
    with connect(config) as db, db.transaction():
        row = db.execute('SELECT * FROM engine_runs WHERE id=%s FOR UPDATE', (run_id,)).fetchone()
        call = db.execute('SELECT * FROM engine_model_calls WHERE run_id=%s AND id=%s FOR UPDATE', (run_id, call_id)).fetchone()
        if not row or not call:
            raise Denied('Unknown job call.')
        if call['settlement_sha256']:
            if call['settlement_sha256'] != fingerprint:
                raise ValueError('Call already settled differently.')
            return call['issue'] or row['abort_reason']
        if usage is not None and call['state'] != 'admitted':
            raise ValueError('Cannot settle usage without an admitted request.')
        if usage is not None:
            db.execute('''UPDATE engine_runs SET charged_input=charged_input+%s,
                charged_output=charged_output+%s WHERE id=%s''',
                       (usage['input'] - call['reserved_input'], usage['output'] - call['reserved_output'], run_id))
            if usage['input'] > call['reserved_input'] or usage['output'] > call['reserved_output']:
                reason = 'provider_usage_exceeded_reservation'
        else:
            reason = reason or 'provider_usage_unknown'
        db.execute('''UPDATE engine_model_calls SET state=%s,usage=%s,issue=%s,
            settlement_sha256=%s,finished_at=clock_timestamp() WHERE id=%s''',
                   ('settled' if usage is not None else 'uncertain', Jsonb(usage), reason, fingerprint, call_id))
        if reason:
            _abort(db, run_id, reason)
        _event(db, run_id, 'model_call_finished', {'call_id': str(call_id), 'usage': usage, 'issue': reason})
        return reason or row['abort_reason']


def inspect_run(config, business_id, run_id):
    """Trusted export source. Secret hashes and owner text are not usage metadata."""
    with connect(config) as db:
        row = db.execute('''SELECT id,business_id,analysis_id,status,abort_reason,calls,
            charged_input,charged_output,snapshot_sha256 FROM engine_runs
            WHERE business_id=%s AND id=%s''', (business_id, run_id)).fetchone()
        if not row:
            raise Denied('Job not found for this business.')
        row['model_calls'] = db.execute('''SELECT id,state,reserved_input,reserved_output,
            usage,issue,count_seconds,started_at,admitted_at,finished_at FROM engine_model_calls
            WHERE run_id=%s ORDER BY started_at,id''', (run_id,)).fetchall()
        return row
