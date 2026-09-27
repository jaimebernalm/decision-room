"""Bounded, read-only views of the prepared data belonging to one web job."""
import duckdb

from ..database import connect
from ..storage import Storage, digest
from ..csv_ingest import identifier as column_identifier
from .errors import WebError, identifier

PAGE_ROWS = 50
PAGE_COLUMNS = 12
CELL_CHARACTERS = 500


def page(ws, job_id, query):
    job = ws.row(job_id)
    with connect(ws.config) as db:
        tables = db.execute('''SELECT p.id,s.original_names,p.row_count,p.columns,
            p.parquet_key,p.parquet_sha256,p.lineage_column
            FROM prepared_tables p JOIN sources s ON s.id=p.source_id AND s.business_id=p.business_id
            WHERE p.business_id=%s AND p.analysis_id=%s AND s.status='ready'
            ORDER BY s.original_names->>0,p.id''', (job['business_id'], job['analysis_id'])).fetchall()
    if not tables:
        raise WebError('Todavía no hay tablas preparadas para consultar.', 409)
    table_id = identifier(query['table'][0]) if query.get('table') else tables[0]['id']
    selected = next((t for t in tables if t['id'] == table_id), None)
    if not selected:
        raise WebError('Esta tabla no pertenece a los datos de este informe.', 404)
    try:
        offset = int(query.get('offset', ['0'])[0])
        column_offset = int(query.get('column_offset', ['0'])[0])
        if 'column_offset' not in query and query.get('column'):
            names = [c['name'] for c in selected['columns']]
            if query['column'][0] in names:
                column_offset = names.index(query['column'][0]) // PAGE_COLUMNS * PAGE_COLUMNS
    except (ValueError, TypeError):
        raise WebError('La página de datos no es válida.') from None
    if not 0 <= offset < max(1, selected['row_count']) or not 0 <= column_offset < len(selected['columns']):
        raise WebError('La página de datos no es válida.')
    path = Storage(ws.config.storage).path(job['business_id'], selected['parquet_key'])
    if not path.is_file() or digest(path) != selected['parquet_sha256']:
        raise WebError('Los datos guardados no coinciden con la versión del informe.', 409)
    columns = [c['name'] for c in selected['columns'][column_offset:column_offset + PAGE_COLUMNS]]
    expressions = [column_identifier(selected['lineage_column'])] + [
        f'left({column_identifier(c)}, {CELL_CHARACTERS + 1})' for c in columns]
    with duckdb.connect(config={'threads': 1, 'memory_limit': '256MB'}) as db:
        db.read_parquet(str(path)).create_view('preview_data')
        rows = db.execute('SELECT ' + ','.join(expressions) + ' FROM preview_data ORDER BY ' +
                          column_identifier(selected['lineage_column']) + ' LIMIT ? OFFSET ?',
                          [PAGE_ROWS, offset]).fetchall()
    return dict(tables=[dict(id=str(t['id']), name=' · '.join(t['original_names']),
                            row_count=t['row_count'], column_count=len(t['columns'])) for t in tables],
                table_id=str(table_id), columns=columns,
                rows=[dict(number=r[0], values=[v[:CELL_CHARACTERS] + '…' if v is not None and len(v) > CELL_CHARACTERS else v for v in r[1:]]) for r in rows],
                offset=offset, column_offset=column_offset, page_rows=PAGE_ROWS, page_columns=PAGE_COLUMNS,
                cell_characters=CELL_CHARACTERS)
