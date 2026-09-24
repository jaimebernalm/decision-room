"""Business-scoped metadata and resumable import batches for a local CLI."""
import hashlib
import json
import uuid
from pathlib import Path

from psycopg.types.json import Jsonb

from .csv_ingest import FORMAT_VERSION, prepare
from .database import connect
from .storage import Storage, digest


def create_business(config, name, description=''):
    name = name.strip()
    if not name:
        raise ValueError('Business name cannot be empty.')
    with connect(config) as db:
        return db.execute('INSERT INTO businesses(id,name,description) VALUES (%s,%s,%s) RETURNING *',
                          (uuid.uuid4(), name, description)).fetchone()


def require_business(db, business_id):
    if not db.execute('SELECT id FROM businesses WHERE id=%s', (business_id,)).fetchone():
        raise ValueError('Business not found.')


def require_analysis(db, business_id, analysis_id):
    row = db.execute('SELECT * FROM analyses WHERE business_id=%s AND id=%s',
                     (business_id, analysis_id)).fetchone()
    if not row:
        raise ValueError('Analysis not found for this business.')
    return row


def batch_metadata(hashes, delimiter=None):
    """Stable identity of data and preparation, independent of upload filenames."""
    preparation = {'format_version': FORMAT_VERSION, 'delimiter': delimiter,
                   'encoding': 'utf-8-sig', 'all_columns_text': True}
    batch_hash = hashlib.sha256(json.dumps({'hashes': sorted(set(hashes)), 'preparation': preparation},
                                          sort_keys=True).encode()).hexdigest()
    return batch_hash, preparation


def import_batch(config, business_id, paths, title='CSV upload', delimiter=None, progress=None):
    paths = [Path(p).resolve() for p in paths]
    if not paths or len(paths) > config.max_files:
        raise ValueError(f'Provide between 1 and {config.max_files} CSV files.')
    if any(not p.is_file() or p.suffix.lower() != '.csv' for p in paths):
        raise ValueError('All inputs must be existing .csv files.')
    if sum(p.stat().st_size for p in paths) > config.max_batch_bytes:
        raise ValueError('Batch exceeds the configured size limit.')
    with connect(config) as db:
        require_business(db, business_id)
    storage = Storage(config.storage)
    grouped, byte_count = {}, 0
    for path in paths:
        item = storage.capture(business_id, path, config.max_file_bytes)
        byte_count += item['byte_count']
        if byte_count > config.max_batch_bytes:
            raise ValueError('Batch exceeds the configured size limit.')
        if item['sha256'] in grouped:
            grouped[item['sha256']]['original_names'] = sorted(set(grouped[item['sha256']]['original_names'] + item['original_names']))
        else:
            grouped[item['sha256']] = item
    batch_hash, preparation = batch_metadata(grouped, delimiter)
    with connect(config) as db, db.transaction():
        created = db.execute('''INSERT INTO analyses(id,business_id,title,batch_sha256,status)
            VALUES (%s,%s,%s,%s,'importing') ON CONFLICT (business_id,batch_sha256) DO NOTHING RETURNING id''',
            (uuid.uuid4(), business_id, title, batch_hash)).fetchone()
        analysis = db.execute('SELECT id FROM analyses WHERE business_id=%s AND batch_sha256=%s',
                              (business_id, batch_hash)).fetchone()
        analysis_id = analysis['id']
        for item in grouped.values():
            db.execute('''INSERT INTO sources(id,business_id,analysis_id,original_names,sha256,byte_count,original_key,status,preparation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'staged',%s) ON CONFLICT (analysis_id,sha256) DO UPDATE
                SET original_names=(SELECT jsonb_agg(DISTINCT v) FROM jsonb_array_elements(sources.original_names || EXCLUDED.original_names) v)''',
                (uuid.uuid4(), business_id, analysis_id, Jsonb(item['original_names']), item['sha256'],
                 item['byte_count'], item['original_key'], Jsonb(preparation)))
    report = resume(config, business_id, analysis_id, progress)
    report.update({'reused_batch': created is None, 'submitted_files': len(paths),
                   'unique_files': len(grouped), 'duplicate_inputs': len(paths)-len(grouped)})
    return report


def resume(config, business_id, analysis_id, progress=None):
    storage = Storage(config.storage)
    with connect(config) as db:
        require_analysis(db, business_id, analysis_id)
        locked = db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS locked',
                             (str(analysis_id),)).fetchone()['locked']
        if not locked:
            raise ValueError('This analysis already has an active importer. Try again after it finishes.')
        # The advisory lock is released even after a crash when the connection closes.
        db.execute("UPDATE analyses SET status='importing',updated_at=now() WHERE business_id=%s AND id=%s", (business_id, analysis_id))
        sources = db.execute('SELECT * FROM sources WHERE business_id=%s AND analysis_id=%s ORDER BY original_names->>0',
                              (business_id, analysis_id)).fetchall()
        for source in sources:
            try:
                original = storage.path(business_id, source['original_key'])
                if digest(original) != source['sha256']:
                    raise ValueError('Original file integrity check failed.')
                existing = db.execute('SELECT * FROM prepared_tables WHERE business_id=%s AND source_id=%s',
                                       (business_id, source['id'])).fetchone()
                if existing and source['status'] == 'ready':
                    cached = storage.path(business_id, existing['parquet_key'])
                    if cached.exists() and digest(cached) == existing['parquet_sha256']:
                        if progress:
                            progress(source['original_names'][0], 'reused', existing['row_count'])
                        continue
                key = f"{business_id}/analyses/{analysis_id}/{source['id']}/table.parquet"
                result = prepare(original, storage.path(business_id, key), config,
                                 source['preparation']['delimiter'])
                with db.transaction():
                    db.execute('''INSERT INTO prepared_tables(id,business_id,analysis_id,source_id,parquet_key,
                        parquet_sha256,row_count,columns,profile,lineage_column,engine_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (source_id) DO UPDATE SET parquet_key=EXCLUDED.parquet_key,
                        parquet_sha256=EXCLUDED.parquet_sha256,row_count=EXCLUDED.row_count,columns=EXCLUDED.columns,
                        profile=EXCLUDED.profile,lineage_column=EXCLUDED.lineage_column,engine_version=EXCLUDED.engine_version''',
                        (uuid.uuid4(), business_id, analysis_id, source['id'], key, result['parquet_sha256'],
                         result['row_count'], Jsonb(result['columns']), Jsonb(result['profile']),
                         result['lineage_column'], result['engine_version']))
                    db.execute("UPDATE sources SET status='ready',issue=NULL,updated_at=now() WHERE id=%s AND business_id=%s",
                               (source['id'], business_id))
                if progress:
                    progress(source['original_names'][0], 'ready', result['row_count'])
            except Exception as error:
                # Persist failure per source; the rest of the batch remains useful.
                # KeyboardInterrupt/SystemExit intentionally escape so resume can recover.
                with db.transaction():
                    db.execute('DELETE FROM prepared_tables WHERE source_id=%s AND business_id=%s', (source['id'], business_id))
                    db.execute("UPDATE sources SET status='failed',issue=%s,updated_at=now() WHERE id=%s AND business_id=%s",
                               (Jsonb({'type': type(error).__name__, 'message': str(error)[:1200]}), source['id'], business_id))
                if progress:
                    progress(source['original_names'][0], 'failed', None)
        counts = db.execute('SELECT status,count(*) AS n FROM sources WHERE business_id=%s AND analysis_id=%s GROUP BY status',
                             (business_id, analysis_id)).fetchall()
        counts = {r['status']: r['n'] for r in counts}
        state = 'ready' if counts.get('ready') == len(sources) else ('partial' if counts.get('ready') else 'failed')
        db.execute('UPDATE analyses SET status=%s,updated_at=now() WHERE business_id=%s AND id=%s',
                   (state, business_id, analysis_id))
    return describe(config, business_id, analysis_id)


def describe(config, business_id, analysis_id, detailed=False):
    with connect(config) as db:
        analysis = require_analysis(db, business_id, analysis_id)
        records = db.execute('''SELECT s.id AS source_id,s.original_names,s.status,s.sha256,s.byte_count,s.original_key,s.issue,
            p.id AS table_id,p.parquet_key,p.parquet_sha256,p.row_count,p.columns,p.profile,p.lineage_column,p.engine_version
            FROM sources s LEFT JOIN prepared_tables p ON p.source_id=s.id AND p.business_id=s.business_id
            WHERE s.business_id=%s AND s.analysis_id=%s ORDER BY s.original_names->>0''',
            (business_id, analysis_id)).fetchall()
        for r in records:
            overlaps = db.execute('''SELECT DISTINCT analysis_id FROM sources WHERE business_id=%s
                AND sha256=%s AND analysis_id<>%s''', (business_id, r['sha256'], analysis_id)).fetchall()
            r['also_in_analyses'] = [x['analysis_id'] for x in overlaps]
            if not detailed:
                r['column_count'] = len(r.pop('columns') or [])
                r.pop('profile')
        return {'analysis': analysis, 'table_count': sum(r['table_id'] is not None for r in records),
                'total_rows': sum(r['row_count'] or 0 for r in records), 'files': records,
                'scope': 'Imported tables kept separate. No business interpretation, joins or report generated.'}


def list_analyses(config, business_id):
    with connect(config) as db:
        require_business(db, business_id)
        return db.execute('SELECT * FROM analyses WHERE business_id=%s ORDER BY created_at DESC', (business_id,)).fetchall()
