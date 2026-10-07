"""Business-scoped recovery export; raw and session observations precede render."""
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from ..database import connect
from ..storage import Storage
from ..reports import verification
from ..web.report_projection import project, render
from . import admission, control, costs, numbers, questions, store


def jsonable(value):
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (UUID, datetime)):
        return str(value)
    return value


def folder(config, business_id, run_id):
    return Storage(config.storage).path(business_id, f'{business_id}/engine/{run_id}')


def snapshot(config, business_id, run_id):
    with connect(config) as db, db.transaction():
        row = control._run(db, business_id, run_id)
        issues = db.execute("SELECT payload FROM engine_events WHERE run_id=%s AND kind='controller_issue' ORDER BY id", (run_id,)).fetchall()
    calls = admission.inspect_run(config, business_id, run_id)
    received = store.read_document(config, business_id, run_id)
    known = [r['usage'] for r in calls['model_calls'] if r['usage'] is not None]
    result = {'contract_version': 1, 'engine_run_id': str(run_id), 'status': row['status'],
              'question': questions.read(config, business_id, run_id),
              'document_id': received['document_id'] if received else None,
              'revision_id': received['revision_id'] if received else None,
              'usage': {k: sum(u[k] for u in known) for k in ('input', 'cached', 'output')},
              'issues': [r['payload']['code'] for r in issues],
              'diagnostics': [{k: r['payload'][k] for k in ('code', 'stage', 'exception_type', 'reason', 'message', 'http_status')
                               if k in r['payload']} for r in issues if 'exception_type' in r['payload']]}
    if row['abort_reason']:
        result['issues'].append(row['abort_reason'])
    result['usage'].update(calls=row['calls'], seconds=float(row['elapsed']),
                          incomplete=len(known) != len(calls['model_calls']),
                          charged_input=row['charged_input'], charged_output=row['charged_output'],
                          cost_catalog=costs.aggregate(calls['model_calls']))
    return jsonable(result)


def export_run(config, business_id, engine_run_id, dest):
    """Return final read snapshot, retaining available content on render failures.

    Active snapshots truthfully retain running/pausing status. Public run/resume
    return after a terminal or waiting transition; export itself never runs or
    resumes a model. There is no fictitious zero cost when usage is missing.
    """
    business_id, engine_run_id = UUID(str(business_id)), UUID(str(engine_run_id))
    result = snapshot(config, business_id, engine_run_id)  # Authorize before touching dest.
    target = Path(dest); target.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Prevent a failed rerender from leaving an older revision looking current.
    for name in ('draft.raw', 'draft.verified.json', 'verification.json', 'informe.html', 'informe.contenido.html'):
        (target / name).unlink(missing_ok=True)
    def write(name, value, raw=False):
        store._write_atomic(target / name, value if raw else admission.canonical(jsonable(value)))
    write('run.json', result)
    received = store.read_document(config, business_id, engine_run_id)
    if received:
        write('draft.raw', received['raw'], raw=True)
    state = control.read_state(config, business_id, engine_run_id)
    write('session-export.json', state)
    calls = admission.inspect_run(config, business_id, engine_run_id)['model_calls']
    write('proxy-calls.jsonl', b''.join(admission.canonical(jsonable(c)) + b'\n' for c in calls), raw=True)
    observations = folder(config, business_id, engine_run_id) / 'session-observations.json'
    if observations.exists():
        try:
            write('session-export.json', {'durable_root': state, 'observed_sessions': json.loads(observations.read_text())})
        except (ValueError, OSError):
            result['issues'].append('session_export_partial')
    raw = received['raw'] if received else None
    if raw is None:
        latest = {}
        for version in state['message_versions']:
            latest[version['message_id']] = version['content']
        texts = [p['text'] for m in latest.values() if m['info']['role'] == 'assistant'
                 for p in m['parts'] if p.get('type') == 'text' and isinstance(p.get('text'), str)]
        if texts:
            raw = '\n\n'.join(texts).encode()
            write('draft.raw', raw, raw=True)
            result['issues'].append('draft_recovered_from_message_text')
    if raw is not None:
        try:
            with connect(config) as db:
                job = control._run(db, business_id, engine_run_id)
            cache = {}
            def resolve(ref):
                selected = {k: ref[k] for k in ('key', 'execution_id', 'metric')}
                numbers._references([selected])
                return numbers._check(config, job, selected, cache)
            doc, ledger = verification.build(raw, resolver=resolve)
            write('draft.verified.json', doc)
            write('verification.json', ledger)
            result['issues'].extend(ledger['issues'])
            projection = project(doc)
            write('informe.html', render(projection).encode(), raw=True)
            write('informe.contenido.html', render(projection, marks=False).encode(), raw=True)
        except Exception:
            # Never include exceptions carrying raw text, credentials or paths.
            result['issues'].append('report_export_incomplete')
    else:
        result['issues'].append('no_generated_report_content')
    result['issues'] = list(dict.fromkeys(result['issues']))
    write('run.json', result)
    return result
