"""Blind, role-separated evaluation kits for the F5 test batch.

Usage: python scripts/f5/kits.py DATA_DIR KITS_DIR KEY_PATH TRIAL_OUTPUT[:business] ...

Each business's attempts come from exactly one trial output (one init, one ledger).

Reads TRIAL_OUTPUT/manifest.json and runs/<code>/ (result.json, informe.html snapshot,
informe.txt) written by scripts/checks/product_trial.py. Writes:
- KITS_DIR/audit/<CODE>/ report.txt + page-NN.png, and KITS_DIR/audit/data/<business>/*.csv;
- KITS_DIR/judge/<CODE>/report.txt (the oracle goes in the judge prompt, never in a kit);
- KITS_DIR/read/<business>-<i>/{A,B}/ page images + report.txt, A/B order randomised;
- KITS_DIR/SEALED.sha256: hash of every kit file.
- KEY_PATH (outside KITS_DIR): code -> attempt/arm, pair order and loss list. Evaluators never
  receive it.
A report enters the kits only if the attempt delivered and its snapshot exists. Lost attempts
get no code and are counted from result.json/failure.json.
"""
import base64
import hashlib
import json
import random
import re
import shutil
import sys
from pathlib import Path

SEED = 5110
MAX_PAIR_IMAGES = 12  # each read once by one fresh reader session per pair
DATA_URI = re.compile(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"')


def pages(snapshot_html):
    return [base64.b64decode(m) for m in DATA_URI.findall(snapshot_html)]


def write_report(target, run, with_pages=True):
    target.mkdir(parents=True)
    shutil.copyfile(run / 'informe.txt', target / 'report.txt')
    if with_pages:
        for i, data in enumerate(pages((run / 'informe.html').read_text()), 1):
            (target / f'page-{i:02d}.png').write_bytes(data)


def build(data_dir, kits, key_path, *trials):
    data_dir, kits, key_path = Path(data_dir), Path(kits), Path(key_path)
    sources = []
    for item in trials:
        path, _, business = item.partition(':')
        sources.append((Path(path), business or None))
    covered = [b for _, b in sources]
    if len(set(covered)) != len(covered):
        raise SystemExit('Each business must come from exactly one trial output.')
    if kits.exists() or key_path.exists():
        raise SystemExit('Kits or key already exist; refusing to overwrite.')
    if key_path.resolve().is_relative_to(kits.resolve()):
        raise SystemExit('The key must live outside the kits.')
    rnd = random.Random(SEED)
    attempts, manifests = [], {}
    for trial, only in sources:
        manifest = json.loads((trial / 'manifest.json').read_text())
        for job in manifest['jobs']:
            if only and job['business_key'] != only:
                continue
            manifests[job['business_key']] = manifest
            run = trial / 'runs' / job['code']
            result = json.loads((run / 'result.json').read_text()) if (run / 'result.json').exists() else None
            if result is None and not (run / 'failure.json').exists():
                raise SystemExit(f"{job['code']} has no result or failure record; finish or reconcile it before building kits.")
            delivered = bool(result and result.get('delivery') and result.get('snapshot')
                             and (run / 'informe.html').exists() and (run / 'informe.txt').exists())
            if delivered and not pages((run / 'informe.html').read_text()):
                raise SystemExit(f"{job['code']} has a snapshot without page images.")
            attempts.append(dict(code=job['code'], business=job['business_key'], repetition=job['repetition'], trial=str(trial),
                                 arm='v1' if job['arm'] == 'opencode' else 'legacy', delivered=delivered,
                                 status=(result or {}).get('status', 'failure' if (run / 'failure.json').exists() else 'not_run'),
                                 run=str(run)))
    codes = rnd.sample(range(100, 1000), len(attempts))
    key = dict(reports={}, pairs={}, attempts=[{k: a[k] for k in ('code', 'business', 'repetition', 'arm', 'delivered', 'status', 'trial')}
                                              for a in attempts])
    for attempt, number in zip(attempts, codes):
        if not attempt['delivered']:
            continue
        code = f'R{number}'
        attempt['kit'] = code
        run = Path(attempt['run'])
        write_report(kits / 'audit' / code, run)
        write_report(kits / 'judge' / code, run)
        key['reports'][code] = {k: attempt[k] for k in ('code', 'business', 'repetition', 'arm')}
    for business in sorted({a['business'] for a in attempts}):
        data = kits / 'audit' / 'data' / business
        data.mkdir(parents=True)
        inputs = {i['name']: i['sha256'] for job in manifests[business]['jobs'] if job['business_key'] == business for i in job['inputs']}
        for name, expected in sorted(inputs.items()):
            source = data_dir / business / 'datos' / name
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise SystemExit(f'{business}/{name} differs from the CSV the trial ran on.')
            shutil.copyfile(source, data / name)
        for repetition in sorted({a['repetition'] for a in attempts if a['business'] == business}):
            pair = {a['arm']: a for a in attempts if a['business'] == business and a['repetition'] == repetition}
            order = ['v1', 'legacy']
            rnd.shuffle(order)
            name = f'{business}-{repetition}'
            key['pairs'][name] = dict(order=order, kits={arm: pair[arm].get('kit') for arm in order})
            if all(pair[arm].get('kit') for arm in order):
                total = sum(len(pages((Path(pair[arm]['run']) / 'informe.html').read_text())) for arm in order)
                key['pairs'][name]['images'] = total
                if total > MAX_PAIR_IMAGES:
                    # Never truncate: dropped pages would depend on the random A/B position.
                    key['pairs'][name]['reading'] = 'incomplete_over_image_limit'
                    continue
                for slot, arm in zip('AB', order):
                    write_report(kits / 'read' / name / slot, Path(pair[arm]['run']))
    # Business per kit code (not secret; the arm is never written in the kits).
    index = dict(reports={code: value['business'] for code, value in key['reports'].items()},
                 pairs=sorted(name for name, pair in key['pairs'].items() if all(pair['kits'].values()) and 'reading' not in pair),
                 incomplete_pairs=sorted(name for name, pair in key['pairs'].items() if pair.get('reading')))
    (kits / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    digest = []
    for path in sorted(p for p in kits.rglob('*') if p.is_file()):
        digest.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(kits)}')
    (kits / 'SEALED.sha256').write_text('\n'.join(digest) + '\n')
    for path in kits.rglob('*'):
        path.chmod(0o555 if path.is_dir() else 0o444)  # read-only before any evaluator runs
    kits.chmod(0o755)  # evaluators write nowhere inside; the root stays listable
    key['sealed_sha256'] = hashlib.sha256((kits / 'SEALED.sha256').read_bytes()).hexdigest()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=2) + '\n')
    key_path.chmod(0o600)
    print(len(key['reports']), 'reports;', sum(1 for p in key['pairs'].values() if all(p['kits'].values())),
          'complete pairs; sealed', key['sealed_sha256'][:12])


if __name__ == '__main__':
    build(*sys.argv[1:])
