"""Read-only M5 rule, frozen before any M5 outcome; never resend or repair data.

Usage: python scripts/f5/m5_analyze.py KEY RESULTS OUT
The structural kit/result verifier is a separate prerequisite. This checks the
20-attempt coverage, evaluator schemas, final checker cross-match and ceilings.
Amounts are integer nano-USD. Terminal uncertain reservations are known bounds,
not known usage; a pending reservation or unavailable source is never zero.
"""
import copy
import json
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts/checks'))
from decision_room.agent import api_budget
import product_trial_verify as verify
from analyze import load_engine_runs
from n4_analyze import addressed, priority_texts

BUSINESSES = ('herbolario', 'clinica')
ARMS = ('v1', 'blocks')
ROLES = ('owner', 'advisor')
REPETITIONS = 5
BATCH_NANO = 5_000_000_000
RUN_NANO = 1_000_000_000
TERMINAL = {'completed', 'failed', 'failure', 'blocked', 'aborted', 'interrupted', 'waiting'}


def read(path):
    return verify.load(Path(path))


def optional(path):
    try:
        return read(path)
    except (OSError, ValueError, TypeError):
        return None


def average(values):
    return sum(values) / len(values) if values and None not in values else None


def all_known(parts):
    # A missing prerequisite stays unknown even if another business fails.
    return None if None in parts else all(parts)


def shape(key):
    expected = {(b, i, a) for b in BUSINESSES for i in range(1, REPETITIONS + 1) for a in ARMS}
    attempts = key['attempts']
    if any(type(a['repetition']) is not int for a in attempts):
        raise ValueError('Repetitions must be integers.')
    identities = [(a['business'], a['repetition'], a['arm']) for a in attempts]
    if len(identities) != len(expected) or set(identities) != expected or len({a['code'] for a in attempts}) != len(attempts):
        raise ValueError('M5 requires 20 unique attempts, 5 repetitions per business and arm.')
    for business in BUSINESSES:
        if len({str(Path(a['trial']).resolve()) for a in attempts if a['business'] == business}) != 1:
            raise ValueError('Each business must come from one trial init.')
    if set(key['pairs']) != {f'{b}-{i}' for b in BUSINESSES for i in range(1, REPETITIONS + 1)}:
        raise ValueError('M5 requires the ten fixed reader pairs.')
    by_code = {a['code']: a for a in attempts}
    seen = set()
    for kit, info in key['reports'].items():
        a = by_code.get(info['code'])
        if not a or a['code'] in seen or not a['delivered'] or any(info[k] != a[k] for k in ('business', 'repetition', 'arm')):
            raise ValueError('Report key does not identify a unique delivered attempt.')
        seen.add(a['code'])
    if any(type(a['delivered']) is not bool or a['status'] == 'not_run' and a['delivered'] for a in attempts):
        raise ValueError('Invalid attempt delivery/status.')


def ledger(path, version, cap, scope_cap):
    """Only SQLite read-only queries; do not instantiate Ledger (it adds columns)."""
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        policy = dict(db.execute('SELECT * FROM policy').fetchone())
        rows = [dict(r) for r in db.execute('SELECT scope, state, reserved, charged FROM calls')]
    scopes = {}
    for row in rows:
        if (any(type(row[k]) is not int or row[k] < 0 for k in ('reserved', 'charged'))
                or row['charged'] > row['reserved']):
            raise ValueError('Invalid ledger amount.')
        entry = scopes.setdefault(row['scope'], dict(nano=0, calls=0, pending=0, known_usage_nano=0,
                                                     uncertain_nano=0, rejected_nano=0, uncertain_calls=0))
        state = row['state']
        if state not in ('settled', 'rejected', 'uncertain', 'reserved'):
            raise ValueError('Unknown ledger call state.')
        if state in ('rejected', 'uncertain', 'reserved') and row['charged'] != row['reserved']:
            raise ValueError('A reservation was not retained in full.')
        entry['nano'] += row['charged']; entry['calls'] += 1
        entry['pending'] += state == 'reserved'
        entry['uncertain_calls'] += state == 'uncertain'
        field = {'settled': 'known_usage_nano', 'uncertain': 'uncertain_nano', 'rejected': 'rejected_nano'}.get(state)
        if field:
            entry[field] += row['charged']
    amount = sum(r['charged'] for r in rows)
    limits = (policy['version'] == version and policy['cap'] == cap and policy['scope_cap'] == scope_cap
              and amount <= cap and all(s['nano'] <= scope_cap for s in scopes.values()))
    return dict(policy=policy, charged_nano=amount, pending=sum(s['pending'] for s in scopes.values()),
                limits=limits, scopes=scopes)


def account(key, missing):
    batch = []
    jobs_seen, scopes_seen, ledgers_seen = set(), set(), set()
    for trial_name in sorted({a['trial'] for a in key['attempts']}):
        trial = Path(trial_name)
        own_attempts = [a for a in key['attempts'] if Path(a['trial']).resolve() == trial.resolve()]
        manifest = optional(trial / 'manifest.json')
        if not manifest:
            missing.append('manifest:' + trial.name)
            continue
        jobs = {j['code']: j for j in manifest['jobs']}
        if len(jobs) != len(manifest['jobs']):
            raise ValueError('Duplicate manifest job code.')
        try:
            source = str(Path(manifest['budget_path']).resolve())
            if source not in ledgers_seen:
                data = ledger(source, api_budget.SCOPED_REJECTION_VERSION, BATCH_NANO, RUN_NANO)
                batch.append(dict(path=source, **{k: v for k, v in data.items() if k != 'scopes'}))
                ledgers_seen.add(source)
            else:
                data = ledger(source, api_budget.SCOPED_REJECTION_VERSION, BATCH_NANO, RUN_NANO)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            data = None
            missing.append('ledger:' + trial.name)
        # Only crashes need a live read-only DB lookup; never replace a recorded run id.
        database = None
        if any(not (optional(trial / 'runs' / a['code'] / 'result.json') or {}).get('engine_run_id')
               for a in own_attempts if a['status'] != 'not_run'):
            database = load_engine_runs(manifest)
        for a in own_attempts:
            run = trial / 'runs' / a['code']; a['run'] = str(run)
            a.update(nano=None, usd=None, calls=None, pending=None, seconds=None, p4_limits=None,
                     uncertain_nano=None, known_usage_nano=None, rejected_nano=None)
            job = jobs.get(a['code'])
            if not job or (job['business_key'], job['repetition'], {'opencode': 'v1', 'blocks': 'blocks'}.get(job['arm'])) != (a['business'], a['repetition'], a['arm']):
                raise ValueError('Manifest and attempt identity differ.')
            job_identity = (str(trial.resolve()), str(job['job_id']))
            if job_identity in jobs_seen:
                raise ValueError('A job belongs to multiple attempts.')
            jobs_seen.add(job_identity)
            result = optional(run / 'result.json') or {}
            failure = optional(run / 'failure.json') or {}
            a['cause'] = result.get('budget_issue') or result.get('issue') or failure.get('issue') or failure.get('error') or a['status']
            started = (run / 'started.json').is_file()
            if started != (a['status'] != 'not_run') or a['status'] == 'not_run' and (result or failure):
                missing.append('attempt_record:' + a['code'])
            if a['status'] == 'not_run':
                a['engine_source'] = 'not_run'
                if data and data['scopes'].get('web:' + str(job['job_id'])):
                    missing.append('not_run_has_send:' + a['code'])
                continue
            if a['status'] not in TERMINAL:
                missing.append('nonterminal:' + a['code'])
            seconds = result.get('seconds')
            if type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0:
                a['seconds'] = seconds
            run_id = result.get('engine_run_id') or (database or {}).get(str(job['job_id']))
            a['engine_source'] = 'result' if result.get('engine_run_id') else 'database' if run_id else 'unknown'
            identifiers = ['web:' + str(job['job_id'])] + (['engine:' + str(run_id)] if run_id else [])
            if data:
                entries = [data['scopes'][s] for s in identifiers if s in data['scopes']]
                a['nano_lower_bound'] = sum(s['nano'] for s in entries)
                for s in identifiers:
                    pair = (str(Path(manifest['budget_path']).resolve()), s)
                    if pair in scopes_seen:
                        raise ValueError('A ledger scope belongs to multiple attempts.')
                    scopes_seen.add(pair)
                if run_id:
                    for field in ('nano', 'calls', 'pending', 'known_usage_nano', 'uncertain_nano', 'rejected_nano', 'uncertain_calls'):
                        a[field] = sum(s[field] for s in entries)
                    a['usd'] = a['nano'] / 1e9
            if run_id:
                try:
                    path = Path(manifest['config']['storage']) / str(job['business_id']) / 'provider-budgets' / (str(run_id) + '.sqlite')
                    p4 = ledger(path, api_budget.VERSION, RUN_NANO, RUN_NANO)
                    a['p4_limits'] = p4['limits']
                    # P4 verifies the same sends; it is never added a second time to cost.
                    a['p4_charged_nano'] = p4['charged_nano']
                    if p4['pending']:
                        a['pending'] = (a['pending'] or 0) + p4['pending']
                except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
                    missing.append('p4_source:' + a['code'])
            if a['nano'] is None:
                missing.append('cost_source:' + a['code'])
    # Unattributed sends cannot disappear from the reported budget/means.
    for trial_name in {a['trial'] for a in key['attempts']}:
        manifest = optional(Path(trial_name) / 'manifest.json')
        if not manifest:
            continue
        try:
            path = str(Path(manifest['budget_path']).resolve())
            data = ledger(path, api_budget.SCOPED_REJECTION_VERSION, BATCH_NANO, RUN_NANO)
            if any((path, s) not in scopes_seen for s in data['scopes']):
                missing.append('unattributed_scope:' + Path(trial_name).name)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
            pass  # already reported above
    # A separate 5 USD ledger per business would enlarge the preregistered cap.
    if len(ledgers_seen) != 1:
        missing.append('one_shared_ledger_required')
    return batch


def evaluation(results, role, kit, function, missing):
    try:
        value = read(Path(results) / f'{role}-{kit}.json')
        function(value)
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        missing.append(f'{role}:{kit}:{type(error).__name__}')
        return None


def checker(a, audit, missing):
    counts = dict(correct_checked=0, false_alarms=0, correct_unexamined=0, errors_examined=0,
                  errors_detected=0, errors_unexamined=0, critical_warned=0, critical_unwarned=0)
    projection = optional(Path(a['run']) / 'informe-bloques.json')
    checks = optional(Path(a['run']) / 'checks-full.json')
    if not projection or not checks or checks.get('state') != 'complete' or not isinstance(checks.get('items'), list):
        missing.append('checker:' + a['code'])
        return None
    try:
        priorities = priority_texts(projection)
        items = checks['items']
        for claim in audit['claims']:
            priority_numeric = claim['seccion'] == 'prioridad' and claim['calculable']
            touched = [i for i in addressed(claim.get('cita'), priorities, items) if i.get('status') in ('confirmed', 'discrepancy')] if priority_numeric else []
            disputed = any(i['status'] == 'discrepancy' for i in touched)
            if claim['veredicto'] == 'critico':
                counts['critical_warned' if disputed else 'critical_unwarned'] += 1
            if not priority_numeric:
                continue
            if claim['veredicto'] == 'correcta':
                counts['correct_checked' if touched else 'correct_unexamined'] += 1
                counts['false_alarms'] += disputed
            elif claim['veredicto'] in ('menor', 'material', 'critico'):
                counts['errors_examined' if touched else 'errors_unexamined'] += 1
                counts['errors_detected'] += disputed
    except (KeyError, TypeError, AttributeError, ValueError):
        missing.append('checker_projection:' + a['code'])
        return None
    return counts


def reading(key, results, missing):
    rows = []
    for business in BUSINESSES:
        for repetition in range(1, REPETITIONS + 1):
            name = f'{business}-{repetition}'; pair = key['pairs'][name]
            arms = {a['arm']: a for a in key['attempts'] if a['business'] == business and a['repetition'] == repetition}
            for role in ROLES:
                row = dict(pair=name, role=role, points=None, source='unaccredited')
                if any(a['status'] == 'not_run' or a['status'] not in TERMINAL for a in arms.values()):
                    missing.append('reading_attempt:' + name)
                elif not all(a['delivered'] for a in arms.values()):
                    row.update(source='delivery', points=1 if arms['blocks']['delivered'] else 0 if arms['v1']['delivered'] else 0.5)
                elif pair.get('reading') or type(pair.get('images')) is not int or not 1 <= pair['images'] <= 16 or sorted(pair.get('order', [])) != sorted(ARMS) or any(not pair['kits'].get(arm) for arm in ARMS):
                    missing.append('reading_material:' + name)
                else:
                    # Do not accept a pair referring to a different report/arm.
                    valid = all(key['reports'].get(pair['kits'][arm], {}).get('code') == arms[arm]['code'] for arm in ARMS)
                    if not valid:
                        missing.append('reading_identity:' + name)
                    else:
                        value = evaluation(results, role, name, lambda v: verify.reader(v, name), missing)
                        if value:
                            pick = value['eleccion']
                            row.update(source='reader', choice=pick, points=0.5 if pick == 'empate' else int(pair['order']['AB'.index(pick)] == 'blocks'))
                rows.append(row)
    return dict(positions=rows, denominator=20, points=sum(r['points'] for r in rows) if all(r['points'] is not None for r in rows) else None,
                known_points=sum(r['points'] for r in rows if r['points'] is not None),
                reader_positions=sum(r['source'] == 'reader' for r in rows), delivery_positions=sum(r['source'] == 'delivery' for r in rows))


def analyze(key, results):
    key = copy.deepcopy(key); shape(key)
    for a in key['attempts']:
        a.update(nano=None, usd=None, calls=None, pending=None, seconds=None, p4_limits=None,
                 uncertain_nano=None, known_usage_nano=None, rejected_nano=None, cause=a['status'],
                 run=str(Path(a['trial']) / 'runs' / a['code']))
    missing = []; batches = account(key, missing)
    kits = {v['code']: k for k, v in key['reports'].items()}
    report = dict(attempts=key['attempts'], businesses={}, ledger=batches)
    for business in BUSINESSES:
        b = dict(arms={})
        for arm in ARMS:
            attempts = [a for a in key['attempts'] if a['business'] == business and a['arm'] == arm]
            ran = [a for a in attempts if a['status'] != 'not_run']
            delivered = [a for a in attempts if a['delivered']]
            audits, groups, judges, checks = [], [], [], []
            for a in delivered:
                kit = kits.get(a['code'])
                if not kit:
                    missing.append('report_material:' + a['code'])
                    audits.append(None); groups.append(None); judges.append(None); checks.append(None)
                    continue
                audit = evaluation(results, 'audit', kit, lambda v: verify.audit(v, kit), missing)
                group = evaluation(results, 'group', kit, lambda v: verify.group(v, kit, audit['claims']), missing) if audit else None
                judge = evaluation(results, 'judge', kit, lambda v: verify.judge(v, kit), missing)
                audits.append(audit); groups.append(group); judges.append(judge)
                if arm == 'blocks':
                    checks.append(checker(a, audit, missing) if audit else None)
            complete_audit = bool(delivered) and all(audits) and all(groups)
            complete_judge = bool(delivered) and all(judges)
            complete_cost = bool(ran) and all(a['nano'] is not None and a['pending'] == 0 and a['p4_limits'] is not None for a in ran)
            natural = None
            if arm == 'blocks' and delivered and all(checks):
                natural = {k: sum(c[k] for c in checks) for k in checks[0]}
            b['arms'][arm] = dict(planned=5, started=len(ran), delivered=len(delivered), losses=len(ran)-len(delivered),
                not_run=5-len(ran), losses_by_cause=dict(Counter(str(a['cause']) for a in ran if not a['delivered'])),
                material_total=sum(g['material_distintos'] for g in groups) if complete_audit else None,
                material_mean=average([g['material_distintos'] for g in groups]) if complete_audit else None,
                critical_total=sum(g['criticos_distintos'] for g in groups) if complete_audit else None,
                audit_n=len(delivered) if complete_audit else 0,
                signal_mean=average([sum(j[f'S{i}'] for i in range(1, 6)) for j in judges]) if complete_judge else None,
                judge_n=len(delivered) if complete_judge else 0,
                decoy_hits=sum(j['S6'] for j in judges) if complete_judge else None,
                cost_n=len(ran), nano_total=sum(a['nano'] for a in ran) if complete_cost else None,
                usd_mean=average([a['usd'] for a in ran]) if complete_cost else None,
                known_usage_nano=sum(a['known_usage_nano'] for a in ran) if complete_cost else None,
                uncertain_nano=sum(a['uncertain_nano'] for a in ran) if complete_cost else None,
                rejected_nano=sum(a['rejected_nano'] for a in ran) if complete_cost else None,
                usd_per_delivery=sum(a['usd'] for a in ran)/len(delivered) if complete_cost and delivered else None,
                seconds_mean=average([a['seconds'] for a in ran]), duration_n=sum(a['seconds'] is not None for a in ran), checker=natural)
        report['businesses'][business] = b
    cond = {}
    arms = {arm: [report['businesses'][b]['arms'][arm] for b in BUSINESSES] for arm in ARMS}
    cond['a'] = None if any(a['status'] == 'not_run' or a['status'] not in TERMINAL for a in key['attempts']) else sum(a['losses'] for a in arms['blocks']) <= sum(a['losses'] for a in arms['v1']) + 1
    cond['b'] = all_known([None if x['material_mean'] is None or y['material_mean'] is None else x['critical_total'] == 0 and x['material_mean'] <= y['material_mean'] for x, y in zip(arms['blocks'], arms['v1'])])
    readers = reading(key, results, missing); report['reading'] = readers
    cond['c'] = None if readers['points'] is None else readers['points'] >= 10
    cond['d'] = all_known([None if x['signal_mean'] is None or y['signal_mean'] is None else x['signal_mean'] >= y['signal_mean'] - 0.5 for x, y in zip(arms['blocks'], arms['v1'])])
    comparisons = [None if x['nano_total'] is None or y['nano_total'] is None else x['nano_total']*y['cost_n'] <= 2*y['nano_total']*x['cost_n'] for x, y in zip(arms['blocks'], arms['v1'])]
    limits = [a['p4_limits'] for a in key['attempts'] if a['status'] != 'not_run'] + [b['limits'] for b in batches]
    cond['e'] = all_known(comparisons + limits) if batches else None
    cond['f'] = all_known([None if x['checker'] is None or not x['checker']['correct_checked'] else x['checker']['false_alarms'] == 0 for x in arms['blocks']])
    missing = sorted(set(missing))
    if missing or any(v is None for v in cond.values()):
        outcome = 'incompleto'
    elif not all(cond.values()):
        outcome = 'no_pasa'
    else:
        outcome = 'mejor' if readers['points'] >= 12 else 'no_peor'
    report.update(conditions=cond, outcome=outcome, missing=missing)
    return report


def main(key_path, results, out):
    if Path(out).resolve() == Path(key_path).resolve() or Path(out).resolve().is_relative_to(Path(results).resolve()):
        raise ValueError('Analysis output must not overwrite the key or evaluations.')
    report = analyze(read(key_path), results)
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: report[k] for k in ('outcome', 'conditions', 'missing')}, ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:])
