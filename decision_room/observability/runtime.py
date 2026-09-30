"""Worker-owned capture/heartbeat. Observer context never enters model inputs."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import logging
import threading
from uuid import UUID
from ..database import connect
from . import store,collector

LOG=logging.getLogger(__name__)
CURRENT=ContextVar('activity_process',default=None)
CALL=ContextVar('activity_call',default=None)


def seed(db,business,kind,source_id):
    current=CURRENT.get()
    trace=current[2] if current and str(current[1])==str(business) else store.linked(db,business,kind,source_id)
    if not trace and kind=='job':
        row=db.execute('''SELECT l.trace_id FROM chat_turns t JOIN activity_links l ON l.source_id=t.id AND l.kind='turn' AND l.business_id=t.business_id
                          WHERE t.business_id=%s AND t.job_id=%s LIMIT 1''',(business,source_id)).fetchone()
        trace=row['trace_id'] if row else None
    if not trace and kind=='turn':
        row=db.execute('SELECT job_id FROM chat_turns WHERE business_id=%s AND id=%s',(business,source_id)).fetchone()
        if row and row['job_id']: trace=store.linked(db,business,'job',row['job_id'])
    if not trace and kind=='session':
        row=db.execute('SELECT supersedes_session_id FROM agent_sessions WHERE business_id=%s AND id=%s',(business,source_id)).fetchone()
        if row and row['supersedes_session_id']: trace=store.linked(db,business,'session',row['supersedes_session_id'])
    trace=store.root(db,business,kind,source_id,trace_id=trace)
    if kind=='turn':
        row=db.execute('SELECT job_id FROM chat_turns WHERE business_id=%s AND id=%s',(business,source_id)).fetchone()
        if row and row['job_id']: store.link(db,business,trace,'job',row['job_id'])
    return trace


def notify(db=None):
    current=CURRENT.get()
    if not current: return
    config,business,trace=current
    def run(connection):
        try:
            with connection.transaction():
                collector.reconcile(connection,business,trace)
        except Exception:
            LOG.exception('Activity catch-up failed')
            try:
                with connection.transaction():
                    connection.execute('UPDATE activity_traces SET history_complete=false WHERE business_id=%s AND id=%s',(business,trace))
            except Exception: LOG.exception('Activity catch-up health failed')
    if db is not None: run(db)
    else:
        try:
            with connect(config) as connection: run(connection)
        except Exception: LOG.exception('Activity connection unavailable')


def incomplete(config,business,trace):
    """Best effort health flag if a producer or sampler failed outside a savepoint."""
    try:
        with connect(config) as db:
            db.execute('UPDATE activity_traces SET history_complete=false WHERE business_id=%s AND id=%s',(business,trace))
    except Exception: LOG.exception('Activity health unavailable')


@contextmanager
def capture(config,business,kind,source_id,*,db=None):
    try:
        if db is None:
            with connect(config) as own: trace=seed(own,business,kind,source_id)
        else: trace=seed(db,business,kind,source_id)
    except Exception:
        LOG.exception('Activity capture unavailable')
        yield
        return
    old=CURRENT.get();token=CURRENT.set((config,business,trace))
    stop=threading.Event();thread=None
    if not old:
        def sample():
            while not stop.is_set():
                try:
                    with connect(config) as connection:
                        connection.execute('UPDATE activity_traces SET heartbeat_at=clock_timestamp(),worker_active=true WHERE business_id=%s AND id=%s',(business,trace))
                        # Catch-up is worker-owned, never an HTTP GET side effect.
                        with connection.transaction(): collector.reconcile(connection,business,trace)
                except Exception:
                    LOG.exception('Activity sampler failed');incomplete(config,business,trace)
                stop.wait(1)
        thread=threading.Thread(target=sample,name='activity-worker-sampler',daemon=True);thread.start()
    notify(db)
    try: yield
    finally:
        notify(db)
        if thread:
            stop.set();thread.join(3)
            try:
                with connect(config) as connection:
                    connection.execute('UPDATE activity_traces SET heartbeat_at=clock_timestamp(),worker_active=false WHERE business_id=%s AND id=%s',(business,trace))
            except Exception: LOG.exception('Activity heartbeat cleanup failed')
        CURRENT.reset(token)


def created(kind):
    def decorate(fn):
        @wraps(fn)
        def wrapped(self,*args,**kwargs):
            result=fn(self,*args,**kwargs)
            if isinstance(result,dict) and result.get('id'):
                try:
                    business=self.business if kind=='turn' else self.row(result['id'])['business_id']
                    with connect(self.config) as db:
                        trace=seed(db,business,kind,result['id'])
                        with db.transaction(): collector.reconcile(db,business,trace)
                except Exception: LOG.exception('Activity creation catch-up failed')
            return result
        return wrapped
    return decorate


def tracked(kind):
    def decorate(fn):
        @wraps(fn)
        def wrapped(self,source_id,*args,**kwargs):
            business=self.business if kind=='turn' else self.row(source_id)['business_id']
            with capture(self.config,business,kind,source_id):
                return fn(self,source_id,*args,**kwargs)
        return wrapped
    return decorate


def session_tracked(fn):
    @wraps(fn)
    def wrapped(config,db,session,*args,**kwargs):
        with capture(config,session['business_id'],'session',session['id'],db=db):
            return fn(config,db,session,*args,**kwargs)
    return wrapped


@contextmanager
def call_context(call_id):
    token=CALL.set(str(call_id))
    try: yield
    finally: CALL.reset(token)


def transport(attempts):
    current=CURRENT.get();call=CALL.get()
    if not current or not call: return
    config,business,trace=current
    try:
        with connect(config) as db:
            for number,attempt in enumerate(attempts):
                waiting=bool(attempt.get('retry_delay_seconds')) and number==len(attempts)-1
                state='retry_wait' if waiting else 'completed'
                collector.emit(db,business,trace,'transport',f'{call}:{number}',state,
                    'Esperando al proveedor antes de reintentar' if waiting else 'Petición al proveedor registrada',
                    role='transport',source={'kind':'transport','call_id':call,'attempt':number},payload=attempt,
                    event_type='provider.retry_wait' if waiting else 'provider.response')
    except Exception:
        LOG.exception('Activity transport capture failed');incomplete(config,business,trace)


def reused(db,kind,source_id):
    """A durable reuse marker; replay of the marker itself is idempotent."""
    current=CURRENT.get()
    if not current: return
    _,business,trace=current
    store.safe(db,business,trace,collector.emit,'reuse',f'{kind}:{source_id}','completed',
        'Resultado guardado reutilizado',source={'kind':kind,'id':str(source_id)},event_type='result.reused')


def reconcile_pending(config):
    """One explicit startup/maintenance pass, including terminal and legacy jobs."""
    with connect(config) as db:
        rows=db.execute('''SELECT id,business_id FROM web_jobs WHERE deleted_at IS NULL
                          UNION ALL SELECT id,business_id FROM chat_turns''').fetchall()
        for row in rows:
            kind='job' if db.execute('SELECT 1 FROM web_jobs WHERE id=%s',(row['id'],)).fetchone() else 'turn'
            try:
                trace=seed(db,row['business_id'],kind,row['id'])
                with db.transaction(): collector.reconcile(db,row['business_id'],trace,reconstructed=True)
            except Exception: LOG.exception('Activity startup reconciliation failed')
