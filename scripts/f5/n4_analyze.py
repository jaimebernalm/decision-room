"""Apply the frozen N4 rule (docs/validation/2026-10-11-n4-preregistration.md): blocks-v1 vs html-v1.

Usage: python scripts/f5/n4_analyze.py KEY_PATH RESULTS_DIR OUT_JSON [SEEDED_JSON]

Reads the unblinding key (kits.py), the sealed evaluator outputs (audit-, group-, judge-,
owner-, advisor-*.json), each attempt's result.json and run files (checks-full.json,
informe-bloques.json for blocks), each trial's ledger read-only, and optionally the seeded
checker validation. Each condition is True, False or None (not accredited). Written before
any N4 result was seen.
"""
import json
import statistics
import sys
from pathlib import Path

from analyze import ledger_scopes, load, load_engine_runs, mean

BUSINESSES = ('herbolario', 'clinica')
ARMS = ('v1', 'blocks')  # v1 = html-v1 (opencode), blocks = blocks-v1
P4_USD = 1.0


def priority_texts(projection):
    """Priority block id -> (canonical text, ids of the priority and its descendants)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from decision_room.engine import blocks
    out = {}
    for b in blocks.walk(projection['blocks']):
        if b['type'] == 'priority':
            out[b['id']] = ('\n'.join(blocks.block_lines(b)), {x['id'] for x in blocks.walk([b])})
    return out


def overlap(a, b):
    return bool(a and b and (a in b or b in a))


def warned(cita, priorities, items):
    """Conservative cross-match: unique quote in one priority + overlapping final discrepancy there."""
    if not cita:
        return False
    hits = [(pid, ids) for pid, (text, ids) in priorities.items() if text.count(cita) == 1]
    if len(hits) != 1 or sum(text.count(cita) for text, _ in priorities.values()) != 1:
        return False
    _, ids = hits[0]
    return any(i.get('status') == 'discrepancy' and not i.get('coverage') and i.get('block_id') in ids
               and overlap(i.get('quote'), cita) for i in items)


def addressed(cita, priorities, items):
    """Checker items (any status, no coverage summaries) overlapping this quote in its unique priority."""
    if not cita:
        return []
    hits = [ids for text, ids in priorities.values() if text.count(cita) == 1]
    if len(hits) != 1:
        return []
    return [i for i in items if not i.get('coverage') and i.get('block_id') in hits[0] and overlap(i.get('quote'), cita)]


def costs(key):
    by_code = {a['code']: a for a in key['attempts']}
    for trial in sorted({a['trial'] for a in key['attempts']}):
        trial = Path(trial)
        manifest = load(trial / 'manifest.json')
        scopes = ledger_scopes(manifest['budget_path'])
        engine_runs = load_engine_runs(manifest)
        for job in manifest['jobs']:
            attempt = by_code.get(job['code'])
            if attempt is None or Path(attempt['trial']) != trial:
                continue
            run = trial / 'runs' / job['code']
            attempt['run'] = str(run)
            result = load(run / 'result.json') or {}
            run_id = result.get('engine_run_id') or (engine_runs or {}).get(job['job_id'])
            own = [o for o in (scopes.get('web:' + job['job_id']), scopes.get('engine:' + str(run_id)) if run_id else None) if o]
            known = bool(run_id) or engine_runs is not None
            if attempt['status'] == 'not_run':
                attempt.update(usd=None, seconds=None)
                continue
            attempt.update(usd=sum(o['usd'] for o in own) if known else None, seconds=result.get('seconds'),
                           unsettled=sum(o['unsettled'] for o in own))


def main(key_path, results, out, seeded_path=None):
    results = Path(results)
    key = load(key_path)
    kit_of = {v['code']: k for k, v in key['reports'].items()}
    costs(key)
    report = dict(businesses={}, conditions={}, attempts=key['attempts'], checker={})
    missing = []
    natural = dict(correct_checked=0, false_alarms=0, critical_priority=0, critical_warned=0)
    for business in BUSINESSES:
        b = dict(arms={})
        for arm in ARMS:
            attempts = [a for a in key['attempts'] if a['business'] == business and a['arm'] == arm]
            ran = [a for a in attempts if a['status'] != 'not_run']
            delivered = [a for a in attempts if a['delivered']]
            groups = [load(results / f"group-{kit_of[a['code']]}.json") for a in delivered]
            audits = [load(results / f"audit-{kit_of[a['code']]}.json") for a in delivered]
            judges = [load(results / f"judge-{kit_of[a['code']]}.json") for a in delivered]
            if delivered and not (all(groups) and all(audits) and all(judges)):
                missing.append(f'evaluations:{business}:{arm}')
            unwarned = warned_critical = 0
            for attempt, audit in zip(delivered, audits):
                if not audit:
                    continue
                criticals = [c for c in audit['claims'] if c.get('veredicto') == 'critico']
                if arm != 'blocks':
                    unwarned += len(criticals)
                    continue
                run = Path(attempt['run'])
                priorities = priority_texts(load(run / 'informe-bloques.json'))
                items = (load(run / 'checks-full.json') or {}).get('items', [])
                for claim in audit['claims']:
                    if claim.get('seccion') != 'prioridad' or not claim.get('calculable'):
                        continue
                    touched = addressed(claim.get('cita'), priorities, items)
                    if claim.get('veredicto') == 'correcta' and touched:
                        natural['correct_checked'] += 1
                        natural['false_alarms'] += any(i['status'] == 'discrepancy' for i in touched)
                    if claim.get('veredicto') == 'critico':
                        natural['critical_priority'] += 1
                for claim in criticals:
                    hit = claim.get('seccion') == 'prioridad' and warned(claim.get('cita'), priorities, items)
                    warned_critical += hit
                    unwarned += not hit
                natural['critical_warned'] += warned_critical
            b['arms'][arm] = dict(
                planned=len(attempts), started=len(ran), delivered=len(delivered),
                not_run=sum(a['status'] == 'not_run' for a in attempts),
                losses=sum(a['status'] != 'not_run' and not a['delivered'] for a in attempts),
                material_mean=mean([g['material_distintos'] for g in groups if g]) if delivered else None,
                critical_total=sum(g['criticos_distintos'] for g in groups if g),
                critical_unwarned=unwarned, critical_warned=warned_critical,
                signal_mean=mean([sum(j[f'S{i}'] for i in range(1, 6)) for j in judges if j]) if delivered else None,
                decoy_hits=sum(j['S6'] for j in judges if j),
                usd=[a['usd'] for a in ran], minutes=[a['seconds'] / 60 if a.get('seconds') is not None else None for a in ran])
        decisions, incomplete = [], False
        repetitions = sorted({a['repetition'] for a in key['attempts'] if a['business'] == business})
        for i in repetitions:
            name = f'{business}-{i}'
            pair = key['pairs'][name]
            if any(a['status'] == 'not_run' for a in key['attempts'] if a['business'] == business and a['repetition'] == i):
                incomplete = True
                continue
            if not all(pair['kits'].values()) or pair.get('reading'):
                incomplete = True  # a pair unread because of a loss or the image limit
                continue
            for role in ('owner', 'advisor'):
                answer = load(results / f'{role}-{name}.json')
                if not answer or answer.get('eleccion') not in ('A', 'B', 'empate'):
                    incomplete = True
                    continue
                decisions.append(0.5 if answer['eleccion'] == 'empate' else
                                 1.0 if pair['order']['AB'.index(answer['eleccion'])] == 'blocks' else 0.0)
        b['reading'] = dict(decisions=decisions, incomplete=incomplete)
        report['businesses'][business] = b

    arms = {arm: [report['businesses'][k]['arms'][arm] for k in BUSINESSES] for arm in ARMS}
    cond = {}
    cond['a'] = sum(x['losses'] for x in arms['blocks']) <= sum(x['losses'] for x in arms['v1'])
    b_state = sum(x['critical_unwarned'] for x in arms['blocks']) == 0
    for k in BUSINESSES:
        bl, v1 = report['businesses'][k]['arms']['blocks'], report['businesses'][k]['arms']['v1']
        if bl['material_mean'] is None or v1['material_mean'] is None:
            b_state = None if b_state is not False else False
        elif bl['material_mean'] > v1['material_mean']:
            b_state = False
    cond['b'] = b_state
    readings = [report['businesses'][k]['reading'] for k in BUSINESSES]
    all_decisions = [d for r in readings for d in r['decisions']]
    cond['c'] = None if any(r['incomplete'] for r in readings) or not all_decisions else mean(all_decisions) >= 0.5
    d_state = True
    for k in BUSINESSES:
        bl, v1 = report['businesses'][k]['arms']['blocks'], report['businesses'][k]['arms']['v1']
        if bl['signal_mean'] is None or v1['signal_mean'] is None:
            d_state = None if d_state is not False else False
        elif bl['signal_mean'] < v1['signal_mean'] - 0.5:
            d_state = False
    cond['d'] = d_state
    usd = [u for x in arms['blocks'] for u in x['usd']]
    minutes = {arm: [m for x in arms[arm] for m in x['minutes']] for arm in ARMS}
    if not usd or None in usd or None in minutes['blocks'] or None in minutes['v1'] or not minutes['v1']:
        cond['e'] = None
    else:
        cond['e'] = (max(usd) <= P4_USD and statistics.median(usd) <= 0.30
                     and statistics.median(minutes['blocks']) <= statistics.median(minutes['v1']) + 5)
    seeded = load(seeded_path) if seeded_path else None
    f_parts = []
    f_parts.append(None if not natural['correct_checked'] else natural['false_alarms'] / natural['correct_checked'] <= 0.10)
    f_parts.append(natural['critical_warned'] == natural['critical_priority'])
    if seeded is None or not seeded.get('seeded'):
        f_parts.append(None)
    else:
        total = len(seeded['seeded'])
        detected = sum(bool(s.get('detected')) for s in seeded['seeded'])
        report['checker']['seeded'] = dict(total=total, detected=detected, checked=sum(bool(s.get('checked')) for s in seeded['seeded']))
        f_parts.append(detected / total >= 0.70)
    report['checker']['natural'] = natural
    cond['f'] = False if False in f_parts else None if None in f_parts else True
    report['conditions'] = cond
    started_all = all(a['status'] != 'not_run' for a in key['attempts'])
    if not started_all or any(r['incomplete'] for r in readings) or missing:
        outcome = 'incompleto'
    else:
        outcome = 'pasa' if all(v is True for v in cond.values()) else 'no_pasa'
    report.update(outcome=outcome, missing=missing)
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + '\n')
    print(json.dumps(dict(outcome=outcome, conditions=cond, missing=missing), ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:5])
