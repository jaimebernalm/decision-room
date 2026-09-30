"""Authenticated client activity reads pinned to the selected business."""
from ..database import connect
from ..observability import store,projection
from .errors import WebError,identifier


def read(ws,kind,source_id,query,*,chat_id=None):
    business=ws.business_id();source_id=identifier(source_id)
    with connect(ws.config) as db:
        if kind=='job':
            record=db.execute('SELECT id FROM web_jobs WHERE business_id=%s AND id=%s AND deleted_at IS NULL',(business,source_id)).fetchone()
        else:
            record=db.execute('''SELECT t.id FROM chat_turns t JOIN chat_conversations c ON c.id=t.conversation_id AND c.business_id=t.business_id
                WHERE t.business_id=%s AND t.id=%s AND c.id=%s AND c.deleted_at IS NULL''',(business,source_id,identifier(chat_id))).fetchone()
        if not record: raise WebError('Proceso no encontrado en este negocio.',404)
        trace=store.linked(db,business,kind,source_id)
        if not trace:
            return dict(schema_version=1,trace_id=None,status='historical',headline='Historial detallado no disponible para este análisis',
                terminal=True,publishable=False,task_updates=[],active_tasks=[],events=[],next_cursor=None,has_more=False,
                previous_cursor=None,history_complete=False,worker_health='unknown')
        endpoint=f'/api/jobs/{source_id}/data' if kind=='job' else None
        if kind=='turn':
            j=db.execute("SELECT source_id FROM activity_links WHERE business_id=%s AND trace_id=%s AND kind='job' LIMIT 1",(business,trace)).fetchone()
            endpoint=f'/api/jobs/{j["source_id"]}/data' if j else None
        return projection.page(db,business,trace,query,data_endpoint=endpoint,config=ws.config)
