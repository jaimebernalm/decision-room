"""Business-scoped recovery export; raw and session observations precede render."""
from datetime import datetime
import json
from pathlib import Path
from uuid import UUID

from ..database import connect
from ..storage import Storage
from . import admission, control, costs, questions, store


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
        events = db.execute("SELECT kind,payload FROM engine_events WHERE run_id=%s AND kind IN ('controller_issue','proxy_issue','aborted','controller_finished') ORDER BY id", (run_id,)).fetchall()
    issues = [r for r in events if r['kind'] in ('controller_issue', 'proxy_issue')]
    details = []
    for event in events:
        payload = event['payload']
        if event['kind'] in ('controller_issue', 'proxy_issue'):
            if 'exception_type' not in payload:
                continue
        elif event['kind'] == 'controller_finished':
            if payload.get('status') != 'aborted':
                continue
            payload = {'code': payload.get('reason'), 'reason': payload.get('reason'), 'stage': 'controller_finished'}
        else:
            payload = {'code': payload.get('reason'), 'stage': 'unspecified', **payload}
        details.append({k: payload[k] for k in (
            'code', 'stage', 'exception_type', 'reason', 'message', 'http_status', 'call_id',
            'limit', 'requested_input', 'requested_output', 'charged_input', 'charged_output',
            'transport') if k in payload})
    calls = admission.inspect_run(config, business_id, run_id)
    received = store.read_document(config, business_id, run_id)
    known = [r['usage'] for r in calls['model_calls'] if r['usage'] is not None]
    result = {'contract_version': 1, 'profile_config': row['profile'],
              'prompt_sha256': row['prompt_sha256'], 'input_sha256': row['input_sha256'], 'engine_run_id': str(run_id), 'status': row['status'],
              'question': questions.read(config, business_id, run_id),
              'document_id': received['document_id'] if received else None,
              'revision_id': received['revision_id'] if received else None,
              'usage': {k: sum(u[k] for u in known) for k in ('input', 'cached', 'output')},
              'issues': [r['payload']['code'] for r in issues],
              'diagnostics': details}
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
    for name in ('draft.raw', 'informe.raw.html'):
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
    if received:
        write('informe.raw.html', received['raw'], raw=True)
        result.update(raw_sha256=received['raw_sha256'],
                      delivery_via=received['delivery_via'])
    else:
        (target / 'informe.raw.html').unlink(missing_ok=True)
        result['issues'].append('no_generated_report_content')
    result.update(profile='html-v1', presentation='not_evaluated', verification='not_requested')
    write('run.json', result)
    return result
