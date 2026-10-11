"""Blind, role-separated evaluation kits for the F5 test batch.

Usage: python scripts/f5/kits.py [--allow-not-run] [--repetitions=N] [--captures=DIR] [--max-pair-images=N]
       [--balanced] DATA_DIR KITS_DIR KEY_PATH TRIAL_OUTPUT[:business] ...

--captures=DIR (M5): page images come from web view captures made by web_captures.py,
DIR/reader/<attempt code>/ for readers and DIR/auditor/<attempt code>/ (no check notices) for
auditors and judges, instead of the PDF or raster snapshot. --balanced alternates the A/B order
across each business's pairs instead of drawing it at random.

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
import subprocess
import sys
from pathlib import Path

SEED = 5110
MAX_PAIR_IMAGES = 16  # each read once by one fresh reader session per pair
ARM_LABEL = {'opencode': 'v1', 'legacy': 'legacy', 'blocks': 'blocks'}
SWIFT = Path(__file__).with_name('pdf_pages.swift')
DATA_URI = re.compile(r'src="data:image/png;base64,([A-Za-z0-9+/=]+)"')


def pages(snapshot_html):
    return [base64.b64decode(m) for m in DATA_URI.findall(snapshot_html)]


def page_count(run):
    if CAPTURES:
        return len(captured(run, auditor=False))
    if (run / 'informe.pdf').exists():  # native blocks: the platform PDF
        from pypdf import PdfReader
        return len(PdfReader(str(run / 'informe.pdf')).pages)
    return len(pages((run / 'informe.html').read_text()))


CAPTURES = None  # set by --captures


def captured(run, auditor):
    folder = CAPTURES / ('auditor' if auditor else 'reader') / run.name
    images = sorted(folder.glob('page-*.png'))
    if not images:
        raise SystemExit(f'{run.name}: no web capture in {folder}.')
    return images


def write_report(target, run, with_pages=True, auditor=False):
    target.mkdir(parents=True)
    shutil.copyfile(run / 'informe.txt', target / 'report.txt')
    if not with_pages:
        return
    if CAPTURES:
        for image in captured(run, auditor):
            shutil.copyfile(image, target / image.name)
        return
    if (run / 'informe.pdf').exists():
        # Auditors get the copy without check notices, so accuracy stays independent of the checker.
        pdf = run / 'informe-auditor.pdf' if auditor and (run / 'informe-auditor.pdf').exists() else run / 'informe.pdf'
        subprocess.run(['swift', str(SWIFT), str(pdf), str(target), '1.5'], check=True, capture_output=True)
        return
    for i, data in enumerate(pages((run / 'informe.html').read_text()), 1):
        (target / f'page-{i:02d}.png').write_bytes(data)


def build(data_dir, kits, key_path, *trials, allow_not_run=False, repetitions=6, balanced=False, max_pair_images=MAX_PAIR_IMAGES):
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
                if not (allow_not_run and not (run / 'started.json').exists()):
                    raise SystemExit(f"{job['code']} has no result or failure record; finish or reconcile it before building kits.")
                # Never started (the trial stopped before it): recorded as not_run, not as a loss.
                attempts.append(dict(code=job['code'], business=job['business_key'], repetition=job['repetition'], trial=str(trial),
                                     arm=ARM_LABEL[job['arm']], delivered=False, status='not_run', run=str(run)))
                continue
            presented = (run / 'informe.txt') if CAPTURES else (run / 'informe.pdf') if job['arm'] == 'blocks' else (run / 'informe.html')
            delivered = bool(result and result.get('delivery') and result.get('snapshot')
                             and presented.exists() and (run / 'informe.txt').exists())
            if delivered and not page_count(run):
                raise SystemExit(f"{job['code']} has a snapshot without page images.")
            attempts.append(dict(code=job['code'], business=job['business_key'], repetition=job['repetition'], trial=str(trial),
                                 arm=ARM_LABEL[job['arm']], delivered=delivered,
                                 status=(result or {}).get('status', 'failure' if (run / 'failure.json').exists() else 'not_run'),
                                 run=str(run)))
    # Each business from exactly one trial, unique codes, and 6 repetitions per arm and business.
    per_business = {}
    for a in attempts:
        per_business.setdefault(a['business'], set()).add(a['trial'])
    if any(len(trials) != 1 for trials in per_business.values()):
        raise SystemExit('A business appears in more than one trial output.')
    if len({a['code'] for a in attempts}) != len(attempts):
        raise SystemExit('Attempt codes are not unique across the selected trials.')
    arms = sorted({a['arm'] for a in attempts})
    if len(arms) != 2:
        raise SystemExit('Kits compare exactly two arms.')
    for business in per_business:
        expected = list(range(1, repetitions + 1))
        for arm in arms:
            reps = sorted(a['repetition'] for a in attempts if a['business'] == business and a['arm'] == arm)
            if reps != expected:
                raise SystemExit(f'{business}/{arm} does not have exactly repetitions 1-{len(expected)}.')
    codes = rnd.sample(range(100, 1000), len(attempts))
    key = dict(reports={}, pairs={}, attempts=[{k: a[k] for k in ('code', 'business', 'repetition', 'arm', 'delivered', 'status', 'trial')}
                                              for a in attempts])
    for attempt, number in zip(attempts, codes):
        if not attempt['delivered']:
            continue
        code = f'R{number}'
        attempt['kit'] = code
        run = Path(attempt['run'])
        write_report(kits / 'audit' / code, run, auditor=True)
        write_report(kits / 'judge' / code, run, auditor=bool(CAPTURES))
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
        for index, repetition in enumerate(sorted({a['repetition'] for a in attempts if a['business'] == business})):
            pair = {a['arm']: a for a in attempts if a['business'] == business and a['repetition'] == repetition}
            order = list(arms)
            if balanced:
                # Alternate per pair, starting differently per business, fixed before any reading.
                start = sorted({a['business'] for a in attempts}).index(business) % 2
                order = order if (index + start) % 2 == 0 else order[::-1]
            else:
                rnd.shuffle(order)
            name = f'{business}-{repetition}'
            key['pairs'][name] = dict(order=order, kits={arm: pair[arm].get('kit') for arm in order})
            if all(pair[arm].get('kit') for arm in order):
                total = sum(page_count(Path(pair[arm]['run'])) for arm in order)
                key['pairs'][name]['images'] = total
                if total > max_pair_images:
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
    args = sys.argv[1:]
    flag = '--allow-not-run' in args
    option = lambda name: next((a.split('=', 1)[1] for a in args if a.startswith(name + '=')), None)
    reps, captures, limit = option('--repetitions'), option('--captures'), option('--max-pair-images')
    CAPTURES = Path(captures) if captures else None
    args = [a for a in args if not a.startswith('--')]
    build(*args, allow_not_run=flag, repetitions=int(reps) if reps else 6, balanced='--balanced' in sys.argv,
          max_pair_images=int(limit) if limit else MAX_PAIR_IMAGES)
