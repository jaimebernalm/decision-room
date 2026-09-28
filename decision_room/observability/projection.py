"""Read-only audience projections. No reconciliation, sync, DuckDB or model calls."""
from datetime import datetime,timezone
from uuid import UUID
from ..web.errors import WebError
from .privacy import text,diagnostic

PUBLIC_KINDS=frozenset(('context','chat_call','chat_review','memory', 'planning','research','branch','execution','planner_consult','question','inspection','data_model','review','review_step','retrieval','discovery','plan','research_step','transport'))
HIDDEN_STEPS=frozenset(('execute','finish','record_candidate','consult_business'))


def integer(value,default,minimum=0,maximum=200):
    try: parsed=int(value) if value is not None else default
    except (ValueError,TypeError): raise WebError('La página de actividad no es válida.') from None
    if not minimum<=parsed<=maximum: raise WebError('La página de actividad no es válida.')
    return parsed


def cursor(value,trace):
    if not value: return None
    try:
        identity,sequence=value.split(':')
        if UUID(identity)!=UUID(str(trace)) or not sequence.isdigit(): raise ValueError()
        return int(sequence)
    except (ValueError,TypeError,AttributeError): raise WebError('El cursor no pertenece a este proceso.',409) from None


def public_task(row,*,data_endpoint=None):
    references=[{k:r.get(k,'') for k in ('kind','id','column')} for r in row['refs'] if r.get('kind') in ('table','column')]
    return dict(id=str(row['id']),parent_id=str(row['parent_task_id']) if row['parent_task_id'] else None,
                status=row['status'],text=text(row['public_text'],240),purpose=text(row['purpose'],240),
                kind=row['kind'],references=references[:4],data_endpoint=data_endpoint if references else None,
                question_id=str(row['source'].get('step') if row['kind']=='review_step' else row['source'].get('id')) if row['status']=='waiting_owner' and row['kind'] in ('question','planner_consult','review_step') else None,
                started_at=row['started_at'],finished_at=row['finished_at'],sequence=row['last_sequence'])


def visible(row):
    if row['kind'] not in PUBLIC_KINDS: return False
    if row['kind']=='research_step' and row['source'].get('action') in HIDDEN_STEPS: return False
    return True


def state(db,business,trace,*,config=None):
    job=db.execute('''SELECT j.* FROM web_jobs j JOIN activity_links l ON l.source_id=j.id AND l.kind='job' AND l.business_id=j.business_id
        WHERE l.business_id=%s AND l.trace_id=%s ORDER BY j.created_at DESC LIMIT 1''',(business,trace)).fetchone()
    if job:
        status=job['status'];outdated=False;partial=False;publishable=False
        if job['deleted_at']: return {'status':'restricted','headline':'Este informe se ha retirado','terminal':True,'publishable':False,'job_id':str(job['id'])}
        if job['analysis_id']:
            d=db.execute('SELECT corrected FROM dataset_versions WHERE business_id=%s AND analysis_id=%s',(business,job['analysis_id'])).fetchone()
            outdated=bool(d and d['corrected'])
        if job['review_id']:
            r=db.execute('SELECT status,approved_sha256 FROM agent_reviews WHERE business_id=%s AND id=%s',(business,job['review_id'])).fetchone()
            hold=db.execute('SELECT 1 FROM agent_review_holds WHERE review_id=%s',(job['review_id'],)).fetchone()
            publishable=bool(r and r['status']=='approved' and r['approved_sha256'] and not hold)
            if hold or r and r['status'] in ('stale','withdrawn'): status='blocked'
            if status=='completed' and not publishable: status='blocked'
            final=db.execute("SELECT action->'report' AS report FROM agent_review_events WHERE review_id=%s AND action->>'action'='submit' ORDER BY step DESC LIMIT 1",(job['review_id'],)).fetchone()
            partial=bool(final and final['report'] and (final['report'].get('delivery_status')=='partial' or any(q.get('status')!='answered' for q in final['report'].get('question_coverage',[]))))
        if job['session_id'] and status in ('completed','blocked','failed','waiting'):
            from ..memory.context import reason
            outdated=outdated or bool(reason(db,job['session_id']))
        if outdated: status='stale';publishable=False
        if status=='completed' and publishable and config:
            # Existence only: the report endpoint retains full integrity and
            # publication checks. Polling never materializes or publishes a report.
            from ..storage import Storage
            storage=Storage(config.storage)
            files=db.execute('''SELECT e.code_key AS key FROM executions e JOIN activity_links l
                ON l.source_id=e.id AND l.kind='execution' AND l.business_id=e.business_id
                WHERE l.business_id=%s AND l.trace_id=%s
                UNION SELECT parquet_key FROM prepared_tables WHERE business_id=%s AND analysis_id=%s''',
                (business,trace,business,job['analysis_id'])).fetchall()
            try: missing=any(not storage.path(business,f['key']).is_file() for f in files)
            except ValueError: missing=True
            if missing: status='blocked';publishable=False
        context_notice = ('Se ha incorporado o corregido información del negocio después de preparar este análisis. Actualízalo para usar el contexto vigente; tus archivos y respuestas siguen guardados.' if outdated else None)
        headline={'queued':'En cola para preparar el análisis','running':'Investigando los datos','waiting':'Esperando tu respuesta',
                  'completed':'Análisis completado · Ver proceso','blocked':'El análisis necesita atención','failed':'El análisis se ha interrumpido','stale':'El análisis usa contexto anterior'}.get(status,'Preparando el análisis')
        if status=='completed' and partial: headline='Análisis parcial completado · Ver proceso'
        return dict(status=status,headline=headline,terminal=status in ('completed','blocked','failed','stale'),publishable=publishable,
                    context_notice=context_notice,recovery_href=f'#analysis/{job["id"]}' if outdated else None,partial=partial,job_id=str(job['id']),phase=job['phase'],created_at=job['created_at'],finished_at=job['updated_at'] if job['status'] in ('completed','blocked','failed') else None)
    turn=db.execute('''SELECT t.* FROM chat_turns t JOIN activity_links l ON l.source_id=t.id AND l.kind='turn' AND l.business_id=t.business_id
        WHERE l.business_id=%s AND l.trace_id=%s ORDER BY t.created_at DESC LIMIT 1''',(business,trace)).fetchone()
    if turn:
        status=turn['status']
        return dict(status=status,headline={'completed':'Proceso completado · Ver proceso','queued':'Preparando tu pregunta','waiting':'Esperando tu respuesta',
                   'failed':'La respuesta se ha interrumpido','blocked':'La respuesta necesita atención'}.get(status,'Preparando tu respuesta'),
                    terminal=status in ('completed','failed','blocked','stale'),created_at=turn['created_at'],finished_at=turn['updated_at'] if status in ('completed','failed','blocked','stale') else None,publishable=False)
    task=db.execute("SELECT status FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND kind IN ('review','research','planning') ORDER BY last_sequence DESC LIMIT 1",(business,trace)).fetchone()
    status=task['status'] if task else 'running'
    return dict(status=status,headline={'completed':'Investigación completada · Ver proceso','waiting_owner':'Esperando tu respuesta','failed':'La investigación necesita atención','superseded':'Investigación con contexto anterior'}.get(status,'Investigando los datos'),terminal=status in ('completed','failed','superseded'),publishable=False)


def page(db,business,trace,query,*,internal=False,data_endpoint=None,config=None):
    # Repeatable read ensures task state and replay cursor describe one cut.
    with db.transaction():
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        root=db.execute('SELECT * FROM activity_traces WHERE business_id=%s AND id=%s',(business,trace)).fetchone()
        if not root: raise WebError('Proceso no encontrado.',404)
        after=cursor(query.get('after',[None])[0],trace);before=cursor(query.get('before',[None])[0],trace)
        if after is not None and before is not None: raise WebError('Selecciona una dirección de historial.')
        limit=integer(query.get('limit',[None])[0],100,1)
        high=root['last_sequence']
        if (after is not None and after>high) or (before is not None and before>high+1): raise WebError('El cursor está fuera del historial.',409)
        if after is not None:
            rows=db.execute('SELECT * FROM activity_events WHERE business_id=%s AND trace_id=%s AND sequence>%s AND sequence<=%s ORDER BY sequence LIMIT %s',
                            (business,trace,after,high,limit)).fetchall()
            scanned=rows[-1]['sequence'] if rows else high
            more=scanned<high
        else:
            end=before if before is not None else high+1
            rows=list(reversed(db.execute('SELECT * FROM activity_events WHERE business_id=%s AND trace_id=%s AND sequence<%s ORDER BY sequence DESC LIMIT %s',
                            (business,trace,end,limit)).fetchall()))
            scanned=high;more=False
        first=rows[0]['sequence'] if rows else 1
        # Changed tasks are tied to the same cursor cut. Full task history is paged separately.
        changed=db.execute('''SELECT * FROM activity_tasks WHERE business_id=%s AND trace_id=%s
            AND id=ANY(%s) ORDER BY last_sequence''',
            (business,trace,[r['task_id'] for r in rows])).fetchall()
        active=db.execute("SELECT * FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND status IN ('queued','running','waiting_owner','waiting_dependency','retry_wait') ORDER BY started_at,id LIMIT 24",(business,trace)).fetchall()
        task_map={r['id']:r for r in changed}
        # A filtered internal event still advances the public replay cursor.
        events=[]
        for e in rows:
            task=task_map.get(e['task_id'])
            if not internal and (not task or not visible(task)): continue
            item=dict(id=str(e['id']),task_id=str(e['task_id']),sequence=e['sequence'],type=e['type'],status=e['status'],
                      text=text(e['payload'].get('activity_text',task['public_text'] if task else ''),240),
                      occurred_at=e['occurred_at'],recorded_at=e['recorded_at'],reconstructed=e['reconstructed'])
            if internal: item['source_event_id']=str(e['id'])
            events.append(item)
        current=state(db,business,trace,config=config)
        shown=[public_task(r,data_endpoint=data_endpoint) for r in changed if internal or visible(r)]
        active_public=[public_task(r,data_endpoint=data_endpoint) for r in active if internal or visible(r)]
        # Parent coordinators are not extra concurrent investigations; count real child branches.
        branches=[r for r in active_public if r['kind']=='branch' and r['status']=='running']
        if current['status'] in ('running','routing','processing'):
            if len(branches)>1: current['headline']=f'Investigando diferentes partes del negocio · {len(branches)} tareas en curso'
            elif any(r['status']=='retry_wait' for r in active_public) and not any(r['kind']=='execution' and r['status']=='running' for r in active_public):
                current['headline']='Esperando al proveedor antes de reintentar'
            else:
                running=[r for r in active_public if r['status']=='running' and r['kind'] not in ('research','planning','review')]
                calls=[r for r in active if r['kind'] in ('call','chat_call','chat_review') and r['status']=='running']
                if running: current['headline']=running[-1]['text']
                elif calls: current['headline']=text(calls[-1]['public_text'],240)
                elif branches: current['headline']=branches[0]['text']
                elif any(r['status']=='retry_wait' for r in active_public): current['headline']='Esperando al proveedor antes de reintentar'
        now=datetime.now(timezone.utc)
        health='live' if root['worker_active'] and root['heartbeat_at'] and (now-root['heartbeat_at']).total_seconds()<15 else 'unconfirmed' if root['worker_active'] else 'idle'
        result=dict(schema_version=1,trace_id=str(trace),**current,task_updates=shown,active_tasks=active_public,events=events,
                    next_cursor=f'{trace}:{scanned}',has_more=more,previous_cursor=f'{trace}:{first}' if first>1 else None,
                    history_complete=root['history_complete'],server_time=now,last_activity_at=rows[-1]['recorded_at'] if rows else root['created_at'],worker_health=health)
        if internal:
            changed=db.execute("SELECT * FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND role NOT IN ('system','calculation','transport','data') ORDER BY last_sequence",(business,trace)).fetchall()
            result['actors']=[dict(id=r['actor_id'],role=r['role'],task_id=str(r['id']),parent_id=str(r['parent_task_id']) if r['parent_task_id'] else None,
                                   status=r['status'],assignment_label=text(r['public_text'],240) if r['kind']=='branch' else None,source=diagnostic(r['source'])) for r in changed]
        return result
