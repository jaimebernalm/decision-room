"""Versioned UI selections. Only server-resolved report content is evidence."""
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
        kinds = ('business', 'memory') if fields == SOURCE_FIELDS else ('chart', 'metric', 'insight', 'section')
        if (item['kind'] not in kinds or
            any(not isinstance(item[k], str) or not 0 < len(item[k]) <= 180
                for k in (version, 'element_key'))):
            raise WebError('La selección no es válida.')
        if item not in result:
            result.append(item)
    return result


def pointers(payload, *, reports_only=False):
    refs = [r for r in (payload.get('context_references') or []) if not reports_only or 'report_id' in r]
    if legacy := payload.get('finding_reference'):
        refs.append(dict(report_id=legacy['report_id'], report_version=legacy['report_version'],
                         kind='insight', element_key=legacy['claim_key']))
    return refs


def resolve(reference, reviewed):
    if not reviewed.get('publishable') or reviewed.get('approved_sha256') != reference['report_version']:
        raise WebError('Un elemento seleccionado ha cambiado o se ha retirado. Vuelve a seleccionarlo.', 409)
    display = presentation(reviewed)
    kind, key = reference['kind'], reference['element_key']
    entries = {'chart': display['charts'], 'metric': display['highlights'], 'insight': display['claims']}
    if kind == 'section':
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
                status='available')


def resolve_source(reference, db, business):
    """Resolve owner-declared context, never treating it as reviewed analysis."""
    from .web.business import profile
    kind, key = reference['kind'], reference['element_key']
    if kind == 'business' and key == 'profile' and reference['source_id'] == str(business):
        row = profile(db, business)
        version = str(row['profile_revision'])
        title = 'Presentación de ' + row['name']
        content = dict(key=key, title=title, statement=row['description'])
        details = dict(authority='owner_declared')
    elif kind == 'memory' and key == 'fact':
        row = db.execute("""SELECT * FROM memory_revisions WHERE business_id=%s AND fact_id=%s
            ORDER BY revision DESC LIMIT 1""", (business, reference['source_id'])).fetchone()
        if not row or row['status'] in ('withdrawn', 'superseded'):
            raise WebError('La información seleccionada ya no está disponible.', 409)
        version = str(row['revision'])
        title = row['content']['statement'][:100]
        content = dict(key=key, title=title, statement=row['content']['statement'])
        details = dict(authority='business_memory', memory_status=row['status'],
                       memory_content=row['content'], alternatives=row.get('alternatives') or [])
    else:
        raise WebError('El elemento seleccionado no pertenece a este negocio.', 409)
    if version != reference['source_version']:
        raise WebError('La información seleccionada ha cambiado. Vuelve a seleccionarla.', 409)
    return dict(**reference, title=title, content=content, status='available',
                report_title='Mi negocio', href='#my-business', **details)
