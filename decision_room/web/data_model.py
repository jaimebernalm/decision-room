"""Owner model of the data: exact document used by the agents, not a separate diagram."""
from ..database import connect
from ..data_knowledge import service
from .dossier import guard, available
from .errors import WebError, identifier


def read(ws, analysis, revision=None):
    business=ws.business_id()
    analysis=identifier(analysis)
    if not business:
        raise WebError('Selecciona un negocio.',409)
    with connect(ws.config) as db:
        if not db.execute('SELECT 1 FROM analyses WHERE id=%s AND business_id=%s',(analysis,business)).fetchone():
            raise WebError('Conjunto no encontrado.',404)
        row=service.latest(db,business,analysis,revision)
        if revision is not None and not row:
            raise WebError('Revisión no encontrada.',404)
        history=db.execute('''SELECT revision,reason,created_at FROM data_model_revisions
            WHERE business_id=%s AND analysis_id=%s ORDER BY revision DESC''',(business,analysis)).fetchall()
        needs_refresh = bool(row and revision is None and not service.current(db,business,{'analysis_id':str(analysis),'revision':row['revision']}))
        return dict(model=row,history=history,editable=available(db,business,analysis),needs_refresh=needs_refresh,
                    affected_reports=db.execute('''SELECT s.id AS session_id,r.id AS review_id,r.status,r.issue
                        FROM agent_sessions s JOIN agent_reviews r ON r.session_id=s.id
                        WHERE s.business_id=%s AND s.analysis_id=%s AND r.status='stale' ''',(business,analysis)).fetchall())


def change(ws, data):
    business=guard(ws,data)
    analysis=identifier(data.get('analysis_id'))
    with connect(ws.config) as db:
        if not available(db,business,analysis):
            raise WebError('Esta versión no está disponible para editar.',409)
    try:
        if data.get('action')=='prepare':
            service.ensure(ws.config,business,analysis)
        else:
            service.change(ws.config,business,analysis,data.get('expected_revision'),data.get('action'),data.get('payload'))
    except (ValueError,TypeError,KeyError) as error:
        raise WebError(str(error) if isinstance(error,ValueError) else 'Revisa los campos del modelo de datos.',409) from None
    return read(ws,analysis)
