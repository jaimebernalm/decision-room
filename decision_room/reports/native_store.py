"""Pure native derivatives, committed with source guards; no Chrome dependency."""
from psycopg.types.json import Jsonb
from ..engine import blocks
from . import derivative_store as ds
POLICY_VERSION = "bloques-escapados-1"


def derive(db, business, document, revision):
    source = ds.source(db, business, document, revision, writing=True)
    existing = result(db, business, document, revision)
    if existing:
        return existing
    try:
        projection = blocks.parse(source['raw'])
        text = blocks.canonical_text(projection)
        inventory = dict(document=projection, text=text, source_sha256=source['raw_sha256'], text_sha256=ds.sha(text.encode()),
                         schema_version=blocks.VERSION, projector_version=blocks.PROJECTOR_VERSION)
        status, state, issue = 'ready', 'allowed', None
        text = inventory['text']; text_hash = inventory['text_sha256']
        inventory_hash = ds.sha(ds.canonical(inventory))
    except blocks.BlocksError:
        inventory = text = text_hash = inventory_hash = None
        status, state, issue = 'failed', 'blocked', 'invalid_native_report'
    identity = (business, document, revision, source['raw_sha256'], POLICY_VERSION)
    db.execute('''INSERT INTO report_presentation_checks
        (business_id,document_id,revision_id,raw_sha256,policy_version,state,reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (*identity, state, issue))
    db.execute('''INSERT INTO report_derivatives
        (business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version,
         derived_version,status,canonical_text,canonical_sha256,inventory,inventory_sha256,issue)
        VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        (*identity, blocks.PROJECTOR_VERSION, status, text, text_hash,
         Jsonb(inventory) if inventory is not None else None, inventory_hash, issue))
    db.execute('''UPDATE report_document_revisions SET presentation_state=%s,presentation_reason=%s,
        policy_version=%s,renderer_version=%s,derived_version=1,derive_status=%s,derive_issue=%s,
        canonical_text=%s,canonical_sha256=%s,inventory_sha256=%s,snapshot_html=NULL
        WHERE business_id=%s AND document_id=%s AND id=%s''',
        (state,issue,POLICY_VERSION,blocks.PROJECTOR_VERSION,status,issue,text,text_hash,inventory_hash,
         business,document,revision))
    return result(db, business, document, revision)


def result(db, business, document, revision):
    row = db.execute('''SELECT x.* FROM report_derivatives x JOIN report_document_revisions r
        ON r.business_id=x.business_id AND r.document_id=x.document_id AND r.id=x.revision_id AND r.raw_sha256=x.raw_sha256
        JOIN report_documents d ON d.id=r.document_id AND d.business_id=r.business_id
        WHERE r.business_id=%s AND r.document_id=%s AND r.id=%s AND d.origin='engine_blocks'
        AND x.policy_version=%s AND x.renderer_version=%s''',
        (business,document,revision,POLICY_VERSION,blocks.PROJECTOR_VERSION)).fetchone()
    if not row: return None
    return {**row, 'document': row['inventory']['document'] if row['status']=='ready' else None,
            'schema_version': blocks.VERSION, 'projector_version': blocks.PROJECTOR_VERSION}
