"""Opt-in report controller shared by product and evaluation, outside legacy code."""
import atexit
import json
import os
from pathlib import Path
import secrets
import threading
import time
from uuid import UUID, uuid4

from ..database import connect
from ..docker_backend import DockerBackend
from ..storage import Storage, digest
from . import admission, control, questions, store
from .container import Runtime
from .export import export_run, folder, snapshot
from .server import Server
from .tunnel import JobTunnel

_services = {}
_service_lock = threading.Lock()


def _service(config, backend):
    # One trusted service per product configuration in this host process.
    key = (config.dsn, str(config.storage))
    with _service_lock:
        if key not in _services:
            server = Server(config, api_key=os.environ.get('OPENAI_API_KEY', ''), backend=backend)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            _services[key] = server
            atexit.register(server.server_close)
            atexit.register(server.shutdown)
        return _services[key]


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    store._write_atomic(path, admission.canonical(value))


def _row(config, business, run):
    with connect(config) as db:
        return control._run(db, business, run)


def _issue(config, run, code):
    with connect(config) as db:
        admission._event(db, run, 'controller_issue', {'code': code})


def _finish(config, business, run, status, reason=None):
    with connect(config) as db, db.transaction():
        row = control._run(db, business, run)
        if row['status'] in ('aborted', 'failed', 'delivered'):
            return
        db.execute('''UPDATE engine_runs SET status=%s,abort_reason=%s,credential_revoked=true,
            active_seconds=%s,active_started_at=NULL WHERE id=%s''', (status, reason, row['elapsed'], run))
        admission._event(db, run, 'controller_finished', {'status': status, 'reason': reason})


def _inputs(config, row):
    files, manifest = {}, []
    storage = Storage(config.storage)
    with connect(config) as db:
        for table in row['snapshot']:
            source = db.execute('''SELECT s.original_key,s.sha256,s.original_names,s.byte_count,t.columns
                FROM prepared_tables t JOIN sources s ON s.id=t.source_id
                WHERE t.business_id=%s AND t.id=%s''', (row['business_id'], table['id'])).fetchone()
            path = storage.path(row['business_id'], source['original_key'])
            if path.suffix.lower() != '.csv':
                raise ValueError('This engine runtime currently requires CSV source files.')
            if source['byte_count'] > 128*1024*1024 or digest(path) != table['source_sha256']:
                raise ValueError('CSV snapshot changed or exceeds the per-file bound.')
            name = table['id'] + '.csv'; raw = path.read_bytes()
            if admission.sha(raw) != table['source_sha256']:
                raise ValueError('CSV snapshot changed during copy.')
            files[name] = raw
            if sum(map(len, files.values())) > 128*1024*1024:
                raise ValueError('CSV inputs exceed the runtime bound.')
            manifest.append({**table, 'file': '/inputs/' + name, 'original_names': source['original_names'], 'columns': source['columns']})
    files['manifest.json'] = admission.canonical(manifest)
    return files


def _observe(config, business, run, client, root):
    queue, seen, result = [root], set(), {}
    while queue:
        session = queue.pop(0)
        if session in seen:
            continue
        if len(seen) >= 64:
            raise ValueError('Session export exceeds the session bound.')
        seen.add(session); messages = []; before = None
        for _ in range(64):
            page = client.messages(session, before=before, limit=100)
            if not isinstance(page, list):
                raise ValueError('Invalid message page.')
            messages = page + messages
            if session == root:
                control.record_messages(config, business, run, page)
            if len(page) < 100:
                break
            cursor = page[0]['info']['id']
            if cursor == before:
                raise ValueError('Message pagination did not advance.')
            before = cursor
        else:
            raise ValueError('Session export exceeds the page bound.')
        result[session] = messages
        for child in client.children(session):
            if child.get('parentID') != session:
                raise ValueError('Child session is outside the job tree.')
            queue.append(child['id'])
    _save(folder(config, business, run) / 'session-observations.json', result)
    return result


def _checkpoint(config, business, run, runtime, meta, meta_path):
    ident = str(uuid4())
    key = f'{business}/engine/{run}/checkpoints/{ident}'
    runtime.capture(Storage(config.storage).path(business, key))
    meta['checkpoint_key'] = key
    _save(meta_path, meta)
    return key


def _completed_turn(messages, user_id):
    replies = [m['info'] for m in messages if m['info'].get('role') == 'assistant' and m['info'].get('parentID') == user_id]
    if not replies:
        return False
    last = replies[-1]
    return bool(last.get('error') or (last.get('time', {}).get('completed') and last.get('finish')
                                    and last['finish'] not in ('tool-calls', 'unknown')))


def _drive(config, business, run, *, new_token=None, answer=None):
    with control.controller_lock(config, business, run):
        row = _row(config, business, run)
        if row['status'] in ('delivered', 'aborted', 'failed'):
            # A process may have died between the terminal DB commit and finally.
            meta_path = folder(config, business, run) / 'control.json'
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    if meta['run_id'] != str(run):
                        raise ValueError('Runtime metadata differs.')
                    Runtime(DockerBackend(), **{k: meta[k] for k in ('run_id', 'instance_id', 'image', 'password', 'token', 'model')}).stop()
                except Exception:
                    _issue(config, run, 'runtime_stop_unconfirmed')
            return
        if row['status'] == 'waiting' and answer is None:
            return
        root_folder = folder(config, business, run); meta_path = root_folder / 'control.json'
        runtime = client = tunnel = None
        try:
            backend = DockerBackend()
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
                if meta['run_id'] != str(run):
                    raise ValueError('Runtime metadata is outside this job.')
                # An abandoned proxy request has no safe automatic replay.
                pending = [c for c in admission.inspect_run(config, business, run)['model_calls']
                           if c['state'] in ('counting', 'admitted')]
                for call in pending:
                    admission.settle(config, run, call['id'], reason='controller_recovery_usage_unknown')
                if pending:
                    runtime = Runtime(backend, **{k: meta[k] for k in ('run_id', 'instance_id', 'image', 'password', 'token', 'model')})
                    runtime.stop()
                    _checkpoint(config, business, run, runtime, meta, meta_path)
                    return
            else:
                if new_token is None:
                    # A bootstrap crash can lose the plaintext token. Rotate only
                    # before there has ever been a session or model admission.
                    with connect(config) as db, db.transaction():
                        locked = control._run(db, business, run)
                        if locked['calls'] or db.execute('SELECT 1 FROM engine_sessions WHERE run_id=%s', (run,)).fetchone():
                            raise ValueError('Missing runtime credential after execution began.')
                        new_token = secrets.token_urlsafe(32)
                        db.execute('UPDATE engine_runs SET credential_sha256=%s WHERE id=%s', (admission.sha(new_token.encode()), run))
                meta = {'run_id': str(run), 'instance_id': str(uuid4()), 'image': os.environ.get('DECISION_ROOM_ENGINE_IMAGE_ID', ''),
                        'password': secrets.token_urlsafe(32), 'token': new_token, 'model': row['model'], 'initialized': False}
                _save(meta_path, meta)
            if row['status'] == 'waiting':
                if not isinstance(answer, dict) or set(answer) != {'question_id', 'disposition', 'text', 'request_key'}:
                    raise ValueError('A complete explicit owner answer is required.')
                questions.answer(config, business, run, **answer)
                previous = Runtime(backend, **{k: meta[k] for k in ('run_id', 'instance_id', 'image', 'password', 'token', 'model')})
                previous.stop()
                restored = {**meta, 'instance_id': str(uuid4()), 'password': secrets.token_urlsafe(32),
                            'token': secrets.token_urlsafe(32), 'initialized': True, 'restoring': True}
                _save(meta_path, restored)
                runtime = Runtime(backend, **{k: restored[k] for k in ('run_id', 'instance_id', 'image', 'password', 'token', 'model')})
                runtime.restore(Storage(config.storage).path(business, meta['checkpoint_key']))
                restored['restoring'] = False; _save(meta_path, restored); meta = restored
                questions.activate_answer(config, business, run, answer['question_id'], new_token=meta['token'])
                previous.remove()
            else:
                if meta.get('restoring'):
                    raise ValueError('An incomplete restore requires explicit recovery.')
                runtime = Runtime(backend, **{k: meta[k] for k in ('run_id', 'instance_id', 'image', 'password', 'token', 'model')})
                runtime.create()
                if not meta['initialized']:
                    runtime.install_files('inputs', _inputs(config, row))
                    meta['initialized'] = True; _save(meta_path, meta)
            server = _service(config, backend)
            client = runtime.start()
            tunnel = JobTunnel(backend, runtime.container_id, run, server.origin).start()
            state = control.read_state(config, business, run)
            root = state['session_id']
            if root is None:
                # Stop/restart clears an uncertain, unbound session creation;
                # no prompt is submitted before the binding transaction.
                runtime.stop(); client.close(); tunnel.close()
                client = runtime.start(); tunnel = JobTunnel(backend, runtime.container_id, run, server.origin).start()
                existing = client._request('GET', '/session')
                roots = [s for s in existing if not s.get('parentID')]
                if len(roots) > 1:
                    raise ValueError('Root session identity is ambiguous.')
                session = roots[0] if roots else client.create_session(title='Informe del negocio', model=row['model'])
                root = control.bind_session(config, business, run, session['id'])
            client.require_mcp()
            state = control.read_state(config, business, run)
            if not state['outbox']:
                prompt = (Path(__file__).resolve().parents[2] / 'engine/opencode/prompts/informe.md').read_text()
                control.enqueue_prompt(config, business, run, request_key='initial', text=prompt + '\n\nEncargo del propietario:\n' + row['owner_context'])
            uncertain_since = None
            while True:
                row = _row(config, business, run)
                if row['status'] in ('aborted', 'failed', 'delivered'):
                    break
                if row['elapsed'] >= row['limits']['active_seconds']:
                    _finish(config, business, run, 'aborted', 'active_time_limit'); break
                tunnel.check()
                state = control.read_state(config, business, run)
                pending = [p for p in state['outbox'] if p['state'] != 'confirmed']
                for pending_prompt in pending:
                    control.dispatch_prompt(config, business, run, pending_prompt['message_id'], client)
                observed = _observe(config, business, run, client, root)
                row = _row(config, business, run)
                if row['status'] in ('aborted', 'failed', 'delivered'):
                    break
                if row['status'] == 'pausing':
                    client.abort(root)
                    key = _checkpoint(config, business, run, runtime, meta, meta_path)
                    q = questions.read(config, business, run)
                    questions.confirm_waiting(config, business, run, q['question_id'], checkpoint_key=key)
                    break
                state = control.read_state(config, business, run)
                pending = [p for p in state['outbox'] if p['state'] != 'confirmed']
                if pending:
                    uncertain_since = uncertain_since or time.monotonic()
                    if time.monotonic() - uncertain_since > 30:
                        _finish(config, business, run, 'aborted', 'prompt_delivery_unresolved'); break
                else:
                    uncertain_since = None
                    statuses = client.statuses()
                    busy = any(statuses.get(session, {}).get('type', 'idle') != 'idle' for session in observed)
                    messages = observed[root]
                    latest_user = state['outbox'][-1]['message_id']
                    finished = _completed_turn(messages, latest_user)
                    if not busy and finished:
                        receipt = store.read_document(config, business, run)
                        status = 'delivered' if receipt and receipt['raw'].strip() else 'failed'
                        _finish(config, business, run, status, None if status == 'delivered' else 'no_delivered_document')
                        break
                time.sleep(0.1)
            if _row(config, business, run)['status'] != 'waiting':
                _observe(config, business, run, client, root)
                _checkpoint(config, business, run, runtime, meta, meta_path)
        except Exception:
            _issue(config, run, 'controller_failure')
            _finish(config, business, run, 'failed', 'controller_failure')
        finally:
            if tunnel:
                tunnel.close()
            if client:
                client.close()
            if runtime:
                try:
                    runtime.stop()
                except Exception:
                    _issue(config, run, 'runtime_stop_unconfirmed')


def run_report(config, business_id, analysis_id, *, owner_context, request_key, limits=None):
    business, analysis = UUID(str(business_id)), UUID(str(analysis_id))
    with connect(config) as db:
        rows = db.execute('SELECT id FROM prepared_tables WHERE business_id=%s AND analysis_id=%s ORDER BY id', (business, analysis)).fetchall()
    budget = admission.Limits(**limits) if isinstance(limits, dict) else limits
    run, token = admission.create_run(config, business, analysis, table_ids=[r['id'] for r in rows],
                                     owner_context=owner_context, request_key=request_key,
                                     model=os.environ.get('DECISION_ROOM_ENGINE_MODEL', 'gpt-6-luna'), limits=budget)
    _drive(config, business, run, new_token=token)
    return export_run(config, business, run, folder(config, business, run) / 'export')


def resume_report(config, business_id, engine_run_id, *, answer=None):
    business, run = UUID(str(business_id)), UUID(str(engine_run_id))
    _row(config, business, run)
    if answer is not None:
        if not isinstance(answer, dict) or set(answer) != {'question_id', 'disposition', 'text', 'request_key'}:
            raise ValueError('A complete explicit owner answer is required.')
        questions.answer(config, business, run, **answer)
    _drive(config, business, run, answer=answer)
    return export_run(config, business, run, folder(config, business, run) / 'export')
