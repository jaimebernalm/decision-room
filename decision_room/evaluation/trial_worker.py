"""One Decision Room trial attempt against a FROZEN source tree.

The launcher copies this file into the batch and runs it with PYTHONPATH set to
the frozen revision, so it must only use product APIs present in that revision.
It never receives the oracle. Owner questions get the exact prompt once, then
'unknown': no invented operational context.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

from decision_room.local_env import load_env
from decision_room.database import connect
from decision_room.service import create_business, import_batch
from decision_room.agent import service, research, review
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.evaluation.quality_runner import configuration, collect
from decision_room.evaluation.runner import write
from decision_room.report import export


def read(path):
    return json.loads(Path(path).read_text())


def trace(config, state, job):
    """Exact persisted calls and executions for later forensics."""
    if not state.get('business_id'):
        return
    with connect(config) as db:
        calls = db.execute('SELECT * FROM agent_calls WHERE session_id=%s ORDER BY created_at',
                           (state['session_id'],)).fetchall() if state.get('session_id') else []
        executions = db.execute('SELECT * FROM executions WHERE business_id=%s ORDER BY created_at',
                                (state['business_id'],)).fetchall()
    write(job / 'model-calls.json', calls)
    write(job / 'executions.json', executions)


def main(job):
    job = Path(job)
    batch = job.parent.parent
    manifest, state = read(batch / 'manifest.json'), read(job / 'state.json')
    assert state['status'] == 'not_run', 'Never redispatch a started attempt.'
    load_env(Path(manifest['env_file']))
    os.environ['DECISION_ROOM_DATABASE_URL'] = manifest['dsn']
    # Older batches have a single product arm described at the top level.
    arm = manifest.get('arms', {}).get(state['system'], manifest)
    os.environ.update(arm.get('env', {}))
    state['arm'] = {k: arm.get(k) for k in ('ref', 'revision', 'env') if k in arm}
    dataset = manifest['datasets'][state['dataset']]
    inputs = sorted((batch / 'inputs' / state['dataset'] / 'datos').glob('*.csv'))
    prompt = (batch / 'inputs' / state['dataset'] / 'prompt.txt').read_text()
    config = configuration(arm)
    model = ModelClient(ModelSettings(**manifest['model']))
    started = time.monotonic()

    def phase(name):
        state.update(status='running', phase=name)
        write(job / 'state.json', state)
        print(json.dumps({'job': job.name, 'phase': name, 'seconds': round(time.monotonic() - started)}), flush=True)

    try:
        assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs} == dataset['inputs']
        assert hashlib.sha256(prompt.encode()).hexdigest() == dataset['prompt_sha256']
        phase('import')
        state['business_id'] = str(create_business(config, f"{dataset['business']} · {job.name}")['id'])
        write(job / 'state.json', state)
        state['analysis_id'] = str(import_batch(config, state['business_id'], inputs)['analysis']['id'])
        phase('planning')
        plan = service.start(config, state['business_id'], state['analysis_id'], owner_context=prompt,
                             request_key=state['key'] + '-plan', model=model)
        state['session_id'] = str(plan['id'])
        write(job / 'state.json', state)
        for number in range(3):
            if not plan['questions']:
                break
            for question in plan['questions']:
                plan = service.answer(config, state['business_id'], plan['id'], question_id=question['id'],
                                      disposition='answered' if number == 0 else 'unknown',
                                      text=prompt if number == 0 else '',
                                      request_key=f"{state['key']}-answer-{question['id']}", model=model)
        if plan['questions']:
            raise ValueError('Planning questions remain; no invented operational context.')
        phase('research')
        work = research.start(config, state['business_id'], plan['id'], request_key=state['key'] + '-research',
                              model=model, max_parallel=1, quality_first=True, business_planner=True)
        state['research_id'] = str(work['id'])
        write(job / 'state.json', state)
        for _ in range(12):
            if not work.get('pending_questions'):
                break
            question = work['pending_questions'][0]
            work = research.answer(config, state['business_id'], work['id'], question_id=question['id'],
                                   disposition='unknown', request_key=f"{state['key']}-unknown-{question['id']}",
                                   model=model)
        if work.get('pending_questions') or work['status'] == 'replan_required':
            raise ValueError('Research requires additional owner facts.')
        phase('review')
        result = review.start(config, state['business_id'], work['id'], request_key=state['key'] + '-review',
                              analyst=model, reviewer=model)
        state['review_id'] = str(result['id'])
        write(job / 'state.json', state)
        for _ in range(3):
            if not result['pending_questions']:
                break
            question = result['pending_questions'][0]
            result = review.answer(config, state['business_id'], result['id'], step=question['step'],
                                   disposition='unknown', text='',
                                   request_key=f"{state['key']}-unknown-review-{question['step']}",
                                   analyst=model, reviewer=model)
        state['review_status'] = result['status']
        state['publishable'] = bool(result['publishable'])
        if result['publishable']:
            phase('export')
            exported = export(config, state['business_id'], result['id'])
            write(job / 'export.json', exported)
            shutil.copyfile(exported['path'], job / 'informe.html')
        state.update(status='completed', phase='done')
    except Exception as error:
        state.update(status='failed', issue=str(error)[:2000], failed_phase=state.get('phase'))
    finally:
        state['seconds'] = round(time.monotonic() - started, 3)
        try:
            collect(config, state, job)
            trace(config, state, job)
        except Exception as error:
            state['collect_issue'] = str(error)[:2000]
        write(job / 'state.json', state)
        print(json.dumps({k: state.get(k) for k in ('job', 'status', 'seconds', 'publishable', 'issue')},
                         ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
