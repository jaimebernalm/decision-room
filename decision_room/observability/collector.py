"""Reconcile authoritative records without invoking agents or publication code.

Writers call this at durable boundaries. A worker sampler provides catch-up while
external operations are running; HTTP readers never reconcile.
"""
from uuid import UUID,uuid5
from datetime import datetime,timezone
from . import store
from .privacy import text

ROLE_LABELS={'planning':'Preparando las preguntas del análisis','business_planner':'Contrastando el trabajo con tu objetivo',
    'research':'Eligiendo las siguientes comprobaciones','analyst_review':'Preparando el informe',
    'reviewer':'Revisando las conclusiones','chat':'Preparando tu respuesta','chat_reviewer':'Revisando la respuesta'}
STATE={'new':'queued','ready':'completed','approved':'completed','partial':'completed','limited':'failed','blocked':'failed',
       'rejected':'failed','withdrawn':'superseded','stale':'superseded','waiting':'waiting_owner','replan_required':'superseded',
       'preparing':'running','routing':'running','processing':'running','uncertain':'interrupted',
       'timed_out':'failed','invalid_output':'failed','resource_limit':'failed'}


def emit(db,business,trace,kind,key,status,label,*,role='system',actor=None,parent=None,source=None,
         purpose='',refs=(),at=None,payload=None,reconstructed=False,event_type=None,started_at=None,finished_at=None,finish_unknown=False):
    state=STATE.get(status,status)
    if state not in store.STATES: state='running'
    source=source or {'kind':kind,'id':str(key)}
    with db.transaction():
        db.execute('SELECT id FROM activity_traces WHERE business_id=%s AND id=%s FOR UPDATE',(business,trace))
        old=db.execute('SELECT * FROM activity_tasks WHERE trace_id=%s AND kind=%s AND source_id=%s',
                       (trace,kind,str(key))).fetchone()
        label=text(label);purpose=text(purpose)
        if old and old['status']==state and old['public_text']==label and old['purpose']==purpose and (parent is None or old['parent_task_id']==parent) and old['role']==role and old['actor_id']==(actor or role) and old['refs']==list(refs) and old['source']==source and (finished_at is None or old['finished_at']==finished_at) and (not finish_unknown or old['finished_at'] is None):
            return old['id']
        return store.append(db,business,trace,kind=kind,source_id=key,role=role,actor_id=actor,
            parent_id=parent,status=state,public_text=label,purpose=purpose,refs=refs,source=source,
            payload=payload,dedupe_key=f'{kind}:{key}:{old["last_sequence"] if old else 0}:{state}',
            occurred_at=at,reconstructed=reconstructed,event_type=event_type,started_at=started_at,finished_at=finished_at,finish_unknown=finish_unknown)


def refs_for(db,business,ids):
    result=[]
    for item in list(ids or ())[:16]:
        try: identifier=UUID(str(item))
        except (TypeError,ValueError): continue
        if db.execute('SELECT 1 FROM prepared_tables WHERE business_id=%s AND id=%s',(business,identifier)).fetchone():
            result.append({'kind':'table','id':str(identifier),'column':''})
    return result


def reconcile(db,business,trace,*,reconstructed=False):
    """May write events. Only worker/maintenance paths call this."""
    t=db.execute('SELECT * FROM activity_traces WHERE business_id=%s AND id=%s',(business,trace)).fetchone()
    if not t: return
    def observe(kind,key,status,label,**kw):
        return store.safe(db,business,trace,emit,kind,key,status,label,reconstructed=reconstructed or bool(kw.get('at') and kw['at']<t['created_at']),**kw)
    links=db.execute('SELECT kind,source_id FROM activity_links WHERE business_id=%s AND trace_id=%s',(business,trace)).fetchall()
    linked={k:[r['source_id'] for r in links if r['kind']==k] for k in ('job','turn','session','execution')}
    analyses=set()
    turn_tasks={}
    for job_id in linked['job']:
        j=db.execute('SELECT * FROM web_jobs WHERE business_id=%s AND id=%s',(business,job_id)).fetchone()
        if not j: continue
        observe('job',j['id'],j['status'],'Preparando el análisis',at=j['updated_at'],started_at=j['created_at'],source={'kind':'job','id':str(j['id']),'phase':j['phase']})
        if j['analysis_id']: analyses.add(j['analysis_id'])
        if j['session_id']:
            store.safe(db,business,trace,store.link,'session',j['session_id'])
            if j['session_id'] not in linked['session']: linked['session'].append(j['session_id'])
    for turn_id in linked['turn']:
        turn=db.execute('SELECT * FROM chat_turns WHERE business_id=%s AND id=%s',(business,turn_id)).fetchone()
        if not turn: continue
        parent=observe('turn',turn_id,turn['status'],'Preparando tu respuesta',role='chat',actor='chat',at=turn['updated_at'],started_at=turn['created_at'])
        turn_tasks[turn_id]=parent
        if turn['job_id']: store.safe(db,business,trace,store.link,'job',turn['job_id'])
        for c in db.execute('SELECT * FROM chat_calls WHERE turn_id=%s ORDER BY attempt,ordinal',(turn_id,)).fetchall():
            key=f'{turn_id}:{c["attempt"]}:{c["ordinal"]}'
            observe('chat_call',key,c['status'],('Fuentes seleccionadas' if (c['response'] or {}).get('action')=='retrieve' else 'Respuesta preparada') if c['status']=='completed' else 'Preparando tu respuesta',role='chat',actor='chat',parent=parent,
                    at=c['finished_at'] or (c['created_at'] if c['status']=='running' else None),started_at=c['created_at'],finished_at=c['finished_at'],finish_unknown=c['status']!='running' and c['finished_at'] is None,source={'kind':'chat_call','action':(c['response'] or {}).get('action',''),'turn_id':str(turn_id),'attempt':c['attempt'],'ordinal':c['ordinal']})
        for r in db.execute('SELECT * FROM chat_retrievals WHERE turn_id=%s ORDER BY attempt,ordinal',(turn_id,)).fetchall():
            observe('retrieval',f'{turn_id}:{r["attempt"]}:{r["ordinal"]}','completed',{'search_reports':'Informes consultados','open_report':'Informe revisado consultado','inspect_dataset':'Datos inspeccionados','search_memory':'Contexto del negocio consultado'}.get(r['request'].get('tool'),'Contexto consultado'),role='chat',actor='chat',parent=parent,
                    source={'kind':'retrieval','turn_id':str(turn_id),'attempt':r['attempt'],'ordinal':r['ordinal']})
        for r in db.execute('SELECT * FROM chat_answer_reviews WHERE turn_id=%s ORDER BY attempt,ordinal',(turn_id,)).fetchall():
            observe('chat_review',f'{turn_id}:{r["attempt"]}:{r["ordinal"]}',r['status'],('Respuesta revisada' if (r['response'] or {}).get('approved') else 'Revisión con ajustes pendientes') if r['status']=='completed' else 'Revisando la respuesta',role='chat_reviewer',actor='chat_reviewer',parent=parent,at=r['finished_at'] or (r['created_at'] if r['status']=='running' else None),started_at=r['created_at'],finished_at=r['finished_at'],finish_unknown=r['status']!='running' and r['finished_at'] is None,source={'kind':'chat_review','turn_id':str(turn_id),'attempt':r['attempt'],'ordinal':r['ordinal']})
    session_tasks={}
    research_tasks={}
    review_tasks={}
    runs={}
    for session_id in linked['session']:
        s=db.execute('SELECT * FROM agent_sessions WHERE business_id=%s AND id=%s',(business,session_id)).fetchone()
        if not s: continue
        analyses.add(s['analysis_id'])
        manifest=db.execute('SELECT stale_reason FROM context_manifests WHERE session_id=%s',(session_id,)).fetchone()
        if manifest and manifest['stale_reason']:
            observe('context',session_id,'superseded','La información del negocio ha cambiado',source={'kind':'context','id':str(session_id)},payload={'reason':manifest['stale_reason']},event_type='context.invalidated')
        state='superseded' if s.get('superseded_by') else s['status']
        owner=db.execute('''SELECT t.id FROM chat_turns t JOIN web_jobs j ON j.id=t.job_id AND j.business_id=t.business_id
            WHERE t.business_id=%s AND j.session_id=%s ORDER BY t.created_at LIMIT 1''',(business,session_id)).fetchone()
        parent=session_tasks.get(s['supersedes_session_id']) or (turn_tasks.get(owner['id']) if owner else None)
        session_tasks[session_id]=observe('planning',session_id,state,'Definiendo qué podemos investigar',role='planning',actor='planning',parent=parent,at=s['updated_at'],started_at=s['created_at'])
        revisions=db.execute('SELECT * FROM agent_revisions WHERE session_id=%s ORDER BY revision',(session_id,)).fetchall()
        for revision in revisions:
            observe('plan',f'{session_id}:{revision["revision"]}','completed','Alcance del análisis preparado',role='planning',actor='planning',parent=session_tasks[session_id],
                at=revision['created_at'],source={'kind':'plan','session_id':str(session_id),'revision':revision['revision']},payload={'proposal':revision['proposal']})
        for q in db.execute('''SELECT q.*,r.created_at,a.id AS answer_id,a.created_at AS answered_at FROM agent_questions q
            JOIN agent_revisions r ON r.session_id=q.session_id AND r.revision=q.revision
            LEFT JOIN agent_answers a ON a.question_id=q.id WHERE q.session_id=%s''',(session_id,)).fetchall():
            observe('question',q['id'],'completed' if q['answer_id'] else 'waiting_owner','Aclaración respondida' if q['answer_id'] else 'Esperando tu respuesta',role='planning',parent=session_tasks[session_id],
                at=q['answered_at'] or q['created_at'],started_at=q['created_at'],finished_at=q['answered_at'],
                refs=[r for r in q['question'].get('references',[]) if r['kind'] in ('table','column')],source={'kind':'question','id':str(q['id'])})
        for run in db.execute('SELECT * FROM agent_research WHERE business_id=%s AND session_id=%s ORDER BY created_at,id',(business,session_id)).fetchall():
            runs[run['id']]=run
            store.safe(db,business,trace,store.link,'research',run['id'])
    branch_number=0
    run_labels={}
    for run_id,run in sorted(runs.items(),key=lambda pair:bool(pair[1]['options'].get('worker_assignment'))):
        branch=db.execute('SELECT * FROM agent_research_branches WHERE business_id=%s AND child_id=%s',(business,run_id)).fetchone()
        role='subanalyst' if branch else 'research'
        questions={i['key']:i for i in run['snapshot'].get('proposal',{}).get('investigations',[])}
        assignment=branch['assignment'] if branch else None
        task=questions.get((assignment or {}).get('investigation_key'),{}) if assignment else next(iter(questions.values())) if len(questions)==1 else {}
        if branch: branch_number+=1
        topic=task.get('activity_label') or (f'Comprobación {branch_number} de los datos' if branch else 'Investigación de los datos')
        run_labels[run_id]=topic
        label=topic
        parent=research_tasks.get(branch['parent_id']) if branch else session_tasks.get(run['session_id'])
        research_tasks[run_id]=observe('branch' if branch else 'research',run_id,run['status'],label,role=role,actor=str(run_id) if branch else 'research',parent=parent,
            at=run['updated_at'],started_at=branch['started_at'] if branch else run['created_at'],purpose='',refs=refs_for(db,business,task.get('table_ids',[])),
            source={'kind':'research','id':str(run_id),'assignment':assignment,'question':task.get('question',''),'parent_id':str(branch['parent_id']) if branch else None})
        for step in db.execute('SELECT * FROM agent_research_steps WHERE research_id=%s ORDER BY step',(run_id,)).fetchall():
            a=step['action'];kind=a['action'];name={'expand':'Ampliando la investigación','record_candidate':'Comprobación registrada, pendiente de revisión',
                 'discard':'Comprobación descartada','block':'Comprobación limitada','delegate':'Investigaciones delegadas','consult_business':'Consultando el enfoque del negocio',
                 'finish':'Investigación terminada','execute':'Cálculo preparado'}.get(kind,'Comprobación preparada')
            observe('research_step',f'{run_id}:{step["step"]}','completed',name,role=role,actor=str(run_id) if branch else 'research',parent=research_tasks[run_id],
                at=step['created_at'],refs=refs_for(db,business,a.get('table_ids',[])),source={'kind':'research_step','research_id':str(run_id),'step':step['step'],'action':kind},
                payload={'action':a,'execution_id':str(step['execution_id']) if step['execution_id'] else None})
            if step['execution_id']:
                store.safe(db,business,trace,store.link,'execution',step['execution_id'])
    for run_id,run in runs.items():
        for event in db.execute('SELECT * FROM business_planner_events WHERE research_id=%s ORDER BY ordinal',(run_id,)).fetchall():
            d=event['direction'];q=d.get('question')
            answer=db.execute('SELECT id,created_at FROM business_planner_answers WHERE event_id=%s',(event['id'],)).fetchone()
            observe('planner_consult',event['id'],'waiting_owner' if q and not answer else 'completed',
                'Esperando tu respuesta' if q and not answer else {'initial':'Enfoque inicial definido','checkpoint':f'Prioridades revisadas · paso {event["ordinal"]}','delivery':'Cobertura del objetivo revisada'}[event['stage']],role='business_planner',actor='business_planner',parent=research_tasks[run_id],
                at=answer['created_at'] if answer else event['created_at'],started_at=event['created_at'],finished_at=answer['created_at'] if answer else None,
                refs=[r for r in (q or {}).get('references',[]) if r['kind'] in ('table','column')],
                source={'kind':'planner_consult','id':str(event['id']),'research_id':str(run_id)},payload={'direction':d})
        for rev in db.execute('SELECT * FROM agent_reviews WHERE business_id=%s AND research_id=%s ORDER BY created_at',(business,run_id)).fetchall():
            store.safe(db,business,trace,store.link,'review',rev['id'])
            parent=observe('review',rev['id'],rev['status'],'Revisando las conclusiones',role='reviewer',actor='reviewer',parent=research_tasks[run_id],at=rev['created_at'],
                           source={'kind':'review','id':str(rev['id'])})
            review_tasks[rev['id']]=parent
            for e in db.execute('SELECT * FROM agent_review_events WHERE review_id=%s ORDER BY step',(rev['id'],)).fetchall():
                action=e['action']['action']
                label={'submit':'Borrador del informe preparado','revise':'Ajustes de la revisión solicitados','approve':'Revisión terminada',
                       'reject':'La revisión necesita atención','execute':'Comprobación adicional preparada','ask_owner':'Esperando tu respuesta'}.get(action,'Revisión registrada')
                answered=db.execute('SELECT created_at FROM agent_review_answers WHERE review_id=%s AND step=%s',(rev['id'],e['step'])).fetchone()
                if action=='ask_owner' and answered: label='Aclaración respondida'
                observe('review_step',f'{rev["id"]}:{e["step"]}','waiting_owner' if action=='ask_owner' and not answered else 'completed',label,
                    role='reviewer' if e['role']=='reviewer' else 'analyst_review',actor='reviewer' if e['role']=='reviewer' else 'analyst_review',parent=parent,at=answered['created_at'] if answered else e['created_at'],
                    started_at=e['created_at'],finished_at=answered['created_at'] if answered else None,
                    source={'kind':'review_step','review_id':str(rev['id']),'step':e['step'],'action':action},payload={'action':e['action']})
                if e['execution_id']: store.safe(db,business,trace,store.link,'execution',e['execution_id'])
    for session_id in linked['session']:
        for c in db.execute('SELECT * FROM agent_calls WHERE session_id=%s ORDER BY created_at,id',(session_id,)).fetchall():
            role=c['phase'];scope=c['scope']
            parent=research_tasks.get(UUID(scope)) if scope and role in ('research','business_planner') else session_tasks.get(session_id)
            if scope and role in ('analyst_review','reviewer'): parent=review_tasks.get(UUID(scope),parent)
            run=runs.get(UUID(scope)) if scope and role=='research' else None
            worker=bool(run and run['options'].get('worker_assignment'))
            call_state='interrupted' if c['status']=='running' and c['issue']=='ModelRequestUncertain' else c['status']
            observe('call',c['id'],call_state,ROLE_LABELS.get(role,'Preparando una comprobación'),role='subanalyst' if worker else role,
                    actor=scope if worker else role,parent=parent,at=c['finished_at'] or c['created_at'],started_at=c['created_at'],finished_at=c['finished_at'],source={'kind':'call','id':str(c['id'])})
            store.safe(db,business,trace,store.link,'call',c['id'])
    executions=db.execute("SELECT source_id FROM activity_links WHERE business_id=%s AND trace_id=%s AND kind='execution'",(business,trace)).fetchall()
    for entry in executions:
        ex=db.execute('SELECT * FROM executions WHERE business_id=%s AND id=%s',(business,entry['source_id'])).fetchone()
        if not ex: continue
        step=db.execute('SELECT research_id FROM agent_research_steps WHERE execution_id=%s ORDER BY created_at LIMIT 1',(ex['id'],)).fetchone()
        owner=step['research_id'] if step else None
        if not owner and ex['request_key'].startswith('research:'):
            try: owner=UUID(ex['request_key'].split(':')[1])
            except ValueError: pass
        parent=research_tasks.get(owner)
        worker=bool(runs.get(owner,{}).get('options',{}).get('worker_assignment'))
        observe('execution',ex['id'],ex['status'],('Cálculo terminado' if ex['status']=='completed' else 'Calculando') + ' · ' + run_labels.get(owner,'Datos del informe'),
                role='subanalyst' if worker else 'research',actor=str(owner) if worker else 'research',parent=parent,at=ex['finished_at'] or ex['created_at'],started_at=ex['created_at'],finished_at=ex['finished_at'],
                refs=refs_for(db,business,[i['id'] for i in ex['inputs'].values()]),source={'kind':'execution','id':str(ex['id'])})
    for analysis in analyses:
        for p in db.execute('SELECT id,source_id,created_at FROM prepared_tables WHERE business_id=%s AND analysis_id=%s',(business,analysis)).fetchall():
            observe('inspection',p['id'],'completed','Archivo preparado para el análisis',role='data',actor='data',at=p['created_at'],refs=refs_for(db,business,[p['id']]),source={'kind':'table','id':str(p['id'])})
        for d in db.execute('SELECT * FROM data_model_discoveries WHERE business_id=%s AND analysis_id=%s ORDER BY created_at',(business,analysis)).fetchall():
            key=f'{analysis}:{d["call_key"]}:{d["attempt"]}'
            discovery_id=uuid5(UUID(str(analysis)),f'{d["call_key"]}:{d["attempt"]}')
            if not store.linked(db,business,'discovery',discovery_id): continue
            observe('discovery',key,d['status'],'Comprobando cómo se relacionan los datos',role='data_discovery',actor='data_discovery',at=d['created_at'],
                source={'kind':'discovery','analysis_id':str(analysis),'call_key':d['call_key'],'attempt':d['attempt']})
        for r in db.execute('SELECT * FROM data_model_revisions WHERE business_id=%s AND analysis_id=%s ORDER BY revision',(business,analysis)).fetchall():
            observe('data_model',f'{analysis}:{r["revision"]}','completed','Modelo de datos registrado',role='data',actor='data',at=r['created_at'],
                source={'kind':'data_model','analysis_id':str(analysis),'revision':r['revision']},payload={'body':r['body']})
