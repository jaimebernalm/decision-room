"""Headless comparative runs through Workspace and the real product controllers.

Private spec/CSV/storage/ledgers live outside Git. No evaluation shell, repaired
report, automatic retry, browser on the host or model call during initialization.
Use init SPEC OUTPUT, run OUTPUT CODE, status OUTPUT, or stop OUTPUT.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

from psycopg import sql
from psycopg.conninfo import make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from decision_room.agent import api_budget
from decision_room.agent.model import ModelSettings
from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.engine import admission, store as engine_store
from decision_room.reports import derive
from decision_room.reports.render_browser import Renderer
from decision_room.web.service import Workspace


def save(path, value):
    path = Path(path)
    temp = path.with_name(path.name+'.tmp')
    with temp.open('x') as out:
        json.dump(value,out,ensure_ascii=False,indent=2,default=str,allow_nan=False)
        out.write('\n');out.flush();os.fsync(out.fileno())
    temp.chmod(0o600);os.replace(temp,path)


def initialize(spec_path, root):
    spec_path, root = Path(spec_path).resolve(), Path(root).resolve()
    spec=json.loads(spec_path.read_text())
    if spec.get('version') != 1 or type(spec.get('repetitions')) is not int or not 1 <= spec['repetitions'] <= 12:
        raise ValueError('Expected version 1 and 1–12 repetitions.')
    if type(spec.get('cap_micro_usd')) is not int or not 1 <= spec['cap_micro_usd'] <= 25_000_000:
        raise ValueError('This trial requires a ceiling of at most 25 USD.')
    root.mkdir(mode=0o700)  # Refuse to overwrite or manufacture an old run.
    base=Config.load();database='dr_product_trial_'+uuid4().hex
    with connect(base) as db:db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
    config=replace(base,dsn=make_conninfo(base.dsn,dbname=database),storage=root/'storage',
        semantic_search=False,report_engine='legacy',**spec.get('engine_limits',{}))
    migrate(config)
    settings=ModelSettings(model='gpt-6-luna',protocol='openai',base_url='https://api.openai.com/v1',
        reasoning='low',max_output_tokens=spec.get('legacy_output_tokens',8192),response_language='es')
    ws=Workspace(config,settings)
    budget_path=Path(spec.get('budget_path',root/'budget.sqlite')).resolve()
    if budget_path.exists():
        policy=api_budget.Ledger(budget_path).snapshot()['policy']
        if policy['cap'] != spec['cap_micro_usd']*1000 or policy['scope_cap'] != spec['scope_cap_micro_usd']*1000:
            raise ValueError('The shared ledger has different ceilings; never reset it.')
    else:
        api_budget.Ledger.create(budget_path,cap_micro_usd=spec['cap_micro_usd'],
                                scope_cap_micro_usd=spec['scope_cap_micro_usd'])
    jobs=[];active=None
    for item in spec['businesses']:
        files=[]
        for name in item['files']:
            source=(spec_path.parent/name).resolve()
            raw=source.read_bytes()
            files.append((source.name,raw))
        # Independent business IDs prevent sequential learning/memory or history
        # in one run from contaminating the following run in either arm.
        for repetition in range(spec['repetitions']):
            for arm in ('legacy','opencode'):
                code=f"{item['key']}-{repetition+1}-{arm}"
                business=ws.save_business({'request_key':str(uuid4()),'name':item['name'],
                    'description':item['description'],'expected_active_id':active})
                active=str(business['id'])
                staged=[ws.stage_upload(name,io.BytesIO(raw),len(raw))['id'] for name,raw in files]
                job=ws.create_batch({'request_key':str(uuid4()),'business_id':active,
                    'profile_revision':business['profile_revision'],'title':item.get('title',item['goal'])[:160],
                    'goal':item['goal'],'files':staged,'engine_kind':arm})['id']
                if item.get('meanings'):
                    from decision_room.data_knowledge import service as knowledge
                    ws.ingest_job(ws.row(job))
                    analysis=ws.row(job)['analysis_id']
                    head=knowledge.ensure(config,active,analysis)
                    with connect(config) as db:
                        tables={name:str(r['id']) for r in knowledge.records(db,active,analysis) for name in r['original_names']}
                    for meaning in item['meanings']:
                        payload={k:v for k,v in meaning.items() if k!='file'}
                        payload['id']=tables[meaning['file']]
                        head=knowledge.change(config,active,analysis,head['revision'],'table',payload)
                jobs.append({'code':code,'job_id':job,'business_id':active,'arm':arm,'repetition':repetition+1,
                    'business_key':item['key'],'inputs':[{'name':n,'sha256':hashlib.sha256(r).hexdigest(),'bytes':len(r)} for n,r in files]})
    save(root/'manifest.json',{'version':1,'config':asdict(config),'settings':asdict(settings),
        'spec_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),'budget_path':str(budget_path),'jobs':jobs})
    print(json.dumps({'database':database,'jobs':len(jobs),'output':str(root)}))


def _execute(root, code):
    root=Path(root).resolve();manifest=json.loads((root/'manifest.json').read_text())
    job=next(j for j in manifest['jobs'] if j['code']==code)
    target=root/'runs'/code;target.mkdir(parents=True,mode=0o700,exist_ok=True)
    if (target/'result.json').exists():
        raise ValueError('This attempt is already recorded; no automatic trial retry.')
    if (target/'started.json').exists():
        raise ValueError('Unfinished attempt requires explicit reconciliation, not a new send.')
    config=Config(**{**manifest['config'],'storage':Path(manifest['config']['storage'])})
    settings=ModelSettings(**manifest['settings']);ws=Workspace(config,settings).scoped(job['business_id'])
    os.environ['DECISION_ROOM_API_BUDGET_PATH']=manifest['budget_path']
    ledger=api_budget.Ledger(manifest['budget_path'])
    if ledger.snapshot()['policy']['stopped']:
        raise api_budget.BudgetStopped('Trial provider budget is stopped.')
    start=time.monotonic();save(target/'started.json',job)
    with api_budget.scope('web:'+job['job_id']):
        ws.run_job(job['job_id'])
    row=ws.row(job['job_id'])
    result={'job':job,'status':row['status'],'phase':row['phase'],'issue':row['issue'],
        'seconds':time.monotonic()-start,'engine_run_id':row['engine_run_id'],
        'session_id':row['session_id'],'research_id':row['research_id'],'review_id':row['review_id'],
        'report_document_id':row['report_document_id'],'delivery':False,'snapshot':False}
    if row['engine_run_id']:
        state=admission.inspect_run(config,job['business_id'],row['engine_run_id'])
        save(target/'engine.json',state)
        receipt=engine_store.read_document(config,job['business_id'],row['engine_run_id'])
        if receipt:
            (target/'informe-agente.html').write_bytes(receipt['raw'])
            result['delivery']=True;result['raw_sha256']=hashlib.sha256(receipt['raw']).hexdigest()
        if row['report_document_id']:
            with connect(config) as db:
                revision=db.execute('SELECT current_revision_id FROM report_documents WHERE id=%s',
                                    (row['report_document_id'],)).fetchone()['current_revision_id']
            if revision:
                output=derive.derive(config,job['business_id'],row['report_document_id'],revision)
                save(target/'derivative.json',output)
                if output.get('snapshot_html'):
                    (target/'informe.html').write_text(output['snapshot_html'])
                    (target/'informe.txt').write_text(output['canonical_text'])
                    result['snapshot']=True
    elif row['status']=='completed':
        display=ws.report(job['job_id'],structured=True)
        html=ws.report(job['job_id']).encode()
        (target/'informe-agente.html').write_bytes(html)
        save(target/'report.json',display)
        result['delivery']=True;result['raw_sha256']=hashlib.sha256(html).hexdigest()
        output=Renderer().render(html,uuid4())
        save(target/'inventory.json',output['inventory'])
        (target/'informe.html').write_text(output['snapshot_html'])
        (target/'informe.txt').write_text(output['inventory']['text'])
        result['snapshot']=True
    result['seconds']=time.monotonic()-start
    result['budget']=ledger.snapshot()
    save(target/'result.json',result)
    print(json.dumps({k:result[k] for k in ('status','phase','delivery','snapshot','seconds')},default=str))


def execute(root, code):
    try:
        _execute(root,code)
    except BaseException as error:
        target=Path(root)/'runs'/code
        if (target.is_dir() and (target/'started.json').exists() and not (target/'result.json').exists()
                and not (target/'failure.json').exists()):
            # Count a crashed/export/render attempt as a loss. Never replay it
            # merely because no final HTML or result record exists.
            save(target/'failure.json',{'exception_type':type(error).__name__})
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('init','run','status','stop'))
    parser.add_argument('path');parser.add_argument('argument',nargs='?')
    args=parser.parse_args()
    if args.command=='init':initialize(args.path,args.argument)
    elif args.command=='run':execute(args.path,args.argument)
    else:
        manifest=json.loads((Path(args.path)/'manifest.json').read_text())
        ledger=api_budget.Ledger(manifest['budget_path'])
        if args.command=='stop':ledger.stop()
        print(json.dumps(ledger.snapshot()))


if __name__=='__main__':main()
