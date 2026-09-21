"""Business-scoped Python tool, independent of any agent framework."""
import hashlib
import json
import re
import shutil
import time
import uuid

from psycopg.types.json import Jsonb

from .database import connect
from .docker_backend import CleanupPendingError, DockerBackend, INPUT_ROOT, LIMITS
from .execution_contract import validate_payload
from .service import require_analysis
from .storage import Storage, digest

# One execution at a time in the local MVP, across controller processes.
LOCK = 87120932


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def get_execution(config, business_id, execution_id):
    with connect(config) as db:
        row = db.execute('SELECT * FROM executions WHERE business_id=%s AND id=%s',
                         (business_id, execution_id)).fetchone()
        if row is None:
            raise ValueError('Execution not found for this business.')
        row['artifacts'] = db.execute('SELECT * FROM execution_artifacts WHERE business_id=%s AND execution_id=%s ORDER BY name',
                                      (business_id, execution_id)).fetchall()
        return row


def list_executions(config, business_id, analysis_id):
    with connect(config) as db:
        require_analysis(db, business_id, analysis_id)
        return db.execute('''SELECT id,request_key,status,created_at,finished_at,duration_seconds,issue
            FROM executions WHERE business_id=%s AND analysis_id=%s ORDER BY created_at DESC''',
                          (business_id, analysis_id)).fetchall()


def execute(config, business_id, analysis_id, *, code, tables, definitions=None,
            request_key, timeout=30, backend=None):
    """Run once; completed results are candidates, never analytically approved.

    `tables` maps readable aliases to prepared table UUIDs. Caller authentication
    belongs to the future API; these IDs are scoped here, not access tokens.
    Backend configuration is trusted operator configuration, never agent input.
    """
    business_id, analysis_id = uuid.UUID(str(business_id)), uuid.UUID(str(analysis_id))
    definitions = {} if definitions is None else definitions
    if not isinstance(code, str) or not code.strip() or len(code.encode()) > 128 * 1024:
        raise ValueError('Provide nonempty Python code, at most 128 KiB.')
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError('Execution timeout must be 1–120 seconds.')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Provide a request key of 1–128 characters.')
    if not isinstance(definitions, dict) or len(canonical(definitions)) > 64 * 1024:
        raise ValueError('Definitions must be a JSON object of at most 64 KiB.')
    # Strict round trip: no NaN, custom Python objects or implicit string casting.
    definitions = json.loads(json.dumps(definitions, allow_nan=False))
    if not isinstance(tables, dict) or not 1 <= len(tables) <= 64:
        raise ValueError('Select between 1 and 64 prepared tables.')
    if any(not isinstance(alias, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', alias) for alias in tables):
        raise ValueError('Invalid table alias.')
    storage = Storage(config.storage)
    with connect(config) as db:
        require_analysis(db, business_id, analysis_id)
        inputs = {}
        for alias, table_id in sorted(tables.items()):
            row = db.execute('''SELECT t.*,s.sha256 AS original_sha256,s.original_names
                FROM prepared_tables t JOIN sources s ON s.id=t.source_id
                WHERE t.business_id=%s AND t.analysis_id=%s AND t.id=%s AND s.status='ready' ''',
                             (business_id, analysis_id, uuid.UUID(str(table_id)))).fetchone()
            if not row:
                raise ValueError('Selected table is not ready in this business and analysis.')
            inputs[alias] = {key: (str(row[key]) if key in ('id', 'source_id') else row[key])
                             for key in ('id', 'source_id', 'original_names', 'original_sha256', 'parquet_key',
                                         'parquet_sha256', 'row_count', 'columns', 'lineage_column', 'engine_version')}
        backend = backend or DockerBackend()
        limits = {**LIMITS, 'timeout_seconds': timeout, 'outer_grace_seconds': 10}
        fingerprint = sha(canonical({'code': code, 'inputs': inputs, 'definitions': definitions,
                                     'limits': limits, 'environment': backend.manifest}))
        # Lock before the check/insert pair to prevent races, including same-key callers.
        if not db.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (LOCK,)).fetchone()['acquired']:
            raise ValueError('Local sandbox is busy. Retry with the same request key later.')
        previous = db.execute('''SELECT id,request_sha256 FROM executions
            WHERE business_id=%s AND analysis_id=%s AND request_key=%s''',
                              (business_id, analysis_id, request_key)).fetchone()
        if previous:
            if previous['request_sha256'] != fingerprint:
                raise ValueError('Request key already used for different code, inputs, definitions or runtime.')
            return get_execution(config, business_id, previous['id'])
        execution_id = uuid.uuid4()
        prefix = f'{business_id}/analyses/{analysis_id}/executions/{execution_id}'
        code_key = prefix + '/program.py'
        db.execute('''INSERT INTO executions(id,business_id,analysis_id,request_key,request_sha256,
            code_sha256,code_key,inputs,definitions,limits,environment,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'preparing')''',
                   (execution_id, business_id, analysis_id, request_key, fingerprint, sha(code.encode()), code_key,
                    Jsonb(inputs), Jsonb(definitions), Jsonb(limits), Jsonb(backend.manifest)))
        stage = INPUT_ROOT / str(execution_id)
        started = time.monotonic()
        status, logs, runtime, result, issue, artifacts = 'failed', {}, {}, None, None, []
        interrupted = False
        try:
            code_path = storage.path(business_id, code_key)
            code_path.parent.mkdir(parents=True, mode=0o700)
            code_path.write_text(code)
            code_path.chmod(0o400)
            INPUT_ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
            stage.mkdir(mode=0o755)
            (stage / 'tables').mkdir(mode=0o755)
            stage.chmod(0o755)
            (stage / 'tables').chmod(0o755)
            exposed, size = {}, 0
            for alias, table in inputs.items():
                source = storage.path(business_id, table['parquet_key'])
                destination = stage / 'tables' / (alias + '.parquet')
                # Copy in chunks with an enforced aggregate budget, then verify the
                # copied bytes. The container never gets the durable source path.
                with source.open('rb') as incoming, destination.open('xb') as outgoing:
                    while chunk := incoming.read(1024**2):
                        size += len(chunk)
                        if size > limits['input_bytes']:
                            raise ValueError('Selected input snapshots exceed 512 MiB.')
                        outgoing.write(chunk)
                if digest(destination) != table['parquet_sha256']:
                    raise ValueError('Prepared input failed its SHA-256 integrity check.')
                destination.chmod(0o444)
                exposed[alias] = {key: value for key, value in table.items() if key != 'parquet_key'}
                exposed[alias]['path'] = '/inputs/tables/' + alias + '.parquet'
            request = {'tables': exposed, 'definitions': definitions, 'timeout_seconds': timeout}
            (stage / 'program.py').write_text(code)
            (stage / 'request.json').write_bytes(canonical(request))
            for name in ('program.py', 'request.json'):
                (stage / name).chmod(0o444)
            db.execute("UPDATE executions SET status='running' WHERE id=%s", (execution_id,))
            outcome = backend.run(execution_id, stage, timeout)
            runtime = outcome['runtime']
            status = outcome['forced_status']
            if status:
                issue = 'Container or host resource control stopped the computation.'
                logs = {'transport_stderr': outcome['transport_stderr'][:65536]}
            else:
                try:
                    status, logs, files, result = validate_payload(outcome['payload'], inputs)
                except ValueError as error:
                    status, issue, files = 'invalid_output', str(error), {}
                for name, raw in files.items():
                    key = prefix + '/artifacts/' + name
                    path = storage.path(business_id, key)
                    path.parent.mkdir(mode=0o700, exist_ok=True)
                    with path.open('xb') as output:
                        output.write(raw)
                    path.chmod(0o400)
                    artifacts.append((uuid.uuid4(), business_id, execution_id, name, key, sha(raw), len(raw)))
        except KeyboardInterrupt:
            status, issue, result, interrupted = 'interrupted', 'Controller interrupted.', None, True
        except CleanupPendingError as error:
            status, issue, result = 'running', str(error), None
        except Exception as error:
            status, issue, result = 'failed', f'{type(error).__name__}: {str(error)[:2000]}', None
        finally:
            # Keep durable code/artifacts; ephemeral input copies never survive a normal return.
            shutil.rmtree(stage, ignore_errors=True)
        with db.transaction():
            for artifact in artifacts:
                db.execute('''INSERT INTO execution_artifacts(id,business_id,execution_id,name,storage_key,sha256,byte_count)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)''', artifact)
            db.execute('''UPDATE executions SET status=%s,result=%s,logs=%s,runtime=%s,issue=%s,
                finished_at=CASE WHEN %s='running' THEN NULL ELSE now() END,duration_seconds=%s WHERE id=%s''',
                       (status, Jsonb(result), Jsonb(logs), Jsonb(runtime), issue, status, time.monotonic()-started, execution_id))
        if interrupted:
            raise KeyboardInterrupt()
        return get_execution(config, business_id, execution_id)


def recover_executions(config, business_id, backend=None):
    """Stop and mark abandoned runs. Never rerun code implicitly."""
    recovered = []
    with connect(config) as db:
        if not db.execute('SELECT pg_try_advisory_lock(%s) AS acquired', (LOCK,)).fetchone()['acquired']:
            raise ValueError('An execution controller is active; recovery skipped.')
        rows = db.execute("SELECT id FROM executions WHERE business_id=%s AND status IN ('preparing','running')",
                          (business_id,)).fetchall()
        if not rows:
            return recovered
        backend = backend or DockerBackend()
        for row in rows:
            backend.remove(row['id'])
            shutil.rmtree(INPUT_ROOT / str(row['id']), ignore_errors=True)
            db.execute("""UPDATE executions SET status='interrupted',result=NULL,finished_at=now(),
                issue='Abandoned execution recovered; no automatic retry.' WHERE id=%s""", (row['id'],))
            recovered.append(row['id'])
    return recovered
