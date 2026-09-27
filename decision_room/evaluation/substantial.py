"""Step 3.1: durable multi-table baseline using the unchanged report pipeline.

Run in a frozen checkout with configured model, PostgreSQL and Docker runtime.
All artifacts and the evaluation database remain local for independent review.
References are computed by the controller and never included in model context.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

from .substantial_data import TABLES, OWNER, GOALS, reference
from .runner import write, source_version, collect, recover_ids
from .assess import token_accounting
from ..config import Config, ROOT
from ..database import connect, migrate
from ..local_env import load_env
from ..service import create_business, import_batch
from ..agent import service, research, review
from ..agent.model import ModelClient, ModelSettings
from ..report import export

PHASES = ('import', 'plan', 'answer', 'research', 'review', 'review-answer', 'export', 'recover')


def owner_reply(question):
    """Repeat only declared owner knowledge; no oracle or improvised answers."""
    text = json.dumps(question, ensure_ascii=False).lower()
    if any(word in text for word in ('extendedprice', 'taxamount', 'lineprofit',
                                     'unitprice', 'moneda', 'currency', 'billtocustomerid',
                                     'customercategory', 'iscreditnote')):
        return 'answered', OWNER
    return 'unknown', ''


def configuration(manifest):
    base = Config.load()
    return replace(base, dsn=make_conninfo(base.dsn, dbname=manifest['database']),
                   storage=Path(manifest['storage']), semantic_search=False)


def worker(directory, phase):
    manifest = json.loads((directory.parent / 'manifest.json').read_text())
    state = json.loads((directory / 'state.json').read_text())
    config = configuration(manifest)
    model = ModelClient(ModelSettings(**manifest['model']))
    start = time.monotonic()
    before = source_version()
    try:
        if before != manifest['source_sha256']:
            raise ValueError('Source changed; create a new batch.')
        business = state.get('business_id')
        key = state['key']
        if phase == 'import':
            if not business:
                business = state['business_id'] = str(create_business(config, 'WWI baseline ' + directory.name)['id'])
                write(directory / 'state.json', state)
            result = import_batch(config, business, [Path(manifest['csv']) / (n + '.csv') for n in TABLES])
            state['analysis_id'] = str(result['analysis']['id'])
            write(directory / 'import.json', result)
            if result['analysis']['status'] != 'ready':
                raise ValueError('Import not fully ready')
        elif phase == 'plan':
            result = service.start(config, business, state['analysis_id'],
                owner_context=OWNER + '\nObjetivo: ' + GOALS[state['scenario']], request_key=key + '-plan', model=model)
            state['session_id'] = str(result['id'])
            write(directory / 'initial-plan.json', result)
        elif phase == 'answer':
            for _ in range(3):
                result = service.show(config, business, state['session_id'])
                if not result['questions']:
                    break
                for q in result['questions']:
                    disposition, text = owner_reply(q)
                    service.answer(config, business, state['session_id'], question_id=q['id'],
                        text=text, disposition=disposition, request_key=key + '-answer-' + q['id'], model=model)
            if service.show(config, business, state['session_id'])['questions']:
                raise ValueError('Unresolved planning question loop')
        elif phase == 'research':
            # Preserve defaults used by the web product: two investigations, 30 s Python.
            result = research.start(config, business, state['session_id'], request_key=key + '-research', model=model)
            state['research_id'] = str(result['id'])
        elif phase == 'review':
            result = review.start(config, business, state['research_id'], request_key=key + '-review',
                                  analyst=model, reviewer=model)
            state['review_id'] = str(result['id'])
        elif phase == 'review-answer':
            for _ in range(3):
                result = review.show(config, business, state['review_id'])
                if not result['pending_questions']:
                    break
                event = result['pending_questions'][0]
                disposition, text = owner_reply(event['action']['question'])
                review.answer(config, business, state['review_id'], step=event['step'], text=text,
                              disposition=disposition, request_key=key + '-review-answer-' + str(event['step']))
            if review.show(config, business, state['review_id'])['pending_questions']:
                raise ValueError('Unresolved review question loop')
        elif phase == 'export':
            result = review.show(config, business, state['review_id'])
            if not result['publishable']:
                raise ValueError('Report not publishable: ' + result['status'])
            write(directory / 'export.json', export(config, business, state['review_id']))
        elif phase == 'recover':
            # Separate process: verify saved approval and evidence survive reopening.
            result = review.show(config, business, state['review_id'])
            with connect(config) as db:
                calls = db.execute('SELECT count(*) AS n FROM agent_calls WHERE session_id=%s', (state['session_id'],)).fetchone()['n']
                executions = db.execute('SELECT count(*) AS n FROM executions WHERE business_id=%s', (business,)).fetchone()['n']
            after = review.resume(config, business, state['review_id'])
            with connect(config) as db:
                unchanged = calls == db.execute('SELECT count(*) AS n FROM agent_calls WHERE session_id=%s', (state['session_id'],)).fetchone()['n']
                unchanged &= executions == db.execute('SELECT count(*) AS n FROM executions WHERE business_id=%s', (business,)).fetchone()['n']
            state['resume_idempotent'] = bool(unchanged and after['publishable'] and result['approved_sha256'] == after['approved_sha256'])
            if not state['resume_idempotent']:
                raise ValueError('Recovery changed approved work')
        state['completed_phases'].append(phase)
        state['status'] = 'completed' if phase == 'recover' else 'running'
    except Exception as error:
        state.update(status='failed', failed_phase=phase, issue=str(error))
    finally:
        state.setdefault('timings', {})[phase] = round(time.monotonic() - start, 3)
        state.setdefault('phase_sources', {})[phase] = {'start': before, 'end': source_version()}
        state['source_stable'] = all(v['start'] == v['end'] == manifest['source_sha256'] for v in state['phase_sources'].values())
        try:
            collect(config, state, directory)
        except Exception as error:
            state.update(status='failed', collection_issue=str(error))
        write(directory / 'state.json', state)
    return int(state['status'] == 'failed')


def summarize(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    jobs = []
    for name in manifest['jobs']:
        job = directory / name
        if not (job / 'state.json').exists():
            jobs.append({'job': name, 'status': 'not_run'})
            continue
        state = json.loads((job / 'state.json').read_text())
        resources = json.loads((job / 'resources.json').read_text()) if (job / 'resources.json').exists() else {}
        report = json.loads((job / 'review.json').read_text()) if (job / 'review.json').exists() else {}
        plan = json.loads((job / 'plan.json').read_text()) if (job / 'plan.json').exists() else {}
        jobs.append({'job': name, 'status': state['status'], 'issue': state.get('issue'),
                     'publishable': report.get('publishable', False), 'review_status': report.get('status'),
                     'source_stable': state.get('source_stable'), 'resume_idempotent': state.get('resume_idempotent'),
                     'seconds': round(sum(state.get('timings', {}).values()), 3),
                     'calls': len(resources.get('calls', [])),
                     'executions': len(resources.get('executions', [])),
                     'execution_failures': sum(e['status'] != 'completed' for e in resources.get('executions', [])),
                     'planning_answers': len(plan.get('answers', [])),
                     'review_questions': sum(e['action']['action'] == 'ask_owner' for e in report.get('conversation', [])),
                     'monetary_cost': None,
                     **token_accounting(resources.get('calls', []), bool(resources))})
    write(directory / 'summary.json', {'jobs': jobs, 'independent_assessment': 'See per-job assessment.json; publishable is not evaluator acceptance.'})
    return jobs


def run(directory, csv, repeats):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = directory / 'manifest.json'
    fixtures = {n: hashlib.sha256((csv / (n + '.csv')).read_bytes()).hexdigest() for n in TABLES}
    settings = asdict(ModelSettings.load())
    version = source_version()
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest['fixtures'], manifest['source_sha256'], manifest['model'], manifest['repeats']) != (fixtures, version, settings, repeats):
            raise ValueError('Cannot mix inputs/code/settings/repeats in a batch')
    else:
        # Compute and save the independent reference before the first model call.
        write(directory / 'reference.json', reference(csv))
        name = 'dr_substantial_' + uuid4().hex
        manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'database': name,
                    'storage': str(directory / 'storage'), 'csv': str(csv), 'fixtures': fixtures,
                    'source_sha256': version, 'model': settings, 'repeats': repeats,
                    'jobs': [f'{goal}-{n}' for goal in GOALS for n in range(1, repeats + 1)],
                    'owner_context': OWNER, 'goals': GOALS,
                    'research_defaults': {'max_investigations': 2, 'python_timeout': 30}}
        with connect(Config.load()) as db:
            db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        write(manifest_path, manifest)
    migrate(configuration(manifest))
    for name in manifest['jobs']:
        job = directory / name
        job.mkdir(exist_ok=True, mode=0o700)
        if not (job / 'state.json').exists():
            write(job / 'state.json', {'key': 'baseline-' + uuid4().hex,
                'scenario': name.rsplit('-', 1)[0], 'status': 'new', 'completed_phases': []})
        for phase in PHASES:
            state = json.loads((job / 'state.json').read_text())
            if state['status'] in ('failed', 'interrupted', 'completed'):
                break
            if phase in state['completed_phases']:
                continue
            if (directory / 'STOP').exists():
                summarize(directory)
                return
            print(json.dumps({'job': name, 'phase': phase, 'event': 'start'}), flush=True)
            started = time.monotonic()
            with (job / (phase + '.log')).open('a') as log:
                try:
                    result = subprocess.run([sys.executable, '-m', __package__ + '.substantial',
                        'worker', str(job), phase], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
                    problem = 'Worker exited unexpectedly' if result.returncode else None
                except subprocess.TimeoutExpired:
                    problem = 'Phase exceeded 1200 seconds; no automatic retry'
            state = json.loads((job / 'state.json').read_text())
            if problem and state['status'] != 'failed':
                state.update(status='interrupted', failed_phase=phase, issue=problem)
                state.setdefault('timings', {})[phase] = round(time.monotonic() - started, 3)
                try:
                    collect(configuration(manifest), state, job)
                except Exception as error:
                    state['collection_issue'] = str(error)
                write(job / 'state.json', state)
            print(json.dumps({'job': name, 'phase': phase, 'status': state['status'], 'issue': state.get('issue')}), flush=True)
            summarize(directory)


def main():
    os.umask(0o077)
    load_env(ROOT / '.env')
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run')
    r.add_argument('directory', type=Path)
    r.add_argument('--csv', type=Path, required=True)
    r.add_argument('--repeats', type=int, choices=range(1, 4), default=2)
    w = sub.add_parser('worker'); w.add_argument('directory', type=Path); w.add_argument('phase', choices=PHASES)
    s = sub.add_parser('summary'); s.add_argument('directory', type=Path)
    args = p.parse_args()
    if args.command == 'worker':
        sys.exit(worker(args.directory.resolve(), args.phase))
    elif args.command == 'summary':
        print(json.dumps(summarize(args.directory.resolve()), indent=2))
    else:
        run(args.directory.resolve(), args.csv.resolve(), args.repeats)


if __name__ == '__main__':
    main()
