"""Versioned UI selections resolved from business-scoped server content."""
from .web.errors import WebError, identifier
from .web.dashboard import presentation

SOURCE_FIELDS = ('source_id', 'source_version', 'kind', 'element_key')
FIELDS = ('report_id', 'report_version', 'kind', 'element_key')
MAX_REFERENCES = 8


def normalize(values):
    if not isinstance(values, list) or len(values) > MAX_REFERENCES:
        raise WebError('Selecciona como máximo ocho elementos.')
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise WebError('La selección no es válida.')
        fields = SOURCE_FIELDS if 'source_id' in value else FIELDS
        if set(value) != set(fields):
            raise WebError('La selección no es válida.')
        identity, version = fields[:2]
        item = dict(value, **{identity: str(identifier(value[identity]))})
        kinds = ('business', 'memory', 'conversation', 'data_model', 'engine_block') if fields == SOURCE_FIELDS else ('chart', 'metric', 'insight', 'section', 'report')
        if (item['kind'] not in kinds or
            any(not isinstance(item[k], str) or not 0 < len(item[k]) <= 180
                for k in (version, 'element_key'))):
            raise WebError('La selección no es válida.')
        if item not in result:
            if item['kind'] == 'conversation' and any(r.get('source_id') == item['source_id'] and r['kind'] == 'conversation' for r in result):
                raise WebError('Selecciona una sola versión de cada conversación.')
            result.append(item)
    return result


def pointers(payload, *, reports_only=False):
    refs = [r for r in (payload.get('context_references') or []) if not reports_only or 'report_id' in r]
    if legacy := payload.get('finding_reference'):
        refs.append(dict(report_id=legacy['report_id'], report_version=legacy['report_version'],
                         kind='insight', element_key=legacy['claim_key']))
    return refs


def resolve(reference, reviewed, display=None):
    if not reviewed.get('publishable') or reviewed.get('approved_sha256') != reference['report_version']:
        raise WebError('Un elemento seleccionado ha cambiado o se ha retirado. Vuelve a seleccionarlo.', 409)
    display = display or presentation(reviewed)
    kind, key = reference['kind'], reference['element_key']
    entries = {'chart': display['charts'], 'metric': display['highlights'], 'insight': display['claims']}
    if kind == 'report' and key == 'report':
        content = dict(key=key, title=display['title'], statement=display.get('summary') or display['title'])
        claims = [c['key'] for c in display['claims']]
    elif kind == 'section':
        text = {'summary': display.get('summary'), 'scope': display['scope']['coverage'],
                'limitations': '\n'.join(display['limitations'])}.get(key)
        labels = {'summary': 'Resumen', 'scope': 'Alcance', 'limitations': 'Limitaciones'}
        content = dict(key=key, title=labels.get(key), statement=text) if text else None
        claims = [c['key'] for c in display['claims']]
    else:
        content = next((x for x in entries.get(kind, []) if x['key'] == key), None)
        claims = [content['key'] if kind == 'insight' else content['claim_key']] if content else []
    if content is None:
        raise WebError('El elemento seleccionado no pertenece a este informe.', 409)
    return dict(**reference, title=content.get('title', content.get('label')),
                period=display['scope']['period'], report_title=display['title'],
                analysis_id=str(reviewed['analysis_id']), claim_keys=claims, content=content,
                authority='reviewed_report', selection_scope='whole_report' if kind == 'report' else 'report_element',
                status='available')


def resolve_source(reference, db, business):
    """Resolve business-scoped context without treating it as reviewed analysis."""
    from .web.business import profile
    if reference['kind'] == 'conversation':
        from .conversation_context import attachment
        return attachment(db, business, reference)
    if reference['kind'] == 'data_model':
        return resolve_data_model(reference, db, business)
    if reference['kind'] == 'engine_block':
        return resolve_engine_block(reference, db, business)
    kind, key = reference['kind'], reference['element_key']
    if kind == 'business' and key == 'profile' and reference['source_id'] == str(business):
        row = profile(db, business)
        version = str(row['profile_revision'])
        title = 'Presentación de ' + row['name']
        content = dict(key=key, title=title, statement=row['description'])
        details = dict(authority='owner_declared')
    elif kind == 'memory' and key == 'fact':
        row = db.execute("""SELECT r.*,s.origin_key,s.payload FROM memory_revisions r
            JOIN memory_sources s ON s.id=r.source_id AND s.business_id=r.business_id
            WHERE r.business_id=%s AND r.fact_id=%s ORDER BY r.revision DESC LIMIT 1""", (business, reference['source_id'])).fetchone()
        if not row or row['status'] in ('withdrawn', 'superseded'):
            raise WebError('La información seleccionada ya no está disponible.', 409)
        version = str(row['revision'])
        title = row['content']['statement'][:100]
        content = dict(key=key, title=title, statement=row['content']['statement'])
        details = dict(authority='business_memory', memory_status=row['status'],
                       memory_content=row['content'], alternatives=row.get('alternatives') or [],
                       provenance=dict(source_id=str(row['source_id']), origin_key=row['origin_key'],
                           kind=row['payload'].get('kind'), original_text=row['payload'].get('text'),
                           question=row['payload'].get('question')))
    else:
        raise WebError('El elemento seleccionado no pertenece a este negocio.', 409)
    if version != reference['source_version']:
        raise WebError('La información seleccionada ha cambiado. Vuelve a seleccionarla.', 409)
    return dict(**reference, title=title, content=content, status='available',
                report_title='Mi negocio', href='#my-business', **details)


def resolve_engine_block(reference, db, business):
    """One block of the current revision of a native v1 report: agent text, never reviewed evidence."""
    from .engine import blocks
    document, revision = identifier(reference['source_id']), identifier(reference['source_version'])
    row = db.execute('''SELECT d.current_revision_id,d.deleted_at,d.stale_reason,r.raw,w.id AS job_id,w.deleted_at AS job_deleted_at
        FROM report_documents d JOIN engine_document_revisions r
          ON r.business_id=d.business_id AND r.document_id=d.id AND r.id=%s
        LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id
        WHERE d.business_id=%s AND d.id=%s''', (revision, business, document)).fetchone()
    if (not row or row['deleted_at'] or row['job_deleted_at'] or row['stale_reason']
            or row['current_revision_id'] != revision):
        raise WebError('El fragmento del informe ha cambiado o se ha retirado. Vuelve a seleccionarlo.', 409)
    try:
        projection = blocks.parse(bytes(row['raw']))
    except blocks.BlocksError:
        raise WebError('El elemento seleccionado no pertenece a este informe.', 409) from None
    block = next((b for b in blocks.walk(projection['blocks']) if b['id'] == reference['element_key']), None)
    if block is None:
        raise WebError('El elemento seleccionado no pertenece a este informe.', 409)
    lines = blocks.block_lines(block)
    title = block.get('title') or block.get('label') or lines[0][:100]
    return dict(**reference, title=title, content=dict(key=block['id'], title=title, statement='\n'.join(lines)),
                status='available', report_title=projection['title'], href=f"#report/{row['job_id']}" if row['job_id'] else None,
                authority='engine_report', selection_scope='report_element')


def resolve_data_model(reference, db, business):
    """Resolve saved schemas and checks, without upgrading proposed business meaning."""
    from .data_knowledge import service
    row = service.latest(db, business, reference['source_id'])
    if (not row or str(row['revision']) != reference['source_version'] or
            not service.current(db, business, dict(analysis_id=reference['source_id'], revision=row['revision']))):
        raise WebError('El modelo de datos ha cambiado o ya no está disponible. Vuelve a seleccionarlo.', 409)
    body, key = row['body'], reference['element_key']
    if key == 'model':
        relations, tables = body['relations'], body['tables']
        title, scope = 'Mapa de relaciones', 'whole_data_model'
    elif key.startswith('table:'):
        table = next((t for t in body['tables'] if t['id'] == key.removeprefix('table:')), None)
        if not table:
            raise WebError('La tabla seleccionada no pertenece a este modelo.', 409)
        tables, relations = [table], []
        title, scope = f"Tabla: {table['name']}", 'table'
    elif key.startswith('relation:'):
        relation = next((r for r in body['relations'] if r['id'] == key.removeprefix('relation:')), None)
        if not relation:
            raise WebError('La relación seleccionada no pertenece a este modelo.', 409)
        relations = [relation]
        tables = [t for t in body['tables'] if t['id'] in (relation['source'], relation['target'])]
        names = {t['id']: t['name'] for t in tables}
        title = f"Relación: {names[relation['source']]} → {names[relation['target']]}"
        scope = 'relationship'
    else:
        raise WebError('El elemento seleccionado no pertenece a este modelo.', 409)
    statements = [f"{len(tables)} tablas · {len(relations)} relaciones"]
    if scope == 'table':
        statements = [title, f"{table['row_count']} filas",
                      'Columnas: ' + ', '.join(c['name'] for c in table['columns'])]
    names = {t['id']: t['name'] for t in tables}
    for relation in relations:
        statements.append(f"{names[relation['source']]} ({', '.join(relation['source_columns'])}) → "
                          f"{names[relation['target']]} ({', '.join(relation['target_columns'])}): "
                          f"{relation['semantic_status']} · {relation['verification']}" +
                          (f". {relation['description']}" if relation['description'] else ''))
    content = dict(key=key, title=title, statement='\n'.join(statements), tables=tables, relations=relations,
                   scope=body.get('scope'), inference=body.get('inference'),
                   discovery_limits=body.get('discovery', {}).get('limitations', []))
    return dict(**reference, title=title, content=content, status='available', authority='data_model',
                selection_scope=scope, analysis_id=str(row['analysis_id']), model_revision=row['revision'],
                report_title='Datos', href='#my-business')
