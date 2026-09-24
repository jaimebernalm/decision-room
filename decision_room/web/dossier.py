"""Owner-facing shared memory and independent, versioned CSV imports."""
import hashlib
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from psycopg.types.json import Jsonb
from pydantic import ValidationError

from ..database import connect
from .. import service as ingestion
from ..memory import service as memory, context
from ..storage import Storage
from .errors import WebError, identifier, bounded
from .business import profile


def guard(ws, data):
    business = ws.business_id()
    if not isinstance(data, dict) or not business or identifier(data.get('business_id')) != business:
        raise WebError('El negocio activo ha cambiado. Recarga la página.', 409)
    return business


def listing(ws):
    business = ws.business_id()
    if not business:
        raise WebError('Selecciona un negocio.', 409)
    with connect(ws.config) as db, db.transaction():
        memory.lock(db, business)
        facts = memory.current(db, business)
        history = db.execute('''SELECT r.*,s.origin_key,s.payload->>'kind' AS origin_kind,
            s.payload->>'text' AS original_text,s.payload->>'question' AS question,
            (SELECT t.conversation_id FROM chat_turns t WHERE t.business_id=r.business_id AND t.memory_source_id=r.source_id LIMIT 1) AS conversation_id
            FROM memory_revisions r JOIN memory_sources s ON s.id=r.source_id
            WHERE r.business_id=%s ORDER BY r.business_revision DESC''', (business,)).fetchall()
        origins = {(r['fact_id'], r['revision']): r for r in history}
        facts = [origins[(r['fact_id'], r['revision'])] for r in facts]
        datasets = db.execute('''SELECT a.id,a.title,a.status,a.created_at,
            coalesce(v.dataset_id,a.id) AS dataset_id,coalesce(v.version,1) AS version,
            v.period_from,v.period_until,v.superseded_by,coalesce(v.corrected,false) AS corrected,
            (SELECT jsonb_agg(jsonb_build_object('id',s.id,'name',s.original_names->>0,
                'status',s.status,'rows',p.row_count)) FROM sources s
                LEFT JOIN prepared_tables p ON p.source_id=s.id WHERE s.analysis_id=a.id) AS files
            FROM analyses a LEFT JOIN dataset_versions v ON v.analysis_id=a.id
            WHERE a.business_id=%s AND NOT EXISTS (SELECT 1 FROM dataset_uploads u WHERE u.business_id=a.business_id AND u.result->>'pending'='true' AND u.result->>'existing_id' IS NULL AND u.result->>'batch_sha256'=a.batch_sha256) ORDER BY a.created_at DESC,a.id''', (business,)).fetchall()
        return dict(business_id=business, business=profile(db, business), memory=memory.status(ws.config, business),
                    facts=facts, history=history, datasets=datasets)


def change(ws, data):
    business = guard(ws, data)
    allowed = {'business_id', 'action', 'request_key', 'content', 'fact_id', 'expected_revision',
               'original_text', 'reason', 'change_kind'}
    if set(data) - allowed or not {'action', 'request_key'} <= set(data):
        raise WebError('Operación de memoria no válida.')
    try:
        return memory.change(ws.config, business, **{k: v for k, v in data.items() if k != 'business_id'})
    except memory.MemoryError as error:
        raise WebError(str(error), error.status) from None
    except ValidationError:
        raise WebError('Revisa la información, el ámbito y las fechas del recuerdo.') from None


def available(db, business, analysis):
    return db.execute('''SELECT 1 FROM analyses a LEFT JOIN dataset_versions v ON v.analysis_id=a.id
        WHERE a.id=%s AND a.business_id=%s AND a.status='ready' AND NOT coalesce(v.corrected,false) AND NOT EXISTS (SELECT 1 FROM dataset_uploads u WHERE u.business_id=a.business_id AND u.result->>'pending'='true' AND u.result->>'existing_id' IS NULL AND u.result->>'batch_sha256'=a.batch_sha256)''',
        (analysis, business)).fetchone() is not None


def upload(ws, data, filename, content):
    business = guard(ws, data)
    key = identifier(data.get('request_key'))
    title = bounded(data.get('title', ''), 'el nombre del conjunto', 160)
    mode = data.get('mode', 'separate')
    if mode not in ('separate', 'update', 'correction'):
        raise WebError('Selecciona datos independientes, actualización o corrección.')
    previous = identifier(data.get('previous_id')) if mode != 'separate' else None
    if mode == 'separate' and data.get('previous_id'):
        raise WebError('Los datos independientes no sustituyen otro conjunto.')
    try:
        start = date.fromisoformat(data['period_from']) if data.get('period_from') else None
        end = date.fromisoformat(data['period_until']) if data.get('period_until') else None
        if start and end and start > end:
            raise ValueError()
    except (ValueError, TypeError):
        raise WebError('Revisa el periodo: utiliza fechas válidas y ordenadas.') from None
    if not isinstance(filename, str) or '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
        raise WebError('El nombre del archivo no es válido.')
    filename = bounded(filename, 'el nombre del archivo', 180)
    if not filename.lower().endswith('.csv') or not content or len(content) > 20 * 1024**2:
        raise WebError('Sube un CSV UTF-8 con datos, de hasta 20 MB.')
    try:
        content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise WebError('Guarda el CSV con codificación UTF-8.') from None
    signature = memory.digest([title, filename, mode, str(previous), str(start), str(end), hashlib.sha256(content).hexdigest()])
    # Serialize uploads for this business across ingestion's separate transactions.
    # An interrupted import is recovered by the existing content-addressed importer.
    with connect(ws.config) as db:
        db.execute('SELECT pg_advisory_lock(hashtextextended(%s, 25))', (str(business),))
        saved = db.execute('SELECT * FROM dataset_uploads WHERE business_id=%s AND request_key=%s', (business, key)).fetchone()
        if saved:
            if saved['signature'] != signature:
                raise WebError('Este envío ya se guardó con otros datos.', 409)
            if not saved['result'].get('pending'):
                return saved['result']
        unfinished = db.execute("SELECT 1 FROM dataset_uploads WHERE business_id=%s AND request_key<>%s AND result->>'pending'='true'", (business, key)).fetchone()
        if unfinished:
            raise WebError('Hay una carga interrumpida. Vuelve a enviar el archivo anterior con los mismos datos para recuperarla.', 409)
        old = None
        if previous:
            old = db.execute('''SELECT a.id,coalesce(v.dataset_id,a.id) AS dataset_id,coalesce(v.version,1) AS version,
                v.superseded_by FROM analyses a LEFT JOIN dataset_versions v ON v.analysis_id=a.id
                WHERE a.id=%s AND a.business_id=%s AND a.status='ready' ''', (previous, business)).fetchone()
            if not old or old['superseded_by']:
                raise WebError('La versión seleccionada ya ha cambiado o no está disponible. Recarga la ficha.', 409)
        batch_hash, _ = ingestion.batch_metadata([hashlib.sha256(content).hexdigest()])
        existing = db.execute('SELECT id FROM analyses WHERE business_id=%s AND batch_sha256=%s', (business, batch_hash)).fetchone()
        if existing and previous and existing['id'] != previous and (not saved or saved['result'].get('existing_id')):
            raise WebError('Este archivo ya pertenece a otra versión o conjunto. Reutilízalo desde la ficha.', 409)
        if not saved:
            pending = dict(pending=True, existing_id=str(existing['id']) if existing else None, batch_sha256=batch_hash)
            db.execute('INSERT INTO dataset_uploads(business_id,request_key,signature,result) VALUES (%s,%s,%s,%s)',
                       (business, key, signature, Jsonb(pending)))
        else:
            pending = saved['result']
        if existing and pending['existing_id']:
            if previous and existing['id'] != previous:
                raise WebError('Este archivo ya pertenece a otra versión o conjunto. Reutilízalo desde la ficha.', 409)
            result = dict(analysis_id=str(existing['id']), reused=True,
                          status=ingestion.describe(ws.config, business, existing['id'])['analysis']['status'])
        else:
            with TemporaryDirectory(prefix='dr-csv-') as directory:
                path = Path(directory) / filename
                path.write_bytes(content)
                imported = (ingestion.resume(ws.config, business, existing['id']) if existing else
                            ingestion.import_batch(ws.config, business, [path], title=title))
            result = dict(analysis_id=str(imported['analysis']['id']), reused=False, status=imported['analysis']['status'])
        analysis = identifier(result['analysis_id'])
        with db.transaction():
            memory.lock(db, business)
            if result['status'] == 'ready' and not result['reused']:
                if old:
                    db.execute('''INSERT INTO dataset_versions(business_id,analysis_id,dataset_id,version)
                        VALUES (%s,%s,%s,1) ON CONFLICT (analysis_id) DO NOTHING''', (business, previous, old['dataset_id']))
                db.execute('''INSERT INTO dataset_versions(business_id,analysis_id,dataset_id,version,period_from,period_until)
                    VALUES (%s,%s,%s,%s,%s,%s)''',
                    (business, analysis, old['dataset_id'] if old else analysis, old['version'] + 1 if old else 1, start, end))
                if old:
                    db.execute('UPDATE dataset_versions SET superseded_by=%s,corrected=%s WHERE analysis_id=%s',
                               (analysis, mode == 'correction', previous))
                    if mode == 'correction':
                        context.invalidate(db, business)
            result['message'] = ('Este archivo ya estaba guardado; conserva su conjunto, periodo y versión.' if result['reused'] else
                'Datos disponibles. Los informes anteriores no se han recalculado.' if result['status'] == 'ready' else
                'No se ha podido preparar el CSV. Corrige sus encabezados o filas y vuelve a subirlo. Se conservan los datos anteriores.')
            db.execute('UPDATE dataset_uploads SET result=%s WHERE business_id=%s AND request_key=%s',
                       (Jsonb(result), business, key))
        return result


def download(ws, source_id):
    with connect(ws.config) as db:
        source = db.execute('SELECT * FROM sources WHERE id=%s AND business_id=%s',
                            (identifier(source_id), ws.business_id())).fetchone()
    if not source:
        raise WebError('Archivo no encontrado.', 404)
    content = Storage(ws.config.storage).path(ws.business_id(), source['original_key']).read_bytes()
    if hashlib.sha256(content).hexdigest() != source['sha256']:
        raise WebError('El original no supera la comprobación de integridad.', 409)
    return source['original_names'][0], content
