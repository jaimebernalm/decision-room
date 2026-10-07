"""Job-scoped deterministic panorama, with frozen, paged evidence observations.

Reuse the existing calculator without enabling the legacy agent contract. Its
observation IDs identify deterministic evidence, not sandbox execution rows or
analytical approval of the agent's interpretation.
"""
from pathlib import Path
from uuid import UUID, uuid4

import duckdb
from psycopg.types.json import Jsonb

from .. import sales_panorama, sales_panorama_store
from ..database import connect
from . import admission, ratios


def _checked(row):
    if row and admission.sha(admission.canonical(row['body'])) != row['body_sha256']:
        raise ValueError('Frozen engine panorama failed its integrity check.')
    return row


def calculate(config, run_id, token, *, table_id, request_key, mapping=None):
    job = admission.authenticate(config, run_id, token)
    table_id = str(UUID(str(table_id)))
    if table_id not in {t['id'] for t in job['snapshot']}:
        raise admission.Denied('Panorama table is outside the job snapshot.')
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid panorama request key.')
    if mapping is not None and (not isinstance(mapping, dict) or set(mapping) != set(sales_panorama.ROLES)
                                or any(not isinstance(v, str) or len(v) > 500 for v in mapping.values())):
        raise ValueError('Invalid explicit panorama column mapping.')
    fingerprint = admission.sha(admission.canonical({
        'table_id': table_id, 'mapping': mapping, 'snapshot': job['snapshot_sha256'],
        'code': admission.sha(Path(sales_panorama.__file__).read_bytes()), 'duckdb': duckdb.__version__, 'ratios': ratios.identity()}))
    with connect(config) as db:
        row = db.execute('SELECT * FROM engine_panoramas WHERE run_id=%s AND request_key=%s',
                         (run_id, request_key)).fetchone()
    if row:
        if row['request_sha256'] != fingerprint:
            raise ValueError('Panorama request key already used with different input.')
        return _checked(row)
    prepared = sales_panorama_store.prepare(config, job['business_id'], job['analysis_id'],
        mappings={} if mapping is None else {table_id: mapping}, table_ids=[table_id])
    for item in prepared:
        item['body'] = ratios.extend(item['body'])
        item['body']['specification']['ratios'] = ratios.identity()
        item['body_sha256'] = admission.sha(admission.canonical(item['body']))
    frozen = sales_panorama_store.review_snapshot(prepared, job['snapshot_sha256'])
    # The calculator runs without holding the run row; late completions cannot
    # admit new evidence into a paused job or a changed snapshot.
    admission.authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        run = admission._locked(db, run_id, token)
        error = admission._active(db, run)
        if not error:
            row = db.execute('SELECT * FROM engine_panoramas WHERE run_id=%s AND request_key=%s',
                             (run_id, request_key)).fetchone()
            if row:
                if row['request_sha256'] != fingerprint:
                    raise ValueError('Panorama request key already used with different input.')
                return _checked(row)
            row = db.execute('''INSERT INTO engine_panoramas
                (id,business_id,run_id,request_key,request_sha256,body,body_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (uuid4(), job['business_id'], run_id, request_key, fingerprint,
                 Jsonb(frozen), admission.sha(admission.canonical(frozen)))).fetchone()
            admission._event(db, run_id, 'panorama_frozen', {'panorama_id': str(row['id']), 'table_id': table_id})
    if error:
        raise admission.Aborted(error)
    return row


def observation(config, business_id, run_id, observation_id):
    """Trusted resolver; an ID from another job never grants evidence access."""
    with connect(config) as db:
        rows = db.execute('''SELECT * FROM engine_panoramas
            WHERE business_id=%s AND run_id=%s
            AND body->'observations' @> %s::jsonb ORDER BY created_at,id''',
            (business_id, run_id, Jsonb([{'execution_id': str(observation_id)}]))).fetchall()
    found = []
    for row in rows:
        _checked(row)
        found.extend(o for o in row['body']['observations'] if o['execution_id'] == str(observation_id))
    if not found:
        return None
    if any(admission.canonical(o) != admission.canonical(found[0]) for o in found[1:]):
        raise ValueError('Conflicting frozen panorama observations.')
    return found[0]
