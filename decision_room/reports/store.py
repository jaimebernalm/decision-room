"""HTML-only gradual registry. No legacy backfill, parsing or publication consent."""
from uuid import UUID

from psycopg.types.json import Jsonb

from ..database import connect
from ..engine import admission
from ..memory import context, service as memory


def capture(db, business, analysis, run, tables):
    """Freeze dependencies at run creation; never retrofit an active run."""
    from ..data_knowledge import service as knowledge
    selection = dict(analysis_id=str(analysis), source_ids=[str(r['id']) for r in db.execute(
        'SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s', (business, analysis)).fetchall()],
        period=context.period())
    db.execute('''INSERT INTO engine_report_contexts
        (run_id,business_id,selection,memories,data_models,table_versions) VALUES (%s,%s,%s,%s,%s,%s)''',
        (run, business, Jsonb(selection), Jsonb(context.scoped(context.effective(db, business), selection)),
         Jsonb(knowledge.heads(db, business, analysis)),
         Jsonb({r['id']: context.table_version(db, business, r['id']) for r in tables})))


def lock(db, document, *, shared=False):
    """Order for HTML operations: memory head, document, then mutable rows."""
    key = 'engine-report:' + str(UUID(str(document)))
    fn = 'pg_advisory_xact_lock_shared' if shared else 'pg_advisory_xact_lock'
    db.execute('SELECT ' + fn + '(hashtextextended(%s,33))', (key,))


def adopt(config, business, run):
    """Idempotently register every receipt and publish only a terminal delivered head.

    Bytes have already committed in the engine. Adoption never reconstructs them
    from HTML or invents approval. Historical F0 runs lack dependency provenance
    and remain non-current until a new analysis is explicitly created.
    """
    business, run = UUID(str(business)), UUID(str(run))
    with connect(config) as db, db.transaction():
        source = db.execute('''SELECT d.id,r.analysis_id,r.status,r.profile FROM engine_documents d
            JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.run_id
            WHERE d.business_id=%s AND d.run_id=%s''', (business, run)).fetchone()
        if not source:
            return None
        memory.lock(db, business)
        document = source['id']; lock(db, document)
        db.execute('''INSERT INTO report_documents(id,business_id,analysis_id,origin,source_run_id)
            VALUES (%s,%s,%s,'engine_html',%s) ON CONFLICT(id) DO NOTHING''',
            (document, business, source['analysis_id'], run))
        revisions = db.execute('''SELECT * FROM engine_document_revisions
            WHERE business_id=%s AND document_id=%s ORDER BY ordinal''', (business, document)).fetchall()
        for row in revisions:
            raw = bytes(row['raw'])
            if admission.sha(raw) != row['raw_sha256']:
                raise ValueError('Report receipt failed its integrity check.')
            db.execute('''INSERT INTO report_document_revisions
                (id,business_id,document_id,ordinal,raw_sha256,raw_bytes,profile_version,
                 presentation_state,verification_state,derived_version,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'not_evaluated','not_requested',0,%s)
                ON CONFLICT(id) DO NOTHING''',
                (row['id'], business, document, row['ordinal'], row['raw_sha256'], len(raw),
                 source['profile']['version'], row['created_at']))
        baseline = db.execute('SELECT 1 FROM engine_report_contexts WHERE run_id=%s AND business_id=%s', (run,business)).fetchone()
        if not baseline:
            db.execute("UPDATE report_documents SET stale_reason=coalesce(stale_reason,'missing_context') WHERE id=%s", (document,))
        if revisions and source['status'] == 'delivered' and revisions[-1]['raw'] and baseline:
            db.execute('''UPDATE report_documents SET current_revision_id=%s
                WHERE id=%s AND business_id=%s AND stale_reason IS NULL''', (revisions[-1]['id'], document, business))
        # This link is metadata only. It never grants content access or replaces a review.
        db.execute('''UPDATE web_jobs SET report_document_id=%s
            WHERE business_id=%s AND engine_run_id=%s AND engine_kind='opencode'
            AND (report_document_id IS NULL OR report_document_id=%s)''', (document,business,run,document))
        return document
