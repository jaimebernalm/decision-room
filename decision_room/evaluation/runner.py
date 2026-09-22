"""Durable evaluation orchestration. Agents never see reference answers or rubrics."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from .cases import ROOT, CASES, SCENARIOS, inputs, reference
from ..config import Config
from ..database import connect
from ..service import create_business, import_batch
from ..agent import service, research, review
from ..agent.model import ModelClient, ModelSettings
from ..report import export
from ..local_env import load_env


def write(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
    temporary.chmod(0o600)
    temporary.replace(path)


def source_version():
    files=sorted((ROOT/'decision_room').rglob('*.py'))
    return hashlib.sha256(b''.join(str(p.relative_to(ROOT)).encode()+p.read_bytes() for p in files)).hexdigest()


def owner_reply(scenario, question=None):
    basis=SCENARIOS[scenario][2]
    if basis in ('unit_price','line_total'):
        question_text=json.dumps(question or {},ensure_ascii=False).lower()
        if not re.search(r'unit price|unitario|per unit|por unidad|line total|row total|total.{0,20}(fila|l[ií]nea)',question_text):
            return 'unknown',''
        responses=json.loads((CASES/'03-ambiguous-amount/evaluation/owner-responses.json').read_text())
        return 'answered',responses[basis]
    return ('declined' if basis=='declined' else 'unknown'),''


def recover_ids(config,state):
    if not state.get('business_id'):return
    with connect(config) as db:
        for table,field,key in [('agent_sessions','session_id','plan'),('agent_research','research_id','research'),('agent_reviews','review_id','review')]:
            row=db.execute(f'SELECT id FROM {table} WHERE business_id=%s AND request_key=%s',
                           (state['business_id'],state['key']+'-'+key)).fetchone()
            if row:state[field]=str(row['id'])


def collect(config,state,directory):
    recover_ids(config,state)
    for field,name,fn in [('session_id','plan',service.show),('research_id','research',research.show),('review_id','review',review.show)]:
        if state.get(field):
            try:write(directory/(name+'.json'),fn(config,state['business_id'],state[field]))
            except Exception as error:write(directory/(name+'-read-error.json'),{'error':str(error)})
    if state.get('session_id'):
        with connect(config) as db:
            calls=db.execute('SELECT phase,status,prompt_version,usage,issue,created_at,finished_at FROM agent_calls WHERE session_id=%s ORDER BY created_at',(state['session_id'],)).fetchall()
            executions=db.execute('SELECT id,status,issue,duration_seconds FROM executions WHERE business_id=%s ORDER BY created_at',(state['business_id'],)).fetchall()
        write(directory/'resources.json',{'calls':calls,'executions':executions,'monetary_cost':None})


def worker(directory,phase):
    state=json.loads((directory/'state.json').read_text())
    config=Config.load()
    model=ModelClient(ModelSettings(**state['model']))
    start=time.monotonic()
    phase_source=source_version()
    try:
        if phase=='import':
            if not state.get('business_id'):
                state['business_id']=str(create_business(config,'Evaluation '+state['scenario'])['id'])
                write(directory/'state.json',state)
            source,_=inputs(state['scenario'])
            state['analysis_id']=str(import_batch(config,state['business_id'],[source])['analysis']['id'])
        elif phase=='plan':
            _,context=inputs(state['scenario'])
            if state.get('supersedes_session_id'):
                value=service.replan(config,state['business_id'],state['supersedes_session_id'],owner_context=state['corrected_context'],request_key=state['key']+'-plan',model=model)
            else:
                value=service.start(config,state['business_id'],state['analysis_id'],owner_context=context,request_key=state['key']+'-plan',model=model)
            state['session_id']=str(value['id'])
            write(directory/'initial-plan.json',value)
        elif phase=='answer':
            plan=service.show(config,state['business_id'],state['session_id'])
            for attempt in range(3):
                if not plan['questions']:break
                for question in plan['questions']:
                    disposition,text=owner_reply(state['scenario'],question)
                    plan=service.answer(config,state['business_id'],state['session_id'],question_id=question['id'],
                                        text=text,disposition=disposition,request_key=state['key']+'-answer-'+question['id'],model=model)
            if plan['questions']:raise ValueError('Question loop: still waiting after three answer batches.')
        elif phase=='research':
            value=research.start(config,state['business_id'],state['session_id'],request_key=state['key']+'-research',max_investigations=3)
            state['research_id']=str(value['id'])
        elif phase=='review':
            value=review.start(config,state['business_id'],state['research_id'],request_key=state['key']+'-review')
            state['review_id']=str(value['id'])
        elif phase=='review-answer':
            value=review.show(config,state['business_id'],state['review_id'])
            for attempt in range(3):
                if not value['pending_questions']:break
                event=value['pending_questions'][0]
                disposition,text=owner_reply(state['scenario'],event['action']['question'])
                value=review.answer(config,state['business_id'],state['review_id'],step=event['step'],text=text,disposition=disposition,
                                    request_key=state['key']+'-review-answer-'+str(event['step']))
            if value['pending_questions']:raise ValueError('Review question loop.')
        elif phase=='export':
            value=export(config,state['business_id'],state['review_id'])
            write(directory/'export.json',value)
            # Fresh-process no-op resume must not add model calls or executions.
            before=review.show(config,state['business_id'],state['review_id'])
            if before['publishable']:
                after=review.resume(config,state['business_id'],state['review_id'])
                if before['approved_sha256']!=after['approved_sha256'] or len(before['model_calls'])!=len(after['model_calls']):
                    raise ValueError('Completed review changed on resume.')
                state['resume_idempotent']=True
            if state.get('supersedes_review_id'):
                old=review.show(config,state['business_id'],state['supersedes_review_id'])
                write(directory/'superseded-review.json',old)
                if old['publishable'] or old['status']!='stale':
                    raise ValueError('Owner correction failed to invalidate the old approval.')
                state['previous_approval_invalidated']=True
        state['completed_phases'].append(phase)
        state['status']='completed' if phase=='export' else 'running'
    except Exception as error:
        state.update(status='failed',issue=str(error),failed_phase=phase)
    finally:
        state.setdefault('phase_sources',{})[phase]={'start':phase_source,'end':source_version()}
        state['source_stable']=all(v['start']==v['end']==state['source_sha256'] for v in state['phase_sources'].values()) and all(p in state['phase_sources'] for p in state['completed_phases'] if p!='import')
        state.setdefault('timings',{})[phase]=round(time.monotonic()-start,3)
        try:
            collect(config,state,directory)
        except Exception as error:
            # A database outage must not erase the original failure or its identity.
            state['collection_issue']=str(error)
            state['status']='failed'
        write(directory/'state.json',state)
    return 0 if state['status']!='failed' else 1


PHASES=('import','plan','answer','research','review','review-answer','export')


def interrupted_phase(directory, phase, issue, started, phase_source):
    # A killed worker cannot run its finally block. Recover durable IDs and
    # account for the interrupted phase instead of showing only earlier work.
    state=json.loads((directory/'state.json').read_text())
    state.update(status='interrupted',issue=issue,failed_phase=phase)
    state.setdefault('timings',{})[phase]=round(time.monotonic()-started,3)
    state.setdefault('phase_sources',{})[phase]={'start':phase_source,'end':source_version()}
    state['source_stable']=all(v['start']==v['end']==state['source_sha256']
                               for v in state['phase_sources'].values()) and all(
                                   p in state['phase_sources'] for p in state['completed_phases'] if p!='import')
    try:
        collect(Config.load(),state,directory)
    except Exception as error:
        state['collection_issue']=str(error)
    write(directory/'state.json',state)


def run_batch(directory,scenarios,repeats,settings,correction=None):
    os.umask(0o077)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    manifest_path=directory/'manifest.json'
    version=source_version()
    fixtures={}
    for scenario in scenarios:
        csv_path,context=inputs(scenario)
        canonical=CASES/SCENARIOS[scenario][0]/'input/sales.csv'
        fixtures[scenario]={'input_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                            'context_sha256':hashlib.sha256(context.encode()).hexdigest(),
                            'reference_csv_sha256':hashlib.sha256(canonical.read_bytes()).hexdigest()}
    requested={'scenarios':scenarios,'repeats':repeats,'model':asdict(settings),'source_sha256':version,'fixtures':fixtures}
    if correction:
        requested['correction']=correction
        requested['fixtures']['line-total']=correction['inherited_fixture']
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest['configuration']!=requested:raise ValueError('Cannot mix source/settings/scenarios in a batch. Start a new directory.')
    else:
        manifest={'configuration':requested,'created_at':datetime.now(timezone.utc).isoformat(),
                  'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  'jobs':[f'{scenario}-{n}' for scenario in scenarios for n in range(1,repeats+1)]}
        write(manifest_path,manifest)
    for scenario in scenarios:
        for n in range(1,repeats+1):
            job=directory/f'{scenario}-{n}';job.mkdir(mode=0o700,exist_ok=True)
            if not (job/'state.json').exists():
                write(job/'state.json',{'key':'eval-'+uuid4().hex,'scenario':scenario,'repetition':n,
                                      'model':asdict(settings),'source_sha256':version,'status':'new','completed_phases':[]})
            state=json.loads((job/'state.json').read_text())
            if state['status'] in ('completed','failed','interrupted'):continue
            for phase in PHASES:
                if (directory/'STOP').exists():
                    print('Stopped between phases by operator; completed phases are preserved.',flush=True)
                    return directory
                state=json.loads((job/'state.json').read_text())
                if phase in state['completed_phases']:continue
                print(json.dumps({'job':job.name,'phase':phase,'event':'start'}),flush=True)
                phase_started=time.monotonic()
                phase_source=source_version()
                try:
                    with (job/(phase+'.log')).open('a') as log:
                        result=subprocess.run([sys.executable,'-m','decision_room.evaluation.runner','worker',str(job),phase],
                                              cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
                except subprocess.TimeoutExpired:
                    interrupted_phase(job,phase,'Phase exceeded 1200 seconds; no automatic retry.',
                                      phase_started,phase_source)
                    result=None
                state=json.loads((job/'state.json').read_text())
                if result is not None and result.returncode and state['status']!='failed':
                    interrupted_phase(job,phase,'Worker exited unexpectedly; inspect before resuming.',
                                      phase_started,phase_source)
                    state=json.loads((job/'state.json').read_text())
                print(json.dumps({'job':job.name,'phase':phase,'event':'end','status':state['status'],'issue':state.get('issue')}),flush=True)
                if state['status'] in ('failed','interrupted'):break
            write(job/'reference.json',reference(scenario))
            from .assess import summary
            summary(directory)
    return directory


def main():
    os.umask(0o077)
    load_env(ROOT / '.env')
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('worker');p.add_argument('directory',type=Path);p.add_argument('phase',choices=PHASES)
    p=sub.add_parser('correct');p.add_argument('source',type=Path);p.add_argument('directory',type=Path)
    p=sub.add_parser('run');p.add_argument('directory',type=Path);p.add_argument('--scenario',action='append',choices=SCENARIOS)
    p.add_argument('--repeats',type=int,choices=range(1,4),default=3);p.add_argument('--model',default=os.environ.get('DECISION_ROOM_AGENT_MODEL','qwen3.8-27b-splash'))
    p.add_argument('--protocol',choices=['lmstudio','lmstudio_structured','chat_completions','openai'],default=os.environ.get('DECISION_ROOM_AGENT_PROTOCOL','lmstudio_structured'))
    p.add_argument('--base-url',default=os.environ.get('DECISION_ROOM_AGENT_BASE_URL'))
    p.add_argument('--reasoning',default=os.environ.get('DECISION_ROOM_AGENT_REASONING','off'))
    p.add_argument('--max-output-tokens',type=int,default=int(os.environ.get('DECISION_ROOM_AGENT_MAX_OUTPUT_TOKENS','8192')))
    args=parser.parse_args()
    if args.command=='worker':sys.exit(worker(args.directory,args.phase))
    if args.command=='correct':
        previous=json.loads((args.source/'state.json').read_text())
        current=review.show(Config.load(),previous['business_id'],previous['review_id'])
        if not current['publishable'] or previous['scenario']!='unit-price':
            raise ValueError('Correction requires a current approved unit-price evaluation.')
        directory=args.directory.resolve();job=directory/'line-total-1'
        job.mkdir(parents=True,mode=0o700,exist_ok=False)
        _,context=inputs('line-total')
        disposition,response=owner_reply('line-total','unit price or row total')
        state={'key':'eval-correction-'+uuid4().hex,'scenario':'line-total','repetition':1,
               'model':previous['model'],'source_sha256':source_version(),'status':'new','completed_phases':['import'],
               'business_id':previous['business_id'],'analysis_id':previous['analysis_id'],
               'supersedes_session_id':previous['session_id'],'supersedes_review_id':previous['review_id'],
               'corrected_context':context+'\nOwner correction: '+response}
        write(job/'state.json',state)
        inherited=json.loads((args.source.parent/'manifest.json').read_text())['configuration']['fixtures']['unit-price']
        inherited=dict(inherited,context_sha256=hashlib.sha256(state['corrected_context'].encode()).hexdigest())
        correction={'source_job':previous['key'],'inherited_fixture':inherited,
                    'description':'Same imported original columns; owner corrects unit price to row total.'}
        run_batch(directory,['line-total'],1,ModelSettings(**previous['model']),correction=correction)
        return
    default_url = 'https://api.openai.com/v1' if args.protocol == 'openai' else 'http://127.0.0.1:1234/'+('api/v1' if args.protocol=='lmstudio' else 'v1')
    settings=ModelSettings(args.model,protocol=args.protocol,base_url=args.base_url or default_url,
                           reasoning=args.reasoning,max_output_tokens=args.max_output_tokens,timeout_seconds=300)
    run_batch(args.directory.resolve(),args.scenario or list(SCENARIOS),args.repeats,settings)


if __name__=='__main__':main()
