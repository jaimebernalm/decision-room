"""Durable render jobs and immutable results, scoped to a source revision.

This module never starts a browser. Raw receipts, run completion, visibility and
render completion are separate records. All writers use memory -> document locks.
"""
from contextlib import contextmanager
import hashlib
import json
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from ..memory import service as memory
from . import derive_policy as policy, store


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def source(db, business, document, revision, *, writing=False):
    business, document, revision = map(lambda v: UUID(str(v)), (business, document, revision))
    if writing:
        memory.lock(db, business)
        store.lock(db, document)
    row = db.execute('''SELECT r.*,s.raw,d.deleted_at,d.source_run_id,w.deleted_at AS job_deleted_at
        FROM report_document_revisions r JOIN report_documents d ON d.business_id=r.business_id AND d.id=r.document_id
        JOIN engine_document_revisions s ON s.business_id=r.business_id AND s.document_id=r.document_id AND s.id=r.id
        LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id
        WHERE r.business_id=%s AND r.document_id=%s AND r.id=%s''', (business, document, revision)).fetchone()
    if not row:
        raise ValueError('Report revision does not belong to this business and document.')
    raw = bytes(row['raw'])
    if len(raw) != row['raw_bytes'] or sha(raw) != row['raw_sha256']:
        raise ValueError('Report revision failed its source integrity check.')
    row['raw'] = raw
    return row


def enqueue(db, business, document, revision):
    """Called in adoption's transaction; queueing cannot grant publication."""
    row = source(db, business, document, revision)
    db.execute('''INSERT INTO report_derivation_jobs
        (id,business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        (uuid4(), business, document, revision, row['raw_sha256'], policy.POLICY_VERSION, policy.renderer_version()))


def set_presentation(db, business, document, revision, raw_sha256, state, reason, *, policy_version=None):
    policy_version = policy.POLICY_VERSION if policy_version is None else policy_version
    row = source(db, business, document, revision, writing=True)
    if row['raw_sha256'] != raw_sha256 or policy_version != policy.POLICY_VERSION or state not in ('allowed', 'blocked'):
        raise ValueError('Presentation assessment identity differs.')
    if reason is not None and (not isinstance(reason, str) or len(reason)>256):
        raise ValueError('Presentation reason must be a bounded neutral message.')
    identity = (business, document, revision, raw_sha256, policy_version)
    db.execute('''INSERT INTO report_presentation_checks
        (business_id,document_id,revision_id,raw_sha256,policy_version,state,reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''', (*identity, state, reason))
    saved = db.execute('''SELECT state,reason FROM report_presentation_checks WHERE
        business_id=%s AND document_id=%s AND revision_id=%s AND raw_sha256=%s AND policy_version=%s''', identity).fetchone()
    if (saved['state'], saved['reason']) != (state, reason):
        raise ValueError('A presentation policy cannot change its assessment for the same source.')
    # A future policy may require a new renderer projection. Never silently attach
    # an old result to that policy; this F4 setter only accepts the current policy.
    if (row['policy_version'],row['renderer_version']) != (policy_version,policy.renderer_version()):
        db.execute('''UPDATE report_document_revisions SET presentation_state=%s,presentation_reason=%s,policy_version=%s,
            renderer_version=%s,derived_version=0,derive_status='pending',derive_issue=NULL,canonical_text=NULL,
            canonical_sha256=NULL,inventory_sha256=NULL,snapshot_html=NULL
            WHERE business_id=%s AND document_id=%s AND id=%s''',
            (state,reason,policy_version,policy.renderer_version(),business,document,revision))
    else:
        db.execute('''UPDATE report_document_revisions SET presentation_state=%s,presentation_reason=%s
            WHERE business_id=%s AND document_id=%s AND id=%s''', (state,reason,business,document,revision))


def result(db, business, document, revision):
    """Cheap scoped read; no filesystem probes, source digest or rendering."""
    return db.execute('''SELECT x.* FROM report_document_revisions r JOIN report_derivatives x
        ON x.business_id=r.business_id AND x.document_id=r.document_id AND x.revision_id=r.id AND x.raw_sha256=r.raw_sha256
        JOIN report_documents d ON d.business_id=r.business_id AND d.id=r.document_id
        WHERE r.business_id=%s AND r.document_id=%s AND r.id=%s AND x.policy_version=%s AND x.renderer_version=%s''',
        (business, document, revision, policy.POLICY_VERSION, policy.renderer_version())).fetchone()


@contextmanager
def claim(config, job_id):
    """Session lock survives commits; death releases it, enabling exact recovery.

    No lease expiry can let a second healthy worker execute the same HTML. The
    controller's container uses this exact job ID and is cleaned on recovery.
    """
    job_id = UUID(str(job_id))
    with connect(config) as db:
        key = 'report-derive:' + str(job_id)
        if not db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,36)) AS locked', (key,)).fetchone()['locked']:
            yield None
            return
        try:
            with db.transaction():
                job = db.execute('SELECT * FROM report_derivation_jobs WHERE id=%s FOR UPDATE', (job_id,)).fetchone()
                if not job or job['status'] in ('ready', 'failed'):
                    job = None
                elif job['policy_version'] != policy.POLICY_VERSION or job['renderer_version'] != policy.renderer_version():
                    job = None
                else:
                    job = db.execute('''UPDATE report_derivation_jobs SET status='running',claim_id=%s,
                        attempts=attempts+1,started_at=clock_timestamp() WHERE id=%s RETURNING *''', (uuid4(),job_id)).fetchone()
            yield job
        finally:
            db.execute('SELECT pg_advisory_unlock(hashtextextended(%s,36))', (key,))


def publish(db, job, *, status, inventory=None, snapshot_html=None, issue=None):
    """One terminal receipt per key, followed by its projection, in one transaction."""
    row = source(db, job['business_id'], job['document_id'], job['revision_id'], writing=True)
    if row['raw_sha256'] != job['raw_sha256']:
        raise ValueError('Derivative source identity differs.')
    if status not in ('ready', 'failed') or (job['policy_version'],job['renderer_version']) != (policy.POLICY_VERSION,policy.renderer_version()):
        raise ValueError('Derivative contract differs.')
    text = text_hash = inventory_hash = None
    if status == 'ready':
        if not isinstance(inventory,dict) or not isinstance(inventory.get('text'),str):
            raise ValueError('Missing canonical inventory.')
        text = inventory['text']; text_hash = sha(text.encode())
        if len(text)>policy.MAX_TEXT or inventory.get('source_sha256') != job['raw_sha256'] or inventory.get('text_sha256') != text_hash:
            raise ValueError('Canonical inventory identity differs.')
        encoded = canonical(inventory)
        if len(encoded)>policy.MAX_INVENTORY_BYTES:
            raise ValueError('Inventory exceeds its bound.')
        inventory_hash = sha(encoded)
        if snapshot_html is not None and (not isinstance(snapshot_html,str) or len(snapshot_html.encode())>policy.MAX_SNAPSHOT_BYTES):
            raise ValueError('Snapshot exceeds its bound.')
        if issue is not None:
            raise ValueError('A ready derivative cannot carry an error.')
    elif inventory is not None or snapshot_html is not None or not isinstance(issue,str) or not 1<=len(issue)<=256:
        raise ValueError('Failed derivatives cannot contain partial content.')
    identity = (job['business_id'],job['document_id'],job['revision_id'],job['raw_sha256'],job['policy_version'],job['renderer_version'])
    values = dict(derived_version=policy.DERIVED_VERSION,status=status,canonical_text=text,canonical_sha256=text_hash,
                  inventory=inventory,inventory_sha256=inventory_hash,snapshot_html=snapshot_html,issue=issue)
    db.execute('''INSERT INTO report_derivatives (business_id,document_id,revision_id,raw_sha256,policy_version,renderer_version,
        derived_version,status,canonical_text,canonical_sha256,inventory,inventory_sha256,snapshot_html,issue)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
        (*identity, policy.DERIVED_VERSION,status,text,text_hash,Jsonb(inventory) if inventory is not None else None,inventory_hash,snapshot_html,issue))
    saved = result(db, *identity[:3])
    if any(saved[k] != value for k,value in values.items()):
        raise ValueError('A renderer cannot rewrite the immutable derivative for this key.')
    # The claim is a fencing token: a dead worker cannot overwrite a recovered one.
    updated = db.execute('''UPDATE report_derivation_jobs SET status=%s,finished_at=clock_timestamp()
        WHERE id=%s AND claim_id=%s AND status='running' ''', (status,job['id'],job['claim_id']))
    if updated.rowcount != 1:
        raise ValueError('Render claim is no longer owned by this worker.')
    db.execute('''UPDATE report_document_revisions SET derived_version=%s,derive_status=%s,derive_issue=%s,
        canonical_text=%s,canonical_sha256=%s,inventory_sha256=%s,snapshot_html=%s,policy_version=%s,renderer_version=%s
        WHERE business_id=%s AND document_id=%s AND id=%s''',
        (policy.DERIVED_VERSION,status,issue,text,text_hash,inventory_hash,snapshot_html,policy.POLICY_VERSION,policy.renderer_version(),*identity[:3]))
    return saved
