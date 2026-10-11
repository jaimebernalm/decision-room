"""Cumulative record of every F5 attempt across trials (F5, F5b, F5c), identified by (trial, code).

Usage: python scripts/f5/cumulative.py OUT_JSON TRIAL_OUTPUT ...

Reads each trial's manifest, run records and its own ledger(s), read-only. Publishes status,
delivery, duration and ledger cost bound per attempt; never merges repeated codes and never
reports an unknown cost as zero. No evaluation content.
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def main(out, *trials):
    rows, seen = [], set()
    for trial in (Path(t).resolve() for t in trials):
        manifest_bytes = (trial / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_bytes)
        identity = hashlib.sha256(manifest_bytes).hexdigest()[:16]
        ledger = sqlite3.connect(Path(manifest['budget_path']).resolve().as_uri() + '?mode=ro', uri=True)
        scopes = {}
        for scope, charged, state in ledger.execute('SELECT scope, charged, state FROM calls'):
            entry = scopes.setdefault(scope, dict(usd=0.0, calls=0, unsettled=0))
            entry['usd'] += charged / 1e9; entry['calls'] += 1; entry['unsettled'] += state not in ('settled', 'rejected')
        stopped = bool(ledger.execute('SELECT stopped FROM policy').fetchone()[0])
        for job in manifest['jobs']:
            run = trial / 'runs' / job['code']
            result = json.loads((run / 'result.json').read_text()) if (run / 'result.json').exists() else None
            state = (result or {}).get('status') or ('failure' if (run / 'failure.json').exists() else
                                                    'not_started' if not (run / 'started.json').exists() else 'unrecorded')
            own = [scopes.get('web:' + job['job_id'])]
            if result and result.get('engine_run_id'):
                own.append(scopes.get('engine:' + str(result['engine_run_id'])))
            known = result is not None or state == 'not_started'
            if (identity, job['code']) in seen:
                raise SystemExit(f'Duplicate attempt {trial}:{job["code"]}.')
            seen.add((identity, job['code']))
            rows.append(dict(trial=str(trial), manifest=identity, code=job['code'], arm=job['arm'], status=state,
                             delivered=bool(result and result.get('delivery') and result.get('snapshot')),
                             seconds=(result or {}).get('seconds'), resumed=bool((result or {}).get('resumed')),
                             usd_bound=sum(o['usd'] for o in own if o) if known else None,
                             unsettled=sum(o['unsettled'] for o in own if o) if known else None,
                             ledger_stopped=stopped))
    Path(out).write_text(json.dumps(rows, indent=2) + '\n')
    for r in rows:
        if r['status'] != 'not_started':
            print(Path(r['trial']).name, r['code'], r['status'], r['delivered'], r['seconds'] and round(r['seconds']), r['usd_bound'] and round(r['usd_bound'], 4))


if __name__ == '__main__':
    main(*sys.argv[1:])
