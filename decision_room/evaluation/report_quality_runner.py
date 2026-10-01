"""3.9 paired versions from immutable Git snapshots, separate databases and storage.

python -m decision_room.evaluation.report_quality_runner run OUTPUT \
    --base-ref REF --new-ref REF --bruma CSV_DIR --wwi CSV_DIR
Failures are preserved. Re-running dispatches only jobs that have never started.
Use summary after independently assessing the exact delivered reports.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from psycopg import sql

from ..config import ROOT, Config
from ..database import connect
from ..local_env import load_env
from ..agent.model import ModelSettings
from .quality_cases import CASES, files, reference
from .quality import compare, digest
from .quality_runner import read, summary as version_summary
from .runner import write

SELECTED = ('bruma-discover', 'wwi-discover', 'wwi-organize')


def order(repeats=2):
    return [(case, repetition, version) for case in SELECTED
            for repetition in range(1, repeats + 1)
            for version in (('base', 'new') if repetition % 2 else ('new', 'base'))]


def child(root, *args, **kwargs):
    env = {**os.environ, 'PYTHONPATH': str(root)}
    return subprocess.run([sys.executable, *args], cwd=root, env=env, **kwargs)


def source_hash(root):
    return child(root, '-c', 'from decision_room.evaluation.quality_runner import source_version; print(source_version())',
                 capture_output=True, text=True, check=True).stdout.strip()


def freeze(directory, ref):
    revision = subprocess.run(['git', 'rev-parse', ref + '^{commit}'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    archive = directory.with_suffix('.tar')
    subprocess.run(['git', 'archive', '-o', str(archive), revision], cwd=ROOT, check=True)
    directory.mkdir()
    subprocess.run(['tar', '-xf', str(archive), '-C', str(directory)], check=True)
    archive.unlink()
    local = directory / '.local'; local.mkdir()
    shutil.copyfile(ROOT / '.local/sandbox-runtime.json', local / 'sandbox-runtime.json')
    # Reuse the verified runtime, with separate staging beneath its mounted path.
    staging = (ROOT / '.local/sandbox-inputs').resolve() / ('evaluation-' + uuid4().hex)
    staging.mkdir()
    (local / 'sandbox-inputs').symlink_to(staging, target_is_directory=True)
    return revision


def prepare(directory, base_ref, new_ref, datasets):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = read(directory / 'manifest.json')
    model = asdict(ModelSettings.load())
    refs = dict(base=base_ref, new=new_ref)
    revisions = {v: subprocess.run(['git', 'rev-parse', r + '^{commit}'], cwd=ROOT,
                  capture_output=True, text=True, check=True).stdout.strip() for v, r in refs.items()}
    if existing:
        if existing['revisions'] != revisions or existing['model'] != model:
            raise ValueError('Cannot mix revisions or model settings in a frozen batch')
        for version in ('base', 'new'):
            folder = directory / version
            manifest = read(folder / 'manifest.json')
            if source_hash(Path(manifest['source_root'])) != manifest['source_sha256']:
                raise ValueError('Frozen product source changed')
            for dataset in manifest['fixtures'].values():
                if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != h for p, h in dataset.items()):
                    raise ValueError('Frozen fixture changed')
        return existing
    cases = {k: CASES[k] for k in SELECTED}
    frozen = directory / 'fixtures'; frozen.mkdir()
    fixtures = {}
    for dataset, origin in datasets.items():
        destination = frozen / dataset; destination.mkdir()
        for path in files(dataset, origin):
            shutil.copyfile(path, destination / path.name)
        fixtures[dataset] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files(dataset, destination)}
    oracles = {d: reference(d, frozen / d) for d in fixtures}
    batch = dict(revisions=revisions, model=model, cases=cases, order=order(), rubric_version=2)
    for version in ('base', 'new'):
        root = directory / (version + '-source')
        freeze(root, revisions[version])
        folder = directory / version; folder.mkdir()
        database = 'dr_delivery_' + version + '_' + uuid4().hex
        with connect(Config.load()) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        jobs = {f'{case}-{rep}-{version}': dict(case=case, repetition=rep, mode=version,
                intent=cases[case]['intent'], dataset=cases[case]['dataset'],
                status='not_run', key='delivery-' + uuid4().hex)
                for case, rep, v in batch['order'] if v == version}
        manifest = dict(source_root=str(root), source_sha256=source_hash(root), revision=revisions[version],
                        database=database, storage=str(folder / 'storage'), model=model,
                        cases=cases, fixtures=fixtures, jobs=jobs, comparison_modes=['base','new'], rubric_version=2,
                        workflow=dict(quality_first=True, business_planner_modes=['base','new']),
                        reference_sha256={d: digest(o) for d, o in oracles.items()})
        for dataset, oracle in oracles.items():
            write(folder / (dataset + '-reference.json'), oracle)
        write(folder / 'manifest.json', manifest)
        # Both real mount probes must pass before dispatching either product.
        child(root, '-c', 'import sys; from pathlib import Path; from decision_room.evaluation.quality_runner import read, configuration, preflight; from decision_room.database import migrate; p=Path(sys.argv[1]); c=configuration(read(p/"manifest.json")); migrate(c); preflight(c,p)',
              str(folder), check=True)
    write(directory / 'manifest.json', batch)
    return batch


def summary(directory):
    batch = read(directory / 'manifest.json')
    rows = []
    for version in ('base', 'new'):
        rows += version_summary(directory / version)['runs']
    result = dict(revisions=batch['revisions'], runs=rows, rubric_version=2,
                  evaluator_sha256=hashlib.sha256(Path(__file__).with_name('quality.py').read_bytes()).hexdigest(),
                  **compare(rows, ('base', 'new')))
    write(directory / 'summary.json', result)
    return result


def followup(directory, origin, new_ref):
    """Six additional attempts; retain and reuse all six historical base attempts.

    This is a follow-up, not a freshly alternating paired experiment. Original
    new-version failures remain in the origin batch and its denominator.
    """
    original = read(origin / 'manifest.json')
    original_base = read(origin / 'base/manifest.json')
    if not original or not original_base:
        raise ValueError('Follow-up requires a completed frozen comparison')
    for version in ('base', 'new'):
        for name in read(origin / version / 'manifest.json')['jobs']:
            state = read(origin / version / name / 'state.json')
            if not state or state['status'] in ('running', 'not_run'):
                raise ValueError('Finish the original comparison before the follow-up')
    model = asdict(ModelSettings.load())
    if model != original['model']:
        raise ValueError('Follow-up must retain the original model settings')
    revision = subprocess.run(['git', 'rev-parse', new_ref + '^{commit}'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    if not (directory / 'manifest.json').exists():
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        baseline = directory / 'base'; baseline.mkdir()
        write(baseline / 'manifest.json', {**original_base, 'historical_reuse': str(origin / 'base')})
        for name in original_base['jobs']:
            shutil.copytree(origin / 'base' / name, baseline / name)
        for dataset in original_base['fixtures']:
            for suffix in ('reference', 'supplement'):
                path = origin / 'base' / (dataset + '-' + suffix + '.json')
                if path.exists(): shutil.copyfile(path, baseline / path.name)
        root = directory / 'new-source'; freeze(root, revision)
        folder = directory / 'new'; folder.mkdir()
        database = 'dr_delivery_recheck_' + uuid4().hex
        with connect(Config.load()) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        jobs = {f'{case}-{rep}-new': dict(case=case, repetition=rep, mode='new',
            intent=original['cases'][case]['intent'], dataset=original['cases'][case]['dataset'],
            status='not_run', key='delivery-recheck-' + uuid4().hex)
            for case in SELECTED for rep in (1, 2)}
        manifest = {**original_base, 'source_root': str(root), 'source_sha256': source_hash(root),
                    'revision': revision, 'database': database, 'storage': str(folder / 'storage'), 'jobs': jobs}
        write(folder / 'manifest.json', manifest)
        for dataset in original_base['fixtures']:
            for suffix in ('reference', 'supplement'):
                path = origin / 'base' / (dataset + '-' + suffix + '.json')
                if path.exists(): shutil.copyfile(path, folder / path.name)
        batch = dict(revisions=dict(base=original_base['revision'], new=revision), model=model,
                     cases=original['cases'], order=order(), rubric_version=2,
                     followup_of=str(origin), historical_base_reused=True,
                     comparison='Six additional new attempts; historical base reused, without fresh alternating dispatch')
        write(directory / 'manifest.json', batch)
        child(root, '-c', 'import sys; from pathlib import Path; from decision_room.evaluation.quality_runner import read, configuration, preflight; from decision_room.database import migrate; p=Path(sys.argv[1]); c=configuration(read(p/"manifest.json")); migrate(c); preflight(c,p)',
              str(folder), check=True)
    else:
        child(Path(read(directory / 'new/manifest.json')['source_root']), '-c',
              'import sys; from pathlib import Path; from decision_room.evaluation.quality_runner import read, configuration, preflight; p=Path(sys.argv[1]); preflight(configuration(read(p/"manifest.json")),p)',
              str(directory / 'new'), check=True)
    return run(directory, original_base['revision'], revision, {})


def run(directory, base_ref, new_ref, datasets):
    batch = prepare(directory, base_ref, new_ref, datasets)
    for case, rep, version in batch['order']:
        folder = directory / version
        manifest = read(folder / 'manifest.json')
        name = f'{case}-{rep}-{version}'; job = folder / name
        saved = read(job / 'state.json')
        if saved and saved['status'] != 'not_run':
            continue
        if saved and any(saved.get(k) for k in ('business_id', 'session_id', 'research_id', 'review_id')):
            raise ValueError('A reserved attempt with product activity cannot be redispatched')
        if (directory / 'STOP').exists():
            break
        root = Path(manifest['source_root'])
        if source_hash(root) != manifest['source_sha256']:
            raise ValueError('Frozen source changed before dispatch')
        if not saved:
            job.mkdir(mode=0o700); write(job / 'state.json', manifest['jobs'][name])
        print(json.dumps(dict(job=name, event='start')), flush=True)
        started = time.monotonic()
        try:
            with (job / 'run.log').open('a') as log:
                result = child(root, '-m', 'decision_room.evaluation.quality_runner', 'worker', str(job),
                               stdout=log, stderr=subprocess.STDOUT, timeout=7200)
            if result.returncode:
                raise RuntimeError('Worker exited unexpectedly')
        except (subprocess.TimeoutExpired, RuntimeError) as error:
            state = read(job / 'state.json')
            state.update(status='interrupted', issue='Worker timed out' if isinstance(error, subprocess.TimeoutExpired) else str(error),
                         seconds=round(time.monotonic() - started, 3),
                         source_stable=source_hash(root) == manifest['source_sha256'],
                         fixtures_stable=all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h
                             for p, h in manifest['fixtures'][state['dataset']].items()))
            write(job / 'state.json', state)
            child(root, '-c', 'import sys; from pathlib import Path; from decision_room.evaluation.quality_runner import read, configuration, collect; p=Path(sys.argv[1]); collect(configuration(read(p.parent/"manifest.json")),read(p/"state.json"),p)',
                  str(job), check=True)
        summary(directory)
        state = read(job / 'state.json')
        print(json.dumps(dict(job=name, status=state['status'], seconds=state.get('seconds'), issue=state.get('issue'))), flush=True)
    return summary(directory)


def main():
    os.umask(0o077); load_env(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'summary', 'followup'))
    parser.add_argument('directory', type=Path)
    parser.add_argument('--base-ref')
    parser.add_argument('--new-ref')
    parser.add_argument('--wwi', type=Path)
    parser.add_argument('--bruma', type=Path)
    parser.add_argument('--from-batch', type=Path)
    args = parser.parse_args()
    if args.command == 'run':
        if not all((args.base_ref, args.new_ref, args.wwi, args.bruma)):
            parser.error('run requires both refs and both fixture directories')
        result = run(args.directory.resolve(), args.base_ref, args.new_ref,
                     dict(wwi=args.wwi.resolve(), bruma=args.bruma.resolve()))
    elif args.command == 'followup':
        if not all((args.from_batch, args.new_ref)):
            parser.error('followup requires --from-batch and --new-ref')
        result = followup(args.directory.resolve(), args.from_batch.resolve(), args.new_ref)
    else:
        result = summary(args.directory.resolve())
    print(json.dumps(result['modes'], indent=2))


if __name__ == '__main__':
    main()
