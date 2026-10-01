"""Source-backed display labels; approved evidence remains immutable."""
from copy import deepcopy
import re

import duckdb

from ..database import connect
from ..data_knowledge import service as knowledge
from ..storage import Storage, digest

LABEL_COLUMNS = {'nombre', 'name', 'label', 'display_name', 'product_name', 'channel_name', 'nombre_producto', 'nombre_canal'}


def catalog_labels(config, business, analysis, db):
    model = knowledge.latest(db, business, analysis)
    if not model or not knowledge.current(db, business, {'analysis_id': str(analysis), 'revision': model['revision']}):
        return []
    tables = {str(t['id']): t for t in db.execute(
        'SELECT id,columns,parquet_key,parquet_sha256,row_count FROM prepared_tables WHERE business_id=%s AND analysis_id=%s',
        (business, analysis)).fetchall()}
    targets = {}
    for rel in model['body']['relations']:
        if (rel['verification'] != 'checked' or rel['semantic_status'] == 'rejected'
                or rel['cardinality'] not in ('many-to-one', 'one-to-one')
                or len(rel['target_columns']) != 1 or not rel['evidence'].get('row_preserving')):
            continue
        targets[(rel['target'], rel['target_columns'][0])] = rel
    labels = []
    for (table_id, key), rel in targets.items():
        table = tables.get(table_id)
        if not table or table['row_count'] > 10_000:
            continue
        candidates = [c['name'] for c in table['columns'] if c['name'].casefold() in LABEL_COLUMNS and c['name'] != key]
        if len(candidates) != 1:
            continue
        name = candidates[0]
        path = Storage(config.storage).path(business, table['parquet_key'])
        if not path.is_file() or path.stat().st_size > 50 * 1024**2 or digest(path) != table['parquet_sha256']:
            continue
        quote = lambda column: '"' + column.replace('"', '""') + '"'
        with duckdb.connect() as engine:
            rows = engine.execute(f'SELECT {quote(key)}, {quote(name)} FROM read_parquet(?)', [str(path)]).fetchall()
        codes = [r[0] for r in rows]
        if not rows or any(not c for c in codes) or len(set(codes)) != len(codes):
            continue
        names = [str(r[1]).strip() if r[1] is not None else '' for r in rows]
        for code, label in zip(codes, names):
            if not label or len(label) > 180 or len(code) > 80:
                continue
            if names.count(label) > 1:
                label += f' ({code})'
            labels.append(dict(id=f'{table_id}:{code}', code=code, name=label, table_id=table_id,
                               key_column=key, name_column=name, source_sha256=table['parquet_sha256']))
    # A code used by distinct dimensions cannot be resolved from legacy text alone.
    return [item for item in labels if sum(x['code'] == item['code'] for x in labels) == 1]


def relabel(result, labels):
    display = deepcopy(result)
    mapping = {item['code']: item['name'] for item in labels}
    # Numeric IDs may be resolved as dimension labels, never inside numerical prose.
    tokens = [code for code in mapping if not re.fullmatch(r'[\d.,+\-]+', code)]
    pattern = re.compile(r'(?<![\w])(' + '|'.join(re.escape(code) for code in sorted(tokens, key=len, reverse=True)) + r')(?![\w])') if tokens else None
    def text(value):
        return pattern.sub(lambda match: mapping[match[0]], value) if pattern else value
    def dimension(value):
        return mapping.get(value, text(value))
    for field in ('title', 'summary'):
        if display.get(field):
            display[field] = text(display[field])
    for metric in display['highlights']:
        metric['original_label'] = metric['label']
        metric['label'] = text(metric['label'])
    for claim in display['claims']:
        for field in ('title', 'statement', 'interpretation', 'next_step'):
            if claim.get(field):
                claim[field] = text(claim[field])
    for chart in display['charts']:
        chart['title'] = text(chart['title'])
        for point in chart['points']:
            point['original_label'] = point['label']
            point['label'] = dimension(point['label'])
        for panel in chart['panels']:
            for coordinate in panel['coordinates']:
                coordinate['label'] = dimension(coordinate['label'])
                coordinate['category'] = dimension(coordinate['category'])
                coordinate['series'] = dimension(coordinate['series'])
            panel['series_order'] = [dimension(s) for s in panel['series_order']]
            panel['colors'] = {dimension(k): v for k, v in panel.get('colors', {}).items()}
    return display


from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError, StrictInt
from psycopg.types.json import Jsonb
from ..agent import review
from ..memory import service as memory
from ..client_report import formatted
from .dashboard import presentation
from .errors import WebError, identifier, bounded


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['report', 'metric', 'chart', 'insight', 'entity']
    key: str = Field(max_length=200)
    field: Literal['title', 'name', 'unit', 'decimals']
    value: str | StrictInt


class Edit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    business_id: str
    base_version: str = Field(min_length=1, max_length=128)
    revision: StrictInt = Field(ge=0)
    request_key: str = Field(min_length=1, max_length=100)
    changes: list[Change] = Field(default_factory=list, max_length=50)
    restore_revision: StrictInt | None = Field(default=None, ge=0)


def head(db, business, reviewed):
    return db.execute('''SELECT * FROM report_presentation_revisions
        WHERE business_id=%s AND report_id=%s AND base_version=%s ORDER BY revision DESC LIMIT 1''',
        (business, reviewed['id'], reviewed['approved_sha256'])).fetchone()


def history(db, business, reviewed):
    rows = db.execute('''SELECT revision,origin,description,created_at FROM report_presentation_revisions
        WHERE business_id=%s AND report_id=%s AND base_version=%s ORDER BY revision DESC LIMIT 50''',
        (business, reviewed['id'], reviewed['approved_sha256'])).fetchall()
    rows = [{**row, 'created_at': row['created_at'].isoformat()} for row in rows]
    return rows or [dict(revision=0, origin='catalog', description='Nombres del catálogo', created_at=None)]


def apply(result, labels, config):
    resolved = [{**item, 'name': config.get('labels', {}).get(item['id'], item['name'])} for item in labels]
    display = relabel(result, resolved)
    for item in resolved:
        item['catalog_name'] = next(x['name'] for x in labels if x['id'] == item['id'])
    # Label collisions make graph categories ambiguous. Keep the original code visible.
    if len({x['name'] for x in resolved}) != len(resolved):
        raise WebError('Dos nombres coinciden. Usa nombres distintos o añade su código.')
    groups = {'metric': display['highlights'], 'chart': display['charts'], 'insight': display['claims']}
    for target, fields in config.get('elements', {}).items():
        kind, key = target.split(':', 1)
        element = display if kind == 'report' else next((x for x in groups[kind] if x['key'] == key), None)
        if element is None:
            continue  # Home contains a bounded subset of the report's findings.
        for field, value in fields.items():
            element['label' if kind == 'metric' and field == 'title' else field] = value
        if 'decimals' in fields:
            if kind == 'metric':
                element['value'] = formatted(element['raw_value'], fields['decimals'])
            elif kind == 'chart':
                for point in element['points']:
                    point['formatted'] = formatted(point['value'], fields['decimals'])
    for group in ('highlights', 'charts'):
        for element, original in zip(display[group], result[group]):
            element['unit_choices'] = unit_choices(original.get('unit', ''))
    return display, resolved


def decorate(ws, reviewed, result, *, db=None):
    if result is None or not reviewed.get('analysis_id') or not reviewed.get('id'):
        return result
    if db is None:
        with connect(ws.config) as connection:
            return decorate(ws, reviewed, result, db=connection)
    labels = catalog_labels(ws.config, ws.business_id(), reviewed['analysis_id'], db)
    saved = head(db, ws.business_id(), reviewed)
    display, resolved = apply(result, labels, saved['config'] if saved else {})
    display['presentation'] = dict(report_id=str(reviewed['id']), base_version=reviewed['approved_sha256'],
                                   revision=saved['revision'] if saved else 0, labels=resolved,
                                   history=history(db, ws.business_id(), reviewed))
    return display


def approved(ws, report_id, db):
    try:
        result = review.show(ws.config, ws.business_id(), identifier(report_id), _db=db)
    except ValueError:
        raise WebError('Este informe no está disponible en este negocio.', 404) from None
    if not result['publishable']:
        raise WebError('Este informe necesita una nueva revisión.', 409)
    # Deletion also withdraws editable/exportable presentation.
    if db.execute('''SELECT 1 FROM web_jobs WHERE business_id=%s AND review_id=%s AND deleted_at IS NOT NULL''',
                  (ws.business_id(), report_id)).fetchone():
        raise WebError('Este informe se ha eliminado.', 409)
    return result


def view(ws, report_id, revision=None, *, db=None):
    if db is None:
        with connect(ws.config) as connection, connection.transaction():
            return view(ws, report_id, revision, db=connection)
    memory.lock(db, ws.business_id())
    reviewed = approved(ws, report_id, db)
    current = decorate(ws, reviewed, presentation(reviewed), db=db)
    if revision is None or revision == current['presentation']['revision']:
        return current
    saved = db.execute('''SELECT snapshot FROM report_presentation_revisions
        WHERE business_id=%s AND report_id=%s AND base_version=%s AND revision=%s''',
        (ws.business_id(), report_id, reviewed['approved_sha256'], revision)).fetchone()
    if not saved:
        raise WebError('Esta versión de presentación no existe.', 404)
    historical = deepcopy(saved['snapshot'])
    historical['presentation']['history'] = current['presentation']['history']
    historical['presentation']['current_revision'] = current['presentation']['revision']
    return historical


def unit_choices(unit):
    normalized = unit.casefold().strip()
    if normalized in ('eur', '€', 'euros', 'euro'):
        return [unit, 'EUR', '€', 'euros']
    if normalized in ('%', 'porcentaje'):
        return [unit, '%', 'porcentaje']
    if normalized.startswith('unidades') or normalized in ('unidad', 'uds.', 'uds'):
        # Preserve a verified caveat; the short name remains a display alias only.
        return list(dict.fromkeys([unit, 'unidades', 'uds.']))
    return [unit]


def amended(config, changes, baseline):
    config = deepcopy(config)
    groups = {'metric': baseline['highlights'], 'chart': baseline['charts'], 'insight': baseline['claims']}
    for change in changes:
        kind, key, field, value = change.kind, change.key, change.field, change.value
        if kind == 'entity':
            if field != 'name' or not any(x['id'] == key for x in baseline['presentation']['labels']):
                raise WebError('Selecciona un nombre del catálogo de este informe.')
            config.setdefault('labels', {})[key] = bounded(value, 'el nombre', 180)
            continue
        element = baseline if kind == 'report' and key == 'title' else next((x for x in groups.get(kind, []) if x['key'] == key), None)
        if element is None:
            raise WebError('Este elemento no pertenece al informe.')
        allowed = ['title'] + (['unit', 'decimals'] if kind in ('metric', 'chart') else [])
        if field not in allowed:
            raise WebError('Este campo requiere una corrección del análisis.')
        if field == 'title':
            value = bounded(value, 'el título', 250)
        elif field == 'unit':
            if value not in unit_choices(element['unit']):
                raise WebError('Esta unidad cambia el significado del cálculo. Solicita una corrección del análisis.')
        elif type(value) is not int or not 0 <= value <= 6:
            raise WebError('Elige entre 0 y 6 decimales.')
        config.setdefault('elements', {}).setdefault(f'{kind}:{key}', {})[field] = value
    return config


def save(ws, report_id, body, *, origin='editor', db=None):
    try:
        edit = Edit.model_validate(body)
    except ValidationError:
        raise WebError('Revisa los campos de la edición.') from None
    if identifier(edit.business_id) != ws.business_id():
        raise WebError('El negocio ha cambiado. Abre el editor de nuevo.', 409)
    if bool(edit.changes) == (edit.restore_revision is not None):
        raise WebError('Indica cambios o una versión que restaurar.')
    if db is None:
        with connect(ws.config) as connection, connection.transaction():
            return save(ws, report_id, body, origin=origin, db=connection)
    memory.lock(db, ws.business_id())
    reviewed = approved(ws, report_id, db)
    if reviewed['approved_sha256'] != edit.base_version:
        raise WebError('El análisis ha cambiado. Abre el editor de nuevo.', 409)
    request_hash = memory.digest({'report_id': str(report_id), 'edit': edit.model_dump(), 'origin': origin})
    prior = db.execute('SELECT * FROM report_presentation_revisions WHERE business_id=%s AND request_key=%s',
                       (ws.business_id(), edit.request_key)).fetchone()
    if prior:
        if prior['request_sha256'] != request_hash:
            raise WebError('La solicitud ya corresponde a otros cambios.', 409)
        return dict(saved=True, revision=prior['revision'], report=view(ws, report_id, db=db), replayed=True)
    old = head(db, ws.business_id(), reviewed)
    if edit.revision != (old['revision'] if old else 0):
        raise WebError('Alguien ha cambiado esta presentación. Abre el editor de nuevo antes de guardar.', 409)
    baseline = decorate(ws, reviewed, presentation(reviewed), db=db)
    if edit.restore_revision is not None:
        target = db.execute('''SELECT config FROM report_presentation_revisions
            WHERE business_id=%s AND report_id=%s AND base_version=%s AND revision=%s''',
            (ws.business_id(), report_id, edit.base_version, edit.restore_revision)).fetchone()
        if not target:
            raise WebError('Esta versión no existe.', 404)
        config = target['config']
        description = f'Restaurada la versión {edit.restore_revision}'
    else:
        # Validate units against approved evidence, not previously shortened labels.
        original = presentation(reviewed)
        original['presentation'] = baseline['presentation']
        config = amended(old['config'] if old else {}, edit.changes, original)
        description = ' · '.join(dict.fromkeys({'title':'Título', 'name':'Nombre', 'unit':'Unidad visible', 'decimals':'Decimales'}[c.field] for c in edit.changes))
    display, labels = apply(presentation(reviewed), catalog_labels(ws.config, ws.business_id(), reviewed['analysis_id'], db), config)
    new_revision = edit.revision + 1
    display['presentation'] = {**baseline['presentation'], 'labels': labels, 'revision': new_revision}
    def insert(revision, config, snapshot, request, signature, source, description):
        db.execute('''INSERT INTO report_presentation_revisions
            (business_id,report_id,base_version,revision,config,snapshot,request_key,request_sha256,origin,description)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (ws.business_id(), report_id, edit.base_version, revision, Jsonb(config), Jsonb(snapshot), request, signature, source, description))
    if not old:
        insert(0, {}, baseline, None, None, 'catalog', 'Nombres del catálogo')
    insert(new_revision, config, display, edit.request_key, request_hash, origin, description)
    display['presentation']['history'] = history(db, ws.business_id(), reviewed)
    return dict(saved=True, revision=new_revision, report=display, replayed=False)
