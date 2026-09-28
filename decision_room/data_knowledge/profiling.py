"""Deterministic full-data checks. No generated SQL, guessed units or automatic joins."""
import re
import time
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from threading import Timer

import duckdb

from ..csv_ingest import identifier as quote
from ..storage import Storage, digest
from ..memory.service import digest as fingerprint

VERSION = 'data-knowledge-v2'


@contextmanager
def engine(config, business, records):
    with TemporaryDirectory(prefix='dr-catalog-') as scratch, duckdb.connect(config={
        'threads': 2, 'memory_limit': '512MB', 'temp_directory': scratch,
        'max_temp_directory_size': '2GB',
    }) as db:
        deadline = time.monotonic() + 180
        timer = Timer(180, db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            for i, record in enumerate(records):
                path = Storage(config.storage).path(business, record['parquet_key'])
                if digest(path) != record['parquet_sha256']:
                    raise ValueError('Los datos no superan la comprobación de integridad.')
                db.read_parquet(str(path)).create_view(f't{i}')
            class Queries:
                def execute(self, query):
                    if time.monotonic() >= deadline:
                        raise ValueError('La comprobación ha superado tres minutos. Divide el conjunto y reintenta.')
                    return db.execute(query)
            yield Queries(), {str(r['id']): f't{i}' for i, r in enumerate(records)}
        finally:
            timer.cancel()


def profile(db, view, record):
    columns = []
    for column in record['columns']:
        name = column['name']
        c = quote(name)
        # Parse checks preserve lexical identifiers and never alter the Parquet.
        numeric = f"regexp_full_match({c}, '[+-]?[0-9]+([.][0-9]+)?') AND try_cast({c} AS DECIMAL(38,10)) IS NOT NULL"
        dates = f"regexp_full_match({c}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}([ T][0-9]{{2}}:[0-9]{{2}}:[0-9]{{2}}([.][0-9]+)?)?') AND try_cast({c} AS TIMESTAMP) IS NOT NULL"
        values = db.execute(f'''SELECT count(*) FILTER (WHERE {c} IS NULL OR {c}=''),
            count(DISTINCT {c}) FILTER (WHERE {c} IS NOT NULL AND {c}<>''),
            count(*) FILTER (WHERE {numeric}), count(*) FILTER (WHERE {dates}),
            min(CASE WHEN {dates} THEN try_cast({c} AS DATE) END),
            max(CASE WHEN {dates} THEN try_cast({c} AS DATE) END)
            FROM {view}''').fetchone()
        missing, distinct, numeric_count, date_count, start, end = values
        n = record['row_count'] - missing
        logical = 'unknown' if not n else 'date' if date_count == n else 'number' if numeric_count == n else 'text'
        if re.search(r'(id|code|key)$', name, re.I):
            logical = 'identifier'
        columns.append(dict(name=name, storage_type='VARCHAR', logical_type=logical,
            missing=missing, distinct=distinct, duplicate_nonempty=n-distinct,
            numeric_parseable=numeric_count, date_parseable=date_count,
            period={'from': str(start), 'until': str(end)} if start else None,
            unique_nonempty=bool(n and distinct == n), key_candidate=bool(n and distinct == n and not missing),
            meaning='', unit='', conversion='', semantic_status='unknown'))
    quoted = ','.join(quote(c['name']) for c in record['columns'])
    unique_rows = db.execute(f'SELECT count(*) FROM (SELECT DISTINCT {quoted} FROM {view})').fetchone()[0]
    return dict(id=str(record['id']), source_id=str(record['source_id']), name=record['original_names'][0],
        sha256=record['parquet_sha256'], row_count=record['row_count'], duplicate_rows=record['row_count']-unique_rows,
        description='', grain='', semantic_status='unknown', columns=columns,
        candidate_keys=[[c['name']] for c in columns if c['key_candidate']], declared_keys=[],
        provenance='Full prepared file; lexical values retained. Logical types are parse observations, not business definitions.')


def relation_id(source, target, source_columns, target_columns):
    return fingerprint([source, target, source_columns, target_columns])[:24]


def validate_relation(db, views, tables, source, target, source_columns, target_columns):
    by_id = {t['id']: t for t in tables}
    if not isinstance(source,str) or not isinstance(target,str) or source not in by_id or target not in by_id:
        raise ValueError('Selecciona dos tablas de esta versión.')
    if any(not isinstance(names,list) or any(not isinstance(n,str) for n in names) for names in (source_columns,target_columns)):
        raise ValueError('Las columnas de cada clave deben ser una lista de nombres.')
    if not 1 <= len(source_columns) <= 6 or len(source_columns) != len(target_columns):
        raise ValueError('Las claves deben tener entre una y seis columnas, en el mismo orden.')
    for table, names in ((source, source_columns), (target, target_columns)):
        if len(set(names)) != len(names) or not set(names) <= {c['name'] for c in by_id[table]['columns']}:
            raise ValueError('Selecciona columnas existentes sin repetirlas.')
    def grouped(table, names):
        cols = ','.join(f'{quote(c)} AS k{i}' for i, c in enumerate(names))
        complete = ' AND '.join(f"{quote(c)} IS NOT NULL AND {quote(c)}<>''" for c in names)
        return f'SELECT {cols},count(*) AS n FROM {views[table]} WHERE {complete} GROUP BY ALL'
    left, right = grouped(source, source_columns), grouped(target, target_columns)
    def counts(query, rows):
        distinct, present, duplicate_keys = db.execute(f'SELECT count(*),coalesce(sum(n),0),count(*) FILTER(WHERE n>1) FROM ({query})').fetchone()
        return dict(rows=rows, complete_rows=int(present), missing_rows=rows-int(present),
                    distinct_keys=distinct, duplicate_keys=duplicate_keys, duplicate_rows=int(present)-distinct)
    a = counts(left, by_id[source]['row_count'])
    b = counts(right, by_id[target]['row_count'])
    on = ' AND '.join(f'a.k{i}=b.k{i}' for i in range(len(source_columns)))
    # Aggregate frequencies before joining: even many-to-many cannot allocate a cartesian explosion.
    joined, unmatched, matched = db.execute(f'''SELECT coalesce(sum(a.n*coalesce(b.n,0)),0),
        coalesce(sum(CASE WHEN b.n IS NULL THEN a.n ELSE 0 END),0),
        coalesce(sum(CASE WHEN b.n IS NOT NULL THEN a.n ELSE 0 END),0)
        FROM ({left}) a LEFT JOIN ({right}) b ON {on}''').fetchone()
    cardinality = ('many' if a['duplicate_keys'] else 'one') + '-to-' + ('many' if b['duplicate_keys'] else 'one')
    safe = bool(a['complete_rows'] and b['complete_rows'] and not a['missing_rows'] and not b['missing_rows'] and not b['duplicate_keys'] and not unmatched)
    return dict(id=relation_id(source,target,source_columns,target_columns), source=source, target=target,
        source_columns=source_columns, target_columns=target_columns, cardinality=cardinality,
        origin='inferred', semantic_status='proposed', description='',
        verification='checked' if safe else 'attention',
        evidence=dict(source=a, target=b, unmatched_rows=int(unmatched), matched_rows=int(matched),
                      inner_join_rows=int(joined), left_join_rows=int(joined+unmatched+a['missing_rows']),
                      extra_rows=max(0,int(joined-matched)), row_preserving=not b['duplicate_keys'],
                      coverage=float(matched/a['complete_rows']) if a['complete_rows'] else None),
        join=dict(operator='equality', comparison='Exact lexical equality; no implicit casts', direction='source → target'),
        precaution='Technical checks do not establish business meaning. Aggregate at the intended grain; never sum parent measures after a one-to-many join.')
