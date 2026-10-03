"""Repeated report-quality trials: Luna in Codex CLI versus frozen Decision Room.

  python -m decision_room.evaluation.trials prepare BATCH --dataset bruma=DIR \
      --dataset albor=DIR --product-ref REF [--repeats 3] [--systems luna,product]
  python -m decision_room.evaluation.trials run BATCH [--system luna|product] [--limit N]
  python -m decision_room.evaluation.trials score BATCH
  python -m decision_room.evaluation.trials summary BATCH

Each DIR holds datos/*.csv and prompt.txt; an optional oracle.json beside them is
copied to BATCH/oracles and never into any agent's folder. Product jobs use a
`git archive` snapshot, a fresh database and storage. Every attempt keeps its
state; an attempt that has started is never dispatched again. BATCH must live in
an ignored folder: it holds model traces and private runtime details.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from html import unescape
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4

from ..config import ROOT
from .runner import write

SYSTEMS = ('luna', 'product')
CODEX_ARGS = ['exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
              '--sandbox', 'workspace-write', '--model', 'gpt-6-luna',
              '-c', 'model_reasoning_effort="low"', '-c', 'web_search="disabled"',
              '-c', 'features.multi_agent=false', '-c', 'features.apps=false',
              '--json', '--output-last-message', 'respuesta.md', '-']
LUNA_TIMEOUT = 2400
PRODUCT_TIMEOUT = 5400


def read(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_order(datasets, systems, repeats):
    """Interleave systems and datasets so drift in time affects all arms alike."""
    order = []
    for repetition in range(1, repeats + 1):
        arms = [(d, s) for d in datasets for s in systems]
        if repetition % 2 == 0:
            arms.reverse()
        order += [f'{d}-{s}-{repetition}' for d, s in arms]
    return order


def freeze(target, ref, runtime_root):
    """Snapshot a commit and attach it to the verified sandbox runtime."""
    revision = subprocess.run(['git', 'rev-parse', ref + '^{commit}'], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    archive = target.with_suffix('.tar')
    subprocess.run(['git', 'archive', '-o', str(archive), revision], cwd=ROOT, check=True)
    target.mkdir()
    subprocess.run(['tar', '-xf', str(archive), '-C', str(target)], check=True)
    archive.unlink()
    local = target / '.local'
    local.mkdir()
    shutil.copyfile(runtime_root / '.local/sandbox-runtime.json', local / 'sandbox-runtime.json')
    staging = (runtime_root / '.local/sandbox-inputs').resolve() / ('trial-' + uuid4().hex)
    staging.mkdir()
    (local / 'sandbox-inputs').symlink_to(staging, target_is_directory=True)
    return revision


def copy_inputs(source, target):
    (target / 'datos').mkdir(parents=True)
    for path in sorted((source / 'datos').glob('*.csv')):
        shutil.copyfile(path, target / 'datos' / path.name)
        (target / 'datos' / path.name).chmod(0o444)
    shutil.copyfile(source / 'prompt.txt', target / 'prompt.txt')
    return {p.name: sha(p) for p in sorted((target / 'datos').glob('*.csv'))}


def prepare(batch, datasets, product_ref, repeats, systems, runtime_root, env_file):
    if (batch / 'manifest.json').exists():
        raise SystemExit('Batch already prepared; inspect it or choose another folder.')
    batch.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'systems': systems,
                'repeats': repeats, 'datasets': {}, 'harness_sha256': sha(__file__),
                'worker_sha256': sha(Path(__file__).with_name('trial_worker.py'))}
    for name, source in datasets.items():
        source = Path(source).resolve()
        target = batch / 'inputs' / name
        inputs = copy_inputs(source, target)
        prompt = (target / 'prompt.txt').read_text()
        first = prompt.split('.', 1)[0]
        manifest['datasets'][name] = {'inputs': inputs, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
                                      'business': re.sub(r'^Mi negocio es ', '', first)[:80]}
        if (source / 'oracle.json').exists():
            (batch / 'oracles').mkdir(exist_ok=True)
            shutil.copyfile(source / 'oracle.json', batch / 'oracles' / f'{name}.json')
    if 'product' in systems:
        from ..agent.model import ModelSettings
        from ..local_env import load_env
        import psycopg
        from psycopg import sql
        from psycopg.conninfo import make_conninfo
        load_env(env_file)
        settings = ModelSettings.load()
        if (settings.model, settings.reasoning) != ('gpt-6-luna', 'low'):
            raise SystemExit('Product must use gpt-6-luna with low reasoning, as Luna in Codex does.')
        dsn = os.environ.get('DECISION_ROOM_DATABASE_URL')
        if not dsn:
            raise SystemExit('Set DECISION_ROOM_DATABASE_URL to the local PostgreSQL cluster.')
        revision = freeze(batch / 'source', product_ref, runtime_root)
        database = 'dr_trials_' + uuid4().hex
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        shutil.copyfile(Path(__file__).with_name('trial_worker.py'), batch / 'worker.py')
        manifest.update(product_ref=product_ref, revision=revision, database=database,
                        dsn=make_conninfo(dsn, dbname='postgres'), storage=str(batch / 'storage'),
                        env_file=str(Path(env_file).resolve()), model=asdict(settings))
    if 'luna' in systems:
        binary = shutil.which('codex')
        if not binary:
            raise SystemExit('Codex CLI not found on PATH.')
        manifest['codex'] = {'version': subprocess.check_output([binary, '--version'], text=True).strip(),
                             'args': CODEX_ARGS}
    manifest['order'] = plan_order(list(datasets), systems, repeats)
    for name in manifest['order']:
        dataset, system, repetition = name.rsplit('-', 2)
        job = batch / 'jobs' / name
        job.mkdir(parents=True)
        if system == 'luna':
            copy_inputs(batch / 'inputs' / dataset, job)
        write(job / 'state.json', {'job': name, 'dataset': dataset, 'system': system,
                                   'repetition': int(repetition), 'status': 'not_run',
                                   'key': 'trial-' + uuid4().hex})
    write(batch / 'manifest.json', manifest)
    if 'product' in systems:
        env = {**os.environ, 'PYTHONPATH': str(batch / 'source')}
        subprocess.run([sys.executable, '-c', PREFLIGHT, str(batch)], cwd=batch / 'source', env=env, check=True)
    return manifest


PREFLIGHT = '''import json,os,sys
from pathlib import Path
from decision_room.local_env import load_env
from decision_room.database import migrate
from decision_room.evaluation.quality_runner import configuration, preflight
batch=Path(sys.argv[1]);manifest=json.loads((batch/"manifest.json").read_text())
load_env(Path(manifest["env_file"]));os.environ["DECISION_ROOM_DATABASE_URL"]=manifest["dsn"]
config=configuration(manifest);migrate(config);preflight(config,batch)
print("Frozen source migrated; sandbox preflight passed.")
'''


def events(path):
    result = []
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                result.append(json.loads(line))
            except ValueError:
                pass
    return result


def run_luna(batch, job):
    state = read(job / 'state.json')
    binary = shutil.which('codex')
    argv = [binary, *read(batch / 'manifest.json')['codex']['args']]
    env = {k: v for k, v in os.environ.items() if k != 'OPENAI_API_KEY' and not k.startswith('DECISION_ROOM_')}
    state.update(status='running', started_at=datetime.now(timezone.utc).isoformat())
    write(job / 'state.json', state)
    started = time.monotonic()
    try:
        with (job / 'prompt.txt').open('rb') as source, (job / 'eventos.jsonl').open('wb') as out, \
                (job / 'errores.log').open('wb') as err:
            process = subprocess.Popen(argv, cwd=job, stdin=source, stdout=out, stderr=err, env=env,
                                       start_new_session=True)
            try:
                code = process.wait(timeout=LUNA_TIMEOUT)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                code, state['status'] = process.returncode, 'timed_out'
        log = events(job / 'eventos.jsonl')
        completed = [e for e in log if e.get('type') == 'turn.completed']
        commands = [e['item'] for e in log if e.get('type') == 'item.completed'
                    and e.get('item', {}).get('type') == 'command_execution']
        state.update(exit_code=code, usage=[e.get('usage') for e in completed], commands=len(commands),
                     failed_commands=sum(c.get('exit_code') not in (0, None) for c in commands),
                     report_exists=(job / 'informe.html').exists(),
                     inputs_unchanged={p.name: sha(p) for p in sorted((job / 'datos').glob('*.csv'))}
                     == read(batch / 'manifest.json')['datasets'][state['dataset']]['inputs'])
        if state['status'] != 'timed_out':
            state['status'] = 'completed' if code == 0 and completed else 'failed'
    except Exception as error:
        state.update(status='failed', issue=str(error)[:2000])
    finally:
        state['seconds'] = round(time.monotonic() - started, 3)
        write(job / 'state.json', state)


def run_product(batch, job):
    env = {**os.environ, 'PYTHONPATH': str(batch / 'source')}
    try:
        subprocess.run([sys.executable, str(batch / 'worker.py'), str(job)], cwd=batch / 'source',
                       env=env, timeout=PRODUCT_TIMEOUT)
    except subprocess.TimeoutExpired:
        state = read(job / 'state.json')
        state.update(status='timed_out', issue=f'Exceeded {PRODUCT_TIMEOUT} seconds.')
        write(job / 'state.json', state)


def run(batch, system=None, limit=None):
    manifest = read(batch / 'manifest.json')
    if 'product' in manifest['systems']:
        frozen = subprocess.run([sys.executable, '-c',
                                 'from decision_room.evaluation.quality_runner import source_version;print(source_version())'],
                                cwd=batch / 'source', env={**os.environ, 'PYTHONPATH': str(batch / 'source')},
                                capture_output=True, text=True, check=True).stdout.strip()
        manifest.setdefault('source_sha256', frozen)
        if frozen != manifest['source_sha256']:
            raise SystemExit('Frozen source changed; start a separate batch.')
        write(batch / 'manifest.json', manifest)
    dispatched = 0
    for name in manifest['order']:
        job = batch / 'jobs' / name
        state = read(job / 'state.json')
        if state['status'] != 'not_run' or (system and state['system'] != system):
            continue
        if limit is not None and dispatched >= limit:
            break
        print(json.dumps({'dispatch': name}), flush=True)
        (run_luna if state['system'] == 'luna' else run_product)(batch, job)
        dispatched += 1
        print(json.dumps({k: read(job / 'state.json').get(k) for k in ('job', 'status', 'seconds')}), flush=True)
    return dispatched


def text_of(html):
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', html))).strip()


def hinted(text, groups):
    lower = text.lower()
    return all(any(term.lower() in lower for term in group) for group in groups)


JARGON = {
    'internal_ids': r'\b[A-Z]{1,3}\d{2}\s*[×x|]\s*[A-Z]{2}\b|\[[A-Z]\d{2}×[A-Z]{2}\]',
    'raw_decimals': r'\b\d+\.\d{4,}\b',
    'causal_disclaimers': r'no (?:demuestra|prueba|identifica|establece)[^.]{0,40}caus|sin atribuir|no equivale a causa',
}


def resources(job, state):
    if state['system'] == 'luna':
        usage = [u or {} for u in state.get('usage', [])]
        return {'seconds': state.get('seconds'), 'steps': state.get('commands'),
                'failed_steps': state.get('failed_commands'),
                'input_tokens': sum(u.get('input_tokens', 0) for u in usage),
                'output_tokens': sum(u.get('output_tokens', 0) for u in usage)}
    data = read(job / 'resources.json', {'calls': [], 'executions': []})
    usage = [c.get('usage') or {} for c in data['calls']]
    return {'seconds': state.get('seconds'), 'steps': len(data['calls']),
            'failed_steps': sum(e.get('status') != 'completed' for e in data['executions']),
            'executions': len(data['executions']),
            'input_tokens': sum(u.get('prompt_tokens', u.get('input_tokens', 0)) or 0 for u in usage),
            'output_tokens': sum(u.get('completion_tokens', u.get('output_tokens', 0)) or 0 for u in usage)}


def score(batch):
    """Automatic indicators only. Signal hints are NOT a verdict; humans score separately."""
    manifest = read(batch / 'manifest.json')
    rows = []
    for name in manifest['order']:
        job = batch / 'jobs' / name
        state = read(job / 'state.json')
        report = job / 'informe.html'
        text = text_of(report.read_text(errors='replace')) if report.exists() else ''
        oracle = read(batch / 'oracles' / f"{state['dataset']}.json", {'signals': []})
        rows.append({'job': name, 'dataset': state['dataset'], 'system': state['system'],
                     'status': state['status'], 'publishable': state.get('publishable'),
                     'report': report.exists(), 'words': len(text.split()), **resources(job, state),
                     'signal_hints': {s['key']: hinted(text, s['hints']) for s in oracle['signals']} if text else {},
                     'jargon': {k: len(re.findall(v, text, flags=re.I)) for k, v in JARGON.items()}})
    write(batch / 'scores.json', rows)
    template = batch / 'evaluation.json'
    if not template.exists():
        write(template, {'instructions': 'Human scoring after reading each report. Per signal: detected, prioritized '
                         '(rank given), numbers_correct, reading_correct; null until scored. rubric_39: 12 criteria 0/1/2.',
                         'jobs': {r['job']: {'signals': {k: {'detected': None, 'rank': None, 'numbers_correct': None,
                                                             'reading_correct': None} for k in r['signal_hints']},
                                             'rubric_39': None, 'notes': ''} for r in rows if r['report']}})
    return rows


def median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    middle = len(values) // 2
    return values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2


def summary(batch):
    rows = read(batch / 'scores.json') or score(batch)
    human = (read(batch / 'evaluation.json') or {}).get('jobs', {})
    lines = ['| Conjunto | Sistema | Completadas | Con informe | Mediana s | Mediana entrada | Mediana salida | Indicios de señal | IDs internos | Detección humana |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |']
    groups = {}
    for row in rows:
        groups.setdefault((row['dataset'], row['system']), []).append(row)
    for (dataset, system), items in sorted(groups.items()):
        hints = Counter(k for r in items for k, v in r['signal_hints'].items() if v)
        detected = Counter(k for r in items for k, v in human.get(r['job'], {}).get('signals', {}).items()
                           if v.get('detected'))
        lines.append('| {} | {} | {}/{} | {} | {} | {} | {} | {} | {} | {} |'.format(
            dataset, system, sum(r['status'] == 'completed' for r in items), len(items),
            sum(r['report'] for r in items), median([r['seconds'] for r in items]),
            median([r['input_tokens'] for r in items]), median([r['output_tokens'] for r in items]),
            ', '.join(f'{k} {v}/{len(items)}' for k, v in sorted(hints.items())) or '—',
            sum(r['jargon']['internal_ids'] for r in items),
            ', '.join(f'{k} {v}/{len(items)}' for k, v in sorted(detected.items())) or 'pendiente'))
    table = '\n'.join(lines) + '\n'
    (batch / 'summary.md').write_text(table)
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('batch', type=Path)
    p.add_argument('--dataset', action='append', required=True, help='NAME=DIR with datos/ and prompt.txt')
    p.add_argument('--product-ref', default='HEAD')
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--systems', default='luna,product')
    p.add_argument('--runtime-root', type=Path, default=ROOT,
                   help='Checkout whose .local holds sandbox-runtime.json and the mounted sandbox-inputs')
    p.add_argument('--env-file', type=Path, default=ROOT / '.env')
    r = commands.add_parser('run')
    r.add_argument('batch', type=Path)
    r.add_argument('--system', choices=SYSTEMS)
    r.add_argument('--limit', type=int)
    for name in ('score', 'summary'):
        commands.add_parser(name).add_argument('batch', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        datasets = dict(item.split('=', 1) for item in args.dataset)
        systems = [s for s in args.systems.split(',') if s]
        if not systems or set(systems) - set(SYSTEMS):
            raise SystemExit('Systems must be luna and/or product.')
        manifest = prepare(args.batch.resolve(), datasets, args.product_ref, args.repeats, systems,
                           args.runtime_root.resolve(), args.env_file)
        print(json.dumps({'jobs': manifest['order'], 'revision': manifest.get('revision')}, indent=2))
    elif args.command == 'run':
        print(json.dumps({'dispatched': run(args.batch.resolve(), args.system, args.limit)}))
    elif args.command == 'score':
        print(json.dumps(score(args.batch.resolve()), ensure_ascii=False, indent=2))
    else:
        print(summary(args.batch.resolve()))


if __name__ == '__main__':
    main()
