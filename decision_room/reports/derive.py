"""Offline report derivatives. Reads never render and failures never restart a model."""
from contextlib import contextmanager
import logging
from uuid import UUID

from ..database import connect
from . import derivative_store as ds, derive_policy as policy, inventory, store
from .render_browser import Renderer, validate_snapshot

LOG = logging.getLogger(__name__)
ISSUE = 'No podemos preparar la vista de esta revisión. Conservamos el HTML original.'


def derived(db, business, document_id, revision_id):
    """Exact policy/image/revision read only; caller still holds owner access guards."""
    row = ds.result(db, business, document_id, revision_id)
    if row:
        return {k: row[k] for k in ('status','raw_sha256','policy_version','renderer_version','derived_version',
            'canonical_text','canonical_sha256','inventory_sha256','snapshot_html','issue')}
    return None


@contextmanager
def _slot(config):
    """One browser container across app workers, in addition to each job's lock."""
    with connect(config) as db:
        acquired = db.execute('SELECT pg_try_advisory_lock(87120946) AS locked').fetchone()['locked']
        try:
            yield acquired
        finally:
            if acquired: db.execute('SELECT pg_advisory_unlock(87120946)')


def derive(config, business, document_id, revision_id, *, renderer=None, inspector=None):
    """Derive a queued revision, preserving raw bytes even when rendering fails.

    renderer/inspector are internal dependency injection for offline tests; never
    report fields or a web endpoint. No database transaction spans Chrome.
    """
    business, document_id, revision_id = map(lambda v:UUID(str(v)), (business,document_id,revision_id))
    with connect(config) as db, db.transaction():
        ds.source(db,business,document_id,revision_id)  # reject foreign identity before any write
        saved=derived(db,business,document_id,revision_id)
        if saved: return saved
        ds.enqueue(db,business,document_id,revision_id)
        job=db.execute('''SELECT * FROM report_derivation_jobs WHERE business_id=%s AND document_id=%s
            AND revision_id=%s AND policy_version=%s AND renderer_version=%s''',
            (business,document_id,revision_id,policy.POLICY_VERSION,policy.renderer_version())).fetchone()
    if renderer is None and policy.renderer_version().endswith(':unconfigured'):
        return dict(status='pending', canonical_text=None, snapshot_html=None, issue=None)
    with _slot(config) as available:
        if not available: return dict(status='pending', canonical_text=None, snapshot_html=None, issue=None)
        with ds.claim(config,job['id']) as claimed:
            if claimed is None:
                with connect(config) as db:
                    return derived(db,business,document_id,revision_id) or dict(status='pending',canonical_text=None,snapshot_html=None,issue=None)
            if inspector is None:
                from .presentation import inspect
                inspector=inspect
            with connect(config) as db, db.transaction():
                source=ds.source(db,business,document_id,revision_id,writing=True)
                check=inspector(source['raw'])
                ds.set_presentation(db,business,document_id,revision_id,claimed['raw_sha256'],check['state'],check['reason'])
                document=db.execute('SELECT * FROM report_documents WHERE business_id=%s AND id=%s',(business,document_id)).fetchone()
                # A content-generation event, not a metadata read. Stale content
                # stays historical; this never mutates the run's frozen inputs.
                store.retire(db,document,config=config,deep=True)
                deleted=bool(source['deleted_at'] or source['job_deleted_at'])
            output=None
            try:
                if deleted: raise ValueError('Deleted report cannot start a render.')
                source['raw'].decode('utf-8',errors='strict')
                if not source['raw']: raise ValueError('Empty report has no canonical text.')
                output=(renderer or Renderer()).render(source['raw'],claimed['id'])
                rendered=inventory.validate(output['inventory'])
                if rendered['source_sha256'] != source['raw_sha256']:
                    raise ValueError('Renderer returned another source.')
                validate_snapshot(output['snapshot_html'])
            except Exception:
                # Logs stay private; the agent/chat/owner receives only ISSUE.
                LOG.exception('Contained report derivation failed for job %s',claimed['id'])
                output=None
            with connect(config) as db, db.transaction():
                # Revalidate identity under locks. A deletion while Chrome ran
                # prevents exposure; the successful local artifact is discarded.
                current=ds.source(db,business,document_id,revision_id,writing=True)
                if current['deleted_at'] or current['job_deleted_at']: output=None
                if output is None:
                    ds.publish(db,claimed,status='failed',issue=ISSUE)
                else:
                    ds.publish(db,claimed,status='ready',inventory=output['inventory'],snapshot_html=output['snapshot_html'])
                return derived(db,business,document_id,revision_id)


def refresh(config):
    """New deployments enqueue their own key; old image results remain historical."""
    with connect(config) as db, db.transaction():
        candidates=db.execute('''SELECT r.business_id,r.document_id,r.id FROM report_document_revisions r
            JOIN report_documents d ON d.business_id=r.business_id AND d.id=r.document_id
            LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id
            WHERE d.deleted_at IS NULL AND w.deleted_at IS NULL AND NOT EXISTS
            (SELECT 1 FROM report_derivation_jobs j WHERE j.business_id=r.business_id AND j.document_id=r.document_id
             AND j.revision_id=r.id AND j.raw_sha256=r.raw_sha256 AND j.policy_version=%s AND j.renderer_version=%s)
            ORDER BY r.created_at LIMIT 16''',(policy.POLICY_VERSION,policy.renderer_version())).fetchall()
        for row in candidates: ds.enqueue(db,row['business_id'],row['document_id'],row['id'])


def work_once(config):
    if policy.renderer_version().endswith(':unconfigured'): return False
    refresh(config)
    with connect(config) as db:
        job=db.execute('''SELECT j.* FROM report_derivation_jobs j JOIN report_documents d
            ON d.business_id=j.business_id AND d.id=j.document_id
            WHERE j.status IN ('pending','running') AND j.policy_version=%s AND j.renderer_version=%s
            AND d.deleted_at IS NULL ORDER BY j.created_at LIMIT 1''',(policy.POLICY_VERSION,policy.renderer_version())).fetchone()
    if not job: return False
    outcome=derive(config,job['business_id'],job['document_id'],job['revision_id'])
    return outcome['status']!='pending'


def worker(config, stop):
    """Independent of job/controller exceptions and provider work."""
    while not stop.is_set():
        try:
            if work_once(config): continue
        except Exception:
            LOG.exception('Report derivative worker unavailable')
        stop.wait(2)
