"""Durable local web jobs; all analytical work goes through existing services."""
import hashlib
import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .. import service as ingestion
from ..agent import service as planning, research, review
from ..agent.model import ModelAPIError, ModelClient, ModelNotReady, ModelSettings
from ..client_report import render_client
from ..database import connect
from ..execution import recover_executions
from ..storage import Storage

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


class WebError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def identifier(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise WebError('Identificador no válido.') from None


def bounded(value, label, limit, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise WebError(f'Revisa {label}: ' + (f'es obligatorio y admite hasta {limit} caracteres.' if required else f'admite hasta {limit} caracteres.'))
    return value.strip()


class Workspace:
    def __init__(self, config, settings=None, model_factory=ModelClient):
        self.config = config
        self.settings = settings
        self.model_factory = model_factory
        self.wake = threading.Event()
        self.stop = threading.Event()

    def create(self, data, filename, content):
        if not isinstance(data, dict):
            raise WebError('Los datos del análisis no son válidos.')
        key = identifier(data.get('request_key'))
        name = bounded(data.get('business'), 'el nombre del negocio', 100)
        context = bounded(data.get('context'), 'la descripción del negocio', 6000)
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
        signature = hashlib.sha256(json.dumps([name, context, goal, title, filename], ensure_ascii=False).encode() + content).hexdigest()
        with connect(self.config) as db, db.transaction():
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 7))', (str(key),))
            old = db.execute('SELECT id,request_sha256 FROM web_jobs WHERE request_key=%s', (key,)).fetchone()
            if old:
                if old['request_sha256'] != signature:
                    raise WebError('Este envío ya se guardó con otros datos. Inicia un nuevo análisis.', 409)
                return {'id': str(old['id'])}
            if self.settings is None:
                raise WebError('Falta configurar el modelo local. El borrador está guardado; podrás enviarlo cuando esté disponible.', 503)
            job_id, business = uuid4(), uuid4()
            upload_key = f'{business}/web/{job_id}/{filename}'
            path = Storage(self.config.storage).path(business, upload_key)
            path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o600)
            try:
                db.execute('INSERT INTO businesses(id,name,description) VALUES (%s,%s,%s)', (business, name, context))
                db.execute('''INSERT INTO web_jobs(id,request_key,request_sha256,business_id,title,context,goal,
                    filename,upload_key,byte_count,model_settings,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')''',
                    (job_id, key, signature, business, title, context, goal, filename, upload_key, len(content), Jsonb(asdict(self.settings))))
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        self.wake.set()
        return {'id': str(job_id)}

    def row(self, job_id):
        with connect(self.config) as db:
            job = db.execute('SELECT w.*,b.name AS business FROM web_jobs w JOIN businesses b ON b.id=w.business_id WHERE w.id=%s',
                             (identifier(job_id),)).fetchone()
        if not job:
            raise WebError('No encontramos este análisis en tu espacio de trabajo.', 404)
        return job

    def update(self, job_id, **values):
        allowed = {'status', 'phase', 'issue', 'pending_answer', 'retry_uncertain', 'analysis_id', 'session_id', 'research_id', 'review_id'}
        assert values.keys() <= allowed
        with connect(self.config) as db:
            db.execute('UPDATE web_jobs SET ' + ','.join(f'{key}=%s' for key in values) + ',updated_at=now() WHERE id=%s',
                       (*values.values(), job_id))

    def sync(self, job_id):
        """Discover durable child IDs even if the process died before a call returned."""
        j = self.row(job_id)
        with connect(self.config) as db:
            for field, table, where, params in [
                ('analysis_id', 'analyses', 'business_id=%s', (j['business_id'],)),
                ('session_id', 'agent_sessions', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
                ('research_id', 'agent_research', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
                ('review_id', 'agent_reviews', 'business_id=%s AND request_key=%s', (j['business_id'], 'web:' + str(j['id']))),
            ]:
                if not j[field]:
                    found = db.execute(f'SELECT id FROM {table} WHERE {where} ORDER BY created_at DESC LIMIT 1', params).fetchone()
                    if found:
                        self.update(job_id, **{field: found['id']})
        return self.row(job_id)

    def public(self, j):
        fields = ('id', 'title', 'business', 'context', 'goal', 'filename', 'byte_count', 'status', 'phase', 'created_at', 'updated_at', 'issue')
        return {key: j[key] for key in fields}

    def review_state(self, j):
        try:
            return review.show(self.config, j['business_id'], j['review_id'])
        except (OSError, ValueError):
            # One missing or changed evidence file must not hide the whole workspace.
            LOG.exception('Cannot read evidence for web job %s', j['id'])
            return {'publishable': False, 'pending_questions': [], 'unavailable': True}

    def listing(self):
        with connect(self.config) as db:
            rows = db.execute('SELECT w.*,b.name AS business FROM web_jobs w JOIN businesses b ON b.id=w.business_id ORDER BY w.created_at DESC').fetchall()
        result = []
        for j in rows:
            item = self.public(j)
            if j['status'] == 'completed' and j['review_id']:
                current = self.review_state(j)
                if not current['publishable']:
                    item.update(status='blocked', phase='review', issue='El informe necesita una nueva revisión.')
            result.append(item)
        return result

    def detail(self, job_id):
        j = self.sync(job_id)
        result = {**self.public(j), 'questions': [], 'answers': [], 'interpretations': [], 'files': [], 'publishable': False,
                  'activity': ''}
        b = j['business_id']
        if j['analysis_id']:
            data = ingestion.describe(self.config, b, j['analysis_id'])
            result['files'] = [{k: f[k] for k in ('original_names', 'status', 'row_count', 'column_count')} for f in data['files']]
        if j['session_id']:
            plan = planning.show(self.config, b, j['session_id'])
            result['questions'] = [{'id': q['id'], 'phase': 'planning', 'text': q['text'], 'reason': q['reason'], 'options': q['options']} for q in plan['questions']]
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
            job = db.execute('SELECT * FROM web_jobs WHERE id=%s FOR UPDATE', (identifier(job_id),)).fetchone()
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

    def retry(self, job_id):
        j = self.row(job_id)
        if j['status'] != 'failed':
            raise WebError('Solo se pueden reintentar los análisis con un fallo técnico.', 409)
        model = self.model_factory(ModelSettings(**j['model_settings']))
        try:
            if check := getattr(model, 'check_ready', None):
                check()
        except ModelNotReady as error:
            # Keep the job paused; a readiness request must never enqueue work
            # or trigger LM Studio's automatic model-loading attempt.
            raise WebError(str(error), 409) from None
        with connect(self.config) as db:
            row = db.execute("UPDATE web_jobs SET status='queued',issue=NULL,retry_uncertain=true,updated_at=now() WHERE id=%s AND status='failed' RETURNING id",
                             (identifier(job_id),)).fetchone()
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
        with session_lock(self.config, j['business_id'], j['session_id']):
            data = self.review_state(j)
            if not data['publishable']:
                raise WebError('Este informe no ha superado la revisión o ha quedado desactualizado.', 409)
            return render_client(data, data['updated_at'].strftime('%d/%m/%Y, %H:%M %Z'), embedded=True)

    def upload(self, job_id):
        j = self.row(job_id)
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
            with connect(self.config) as db:
                abandoned = db.execute("SELECT 1 FROM executions WHERE business_id=%s AND status IN ('preparing','running') LIMIT 1", (b,)).fetchone()
            if abandoned:
                recover_executions(self.config, b)
            if not j['analysis_id']:
                self.update(job_id, phase='upload')
                self.upload(job_id)  # Verify the persisted upload before the importer consumes it.
                path = Storage(self.config.storage).path(b, j['upload_key'])
                data = ingestion.import_batch(self.config, b, [path], title=j['title'])
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
                    context = f"Negocio: {j['business']}\n{j['context']}\nObjetivo: {j['goal'] or 'Exploración general de la actividad disponible.'}"
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
            j = db.execute("SELECT id FROM web_jobs WHERE status IN ('queued','running') ORDER BY created_at LIMIT 1").fetchone()
            if not j:
                return False
            self.run_job(j['id'])
            return True

    def worker(self):
        while not self.stop.is_set():
            try:
                if self.work_once():
                    continue
            except Exception:
                LOG.exception('Web worker unavailable')
            self.wake.wait(2)
            self.wake.clear()
