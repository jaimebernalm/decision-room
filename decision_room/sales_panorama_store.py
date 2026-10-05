"""Private import-time P1a cache, isolated from research and frozen into reviews."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid5

import duckdb
from psycopg.types.json import Jsonb

from . import sales_panorama as calculator
from .agent.context import encoded, fingerprint
from .execution_contract import validate_result
from .database import connect
from .storage import Storage, digest


def prepare(config, business_id, analysis_id, mappings=None, table_ids=None):
    mappings = {} if mappings is None else mappings
    if not isinstance(mappings, dict):
        raise ValueError('Panorama mappings must be keyed by table ID.')
    with connect(config) as db:
        if not db.execute('SELECT 1 FROM analyses WHERE business_id=%s AND id=%s', (business_id, analysis_id)).fetchone():
            raise ValueError('Panorama analysis does not belong to this business.')
        rows = db.execute('''SELECT p.*,s.original_names FROM prepared_tables p JOIN sources s ON s.id=p.source_id
            WHERE p.business_id=%s AND p.analysis_id=%s AND s.status='ready' ORDER BY p.id''',
            (business_id, analysis_id)).fetchall()
        if table_ids is not None:
            rows = [r for r in rows if str(r['id']) in table_ids]
            if set(table_ids) != {str(r['id']) for r in rows}:
                raise ValueError('Panorama tables must belong to the current business and analysis.')
        if set(mappings) - {str(r['id']) for r in rows}:
            raise ValueError('Panorama mapping references an unauthorized table.')
        source_code = Path(calculator.__file__).read_text()
        code_hash = sha256(source_code.encode()).hexdigest()
        result = []
        for row in rows:
            identifier = str(row['id'])
            source = Storage(config.storage).path(business_id, row['parquet_key'])
            if digest(source) != row['parquet_sha256']:
                raise ValueError('Panorama source integrity check failed.')
            specification = dict(version=calculator.VERSION, code_sha256=code_hash, engine_version=duckdb.__version__,
                                 table_id=identifier, parquet_sha256=row['parquet_sha256'], mapping=mappings.get(identifier))
            key = fingerprint(specification)
            stored = db.execute('SELECT * FROM sales_panoramas WHERE business_id=%s AND table_id=%s AND request_sha256=%s',
                                (business_id, row['id'], key)).fetchone()
            if stored:
                if fingerprint(stored['body']) != stored['body_sha256']:
                    raise ValueError('Panorama cache integrity check failed.')
                body = stored['body']
            else:
                body = calculator.calculate(source, [c['name'] for c in row['columns']], mappings.get(identifier))
                if digest(source) != row['parquet_sha256']:
                    raise ValueError('Panorama source changed while calculating.')
                body = {**body, 'specification': specification}
                db.execute('''INSERT INTO sales_panoramas(business_id,table_id,request_sha256,body_sha256,body)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                    (business_id, row['id'], key, fingerprint(body), Jsonb(body)))
            result.append(dict(table_id=identifier, names=row['original_names'], body=body,
                               body_sha256=fingerprint(body), code=source_code))
        return result


def review_snapshot(prepared, knowledge, catalog_labels=None):
    """Standard metric observations; numbers use the existing evidence resolver."""
    overviews, observations = [], []
    for item in prepared:
        body = item['body']
        if body['status'] != 'available':
            overviews.append(dict(table_id=item['table_id'], names=item['names'], **body))
            continue
        payload = body['result']
        refs = {}
        chunks, chunk = [], []
        evidence = {entry['metric']:entry for entry in payload['evidence']}
        def result_for(keys):
            return dict(schema_version=1, metrics={k:payload['metrics'][k] for k in keys},
                        evidence=[evidence[k] for k in keys], notes=[], series={})
        # Preserve every metric while keeping each result below the 64 KB omission
        # threshold, including long Unicode dimensions. Code appears once per table.
        for key in sorted(payload['metrics']):
            if chunk and (len(chunk) >= 40 or len(encoded(result_for([*chunk,key])).encode()) > 48000):
                chunks.append(chunk); chunk = []
            chunk.append(key)
        if chunk:
            chunks.append(chunk)
        first_id = None
        for index, selected in enumerate(chunks):
            execution_id = str(uuid5(UUID(item['table_id']), item['body_sha256']+':'+str(index)))
            first_id = first_id or execution_id
            refs.update({k: dict(execution_id=execution_id, metric=k) for k in selected})
            result = result_for(selected)
            result = validate_result(encoded(result), {'source': {'row_count':int(payload['metrics']['rows'])}})
            observations.append(dict(execution_id=execution_id, status='completed', current=True,
                knowledge_sha256=knowledge, origin=calculator.VERSION,
                code=item['code'] if index == 0 else '',
                code_reference=None if index == 0 else {'execution_id': first_id, 'field': 'observations.code'},
                code_sha256=body['specification']['code_sha256'],
                inputs={'source': dict(id=item['table_id'], original_names=item['names'],
                    parquet_sha256=body['specification']['parquet_sha256'], row_count=int(payload['metrics']['rows']))},
                result=result, logs={}, issue=None, artifacts=[], specification=body['specification']))
        def bind(value):
            if isinstance(value, dict):
                if set(value) == {'metric'}:
                    return refs[value['metric']]
                return {k:bind(v) for k,v in value.items()}
            if isinstance(value, list):
                return [bind(v) for v in value]
            return value
        overviews.append(dict(table_id=item['table_id'], names=item['names'], **bind(body['summary'])))
    frozen = dict(version=calculator.VERSION, tables=overviews, observations=observations)
    if catalog_labels is not None:
        frozen['catalog_labels'] = deepcopy(catalog_labels)
    return {**frozen, 'sha256': fingerprint(frozen)}


def materialize(config, business_id, snapshot, knowledge):
    frozen = deepcopy(snapshot)
    expected = frozen.pop('sha256')
    if fingerprint(frozen) != expected:
        raise ValueError('Frozen panorama integrity check failed.')
    with connect(config) as db:
        for table in frozen['tables']:
            row = db.execute('SELECT parquet_key,parquet_sha256 FROM prepared_tables WHERE business_id=%s AND id=%s',
                             (business_id, table['table_id'])).fetchone()
            spec = table.get('specification')
            if not spec:
                spec = next(o['specification'] for o in frozen['observations'] if o['inputs']['source']['id']==table['table_id'])
            if not row or row['parquet_sha256'] != spec['parquet_sha256'] or digest(Storage(config.storage).path(business_id,row['parquet_key'])) != spec['parquet_sha256']:
                raise ValueError('Frozen panorama source changed or belongs to another business.')
    with connect(config) as db:
        for label in frozen.get('catalog_labels', []):
            row = db.execute('SELECT parquet_key,parquet_sha256 FROM prepared_tables WHERE business_id=%s AND id=%s',
                             (business_id, label['table_id'])).fetchone()
            if not row or row['parquet_sha256'] != label['source_sha256'] or digest(Storage(config.storage).path(business_id,row['parquet_key'])) != label['source_sha256']:
                raise ValueError('Frozen panorama catalog changed or belongs to another business.')
    for observation in frozen['observations']:
        observation['current'] = observation['knowledge_sha256'] == knowledge
    return frozen
