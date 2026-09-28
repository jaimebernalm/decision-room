"""3.6 isolated, immutable, repeated quality matrix. No reference answers reach agents.

python -m decision_room.evaluation.quality_runner run OUTPUT --wwi CSV_DIR --bruma CSV_DIR
python -m decision_room.evaluation.quality_runner summary OUTPUT
Credentials/DSN come from environment. Generated datasets and reports stay local.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from ..config import Config, ROOT
from ..database import connect, migrate
from ..service import create_business, import_batch
from ..agent import service, research, review
from ..agent.model import ModelClient, ModelSettings
from ..local_env import load_env
from ..report import export
from .runner import write, collect as collect_pipeline
from .quality_cases import CASES, files, reference
from .quality import assess, compare, resources, digest


def source_version():
    paths = sorted([*(ROOT / 'decision_room').rglob('*.py'), ROOT / 'decision_room/schema.sql',
                    *(ROOT / 'frontend/src').rglob('*.tsx'), *(ROOT / 'frontend/src').rglob('*.ts')])
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode() + p.read_bytes() for p in paths)).hexdigest()


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def configuration(manifest):
    base = Config.load()
    return replace(base, dsn=make_conninfo(base.dsn, dbname=manifest['database']),
                   storage=Path(manifest['storage']), semantic_search=False)


def collect(config, state, directory):
    collect_pipeline(config, state, directory)
    collect_discovery_resources(config, state, directory)


def collect_discovery_resources(config, state, directory):
    """Discovery runs before a planning session exists, including early failures."""
    if not state.get('business_id'):
        return
    data = read(directory / 'resources.json', {'calls': [], 'executions': []})
    with connect(config) as db:
        calls = db.execute("""SELECT 'data_discovery' AS phase,status,usage,issue,created_at,
            call_key,attempt FROM data_model_discoveries WHERE business_id=%s ORDER BY created_at""",
            (state['business_id'],)).fetchall()
        if not state.get('session_id'):
            data['executions'] = db.execute('SELECT id,status,issue,duration_seconds FROM executions WHERE business_id=%s ORDER BY created_at',
                                           (state['business_id'],)).fetchall()
    data['calls'] = [c for c in data['calls'] if c['phase'] != 'data_discovery'] + calls
    data['includes_data_discovery'] = True
    write(directory / 'resources.json', data)


def preflight(config, directory):
    """Exercise the actual Docker bind mount before spending any model calls."""
    from ..execution import execute
    from ..service import describe
    previous = read(directory / 'preflight.json')
    if previous and previous.get('status') == 'completed':
        return
    business = create_business(config, 'Evaluation runtime probe')['id']
    path = directory / 'runtime-probe.csv'
    path.write_text('probe\n1\n')
    batch = import_batch(config, business, [path])
    analysis = batch['analysis']['id']
    table = next(f['table_id'] for f in describe(config, business, analysis)['files'] if f.get('table_id'))
    result = execute(config, business, analysis, request_key='runtime-probe', tables={'probe': table},
        code="from dr_runtime import connect, write_result\nwith connect() as db: n=db.execute('SELECT count(*) FROM probe').fetchone()[0]\nwrite_result({'rows':n},evidence=[{'metric':'rows','tables':['probe'],'operation':'SELECT count(*) FROM probe'}])")
    write(directory / 'preflight.json', {k: result[k] for k in ('id', 'status', 'issue', 'result', 'environment')})
    if result['status'] != 'completed' or result['result']['metrics']['rows'] != 1:
        raise ValueError('Runtime preflight failed; no model calls made: ' + str(result['issue']))


def worker(directory):
    manifest = read(directory.parent / 'manifest.json')
    state = read(directory / 'state.json')
    config = configuration(manifest)
    model = ModelClient(ModelSettings(**manifest['model']))
    case = manifest['cases'][state['case']]
    started = time.monotonic()
    phase = 'import'
    state['status'] = 'running'
    write(directory / 'state.json', state)
    try:
        if source_version() != manifest['source_sha256']:
            raise ValueError('Source changed; start a separate batch')
        for path, expected in manifest['fixtures'][case['dataset']].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ValueError('Fixture changed')
        business = create_business(config, 'Evaluation ' + state['case'])['id']
        state['business_id'] = str(business); write(directory / 'state.json', state)
        imported = import_batch(config, business, [Path(p) for p in manifest['fixtures'][case['dataset']]])
        state['analysis_id'] = str(imported['analysis']['id']); write(directory / 'state.json', state)
        phase = 'planning'
        plan = service.start(config, business, state['analysis_id'], owner_context=case['owner'] + '\nObjetivo: ' + case['goal'],
                             request_key=state['key'] + '-plan', model=model)
        state['session_id'] = str(plan['id']); write(directory / 'state.json', state)
        # No ad hoc answers: repeat the predeclared knowledge once, then unknown.
        for round_number in range(3):
            if not plan['questions']:
                break
            for question in plan['questions']:
                plan = service.answer(config, business, plan['id'], question_id=question['id'],
                    disposition='answered' if round_number == 0 else 'unknown',
                    text=case['owner'] if round_number == 0 else '',
                    request_key='answer-' + question['id'], model=model)
        if plan['questions']:
            raise ValueError('Planning questions remain after bounded owner replies')
        phase = 'research'
        work = research.start(config, business, plan['id'], request_key=state['key'] + '-research',
                              model=model, max_parallel=1 if state['mode'] == 'serial' else 3)
        state['research_id'] = str(work['id']); write(directory / 'state.json', state)
        phase = 'review'
        result = review.start(config, business, work['id'], request_key=state['key'] + '-review', analyst=model, reviewer=model)
        state['review_id'] = str(result['id']); write(directory / 'state.json', state)
        for _ in range(3):
            if not result['pending_questions']:
                break
            q = result['pending_questions'][0]
            result = review.answer(config, business, result['id'], step=q['step'], disposition='unknown',
                                   text='', request_key='answer-' + str(q['step']), analyst=model, reviewer=model)
        state['status'] = result['status']
        if result['publishable']:
            phase = 'export'
            write(directory / 'export.json', export(config, business, result['id']))
            phase = 'recovery'
            before = len(result['model_calls'])
            after = review.resume(config, business, result['id'], analyst=model, reviewer=model)
            state['resume_idempotent'] = (before == len(after['model_calls']) and
                result['approved_sha256'] == after['approved_sha256'])
            state['status'] = 'completed' if state['resume_idempotent'] else 'failed'
    except Exception as error:
        state.update(status='failed', issue=str(error), failed_phase=phase)
    finally:
        state.update(seconds=round(time.monotonic() - started, 3), source_stable=source_version() == manifest['source_sha256'],
            fixtures_stable=all(Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in manifest['fixtures'][case['dataset']].items()))
        try:
            collect(config, state, directory)
        except Exception as error:
            state.update(status='failed', collection_issue=str(error))
        write(directory / 'state.json', state)
        print(json.dumps({k: state.get(k) for k in ('case', 'mode', 'repetition', 'status', 'seconds', 'issue')}), flush=True)
    return 0


def summary(directory):
    manifest = read(directory / 'manifest.json')
    rows = []
    for name in manifest['jobs']:
        job = directory / name
        state = read(job / 'state.json', manifest['jobs'][name])
        report = read(job / 'review.json', {})
        oracle = read(directory / (state['dataset'] + '-reference.json'))
        result = assess(state, report, oracle, read(job / 'assessment.json'))
        result['checks']['reference_unchanged'] = digest(oracle) == manifest.get('reference_sha256', {}).get(state['dataset'])
        result['checks']['fixtures_unchanged'] = state.get('fixtures_stable') is True
        result['accepted'] = result['accepted'] and result['checks']['reference_unchanged'] and result['checks']['fixtures_unchanged']
        if not result['checks']['reference_unchanged'] or not result['checks']['fixtures_unchanged']:
            result['status'] = 'failed'
        result['assessment_status'] = result['status']
        data = read(job / 'resources.json', {})
        result.update({k: state.get(k) for k in ('case', 'intent', 'mode', 'repetition', 'seconds', 'status', 'issue')})
        result.update(job=name, publishable=bool(report.get('publishable')), review_status=report.get('status'),
                      **resources(data.get('calls', []), data.get('includes_data_discovery') is True and not state.get('collection_issue'), manifest.get('rates')))
        result['execution_failures'] = sum(e['status'] != 'completed' for e in data.get('executions', []))
        result['review_rounds'] = sum(e.get('role') == 'reviewer' for e in report.get('conversation', []))
        rows.append(result)
    result = dict(runs=rows, evaluator_sha256=hashlib.sha256(Path(__file__).with_name('quality.py').read_bytes()).hexdigest(), **compare(rows))
    write(directory / 'summary.json', result)
    html = ['<!doctype html><html lang="es"><meta charset="utf-8"><title>Evaluación 3.6</title><style>body{font:16px/1.5 system-ui;max-width:1250px;margin:40px auto;padding:20px;color:#123}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:10px;border-bottom:1px solid #ddd}a{color:#246b8c}</style><h1>Evaluación de calidad · 3.6</h1><p>Aprobación del producto y aceptación independiente se muestran por separado. Los fallos permanecen en la matriz; los tiempos no prueban una mejora causal.</p><table><tr><th>Caso</th><th>Modo</th><th>Producto</th><th>Evaluación</th><th>Segundos</th><th>Llamadas</th><th>Evidencia</th></tr>']
    for row in rows:
        name = row['job']
        links = [f'<a href="{escape(name)}/{filename}">{label}</a>' for filename, label in
                 [('review.json','Informe y revisión'),('assessment.json','Evaluación'),('resources.json','Recursos')]
                 if (directory / name / filename).exists()]
        exported = read(directory / name / 'export.json', {})
        if exported.get('path'):
            links.append(f'<a href="{escape(Path(exported["path"]).as_uri())}">Ver informe</a>')
        html.append('<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in
            [row['case'] + ' · ' + str(row['repetition']),row['mode'],row['review_status'],
             'Aceptado' if row['accepted'] else row['assessment_status'],row['seconds'],row['calls']])
            + '<td>' + ' · '.join(links) + '</td></tr>')
    html.append('</table><p>Las entradas repetidas y en caché están incluidas en el uso de tokens. Coste desconocido sin tarifas explícitas y uso completo.</p></html>')
    (directory / 'summary.html').write_text(''.join(html))
    return result


def run(directory, datasets, repeats, selected=None):
    cases = {key: CASES[key] for key in (selected or CASES)}
    fixtures = {dataset: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files(dataset, folder)}
                for dataset, folder in datasets.items() if dataset in {c['dataset'] for c in cases.values()}}
    if any(not v for v in fixtures.values()):
        raise ValueError('Missing fixture files')
    expected = dict(source_sha256=source_version(), model=asdict(ModelSettings.load()), repeats=repeats, cases=cases, fixtures=fixtures)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = read(directory / 'manifest.json')
    if manifest:
        if any(manifest[k] != v for k, v in expected.items()):
            raise ValueError('Cannot mix code, fixtures, cases, repeats or model settings')
    else:
        jobs = {}
        for case, definition in cases.items():
            for repetition in range(1, repeats + 1):
                for mode in (('serial', 'parallel') if repetition % 2 else ('parallel', 'serial')):
                    jobs[f'{case}-{repetition}-{mode}'] = dict(case=case, dataset=definition['dataset'], intent=definition['intent'],
                        repetition=repetition, mode=mode, status='not_run', key='quality-' + uuid4().hex)
        name = 'dr_quality_' + uuid4().hex
        with connect(Config.load()) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        manifest = dict(**expected, database=name, storage=str(directory / 'storage'), jobs=jobs,
                        comparison='Independent plans, same inputs/budgets; serial worker scheduling vs parallel, not single-analyst baseline')
        for dataset in fixtures:
            write(directory / (dataset + '-reference.json'), reference(dataset, datasets[dataset]))
        manifest['reference_sha256'] = {d: digest(read(directory / (d + '-reference.json'))) for d in fixtures}
        write(directory / 'manifest.json', manifest)
    migrate(configuration(manifest))
    preflight(configuration(manifest), directory)
    for dataset, expected_hash in manifest['reference_sha256'].items():
        if digest(read(directory / (dataset + '-reference.json'))) != expected_hash:
            raise ValueError('Independent reference changed')
    for name, initial in manifest['jobs'].items():
        job = directory / name; job.mkdir(exist_ok=True, mode=0o700)
        state = read(job / 'state.json')
        if state:
            continue  # Never silently replace failures or duplicate interrupted work.
        if (directory / 'STOP').exists():
            break
        write(job / 'state.json', initial)
        print(json.dumps(dict(job=name, event='start')), flush=True)
        started = time.monotonic()
        try:
            with (job / 'run.log').open('a') as log:
                result = subprocess.run([sys.executable, '-m', __package__ + '.quality_runner', 'worker', str(job)],
                                        cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
            problem = 'Worker exited unexpectedly' if result.returncode else None
        except subprocess.TimeoutExpired:
            problem = 'Worker exceeded 1800 seconds; inspect before explicit recovery'
        if problem:
            state = read(job / 'state.json')
            state.update(status='interrupted', issue=problem, seconds=round(time.monotonic() - started, 3), source_stable=source_version() == manifest['source_sha256'])
            try:
                collect(configuration(manifest), state, job)
            except Exception as error:
                state['collection_issue'] = str(error)
            write(job / 'state.json', state)
        summary(directory)
        state = read(job / 'state.json')
        print(json.dumps(dict(job=name, status=state['status'], seconds=state.get('seconds'), issue=state.get('issue'))), flush=True)
    return summary(directory)


def main():
    os.umask(0o077)
    load_env(ROOT / '.env')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('run', 'worker', 'summary'))
    p.add_argument('directory', type=Path)
    p.add_argument('--wwi', type=Path)
    p.add_argument('--bruma', type=Path)
    p.add_argument('--repeats', type=int, choices=(1, 2, 3), default=2)
    p.add_argument('--cases', nargs='+', choices=tuple(CASES))
    args = p.parse_args()
    directory = args.directory.resolve()
    if args.command == 'worker':
        worker(directory)
    elif args.command == 'summary':
        print(json.dumps(summary(directory)['modes'], indent=2))
    else:
        run(directory, {k: v.resolve() for k, v in [('wwi', args.wwi), ('bruma', args.bruma)] if v}, args.repeats, args.cases)


if __name__ == '__main__':
    main()
