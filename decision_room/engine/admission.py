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
from . import profile


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
    input_tokens: int = 6_000_000
    output_tokens: int = 128_000
    output_per_call: int = 16_000
    calls: int = 60
    active_seconds: int = 1_200

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in asdict(self).values()):
            raise ValueError('Engine limits must be positive integers.')
        if self.output_per_call > self.output_tokens:
            raise ValueError('Per-call output exceeds the job output budget.')


def _snapshot(db, config, business_id, analysis_id, table_ids):
    require_analysis(db, business_id, analysis_id)
    rows = db.execute('''SELECT t.id,t.parquet_key,t.parquet_sha256,s.sha256 AS source_sha256,s.original_names,t.columns
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
             'source_sha256': r['source_sha256'], 'original_names': r['original_names'],
             'columns': r['columns']} for r in rows]


def _frozen(prompt, brief):
    brief = {} if brief is None else brief
    if not isinstance(prompt, str):
        raise ValueError('Invalid frozen prompt.')
    if len(prompt.encode()) > 256 * 1024:
        raise ValueError('Engine prompt exceeds 256 KiB.')
    if not isinstance(brief, dict) or len(canonical(brief)) > 64 * 1024:
        raise ValueError('Invalid brief provenance.')
    return prompt, brief


def create_run(config, business_id, analysis_id, *, table_ids, owner_context, request_key,
               model, limits=None, context=None, engine_config=None, frozen_prompt=None, brief=None, builder=None):
    """Trusted bootstrap. Returns (run_id, token); replay returns (run_id, None).

    ``builder(db)`` may return (prompt, brief provenance). It runs under the memory
    head lock in the same transaction that captures the report dependencies, so the
    brief and the dependency baseline always describe the same revisions.

    Tokens are never stored in cleartext. The controller must retain its private
    credential or explicitly rotate it; idempotent creation does not rotate it.
    """
    business_id, analysis_id = UUID(str(business_id)), UUID(str(analysis_id))
    table_ids = sorted({UUID(str(v)) for v in table_ids})
    limits = limits or Limits()
    context = profile.context_files(context)
    if not isinstance(owner_context, str) or len(owner_context.encode()) > 256 * 1024:
        raise ValueError('Owner context exceeds 256 KiB.')
    if engine_config is not None and not isinstance(engine_config, dict):
        raise ValueError('Unsupported engine configuration.')
    settings = profile.configuration(model=model) if engine_config is None else engine_config
    ceiling = settings.get('usd_ceiling')
    if ceiling is not None and (not isinstance(ceiling, dict) or 'cap_micro_usd' not in ceiling):
        raise ValueError('Unsupported engine ceiling.')
    expected = profile.configuration(model=model, image=settings.get("image_id", ""), questions=settings.get("questions", False),
                                     usd_cap_micro=ceiling['cap_micro_usd'] if ceiling is not None else None, format=settings.get('format', 'html'))
    if settings != expected:
        raise ValueError("Unsupported engine configuration.")
    if builder is not None and (frozen_prompt is not None or brief is not None):
        raise ValueError('Use either a brief builder or a frozen prompt.')
    if builder is None:
        prompt, brief = _frozen(profile.prompt(owner_context, format=settings.get('format', 'html')) if frozen_prompt is None else frozen_prompt, brief)
    if not 1 <= len(table_ids) <= 64 or not isinstance(limits, Limits):
        raise ValueError('Select 1–64 tables and valid limits.')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid engine request key.')
    if not isinstance(owner_context, str) or len(owner_context.encode()) > 256 * 1024:
        raise ValueError('Owner context exceeds 256 KiB.')
    if not isinstance(model, str) or not 1 <= len(model) <= 128:
        raise ValueError('A fixed model is required.')
    with connect(config) as db, db.transaction():
        from ..memory import service as memory
        memory.lock(db, business_id)
        lock = int.from_bytes(hashlib.sha256(canonical([str(business_id), request_key])).digest()[:8], 'big', signed=True)
        db.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
        if builder is not None:
            prompt, brief = _frozen(*builder(db))
        snapshot = _snapshot(db, config, business_id, analysis_id, table_ids)
        fingerprint = sha(canonical([str(analysis_id), snapshot, owner_context, model, asdict(limits), settings, context, prompt, brief]))
        previous = db.execute('SELECT id,request_sha256 FROM engine_runs WHERE business_id=%s AND request_key=%s',
                              (business_id, request_key)).fetchone()
        if previous:
            if previous['request_sha256'] != fingerprint:
                raise ValueError('Engine request key already used with different input.')
            return previous['id'], None
        run_id, token = uuid4(), secrets.token_urlsafe(32)
        from . import provider_budget
        provider_budget.create(config, business_id, run_id, settings, limits)
        db.execute('''INSERT INTO engine_runs
            (id,business_id,analysis_id,request_key,request_sha256,owner_context,model,
             snapshot,snapshot_sha256,limits,credential_sha256,profile,prompt,prompt_sha256,input_context,input_sha256,brief)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                   (run_id, business_id, analysis_id, request_key, fingerprint, owner_context,
                    model, Jsonb(snapshot), sha(canonical(snapshot)), Jsonb(asdict(limits)), sha(token.encode()), Jsonb(settings), prompt, sha(prompt.encode()),
                    Jsonb(context), sha(canonical({"snapshot": snapshot, "context": context})), Jsonb(brief)))
        _event(db, run_id, 'created', {})
        from ..reports.store import capture
        capture(db, business_id, analysis_id, run_id, snapshot)
        return run_id, token


def _event(db, run_id, kind, payload):
    db.execute('INSERT INTO engine_events(run_id,kind,payload) VALUES (%s,%s,%s)',
               (run_id, kind, Jsonb(payload)))


def _locked(db, run_id, token, *, allow_checker=False):
    try:
        run_id = UUID(str(run_id))
    except (ValueError, TypeError, AttributeError):
        raise Denied('Invalid job credential.') from None
    row = db.execute('''SELECT *,clock_timestamp() AS checked_at,
        active_seconds + CASE WHEN active_started_at IS NULL THEN 0
            ELSE EXTRACT(EPOCH FROM clock_timestamp()-active_started_at) END AS elapsed
        FROM engine_runs WHERE id=%s FOR UPDATE''', (run_id,)).fetchone()
    if (not row or not isinstance(token, str) or len(token) > 256
            or row['credential_revoked'] or row['credential_expires_at'] <= row['checked_at']):
        raise Denied('Invalid job credential.')
    if not hmac.compare_digest(row['credential_sha256'], sha(token.encode())):
        delegated = db.execute('''SELECT * FROM engine_native_checks WHERE run_id=%s
            AND credential_sha256=%s AND status='running' AND started_at>clock_timestamp()-interval '300 seconds' ''',
            (run_id,sha(token.encode()))).fetchone() if allow_checker else None
        if not delegated:
            raise Denied('Invalid job credential.')
        row['checker_id'] = delegated['id']
        row['checker_calls'] = delegated['calls']
    return row


def _abort(db, run_id, reason, *, stage='admission', details=None):
    db.execute('''UPDATE engine_runs SET status='aborted',abort_reason=%s,
        active_seconds=active_seconds+CASE WHEN active_started_at IS NULL THEN 0
            ELSE EXTRACT(EPOCH FROM clock_timestamp()-active_started_at) END,
        active_started_at=NULL WHERE id=%s AND status<>'aborted' ''', (reason, run_id))
    _event(db, run_id, 'aborted', {'code': reason, 'reason': reason, 'stage': stage, **(details or {})})


def _active(db, row):
    if row['status'] != 'running':
        raise Denied('Job is not running.')
    if row['elapsed'] >= row['limits']['active_seconds']:
        _abort(db, row['id'], 'active_time_limit', stage='check_active_time')
        return 'Active time limit reached.'
    return None


def check_credential(config, run_id, token, *, allow_checker=False):
    """HTTP precheck only; each operation still enforces its allowed job state."""
    with connect(config) as db, db.transaction():
        _locked(db, run_id, token, allow_checker=allow_checker)


def authenticate(config, run_id, token, *, check_snapshot=True, allow_checker=False):
    """Validate every operation. Never allow a caller-supplied business override."""
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token, allow_checker=allow_checker)
        error = _active(db, row)
        if not error and check_snapshot:
            try:
                current = _snapshot(db, config, row['business_id'], row['analysis_id'],
                                    [UUID(t['id']) for t in row['snapshot']])
                if sha(canonical(current)) != row['snapshot_sha256']:
                    raise Denied('Snapshot changed.')
            except (Denied, ValueError, OSError):
                _abort(db, row['id'], 'snapshot_changed', stage='authenticate_snapshot')
                error = 'Snapshot changed or is unavailable.'
    if error:
        raise Aborted(error)
    return {**{k: row[k] for k in ('id', 'business_id', 'analysis_id', 'snapshot', 'snapshot_sha256', 'model', 'limits', 'profile')},
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


def begin_call(config, run_id, token, request_sha256, *, requested_model=None, requested_tier=None):
    """Persist a counted attempt before token-count preflight; never auto-replay."""
    authenticate(config, run_id, token, allow_checker=True)
    call_id = uuid4()
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token, allow_checker=True)
        error = _active(db, row)
        if not error and row['calls'] >= row['limits']['calls']:
            _abort(db, row['id'], 'call_limit', stage='begin_model_call')
            error = 'Call limit reached.'
        if not error and row.get('checker_id') and row['checker_calls'] >= 20:
            # The checker ceiling ends only this check. Parent admission limits
            # above still abort the whole analysis and are never reopened.
            raise Denied('Checker call limit reached.')
        if not error:
            if row.get('checker_id'):
                db.execute('UPDATE engine_native_checks SET calls=calls+1 WHERE id=%s', (row['checker_id'],))
            db.execute('UPDATE engine_runs SET calls=calls+1 WHERE id=%s', (run_id,))
            db.execute('''INSERT INTO engine_model_calls(id,run_id,request_sha256,state)
                VALUES (%s,%s,%s,'counting')''', (call_id, run_id, request_sha256))
            _event(db, run_id, 'model_call_started', {'call_id': str(call_id), 'requested_model': requested_model, 'requested_tier': requested_tier})
    if error:
        raise Aborted(error)
    return call_id


def reserve(config, run_id, token, call_id, input_tokens, output_tokens):
    """Serial admission includes all concurrent outstanding reservations."""
    if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)) or not output_tokens:
        raise ValueError('Invalid token reservation.')
    authenticate(config, run_id, token, allow_checker=True)
    with connect(config) as db, db.transaction():
        row = _locked(db, run_id, token, allow_checker=True)
        error = _active(db, row)
        call = db.execute('SELECT * FROM engine_model_calls WHERE run_id=%s AND id=%s FOR UPDATE',
                          (run_id, call_id)).fetchone()
        if not call or call['state'] != 'counting':
            raise Denied('Call is not available for admission.')
        limits = row['limits']
        if not error and (row['charged_input'] + input_tokens > limits['input_tokens']
                          or row['charged_output'] + output_tokens > limits['output_tokens']
                          or output_tokens > limits['output_per_call']):
            _abort(db, run_id, 'token_limit', stage='reserve_tokens', details={
                'call_id': str(call_id),
                'limit': ('input' if row['charged_input'] + input_tokens > limits['input_tokens'] else
                          'per_call_output' if output_tokens > limits['output_per_call'] else 'output'),
                'requested_input': input_tokens, 'requested_output': output_tokens,
                'charged_input': row['charged_input'], 'charged_output': row['charged_output']})
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


def settle(config, run_id, call_id, *, usage=None, reason=None, billing=None):
    """Trusted proxy completion, including after expiry/revocation/abort.

    Missing usage is never treated as zero. A retry with identical settlement is
    harmless; a different settlement cannot rewrite the ledger.
    """
    if usage is not None:
        if set(usage) != {'input', 'cached', 'output'} or any(type(v) is not int or v < 0 for v in usage.values()) or usage['cached'] > usage['input']:
            raise ValueError('Invalid provider usage.')
    fingerprint = sha(canonical([usage, reason] if billing is None else [usage, reason, billing]))
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
            _abort(db, run_id, reason, stage='settle_model_call', details={'call_id': str(call_id)})
        _event(db, run_id, 'model_call_finished', {'call_id': str(call_id), 'usage': usage, 'issue': reason, 'billing': billing})
        return reason or row['abort_reason']


def inspect_run(config, business_id, run_id):
    """Trusted export source. Secret hashes and owner text are not usage metadata."""
    with connect(config) as db:
        row = db.execute('''SELECT id,business_id,analysis_id,status,abort_reason,calls,
            charged_input,charged_output,snapshot_sha256,profile FROM engine_runs
            WHERE business_id=%s AND id=%s''', (business_id, run_id)).fetchone()
        if not row:
            raise Denied('Job not found for this business.')
        row['model_calls'] = db.execute('''SELECT id,state,reserved_input,reserved_output,
            usage,issue,count_seconds,started_at,admitted_at,finished_at FROM engine_model_calls
            WHERE run_id=%s ORDER BY started_at,id''', (run_id,)).fetchall()
        from . import costs
        events = db.execute("SELECT kind,payload FROM engine_events WHERE run_id=%s AND kind IN ('model_call_started','model_call_finished','model_call_transport','proxy_issue') ORDER BY id", (run_id,)).fetchall()
        metadata = {}
        for event in events:
            data = event['payload']; call = metadata.setdefault(data['call_id'], {})
            if event['kind'] == 'model_call_started':
                call.update(requested_model=data.get('requested_model'), requested_tier=data.get('requested_tier'))
            elif event['kind'] == 'proxy_issue':
                call['diagnostic'] = data
                call['transport'] = data.get('transport')
            elif event['kind'] == 'model_call_transport':
                call['transport'] = data['transport']
            elif data.get('billing') is not None:
                call.update(data['billing'])
        for call in row['model_calls']:
            metadata_for_call = dict(metadata.get(str(call['id']), {}))
            call['diagnostic'] = metadata_for_call.pop('diagnostic', None)
            call['transport'] = metadata_for_call.pop('transport', None)
            call['billing'] = metadata_for_call or None
            call['cost_catalog'] = costs.estimate(call['billing'])
        from . import provider_budget
        row['provider_budget'] = provider_budget.usage(config, row)
        row.pop('profile')
        return row
