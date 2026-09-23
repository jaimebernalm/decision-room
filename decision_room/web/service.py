"""Durable local web jobs; all analytical work goes through existing services."""
import hashlib
import json
import logging
import threading
from dataclasses import asdict
from contextlib import nullcontext
from pathlib import Path
from uuid import uuid4

from psycopg.types.json import Jsonb

from .. import service as ingestion
from ..agent import service as planning, research, review
from ..agent.model import ModelAPIError, ModelClient, ModelNotReady, ModelSettings
from ..client_report import render_client
from ..database import connect
from ..execution import recover_executions
from ..storage import Storage
from ..memory import service as memory, extraction as memory_extraction
from . import business as business_store
from .dashboard import projection as dashboard_projection
from .errors import WebError, bounded, identifier

MAX_UPLOAD = 20 * 1024**2
LOG = logging.getLogger(__name__)


def failure_message(error):
    # Agent services wrap failures to persist stage diagnostics. Inspect the
    # original typed exception, never copy arbitrary exception/server text to UI.
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, ModelAPIError):
            return (
                f'El servidor del modelo rechazó la petición (HTTP {error.status_code}). '
                'Tus datos y respuestas están guardados. Revisa el estado del modelo en LM Studio '
                'o en el servidor configurado. Si el motor ha fallado o no tiene memoria suficiente, '
                'recupéralo antes de reintentar. Reintentar aquí reanuda el análisis, pero no reinicia el modelo.'
            )
        error = error.__cause__ or error.__context__
    return ('El análisis se ha interrumpido. Tus datos y respuestas están guardados. '
            'Comprueba que el modelo local y el motor de análisis están disponibles y reintenta '
            'para continuar desde el último paso guardado.')


class Workspace:
    def __init__(self, config, settings=None, model_factory=ModelClient):
        self.config = config
        self.settings = settings
        self.model_factory = model_factory
        self.wake = threading.Event()
        self.stop = threading.Event()
        self._scoped = False
        self._business_id = None

    def scoped(self, business_id):
        """Pin a request/worker to one authorized business, even during selection changes."""
        if business_id is not None:
            with connect(self.config) as db:
                business_store.profile(db, business_id)
        scoped = Workspace(self.config, self.settings, self.model_factory)
        scoped._scoped, scoped._business_id = True, business_id
        scoped.wake, scoped.stop = self.wake, self.stop
        return scoped

    def business_id(self):
        if self._scoped:
            return self._business_id
        current = business_store.state(self.config)['business']
        return current['id'] if current else None

    def save_business(self, data):
        saved = business_store.save(self.config, data)
        self.wake.set()
        return saved

    def select_business(self, data):
        return business_store.select(self.config, data)

    def state(self):
        current = business_store.state(self.config)
        business_id = current['business']['id'] if current['business'] else None
        return {**current, 'configured': self.settings is not None,
                'analyses': self.scoped(business_id).listing(),
                'memory': memory.status(self.config, business_id)}

    def retry_memory(self, data):
        business_id = self.business_id()
        if business_id is None:
            raise WebError('Selecciona un negocio antes de reintentar.', 409)
        if not isinstance(data, dict) or identifier(data.get('business_id')) != business_id:
            raise WebError('El negocio activo ha cambiado. Recarga la página antes de reintentar.', 409)
        memory_extraction.retry(self.config, business_id)
        self.wake.set()
        return memory.status(self.config, business_id)

    def create(self, data, filename, content):
        if not isinstance(data, dict):
            raise WebError('Los datos del análisis no son válidos.')
        key = identifier(data.get('request_key'))
        business = self.business_id()
        if business is None or identifier(data.get('business_id')) != business:
            raise WebError('Selecciona tu negocio antes de crear un análisis. Si ha cambiado, recarga la página.', 409)
        revision = data.get('profile_revision')
        if type(revision) is not int or revision < 1:
            raise WebError('Vuelve a cargar el contexto de tu negocio.', 409)
        if 'business' in data or 'context' in data:
            raise WebError('Guarda el contexto desde el formulario del negocio antes de iniciar el análisis.', 409)
        goal = bounded(data.get('goal', ''), 'la pregunta', 2000, False)
        title = bounded(data.get('title') or goal or 'Exploración general', 'el título', 160)
        if not isinstance(filename, str) or '/' in filename or '\\' in filename or any(ord(c) < 32 for c in filename):
            raise WebError('El nombre del archivo no es válido.')
        filename = bounded(filename, 'el nombre del archivo', 180)
        if not filename.lower().endswith('.csv'):
            raise WebError('Sube un archivo CSV. El soporte de Excel llegará en una próxima entrega.')
        if not content or len(content) > MAX_UPLOAD:
            raise WebError('El CSV debe contener datos y ocupar como máximo 20 MB.')
        try:
            content.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise WebError('Guarda el archivo como CSV UTF-8 y vuelve a subirlo.') from None
        with connect(self.config) as db, db.transaction():
            # Serialize profile edits/selection with capturing this job's snapshot.
            selected = db.execute('SELECT active_business_id FROM web_workspace WHERE singleton FOR SHARE').fetchone()
            if selected['active_business_id'] != business:
                raise WebError('El negocio activo ha cambiado. Vuelve a abrir el formulario.', 409)
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 7))', (str(key),))
            old = db.execute('SELECT * FROM web_jobs WHERE request_key=%s', (key,)).fetchone()
            current = business_store.profile(db, business)
            name, context = (old['business_name'], old['context']) if old else (current['name'], current['description'])
            signature = hashlib.sha256(json.dumps([name, context, goal, title, filename], ensure_ascii=False).encode() + content).hexdigest()
            if old:
                if old['business_id'] != business or old['business_revision'] != revision or old['request_sha256'] != signature:
                    raise WebError('Este envío ya se guardó con otros datos. Inicia un nuevo análisis.', 409)
                return {'id': str(old['id'])}
            if current['profile_revision'] != revision:
                raise WebError('El contexto del negocio ha cambiado. Recárgalo antes de iniciar otro análisis.', 409)
            if self.settings is None:
                raise WebError('Falta configurar el modelo local. El borrador está guardado; podrás enviarlo cuando esté disponible.', 503)
            job_id = uuid4()
            upload_key = f'{business}/web/{job_id}/{filename}'
            path = Storage(self.config.storage).path(business, upload_key)
            path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o600)
            try:
                db.execute('''INSERT INTO web_jobs(id,request_key,request_sha256,business_id,business_name,business_revision,title,context,goal,
                    filename,upload_key,byte_count,model_settings,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')''',
                    (job_id, key, signature, business, name, revision, title, context, goal, filename, upload_key, len(content), Jsonb(asdict(self.settings))))
                db.execute("UPDATE web_businesses SET onboarding_status='analysis_started',updated_at=now() WHERE business_id=%s", (business,))
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        self.wake.set()
        return {'id': str(job_id)}

    def row(self, job_id):
        with connect(self.config) as db:
            job = db.execute('SELECT w.*,w.business_name AS business FROM web_jobs w WHERE w.id=%s AND w.business_id=%s',
                             (identifier(job_id), self.business_id())).fetchone()
        if not job:
            raise WebError('No encontramos este análisis en tu espacio de trabajo.', 404)
        return job

    def update(self, job_id, **values):
        allowed = {'status', 'phase', 'issue', 'pending_answer', 'retry_uncertain', 'analysis_id', 'session_id', 'research_id', 'review_id'}
        assert values.keys() <= allowed
        with connect(self.config) as db:
            row = db.execute('UPDATE web_jobs SET ' + ','.join(f'{key}=%s' for key in values) + ',updated_at=now() WHERE id=%s AND business_id=%s RETURNING id',
                             (*values.values(), job_id, self.business_id())).fetchone()
            if not row:
                raise WebError('Análisis no encontrado en el negocio activo.', 404)

    def sync(self, job_id):
        """Discover durable child IDs even if the process died before a call returned."""
        j = self.row(job_id)
        # The imported batch is recovered by its content/preparation identity in
        # run_job, never by "latest analysis" now that businesses can have many.
        with connect(self.config) as db:
            for field, table, where, params in [
                ('session_id', 'agent_sessions', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
                ('research_id', 'agent_research', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
                ('review_id', 'agent_reviews', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
            ]:
                if not j[field]:
                    found = db.execute(f'SELECT id FROM {table} WHERE {where} ORDER BY created_at DESC LIMIT 1', params).fetchone()
                    if found:
                        if field != 'session_id':
                            parent = db.execute(f'SELECT session_id FROM {table} WHERE id=%s', (found['id'],)).fetchone()
                            if parent['session_id'] != j['session_id']:
                                continue
                        self.update(job_id, **{field: found['id']})
                        j[field] = found['id']
        j = self.row(job_id)
        if j['session_id']:
            with connect(self.config) as db:
                next_id = db.execute('SELECT superseded_by FROM agent_sessions WHERE id=%s', (j['session_id'],)).fetchone()['superseded_by']
                if next_id:
                    self.update(job_id, session_id=next_id, research_id=None, review_id=None, pending_answer=None, phase='planning')
                    return self.sync(job_id)
        return j

    def public(self, j):
        fields = ('id', 'business_id', 'title', 'business', 'context', 'goal', 'filename', 'byte_count', 'status', 'phase', 'created_at', 'updated_at', 'issue', 'origin')
        result = {key: j[key] for key in fields}
        with connect(self.config) as db:
            result['data_version'] = db.execute('SELECT version,superseded_by,corrected FROM dataset_versions WHERE analysis_id=%s AND business_id=%s', (j['analysis_id'], j['business_id'])).fetchone()
        if j['origin'] == 'chat':
            with connect(self.config) as db:
                source = db.execute('SELECT conversation_id FROM chat_turns WHERE job_id=%s AND business_id=%s ORDER BY created_at LIMIT 1', (j['id'], j['business_id'])).fetchone()
            result['conversation_id'] = source['conversation_id'] if source else None
        return result

    def review_state(self, j, *, _db=None):
        try:
            return review.show(self.config, j['business_id'], j['review_id'], _db=_db)
        except (OSError, ValueError):
            # One missing or changed evidence file must not hide the whole workspace.
            LOG.exception('Cannot read evidence for web job %s', j['id'])
            return {'publishable': False, 'pending_questions': [], 'unavailable': True}

    def listing(self):
        with connect(self.config) as db:
            rows = db.execute("SELECT w.*,w.business_name AS business FROM web_jobs w WHERE w.business_id=%s AND (w.origin='upload' OR EXISTS (SELECT 1 FROM chat_turns t WHERE t.business_id=w.business_id AND (t.job_id=w.id OR t.response->>'report_id'=w.review_id::text) AND t.report_requested)) ORDER BY w.created_at DESC",
                              (self.business_id(),)).fetchall()
        result = []
        for j in rows:
            item = self.public(j)
            if j['status'] == 'completed' and j['review_id']:
                current = self.review_state(j)
                if not current['publishable']:
                    item.update(status='blocked', presentation_status='withdrawn', phase='review', issue='Informe retirado: necesita un nuevo cálculo y revisión.')
            result.append(item)
        return result

    def daily_activity(self, listing):
        """Latest chat turns, including work not yet published as a report."""
        from ..conversations import Conversations, dependencies_current, reviewed
        items = []
        with connect(self.config) as db:
            rows = db.execute("""SELECT t.*,c.title FROM chat_conversations c
                JOIN LATERAL (SELECT * FROM chat_turns WHERE conversation_id=c.id ORDER BY ordinal DESC LIMIT 1) t ON true
                WHERE c.business_id=%s AND (t.status!='completed' OR t.response->>'kind'='evidence')
                ORDER BY t.updated_at DESC LIMIT 12""", (self.business_id(),)).fetchall()
            chats = Conversations(self)
            for turn in rows:
                status, response = turn['status'], turn['response'] or {}
                if response.get('kind') == 'evidence':
                    r = reviewed(self.config, self.business_id(), response['report_id'], db)
                    if not r['publishable'] or r['approved_sha256'] != response.get('report_version'):
                        status = 'stale'
                if not turn['job_id'] and turn['snapshot'] and not dependencies_current(self.config, db, turn['snapshot'], chats.events(db, turn)):
                    status = 'stale'
                if status == 'waiting' and turn['job_id'] and self.detail(turn['job_id']).get('context_stale'):
                    status = 'stale'
                if status == 'completed':
                    if not turn['report_requested'] and response.get('kind') == 'evidence':
                        status = 'ready'
                    else:
                        continue
                status = {'routing': 'running', 'processing': 'running', 'stale': 'withdrawn' if response.get('kind') == 'evidence' else 'outdated'}.get(status, status)
                items.append(dict(title=turn['title'], status=status, href='#chat/' + str(turn['conversation_id']), created_at=turn['updated_at']))
        items += [dict(title=x['title'], status=x.get('presentation_status', x['status']), href='#analysis/' + str(x['id']), created_at=x['created_at'])
                  for x in listing if x['origin'] != 'chat' and x['status'] != 'completed']
        return sorted(items, key=lambda x: x['created_at'], reverse=True)[:5]

    def dashboard(self, selected=None):
        """One currently publishable revision, scoped to the active business."""
        listing = self.listing()
        activity = self.daily_activity(listing)
        reports = [item for item in listing if item['status'] == 'completed']
        choices = [{'id': str(item['id']), 'title': item['title'],
                    'created_at': item['created_at']} for item in reports]
        requested = identifier(selected) if selected else None
        candidates = ([item for item in reports if item['id'] == requested] if requested else [])
        candidates += [item for item in reports if item not in candidates]
        from ..agent.persistence import session_lock
        for item in candidates:
            job = self.row(item['id'])
            if not job['review_id'] or not job['session_id']:
                continue
            try:
                with session_lock(self.config, job['business_id'], job['session_id']) as (db, _), db.transaction():
                    memory.lock(db, job['business_id'])
                    reviewed = self.review_state(job, _db=db)
                    content = dashboard_projection(reviewed)
                    if content:
                        return {'reports': choices, 'activity': activity, 'report_id': str(reviewed['id']),
                                'report_version': reviewed['approved_sha256'], 'analysis_id': str(job['analysis_id']),
                                'selected_id': str(job['id']),
                                'report': content, 'created_at': job['created_at'],
                                'filename': job['filename'], 'data_version': item.get('data_version')}
            except ValueError:
                # The review may be running or changing. Show no stale content.
                continue
        return {'reports': choices, 'activity': activity, 'selected_id': None, 'report': None}

    def detail(self, job_id):
        j = self.sync(job_id)
        result = {**self.public(j), 'questions': [], 'answers': [], 'interpretations': [], 'files': [], 'publishable': False,
                  'activity': ''}
        b = j['business_id']
        result['memory'] = memory.status(self.config, b)
        if j['analysis_id']:
            data = ingestion.describe(self.config, b, j['analysis_id'])
            result['files'] = [{k: f[k] for k in ('original_names', 'status', 'row_count', 'column_count')} for f in data['files']]
        if j['session_id']:
            plan = planning.show(self.config, b, j['session_id'])
            result['questions'] = [{'id': q['id'], 'phase': 'planning', 'text': q['text'], 'reason': q['reason'], 'options': q['options']} for q in plan['questions']]
            if plan.get('context_stale'):
                result.update(status='failed', phase='planning', issue='La memoria aplicable ha cambiado. Reintenta para recalcular con las definiciones actuales.', questions=[])
            result['answers'] = [{'text': a['text'], 'disposition': a['disposition'], 'question': a.get('question', '')} for a in plan['answers']]
            if plan['revisions']:
                result['interpretations'] = [{'text': i['statement'], 'status': i['status']} for i in plan['revisions'][-1]['proposal']['interpretations']]
        if j['review_id']:
            data = self.review_state(j)
            result['publishable'] = data['publishable']
            if data.get('conversation'):
                action = data['conversation'][-1]['action']['action']
                result['activity'] = {
                    'submit': 'El analista ha preparado una versión del informe. El revisor está contrastando sus conclusiones.',
                    'revise': 'El revisor ha solicitado ajustes. El analista está preparando una nueva versión del informe.',
                    'execute': 'Se ha registrado un cálculo adicional para contrastar la evidencia.',
                }.get(action, '')
            result['questions'] = [{'id': str(q['step']), 'phase': 'review', 'text': q['action']['question'],
                                    'reason': q['action']['message'], 'options': []} for q in data['pending_questions']]
            if data['publishable']:
                result['status'] = 'completed'
            elif j['status'] == 'completed':
                result.update(status='blocked', phase='review', issue='El informe necesita una nueva revisión porque sus datos o su validación han cambiado.')
            if data.get('independent_hold'):
                result.update(status='blocked', phase='review', issue='La revisión independiente ha bloqueado este informe. ' + data['independent_hold']['reason'])
            if data.get('unavailable'):
                result.update(status='blocked', phase='review', issue='No podemos recuperar toda la evidencia de este análisis. Conservamos sus datos de registro, pero el informe no está disponible. Revisa el almacenamiento local o crea otro análisis.')
        if j['session_id'] and plan.get('context_stale'):
            result.update(status=j['status'] if j['status'] in ('queued', 'running') else 'failed',
                          phase='planning', context_stale=True, questions=[], publishable=False,
                          issue='La memoria aplicable ha cambiado. Recalcula para revisar el informe con las definiciones actuales.')
        if (result.get('data_version') or {}).get('corrected'):
            result.update(status='blocked', publishable=False, questions=[],
                          issue='Esta versión de datos se ha corregido. Abre Mi negocio y pregunta con la versión actual; el informe anterior se conserva como registro, pero no como resultado válido.')
        return result

    def reply(self, job_id, data):
        if not isinstance(data, dict):
            raise WebError('La respuesta no es válida.')
        key = identifier(data.get('request_key'))
        text = bounded(data.get('text', ''), 'la respuesta', 6000, False)
        disposition = data.get('disposition', 'answered')
        if disposition not in ('answered', 'unknown', 'declined') or (disposition == 'answered' and not text):
            raise WebError('Escribe una respuesta o selecciona «No lo sé».')
        answer = {'id': str(data.get('question_id', '')), 'phase': data.get('phase'), 'text': text,
                  'disposition': disposition, 'request_key': str(key)}
        questions = self.detail(job_id)['questions']
        with connect(self.config) as db, db.transaction():
            job = db.execute('SELECT * FROM web_jobs WHERE id=%s AND business_id=%s FOR UPDATE',
                             (identifier(job_id), self.business_id())).fetchone()
            if not job:
                raise WebError('Análisis no encontrado.', 404)
            prior = db.execute('SELECT answer FROM web_replies WHERE job_id=%s AND request_key=%s', (job_id, key)).fetchone()
            if prior:
                if prior['answer'] != answer:
                    raise WebError('Este envío ya contiene otra respuesta.', 409)
                return {'saved': True}
            if job['status'] != 'waiting':
                raise WebError('La pregunta ya está siendo procesada. Actualiza el análisis.', 409)
            if not any(q['id'] == answer['id'] and q['phase'] == answer['phase'] for q in questions):
                raise WebError('Esta pregunta ya no está pendiente.', 409)
            db.execute('INSERT INTO web_replies(job_id,request_key,answer) VALUES (%s,%s,%s)', (job_id, key, Jsonb(answer)))
            db.execute("UPDATE web_jobs SET pending_answer=%s,status='queued',issue=NULL,updated_at=now() WHERE id=%s", (Jsonb(answer), job_id))
        self.wake.set()
        return {'saved': True}

    def retry(self, job_id, *, _db=None):
        j = self.row(job_id)
        from .dossier import available
        with connect(self.config) as db:
            if j['analysis_id'] and not available(db, j['business_id'], j['analysis_id']):
                raise WebError('Los datos ya no están disponibles para recalcular. Selecciona la versión actual desde Mi negocio.', 409)
        from ..memory.context import reason
        with connect(self.config) as db:
            stale = j['session_id'] and reason(db, j['session_id'])
        if j['status'] != 'failed' and not stale:
            raise WebError('Solo se pueden reintentar los análisis con un fallo técnico.', 409)
        model = self.model_factory(ModelSettings(**j['model_settings']))
        try:
            if check := getattr(model, 'check_ready', None):
                check()
        except ModelNotReady as error:
            # Keep the job paused; a readiness request must never enqueue work
            # or trigger LM Studio's automatic model-loading attempt.
            raise WebError(str(error), 409) from None
        with (nullcontext(_db) if _db is not None else connect(self.config)) as db:
            row = db.execute("UPDATE web_jobs SET status='queued',issue=NULL,retry_uncertain=true,updated_at=now() WHERE id=%s AND business_id=%s AND (status='failed' OR %s) RETURNING id",
                             (identifier(job_id), j['business_id'], bool(stale))).fetchone()
        if not row:
            raise WebError('Solo se pueden reintentar los análisis con un fallo técnico.', 409)
        self.wake.set()
        return {'saved': True}

    def report(self, job_id):
        j = self.row(job_id)
        if not j['review_id']:
            raise WebError('El informe todavía no está disponible.', 409)
        # Export uses the same parent lock; approval is rechecked on every request.
        from ..agent.persistence import session_lock
        with session_lock(self.config, j['business_id'], j['session_id']) as (db, _), db.transaction():
            memory.lock(db, j['business_id'])
            data = self.review_state(j, _db=db)
            if not data['publishable']:
                raise WebError('Este informe no ha superado la revisión o ha quedado desactualizado.', 409)
            return render_client(data, data['updated_at'].strftime('%d/%m/%Y, %H:%M %Z'), embedded=True)

    def upload(self, job_id):
        j = self.row(job_id)
        if j['origin'] == 'chat':
            raise WebError('Esta conversación reutiliza un conjunto de datos existente.', 409)
        content = Storage(self.config.storage).path(j['business_id'], j['upload_key']).read_bytes()
        signature = hashlib.sha256(json.dumps([j['business'], j['context'], j['goal'], j['title'], j['filename']], ensure_ascii=False).encode() + content).hexdigest()
        if signature != j['request_sha256']:
            raise WebError('El archivo guardado ha cambiado y no coincide con el original enviado.', 409)
        return j['filename'], content

    def run_job(self, job_id):
        j = self.sync(job_id)
        b, key = j['business_id'], 'web:' + str(j['id'])
        model = self.model_factory(ModelSettings(**j['model_settings']))
        retry = j['retry_uncertain']
        self.update(job_id, status='running', issue=None)
        try:
            if j['session_id']:
                from ..memory.context import reason
                with connect(self.config) as db:
                    stale = reason(db, j['session_id'])
                if stale:
                    # Create the successor before driving it; sync recovers this link after a crash.
                    from ..agent.service import _create_session
                    from ..agent.persistence import session_lock
                    with session_lock(self.config, b, j['session_id']):
                        successor = _create_session(self.config, b, j['analysis_id'], owner_context=j['goal'] or 'Exploración general de la actividad disponible.',
                            request_key='web-replan:' + str(j['session_id']), model=model, supersedes=j['session_id'])
                    self.update(job_id, session_id=successor['id'], research_id=None, review_id=None, pending_answer=None, phase='planning')
                    j = self.sync(job_id)
            with connect(self.config) as db:
                abandoned = db.execute("SELECT 1 FROM executions WHERE business_id=%s AND status IN ('preparing','running') LIMIT 1", (b,)).fetchone()
            if abandoned:
                recover_executions(self.config, b)
            if not j['analysis_id']:
                self.update(job_id, phase='upload')
                content = self.upload(job_id)[1]  # Verify before reuse or import.
                path = Storage(self.config.storage).path(b, j['upload_key'])
                batch_hash, _ = ingestion.batch_metadata([hashlib.sha256(content).hexdigest()])
                with connect(self.config) as db:
                    existing = db.execute('SELECT id FROM analyses WHERE business_id=%s AND batch_sha256=%s',
                                          (b, batch_hash)).fetchone()
                # Reuse and verify the exact batch without changing the names
                # in previous source snapshots. This upload keeps its own name.
                data = (ingestion.resume(self.config, b, existing['id']) if existing else
                        ingestion.import_batch(self.config, b, [path], title=j['title']))
            else:
                data = ingestion.describe(self.config, b, j['analysis_id'])
                if data['analysis']['status'] == 'importing':
                    data = ingestion.resume(self.config, b, j['analysis_id'])
            self.update(job_id, analysis_id=data['analysis']['id'])
            if data['analysis']['status'] != 'ready':
                self.update(job_id, status='blocked', issue='No hemos podido leer el CSV. Comprueba que tiene encabezados y filas con el mismo número de columnas, y crea un nuevo análisis con el archivo corregido.')
                return
            j = self.sync(job_id)
            # Once review exists it owns continuity, including answers that invalidate research.
            if not j['review_id']:
                self.update(job_id, phase='planning')
                if j['pending_answer'] and j['pending_answer']['phase'] == 'planning':
                    a = j['pending_answer']
                    planning.answer(self.config, b, j['session_id'], question_id=a['id'], text=a['text'], disposition=a['disposition'], request_key=a['request_key'], model=model, retry_uncertain=retry)
                    self.update(job_id, pending_answer=None)
                if j['session_id']:
                    plan = planning.resume(self.config, b, j['session_id'], model=model, retry_uncertain=retry)
                else:
                    context = j['goal'] or 'Exploración general de la actividad disponible.'
                    plan = planning.start(self.config, b, j['analysis_id'], owner_context=context, request_key=key, model=model)
                self.update(job_id, session_id=plan['id'])
                if plan['questions']:
                    self.update(job_id, status='waiting', retry_uncertain=False)
                    return
                investigations = plan['revisions'][-1]['proposal']['investigations'] if plan['revisions'] else []
                if not any(i['status'] == 'ready' for i in investigations):
                    self.update(job_id, status='blocked', issue='Con los datos y respuestas disponibles no hay una investigación que podamos completar. Crea otro análisis con más contexto o un archivo más completo.')
                    return
                j = self.sync(job_id)
                self.update(job_id, phase='research')
                if j['research_id']:
                    work = research.resume(self.config, b, j['research_id'], model=model, retry_uncertain=retry)
                else:
                    work = research.start(self.config, b, plan['id'], request_key=key, model=model)
                self.update(job_id, research_id=work['id'])
                if not any(f['status'] == 'candidate' for f in work['findings']):
                    self.update(job_id, status='blocked', issue='El análisis no produjo hallazgos que puedan pasar a revisión. Puedes crear otro análisis con una pregunta más concreta o datos adicionales.')
                    return
                j = self.sync(job_id)
            self.update(job_id, phase='review')
            if j['pending_answer'] and j['pending_answer']['phase'] == 'review':
                a = j['pending_answer']
                review.answer(self.config, b, j['review_id'], step=int(a['id']), text=a['text'], disposition=a['disposition'], request_key=a['request_key'], analyst=model, reviewer=model, retry_uncertain=retry)
                self.update(job_id, pending_answer=None)
            if j['review_id']:
                result = review.resume(self.config, b, j['review_id'], analyst=model, reviewer=model, retry_uncertain=retry)
            else:
                result = review.start(self.config, b, j['research_id'], request_key=key, analyst=model, reviewer=model)
            self.update(job_id, review_id=result['id'], retry_uncertain=False)
            if result['publishable']:
                self.update(job_id, status='completed', phase='done')
            elif result['pending_questions']:
                self.update(job_id, status='waiting')
            else:
                self.update(job_id, status='blocked', issue='La revisión no ha aprobado un informe para entregar. Tus archivos y respuestas siguen guardados. Puedes iniciar otro análisis con una pregunta más acotada.')
        except Exception as error:
            LOG.exception('Web job %s failed', job_id)
            self.sync(job_id)
            self.update(job_id, status='failed', issue=failure_message(error))

    def work_once(self):
        # Session lock survives individual commits and prevents two workers claiming work.
        with connect(self.config) as db:
            if not db.execute('SELECT pg_try_advisory_lock(87120938) AS locked').fetchone()['locked']:
                return False
            j = db.execute("SELECT j.id,j.business_id FROM web_jobs j JOIN web_businesses b ON b.business_id=j.business_id WHERE status IN ('queued','running') ORDER BY created_at LIMIT 1").fetchone()
            if not j:
                from ..conversations import work_once
                return work_once(self, db)
            self.scoped(j['business_id']).run_job(j['id'])
            return True

    def worker(self):
        while not self.stop.is_set():
            try:
                if self.settings and memory_extraction.work_once(self.config, self.model_factory, self.settings):
                    continue
                if self.work_once():
                    continue
            except Exception:
                LOG.exception('Web worker unavailable')
            self.wake.wait(2)
            self.wake.clear()
