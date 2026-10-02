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
