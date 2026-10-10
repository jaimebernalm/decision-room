"""Business/document/revision guard and metadata-only HTML read model."""
from contextlib import contextmanager

from ..database import connect
from ..memory import service as memory
from ..web.errors import WebError, identifier
from . import store


@contextmanager
def read(config, business, document, *, revision=None, deleted=False):
    business, document = identifier(business), identifier(document)
    revision = identifier(revision) if revision is not None else None
    with connect(config) as db, db.transaction():
        # Resolve before acquiring authority locks; a run credential is not accepted.
        scoped = db.execute('SELECT 1 FROM report_documents WHERE business_id=%s AND id=%s', (business,document)).fetchone()
        if not scoped:
            raise WebError('Informe no encontrado.',404)
        memory.lock(db,business)
        store.lock(db,document,shared=True)
        row = db.execute('''SELECT d.*,r.status AS run_status,r.snapshot,r.prompt_sha256,r.input_sha256,
            w.id AS job_id,w.title,w.goal,w.deleted_at AS job_deleted_at
            FROM report_documents d JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.source_run_id
            LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
            WHERE d.business_id=%s AND d.id=%s''', (business,document)).fetchone()
        if not row or not deleted and (row['deleted_at'] or row['job_deleted_at']):
            raise WebError('Informe no encontrado.',404)
        row['stale_reason'] = store.reason(db,row,config=config)
        params = [business,document]
        where = ''
        if revision:
            where = ' AND id=%s'; params.append(revision)
        selected = db.execute('SELECT * FROM report_document_revisions WHERE business_id=%s AND document_id=%s' +
                              where + ' ORDER BY ordinal DESC LIMIT 1', params).fetchone()
        if not selected:
            raise WebError('Revisión no encontrada.',404)
        # Recheck raw provenance under the same document/revision scope.
        raw = db.execute('''SELECT raw,raw_sha256,delivery_via FROM engine_document_revisions
            WHERE business_id=%s AND document_id=%s AND id=%s''', (business,document,selected['id'])).fetchone()
        if not raw or store.admission.sha(bytes(raw['raw'])) != selected['raw_sha256'] or raw['raw_sha256'] != selected['raw_sha256']:
            raise WebError('No podemos recuperar la integridad de esta revisión.',409)
        selected['delivery_via'] = raw['delivery_via']
        yield db,row,selected


def metadata(db, document, revision, *, history=True):
    current = store.is_current(document,revision,document['run_status'])
    state = ('incomplete' if document['run_status']!='delivered' or not revision['raw_bytes'] else
             'withdrawn' if document['stale_reason'] else 'current' if current else
             'historical' if document['current_revision_id'] else 'incomplete')
    history = db.execute('''SELECT r.id,r.ordinal,r.raw_sha256,r.raw_bytes,r.created_at,s.delivery_via
        FROM report_document_revisions r JOIN engine_document_revisions s
        ON s.business_id=r.business_id AND s.document_id=r.document_id AND s.id=r.id
        WHERE r.business_id=%s AND r.document_id=%s ORDER BY r.ordinal''',
        (document['business_id'],document['id'])).fetchall() if history else []
    return dict(origin='engine_html',document_id=str(document['id']),revision_id=str(revision['id']),
                business_id=str(document['business_id']),analysis_id=str(document['analysis_id']),
                source_run_id=str(document['source_run_id']),raw_sha256=revision['raw_sha256'],raw_bytes=revision['raw_bytes'],
                profile_version=revision['profile_version'],presentation_state=revision['presentation_state'],
                verification_state=revision['verification_state'],derived_version=revision['derived_version'],
                canonical_sha256=revision['canonical_sha256'],run_status=document['run_status'],state=state,
                is_current=current,stale_reason=document['stale_reason'],deleted=bool(document['deleted_at'] or document.get('job_deleted_at')),
                delivery_via=revision['delivery_via'],prompt_sha256=document['prompt_sha256'],input_sha256=document['input_sha256'],
                history=[{**r,'id':str(r['id'])} for r in history])


def blocked_content():
    raise WebError('La presentación de este informe todavía no está disponible. Conservamos su entrega y sus metadatos.',409)


def presentation(document, revision, value):
    """Typed metadata envelope; empty evidence cannot be mistaken for extraction."""
    summaries = {'current':'La entrega está guardada. Su presentación todavía no está disponible.',
                 'withdrawn':'Los datos o la memoria aplicable han cambiado. Conservamos esta entrega como histórico.',
                 'historical':'Esta revisión es histórica. Conservamos sus metadatos y su hash.',
                 'incomplete':'La ejecución no completó un informe actual. Conservamos las entregas recibidas.'}
    return dict(origin='engine_html',engine_report=value,report_id=str(document['id']),report_version=revision['raw_sha256'],
                title=document.get('title') or 'Informe',summary=summaries[value['state']],
                scope=dict(period='',coverage='',question=document.get('goal') or ''),
                claims=[],highlights=[],charts=[],limitations=[])
