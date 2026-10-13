"""Saved indicators: an owner-confirmed fixed formula recomputed without a model.

A version freezes, from a published quick calculation, the code, the table keys, the
chosen metric keys, the definitions the program receives and a conservative semantic
signature. Each eligible dataset version gets one value, computed through an attempt
journal written before any Docker call. A structural mismatch leaves the value
unavailable with its reason; nothing is adapted silently and no model is ever called.
Recomputation reuses the same visible code; it is not an independent check.
"""
import hashlib
import unicodedata
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from . import execution, quick_calc
from .database import connect
from .memory import context as ctx, service as memory
from .web.errors import WebError, bounded, identifier

VERSION = 'indicators-1'
PREFIX = 'indicator:'
LABEL = 'Indicador guardado · fórmula fija recalculada sin modelo · sin comprobación independiente'
INHERITED = ('Calculado con la fórmula y los significados guardados de la versión {}; '
             'esos significados no están confirmados en esta versión.')
MAX_METRICS = 10
MAX_KEY_CHARS = 80
TIMEOUT = quick_calc.TIMEOUT
MAX_INPUT_BYTES = quick_calc.MAX_INPUT_BYTES
BACKOFF = (60, 300, 900, 3600)
RESOURCE_RETRIES = 1
MEMORY_KINDS = ('definition', 'availability')
TERMINAL = quick_calc.TERMINAL
REASONS = {
    'missing_table': 'Falta en estos datos un archivo que usa la fórmula.',
    'ambiguous_table': 'Varios archivos de estos datos podrían ser el que usa la fórmula.',
    'schema_changed': 'Las columnas de un archivo han cambiado.',
    'meanings_changed': 'Ha cambiado lo que significan los datos o tus definiciones.',
    'meanings_unknown': 'Se retiró un significado del que depende la fórmula.',
    'basis_changed': 'Los significados con los que se guardó la fórmula ya no son válidos.',
    'program_failed': 'La fórmula falló con estos datos.',
    'invalid_result': 'La fórmula no devolvió un resultado válido.',
    'metric_missing': 'La fórmula ya no devuelve una de las cifras guardadas.',
    'resource_limit': 'El cálculo superó el tiempo o la memoria permitidos.',
    'corrected': 'Estos datos se corrigieron después.',
}


def file_key(name):
    return unicodedata.normalize('NFKC', name).strip().casefold()


def digest(value):
    return hashlib.sha256(memory.encoded(value).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc)


# ---- Datasets and tables -------------------------------------------------------------

def dataset_of(db, business, analysis):
    return db.execute('''SELECT a.id,a.status,coalesce(v.dataset_id,a.id) AS dataset_id,coalesce(v.version,1) AS dataset_version,
        coalesce(v.corrected,false) AS corrected,v.superseded_by FROM analyses a
        LEFT JOIN dataset_versions v ON v.analysis_id=a.id WHERE a.business_id=%s AND a.id=%s''',
                      (business, analysis)).fetchone()


def eligible(db, business, dataset_id):
    """Ready, uncorrected versions of one logical dataset, oldest first."""
    return db.execute('''SELECT a.id AS analysis_id,coalesce(v.version,1) AS dataset_version FROM analyses a
        LEFT JOIN dataset_versions v ON v.analysis_id=a.id
        WHERE a.business_id=%s AND coalesce(v.dataset_id,a.id)=%s AND a.status='ready' AND NOT coalesce(v.corrected,false)
        ORDER BY 2''', (business, dataset_id)).fetchall()


def tables_of(db, business, analysis):
    return db.execute('''SELECT p.id,p.source_id,p.columns,s.original_names FROM prepared_tables p
        JOIN sources s ON s.id=p.source_id WHERE p.business_id=%s AND p.analysis_id=%s AND s.status='ready'
        ORDER BY p.id''', (business, analysis)).fetchall()


def mapping(db, business, analysis, tables):
    """One-to-one: each alias to the single table sharing one of its file keys. Never the first of a list."""
    rows = tables_of(db, business, analysis)
    result, used = {}, set()
    for table in tables:
        keys = set(table['file_keys'])
        found = [r for r in rows if keys & {file_key(n) for n in r['original_names']}]
        if not found:
            return None, ('missing_table', table['alias'])
        if len(found) > 1 or found[0]['id'] in used:
            return None, ('ambiguous_table', table['alias'])
        used.add(found[0]['id'])
        result[table['alias']] = found[0]
    return result, None


# ---- Semantic signature --------------------------------------------------------------

def _raw(body, table_id):
    """Every meaning element of one table, declared or not (to detect owner changes)."""
    table = next((t for t in (body or {}).get('tables', []) if t.get('id') == str(table_id)), None)
    if not table:
        return {}
    out = {'table': (table.get('semantic_status'), table.get('description', ''), table.get('grain', ''))}
    for column in table.get('columns', []):
        out['column:' + column['name']] = (column.get('semantic_status'), column.get('meaning', ''),
                                           column.get('unit', ''), column.get('conversion', ''))
    return out


def declared_elements(body, table_id):
    """Owner-declared elements of one table, keyed by name so versions are comparable."""
    out = {}
    for key, value in _raw(body, table_id).items():
        if value[0] == 'owner_declared':
            out[key] = list(value[1:])
    return out


def owner_touched(db, business, analysis, table_ids):
    """Elements an owner correction actually changed in this analysis, per table id."""
    revisions = db.execute('SELECT revision,reason,body FROM data_model_revisions WHERE business_id=%s AND analysis_id=%s '
                           'ORDER BY revision', (business, analysis)).fetchall()
    touched = {str(t): set() for t in table_ids}
    for before, after in zip(revisions, revisions[1:]):
        if not (after['reason'] or '').startswith('Owner correction'):
            continue
        for table_id in touched:
            old, new = _raw(before['body'], table_id), _raw(after['body'], table_id)
            touched[table_id] |= {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    return touched


def memory_set(db, business, analysis, rows_by_alias, effective=None):
    """Applicable declared definitions/availability, scoped with this analysis' own ids; no ids kept."""
    from . import business_knowledge
    sources = [str(r['id']) for r in db.execute('SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s',
                                                 (business, analysis)).fetchall()]
    by_source = {str(r['source_id']): alias for alias, r in rows_by_alias.items()}
    rows = business_knowledge.declared(ctx.scoped(effective if effective is not None else ctx.effective(db, business),
                                                  dict(analysis_id=str(analysis), source_ids=sources, period=ctx.period())))
    items = []
    for row in rows:
        content = row['content']
        if content.get('kind') not in MEMORY_KINDS:
            continue
        if content['scope'] == 'source':
            if str(content.get('scope_id')) not in by_source:
                continue  # Another table of the analysis: not one the formula reads.
            scope = 'table:' + by_source[str(content['scope_id'])]
        else:
            scope = content['scope']
        items.append(dict(kind=content['kind'], statement=content['statement'], period=row['period'], scope=scope))
    return sorted(items, key=memory.encoded)


def signature(db, business, analysis, rows_by_alias, effective=None):
    from .data_knowledge import service as knowledge
    head = knowledge.latest(db, business, analysis)
    body = head['body'] if head else None
    return dict(version=VERSION,
                schema={alias: [c['name'] for c in r['columns']] for alias, r in sorted(rows_by_alias.items())},
                elements={alias: declared_elements(body, r['id']) for alias, r in sorted(rows_by_alias.items())},
                memory=memory_set(db, business, analysis, rows_by_alias, effective),
                basis=dict(analysis_id=str(analysis), data_model_revision=head['revision'] if head else None,
                           tables={alias: str(r['id']) for alias, r in sorted(rows_by_alias.items())}))


def check(db, business, frozen, analysis, rows_by_alias, effective=None):
    """Compare the frozen signature with this analysis. Returns (reason, detail, meanings_basis)."""
    from .data_knowledge import service as knowledge
    current = signature(db, business, analysis, rows_by_alias, effective)
    for alias in frozen['schema']:
        if frozen['schema'][alias] != current['schema'].get(alias):
            return 'schema_changed', alias, None
    if frozen['memory'] != current['memory']:
        return 'meanings_changed', 'definiciones', None
    basis = frozen['basis']
    source = dataset_of(db, business, basis['analysis_id'])
    if not source or source['corrected']:
        return 'basis_changed', 'versión de origen corregida', None
    if basis['analysis_id'] != str(analysis):
        head = knowledge.latest(db, business, basis['analysis_id'])
        for alias, table_id in basis['tables'].items():
            if declared_elements(head['body'] if head else None, table_id) != frozen['elements'][alias]:
                return 'basis_changed', alias, None
    touched = owner_touched(db, business, analysis, [r['id'] for r in rows_by_alias.values()])
    confirmed, inherited, undeclared = [], [], []
    for alias, row in sorted(rows_by_alias.items()):
        old, new = frozen['elements'].get(alias, {}), current['elements'][alias]
        for key, value in new.items():
            if old.get(key) != value:
                return 'meanings_changed', f'{alias}: {key}', None
        for key in old:
            if key in new:
                confirmed.append(f'{alias}: {key}')
            elif key in touched[str(row['id'])]:
                return 'meanings_unknown', f'{alias}: {key}', None
            else:
                inherited.append(f'{alias}: {key}')
        undeclared += [f'{alias}: column:{c}' for c in current['schema'][alias] if f'column:{c}' not in old]
    return None, None, dict(analysis_id=basis['analysis_id'], dataset_version=frozen.get('dataset_version'),
                            data_model_revision=basis['data_model_revision'], current_meanings_confirmed=not inherited,
                            confirmed=confirmed, inherited=inherited, undeclared=undeclared[:50],
                            undeclared_omitted=max(0, len(undeclared) - 50))


# ---- Requests ------------------------------------------------------------------------

def receipt(db, business, key, kind, request):
    """Idempotent owner requests: same key and payload returns the result; another payload is 409."""
    sha = digest(dict(kind=kind, request=request))
    row = db.execute('SELECT * FROM indicator_requests WHERE business_id=%s AND request_key=%s', (business, key)).fetchone()
    if row and (row['kind'] != kind or row['request_sha256'] != sha):
        raise WebError('Este envío ya se guardó con otros datos.', 409)
    return (row['result'] if row else None), sha


def remember(db, business, key, kind, sha, result):
    db.execute('INSERT INTO indicator_requests(business_id,request_key,kind,request_sha256,result) VALUES (%s,%s,%s,%s,%s)',
               (business, key, kind, sha, Jsonb(result)))


# ---- Published source ----------------------------------------------------------------

def _meaning_view(defs):
    """What a calculation's frozen definitions said, without ids or revisions."""
    return dict(meanings=defs['data_model']['meanings'], unknown=defs['data_model']['unknown'],
                omitted=defs['data_model']['omitted'], memory_omitted=defs['memory_omitted'],
                memory=[{k: m.get(k) for k in ('kind', 'statement', 'period', 'temporal_scope', 'scope')} for m in defs['memory']])


def published(db, business, turn_id, calculation_id, metric_keys):
    """A completed calculation as published in a chat answer, still valid for current data."""
    turn = db.execute('''SELECT t.response,t.status FROM chat_turns t JOIN chat_conversations c ON c.id=t.conversation_id
        WHERE t.business_id=%s AND t.id=%s AND c.deleted_at IS NULL''', (business, turn_id)).fetchone()
    item = next((c for c in ((turn or {}).get('response') or {}).get('calculations', [])
                 if c.get('calculation_id') == str(calculation_id)), None) if turn and turn['status'] == 'completed' else None
    if not item:
        raise WebError('Ese cálculo no está publicado en esta conversación.', 404)
    row = db.execute("""SELECT * FROM chat_calculations WHERE business_id=%s AND id=%s AND turn_id=%s AND admission='admitted'""",
                     (business, calculation_id, turn_id)).fetchone()
    done = row and db.execute("SELECT * FROM executions WHERE business_id=%s AND id=%s AND status='completed' AND analysis_id=%s",
                              (business, row['execution_id'], row['analysis_id'])).fetchone()
    if not done or item['code'] != row['request']['code'] or str(done['id']) != item['execution_id']:
        raise WebError('Ese cálculo no está disponible para guardarlo.', 409)
    if (not isinstance(metric_keys, list) or not 1 <= len(metric_keys) <= MAX_METRICS or len(set(metric_keys)) != len(metric_keys)
            or any(not isinstance(k, str) or len(k) > MAX_KEY_CHARS or k not in item['metrics']
                   or done['result']['metrics'].get(k) != item['metrics'][k] for k in metric_keys)):
        raise WebError(f'Elige entre 1 y {MAX_METRICS} cifras distintas de ese cálculo, con nombres de hasta {MAX_KEY_CHARS} caracteres.')
    source = dataset_of(db, business, row['analysis_id'])
    if not source or source['corrected'] or any(ctx.table_version(db, business, t['id']) != t['metadata_version']
                                                for t in row['request']['tables']):
        raise WebError('Los datos de ese cálculo han cambiado o se corrigieron. Pide un cálculo nuevo.', 409)
    if _meaning_view(quick_calc.definitions(db, business, str(row['analysis_id']))) != _meaning_view(row['definitions']):
        raise WebError('Los significados de los datos han cambiado desde ese cálculo. Pide un cálculo nuevo.', 409)
    rows = {t['alias']: r for t in row['request']['tables'] for r in tables_of(db, business, row['analysis_id']) if str(r['id']) == t['id']}
    if len(rows) != len(row['request']['tables']):
        raise WebError('Los datos de ese cálculo ya no están disponibles.', 409)
    return row, done, source, rows


def _version_fields(db, business, row, done, source, rows, metric_keys, turn_id):
    frozen = signature(db, business, row['analysis_id'], rows)
    frozen['dataset_version'] = source['dataset_version']
    tables = [dict(alias=t['alias'], file_keys=sorted({file_key(n) for n in t['original_names']}), original_names=t['original_names'])
              for t in row['request']['tables']]
    provenance = dict(turn_id=str(turn_id), calculation_id=str(row['id']), execution_id=str(done['id']),
                      analysis_id=str(row['analysis_id']), dataset_version=source['dataset_version'],
                      identity_sha256=row['identity_sha256'], code_sha256=done['code_sha256'])
    return dict(code=row['request']['code'], code_sha256=hashlib.sha256(row['request']['code'].encode()).hexdigest(),
                tables=tables, metric_keys=metric_keys, definitions=row['definitions'], signature=frozen,
                signature_sha256=digest(frozen), provenance=provenance)


def create(config, business, data):
    """Owner button under a published calculation: version 1 and its first value, copied, not rerun."""
    key = identifier(data.get('request_key'))
    turn_id, calculation_id = identifier(data.get('turn_id')), identifier(data.get('calculation_id'))
    name = bounded(data.get('name'), 'el nombre del indicador', 120)
    metric_keys = data.get('metric_keys')
    request = dict(turn_id=str(turn_id), calculation_id=str(calculation_id), name=name, metric_keys=metric_keys)
    with connect(config) as db, db.transaction():
        memory.lock(db, business)
        prior, sha = receipt(db, business, key, 'create', request)
        if prior:
            return prior
        row, done, source, rows = published(db, business, turn_id, calculation_id, metric_keys)
        fields = _version_fields(db, business, row, done, source, rows, metric_keys, turn_id)
        reason, detail, basis = check(db, business, fields['signature'], row['analysis_id'], rows)
        if reason:
            raise WebError('Los datos de ese cálculo ya no son válidos para guardarlo. Pide un cálculo nuevo.', 409)
        indicator, version, value = uuid4(), uuid4(), uuid4()
        db.execute('INSERT INTO saved_indicators(id,business_id,dataset_id,name,status) VALUES (%s,%s,%s,%s,%s)',
                   (indicator, business, source['dataset_id'], name, 'active'))
        _insert_version(db, business, indicator, version, 1, 'active', fields, applies_from=source['dataset_version'])
        db.execute('''INSERT INTO indicator_values(id,business_id,indicator_id,version_id,analysis_id,dataset_version,status,metrics,
            meanings_basis,execution_id,computed_at) VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,%s,%s,now())''',
                   (value, business, indicator, version, row['analysis_id'], source['dataset_version'],
                    Jsonb({k: done['result']['metrics'][k] for k in metric_keys}), Jsonb(basis), done['id']))
        reconcile(db, business)
        bump(db, business)
        result = dict(indicator_id=str(indicator), version_id=str(version), value_id=str(value))
        remember(db, business, key, 'create', sha, result)
    return result


def _insert_version(db, business, indicator, version, number, state, fields, *, applies_from=None, comparison=None):
    db.execute('''INSERT INTO indicator_versions(id,business_id,indicator_id,version,state,code,code_sha256,tables,metric_keys,
        definitions,signature,signature_sha256,provenance,applies_from,comparison,confirmed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='active' THEN now() END)''',
               (version, business, indicator, number, state, fields['code'], fields['code_sha256'], Jsonb(fields['tables']),
                Jsonb(fields['metric_keys']), Jsonb(fields['definitions']), Jsonb(fields['signature']),
                fields['signature_sha256'], Jsonb(fields['provenance']), applies_from,
                Jsonb(comparison) if comparison is not None else None, state))


# ---- Queue ---------------------------------------------------------------------------

def reconcile(db, business):
    """Idempotent gaps only: every active version x every eligible dataset version from applies_from."""
    created = 0
    for version in db.execute('''SELECT x.* FROM indicator_versions x JOIN saved_indicators i ON i.id=x.indicator_id
            WHERE x.business_id=%s AND x.state='active' AND i.status='active' ''', (business,)).fetchall():
        indicator = db.execute('SELECT dataset_id FROM saved_indicators WHERE id=%s', (version['indicator_id'],)).fetchone()
        for item in eligible(db, business, indicator['dataset_id']):
            if item['dataset_version'] < (version['applies_from'] or 1):
                continue
            created += db.execute('''INSERT INTO indicator_values(id,business_id,indicator_id,version_id,analysis_id,dataset_version,status)
                VALUES (%s,%s,%s,%s,%s,%s,'pending') ON CONFLICT (indicator_id,version_id,analysis_id) DO NOTHING''',
                                  (uuid4(), business, version['indicator_id'], version['id'], item['analysis_id'],
                                   item['dataset_version'])).rowcount
    return created


def revoke(db, business, analysis):
    """A corrected dataset version: its values stay for audit but are never current or a baseline."""
    count = db.execute("""UPDATE indicator_values SET status='revoked',reason='corrected',metrics=NULL,updated_at=now()
        WHERE business_id=%s AND analysis_id=%s AND status<>'revoked'""", (business, analysis)).rowcount
    requeue_comparisons(db, business)
    return count


def revalidate(db, business):
    """Business knowledge changed (inside its writer transaction and memory.lock): every completed value is checked
    again against its version. One whose data, meanings or basis no longer match stops with the reason; a stop is
    never undone here, the repair is the owner's new version. Unchanged values keep their state."""
    values = db.execute("""SELECT v.* FROM indicator_values v JOIN indicator_versions x ON x.id=v.version_id
        WHERE v.business_id=%s AND v.status='completed' AND x.state='active' ORDER BY v.id""", (business,)).fetchall()
    if not values:
        return 0
    effective, versions, changed = ctx.effective(db, business), {}, 0
    for value in values:
        version = versions.get(value['version_id']) or db.execute('SELECT * FROM indicator_versions WHERE id=%s',
                                                                  (value['version_id'],)).fetchone()
        versions[value['version_id']] = version
        source = dataset_of(db, business, value['analysis_id'])
        if not source or source['corrected']:
            db.execute("UPDATE indicator_values SET status='revoked',reason='corrected',metrics=NULL,updated_at=now() WHERE id=%s",
                       (value['id'],))
            changed += 1
            continue
        rows, failure = mapping(db, business, value['analysis_id'], version['tables'])
        reason, detail, basis = check(db, business, version['signature'], value['analysis_id'], rows, effective) if rows else (*failure, None)
        if reason:
            db.execute("""UPDATE indicator_values SET status='unavailable',reason=%s,detail=%s,metrics=NULL,next_attempt_at=NULL,
                updated_at=now() WHERE id=%s""", (reason, (detail or '')[:500], value['id']))
            changed += 1
        elif basis != value['meanings_basis']:
            db.execute('UPDATE indicator_values SET meanings_basis=%s,updated_at=now() WHERE id=%s', (Jsonb(basis), value['id']))
            changed += 1
    requeue_comparisons(db, business)
    if changed:
        bump(db, business)
    return changed


# ---- Projection and freshness --------------------------------------------------------

def current_values(db, business, indicator_id):
    """Values of the active version, latest eligible dataset version first (never by computation time)."""
    return db.execute('''SELECT v.* FROM indicator_values v JOIN indicator_versions x ON x.id=v.version_id
        WHERE v.business_id=%s AND v.indicator_id=%s AND x.state='active' AND v.status<>'revoked'
        ORDER BY v.dataset_version DESC''', (business, indicator_id)).fetchall()


def projection(db, business):
    """Owner-visible state of every indicator; its digest drives knowledge_heads."""
    items = []
    for indicator in db.execute('SELECT * FROM saved_indicators WHERE business_id=%s ORDER BY created_at,id', (business,)).fetchall():
        values = current_values(db, business, indicator['id'])
        latest = values[0] if values else None
        version = db.execute("SELECT id,version FROM indicator_versions WHERE indicator_id=%s AND state='active'",
                             (indicator['id'],)).fetchone()
        proposed = db.execute("SELECT id,version,comparison FROM indicator_versions WHERE indicator_id=%s AND state='proposed' ORDER BY version",
                              (indicator['id'],)).fetchall()
        items.append(dict(id=str(indicator['id']), name=indicator['name'], status=indicator['status'],
                          version=version['version'] if version else None,
                          latest=dict(status=latest['status'], dataset_version=latest['dataset_version'], metrics=latest['metrics'],
                                      reason=latest['reason'], meanings_basis=latest['meanings_basis']) if latest else None,
                          proposed=[dict(version=p['version'], comparison=(p['comparison'] or {}).get('state')) for p in proposed]))
    return items


def bump(db, business):
    """Raise the indicators revision only when the owner-visible projection changed (caller holds memory.lock)."""
    sha = digest(projection(db, business))
    row = db.execute('''INSERT INTO knowledge_heads(business_id,indicators_revision,indicators_sha256) VALUES (%s,1,%s)
        ON CONFLICT (business_id) DO UPDATE SET indicators_revision=knowledge_heads.indicators_revision+1,indicators_sha256=EXCLUDED.indicators_sha256
        WHERE knowledge_heads.indicators_sha256<>EXCLUDED.indicators_sha256 RETURNING indicators_revision''', (business, sha)).fetchone()
    return row['indicators_revision'] if row else None


# ---- Worker --------------------------------------------------------------------------

def _classify(result):
    """(outcome, reason) by cause, never by searching the error text."""
    status = result['status']
    if status == 'completed':
        return 'completed', None
    if status == 'interrupted' or (status == 'failed' and result['issue']):
        return 'transient', 'host'  # Recovered run, or a host/transport failure after admission.
    if status in ('timed_out', 'resource_limit'):
        return 'resource', 'resource_limit'
    if status == 'invalid_output':
        return 'structural', 'invalid_result'
    return 'structural', 'program_failed'


def _defer(db, value, attempt_no):
    delay = BACKOFF[min(attempt_no - 1, len(BACKOFF) - 1)]
    db.execute('UPDATE indicator_values SET next_attempt_at=%s,updated_at=now() WHERE id=%s', (now() + timedelta(seconds=delay), value['id']))


def _unavailable(db, business, value, reason, detail):
    db.execute("""UPDATE indicator_values SET status='unavailable',reason=%s,detail=%s,metrics=NULL,next_attempt_at=NULL,updated_at=now()
        WHERE id=%s AND status='pending'""", (reason, (detail or '')[:500], value['id']))


def _freeze(db, business, value, version):
    """Write the attempt (frozen identity and key) before any Docker call, or decide without running."""
    source = dataset_of(db, business, value['analysis_id'])
    if not source or source['corrected'] or source['status'] != 'ready':
        db.execute("UPDATE indicator_values SET status='revoked',reason='corrected',updated_at=now() WHERE id=%s", (value['id'],))
        return None
    rows, failure = mapping(db, business, value['analysis_id'], version['tables'])
    if failure:
        _unavailable(db, business, value, *failure)
        return None
    reason, detail, basis = check(db, business, version['signature'], value['analysis_id'], rows)
    if reason:
        _unavailable(db, business, value, reason, detail)
        return None
    number = (db.execute('SELECT max(attempt_no) AS n FROM indicator_attempts WHERE value_id=%s', (value['id'],)).fetchone()['n'] or 0) + 1
    identity = dict(code_sha256=version['code_sha256'], signature_sha256=version['signature_sha256'],
                    definitions_sha256=digest(version['definitions']), meanings_basis=basis,
                    tables=[dict(alias=a, table_id=str(r['id']), metadata_version=ctx.table_version(db, business, r['id']))
                            for a, r in sorted(rows.items())])
    attempt = db.execute('''INSERT INTO indicator_attempts(id,business_id,purpose,value_id,version_id,analysis_id,attempt_no,identity,admission)
        VALUES (%s,%s,'value',%s,%s,%s,%s,%s,'reserved') RETURNING *''',
                         (uuid4(), business, value['id'], version['id'], value['analysis_id'], number, Jsonb(identity))).fetchone()
    db.execute('UPDATE indicator_values SET latest_attempt_id=%s,updated_at=now() WHERE id=%s', (attempt['id'], value['id']))
    return attempt


def _identity_holds(db, business, attempt, version):
    """Every table the attempt froze keeps its metadata version (data, columns, profile, names, status) and the
    current one-to-one mapping still picks exactly those tables: a new competing file makes it ambiguous."""
    frozen = attempt['identity']['tables']
    if any(ctx.table_version(db, business, t['table_id']) != t['metadata_version'] for t in frozen):
        return False
    rows, _ = mapping(db, business, attempt['analysis_id'], version['tables'])
    return bool(rows) and {a: str(r['id']) for a, r in rows.items()} == {t['alias']: t['table_id'] for t in frozen}


def _run(config, business, attempt, version):
    """Outside any transaction: the terminal execution of this attempt, None when refused, raises if open."""
    key = PREFIX + str(attempt['id'])
    with connect(config) as db:
        found = attempt['execution_id'] or (db.execute('SELECT id FROM executions WHERE business_id=%s AND analysis_id=%s AND request_key=%s',
                                                       (business, attempt['analysis_id'], key)).fetchone() or {}).get('id')
        if found is None and not _identity_holds(db, business, attempt, version):
            return None, 'identity_changed'  # Never admitted: the next attempt freezes the current tables.
    if found is None:
        try:
            result = execution.execute(config, business, attempt['analysis_id'], code=version['code'],
                                       tables={t['alias']: t['table_id'] for t in attempt['identity']['tables']},
                                       definitions=version['definitions'], request_key=key, timeout=TIMEOUT,
                                       max_input_bytes=MAX_INPUT_BYTES)
        except Exception as error:
            with connect(config) as db:
                found = (db.execute('SELECT id FROM executions WHERE business_id=%s AND analysis_id=%s AND request_key=%s',
                                    (business, attempt['analysis_id'], key)).fetchone() or {}).get('id')
            if found is None:
                return None, quick_calc._reason(error)
            result = execution.get_execution(config, business, found)
    else:
        result = execution.get_execution(config, business, found)
    with connect(config) as db:
        db.execute("""UPDATE indicator_attempts SET admission='admitted',execution_id=%s,runtime=%s
            WHERE id=%s AND execution_id IS NULL""", (result['id'], Jsonb(result['environment']), attempt['id']))
    if result['status'] not in TERMINAL:
        if execution.recover_execution(config, business, result['id']) is None:
            raise quick_calc.Unresolved('An indicator attempt is still open.')
        result = execution.get_execution(config, business, result['id'])
    return result, None


def process(config, business, value_id):
    """One attempt for one pending value. Returns True when something was done."""
    with connect(config) as db:
        if not db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,40)) AS locked', (str(value_id),)).fetchone()['locked']:
            return False
        with db.transaction():
            memory.lock(db, business)
            value = db.execute("SELECT * FROM indicator_values WHERE business_id=%s AND id=%s AND status='pending'",
                               (business, value_id)).fetchone()
            if not value:
                return False
            version = db.execute('''SELECT x.* FROM indicator_versions x JOIN saved_indicators i ON i.id=x.indicator_id
                WHERE x.id=%s AND x.state='active' AND i.status='active' ''', (value['version_id'],)).fetchone()
            if not version:
                return False
            attempt = db.execute('SELECT * FROM indicator_attempts WHERE value_id=%s AND outcome IS NULL ORDER BY attempt_no DESC LIMIT 1',
                                 (value_id,)).fetchone() or _freeze(db, business, value, version)
            if attempt is None:
                bump(db, business)
                return True
        try:
            result, refusal = _run(config, business, attempt, version)
        except quick_calc.Unresolved:
            # Left open, never relabelled; step aside so it cannot starve other values.
            db.execute('UPDATE indicator_values SET next_attempt_at=%s WHERE id=%s', (now() + timedelta(seconds=BACKOFF[0]), value_id))
            return False
        with db.transaction():
            memory.lock(db, business)
            value = db.execute('SELECT * FROM indicator_values WHERE id=%s', (value_id,)).fetchone()
            outcome, reason = _publish(db, business, value, version, attempt, result, refusal)
            db.execute('UPDATE indicator_attempts SET outcome=%s,reason=%s,finished_at=now(),admission=CASE WHEN execution_id IS NULL '
                       "THEN 'refused' ELSE admission END WHERE id=%s", (outcome, reason, attempt['id']))
            bump(db, business)
    return True


def _publish(db, business, value, version, attempt, result, refusal):
    """Record the attempt's effect only if version, data and meanings still match it."""
    if value['status'] != 'pending':
        return 'structural', 'superseded'
    if refusal == 'identity_changed' or (result is not None and not _identity_holds(db, business, attempt, version)):
        return 'structural', 'identity_changed'  # The value stays pending; a new attempt freezes the current tables.
    if result is None:
        if refusal == 'input_too_large':
            _unavailable(db, business, value, 'resource_limit', 'Los datos superan el límite del cálculo.')
            return 'structural', 'resource_limit'
        _defer(db, value, attempt['attempt_no'])
        return 'transient', refusal
    outcome, reason = _classify(result)
    if outcome == 'transient':
        _defer(db, value, attempt['attempt_no'])
        return 'transient', reason
    if outcome == 'resource':
        retried = db.execute("SELECT count(*) AS n FROM indicator_attempts WHERE value_id=%s AND reason='resource_limit'",
                             (value['id'],)).fetchone()['n']
        if retried < RESOURCE_RETRIES:
            _defer(db, value, attempt['attempt_no'])
            return 'transient', 'resource_limit'
        _unavailable(db, business, value, 'resource_limit', result['status'])
        return 'structural', 'resource_limit'
    if outcome == 'structural':
        stderr = ((result['logs'] or {}).get('stderr') or '')[-500:]
        _unavailable(db, business, value, reason, stderr)
        return 'structural', reason
    metrics = (result['result'] or {}).get('metrics', {})
    missing = [k for k in version['metric_keys'] if k not in metrics]
    if missing:
        _unavailable(db, business, value, 'metric_missing', ', '.join(missing)[:500])
        return 'structural', 'metric_missing'
    current = db.execute("SELECT state FROM indicator_versions WHERE id=%s", (version['id'],)).fetchone()
    source = dataset_of(db, business, value['analysis_id'])
    if current['state'] != 'active' or not source or source['corrected']:
        return 'structural', 'superseded'
    rows, failure = mapping(db, business, value['analysis_id'], version['tables'])
    reason, detail, basis = check(db, business, version['signature'], value['analysis_id'], rows) if rows else (failure[0], failure[1], None)
    if reason:
        _unavailable(db, business, value, reason, detail)
        return 'structural', reason
    db.execute("""UPDATE indicator_values SET status='completed',metrics=%s,meanings_basis=%s,execution_id=%s,reason=NULL,detail=NULL,
        next_attempt_at=NULL,computed_at=now(),updated_at=now() WHERE id=%s""",
               (Jsonb({k: metrics[k] for k in version['metric_keys']}), Jsonb(basis), result['id'], value['id']))
    return 'completed', None


def work_once(config):
    """One due comparison or value attempt for any business; the worker alternates this with chat turns."""
    return _compare_once(config) or _values_once(config)


def _values_once(config):
    with connect(config) as db:
        due = db.execute("""SELECT v.id,v.business_id FROM indicator_values v JOIN saved_indicators i ON i.id=v.indicator_id
            JOIN indicator_versions x ON x.id=v.version_id
            WHERE v.status='pending' AND i.status='active' AND x.state='active'
              AND (v.next_attempt_at IS NULL OR v.next_attempt_at<=now())
            ORDER BY v.next_attempt_at NULLS FIRST,v.created_at LIMIT 5""").fetchall()
    return any(process(config, row['business_id'], row['id']) for row in due)


# ---- Repair: proposed version, comparison, confirmation -------------------------------

POLICY = 'indicator-compare-1'
COMPARISON_REASONS = {
    'program_failed': 'La fórmula nueva falla con los datos anteriores; pasa, por ejemplo, si una columna cambió de nombre.',
    'no_baseline': 'No hay un valor anterior calculado con el que comparar.',
    'metric_missing': 'Con los datos anteriores, la fórmula nueva no devuelve todas las cifras guardadas.',
}


def comparison_reason(code):
    """The owner-facing sentence for why a comparison is unavailable; never a bare code."""
    if not code:
        return None
    return COMPARISON_REASONS.get(code) or REASONS.get(code) or 'No se ha podido ejecutar la comparación.'


def same(a, b):
    """bool/string/null: same type and exact; int/int exact; numbers with a float: fixed relative policy."""
    if any(isinstance(x, (bool, str)) or x is None for x in (a, b)):
        return type(a) is type(b) and a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(1e-9, 1e-9 * max(abs(a), abs(b)))
    return False


def _sealed(receipt_body):
    return {**receipt_body, 'sha256': digest(receipt_body)}


def _active(db, indicator_id):
    return db.execute("SELECT * FROM indicator_versions WHERE indicator_id=%s AND state='active'", (indicator_id,)).fetchone()


def _indicator(db, business, indicator_id, lock=False):
    row = db.execute('SELECT * FROM saved_indicators WHERE business_id=%s AND id=%s' + (' FOR UPDATE' if lock else ''),
                     (business, indicator_id)).fetchone()
    if not row:
        raise WebError('Ese indicador no existe en este negocio.', 404)
    return row


def propose(config, business, indicator_id, data):
    """A repaired formula from a published calculation, as a proposed version; its comparison is queued."""
    key = identifier(data.get('request_key'))
    indicator_id, turn_id = identifier(indicator_id), identifier(data.get('turn_id'))
    calculation_id, expected = identifier(data.get('calculation_id')), identifier(data.get('expected_active_version_id'))
    request = dict(indicator_id=str(indicator_id), turn_id=str(turn_id), calculation_id=str(calculation_id), expected=str(expected))
    with connect(config) as db, db.transaction():
        memory.lock(db, business)
        prior, sha = receipt(db, business, key, 'propose', request)
        if prior:
            return prior
        indicator = _indicator(db, business, indicator_id, lock=True)
        active = _active(db, indicator_id)
        if indicator['status'] != 'active' or not active or active['id'] != expected:
            raise WebError('El indicador ha cambiado. Recarga antes de proponer otra versión.', 409)
        row, done, source, rows = published(db, business, turn_id, calculation_id, active['metric_keys'])
        if source['dataset_id'] != indicator['dataset_id']:
            raise WebError('Ese cálculo usa otros datos distintos de los del indicador.', 409)
        fields = _version_fields(db, business, row, done, source, rows, active['metric_keys'], turn_id)
        if check(db, business, fields['signature'], row['analysis_id'], rows)[0]:
            raise WebError('Los datos de ese cálculo ya no son válidos. Pide un cálculo nuevo.', 409)
        number = db.execute('SELECT max(version) AS n FROM indicator_versions WHERE indicator_id=%s', (indicator_id,)).fetchone()['n'] + 1
        version = uuid4()
        _insert_version(db, business, indicator_id, version, number, 'proposed', fields,
                        comparison=dict(state='pending', policy=POLICY, attempts=0))
        bump(db, business)
        result = dict(indicator_id=str(indicator_id), version_id=str(version), version=number)
        remember(db, business, key, 'propose', sha, result)
    return result


def _baseline(db, business, indicator_id):
    """Latest eligible completed value of the active version, by dataset version."""
    for value in current_values(db, business, indicator_id):
        source = dataset_of(db, business, value['analysis_id'])
        if value['status'] == 'completed' and source and not source['corrected']:
            return value
    return None


def _compare_once(config):
    with connect(config) as db:
        due = db.execute("""SELECT x.id,x.business_id FROM indicator_versions x JOIN saved_indicators i ON i.id=x.indicator_id
            WHERE x.state='proposed' AND i.status='active' AND x.comparison->>'state'='pending'
              AND (x.comparison->>'next_attempt_at' IS NULL OR (x.comparison->>'next_attempt_at')::timestamptz<=now())
            ORDER BY x.created_at LIMIT 5""").fetchall()
    return any(compare(config, row['business_id'], row['id']) for row in due)


def compare(config, business, version_id):
    """Run the proposed code on the baseline's data and seal a typed comparison receipt."""
    with connect(config) as db:
        if not db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,41)) AS locked', (str(version_id),)).fetchone()['locked']:
            return False
        with db.transaction():
            memory.lock(db, business)
            version = db.execute("SELECT * FROM indicator_versions WHERE business_id=%s AND id=%s AND state='proposed'",
                                 (business, version_id)).fetchone()
            if not version or version['comparison'].get('state') != 'pending':
                return False
            attempt = db.execute("""SELECT * FROM indicator_attempts WHERE purpose='comparison' AND version_id=%s AND outcome IS NULL
                ORDER BY attempt_no DESC LIMIT 1""", (version_id,)).fetchone()
            if not attempt:
                base = _baseline(db, business, version['indicator_id'])
                rows, failure = mapping(db, business, base['analysis_id'], version['tables']) if base else (None, ('no_baseline', ''))
                if failure:
                    _seal(db, business, version, dict(state='unavailable', reason=failure[0], detail=failure[1]))
                    return True
                number = (db.execute("SELECT max(attempt_no) AS n FROM indicator_attempts WHERE purpose='comparison' AND version_id=%s",
                                     (version_id,)).fetchone()['n'] or 0) + 1
                identity = dict(code_sha256=version['code_sha256'], definitions_sha256=digest(version['definitions']),
                                baseline=dict(value_id=str(base['id']), version_id=str(base['version_id']),
                                              analysis_id=str(base['analysis_id']), dataset_version=base['dataset_version'],
                                              metrics=base['metrics'], meanings_basis=base['meanings_basis'],
                                              meanings=meanings_note(base['meanings_basis'])),
                                tables=[dict(alias=a, table_id=str(r['id']), metadata_version=ctx.table_version(db, business, r['id']))
                                        for a, r in sorted(rows.items())])
                attempt = db.execute('''INSERT INTO indicator_attempts(id,business_id,purpose,version_id,analysis_id,attempt_no,identity,admission)
                    VALUES (%s,%s,'comparison',%s,%s,%s,%s,'reserved') RETURNING *''',
                                     (uuid4(), business, version_id, base['analysis_id'], number, Jsonb(identity))).fetchone()
        try:
            result, refusal = _run(config, business, attempt, version)
        except quick_calc.Unresolved:
            return False
        with db.transaction():
            memory.lock(db, business)
            version = db.execute('SELECT * FROM indicator_versions WHERE id=%s', (version_id,)).fetchone()
            outcome, reason = ('transient', refusal) if result is None else _classify(result)
            stale = _stale_comparison(db, business, version, attempt, refusal)
            if stale:
                # Nothing is sealed from a stale run; a pending comparison takes a new baseline on its next attempt.
                outcome, reason = 'structural', stale
            elif outcome in ('transient', 'resource') and attempt['attempt_no'] <= len(BACKOFF) and refusal != 'input_too_large':
                delay = BACKOFF[min(attempt['attempt_no'] - 1, len(BACKOFF) - 1)]
                db.execute("UPDATE indicator_versions SET comparison=comparison || %s WHERE id=%s",
                           (Jsonb(dict(next_attempt_at=(now() + timedelta(seconds=delay)).isoformat())), version_id))
            elif outcome != 'completed':
                _seal(db, business, version, dict(state='unavailable', reason=reason or refusal,
                                                  detail=((result or {}).get('logs') or {}).get('stderr', '')[-300:]))
            else:
                base = attempt['identity']['baseline']
                metrics = (result['result'] or {}).get('metrics', {})
                rows = [dict(metric=k, before=base['metrics'].get(k), after=metrics.get(k), present=k in metrics,
                             same=k in metrics and same(base['metrics'].get(k), metrics.get(k))) for k in version['metric_keys']]
                state = 'unavailable' if not all(r['present'] for r in rows) else 'match' if all(r['same'] for r in rows) else 'mismatch'
                _seal(db, business, version, dict(state=state, baseline=base, execution_id=str(result['id']), metrics=rows,
                                                  reason='metric_missing' if state == 'unavailable' else None))
            db.execute('UPDATE indicator_attempts SET outcome=%s,reason=%s,finished_at=now(),admission=CASE WHEN execution_id IS NULL '
                       "THEN 'refused' ELSE admission END WHERE id=%s",
                       ('completed' if outcome == 'completed' else 'transient' if outcome in ('transient', 'resource') else 'structural',
                        reason or refusal, attempt['id']))
            bump(db, business)
    return True


def _baseline_valid(db, business, base):
    """A receipt's baseline is still a completed value of uncorrected data."""
    value = db.execute('SELECT status FROM indicator_values WHERE business_id=%s AND id=%s', (business, base['value_id'])).fetchone()
    source = dataset_of(db, business, base['analysis_id'])
    return bool(value and value['status'] == 'completed' and source and not source['corrected'])


def _stale_comparison(db, business, version, attempt, refusal):
    if version['state'] != 'proposed' or (version['comparison'] or {}).get('state') != 'pending':
        return 'superseded'
    if not _baseline_valid(db, business, attempt['identity']['baseline']):
        return 'baseline_changed'
    if refusal == 'identity_changed' or not _identity_holds(db, business, attempt, version):
        return 'identity_changed'
    return None


def _seal(db, business, version, body):
    """A comparison receipt is immutable; a revoked one is kept in history."""
    sealed = _sealed(dict(body, policy=POLICY, created_at=now().isoformat()))
    history = (version['comparison'] or {}).get('history', [])
    db.execute('UPDATE indicator_versions SET comparison=%s WHERE id=%s', (Jsonb({**sealed, 'history': history}), version['id']))
    bump(db, business)


def requeue_comparisons(db, business):
    """A receipt whose baseline stopped being a completed value of uncorrected data is kept as history; compare again."""
    for version in db.execute("""SELECT * FROM indicator_versions WHERE business_id=%s AND state='proposed'
            AND comparison ? 'baseline'""", (business,)).fetchall():
        base = version['comparison']['baseline']
        if _baseline_valid(db, business, base):
            continue
        source = dataset_of(db, business, base['analysis_id'])
        old = {k: v for k, v in version['comparison'].items() if k != 'history'}
        why = 'baseline_corrected' if not source or source['corrected'] else 'baseline_changed'
        db.execute('UPDATE indicator_versions SET comparison=%s WHERE id=%s',
                   (Jsonb(dict(state='pending', policy=POLICY, history=[*version['comparison'].get('history', []),
                                                                         dict(old, revoked=why)])), version['id']))


def confirm(config, business, indicator_id, version_id, data):
    """The owner's button: activates exactly this proposal after revalidating it; a match is not required."""
    key = identifier(data.get('request_key'))
    indicator_id, version_id = identifier(indicator_id), identifier(version_id)
    expected = identifier(data.get('expected_active_version_id'))
    comparison_sha = data.get('comparison_sha')
    request = dict(indicator_id=str(indicator_id), version_id=str(version_id), expected=str(expected), comparison_sha=comparison_sha)
    with connect(config) as db:
        with db.transaction():
            memory.lock(db, business)
            prior, sha = receipt(db, business, key, 'confirm', request)
            if prior:
                return prior
            indicator = _indicator(db, business, indicator_id, lock=True)
            active = _active(db, indicator_id)
            version = db.execute("SELECT * FROM indicator_versions WHERE business_id=%s AND id=%s AND indicator_id=%s",
                                 (business, version_id, indicator_id)).fetchone()
            if indicator['status'] != 'active' or not active or active['id'] != expected or not version or version['state'] != 'proposed':
                raise WebError('El indicador ha cambiado. Recarga antes de confirmar.', 409)
            comparison = version['comparison'] or {}
            if comparison.get('state') == 'pending':
                raise WebError('La comparación con los datos anteriores todavía se está haciendo.', 409)
            stale = bool(comparison.get('baseline')) and not _baseline_valid(db, business, comparison['baseline'])
            if stale:  # Committed before refusing, so the comparison really is repeated.
                requeue_comparisons(db, business)
                bump(db, business)
            else:
                result = _activate(db, business, indicator_id, version, active, comparison_sha)
                remember(db, business, key, 'confirm', sha, result)
        if stale:
            raise WebError('Los datos de la comparación han cambiado. Se está repitiendo; vuelve a revisarla.', 409)
    return result


def _activate(db, business, indicator_id, version, active, comparison_sha):
    if (version['comparison'] or {}).get('sha256') != comparison_sha:
        raise WebError('La comparación ha cambiado. Revísala antes de confirmar.', 409)
    provenance = version['provenance']
    row, done, calc_source, rows = published(db, business, identifier(provenance['turn_id']),
                                             identifier(provenance['calculation_id']), version['metric_keys'])
    reason, _, basis = check(db, business, version['signature'], row['analysis_id'], rows)
    if reason or calc_source['dataset_version'] != provenance['dataset_version']:
        raise WebError('Los datos o los significados de ese cálculo han cambiado. Pide un cálculo nuevo.', 409)
    db.execute("UPDATE indicator_versions SET state='superseded' WHERE id=%s", (active['id'],))
    db.execute("UPDATE indicator_versions SET state='discarded' WHERE indicator_id=%s AND state='proposed' AND id<>%s",
               (indicator_id, version['id']))
    db.execute("UPDATE indicator_versions SET state='active',confirmed_at=now(),applies_from=%s WHERE id=%s",
               (calc_source['dataset_version'], version['id']))
    db.execute('''INSERT INTO indicator_values(id,business_id,indicator_id,version_id,analysis_id,dataset_version,status,metrics,
        meanings_basis,execution_id,computed_at) VALUES (%s,%s,%s,%s,%s,%s,'completed',%s,%s,%s,now())
        ON CONFLICT (indicator_id,version_id,analysis_id) DO NOTHING''',
               (uuid4(), business, indicator_id, version['id'], row['analysis_id'], calc_source['dataset_version'],
                Jsonb({k: done['result']['metrics'][k] for k in version['metric_keys']}), Jsonb(basis), done['id']))
    db.execute('UPDATE saved_indicators SET revision=revision+1 WHERE id=%s', (indicator_id,))
    reconcile(db, business)
    bump(db, business)
    return dict(indicator_id=str(indicator_id), version_id=str(version['id']), state='active')


def retire(config, business, indicator_id, data):
    key = identifier(data.get('request_key'))
    indicator_id = identifier(indicator_id)
    expected = data.get('expected_revision')
    with connect(config) as db, db.transaction():
        memory.lock(db, business)
        prior, sha = receipt(db, business, key, 'retire', dict(indicator_id=str(indicator_id), expected=expected))
        if prior:
            return prior
        indicator = _indicator(db, business, indicator_id, lock=True)
        if indicator['revision'] != expected:
            raise WebError('El indicador ha cambiado. Recarga antes de retirarlo.', 409)
        db.execute("UPDATE saved_indicators SET status='retired',retired_at=now(),revision=revision+1 WHERE id=%s", (indicator_id,))
        bump(db, business)
        result = dict(indicator_id=str(indicator_id), status='retired')
        remember(db, business, key, 'retire', sha, result)
    return result


INSPECT_BYTES = 12 * 1024


INSPECT_NAMES = 2
INSPECT_NAME_CHARS = 100
INSPECT_PROPOSALS = 3
INSPECT_VALUES = 5


def _size(value):
    return len(memory.encoded(value).encode())


def inspect(db, business, indicator_id):
    """One indicator for the chat, at most INSPECT_BYTES of the whole serialized object.

    Room for the latest value's state is reserved first. If the base does not fit with it, it is cut in a
    fixed order, each cut said explicitly: proposals, then file names, then the code (its hash stays), then the
    metric keys. Without code and keys the base is a few hundred bytes, so this always ends inside the budget.
    Values go latest first; if the latest does not fit whole, a minimal record with its state takes its place
    and nothing older is offered instead. Definitions only when the whole object still fits."""
    indicator = _indicator(db, business, indicator_id)
    version = _active(db, indicator_id)
    if not version:
        raise WebError('Ese indicador no tiene una versión activa.', 409)
    proposals = db.execute("SELECT version,comparison FROM indicator_versions WHERE indicator_id=%s AND state='proposed' "
                           'ORDER BY version DESC', (indicator_id,)).fetchall()
    values = current_values(db, business, indicator_id)
    result = dict(indicator=dict(id=str(indicator['id']), name=indicator['name'], status=indicator['status'], label=LABEL),
                  version=dict(version=version['version'], code=version['code'], code_sha256=version['code_sha256'],
                               code_omitted=False, metric_keys=version['metric_keys'], metric_keys_omitted=False,
                               applies_from=version['applies_from'],
                               tables=[dict(alias=t['alias'], original_names=[n[:INSPECT_NAME_CHARS] for n in t['original_names'][:INSPECT_NAMES]],
                                            names_omitted=max(0, len(t['original_names']) - INSPECT_NAMES)) for t in version['tables']]),
                  proposed=[dict(version=p['version'], comparison=(p['comparison'] or {}).get('state'))
                            for p in proposals[:INSPECT_PROPOSALS]],
                  proposed_omitted=max(0, len(proposals) - INSPECT_PROPOSALS),
                  values=[], values_omitted=0, definitions_omitted=True)
    latest = values[0] if values else None
    reserve = [dict(dataset_version=latest['dataset_version'], status=latest['status'], omitted=True)] if latest else []

    def fits(candidate):
        return _size({**candidate, 'values': reserve, 'values_omitted': len(values)}) <= INSPECT_BYTES

    cuts = [lambda r: r.update(proposed=[], proposed_omitted=len(proposals)),
            lambda r: r['version'].update(tables=[dict(alias=t['alias'], original_names=[], names_omitted=len(t['original_names']))
                                                  for t in version['tables']]),
            lambda r: r['version'].update(code=None, code_omitted=True),
            lambda r: r['version'].update(metric_keys=[], metric_keys_omitted=True)]
    for cut in cuts:
        if fits(result):
            break
        cut(result)
    for index, value in enumerate(values):
        item = dict(dataset_version=value['dataset_version'], analysis_id=str(value['analysis_id']),
                    period=period_of(db, business, value['analysis_id']), status=value['status'], metrics=value['metrics'],
                    reason=REASONS.get(value['reason'], value['reason']) if value['reason'] else None,
                    detail=(value['detail'] or '')[:300] or None, meanings=meanings_note(value['meanings_basis']))
        # Room for the final omitted count, whatever it turns out to be.
        trial = {**result, 'values': [*result['values'], item], 'values_omitted': len(values)}
        if len(result['values']) < INSPECT_VALUES and _size(trial) <= INSPECT_BYTES:
            result['values'].append(item)
            continue
        if index == 0:
            result['values'] = reserve
        result['values_omitted'] = len(values) - len(result['values'])
        break
    with_definitions = {**result, 'definitions': version['definitions'], 'definitions_omitted': False}
    if _size(with_definitions) <= INSPECT_BYTES:
        result = with_definitions
    return result


def overview(db, business):
    """Owner page: every indicator with its version, values (latest first), proposals and receipts."""
    items = []
    for row in db.execute('SELECT * FROM saved_indicators WHERE business_id=%s ORDER BY status,name,id', (business,)).fetchall():
        active = _active(db, row['id'])
        values = []
        for value in current_values(db, business, row['id'])[:12]:
            values.append(dict(id=str(value['id']), dataset_version=value['dataset_version'], status=value['status'],
                               period=period_of(db, business, value['analysis_id']), metrics=value['metrics'],
                               display={k: display(v) for k, v in (value['metrics'] or {}).items()},
                               reason=REASONS.get(value['reason'], value['reason']) if value['reason'] else None,
                               detail=value['detail'], computed_at=value['computed_at'], meanings=meanings_note(value['meanings_basis'])))
        proposals = [dict(id=str(p['id']), version=p['version'],
                          comparison={**{k: v for k, v in (p['comparison'] or {}).items() if k != 'history'},
                                      'reason': comparison_reason((p['comparison'] or {}).get('reason')),
                                      'reason_code': (p['comparison'] or {}).get('reason')},
                          code=p['code'], created_at=p['created_at'])
                     for p in db.execute("SELECT * FROM indicator_versions WHERE indicator_id=%s AND state='proposed' ORDER BY version",
                                         (row['id'],)).fetchall()]
        items.append(dict(id=str(row['id']), name=row['name'], status=row['status'], revision=row['revision'], label=LABEL,
                          version=dict(id=str(active['id']), version=active['version'], code=active['code'],
                                       metric_keys=active['metric_keys'], applies_from=active['applies_from']) if active else None,
                          values=values, proposals=proposals))
    return items



def meanings_note(basis):
    """The owner-visible caveat of a value computed with inherited meanings, or None.

    current_meanings_confirmed covers the elements declared when the formula was saved; columns never
    declared stay unknown either way (listed in `undeclared`), so it is never a confirmation of every column."""
    return INHERITED.format(basis.get('dataset_version')) if basis and not basis.get('current_meanings_confirmed', True) else None


def period_of(db, business, analysis):
    row = db.execute('SELECT period_from,period_until FROM dataset_versions WHERE business_id=%s AND analysis_id=%s',
                     (business, analysis)).fetchone()
    return {'from': row['period_from'].isoformat() if row and row['period_from'] else None,
            'until': row['period_until'].isoformat() if row and row['period_until'] else None}


def display(value):
    """Owner-facing (and brief) formatting of a metric value; the raw value is kept alongside.

    Floats keep two decimals, or four below 1 so a ratio such as 0.0478 is not shown as 0,05."""
    from .engine import blocks
    if isinstance(value, bool):
        return 'sí' if value else 'no'
    if isinstance(value, int):
        return blocks.format_number(value, 0)
    if isinstance(value, float):
        return blocks.format_number(value, 2 if abs(value) >= 1 or value == 0 else 4)
    return '—' if value is None else str(value)
