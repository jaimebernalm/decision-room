"""Apply the frozen F5 decision rule (docs/validation/2026-10-11-f5-preregistration.md).

Usage: python scripts/f5/analyze.py TRIAL_OUTPUT KEY_PATH RESULTS_DIR OUT_JSON

Reads the unblinding key (kits.py), the sealed evaluator outputs (RESULTS_DIR/audit-, group-,
judge-, owner-, advisor-*.json), result.json of every attempt and the trial ledger. Prints
and writes every condition per business. Written before any result was seen.
"""
import json
import sqlite3
import statistics
import sys
from pathlib import Path

BUSINESSES = ('herbolario', 'clinica')


def load(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def mean(values):
    return sum(values) / len(values) if values else None


def load_engine_runs(manifest):
    """Read-only job -> engine run map (for attempts that crashed before result.json), or None."""
    try:
        import psycopg
        with psycopg.connect(manifest['config']['dsn']) as db:
            return {str(job): str(run) for job, run in db.execute(
                'SELECT id, engine_run_id FROM web_jobs WHERE engine_run_id IS NOT NULL').fetchall()}
    except Exception:  # noqa: BLE001 - an unknown source leaves (e) unaccredited
        return None


def extra_v1_losses_allowed(_):
    return 1  # (a): v1 loses at most 1 of its 12 attempts


def main(trial, key_path, results, out):
    trial, results = Path(trial), Path(results)
    key = load(key_path)
    manifest = load(trial / 'manifest.json')
    by_code = {a['code']: a for a in key['attempts']}
    kit_of = {v['code']: k for k, v in key['reports'].items()}
    report = dict(businesses={}, conditions={}, attempts=key['attempts'])

    # Cost bound per attempt from the trial ledger: the job's web scope plus its engine scope.
    ledger = sqlite3.connect(Path(manifest['budget_path']).resolve().as_uri() + '?mode=ro', uri=True)
    scopes = {}
    for scope, charged, state in ledger.execute('SELECT scope, charged, state FROM calls'):
        entry = scopes.setdefault(scope, dict(usd=0.0, calls=0, unsettled=0))
        entry['usd'] += charged / 1e9
        entry['calls'] += 1
        entry['unsettled'] += state not in ('settled', 'rejected')  # rejected is terminal, fully charged
    engine_runs = load_engine_runs(manifest)
    for job in manifest['jobs']:
        result = load(trial / 'runs' / job['code'] / 'result.json') or {}
        own = [scopes.get('web:' + job['job_id'])]
        run_id = result.get('engine_run_id') or (engine_runs or {}).get(job['job_id'])
        if run_id:
            own.append(scopes.get('engine:' + str(run_id)))
        by_code[job['code']]['engine_source'] = ('result' if result.get('engine_run_id') else
                                                  'database' if run_id else 'unknown' if engine_runs is None else 'none')
        own = [o for o in own if o]
        by_code[job['code']].update(
            usd=sum(o['usd'] for o in own), calls=sum(o['calls'] for o in own),
            unsettled=sum(o['unsettled'] for o in own), seconds=result.get('seconds'),
            owner_answers=result.get('owner_answers'))

    ok = {}
    for business in BUSINESSES:
        b = dict(arms={})
        for arm in ('v1', 'legacy'):
            attempts = [a for a in key['attempts'] if a['business'] == business and a['arm'] == arm]
            delivered = [a for a in attempts if a['delivered']]
            groups = [load(results / f"group-{kit_of[a['code']]}.json") for a in delivered]
            audits = [load(results / f"audit-{kit_of[a['code']]}.json") for a in delivered]
            judges = [load(results / f"judge-{kit_of[a['code']]}.json") for a in delivered]
            complete = all(groups) and all(audits) and all(judges)
            den = dict(prioridad_calculables=0, prioridad_correctas=0, resto_calculables=0, resto_correctas=0)
            for audit in filter(None, audits):
                for claim in audit['claims']:
                    if claim.get('calculable'):
                        section = 'prioridad' if claim['seccion'] == 'prioridad' else 'resto'
                        den[section + '_calculables'] += 1
                        den[section + '_correctas'] += claim['veredicto'] == 'correcta'
            b['arms'][arm] = dict(
                attempts=len(attempts), delivered=len(delivered), losses=len(attempts) - len(delivered),
                evaluations_complete=complete,
                material_mean=mean([g['material_distintos'] for g in groups if g]),
                critical_total=sum(g['criticos_distintos'] for g in groups if g),
                denominators=den,
                signal_mean=mean([sum(j[f'S{i}'] for i in range(1, 6)) for j in judges if j]),
                decoy_hits=sum(j['S6'] for j in judges if j),
                usd_mean=mean([a['usd'] for a in attempts]), usd_max=max((a['usd'] for a in attempts), default=None),
                unsettled=sum(a['unsettled'] for a in attempts),
                minutes_median=statistics.median([a['seconds'] / 60 for a in attempts if a['seconds'] is not None])
                if any(a['seconds'] is not None for a in attempts) else None)
        # Reading: 1 v1, 0.5 explicit tie, 0 legacy; loss rules; incomplete if any reading missing.
        reading = {}
        for role in ('owner', 'advisor'):
            scores, incomplete = [], False
            for i in range(1, 7):
                name = f'{business}-{i}'
                pair = key['pairs'][name]
                kits = pair['kits']
                if not kits['v1'] and not kits['legacy']:
                    scores.append(0.5)
                elif not kits['legacy']:
                    scores.append(1.0)
                elif not kits['v1']:
                    scores.append(0.0)
                elif pair.get('reading'):
                    incomplete = True
                else:
                    answer = load(results / f'{role}-{name}.json')
                    if not answer or answer.get('eleccion') not in ('A', 'B', 'empate'):
                        incomplete = True
                        continue
                    if answer['eleccion'] == 'empate':
                        scores.append(0.5)
                    else:
                        arm = pair['order']['AB'.index(answer['eleccion'])]
                        scores.append(1.0 if arm == 'v1' else 0.0)
            reading[role] = dict(scores=scores, mean=None if incomplete else mean(scores), incomplete=incomplete)
        b['reading'] = reading
        report['businesses'][business] = b

    v1 = {k: report['businesses'][k]['arms']['v1'] for k in BUSINESSES}
    lg = {k: report['businesses'][k]['arms']['legacy'] for k in BUSINESSES}
    v1_losses, lg_losses = sum(v['losses'] for v in v1.values()), sum(v['losses'] for v in lg.values())
    # Each condition is True (met), False (failed) or None (not accredited). Missing evaluations
    # make the trial incomplete; a comparison without legacy deliveries is not accredited.
    unaccredited, missing = [], []
    cond = {'a': v1_losses <= extra_v1_losses_allowed(v1_losses) and v1_losses <= lg_losses}
    for k in BUSINESSES:
        for arm in (v1[k], lg[k]):
            if arm['delivered'] and not arm['evaluations_complete']:
                missing.append(f'evaluations:{k}')
    b_state = sum(v['critical_total'] for v in v1.values()) == 0
    for k in BUSINESSES:
        if v1[k]['material_mean'] is None or lg[k]['material_mean'] is None:
            unaccredited.append(f'b:{k}'); b_state = None if b_state is not False else False
            continue
        if not (v1[k]['material_mean'] <= 0.5 and v1[k]['material_mean'] - lg[k]['material_mean'] <= 0.25):
            b_state = False
    cond['b'] = b_state
    c_state = True
    for k in BUSINESSES:
        r = report['businesses'][k]['reading']
        if r['owner']['incomplete'] or r['advisor']['incomplete']:
            missing.append(f'reading:{k}')
            c_state = None if c_state is not False else False
            continue
        if not (r['owner']['mean'] > 0.5 and r['advisor']['mean'] >= 0.5):
            c_state = False
    cond['c'] = c_state
    d_state = True
    for k in BUSINESSES:
        if v1[k]['signal_mean'] is None or lg[k]['signal_mean'] is None:
            unaccredited.append(f'd:{k}'); d_state = None if d_state is not False else False
            continue
        if not (v1[k]['signal_mean'] >= lg[k]['signal_mean'] - 1 and v1[k]['decoy_hits'] <= lg[k]['decoy_hits'] + 1):
            d_state = False
    cond['d'] = d_state
    usd = [a['usd'] for a in key['attempts'] if a['arm'] == 'v1']
    seconds = [by_code[a['code']]['seconds'] for a in key['attempts'] if a['arm'] == 'v1']
    sources = [by_code[a['code']]['engine_source'] for a in key['attempts'] if a['arm'] == 'v1']
    if None in seconds or 'unknown' in sources:
        cond['e'] = None  # no zero cost and no partial median: not accredited
        unaccredited.append('e')
    else:
        cond['e'] = (mean(usd) <= 0.50 and max(usd) <= 1.00 and sum(v['unsettled'] for v in v1.values()) == 0
                     and statistics.median(seconds) / 60 <= 15)
    attempted = all(a['status'] in ('completed', 'blocked', 'failed', 'waiting', 'failure') for a in key['attempts'])
    complete = attempted and not missing and not key.get('incomplete_pairs') and not any(
        p.get('reading') for p in key['pairs'].values())
    failed_bcd = [c for c in 'bcd' if cond[c] is False]
    if not complete:
        outcome = 'incompleto'  # never candidato, never decided on a subset
    elif not cond['a'] or len(failed_bcd) >= 2:
        outcome = 'no_candidato'
    elif failed_bcd or cond['e'] is not True or any(cond[c] is None for c in 'bcd'):
        outcome = 'mixto'
    else:
        outcome = 'candidato'
    report['conditions'] = dict(cond, unaccredited=unaccredited, missing=missing, v1_losses=v1_losses,
                                legacy_losses=lg_losses, complete=complete, outcome=outcome)
    Path(out).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n')
    print(json.dumps(report['conditions'], ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:5])
