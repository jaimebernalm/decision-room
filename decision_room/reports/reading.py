"""Business/document/revision guard. Only a trusted raster snapshot is framed."""
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
        if revision is None and row['origin']=='engine_blocks' and row['current_revision_id']:
            revision=row['current_revision_id']
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
        selected['raw'] = bytes(raw['raw'])
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
    return dict(origin=document['origin'],document_id=str(document['id']),revision_id=str(revision['id']),
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


def pdf_unavailable():
    raise WebError('PDF no disponible todavía. Puedes descargar el HTML original.',409)


def derived_for(db, document, revision):
    """The isolated renderer's result for this exact revision, or None. Never renders here."""
    if document['origin'] == 'engine_blocks':
        from .native_store import result
        value=result(db, document['business_id'], document['id'], revision['id'])
        if value and value['status']=='ready':
            from ..engine import native_checks, admission
            checks=native_checks.read(db,document['business_id'],document['source_run_id'],revision['id'])
            value['checks']=checks
            value['check_sha256']=admission.sha(admission.canonical(checks))
            from ..engine import check_contract
            warnings=check_contract.visible(checks)
            value['canonical_text'] += '\nComprobación independiente: '+checks['state']+'\n'+'\n'.join(
                i['message'] if i.get('coverage') else 'Cifra en revisión: '+i['quote']+' — '+i['message']
                for i in warnings['items'])
            value['canonical_sha256']=admission.sha(value['canonical_text'].encode())
        return value
    from .derive import derived
    return derived(db, document['business_id'], document['id'], revision['id'])


def view(db, document, revision):
    if document['origin'] == 'engine_blocks':
        derived = derived_for(db, document, revision)
        if derived and derived['status'] == 'ready':
            from ..engine import native_checks, check_contract
            checks=native_checks.read(db,document['business_id'],document['source_run_id'],revision['id'])
            return dict(mode='blocks', blocks=derived['document'], canonical_text=derived['canonical_text'],
                        checks=check_contract.visible(checks))
        return dict(mode='blocked', reason='invalid_native_report', canonical_text='')
    from . import presentation as policy
    return policy.view(revision['raw'], derived_for(db, document, revision))


def presentation(document, revision, value, view=None):
    """Typed metadata envelope; empty evidence cannot be mistaken for extraction."""
    shown = bool(view and view['mode'] in ('snapshot', 'blocks'))
    summaries = {'current':'' if shown else 'La entrega está guardada. Su presentación todavía no está disponible.',
                 'withdrawn':'Los datos o la memoria aplicable han cambiado. Conservamos esta entrega como histórico.',
                 'historical':'Esta revisión es histórica. Conservamos sus metadatos y su hash.',
                 'incomplete':'La ejecución no completó un informe actual. Conservamos las entregas recibidas.'}
    return dict(origin=document['origin'],engine_report=value,report_id=str(document['id']),report_version=revision['raw_sha256'],
                title=document.get('title') or 'Informe',summary=summaries[value['state']],view=view,
                scope=dict(period='',coverage='',question=document.get('goal') or ''),
                claims=[],highlights=[],charts=[],limitations=[])


CHAT_TEXT_LIMIT = 40000


def chat_version(revision, derived):
    """Exact identity of what the chat read: revision, bytes, canonical text, policy, renderer."""
    return ':'.join(('engine', str(revision['id']), revision['raw_sha256'], derived['canonical_sha256'],
                     derived['policy_version'], derived['renderer_version'])) + (':'+derived['check_sha256'] if derived.get('check_sha256') else '')


def chat_documents(db, business, analysis=None):
    """Current engine reports whose canonical text is ready. Cheap; never renders."""
    rows = db.execute('''SELECT d.*,r.status AS run_status,w.title,w.goal,w.deleted_at AS job_deleted_at
        FROM report_documents d JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.source_run_id
        LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
        WHERE d.business_id=%s AND d.deleted_at IS NULL AND d.current_revision_id IS NOT NULL
        AND (%s::uuid IS NULL OR d.analysis_id=%s) ORDER BY d.created_at DESC,d.id LIMIT 1001''',
        (business, analysis, analysis)).fetchall()
    if len(rows) > 1000:
        raise ValueError('Report corpus exceeds 1000 objects. Narrow the source scope.')
    result = []
    for row in rows:
        item = chat_document(db, business, row['id'])
        if item:
            result.append(item)
    return result


def chat_document(db, business, document_id, *, row=None):
    """Under the same memory -> document(shared) order as owner reads; revalidated each call."""
    document_id = identifier(document_id)
    with db.transaction():
        if not db.execute('SELECT 1 FROM report_documents WHERE business_id=%s AND id=%s', (business, document_id)).fetchone():
            return None
        memory.lock(db, business)
        store.lock(db, document_id, shared=True)
        return _chat_document(db, business, document_id)


def _chat_document(db, business, document_id, *, row=None):
    if row is None:
        row = db.execute('''SELECT d.*,r.status AS run_status,w.title,w.goal,w.deleted_at AS job_deleted_at
            FROM report_documents d JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.source_run_id
            LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
            WHERE d.business_id=%s AND d.id=%s''', (business, document_id)).fetchone()
    if not row or row['deleted_at'] or row['job_deleted_at']:
        return None
    row['stale_reason'] = store.reason(db, row)
    revision = db.execute('''SELECT * FROM report_document_revisions WHERE business_id=%s AND document_id=%s AND id=%s''',
                          (business, row['id'], row['current_revision_id'])).fetchone() if row['current_revision_id'] else None
    if not store.is_current(row, revision, row['run_status']):
        return None
    if revision['presentation_state'] == 'blocked':
        # Blocked receipts keep canonical text for the owner, but the chat does not
        # quote a report whose presentation could not be shown safely.
        return None
    derived = derived_for(db, row, revision)
    if not derived or derived.get('status') != 'ready' or not derived.get('canonical_text'):
        return None
    text = derived['canonical_text']
    return dict(id=str(row['id']), version=chat_version(revision, derived), origin=row['origin'],
                title=row.get('title') or 'Informe', analysis_id=str(row['analysis_id']),
                created_at=revision['created_at'].isoformat(), text=text[:CHAT_TEXT_LIMIT],
                truncated=len(text) > CHAT_TEXT_LIMIT, canonical_sha256=derived['canonical_sha256'])


class RawAttachment(bytes):
    """Raw receipt plus a trusted format; still compared/exported as exact bytes."""
    def __new__(cls, raw, *, native=False):
        value = super().__new__(cls, raw)
        value.native = native
        return value
