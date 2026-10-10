"""Concurrent report readers share the parent lock; analytical writers stay exclusive."""
from contextlib import contextmanager
from ..database import connect
from .errors import WebError, identifier


@contextmanager
def read_lock(config, business_id, session_id):
    session = identifier(session_id)
    with connect(config) as db:
        row = db.execute('SELECT * FROM agent_sessions WHERE business_id=%s AND id=%s', (business_id,session)).fetchone()
        if not row:
            raise WebError('El análisis no pertenece a este negocio.',404)
        key = int.from_bytes(session.bytes[:8], 'big', signed=True)
        if not db.execute('SELECT pg_try_advisory_lock_shared(%s) AS locked', (key,)).fetchone()['locked']:
            raise WebError('El análisis se está actualizando. Vuelve a abrir el informe cuando termine.',409)
        try:
            yield db, row
        finally:
            db.execute('SELECT pg_advisory_unlock_shared(%s)', (key,))


@contextmanager
def read_job(workspace, job_id, *, revision=None, deleted=False):
    """Common dispatch, preserving legacy parent coordination and identifiers."""
    job = workspace.row(job_id)
    if job['engine_kind']=='opencode':
        if not deleted and job['deleted_at']:
            raise WebError('Informe no encontrado.',404)
        if not job['report_document_id']:
            raise WebError('El informe todavía no tiene una entrega registrada.',409)
        from ..reports.reading import read
        with read(workspace.config,job['business_id'],job['report_document_id'],revision=revision,deleted=deleted) as (db,doc,version):
            if doc['job_id'] != job['id'] or doc['source_run_id'] != job['engine_run_id'] or doc['analysis_id'] != job['analysis_id']:
                raise WebError('Informe no encontrado.',404)
            yield db,job,(doc,version)
    else:
        if revision is not None:
            raise WebError('La revisión solicitada no pertenece a este informe.',404)
        if not job['session_id']:
            raise WebError('El informe todavía no está disponible.',409)
        with read_lock(workspace.config,job['business_id'],job['session_id']) as (db,_):
            yield db,job,None
