"""Shared business knowledge for the chat and the report brief. Read-only; no model calls.

Both consumers receive the same core for the same business, selection and instant:
profile, selection, applicable DECLARED memory, the current data-model meanings of the
selected analysis and a bounded discovery catalogue. Proposed, conflicted or withdrawn
memory never enters the core; the chat keeps its own labelled memory for managing it.
The catalogue is discovery only: other datasets are not mounted or authorised for
calculation. The prior-report history is labelled background: what an earlier report
said is that report's statement, not current evidence.
"""
from .memory import context

VERSION = 'business-knowledge-2'
CATALOG_LIMIT = 20


def declared(rows):
    """Applicable declared statements with a resolved period, without alternatives or origins."""
    return [dict(id=r['id'], reference=r['reference'], revision=r['revision'], status=r['status'],
                 content=r['content'], period=r['period'])
            for r in rows
            if r['status'] == 'declared' and r['content'].get('temporal_scope') != 'unresolved']


def data_model(db, business, analysis):
    """Current owner-declared meanings of the selected analysis, or None when unknown/stale."""
    from .data_knowledge import service as knowledge
    from .engine.brief import meanings
    if not analysis:
        return None
    head = knowledge.latest(db, business, analysis)
    if not head or not knowledge.current(db, business, {'analysis_id': str(analysis), 'revision': head['revision']}):
        return dict(analysis_id=str(analysis), revision=None, declared=[], unknown=True)
    lines, unknown = meanings(head['body'])
    return dict(analysis_id=str(analysis), revision=head['revision'], declared=lines, unknown=bool(unknown))


def catalog(db, business):
    items = context.datasets(db, business, limit=CATALOG_LIMIT)
    seen, result = set(), []
    for item in items['items']:
        if item['analysis_id'] in seen:
            continue
        seen.add(item['analysis_id'])
        result.append({k: item[k] for k in ('analysis_id', 'dataset_id', 'dataset_version', 'description', 'period')})
    return dict(items=result, more=items['more'],
                use='Discovery only: these datasets are not mounted or authorised for calculation.')


def build(db, business, selection, *, profile=None, explicit=()):
    """The shared core. `profile` is a frozen {name, description} when the job captured one."""
    return build_with_files(db, business, selection, profile=profile, explicit=explicit)[0]


def build_with_files(db, business, selection, *, profile=None, explicit=()):
    """The core plus the frozen prior-report files and manifest, read in the caller's transaction."""
    from .reports import history
    if profile is None:
        row = db.execute('SELECT name,description FROM businesses WHERE id=%s', (business,)).fetchone()
        if not row:
            raise ValueError('Business profile not found.')
        profile = dict(name=row['name'], description=row['description'])
    scope = {k: selection[k] for k in ('analysis_id', 'source_ids', 'period')}
    prior, files, manifest = history.select(db, business, scope['analysis_id'], explicit=explicit)
    core = dict(version=VERSION,
                profile=dict(name=profile['name'], description=profile['description']),
                selection=scope,
                memory=declared(context.scoped(context.effective(db, business), scope)),
                data_model=data_model(db, business, scope['analysis_id']),
                catalog=catalog(db, business),
                history=prior)
    return core, files, manifest
