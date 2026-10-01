"""Owner-defined presentation groups, independent of analytical memory."""
import re
from uuid import UUID

from psycopg.types.json import Jsonb

from ..database import connect
from .errors import WebError

DEFAULT_GROUPS = [
    {'id': 'business', 'name': 'Sobre el negocio', 'description': 'Actividad del negocio, productos, clientes y características generales.'},
    {'id': 'operations', 'name': 'Operativa', 'description': 'Horarios, procesos, recursos disponibles y significado de los datos.'},
    {'id': 'goals', 'name': 'Objetivos y preferencias', 'description': 'Prioridades, metas y preferencias para orientar las recomendaciones.'},
]


def load(db, business):
    row = db.execute('SELECT revision,layout FROM web_dossier_layouts WHERE business_id=%s', (business,)).fetchone()
    layout = {'revision': row['revision'], **row['layout']} if row else {
        'revision': 0, 'groups': [dict(g) for g in DEFAULT_GROUPS], 'assignments': {}}
    # Existing saved layouts remain usable without rewriting owner configuration.
    defaults = {g['id']: g['description'] for g in DEFAULT_GROUPS}
    layout['groups'] = [{**g, 'description': g.get('description', defaults.get(g['id'], ''))} for g in layout['groups']]
    return layout


def validate(body):
    if set(body) != {'business_id', 'revision', 'groups', 'assignments'} or type(body['revision']) is not int or body['revision'] < 0:
        raise WebError('Configuración de grupos no válida.')
    groups, assignments = body['groups'], body['assignments']
    if not isinstance(groups, list) or len(groups) > 20 or not isinstance(assignments, dict) or len(assignments) > 5000:
        raise WebError('Puedes crear hasta 20 grupos y organizar hasta 5000 recuerdos.')
    normalized, ids, names = [], set(), set()
    for group in groups:
        if (not isinstance(group, dict) or not {'id', 'name'} <= set(group) or set(group) - {'id', 'name', 'description'} or
                not isinstance(group['id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', group['id']) or
                group['id'] in ('review', 'ungrouped', 'auto') or not isinstance(group['name'], str)):
            raise WebError('Revisa el identificador y el nombre de cada grupo.')
        name = ' '.join(group['name'].split())
        description = group.get('description', next((g['description'] for g in DEFAULT_GROUPS if g['id'] == group['id']), ''))
        if not isinstance(description, str) or len(description) > 500:
            raise WebError('La descripción de cada grupo debe tener como máximo 500 caracteres.')
        if not 1 <= len(name) <= 60 or name.casefold() in names or group['id'] in ids or name.casefold() in ('por revisar', 'sin grupo'):
            raise WebError('Usa nombres distintos de entre 1 y 60 caracteres; Por revisar y Sin grupo están reservados.')
        ids.add(group['id'])
        names.add(name.casefold())
        normalized.append({'id': group['id'], 'name': name, 'description': description.strip()})
    for fact, group in assignments.items():
        try:
            valid_fact = isinstance(fact, str) and str(UUID(fact)) == fact
        except (TypeError, ValueError):
            valid_fact = False
        if not valid_fact or not isinstance(group, str) or group not in ids:
            raise WebError('Revisa los recuerdos y sus grupos de destino.')
    return {'groups': normalized, 'assignments': assignments}


def save(ws, body):
    from .dossier import guard
    business = guard(ws, body)
    layout = validate(body)
    with connect(ws.config) as db, db.transaction():
        # Serialize first writes too; a missing layout row cannot be locked.
        db.execute('SELECT id FROM businesses WHERE id=%s FOR UPDATE', (business,))
        old = load(db, business)
        if old['revision'] != body['revision']:
            # An exact retry after a lost response remains safe.
            if old['revision'] == body['revision'] + 1 and all(old[k] == layout[k] for k in layout):
                return old
            raise WebError('Los grupos han cambiado. Actualiza la ficha antes de guardar.', 409)
        known = {str(r['id']) for r in db.execute('SELECT id FROM memory_facts WHERE business_id=%s', (business,)).fetchall()}
        if not set(layout['assignments']) <= known:
            raise WebError('Algún recuerdo no pertenece a este negocio.', 409)
        revision = old['revision'] + 1
        db.execute('''INSERT INTO web_dossier_layouts(business_id,revision,layout) VALUES (%s,%s,%s)
            ON CONFLICT(business_id) DO UPDATE SET revision=excluded.revision,layout=excluded.layout''',
                   (business, revision, Jsonb(layout)))
        return {'revision': revision, **layout}
