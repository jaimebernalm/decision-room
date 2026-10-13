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

VERSION = 'business-knowledge-3'
INDICATORS_BYTES = 4 * 1024
FOLLOW_UPS_BYTES = 6 * 1024
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
                history=prior,
                indicators=indicators(db, business),
                follow_ups=follow_ups(db, business),
                heads=heads(db, business))
    return core, files, manifest


def heads(db, business):
    row = db.execute('SELECT indicators_revision,follow_ups_revision FROM knowledge_heads WHERE business_id=%s', (business,)).fetchone()
    return dict(indicators=row['indicators_revision'] if row else 0, follow_ups=row['follow_ups_revision'] if row else 0)


def _bounded(items, limit, wrap):
    """Whole items while the WHOLE returned object fits a real serialized byte budget; the rest only counted.

    Each trial is measured with the largest omitted count it could end with, so the final object never grows."""
    from .memory.service import encoded
    kept = []
    for index, item in enumerate(items):
        if len(encoded(wrap([*kept, item], len(items) - len(kept) - 1)).encode()) <= limit:
            kept.append(item)
    return wrap(kept, len(items) - len(kept))


def indicators(db, business):
    """Active saved indicators with their latest value (latest eligible dataset version)."""
    from . import indicators as store
    items = []
    for row in db.execute("SELECT * FROM saved_indicators WHERE business_id=%s AND status='active' ORDER BY name,id", (business,)).fetchall():
        version = db.execute("SELECT id,version,metric_keys FROM indicator_versions WHERE indicator_id=%s AND state='active'",
                             (row['id'],)).fetchone()
        values = store.current_values(db, business, row['id'])
        latest = values[0] if values else None
        item = dict(id=str(row['id']), name=row['name'], version=version['version'] if version else None, label=store.LABEL)
        if latest:
            item['latest'] = dict(value_id=str(latest['id']), version_id=str(latest['version_id']),
                                  analysis_id=str(latest['analysis_id']), dataset_version=latest['dataset_version'],
                                  period=store.period_of(db, business, latest['analysis_id']), status=latest['status'])
            if latest['status'] == 'completed':
                item['latest']['metrics'] = latest['metrics']
                if store.meanings_note(latest['meanings_basis']):
                    item['latest']['meanings'] = store.meanings_note(latest['meanings_basis'])
            elif latest['status'] == 'unavailable':
                item['latest']['reason'] = store.REASONS.get(latest['reason'], latest['reason'])
        items.append(item)
    return _bounded(items, INDICATORS_BYTES, lambda kept, omitted: dict(
        items=kept, omitted=omitted, use='Saved fixed formulas recomputed without a model; not independently checked.'))


def follow_ups(db, business):
    """Open topics from earlier native reports, verbatim, newest report first; closed ones only counted."""
    from . import follow_ups as register
    from . import indicators as store
    items = []
    rows = register.listing(db, business)
    reports = register.report_states(db, business, rows)
    for row in rows:
        item = dict(id=str(row['id']), state=row['state'], headline=row['headline'], date=row['report_date'].date().isoformat(),
                    priority=row['priority_title'], labels=row['content']['labels'],
                    **{k: row['content'][k] for k in register.BRANCHES if row['content'][k] is not None},
                    report=reports[row['document_id']])
        if row['link']:
            link = row['link']
            item['link'] = {k: link[k] for k in ('indicator_id', 'version_id', 'value_id', 'metric_key', 'value', 'dataset_version')}
            if store.meanings_note(link.get('meanings_basis')):
                item['link']['meanings'] = store.meanings_note(link['meanings_basis'])
        items.append(item)
    counts = register.counts(db, business)
    return _bounded(items, FOLLOW_UPS_BYTES, lambda kept, omitted: dict(
        items=kept, omitted=omitted, counts=counts,
        use="Earlier reports' proposals with the owner's state; 'checked' is the owner's declaration, not a verification."))
