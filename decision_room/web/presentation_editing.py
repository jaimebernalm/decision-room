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


def decorate(ws, reviewed, result, *, db=None):
    if result is None or not reviewed.get('analysis_id') or not reviewed.get('id'):
        return result
    if db is None:
        with connect(ws.config) as connection:
            return decorate(ws, reviewed, result, db=connection)
    labels = catalog_labels(ws.config, ws.business_id(), reviewed['analysis_id'], db)
    display = relabel(result, labels)
    display['presentation'] = dict(report_id=str(reviewed['id']), base_version=reviewed['approved_sha256'],
                                   revision=0, labels=labels)
    return display
