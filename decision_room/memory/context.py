"""Business-scoped retrieval and freshness, independent of graph checkpoints.

The manifest records delivery, never an assertion about the model's reasoning.
Unknown periods widen applicability. Retrieval cannot authorize new Python inputs.
"""
from datetime import date, timedelta

from psycopg.types.json import Jsonb

from .service import digest, encoded, lock

VERSION = 'business-context-v1'
MEMORY_BYTES = 48000
CONTEXT_BYTES = 200000
MAX_RETRIEVALS = 12


class StaleContext(ValueError):
    pass


def period(value=None):
    if value is None:
        return {'from': None, 'until': None}
    if not isinstance(value, dict) or set(value) != {'from', 'until'}:
        raise ValueError('Period requires from and until ISO dates, or null for unknown bounds.')
    result = {k: date.fromisoformat(v).isoformat() if v else None for k, v in value.items()}
    if result['from'] and result['until'] and result['from'] > result['until']:
        raise ValueError('Invalid context period.')
    return result


def intersects(a, b):
    return not ((a['until'] and b['from'] and a['until'] < b['from']) or
                (b['until'] and a['from'] and b['until'] < a['from']))


def effective(db, business_id):
    """A future change closes prior applicability; a historical correction replaces it."""
    rows = db.execute('''SELECT r.*,s.origin_key FROM memory_revisions r
        JOIN memory_sources s ON s.id=r.source_id WHERE r.business_id=%s
        ORDER BY r.business_revision''', (business_id,)).fetchall()
    timelines = {}
    for r in rows:
        key = str(r['fact_id'])
        content = r['content']
        if content['kind'] == 'result_reference':
            content = {**content, 'statement': 'Referencia a resultado: abrir el informe original y comprobar su vigencia antes de usar sus conclusiones.'}
        if r['change_kind'] == 'future':
            before = (date.fromisoformat(content['valid_from']) - timedelta(days=1)).isoformat()
            old = []
            for item in timelines.get(key, []):
                end = min(item['period']['until'] or before, before)
                if not item['period']['from'] or item['period']['from'] <= end:
                    old.append({**item, 'period': {**item['period'], 'until': end}})
        else:
            old = []
        timelines[key] = old
        if r['status'] not in ('withdrawn', 'superseded'):
            timelines[key].append(dict(id=key, reference=f"{key}@{r['revision']}", revision=r['revision'], status=r['status'],
                content=content, origin_id=str(r['source_id']), origin_key=r['origin_key'],
                alternatives=r['alternatives'], period={'from': content['valid_from'], 'until': content['valid_until']}))
    return [row for key in sorted(timelines) for row in timelines[key]]


def own_origins(db, session_id):
    rows = db.execute('''SELECT 'planning_answer:' || a.id AS key FROM agent_answers a
        JOIN agent_questions q ON q.id=a.question_id WHERE q.session_id=%s
        UNION ALL SELECT 'review_answer:' || a.id FROM agent_review_answers a
        JOIN agent_reviews r ON r.id=a.review_id WHERE r.session_id=%s''', (session_id, session_id)).fetchall()
    return {r['key'] for r in rows}


def scoped(rows, selection):
    return [r for r in rows if intersects(r['period'], selection['period']) and
            (r['content']['scope'] == 'business' or
             r['content']['scope'] == 'analysis' and r['content']['scope_id'] == selection['analysis_id'] or
             r['content']['scope'] == 'source' and r['content']['scope_id'] in selection['source_ids'])]


def watch(rows, selection):
    # Clip applicability to this request: a change in September does not alter June.
    result = []
    for r in scoped(rows, selection):
        if r['content']['kind'] == 'priority':
            continue  # Orientation for new work, not grounds to revoke prior arithmetic.
        span = {'from': max(filter(None, [r['period']['from'], selection['period']['from']]), default=None),
                'until': min(filter(None, [r['period']['until'], selection['period']['until']]), default=None)}
        result.append({**r, 'period': span})
    return digest(result)


def table_version(db, business_id, table_id):
    row = db.execute('''SELECT p.parquet_sha256,p.row_count,p.columns,p.profile,s.status,s.original_names,a.title
        FROM prepared_tables p JOIN sources s ON s.id=p.source_id JOIN analyses a ON a.id=p.analysis_id
        WHERE p.business_id=%s AND p.id=%s AND NOT EXISTS (SELECT 1 FROM dataset_versions v WHERE v.analysis_id=p.analysis_id AND v.corrected)''', (business_id, table_id)).fetchone()
    return digest(row) if row and row['status'] == 'ready' else None


def datasets(db, business_id, query='', limit=20, analysis_id=None):
    # Rank metadata in PostgreSQL; numbers remain in typed files for SQL/Python.
    rows = db.execute('''SELECT p.id,p.source_id,p.analysis_id,p.parquet_sha256,p.row_count,p.columns,
        s.original_names,a.title,v.dataset_id,v.version AS dataset_version,v.period_from,v.period_until,
        ts_rank(to_tsvector('spanish',a.title || ' ' || s.original_names::text || ' ' || p.columns::text),
                plainto_tsquery('spanish',%s)) AS score
        FROM prepared_tables p JOIN sources s ON s.id=p.source_id JOIN analyses a ON a.id=p.analysis_id
        LEFT JOIN dataset_versions v ON v.analysis_id=a.id
        WHERE p.business_id=%s AND s.status='ready' AND NOT EXISTS (SELECT 1 FROM dataset_versions v WHERE v.analysis_id=p.analysis_id AND (v.corrected OR (v.superseded_by IS NOT NULL AND p.analysis_id IS DISTINCT FROM %s::uuid))) AND NOT EXISTS (SELECT 1 FROM dataset_uploads u WHERE u.business_id=p.business_id AND u.result->>'pending'='true' AND u.result->>'existing_id' IS NULL AND u.result->>'batch_sha256'=a.batch_sha256) AND (%s::uuid IS NULL OR p.analysis_id=%s)
        AND (%s='' OR to_tsvector('spanish',a.title || ' ' || s.original_names::text || ' ' || p.columns::text)
             @@ plainto_tsquery('spanish',%s))
        ORDER BY score DESC,p.id LIMIT %s''',
        (query, business_id, analysis_id, analysis_id, analysis_id, query, query, limit + 1)).fetchall()
    items = [dict(id=str(r['id']), source_id=str(r['source_id']), analysis_id=str(r['analysis_id']),
                  version=r['parquet_sha256'], description=r['title'], names=r['original_names'],
                  columns=[c['name'] for c in r['columns']], row_count=r['row_count'],
                  dataset_id=str(r['dataset_id'] or r['analysis_id']), dataset_version=r['dataset_version'] or 1,
                  period={'from': str(r['period_from']) if r['period_from'] else None, 'until': str(r['period_until']) if r['period_until'] else None}, coverage='Owner-declared period; records remain separate, coverage not verified.')
             for r in rows[:limit]]
    return {'items': items, 'more': len(rows) > limit}


def create(db, session, request_period=None):
    lock(db, session['business_id'])
    if db.execute('SELECT 1 FROM context_manifests WHERE session_id=%s', (session['id'],)).fetchone():
        return
    source_ids = [str(r['id']) for r in db.execute('SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s',
                                                  (session['business_id'], session['analysis_id'])).fetchall()]
    selection = dict(version=VERSION, analysis_id=str(session['analysis_id']), source_ids=source_ids,
                     period=period(request_period), objective=session['source_snapshot']['owner_context'],
                     rules='Business + explicit source/analysis links + interval overlap; all applicable material doubts; text/hybrid discovery with recorded search mode.',
                     limits=dict(memory_bytes=MEMORY_BYTES, context_bytes=CONTEXT_BYTES, retrievals=MAX_RETRIEVALS),
                     original_source=session['source_snapshot'])
    rows = effective(db, session['business_id'])
    memories = scoped(rows, selection)
    # Small memories are supplied whole. Never truncate a material doubt or definition.
    if len(encoded(memories).encode()) > MEMORY_BYTES:
        raise ValueError('Applicable memory exceeds 48 KB. Narrow the source/period before continuing; no material doubts were dropped.')
    business = db.execute('SELECT name FROM businesses WHERE id=%s', (session['business_id'],)).fetchone()
    initial = dict(profile={'id': str(session['business_id']), 'name': business['name']},
                   memories=memories, period=selection['period'],
                   dataset_catalog=datasets(db, session['business_id'], analysis_id=session['analysis_id']),
                   authorized_source_ids=source_ids, authorized_analysis_id=str(session['analysis_id']),
                   pending_context='Other business datasets/reports available through retrieval. Unknown dates require checking before use.')
    if session['request_key'].startswith('web:'):
        import json
        from ..conversations import fresh
        from uuid import UUID
        try:
            job_id = UUID(session['request_key'][4:])
        except ValueError:
            job_id = None
        job = db.execute("SELECT context FROM web_jobs WHERE id=%s AND business_id=%s AND origin='chat'", (job_id,session['business_id'])).fetchone()
        if job and job['context']:
            continuation = json.loads(job['context'])
            if any(not fresh(db,dep['snapshot']) for dep in continuation['dependencies']):
                raise StaleContext('Conversation history changed before planning; retry with current memory.')
            initial['conversation_start'] = continuation['context']
            initial['conversation_dependencies'] = continuation['dependencies']
    db.execute('''INSERT INTO context_manifests(session_id,business_id,selection,initial_context)
        VALUES (%s,%s,%s,%s)''', (session['id'], session['business_id'], Jsonb(selection), Jsonb(initial)))


def manifest(db, session_id):
    return db.execute('SELECT * FROM context_manifests WHERE session_id=%s', (session_id,)).fetchone()


def source_current(db, business_id, saved):
    for table in saved['tables']:
        row = db.execute('''SELECT p.parquet_sha256,p.row_count,p.columns,p.profile,s.status,s.original_names
            FROM prepared_tables p JOIN sources s ON s.id=p.source_id WHERE p.business_id=%s AND p.id=%s AND NOT EXISTS (SELECT 1 FROM dataset_versions v WHERE v.analysis_id=p.analysis_id AND v.corrected)''',
                         (business_id, table['id'])).fetchone()
        if not row or row['status'] != 'ready' or row['parquet_sha256'] != table['sha256'] or row['row_count'] != table['row_count']:
            return False
        if row['columns'] != table['columns'] or row['original_names'] != table['names'] or row['profile']['sample_rows'][:5] != table['sample_rows']:
            return False
    return True


def reason(db, session_id, seen=None):
    corrected = db.execute('''SELECT 1 FROM agent_sessions s JOIN dataset_versions v ON v.analysis_id=s.analysis_id
        WHERE s.id=%s AND v.corrected''', (session_id,)).fetchone()
    if corrected:
        return 'Source version corrected; select the replacement data for a new investigation.'
    m = manifest(db, session_id)
    if not m:
        return None  # Legacy history is preserved; resuming it requires explicit replanning.
    if m['stale_reason']:
        return m['stale_reason']
    seen = set(seen or ())
    if str(session_id) in seen:
        return 'Cyclic context dependency.'
    seen.add(str(session_id))
    selection = m['selection']
    # A source already supplied as an answer in THIS session does not add knowledge.
    # A later correction uses a new origin and therefore does invalidate it.
    originals = own_origins(db, session_id)
    if originals:
        retired_answers = db.execute('''SELECT r.content FROM memory_revisions r
            JOIN memory_sources s ON s.id=r.source_id WHERE r.business_id=%s AND s.origin_key=ANY(%s)
            AND EXISTS (SELECT 1 FROM memory_revisions later WHERE later.fact_id=r.fact_id
                AND later.revision>r.revision AND later.status IN ('withdrawn','superseded'))''',
            (m['business_id'], list(originals))).fetchall()
        retired = [dict(content=r['content'], period={'from': r['content']['valid_from'], 'until': r['content']['valid_until']})
                   for r in retired_answers]
        if scoped(retired, selection):
            return 'Withdrawn owner answer cannot be replayed; replan with current context.'
    rows = [r for r in effective(db, m['business_id']) if r['origin_key'] not in originals]
    baseline = [r for r in m['initial_context']['memories'] if r['origin_key'] not in originals]
    active_ids = {r['id'] for r in scoped(rows, selection)}
    if any(r['id'] not in active_ids for r in baseline if r['content']['kind'] == 'priority'):
        return 'Withdrawn memory cannot be replayed; replan with current context.'
    if watch(rows, selection) != watch(baseline, selection):
        return 'Applicable business memory changed; replan with current definitions.'
    if not source_current(db, m['business_id'], selection['original_source']):
        return 'Source metadata changed; replan with current data.'
    events = db.execute('SELECT dependencies FROM context_retrievals WHERE session_id=%s', (session_id,)).fetchall()
    for event in [dict(dependencies=m['initial_context'].get('conversation_dependencies', [])), *events]:
        for dep in event['dependencies']:
            if dep['kind'] == 'memory':
                scope = {**selection, **dep['selection']}
                current_rows = effective(db, m['business_id'])
                available = {r['id'] for r in scoped(current_rows, scope)}
                if watch(current_rows, scope) != dep['watch'] or not set(dep.get('priority_ids', [])) <= available:
                    return 'Retrieved memory changed; replan.'
            elif dep['kind'] == 'chat':
                from ..conversations import fresh
                if not fresh(db, dep['snapshot'], ignore_origins=originals):
                    return 'Retrieved conversation context changed; replan.'
            elif dep['kind'] == 'table':
                if table_version(db, m['business_id'], dep['id']) != dep['metadata_version']:
                    return 'Retrieved dataset changed; replan.'
            elif dep['kind'] == 'report':
                row = db.execute('''SELECT r.*,s.superseded_by FROM agent_reviews r JOIN agent_sessions s ON s.id=r.session_id
                    WHERE r.id=%s AND r.business_id=%s''', (dep['id'], m['business_id'])).fetchone()
                if (not row or row['status'] != 'approved' or row['superseded_by'] or row['approved_sha256'] != dep['version'] or
                    db.execute('SELECT 1 FROM agent_review_holds WHERE review_id=%s', (dep['id'],)).fetchone() or
                    reason(db, row['session_id'], seen)):
                    return 'Retrieved report is no longer valid; replan.'
    return None


def ensure(db, session_id):
    problem = reason(db, session_id)
    if problem:
        raise StaleContext(problem)


def invalidate(db, business_id):
    """Called inside the memory writer transaction and its business head lock."""
    rows = db.execute('SELECT session_id FROM context_manifests WHERE business_id=%s AND stale_reason IS NULL', (business_id,)).fetchall()
    for row in rows:
        problem = reason(db, row['session_id'])
        if problem:
            db.execute('UPDATE context_manifests SET stale_reason=%s WHERE session_id=%s', (problem, row['session_id']))
            db.execute("UPDATE agent_research SET status='stale',issue=%s,updated_at=now() WHERE session_id=%s", (problem, row['session_id']))
            db.execute("UPDATE agent_reviews SET status='stale',issue=%s,updated_at=now() WHERE session_id=%s", (problem, row['session_id']))
    # Old checkpoints have no dependency record: conservatively hold their output.
    db.execute("""UPDATE agent_reviews r SET status='stale',issue='Memory changed; legacy context requires replanning.'
        WHERE business_id=%s AND NOT EXISTS (SELECT 1 FROM context_manifests m WHERE m.session_id=r.session_id)""", (business_id,))


def delivered(db, session_id):
    m = manifest(db, session_id)
    if not m:
        raise StaleContext('Legacy session has no context manifest. Use agent-replan to preserve history and resume with current memory.')
    events = db.execute('''SELECT decision_key,ordinal,request,response FROM context_retrievals
        WHERE session_id=%s ORDER BY created_at,decision_key,ordinal''', (session_id,)).fetchall()
    return dict(manifest_id=str(session_id), version=VERSION, **{k:v for k,v in m['initial_context'].items() if k != 'conversation_dependencies'}, retrievals=events,
                selection_rules=m['selection']['rules'], limits=m['selection']['limits'])
