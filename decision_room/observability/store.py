"""Short serialized writes give each process a commit-ordered replay cursor."""
import logging
from uuid import UUID, uuid5
from psycopg.types.json import Jsonb

LOG = logging.getLogger(__name__)
STATES = frozenset(('queued','running','waiting_owner','waiting_dependency','retry_wait',
                    'completed','failed','interrupted','superseded'))


def root(db, business, kind, source_id, *, trace_id=None):
    business, source_id = UUID(str(business)), UUID(str(source_id))
    existing = linked(db,business,kind,source_id)
    if existing:
        return existing
    trace_id = UUID(str(trace_id)) if trace_id else uuid5(business, f'activity:{kind}:{source_id}')
    with db.transaction():
        if not db.execute('SELECT 1 FROM activity_traces WHERE business_id=%s AND id=%s',(business,trace_id)).fetchone():
            db.execute('''INSERT INTO activity_traces(id,business_id,origin_kind,origin_id)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(trace_id,business,kind,source_id))
        link(db,business,trace_id,kind,source_id)
    return trace_id


def linked(db,business,kind,source_id):
    row=db.execute('SELECT trace_id FROM activity_links WHERE business_id=%s AND kind=%s AND source_id=%s',
                   (business,kind,source_id)).fetchone()
    return row['trace_id'] if row else None


def link(db,business,trace_id,kind,source_id):
    if not db.execute('SELECT 1 FROM activity_traces WHERE business_id=%s AND id=%s',(business,trace_id)).fetchone():
        raise ValueError('Activity process does not belong to business.')
    db.execute('''INSERT INTO activity_links(business_id,trace_id,kind,source_id)
                  VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',(business,trace_id,kind,source_id))
    if linked(db,business,kind,source_id)!=UUID(str(trace_id)):
        raise ValueError('Activity source already belongs to another process.')


def append(db,business,trace_id,*,kind,source_id,role='system',actor_id=None,
           status,public_text,dedupe_key,event_type=None,parent_id=None,purpose='',refs=(),
           source=None,payload=None,occurred_at=None,reconstructed=False,started_at=None,finished_at=None):
    if status not in STATES:
        raise ValueError('Invalid activity state.')
    business,trace_id=UUID(str(business)),UUID(str(trace_id))
    task_id=uuid5(trace_id,f'{kind}:{source_id}')
    if parent_id==task_id:
        raise ValueError('Activity parent cycle.')
    with db.transaction():
        trace=db.execute('SELECT * FROM activity_traces WHERE business_id=%s AND id=%s FOR UPDATE',
                         (business,trace_id)).fetchone()
        if not trace:
            raise ValueError('Activity process does not belong to business.')
        prior=db.execute('SELECT id FROM activity_events WHERE trace_id=%s AND dedupe_key=%s',
                         (trace_id,dedupe_key)).fetchone()
        if prior:
            return task_id
        if parent_id:
            cursor=parent_id
            seen={task_id}
            while cursor:
                if cursor in seen: raise ValueError('Activity parent cycle.')
                seen.add(cursor)
                parent=db.execute('SELECT parent_task_id FROM activity_tasks WHERE business_id=%s AND trace_id=%s AND id=%s',
                                  (business,trace_id,cursor)).fetchone()
                if not parent: raise ValueError('Activity parent belongs to another process.')
                cursor=parent['parent_task_id']
        sequence=trace['last_sequence']+1
        terminal=status in ('completed','failed','interrupted','superseded')
        db.execute('''INSERT INTO activity_tasks(id,business_id,trace_id,parent_task_id,actor_id,role,kind,source_id,
            status,public_text,purpose,refs,source,started_at,finished_at,last_sequence)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                CASE WHEN %s='queued' THEN NULL ELSE COALESCE(%s,clock_timestamp()) END,
                CASE WHEN %s THEN COALESCE(%s,clock_timestamp()) ELSE NULL END,%s)
            ON CONFLICT (trace_id,kind,source_id) DO UPDATE SET
                status=excluded.status,public_text=excluded.public_text,purpose=excluded.purpose,
                refs=excluded.refs,source=excluded.source,last_sequence=excluded.last_sequence,
                started_at=COALESCE(activity_tasks.started_at,excluded.started_at),
                finished_at=excluded.finished_at,parent_task_id=COALESCE(excluded.parent_task_id,activity_tasks.parent_task_id),
                actor_id=excluded.actor_id,role=excluded.role''',
            (task_id,business,trace_id,parent_id,actor_id or role,role,kind,str(source_id),status,
             public_text[:500],purpose[:500],Jsonb(list(refs)),Jsonb(source or {}),
             status,started_at or occurred_at,terminal,finished_at or occurred_at,sequence))
        db.execute('''INSERT INTO activity_events(id,business_id,trace_id,sequence,task_id,dedupe_key,type,status,payload,occurred_at,reconstructed)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (uuid5(trace_id,dedupe_key),business,trace_id,sequence,task_id,dedupe_key,
             event_type or f'{kind}.{status}',status,Jsonb({**(payload or {}),'activity_text':public_text[:500]}),occurred_at,reconstructed))
        db.execute('UPDATE activity_traces SET last_sequence=%s WHERE id=%s',(sequence,trace_id))
    return task_id


def safe(db,business,trace_id,fn,*args,**kwargs):
    """A savepoint protects domain transactions from a failed observer write."""
    try:
        with db.transaction():
            return fn(db,business,trace_id,*args,**kwargs)
    except Exception:
        LOG.exception('Activity write failed')
        try:
            with db.transaction():
                db.execute('UPDATE activity_traces SET history_complete=false WHERE business_id=%s AND id=%s',
                           (business,trace_id))
        except Exception:
            LOG.exception('Activity health update failed')
        return None
