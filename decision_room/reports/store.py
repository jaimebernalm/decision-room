"""Gradual HTML/native registry. No legacy backfill, parsing or publication consent."""
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
        native = source['profile'].get('format') == 'blocks'
        origin = 'engine_blocks' if native else 'engine_html'
        db.execute('''INSERT INTO report_documents(id,business_id,analysis_id,origin,source_run_id)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',
            (document, business, source['analysis_id'], origin, run))
        revisions = db.execute('''SELECT * FROM engine_document_revisions
            WHERE business_id=%s AND document_id=%s ORDER BY ordinal''', (business, document)).fetchall()
        added = False
        for row in revisions:
            raw = bytes(row['raw'])
            if admission.sha(raw) != row['raw_sha256']:
                raise ValueError('Report receipt failed its integrity check.')
            inserted = db.execute('''INSERT INTO report_document_revisions
                (id,business_id,document_id,ordinal,raw_sha256,raw_bytes,profile_version,
                 presentation_state,verification_state,derived_version,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'not_evaluated','not_requested',0,%s)
                ON CONFLICT(id) DO NOTHING''',
                (row['id'], business, document, row['ordinal'], row['raw_sha256'], len(raw),
                 source['profile']['version'], row['created_at']))
            added = added or inserted.rowcount > 0
            # Durable work only; adoption/metadata requests never launch Chrome.
            if native:
                from .native_store import derive
                derive(db, business, document, row['id'])
            else:
                from .derivative_store import enqueue
                enqueue(db, business, document, row['id'])
        registered = db.execute('SELECT * FROM report_documents WHERE id=%s', (document,)).fetchone()
        if added:
            retire(db,registered,config=config,deep=True)
        baseline = db.execute('SELECT 1 FROM engine_report_contexts WHERE run_id=%s AND business_id=%s', (run,business)).fetchone()
        if not baseline:
            db.execute("UPDATE report_documents SET stale_reason=coalesce(stale_reason,'missing_context') WHERE id=%s", (document,))
        if not native and revisions and source['status'] == 'delivered' and revisions[-1]['raw'] and baseline:
            db.execute('''UPDATE report_documents SET current_revision_id=%s
                WHERE id=%s AND business_id=%s AND stale_reason IS NULL''', (revisions[-1]['id'], document, business))
        if native and source['status'] == 'delivered' and baseline:
            chosen=db.execute("SELECT selected_revision_id FROM engine_native_cycles WHERE business_id=%s AND run_id=%s AND stage IN ('complete','incomplete') AND selected_revision_id IS NOT NULL",(business,run)).fetchone()
            if chosen:
                checked=db.execute("SELECT 1 FROM report_document_revisions WHERE business_id=%s AND document_id=%s AND id=%s AND derive_status='ready'",(business,document,chosen['selected_revision_id'])).fetchone()
                if checked:
                    db.execute('UPDATE report_documents SET current_revision_id=%s WHERE business_id=%s AND id=%s AND stale_reason IS NULL AND deleted_at IS NULL',
                               (chosen['selected_revision_id'],business,document))
        # This link is metadata only. It never grants content access or replaces a review.
        db.execute('''UPDATE web_jobs SET report_document_id=%s
            WHERE business_id=%s AND engine_run_id=%s AND engine_kind='opencode'
            AND (report_document_id IS NULL OR report_document_id=%s)''', (document,business,run,document))
        return document


def reason(db, document, *, config=None, deep=False):
    """Compare frozen dependencies, never recalculate or alter a run snapshot."""
    if document['stale_reason']:
        return document['stale_reason']
    baseline = db.execute('SELECT * FROM engine_report_contexts WHERE run_id=%s AND business_id=%s',
                          (document['source_run_id'], document['business_id'])).fetchone()
    if not baseline:
        return 'missing_context'
    business = document['business_id']
    if db.execute('''SELECT 1 FROM dataset_versions WHERE business_id=%s AND analysis_id=%s
        AND (corrected OR superseded_by IS NOT NULL)''', (business, document['analysis_id'])).fetchone():
        return 'data_changed'
    from ..data_knowledge import service as knowledge
    if any(not knowledge.current(db,business,dep) for dep in baseline['data_models']):
        return 'definitions_changed'
    if knowledge.heads(db,business,document['analysis_id']) != baseline['data_models']:
        return 'definitions_changed'
    for table, version in baseline['table_versions'].items():
        if version is None or context.table_version(db,business,table) != version:
            return 'data_changed'
    current = context.effective(db,business)
    selection = baseline['selection']
    active = {r['id'] for r in context.scoped(current,selection)}
    if any(r['id'] not in active for r in baseline['memories'] if r['content']['kind']=='priority'):
        return 'memory_changed'
    if context.watch(current,selection) != context.watch(baseline['memories'],selection):
        return 'memory_changed'
    if config is not None:
        from ..storage import Storage, digest
        storage = Storage(config.storage)
        source = db.execute('SELECT snapshot FROM engine_runs WHERE business_id=%s AND id=%s',
                            (business,document['source_run_id'])).fetchone()['snapshot']
        try:
            if deep and admission._snapshot(db,config,business,document['analysis_id'],[UUID(v) for v in baseline['table_versions']]) != source:
                return 'data_changed'
            originals = db.execute('''SELECT DISTINCT s.original_key,s.sha256,p.parquet_key FROM sources s
                JOIN prepared_tables p ON p.source_id=s.id AND p.business_id=s.business_id
                WHERE p.business_id=%s AND p.id=ANY(%s::uuid[])''',
                (business,list(baseline['table_versions']))).fetchall()
            if any(not storage.path(business,r[key]).is_file() for r in originals for key in ('original_key','parquet_key')):
                return 'data_unavailable'
            if deep and any(digest(storage.path(business,r['original_key'])) != r['sha256'] for r in originals):
                return 'data_unavailable'
        except (OSError,ValueError):
            return 'data_unavailable'
    return None


def retire(db, document, *, config=None, deep=False):
    problem = reason(db,document,config=config,deep=deep)
    if problem and not document['stale_reason']:
        db.execute('UPDATE report_documents SET stale_reason=%s WHERE business_id=%s AND id=%s',
                   (problem,document['business_id'],document['id']))
    return problem


def invalidate(db, business):
    """Writer already holds memory head; documents follow in stable ID order."""
    rows = db.execute('SELECT * FROM report_documents WHERE business_id=%s AND stale_reason IS NULL ORDER BY id',
                      (business,)).fetchall()
    for document in rows:
        lock(db,document['id'])
        retire(db,document)


def is_current(document, revision, run_status):
    return bool(revision and document['current_revision_id']==revision['id'] and
                run_status=='delivered' and not document['stale_reason'] and not document['deleted_at'])


def audit(config, business, document):
    """Explicit integrity inspection, outside metadata reads; no provider call."""
    business,document=UUID(str(business)),UUID(str(document))
    with connect(config) as db, db.transaction():
        row=db.execute('SELECT * FROM report_documents WHERE business_id=%s AND id=%s',(business,document)).fetchone()
        if not row:
            raise ValueError('Report does not belong to this business.')
        memory.lock(db,business); lock(db,document)
        row=db.execute('SELECT * FROM report_documents WHERE business_id=%s AND id=%s',(business,document)).fetchone()
        return retire(db,row,config=config,deep=True)
