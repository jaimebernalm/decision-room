"""Versioned UI selections. Only server-resolved report content is evidence."""
from .web.errors import WebError, identifier
from .web.dashboard import presentation

FIELDS = ('report_id', 'report_version', 'kind', 'element_key')
MAX_REFERENCES = 8


def normalize(values):
    if not isinstance(values, list) or len(values) > MAX_REFERENCES:
        raise WebError('Selecciona como máximo ocho elementos.')
    result = []
    for value in values:
        if not isinstance(value, dict) or set(value) != set(FIELDS):
            raise WebError('La selección no es válida.')
        item = dict(value, report_id=str(identifier(value['report_id'])))
        if (item['kind'] not in ('chart', 'metric', 'insight', 'section') or
            any(not isinstance(item[k], str) or not 0 < len(item[k]) <= 180
                for k in ('report_version', 'element_key'))):
            raise WebError('La selección no es válida.')
        if item not in result:
            result.append(item)
    return result


def pointers(payload):
    refs = list(payload.get('context_references') or [])
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
