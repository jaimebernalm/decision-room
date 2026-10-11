"""Headless comparative runs through Workspace and the real product controllers.

Private spec/CSV/storage/ledgers live outside Git. No evaluation shell, repaired
report, automatic retry, browser on the host or model call during initialization.
Use init SPEC OUTPUT, run OUTPUT CODE, accounting OUTPUT CODE, status OUTPUT, or stop OUTPUT.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import io
import json
import os
import re
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
    # Per-report scope quotas of the ledger. Defaults mirror the engine's admission limits;
    # a spec may widen them so they never bind legacy before the dollar caps do.
    quotas={'input_tokens':6000000,'output_tokens':128000,'calls':60,'seconds':1200,**spec.get('scope_quotas',{})}
    if set(quotas)!={'input_tokens','output_tokens','calls','seconds'} or any(type(v) is not int or v<=0 for v in quotas.values()):
        raise ValueError('Scope quotas must be positive integers.')
    rejections=spec.get('explicit_http_rejections',False)
    if type(rejections) is not bool:
        raise ValueError('explicit_http_rejections must be a boolean.')
    version=api_budget.REJECTION_VERSION if rejections else api_budget.VERSION
    if spec.get('ledger_version',version)!=version:
        raise ValueError('The spec ledger version does not match its rejection policy.')
    if budget_path.exists():
        policy=api_budget.Ledger(budget_path).snapshot()['policy']
        expected={'input_cap':quotas['input_tokens'],'output_cap':quotas['output_tokens'],'calls_cap':quotas['calls'],'seconds_cap':quotas['seconds']}
        if (policy['cap'] != spec['cap_micro_usd']*1000 or policy['scope_cap'] != spec['scope_cap_micro_usd']*1000
                or policy['version'] != version or any(policy[k]!=v for k,v in expected.items())):
            raise ValueError('The shared ledger has different ceilings; never reset it.')
    else:
        api_budget.Ledger.create(budget_path,cap_micro_usd=spec['cap_micro_usd'],
                                scope_cap_micro_usd=spec['scope_cap_micro_usd'],explicit_http_rejections=rejections,**quotas)
    jobs=[];active=None
    for item in spec['businesses']:
        if not isinstance(item['key'],str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',item['key']):
            raise ValueError('Business keys must be simple lowercase identifiers.')
        if any(j['business_key']==item['key'] for j in jobs):
            raise ValueError('Duplicate business key.')
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
    # The owner stand-in knows what any owner knows: today's date, its description and its request.
    owners={item['key']:{'today':spec['owner_today'],'description':item['description'],'goal':item['goal']} for item in spec['businesses']}
    save(root/'manifest.json',{'version':1,'owners':owners,'config':asdict(config),'settings':asdict(settings),
        'spec_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),'budget_path':str(budget_path),'jobs':jobs})
    print(json.dumps({'database':database,'jobs':len(jobs),'output':str(root)}))

MAX_ANSWERS=6
MAX_RERUNS=8
OWNER_PROMPT=(
    'Eres la persona dueña del negocio descrito abajo. Encargaste un informe a una herramienta de análisis y ahora te hace '
    'una pregunta. Responde como lo haría esa persona: en primera persona, breve (de una a tres frases), coherente con la '
    'descripción y con lo que pediste. Puedes expresar preferencias razonables que se deduzcan de tu petición (qué periodos '
    'comparar, qué te importa más). No inventes hechos que no estén en la descripción: causas, cifras, acontecimientos o '
    'significados de columnas que no se explican. Si te preguntan algo así, di con naturalidad que no lo sabes. Si la pregunta '
    'ofrece opciones, elige la que mejor encaje con tu petición. Responde en JSON con "disposition" ("answered" si '
    'respondes, "unknown" si no lo sabes, "declined" si prefieres no responder) y "text" (tu respuesta; vacío si no '
    'respondes).\n\n'
    'Hoy es {today}.\n\nDescripción del negocio:\n{description}\n\nLo que pediste:\n{goal}\n\nPregunta de la herramienta:\n{question}')


def owner_answer(owner, question):
    """Owner stand-in for legacy questions. Sends only through the scoped budget transport."""
    import httpx
    shown={k:question.get(k) for k in ('text','reason','options') if question.get(k)}
    prompt=OWNER_PROMPT.format(today=owner['today'],description=owner['description'],goal=owner['goal'],
                               question=json.dumps(shown,ensure_ascii=False,indent=1))
    transport=api_budget.transport()
    if transport is None:
        raise api_budget.BudgetStopped('The owner stand-in requires the trial budget.')
    schema={'type':'object','additionalProperties':False,'required':['disposition','text'],
            'properties':{'disposition':{'type':'string','enum':['answered','unknown','declined']},'text':{'type':'string'}}}
    with httpx.Client(transport=transport,trust_env=False,timeout=120) as client:
        response=client.post('https://api.openai.com/v1/chat/completions',
            headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']},
            json={'model':'gpt-6-luna','reasoning_effort':'low','store':False,'max_completion_tokens':2000,
                  'response_format':{'type':'json_schema','json_schema':{'name':'owner_answer','strict':True,'schema':schema}},
                  'messages':[{'role':'user','content':prompt}]})
        response.raise_for_status()
        choice=response.json()['choices'][0]
    # A truncated or malformed answer is not an owner declaration: refuse it, never repair it.
    if choice.get('finish_reason')!='stop' or not isinstance(choice['message'].get('content'),str):
        raise ValueError('The owner stand-in did not finish a complete answer.')
    value=json.loads(choice['message']['content'])
    if (not isinstance(value,dict) or set(value)!={'disposition','text'} or value['disposition'] not in ('answered','unknown','declined')
            or not isinstance(value['text'],str) or len(value['text'])>1500
            or (value['disposition']=='answered' and not value['text'].strip())):
        raise ValueError('The owner stand-in answer is invalid.')
    # unknown/declined is sent without text, as the product's «No lo sé» button does; an
    # explanatory text alongside it is dropped, not treated as an invalid declaration.
    return value['disposition'],value['text'].strip() if value['disposition']=='answered' else ''


def _execute(root, code, resume=False):
    root=Path(root).resolve();manifest=json.loads((root/'manifest.json').read_text())
    job=next(j for j in manifest['jobs'] if j['code']==code)
    target=root/'runs'/code;target.mkdir(parents=True,mode=0o700,exist_ok=True)
    if resume:
        # Continue the SAME job whose recorded result was not a terminal product state.
        # The first result is kept; nothing already sent is replayed.
        initial=json.loads((target/'result.json').read_text())
        if initial['status'] not in ('queued','running') or (target/'result-initial.json').exists():
            raise ValueError('Only a non-terminal recorded attempt can be continued, once.')
        os.replace(target/'result.json',target/'result-initial.json')
    elif (target/'result.json').exists():
        raise ValueError('This attempt is already recorded; no automatic trial retry.')
    elif (target/'started.json').exists():
        raise ValueError('Unfinished attempt requires explicit reconciliation, not a new send.')
    config=Config(**{**manifest['config'],'storage':Path(manifest['config']['storage'])})
    settings=ModelSettings(**manifest['settings']);ws=Workspace(config,settings).scoped(job['business_id'])
    os.environ['DECISION_ROOM_API_BUDGET_PATH']=manifest['budget_path']
    ledger=api_budget.Ledger(manifest['budget_path'])
    if ledger.snapshot()['policy']['stopped']:
        raise api_budget.BudgetStopped('Trial provider budget is stopped.')
    start=time.monotonic()
    if resume:
        start-=initial['seconds']  # durations include the first, recorded segment
    else:
        save(target/'started.json',job)
    answers=json.loads((target/'answers.json').read_text()) if resume and (target/'answers.json').exists() else []
    continuations=json.loads((target/'continuations.json').read_text()) if resume and (target/'continuations.json').exists() else []
    with api_budget.scope('web:'+job['job_id']):
        ws.run_job(job['job_id'])
        # Legacy may ask its owner. A stand-in that knows only the spec's description
        # and goal answers, inside the same budget scope as the job; one send per
        # question and no repeat after an uncertain send (it stops the ledger).
        reruns=0
        while True:
            status=ws.row(job['job_id'])['status']
            if status in ('queued','running') and reruns<MAX_RERUNS:
                # Not terminal: the product worker would pick the job up again (for example
                # after a legacy replan). Continue the same job; nothing is resent.
                reruns+=1;continuations.append({'status':status,'at':time.monotonic()-start})
                save(target/'continuations.json',continuations)
                ws.run_job(job['job_id'])
                continue
            if not (status=='waiting' and job['arm']=='legacy' and len(answers)<MAX_ANSWERS):
                break
            pending=ws.detail(job['job_id'])['questions']
            if not pending:
                break
            question=pending[0]
            shown={k:question.get(k) for k in ('text','reason','options')}
            attempt={'question_id':str(question['id']),'phase':question['phase'],'question':shown,'state':'sending',
                     'question_sha256':hashlib.sha256(json.dumps(shown,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
            if any(a['question_id']==attempt['question_id'] and a['phase']==attempt['phase'] for a in answers):
                break  # never send the same question twice; the wait stays a loss
            answers.append(attempt);save(target/'answers.json',answers)  # durable before the send
            disposition,text=owner_answer(manifest['owners'][job['business_key']],question)
            attempt.update(answer=text,disposition=disposition,state='answered')
            save(target/'answers.json',answers)  # durable before the reply; a failed reply is not resent
            ws.reply(job['job_id'],{'request_key':str(uuid4()),'question_id':question['id'],'phase':question['phase'],
                                    'text':text,'disposition':disposition})
            attempt['state']='replied';save(target/'answers.json',answers)
            ws.run_job(job['job_id'])
    row=ws.row(job['job_id'])
    # OpenCode can acknowledge a terminal turn before the provider stream's
    # final settlement commits on the server thread. Export after that boundary
    # rather than reporting a transient reservation as final token consumption.
    identifier=('engine:'+str(row['engine_run_id'])) if row['engine_run_id'] else 'web:'+job['job_id']
    deadline=time.monotonic()+15
    while any(c['scope']==identifier and c['state']=='reserved' for c in ledger.snapshot()['calls']):
        if time.monotonic()>=deadline:
            ledger.stop()
            break
        time.sleep(0.1)
    result={'job':job,'status':row['status'],'phase':row['phase'],'issue':row['issue'],
        'seconds':time.monotonic()-start,'engine_run_id':row['engine_run_id'],
        'session_id':row['session_id'],'research_id':row['research_id'],'review_id':row['review_id'],
        'report_document_id':row['report_document_id'],'delivery':False,'snapshot':False,'owner_answers':len(answers),
        'continuations':len(continuations),'resumed':resume}
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


def execute(root, code, resume=False):
    try:
        _execute(root,code,resume)
    except BaseException as error:
        target=Path(root)/'runs'/code
        if (target.is_dir() and (target/'started.json').exists() and not (target/'result.json').exists()
                and not (target/'failure.json').exists()):
            # Count a crashed/export/render attempt as a loss. Never replay it
            # merely because no final HTML or result record exists.
            save(target/'failure.json',{'exception_type':type(error).__name__})
        raise


def accounting(root, code):
    """Reconcile bookkeeping after controller/server settlement, without a send."""
    root=Path(root).resolve();manifest=json.loads((root/'manifest.json').read_text())
    job=next(j for j in manifest['jobs'] if j['code']==code)
    config=Config(**{**manifest['config'],'storage':Path(manifest['config']['storage'])})
    row=Workspace(config,ModelSettings(**manifest['settings'])).scoped(job['business_id']).row(job['job_id'])
    result={'job_id':job['job_id'],'status':row['status'],'budget':api_budget.Ledger(manifest['budget_path']).snapshot()}
    if row['engine_run_id']:
        result['engine']=admission.inspect_run(config,job['business_id'],row['engine_run_id'])
    save(root/'runs'/code/'accounting-final.json',result)
    print(json.dumps({'status':row['status'],'charged_nano_usd':result['budget']['charged_nano_usd'],
                      'uncertain':result['budget']['uncertain']}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('init','run','continue','accounting','status','stop'))
    parser.add_argument('path');parser.add_argument('argument',nargs='?')
    args=parser.parse_args()
    if args.command=='init':initialize(args.path,args.argument)
    elif args.command=='run':execute(args.path,args.argument)
    elif args.command=='continue':execute(args.path,args.argument,resume=True)
    elif args.command=='accounting':accounting(args.path,args.argument)
    else:
        manifest=json.loads((Path(args.path)/'manifest.json').read_text())
        ledger=api_budget.Ledger(manifest['budget_path'])
        if args.command=='stop':ledger.stop()
        print(json.dumps(ledger.snapshot()))


if __name__=='__main__':main()
