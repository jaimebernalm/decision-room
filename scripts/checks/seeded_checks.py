"""Seeded-error validation of the independent checker (N4 annexes), on copies of delivered reports.

STATUS: development tool, NOT validated and never run. Known gaps (Astra's review, 2026-10-11):
seed_document may match the number in another priority or a title (an empty fragment of the quote
matches any string); it must pin the exact priority block, change one unambiguous occurrence there,
verify that only that span changed in the canonical projection, mark quotes from numeric fields as
not seedable, forbid overlapping picks and record missing seeds in the denominator. Fix with
adversarial fixtures before any use; its two format tests accredit nothing.

Usage: python scripts/checks/seeded_checks.py TRIAL_ROOT KEY_PATH RESULTS_DIR LEDGER OUT_JSON [--seed N]

For each delivered blocks-v1 attempt, picks 2 priority figures the blind auditor judged correct
(exact quote found once in one priority), changes one number in each by +-20-60 % (seeded), and
runs ONLY the checker on that modified copy through native_checks.run_standalone: a new
budgeted run with no writer, cycle or publication, routed through its own durable ledger.
Detection = a located discrepancy overlapping the changed number in the same priority.
The original report bytes and checks are never modified. Stops at the first ledger stop.
"""
import json
import os
import random
import re
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts/f5'))

NUMBER = re.compile(r'(?<![\w.,])\d{1,3}(?:\.\d{3})+(?:,\d+)?|(?<![\w.,])\d+,\d+|(?<![\w.,])\d{2,}(?![\w])')
CAP_MICRO_USD = 600_000


def es_value(token):
    return float(token.replace('.', '').replace(',', '.'))


def es_format(value, like):
    decimals = len(like.split(',')[1]) if ',' in like else 0
    text = f'{abs(value):,.{decimals}f}'.translate(str.maketrans({',': '.', '.': ','}))
    if '.' not in like.split(',')[0]:
        text = text.replace('.', '') if decimals == 0 else text.split(',')[0].replace('.', '') + ',' + text.split(',')[1]
    return ('-' if value < 0 else '') + text


def candidates(audit, priorities):
    from n4_analyze import unique_priority
    for claim in audit.get('claims', []):
        if claim.get('seccion') != 'prioridad' or claim.get('veredicto') != 'correcta' or not claim.get('calculable'):
            continue
        cita = claim.get('cita')
        if not unique_priority(cita, priorities):
            continue
        tokens = [m for m in NUMBER.finditer(cita) if not re.fullmatch(r'(19|20)\d\d', m.group())]
        if tokens:
            yield cita, max(tokens, key=lambda m: es_value(m.group()))


def seed_document(raw, cita, token, rnd):
    """Replace the token inside the agent text that holds the quote; returns (new_raw, original, seeded)."""
    document = json.loads(raw)
    original = token.group()
    value = es_value(original)
    change = rnd.uniform(0.2, 0.6) * rnd.choice((-1, 1))
    seeded = es_format(value * (1 + change), original)
    if seeded == original:
        seeded = es_format(value * 1.5, original)
    done = []

    def visit(node):
        if isinstance(node, dict):
            return {k: visit(v) for k, v in node.items()}
        if isinstance(node, list):
            return [visit(v) for v in node]
        if isinstance(node, str) and not done and original in node and (cita in node or node in cita or
                                                                        any(part in node for part in cita.split(original))):
            done.append(True)
            return node.replace(original, seeded, 1)
        return node
    changed = visit(document)
    if not done:
        return None
    return json.dumps(changed, ensure_ascii=False).encode(), original, seeded


def main(trial_root, key_path, results, ledger_path, out, seed=20261012):
    from decision_room.agent import api_budget
    from decision_room.config import Config
    from decision_room.database import connect
    from decision_room.engine import admission, native_checks, profile
    from n4_analyze import priority_texts, overlap
    trial_root, results = Path(trial_root), Path(results)
    manifest = json.loads((trial_root / 'manifest.json').read_text())
    config = Config(**{**manifest['config'], 'storage': Path(manifest['config']['storage'])})
    if not Path(ledger_path).exists():
        api_budget.Ledger.create(ledger_path, cap_micro_usd=CAP_MICRO_USD, scope_cap_micro_usd=CAP_MICRO_USD,
                                 explicit_http_rejections=True, input_tokens=40_000_000, output_tokens=1_000_000,
                                 calls=400, seconds=3600)
    os.environ['DECISION_ROOM_API_BUDGET_PATH'] = str(Path(ledger_path).resolve())
    ledger = api_budget.Ledger(ledger_path)
    key = json.loads(Path(key_path).read_text())
    kit_of = {v['code']: k for k, v in key['reports'].items()}
    rnd = random.Random(seed)
    image = os.environ['DECISION_ROOM_ENGINE_IMAGE_ID']
    report = dict(seed=seed, seeded=[], ledger=str(ledger_path))
    for attempt in sorted((a for a in key['attempts'] if a['arm'] == 'blocks' and a['delivered']), key=lambda a: a['code']):
        if ledger.snapshot()['policy']['stopped']:
            report['stopped'] = True
            break
        job = next(j for j in manifest['jobs'] if j['code'] == attempt['code'])
        run_dir = trial_root / 'runs' / attempt['code']
        audit = json.loads((results / f"audit-{kit_of[attempt['code']]}.json").read_text())
        projection = json.loads((run_dir / 'informe-bloques.json').read_text())
        priorities = priority_texts(projection)
        result = json.loads((run_dir / 'result.json').read_text())
        with connect(config) as db:
            source = db.execute('SELECT * FROM engine_runs WHERE id=%s', (result['engine_run_id'],)).fetchone()
            current = db.execute('''SELECT r.raw FROM report_documents d JOIN engine_document_revisions r
                ON r.business_id=d.business_id AND r.document_id=d.id AND r.id=d.current_revision_id
                WHERE d.source_run_id=%s''', (result['engine_run_id'],)).fetchone()
        raw = bytes(current['raw'])
        picks = []
        for cita, token in candidates(audit, priorities):
            if len(picks) == 2:
                break
            seeded = seed_document(raw if not picks else picks[-1][0], cita, token, rnd)
            if seeded:
                picks.append((seeded[0], cita, seeded[1], seeded[2]))
        if not picks:
            report['seeded'].append(dict(code=attempt['code'], eligible=False))
            continue
        modified = picks[-1][0]
        run, token = admission.create_run(
            config, job['business_id'], source['analysis_id'], table_ids=[t['id'] for t in source['snapshot']],
            owner_context=source['owner_context'], request_key=f"seeded-{attempt['code']}-{seed}", model=source['model'],
            brief=source['brief'],
            engine_config=profile.configuration(model=source['model'], format='blocks', usd_cap_micro=1_000_000, image=image))
        if token is None:
            raise SystemExit(f"{attempt['code']}: seeded run already exists; never resend.")
        checked = native_checks.run_standalone(config, job['business_id'], run, token, modified)
        from decision_room.engine import blocks
        seeded_priorities = priority_texts(blocks.parse(modified))
        items = checked.get('items', [])
        for _, cita, original, value in picks:
            new_cita = cita.replace(original, value, 1)
            ids = next((ids for text, ids in seeded_priorities.values() if new_cita in text), set())
            near = [i for i in items if i.get('located') and not i.get('coverage') and i.get('block_id') in ids
                    and value in (i.get('quote') or '') and overlap(i.get('quote'), new_cita)]
            report['seeded'].append(dict(code=attempt['code'], eligible=True, original=original, seeded=value,
                                         quote=new_cita, state=checked.get('state'), checked=bool(near),
                                         detected=any(i['status'] == 'discrepancy' for i in near), run_id=str(run)))
    report['ledger_snapshot'] = ledger.snapshot()['policy']
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str) + '\n')
    seeded = [s for s in report['seeded'] if s.get('eligible')]
    print(json.dumps(dict(seeded=len(seeded), detected=sum(s['detected'] for s in seeded),
                          checked=sum(s['checked'] for s in seeded), stopped=report.get('stopped', False))))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--seed=')]
    seeds = [int(a.split('=', 1)[1]) for a in sys.argv[1:] if a.startswith('--seed=')]
    main(*args, **({'seed': seeds[0]} if seeds else {}))
