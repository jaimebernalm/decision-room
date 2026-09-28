"""Read-only diagnostic API; operator authorization lives at the HTTP boundary."""
import json
from datetime import datetime,timezone
from uuid import UUID,uuid5
from ..database import connect
from ..observability import projection
from ..observability.privacy import diagnostic,text
from ..storage import Storage
from .errors import WebError,identifier


def authorized(db,trace_id):
    row=db.execute('''SELECT t.*,b.name AS business FROM activity_traces t JOIN web_businesses w ON w.business_id=t.business_id
                     JOIN businesses b ON b.id=t.business_id WHERE t.id=%s''',(identifier(trace_id),)).fetchone()
    if not row: raise WebError('Proceso interno no encontrado.',404)
    return row


def listing(ws,query):
    limit=projection.integer(query.get('limit',[None])[0],25,1,100)
    offset=projection.integer(query.get('offset',[None])[0],0,0,100000)
    business=query.get('business_id',[None])[0]
    with connect(ws.config) as db:
        rows=db.execute('''SELECT t.*,b.name AS business FROM activity_traces t JOIN web_businesses w ON w.business_id=t.business_id
            JOIN businesses b ON b.id=t.business_id WHERE (%s::uuid IS NULL OR t.business_id=%s::uuid)
            ORDER BY t.created_at DESC,t.id LIMIT %s OFFSET %s''',(identifier(business) if business else None,identifier(business) if business else None,251 if query.get('status') else limit+1,offset)).fetchall()
        items=[];scanned=0
        for r in rows[:250]:
            if len(items)==limit: break
            scanned+=1
            current=projection.state(db,r['business_id'],r['id'],config=ws.config)
            title=db.execute('''SELECT j.title,j.goal FROM web_jobs j JOIN activity_links l ON l.source_id=j.id AND l.kind='job' AND l.business_id=j.business_id
                WHERE l.trace_id=%s LIMIT 1''',(r['id'],)).fetchone()
            item=dict(id=str(r['id']),business_id=str(r['business_id']),business=text(r['business']),
                      title=text(title['title']) if title else 'Conversación e investigación',goal=text(title['goal']) if title else '',
                      **current)
            if not query.get('status') or item['status'] in query['status']: items.append(item)
        choices=db.execute('SELECT b.id,b.name FROM businesses b JOIN web_businesses w ON w.business_id=b.id ORDER BY b.name,b.id').fetchall()
        return dict(items=items,has_more=len(rows)>scanned,next_offset=offset+scanned,
                    businesses=[dict(id=str(b['id']),name=text(b['name'])) for b in choices])


def resources(db,root):
    business,trace=root['business_id'],root['id']
    calls=db.execute('''SELECT c.id::text AS id,c.usage,c.status,t.role,c.created_at,c.finished_at
        FROM agent_calls c JOIN activity_links l ON l.source_id=c.id AND l.kind='call'
        JOIN activity_tasks t ON t.trace_id=l.trace_id AND t.kind='call' AND t.source_id=c.id::text
        WHERE l.business_id=%s AND l.trace_id=%s''',(business,trace)).fetchall()
    turns=db.execute("SELECT source_id FROM activity_links WHERE business_id=%s AND trace_id=%s AND kind='turn'",(business,trace)).fetchall()
    for turn in turns:
        for table,role in [('chat_calls','chat'),('chat_answer_reviews','chat_reviewer')]:
            calls.extend(dict(id=f'{"chat" if table=="chat_calls" else "chat-review"}:{turn["source_id"]}:{r["attempt"]}:{r["ordinal"]}',role=role,finished_at=None,**r)
                         for r in db.execute(f'SELECT attempt,ordinal,usage,status,created_at FROM {table} WHERE turn_id=%s',(turn['source_id'],)).fetchall())
    calls.extend(db.execute('''SELECT t.source_id AS id,t.source,d.usage,d.status,'data_discovery' AS role,d.created_at
        FROM activity_tasks t JOIN data_model_discoveries d ON d.business_id=t.business_id
        AND d.analysis_id=(t.source->>'analysis_id')::uuid AND d.call_key=t.source->>'call_key'
        AND d.attempt=(t.source->>'attempt')::integer
        WHERE t.business_id=%s AND t.trace_id=%s AND t.kind='discovery' ''',(business,trace)).fetchall())
    # Older successful calls may lack the final transport metadata. Count only
    # durable attempt tasks for the exact call, never infer attempts from success.
    transport_counts={r['call_id']:r['n'] for r in db.execute(
        "SELECT source->>'call_id' AS call_id,count(*) n FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND kind='transport' GROUP BY source->>'call_id'",
        (business,trace)).fetchall()}
    groups={};unknown=0;known_in=0;known_out=0;attempts=0;unknown_http=0;input_records=0;output_records=0
    for c in calls:
        u=c['usage'] or {};a=u.get('transport_attempts',[])
        call_id=c['id']
        if c['role']=='data_discovery':
            source=c['source'];call_id=str(uuid5(UUID(source['analysis_id']),f"{source['call_key']}:{source['attempt']}"))
        count=len(a) if a else transport_counts.get(call_id,0)
        attempts+=count;unknown_http+=not bool(count)
        inputs=u.get('prompt_tokens',u.get('input_tokens',u.get('total_input_tokens')));outputs=u.get('completion_tokens',u.get('output_tokens',u.get('total_output_tokens')))
        complete=type(inputs) is int and type(outputs) is int and not u.get('rejected_attempt_usage_unknown')
        if not complete: unknown+=1
        group=groups.setdefault(c['role'],dict(calls=0,input_tokens=0,output_tokens=0,unknown_usage=0))
        group['calls']+=1;group['unknown_usage']+=not complete
        if type(inputs) is int: known_in+=inputs;group['input_tokens']+=inputs;input_records+=1
        if type(outputs) is int: known_out+=outputs;group['output_tokens']+=outputs;output_records+=1
    executions=db.execute("SELECT count(*) n FROM activity_links WHERE business_id=%s AND trace_id=%s AND kind='execution'",(business,trace)).fetchone()['n']
    last=db.execute('SELECT max(COALESCE(occurred_at,recorded_at)) at FROM activity_events WHERE trace_id=%s',(trace,)).fetchone()['at']
    current=projection.state(db,business,trace)
    wall_end=(current.get('finished_at') or last or root['created_at']) if current['terminal'] else datetime.now(timezone.utc)
    reused=db.execute("SELECT count(*) n FROM activity_events WHERE trace_id=%s AND type='result.reused'",(trace,)).fetchone()['n']
    # Provider/client wait intervals are unions; overlapping branches aren't summed.
    transitions=db.execute("SELECT task_id,status,COALESCE(occurred_at,recorded_at) AS occurred_at FROM activity_events WHERE trace_id=%s ORDER BY sequence",(trace,)).fetchall()
    def waiting_seconds(state):
        intervals=[];open_tasks={}
        for e in transitions:
            key=e['task_id']
            if e['status']==state and key not in open_tasks: open_tasks[key]=e['occurred_at']
            elif e['status']!=state and key in open_tasks: intervals.append((open_tasks.pop(key),e['occurred_at']))
        intervals.extend((v,wall_end) for v in open_tasks.values())
        merged=[]
        for start,end in sorted(intervals):
            start=max(start,root['created_at']);end=min(end,wall_end)
            if end<=start: continue
            if merged and start<=merged[-1][1]: merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
            else: merged.append((start,end))
        return sum(max(0,(b-a).total_seconds()) for a,b in merged)
    return dict(logical_calls=len(calls),http_attempts=attempts,unknown_http_calls=unknown_http,executions=executions,cache_hits=reused,
                input_tokens=known_in if input_records else None,output_tokens=known_out if output_records else None,unknown_usage_calls=unknown,
                token_usage_complete=bool(calls) and not unknown,by_role=groups,estimated_cost=None,
                wall_seconds=max(0,(wall_end-root['created_at']).total_seconds()),owner_wait_seconds=waiting_seconds('waiting_owner'),
                provider_wait_seconds=waiting_seconds('retry_wait'))


def read(ws,trace_id,query):
    with connect(ws.config) as db:
        root=authorized(db,trace_id)
        result=projection.page(db,root['business_id'],root['id'],query,internal=True,config=ws.config)
        result['resources']=resources(db,root)
        result['business']=text(root['business']);result['business_id']=str(root['business_id'])
        return result


def bounded(value):
    safe=diagnostic(value)
    raw=json.dumps(safe,default=str,ensure_ascii=False)
    def limited(item,depth=0):
        if depth>8: return True
        if isinstance(item,str): return len(item)>12000
        if isinstance(item,(list,dict)):
            return len(item)>100 or any(limited(v,depth+1) for v in (item.values() if isinstance(item,dict) else item))
        return False
    return {'content':safe,'truncated':limited(value)} if len(raw.encode())<=64000 else {'content':raw[:16000],'truncated':True}


def detail(ws,trace_id,kind,object_id,*,event_id=None):
    with connect(ws.config) as db:
        root=authorized(db,trace_id);business,trace=root['business_id'],root['id']
        if kind=='tasks':
            task=db.execute('SELECT * FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND id=%s',(business,trace,identifier(object_id))).fetchone()
            if not task: raise WebError('Tarea no encontrada en este proceso.',404)
            source=task['source'];content={'task':projection.public_task(task),'source':source}
            if event_id:
                selected=db.execute('SELECT id,sequence,type,status,payload,occurred_at,recorded_at,reconstructed FROM activity_events WHERE business_id=%s AND trace_id=%s AND task_id=%s AND id=%s',
                                    (business,trace,task['id'],identifier(event_id))).fetchone()
                if not selected: raise WebError('Evento no encontrado en esta tarea.',404)
                content['selected_event']=selected
            sk=source.get('kind')
            if sk=='call':
                call=db.execute('SELECT phase,prompt_version,context_payload,output,usage,status,issue FROM agent_calls WHERE id=%s',(source['id'],)).fetchone()
                if call:
                    context=call.pop('context_payload') or {}
                    # Useful explicit inputs only. Full memory/prompt headers never leave persistence.
                    call['inputs']={k:context[k] for k in ('analyst_message','stage','owner_replies','message','plan','findings','conversation','assignment') if k in context}
                    content['call']=call
            elif sk=='execution':
                ex=db.execute('SELECT * FROM executions WHERE business_id=%s AND id=%s',(business,source['id'])).fetchone()
                if ex:
                    path=Storage(ws.config.storage).path(business,ex['code_key'])
                    content['execution']={k:ex[k] for k in ('id','status','result','logs','runtime','duration_seconds','issue','inputs','definitions')}
                    content['code']=path.read_text()[:16000] if path.is_file() else '[código no disponible]'
            elif sk=='research':
                r=db.execute('SELECT snapshot,options,status,issue FROM agent_research WHERE business_id=%s AND id=%s',(business,source['id'])).fetchone()
                if r: content['research']={'assignment':source.get('assignment'),'plan':r['snapshot'].get('proposal'),'status':r['status'],'issue':r['issue']}
            elif sk=='chat_call' or sk=='chat_review':
                table='chat_calls' if sk=='chat_call' else 'chat_answer_reviews'
                c=db.execute(f'SELECT context,response,usage,status FROM {table} WHERE turn_id=%s AND attempt=%s AND ordinal=%s',
                             (source['turn_id'],source['attempt'],source['ordinal'])).fetchone()
                if c: content['call']={'inputs':{k:v for k,v in c['context'].items() if k in ('message','draft','recent_dialogue')},'output':c['response'],'usage':c['usage'],'status':c['status']}
            elif sk=='discovery':
                c=db.execute('''SELECT output,usage,status,issue FROM data_model_discoveries WHERE business_id=%s AND analysis_id=%s AND call_key=%s AND attempt=%s''',
                             (business,source['analysis_id'],source['call_key'],source['attempt'])).fetchone()
                if c: content['discovery']=c
            events=db.execute('SELECT id,sequence,type,status,payload,occurred_at,recorded_at,reconstructed FROM activity_events WHERE business_id=%s AND trace_id=%s AND task_id=%s ORDER BY sequence DESC LIMIT 20',
                             (business,trace,task['id'])).fetchall()
            content['events']=list(reversed(events))
            return bounded(content)
        if kind in ('calls','executions'):
            source_kind='call' if kind=='calls' else 'execution'
            task=db.execute("SELECT id FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND source->>'kind'=%s AND source->>'id'=%s",(business,trace,source_kind,str(identifier(object_id)))).fetchone()
            if not task: raise WebError('Registro no encontrado en este proceso.',404)
            return detail(ws,trace_id,'tasks',str(task['id']),event_id=event_id)
        raise WebError('Detalle interno no encontrado.',404)
