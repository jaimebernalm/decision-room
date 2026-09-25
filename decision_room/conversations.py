"""Durable chat with model-authored, checked prose and scoped tool execution.

Legacy templates remain readable/replayable; new decisions use chat_agent.Decision.
"""

from dataclasses import asdict
from datetime import datetime
import re
import unicodedata
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from .database import connect
from . import chat_agent
from .greetings import is_greeting, salutation
from .agent.model import ModelSettings, ModelRequestUncertain
from .agent import review
from .memory import context as ctx, service as memory, extraction, retrieval, semantic
from .web.errors import WebError, identifier, bounded
from .web.dossier import available as dataset_available
from .web.dashboard import projection

PROMPT_VERSION = chat_agent.PROMPT_VERSION


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal[
        'retrieve', 'investigate', 'explain', 'remember', 'clarify', 'missing', 'catalog', 'recall', 'respond', 'answer'
    ]
    retrieval: retrieval.Request | None
    analysis_id: str = Field(max_length=36)
    report_id: str = Field(max_length=36)
    claim_keys: list[str] = Field(max_length=20)
    question: str = Field(max_length=600)
    message_ids: list[str] = Field(max_length=10)
    text: str = Field(default='', max_length=12000)
    sources: list[str] = Field(default_factory=list, max_length=20)
    reply_kind: Literal['', 'date', 'time', 'capabilities', 'help', 'thanks', 'unavailable',
                        'greeting', 'greeting_repair', 'acknowledgement'] = ''
    answer_mode: Literal['summary', 'method', 'recency'] = 'summary'


def runtime_context():
    now = datetime.now().astimezone()
    return dict(server_time=now.isoformat(timespec='seconds'), timezone=str(now.tzinfo),
                web_access=False, live_business_feed=False,
                can_analyze_uploaded_datasets=True,
                available_sources=['saved business context', 'uploaded datasets', 'reviewed reports'])


def direct_question(text):
    """Narrow clock questions; compound/business requests still go through the router."""
    normalized = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))
    normalized = re.sub(r'[¿?¡!.,\s]+', ' ', normalized).strip()
    normalized = re.sub(r'^(hola |buenas )', '', normalized)
    if re.fullmatch(r'(que (dia|fecha) es( hoy)?|que dia (es|estamos) hoy|a que (dia|fecha) estamos|cual es la fecha( de hoy| actual)?|fecha (de hoy|actual)|what (day|date) is (it|today))', normalized):
        return 'date'
    if re.fullmatch(r'(que hora es( ahora)?|cual es la hora( actual)?|what time is it)', normalized):
        return 'time'
    return None


def direct_reply(kind, runtime, owner_text='', dialogue=()):
    if kind in ('date', 'time'):
        now = datetime.fromisoformat(runtime['server_time'])
        weekdays = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
        months = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
        text = (f"Hoy es {weekdays[now.weekday()]}, {now.day} de {months[now.month - 1]} de {now.year}."
                if kind == 'date' else f"Son las {now:%H:%M}.")
        text += f" Según el reloj del servidor ({runtime['timezone']}, UTC{now:%z})."
    elif kind in ('greeting', 'greeting_repair'):
        greeting = salutation(owner_text)
        if greeting == '¡Hola!' and kind == 'greeting_repair':
            greeting = next((salutation(item['owner']) for item in reversed(dialogue)
                             if salutation(item['owner']) != '¡Hola!'), greeting)
        text = greeting + (' Perdona, antes no te devolví el saludo.' if kind == 'greeting_repair' else '')
        text += ' ¿En qué te puedo ayudar?'
    else:
        text = {
            'capabilities': 'Puedo consultar lo que has guardado sobre tu negocio, los archivos que has añadido y los análisis revisados. No tengo acceso a internet ni a la actividad de tu empresa en tiempo real. La fecha de los datos depende de cada archivo.',
            'help': 'Puedo ayudarte a entender tus datos, explicar un resultado o recordar lo que me cuentes del negocio. ¿Qué te gustaría averiguar?',
            'thanks': 'De nada. Si quieres, podemos seguir con otra pregunta.',
            'acknowledgement': 'Vale. Cuando quieras, seguimos.',
            'unavailable': 'Con las fuentes que tengo aquí no puedo comprobar eso. Puedo consultar la información de tu negocio y los datos que hayas añadido, pero no internet ni otras cuentas externas.',
        }[kind]
    return dict(kind='answer', text=text, reply_kind=kind)


def dialogue_reply(response):
    """Bounded client-visible prose, not raw metrics or internal review messages."""
    if not response:
        return None
    parts = [response.get('text', '')]
    if response.get('kind') == 'evidence':
        parts += response.get('paragraphs') or [part for c in response.get('claims', [])
                                               for part in (c['statement'], c.get('interpretation', ''))]
    elif response.get('kind') == 'memory':
        parts += [f"{item['status']}: {item['content']['statement']}" for item in response.get('items', [])]
    elif response.get('kind') == 'questions':
        parts += [item['text'] for item in response.get('questions', [])]
    elif response.get('kind') == 'catalog':
        parts += [' · '.join([item.get('description', ''), ', '.join(item.get('names', [])),
                              ', '.join(item.get('columns', []))]) for item in response.get('items', [])]
    text = '\n'.join(part for part in parts if part)
    return dict(kind=response['kind'], text=text[:4000], truncated=len(text) > 4000,
                use='Conversation continuity only; not factual evidence.')


def revision(db, business):
    row = db.execute('SELECT revision FROM memory_heads WHERE business_id=%s', (business,)).fetchone()
    return row['revision'] if row else 0


def selected_sources(db, business, analysis_id):
    return [str(r['id']) for r in db.execute(
        'SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s',
        (business, analysis_id),
    ).fetchall()]


def snapshot(db, business, analysis_id, objective):
    selection = dict(
        analysis_id=str(analysis_id) if analysis_id else None,
        source_ids=selected_sources(db, business, analysis_id),
        period=ctx.period(),
        objective=objective,
    )
    catalog = ctx.datasets(db, business)
    if analysis_id:
        selected = ctx.datasets(db, business, analysis_id=analysis_id)
        catalog['items'] = selected['items'] + [item for item in catalog['items'] if item['analysis_id'] != str(analysis_id)]
    memories = ctx.scoped(ctx.effective(db, business), selection)
    if len(memory.encoded(memories).encode()) > ctx.MEMORY_BYTES:
        raise WebError('La memoria aplicable es demasiado amplia. Acota el conjunto de datos.', 409)
    profile = db.execute('SELECT name,description FROM businesses WHERE id=%s', (business,)).fetchone()
    return dict(
        business_id=str(business),
        session_id=None,
        selection=selection,
        revision=revision(db, business),
        profile=profile,
        memories=memories,
        catalog=catalog,
        tables={r['id']: ctx.table_version(db, business, r['id']) for r in catalog['items']},
        runtime=runtime_context(),
        rules='Current memory; explicit business/source scope; historical quotes are not facts; reviewed evidence only.',
    )


def fresh(db, saved, ignore_origins=None):
    if not saved:
        return False
    if revision(db, saved['business_id']) != saved['revision']:
        changes = db.execute(
            """SELECT DISTINCT s.origin_key FROM memory_revisions r JOIN memory_sources s ON s.id=r.source_id WHERE r.business_id=%s AND r.business_revision>%s""",
            (saved['business_id'], saved['revision']),
        ).fetchall()
        if not changes or not {r['origin_key'] for r in changes} <= set(ignore_origins or ()):
            return False
    if (
        db.execute('SELECT name,description FROM businesses WHERE id=%s', (saved['business_id'],)).fetchone()
        != saved['profile']
    ):
        return False
    return all(
        ctx.table_version(db, saved['business_id'], key) == value for key, value in saved['tables'].items()
    )


def search_history(config, db, manifest, request):
    """Retrieve owner+preceding question, never unreviewed assistant conclusions.

    Conservatively exclude fragments captured before any memory revision. This is
    deliberate: old quotes cannot restore a withdrawn/corrected declaration.
    """
    scope = retrieval._scope(db, manifest, request.id)
    rows = db.execute(
        """SELECT t.*,c.analysis_id FROM chat_turns t JOIN chat_conversations c ON c.id=t.conversation_id
        WHERE t.business_id=%s AND c.deleted_at IS NULL AND t.status IN ('completed','waiting') AND t.snapshot IS NOT NULL
        AND (%s::uuid IS NULL OR c.analysis_id IS NULL OR c.analysis_id=%s) ORDER BY t.created_at DESC LIMIT %s""",
        (manifest['business_id'], scope['analysis_id'], scope['analysis_id'], semantic.MAX_DOCUMENTS + 1),
    ).fetchall()
    if len(rows) > semantic.MAX_DOCUMENTS:
        raise ValueError('Too much conversation history; narrow the source scope.')
    available, docs = {}, []
    for row in rows:
        if not fresh(db, row['snapshot']):
            continue
        key = str(row['id'])
        fragment = dict(
            message_id=key,
            conversation_id=str(row['conversation_id']),
            analysis_id=str(row['analysis_id']) if row['analysis_id'] else None,
            text=row['payload']['text'],
            preceding_question=row['payload'].get('question', ''),
            classification='Historical owner text: may be a quote, hypothesis or question; consult current memory.',
            memory_source_id=str(row['memory_source_id']) if row['memory_source_id'] else None,
        )
        available[key] = (fragment, row['snapshot'])
        docs.append(
            dict(
                key=key,
                version=memory.digest(fragment),
                text=fragment['preceding_question'] + '\n' + fragment['text'],
            )
        )
    keys, search = semantic.rank(
        config, db, manifest['business_id'], 'chat', docs, request.query, request.limit
    )
    if any(not fresh(db, available[k][1]) for k in keys):
        raise ctx.StaleContext('Conversation context changed during retrieval.')
    return dict(items=[available[k][0] for k in keys], search=search), [
        dict(kind='chat', id=k, snapshot=available[k][1]) for k in keys
    ]


def reviewed(config, business, report_id, db=None):
    try:
        return review.show(config, business, report_id, _db=db)
    except (ValueError, OSError):
        return {'publishable': False}


def dependencies_current(config, db, saved, events):
    if not fresh(db, saved):
        return False
    reference = saved.get('finding_reference')
    if reference:
        r = reviewed(config, saved['business_id'], reference['report_id'], db)
        if not r['publishable'] or r['approved_sha256'] != reference['report_version']:
            return False
    for event in events:
        for dep in event['dependencies']:
            if (
                dep['kind'] == 'table'
                and ctx.table_version(db, saved['business_id'], dep['id']) != dep['metadata_version']
            ):
                return False
            if dep['kind'] == 'chat' and not fresh(db, dep['snapshot']):
                return False
            if (
                dep['kind'] == 'memory'
                and ctx.watch(ctx.effective(db, saved['business_id']), dep['selection']) != dep['watch']
            ):
                return False
            if dep['kind'] == 'report':
                result = reviewed(config, saved['business_id'], dep['id'], db)
                row = db.execute(
                    'SELECT approved_sha256 FROM agent_reviews WHERE id=%s', (dep['id'],)
                ).fetchone()
                if not result['publishable'] or row['approved_sha256'] != dep['version']:
                    return False
    return True


def brief(data, keys=None, mode='summary'):
    if not data['publishable']:
        raise WebError('La evidencia necesita una nueva revisión.', 409)
    report = data['report']
    claims = report['claims'] if not keys else [c for c in report['claims'] if c['key'] in keys]
    if not claims or (keys and set(keys) != {c['key'] for c in claims}):
        raise ValueError('Unknown reviewed claim reference.')
    metrics = []
    observations = {o['execution_id']: o for o in data['observations'] if o['current'] and o['result']}
    for claim in claims:
        for ref in claim['evidence']:
            observation = observations[ref['execution_id']]
            metrics.append(
                dict(
                    execution_id=ref['execution_id'],
                    metric=ref['metric'],
                    value=observation['result']['metrics'][ref['metric']],
                )
            )
    display = projection(data) or {}
    selected = {c['key'] for c in claims}
    if mode == 'method':
        paragraphs = ['El cálculo se hizo así:', *[c['method'] for c in claims],
                      *[c['statement'] for c in claims]]
    elif mode == 'recency':
        paragraphs = [f"La información que he podido comprobar en este informe corresponde a: {report['scope']['period']}.",
                      'Describe los registros de ese archivo. No me permite confirmar qué ha ocurrido después ni otros acontecimientos de la empresa.',
                      *[c['statement'] for c in claims]]
    else:
        paragraphs = [part for c in claims for part in (c['statement'], c['interpretation']) if part]
    return dict(
        answer_mode=mode,
        paragraphs=list(dict.fromkeys(paragraphs)),
        highlights=[h for h in display.get('highlights', []) if h['claim_key'] in selected],
        charts=[c for c in display.get('charts', []) if c['claim_key'] in selected],
        kind='evidence',
        report_id=str(data['id']),
        report_version=data['approved_sha256'],
        title=report['title'],
        metrics=metrics,
        scope=report['scope'],
        claims=claims,
        limitations=report['limitations'],
    )


def memory_reply(profile, items, progress):
    name = profile['name']
    if any(item['status'] == 'declared' for item in items):
        return f'Esto es lo que me has contado sobre {name}:'
    if items:
        return f'Tengo información sobre {name}, pero todavía necesita una aclaración antes de que pueda darla por buena:'
    if progress['failed'] or progress['uncertain']:
        return (f'He guardado lo que me contaste sobre {name}, pero aún no he podido incorporarlo a lo que sé del negocio. '
                'Puedes reintentar la preparación de la memoria y volver a preguntarme.')
    if progress['pending']:
        return (f'He guardado lo que me contaste sobre {name} y todavía lo estoy preparando. '
                'Vuelve a preguntarme en un momento.')
    return (f'He revisado la información guardada sobre {name} y todavía no encuentro nada que pueda contarte con seguridad. '
            'Si me cuentas a qué se dedica tu negocio o añades datos en Mi negocio, podré ayudarte mejor.')


def greeting_reply(manifest, owner_text=''):
    name = manifest['profile']['name']
    has_context = any(item['status'] == 'declared' for item in manifest['memories'])
    has_data = bool(manifest['catalog']['items'])
    if has_context and has_data:
        text = f'¡Hola! Tengo presente lo que me has contado sobre {name} y veo tus datos. ¿Qué te gustaría averiguar hoy?'
    elif has_context:
        text = f'¡Hola! Ya tengo presente lo que me has contado sobre {name}. ¿Qué te gustaría saber o investigar?'
    elif has_data:
        text = f'¡Hola! Veo los datos de {name}. ¿Qué te gustaría investigar con ellos?'
    else:
        text = f'¡Hola! ¿Qué te gustaría saber sobre {name}? También puedes contarme más del negocio o añadir datos para analizarlos.'
    return dict(kind='greeting', text=text.replace('¡Hola!', salutation(owner_text), 1))


class Conversations:
    def __init__(self, workspace):
        self.ws = workspace
        self.config = workspace.config
        self.business = workspace.business_id()

    def guard(self, data):
        if self.business is None or identifier(data.get('business_id')) != self.business:
            raise WebError('El negocio activo ha cambiado. Recarga la conversación.', 409)

    def conversation(self, db, chat_id, *, lock=False):
        row = db.execute(
            'SELECT * FROM chat_conversations WHERE id=%s AND business_id=%s AND deleted_at IS NULL'
            + (' FOR UPDATE' if lock else ''),
            (identifier(chat_id), self.business),
        ).fetchone()
        if not row:
            raise WebError('Conversación no encontrada.', 404)
        return row

    def turn(self, db, chat_id, turn_id):
        self.conversation(db, chat_id)
        row = db.execute(
            'SELECT * FROM chat_turns WHERE id=%s AND conversation_id=%s AND business_id=%s',
            (identifier(turn_id), identifier(chat_id), self.business),
        ).fetchone()
        if not row:
            raise WebError('Mensaje no encontrado.', 404)
        return row

    def listing(self):
        with connect(self.config) as db:
            return dict(
                business_id=self.business,
                conversations=db.execute(
                    '''SELECT c.*,last_turn.created_at AS last_message_at FROM chat_conversations c
                    LEFT JOIN LATERAL (SELECT created_at FROM chat_turns t
                        WHERE t.conversation_id=c.id ORDER BY created_at DESC,id DESC LIMIT 1) last_turn ON true
                    WHERE c.business_id=%s AND c.deleted_at IS NULL
                    ORDER BY COALESCE(last_turn.created_at,c.created_at) DESC,c.created_at DESC,c.id DESC''',
                    (self.business,),
                ).fetchall(),
                deleted_conversations=db.execute(
                    'SELECT id,title,deleted_at FROM chat_conversations WHERE business_id=%s AND deleted_at IS NOT NULL ORDER BY deleted_at DESC',
                    (self.business,),
                ).fetchall(),
                datasets=ctx.datasets(db, self.business) if self.business else {'items': [], 'more': False},
            )

    def delete(self, chat_id, data):
        self.guard(data)
        with connect(self.config) as db, db.transaction():
            self.conversation(db, chat_id, lock=True)
            db.execute('UPDATE chat_conversations SET deleted_at=now() WHERE id=%s', (chat_id,))
        return {'saved': True}

    def restore(self, chat_id, data):
        self.guard(data)
        with connect(self.config) as db, db.transaction():
            row = db.execute('SELECT id FROM chat_conversations WHERE id=%s AND business_id=%s AND deleted_at IS NOT NULL FOR UPDATE',
                             (identifier(chat_id), self.business)).fetchone()
            if not row:
                raise WebError('Conversación eliminada no encontrada.', 404)
            db.execute('UPDATE chat_conversations SET deleted_at=NULL WHERE id=%s', (chat_id,))
        self.ws.wake.set()
        return {'saved': True}

    def create(self, data):
        self.guard(data)
        key = identifier(data.get('request_key'))
        analysis = identifier(data['analysis_id']) if data.get('analysis_id') else None
        title = bounded(data.get('title') or 'Nueva conversación', 'el título', 160)
        with connect(self.config) as db, db.transaction():
            db.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 17))', (str(key),))
            old = db.execute(
                'SELECT * FROM chat_conversations WHERE business_id=%s AND request_key=%s',
                (self.business, key),
            ).fetchone()
            if old:
                if old['analysis_id'] != analysis or old['title'] != title:
                    raise WebError('Este envío ya creó una conversación distinta.', 409)
                return old
            if (
                analysis
                and not dataset_available(db, self.business, analysis)
            ):
                raise WebError('El conjunto de datos no está disponible en este negocio.', 409)
            return db.execute(
                """INSERT INTO chat_conversations(id,business_id,request_key,title,analysis_id)
                VALUES (%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(), self.business, key, title, analysis),
            ).fetchone()

    def finding_reference(self, db, value, analysis_id):
        if not isinstance(value, dict) or set(value) != {'report_id', 'report_version', 'claim_key'}:
            raise WebError('La referencia al hallazgo no es válida.')
        report_id = identifier(value['report_id'])
        r = reviewed(self.config, self.business, report_id, db)
        if not r['publishable'] or r['approved_sha256'] != value['report_version']:
            raise WebError('Este hallazgo ha cambiado o se ha retirado. Vuelve a Inicio para elegir uno vigente.', 409)
        claim = next((c for c in r['report']['claims'] if c['key'] == value['claim_key']), None)
        if not claim or (analysis_id and str(analysis_id) != str(r['analysis_id'])):
            raise WebError('El hallazgo no corresponde al conjunto seleccionado.', 409)
        executions = {e['execution_id'] for e in claim['evidence']}
        table_ids = {v['id'] for o in r['observations'] if o['execution_id'] in executions for v in o['inputs'].values()}
        sources = db.execute('SELECT DISTINCT source_id FROM prepared_tables WHERE business_id=%s AND id=ANY(%s::uuid[])',
                             (self.business, list(table_ids))).fetchall()
        return {**value, 'report_id': str(report_id), 'analysis_id': str(r['analysis_id']),
                'source_ids': sorted(str(x['source_id']) for x in sources),
                'title': claim['title'], 'period': r['report']['scope']['period']}

    def send(self, chat_id, data):
        self.guard(data)
        key = identifier(data.get('request_key'))
        text = bounded(data.get('text'), 'el mensaje', 6000)
        question_id = str(data.get('question_id') or '')
        reference = data.get('finding_reference')
        disposition = data.get('disposition', 'answered')
        if disposition not in ('answered', 'unknown', 'declined'):
            raise WebError('Respuesta no válida.')
        with connect(self.config) as db, db.transaction():
            chat = self.conversation(db, chat_id, lock=True)
            prior = db.execute(
                'SELECT * FROM chat_turns WHERE conversation_id=%s AND request_key=%s', (chat_id, key)
            ).fetchone()
            if prior:
                if any(
                    prior['payload'].get(k) != v
                    for k, v in dict(text=text, question_id=question_id, disposition=disposition).items()
                ):
                    raise WebError('Este envío ya contiene otro mensaje.', 409)
                saved_ref = prior['payload'].get('finding_reference')
                if (None if not saved_ref else {k: saved_ref[k] for k in ('report_id', 'report_version', 'claim_key')}) != reference:
                    raise WebError('Este envío ya contiene otro hallazgo.', 409)
                return {'id': prior['id']}
            if not self.ws.settings:
                raise WebError('Configura el modelo antes de enviar mensajes.', 409)
            if reference is not None:
                memory.lock(db, self.business)
                reference = self.finding_reference(db, reference, chat['analysis_id'])
                if not chat['analysis_id']:
                    chat['analysis_id'] = identifier(reference['analysis_id'])
                    db.execute('UPDATE chat_conversations SET analysis_id=%s WHERE id=%s', (chat['analysis_id'], chat_id))
            previous = db.execute(
                'SELECT * FROM chat_turns WHERE conversation_id=%s ORDER BY ordinal DESC LIMIT 1', (chat_id,)
            ).fetchone()
            waiting = db.execute(
                "SELECT * FROM chat_turns WHERE conversation_id=%s AND status='waiting' ORDER BY ordinal LIMIT 1", (chat_id,)
            ).fetchone()
            job, question, phase = None, '', None
            if waiting:
                questions = self.ws.detail(waiting['job_id'])['questions']
                chosen = next((q for q in questions if str(q['id']) == question_id), None)
                if not chosen:
                    raise WebError('Selecciona una aclaración pendiente.', 409)
                job, question, phase = waiting['job_id'], chosen['text'], chosen['phase']
            elif question_id:
                raise WebError('Esa aclaración ya no está pendiente.', 409)
            elif previous and previous['response'] and previous['response'].get('kind') == 'clarification':
                question = previous['response']['text']
            turn_id = uuid4()
            settings = asdict(self.ws.settings)
            source = None
            defer_memory = bool(not job and previous and previous['status'] != 'completed' and not direct_question(text))
            if not job and not defer_memory and not direct_question(text):
                source = memory.capture(
                    db,
                    self.business,
                    'chat_message:' + str(turn_id),
                    text=text,
                    kind='manual',
                    question=question,
                    disposition=disposition,
                    default_scope='analysis' if chat['analysis_id'] else 'business',
                    scope_id=chat['analysis_id'],
                    allow_business=True,
                    model_settings=settings,
                )
            payload = dict(
                text=text, question_id=question_id, disposition=disposition, question=question, phase=phase,
                memory_deferred=defer_memory,
            )
            if reference:
                payload['finding_reference'] = reference
            ordinal = previous['ordinal'] + 1 if previous else 1
            if waiting and previous['id'] != waiting['id']:
                successors = db.execute('SELECT id,status FROM chat_turns WHERE conversation_id=%s AND ordinal>%s ORDER BY ordinal DESC',
                                        (chat_id, waiting['ordinal'])).fetchall()
                if any(item['status'] != 'queued' for item in successors):
                    raise WebError('Hay una respuesta posterior en curso. Espera a que termine.', 409)
                for item in successors:
                    db.execute('UPDATE chat_turns SET ordinal=ordinal+1 WHERE id=%s', (item['id'],))
                ordinal = waiting['ordinal'] + 1
            db.execute(
                """INSERT INTO chat_turns(id,business_id,conversation_id,ordinal,request_key,payload,status,model_settings,memory_source_id,job_id)
                VALUES (%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s)""",
                (
                    turn_id,
                    self.business,
                    chat_id,
                    ordinal,
                    key,
                    Jsonb(payload),
                    Jsonb(settings),
                    source['id'] if source else None,
                    job,
                ),
            )
            if job:
                db.execute("UPDATE chat_turns SET status='completed' WHERE id=%s", (waiting['id'],))
        self.ws.wake.set()
        return {'id': turn_id}

    def events(self, db, turn):
        return db.execute(
            'SELECT * FROM chat_retrievals WHERE turn_id=%s AND attempt=%s ORDER BY ordinal',
            (turn['id'], turn['attempt']),
        ).fetchall()

    def detail(self, chat_id):
        with connect(self.config) as db:
            chat = self.conversation(db, chat_id)
            turns = db.execute(
                'SELECT * FROM chat_turns WHERE conversation_id=%s ORDER BY ordinal', (chat_id,)
            ).fetchall()
            result = []
            previous_snapshot = None
            for t in turns:
                value = {
                    k: t[k]
                    for k in (
                        'id',
                        'ordinal',
                        'payload',
                        'status',
                        'response',
                        'issue',
                        'job_id',
                        'report_requested',
                        'created_at',
                    )
                }
                if t['snapshot']:
                    if previous_snapshot and any(
                        previous_snapshot.get(key) != t['snapshot'].get(key)
                        for key in ('revision', 'profile', 'tables')
                    ):
                        value['context_changed_before'] = True
                    previous_snapshot = t['snapshot']
                if t['response'] and t['response'].get('report_id'):
                    r = reviewed(self.config, self.business, t['response']['report_id'])
                    valid = r['publishable'] and r['approved_sha256'] == t['response'].get('report_version')
                    if valid and t['response']['kind'] == 'evidence':
                        value['response'] = brief(r, [c['key'] for c in t['response']['claims']], t['response'].get('answer_mode', 'summary'))
                else:
                    valid = True
                if not t['job_id'] and t['snapshot'] and (t['response'] or {}).get('kind') != 'answer':
                    valid = valid and dependencies_current(self.config, db, t['snapshot'], self.events(db, t))
                if not valid:
                    value.update(
                        status='stale',
                        historical=bool(t['response']),
                        report_outdated=bool(t['response'] and t['response'].get('report_id')),
                        issue=None if t['response'] else 'El contexto o la evidencia han cambiado. Recalcula este mensaje.',
                    )
                if t['status'] == 'waiting' and t['job_id']:
                    detail = self.ws.detail(t['job_id'])
                    if detail.get('context_stale'):
                        value.update(status='stale', response=None, issue=detail['issue'])
                    else:
                        value['questions'] = detail['questions']
                result.append(value)
            context_changed_after = bool(previous_snapshot and not fresh(db, previous_snapshot))
            return dict(
                conversation=chat,
                dataset=db.execute('SELECT a.title,COALESCE(v.version,1) AS version,v.corrected,v.superseded_by FROM analyses a LEFT JOIN dataset_versions v ON v.analysis_id=a.id WHERE a.id=%s AND a.business_id=%s', (chat['analysis_id'], self.business)).fetchone() if chat['analysis_id'] else None,
                turns=result,
                context_changed_after=context_changed_after,
                memory=memory.status(self.config, self.business),
                memory_items=ctx.scoped(
                    ctx.effective(db, self.business),
                    {
                        'analysis_id': str(chat['analysis_id']) if chat['analysis_id'] else None,
                        'source_ids': selected_sources(db, self.business, chat['analysis_id']),
                        'period': ctx.period(),
                    },
                ),
            )

    def retry(self, chat_id, turn_id, data):
        self.guard(data)
        # Serialize retries with processing and sends. A second click cannot reset
        # a newly running turn or authorize a second provider request.
        with connect(self.config) as db, db.transaction():
            if not db.execute(
                'SELECT pg_try_advisory_xact_lock(hashtextextended(%s,18)) AS locked',
                (str(identifier(turn_id)),),
            ).fetchone()['locked']:
                raise WebError('El mensaje todavía está procesándose.', 409)
            self.conversation(db, chat_id, lock=True)
            turn = self.turn(db, chat_id, turn_id)
            successors = db.execute(
                'SELECT status FROM chat_turns WHERE conversation_id=%s AND ordinal>%s', (chat_id, turn['ordinal'])
            ).fetchall()
            if any(item['status'] != 'queued' for item in successors):
                raise WebError('Abre un nuevo mensaje para recalcular una respuesta anterior.', 409)
            item = next(x for x in self.detail(chat_id)['turns'] if x['id'] == turn['id'])
            if turn['status'] in ('queued', 'routing', 'processing') or item['status'] not in (
                'failed',
                'stale',
                'blocked',
            ):
                raise WebError('Este mensaje no necesita reintento.', 409)
            if turn['job_id']:
                # On explicit recalculation after a memory change, do not replay
                # historical quotations selected under the old memory revision.
                origin = db.execute(
                    'SELECT snapshot FROM chat_turns WHERE job_id=%s ORDER BY ordinal LIMIT 1',
                    (turn['job_id'],),
                ).fetchone()
                if origin and not fresh(db, origin['snapshot']):
                    clear_context = True
                else:
                    clear_context = False
                self.ws.retry(turn['job_id'], _db=db)
                if clear_context:
                    db.execute("UPDATE web_jobs SET context='' WHERE id=%s", (turn['job_id'],))
            elif turn['memory_source_id']:
                extraction.retry(self.config, self.business, turn['memory_source_id'])
            db.execute(
                'UPDATE chat_turns SET status=%s,attempt=attempt+1,snapshot=NULL,response=NULL,issue=NULL,response_history=%s,updated_at=now() WHERE id=%s',
                (
                    'processing' if turn['job_id'] else 'queued',
                    Jsonb(
                        turn['response_history']
                        + [
                            dict(
                                attempt=turn['attempt'],
                                response=turn['response'],
                                snapshot=turn['snapshot'],
                                status=turn['status'],
                                issue=turn['issue'],
                            )
                        ]
                    ),
                    turn_id,
                ),
            )
        self.ws.wake.set()
        return {'saved': True}

    def report(self, chat_id, turn_id, data=None):
        if data is not None:
            self.guard(data)
        with connect(self.config) as db, db.transaction():
            t = self.turn(db, chat_id, turn_id)
            memory.lock(db, self.business)
            if not t['response'] or not t['response'].get('report_id'):
                raise WebError('Este mensaje todavía no tiene evidencia revisada.', 409)
            if not t['job_id'] and not dependencies_current(
                self.config, db, t['snapshot'], self.events(db, t)
            ):
                raise WebError('La respuesta ha quedado desactualizada.', 409)
            r = reviewed(self.config, self.business, t['response']['report_id'], db)
            if not r['publishable'] or r['approved_sha256'] != t['response'].get('report_version'):
                raise WebError('El informe necesita una nueva revisión.', 409)
            if data is not None:
                db.execute('UPDATE chat_turns SET report_requested=true WHERE id=%s', (turn_id,))
                return {'saved': True}
            if not t['report_requested']:
                raise WebError('Genera primero el informe de este mensaje.', 409)
            from .client_report import render_client

            return render_client(r, r['updated_at'].strftime('%d/%m/%Y, %H:%M %Z'), embedded=True)

    def resolve(self, chat_id, data):
        """Owner explicitly chooses an extracted alternative; optimistic memory edit."""
        self.guard(data)
        with connect(self.config) as db:
            self.conversation(db, chat_id)
            fact = next(
                (r for r in memory.current(db, self.business) if str(r['fact_id']) == data.get('fact_id')),
                None,
            )
            if not fact or fact['revision'] != data.get('revision'):
                raise WebError('El recuerdo ha cambiado. Recarga antes de confirmarlo.', 409)
            alternative = data.get('alternative')
            if type(alternative) is not int or alternative < 0 or alternative >= len(fact['alternatives']):
                raise WebError('Selecciona una propuesta disponible.')
            content = fact['alternatives'][alternative]['content']
        try:
            memory.change(
                self.config,
                self.business,
                action='correct',
                request_key='chat-confirm:' + str(identifier(data.get('request_key'))),
                content=content,
                fact_id=str(fact['fact_id']),
                expected_revision=fact['revision'],
                original_text=content['statement'],
            )
        except memory.MemoryError as error:
            raise WebError(str(error), error.status) from None
        return {'saved': True}

    def _answer(self, db, turn, ordinal, action, context, model):
        """Check free prose against server-owned sources before publishing it.

        Persist the review before network I/O. Interrupted reviews require the
        same explicit retry as interrupted author calls; completed ones replay.
        """
        available = context.get('available_sources') or chat_agent.sources_for(context)
        unknown = set(action.sources) - available.keys()
        cited = {key: available[key] for key in dict.fromkeys(action.sources) if key in available}
        source_issues = ['Use only available source keys; unknown: ' + ', '.join(sorted(unknown))] if unknown else []
        reference = context['message'].get('finding_reference')
        if reference and not any(e['request']['tool'] == 'open_report'
                                 and e['response'].get('id') == reference['report_id']
                                 and e['response'].get('version') == reference['report_version']
                                 and f'tool/{e.get("ordinal", i)}' in cited
                                 for i, e in enumerate(context['retrievals'])):
            source_issues.append('Open and cite the exact report/version in finding_reference before answering about its claim.')
        check_context = dict(message=context['message'], recent_dialogue=context['recent_dialogue'],
                             draft=action.text, cited_sources=cited,
                             runtime=context['chat_context'].get('runtime', {}),
                             memory_status=context['chat_context'].get('memory_status', {}),
                             saved_corrections=context['chat_context'].get('saved_corrections', []),
                             finding_reference=context['message'].get('finding_reference'))
        row = db.execute('SELECT * FROM chat_answer_reviews WHERE turn_id=%s AND attempt=%s AND ordinal=%s',
                         (turn['id'], turn['attempt'], ordinal)).fetchone()
        if row and row['status'] != 'completed':
            raise ModelRequestUncertain('Interrupted answer review requires explicit retry.')
        if row:
            result = row['response']
        else:
            db.execute("INSERT INTO chat_answer_reviews(turn_id,attempt,ordinal,prompt_version,context,status) VALUES (%s,%s,%s,%s,%s,'running')",
                       (turn['id'], turn['attempt'], ordinal, PROMPT_VERSION, Jsonb(check_context)))
            if source_issues:
                result, usage = dict(approved=False, issues=source_issues), {}
            else:
                result, usage = model.review_chat_answer(check_context)
            checked = chat_agent.AnswerReview.model_validate(result)
            if checked.approved and checked.issues:
                raise ValueError('Approved review must not contain unresolved issues.')
            db.execute("UPDATE chat_answer_reviews SET response=%s,usage=%s,status='completed' WHERE turn_id=%s AND attempt=%s AND ordinal=%s",
                       (Jsonb(result), Jsonb(usage), turn['id'], turn['attempt'], ordinal))
        if not result['approved']:
            return None
        response = dict(kind='grounded_answer', text=action.text.strip(),
                        sources=[dict(reference=key, label=item['label']) for key, item in cited.items()])
        # An optional evidence attachment retains report export and version checks.
        opened = [e['response'] for i, e in enumerate(context['retrievals'])
                  if f'tool/{e.get("ordinal", i)}' in cited and e['request']['tool'] == 'open_report' and 'error' not in e['response']]
        if opened:
            ref = context['message'].get('finding_reference')
            report = next((r for r in opened if ref and r['id'] == ref['report_id']), opened[-1])
            evidence = brief(review.show(self.config, self.business, report['id']), [ref['claim_key']] if ref else None)
            response.update(evidence=evidence, report_id=evidence['report_id'], report_version=evidence['report_version'])
        return response

    def _save(self, db, turn, status, response=None, issue=None):
        db.execute(
            'UPDATE chat_turns SET status=%s,response=%s,issue=%s,updated_at=now() WHERE id=%s',
            (status, Jsonb(response) if response else None, issue, turn['id']),
        )

    def _job(self, db, chat, turn, analysis_id):
        # Persist job and link atomically: recovery cannot create a second analysis.
        with db.transaction():
            memory.lock(db, self.business)
            if not dependencies_current(self.config, db, turn['snapshot'], self.events(db, turn)):
                raise ctx.StaleContext('Context changed before investigation.')
            if chat['analysis_id'] and str(chat['analysis_id']) != analysis_id:
                raise ValueError('Cannot silently switch the selected dataset.')
            if not dataset_available(db, self.business, identifier(analysis_id)):
                raise ValueError('Analysis unavailable.')
            call = db.execute(
                'SELECT context FROM chat_calls WHERE turn_id=%s AND attempt=%s ORDER BY ordinal DESC LIMIT 1',
                (turn['id'], turn['attempt']),
            ).fetchone()
            context = call['context']
            quotes = list(context['recent_owner_messages'])
            for event in self.events(db, turn):
                if event['request']['tool'] == 'search_chats':
                    quotes.extend(event['response'].get('items', []))
            reference = turn['payload'].get('finding_reference')
            dependencies = ([dict(kind='report', id=reference['report_id'], version=reference['report_version'])] if reference else [])
            for quote in quotes:
                row = db.execute(
                    'SELECT snapshot FROM chat_turns WHERE id=%s AND business_id=%s',
                    (quote['message_id'], self.business),
                ).fetchone()
                if not row or not fresh(db, row['snapshot']):
                    raise ctx.StaleContext('Historical context changed before investigation.')
                dependencies.append(dict(kind='chat', id=quote['message_id'], snapshot=row['snapshot']))
            continuation = dict(
                context=dict(
                    finding_reference=reference,
                    historical_owner_quotes=quotes,
                    reviewed_result_pointers=context['recent_reviewed_results'],
                    rule='Historical quotes may be hypotheses; current memory wins. Open reports before using their conclusions.',
                ),
                dependencies=dependencies,
            )
            job = uuid4()
            db.execute(
                """INSERT INTO web_jobs(id,request_key,request_sha256,business_id,analysis_id,title,context,goal,filename,upload_key,byte_count,model_settings,status,phase,business_name,origin)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'','',0,%s,'queued','planning',%s,'chat')""",
                (
                    job,
                    turn['id'],
                    memory.digest(turn['payload']),
                    self.business,
                    analysis_id,
                    chat['title'],
                    memory.encoded(continuation),
                    turn['payload']['text'],
                    Jsonb(turn['model_settings']),
                    turn['snapshot']['profile']['name'],
                ),
            )
            db.execute("UPDATE chat_turns SET job_id=%s,status='processing' WHERE id=%s", (job, turn['id']))
            db.execute('UPDATE chat_conversations SET analysis_id=%s WHERE id=%s', (analysis_id, chat['id']))

    def run(self, turn_id):
        with connect(self.config) as db:
            if not db.execute(
                'SELECT pg_try_advisory_lock(hashtextextended(%s,18)) AS locked', (str(identifier(turn_id)),)
            ).fetchone()['locked']:
                return
            turn = db.execute(
                'SELECT * FROM chat_turns WHERE id=%s AND business_id=%s', (turn_id, self.business)
            ).fetchone()
            if not turn or turn['status'] not in ('queued', 'routing', 'processing'):
                return
            if db.execute("SELECT 1 FROM chat_turns WHERE conversation_id=%s AND ordinal<%s AND status<>'completed' LIMIT 1",
                          (turn['conversation_id'], turn['ordinal'])).fetchone():
                return
            chat = db.execute('SELECT * FROM chat_conversations WHERE id=%s AND business_id=%s AND deleted_at IS NULL',
                              (turn['conversation_id'], self.business)).fetchone()
            if not chat:
                return
            try:
                if turn['payload'].get('memory_deferred'):
                    with db.transaction():
                        source = memory.capture(
                            db, self.business, 'chat_message:' + str(turn_id),
                            text=turn['payload']['text'], kind='manual',
                            question=turn['payload'].get('question', ''),
                            disposition=turn['payload']['disposition'],
                            default_scope='analysis' if chat['analysis_id'] else 'business',
                            scope_id=chat['analysis_id'], allow_business=True,
                            model_settings=turn['model_settings'],
                        )
                        payload = {**turn['payload'], 'memory_deferred': False}
                        db.execute('UPDATE chat_turns SET memory_source_id=%s,payload=%s WHERE id=%s',
                                   (source['id'], Jsonb(payload), turn_id))
                        turn = {**turn, 'memory_source_id': source['id'], 'payload': payload}
                if turn['job_id']:
                    if turn['status'] == 'queued':
                        a = turn['payload']
                        self.ws.reply(
                            turn['job_id'],
                            dict(
                                request_key=str(turn['id']),
                                question_id=a['question_id'],
                                phase=a['phase'],
                                text=a['text'],
                                disposition=a['disposition'],
                            ),
                        )
                        self._save(db, turn, 'processing')
                        return
                    job = self.ws.detail(turn['job_id'])
                    # Snapshot captures the clarification's current memory; history is still labelled as a quote.
                    saved = snapshot(db, self.business, chat['analysis_id'], turn['payload']['text'])
                    db.execute('UPDATE chat_turns SET snapshot=%s WHERE id=%s', (Jsonb(saved), turn_id))
                    if job['publishable']:
                        row = self.ws.row(turn['job_id'])
                        self._save(db, turn, 'completed', brief(self.ws.review_state(row)))
                    elif job['status'] == 'waiting':
                        self._save(db, turn, 'waiting', dict(kind='questions', questions=job['questions']))
                    else:
                        self._save(
                            db,
                            turn,
                            job['status'] if job['status'] in ('failed', 'blocked') else 'processing',
                            issue=job['issue'],
                        )
                    return
                model = self.ws.model_factory(ModelSettings(**turn['model_settings']))
                if turn['memory_source_id']:
                    extraction.process(self.config, self.business, turn['memory_source_id'], model)
                    source = db.execute(
                        'SELECT status FROM memory_sources WHERE id=%s', (turn['memory_source_id'],)
                    ).fetchone()
                    if source['status'] != 'applied':
                        raise ValueError('Memory extraction needs explicit retry.')
                if not turn['snapshot']:
                    with db.transaction():
                        memory.lock(db, self.business)
                        turn['snapshot'] = snapshot(
                            db, self.business, chat['analysis_id'], turn['payload']['text']
                        )
                        if turn['memory_source_id']:
                            source_response = db.execute(
                                'SELECT response FROM memory_sources WHERE id=%s',
                                (turn['memory_source_id'],),
                            ).fetchone()['response'] or {}
                            correction_candidates = [candidate for candidate in source_response.get('candidates', [])
                                                     if candidate.get('correction_of') or candidate.get('profile_replacement')]
                            saved_corrections = db.execute(
                                """SELECT fact_id,revision,content FROM memory_revisions
                                WHERE business_id=%s AND source_id=%s AND status='declared'
                                ORDER BY business_revision""",
                                (self.business, turn['memory_source_id']),
                            ).fetchall() if correction_candidates else []
                            turn['snapshot']['saved_corrections'] = [
                                dict(fact_id=str(row['fact_id']), revision=row['revision'],
                                     statement=row['content']['statement'])
                                for row in saved_corrections
                            ]
                            for candidate in correction_candidates:
                                if (candidate.get('profile_replacement') and
                                    not any(saved['statement'] == candidate['content']['statement']
                                            for saved in turn['snapshot']['saved_corrections'])):
                                    turn['snapshot']['saved_corrections'].append(dict(
                                        statement=candidate['content']['statement'], profile_updated=True))
                        if turn['payload'].get('finding_reference'):
                            turn['snapshot']['finding_reference'] = turn['payload']['finding_reference']
                        db.execute(
                            "UPDATE chat_turns SET snapshot=%s,status='routing' WHERE id=%s",
                            (Jsonb(turn['snapshot']), turn_id),
                        )
                turn['snapshot']['memory_status'] = memory.status(self.config, self.business)
                for ordinal in range(ctx.MAX_RETRIEVALS + 1):
                    events = self.events(db, turn)
                    if not dependencies_current(self.config, db, turn['snapshot'], events):
                        raise ctx.StaleContext('Context changed; retry with current memory.')
                    call = db.execute(
                        'SELECT * FROM chat_calls WHERE turn_id=%s AND attempt=%s AND ordinal=%s',
                        (turn_id, turn['attempt'], ordinal),
                    ).fetchone()
                    if call and call['status'] != 'completed':
                        raise ModelRequestUncertain('Interrupted conversation call requires explicit retry.')
                    if not call:
                        recent = db.execute(
                            'SELECT id,payload,response,snapshot FROM chat_turns WHERE conversation_id=%s AND ordinal<%s ORDER BY ordinal DESC LIMIT 12',
                            (chat['id'], turn['ordinal']),
                        ).fetchall()
                        history = [
                            dict(
                                message_id=str(x['id']),
                                owner=x['payload']['text'],
                                preceding_question=x['payload'].get('question', ''),
                            )
                            for x in reversed(recent)
                            if fresh(db, x['snapshot'])
                        ]
                        current_ids = {x['message_id'] for x in history}
                        dialogue = [dict(message_id=str(x['id']), owner=x['payload']['text'],
                                         assistant=dialogue_reply(x['response']) if str(x['id']) in current_ids else
                                         dict(kind='stale', text='Earlier reply is outdated; retrieve current sources before answering.'),
                                         current_context=str(x['id']) in current_ids)
                                    for x in reversed(recent)]
                        result_refs = []
                        for item in recent:
                            response = item['response'] or {}
                            if not response.get('report_id'):
                                continue
                            result = reviewed(self.config, self.business, response['report_id'])
                            if result['publishable'] and result['approved_sha256'] == response.get('report_version'):
                                result_refs.append(
                                    dict(
                                        report_id=response['report_id'],
                                        title=response.get('evidence', response)['title'],
                                        scope=response.get('evidence', response)['scope'],
                                    )
                                )
                            else:
                                for exchange in dialogue:
                                    if exchange['message_id'] == str(item['id']):
                                        exchange['assistant'] = dict(kind='evidence', text='Previous evidence is no longer current; retrieve current sources before answering.')
                        context = dict(
                            recent_reviewed_results=result_refs,
                            message=turn['payload'],
                            chat_context=turn['snapshot'],
                            recent_owner_messages=history,
                            recent_dialogue=dialogue,
                            retrievals=[{k: e[k] for k in ('ordinal', 'request', 'response')} for e in events],
                        )
                        context['available_sources'] = chat_agent.sources_for(context)
                        context['remaining_steps'] = ctx.MAX_RETRIEVALS - ordinal
                        context['validation_feedback'] = [r['response']['issues'] for r in db.execute(
                            "SELECT response FROM chat_answer_reviews WHERE turn_id=%s AND attempt=%s AND status='completed' ORDER BY ordinal",
                            (turn_id, turn['attempt'])).fetchall() if not r['response']['approved']]
                        if len(memory.encoded(context).encode()) > ctx.CONTEXT_BYTES:
                            raise ValueError('Conversation context exceeds safe limit.')
                        db.execute(
                            "INSERT INTO chat_calls(turn_id,attempt,ordinal,prompt_version,context,status) VALUES (%s,%s,%s,%s,%s,'running')",
                            (turn_id, turn['attempt'], ordinal, PROMPT_VERSION, Jsonb(context)),
                        )
                        output, usage = model.generate_chat(context)
                        db.execute(
                            "UPDATE chat_calls SET response=%s,usage=%s,status='completed' WHERE turn_id=%s AND attempt=%s AND ordinal=%s",
                            (Jsonb(output), Jsonb(usage), turn_id, turn['attempt'], ordinal),
                        )
                    else:
                        output = call['response']
                        context = call['context']
                    if output.get('action') == 'answer' or 'text' in output:
                        decision = chat_agent.Decision.model_validate(output)
                        chat_agent.validate_decision(decision)
                        action = Action.model_validate(dict(report_id='', claim_keys=[], question='', message_ids=[], **decision.model_dump()))
                    else:
                        # Replay legacy persisted decisions; the provider no longer sees these actions.
                        action = Action.model_validate(output)
                    if action.action == 'retrieve':
                        if not action.retrieval or any(
                            (
                                action.analysis_id,
                                action.report_id,
                                action.claim_keys,
                                action.message_ids,
                                action.reply_kind,
                            )
                        ):
                            raise ValueError('Retrieval cannot mix actions.')
                        if ordinal >= ctx.MAX_RETRIEVALS:
                            raise ValueError('Retrieval budget exhausted.')
                        if not any(e['ordinal'] == ordinal for e in events):
                            duplicate = next((e for e in events if e['request'] == action.retrieval.model_dump()), None)
                            try:
                                if duplicate:
                                    response, deps = dict(error=f'Identical lookup already performed at tool/{duplicate["ordinal"]}. Use its result or choose another tool; do not repeat.', items=[]), duplicate['dependencies']
                                else:
                                    response, deps = retrieval.retrieve(
                                        self.config,
                                        db,
                                        None,
                                        action.retrieval,
                                        manifest=turn['snapshot'],
                                        opened=[
                                            dict(response=e['response'])
                                            for e in events
                                            if e['request']['tool'] == 'open_report'
                                            and 'error' not in e['response']
                                        ],
                                    )
                            except ctx.StaleContext:
                                raise
                            except (ValueError, OSError):
                                response, deps = (
                                    dict(
                                        error='Object unavailable in the permitted current context. Search for applicable references; never guess identifiers.',
                                        items=[],
                                    ),
                                    [],
                                )
                            with db.transaction():
                                memory.lock(db, self.business)
                                if not dependencies_current(
                                    self.config, db, turn['snapshot'], [*events, dict(dependencies=deps)]
                                ):
                                    raise ctx.StaleContext('Context changed during retrieval.')
                                db.execute(
                                    'INSERT INTO chat_retrievals VALUES (%s,%s,%s,%s,%s,%s)',
                                    (
                                        turn_id,
                                        turn['attempt'],
                                        ordinal,
                                        Jsonb(action.retrieval.model_dump()),
                                        Jsonb(response),
                                        Jsonb(deps),
                                    ),
                                )
                        continue
                    if action.retrieval is not None:
                        raise ValueError('Unexpected retrieval payload.')
                    if action.reply_kind and action.action != 'respond':
                        raise ValueError('Conversational reply cannot mix actions.')
                    if action.action == 'investigate':
                        self._job(db, chat, turn, action.analysis_id)
                        return
                    if action.action == 'answer':
                        response = self._answer(db, turn, ordinal, action, context, model)
                        if response is None:
                            if ordinal >= ctx.MAX_RETRIEVALS:
                                raise ValueError('Answer validation budget exhausted.')
                            continue
                    elif action.action == 'explain':
                        opened = next(
                            (
                                e
                                for e in events
                                if e['request']['tool'] == 'open_report'
                                and e['response'].get('id') == action.report_id
                            ),
                            None,
                        )
                        if not opened:
                            raise ValueError('Open report before explaining its claims.')
                        reference = turn['payload'].get('finding_reference')
                        keys = action.claim_keys
                        if reference:
                            if action.report_id != reference['report_id']:
                                raise ValueError('Explanation must use the selected finding report.')
                            keys = [reference['claim_key']]
                        response = brief(review.show(self.config, self.business, action.report_id), keys, action.answer_mode)
                    elif action.action == 'catalog':
                        items = {x['id']: x for x in turn['snapshot']['catalog']['items']}
                        for event in events:
                            if event['request']['tool'] == 'search_datasets':
                                items.update({x['id']: x for x in event['response']['items']})
                        response = dict(
                            kind='catalog',
                            items=list(items.values()),
                            text=(('He encontrado datos de tu negocio, pero todavía no tengo un resultado revisado que confirme qué periodo cubren. Puedo analizarlos si quieres. '
                                   'No tengo acceso a lo que ocurre en la empresa en tiempo real.') if items else
                                  'Todavía no encuentro datos con los que comprobar qué ha pasado en tu negocio. Puedes añadir un archivo o contarme una novedad.')
                                 if action.answer_mode == 'recency' else 'Estos son los datos que tengo disponibles para tu negocio.',
                        )
                    elif action.action == 'recall':
                        found = {
                            x['message_id']: x
                            for e in events
                            if e['request']['tool'] == 'search_chats'
                            for x in e['response']['items']
                        }
                        if not action.message_ids or any(key not in found for key in action.message_ids):
                            raise ValueError('Search original conversation before quoting it.')
                        response = dict(
                            kind='history',
                            items=[found[key] for key in action.message_ids],
                            text='Antecedentes de conversaciones. Son citas históricas, no hechos confirmados actuales.',
                        )
                    elif action.action == 'respond':
                        if not action.reply_kind or any((action.analysis_id, action.report_id, action.claim_keys, action.question, action.message_ids)):
                            raise ValueError('Choose one conversational reply without unrelated references.')
                        response = direct_reply(action.reply_kind, turn['snapshot'].get('runtime') or runtime_context(),
                                                turn['payload']['text'], context.get('recent_dialogue', []))
                    elif action.action == 'remember':
                        items = turn['snapshot']['memories']
                        response = dict(
                            kind='memory',
                            text=memory_reply(turn['snapshot']['profile'], items,
                                              memory.status(self.config, self.business)),
                            items=items,
                        )
                    elif action.action == 'clarify':
                        # A question cannot smuggle an unreviewed numerical answer.
                        q = action.question.strip()
                        if '¿' in q:
                            q = q[q.rfind('¿') :]
                        if not q.startswith('¿') or not q.endswith('?') or any(c.isdigit() for c in q):
                            q = '¿Qué quieres averiguar y sobre qué datos?'
                        response = dict(kind='clarification', text=q)
                    else:
                        response = dict(
                            kind='missing',
                            text='He revisado la información disponible, pero todavía no encuentro lo necesario para responderte con seguridad. Si me das más contexto o añades datos, podré intentarlo de nuevo.',
                        )
                    with db.transaction():
                        memory.lock(db, self.business)
                        if not dependencies_current(self.config, db, turn['snapshot'], events):
                            raise ctx.StaleContext('Context changed before publication.')
                        self._save(db, turn, 'completed', response)
                    return
            except Exception as error:
                db.execute(
                    "UPDATE chat_calls SET status=%s WHERE turn_id=%s AND attempt=%s AND status='running'",
                    (
                        'uncertain' if isinstance(error, ModelRequestUncertain) else 'failed',
                        turn_id,
                        turn['attempt'],
                    ),
                )
                db.execute(
                    "UPDATE chat_answer_reviews SET status=%s WHERE turn_id=%s AND attempt=%s AND status='running'",
                    ('uncertain' if isinstance(error, ModelRequestUncertain) else 'failed', turn_id, turn['attempt']))
                import logging

                logging.getLogger(__name__).exception('Conversation turn %s interrupted', turn_id)
                self._save(
                    db,
                    turn,
                    'failed',
                    issue='El mensaje está guardado, pero el procesamiento se ha interrumpido. Reintenta para continuar; si hubo una petición incierta al modelo, el reintento puede repetirla.',
                )


def work_once(workspace, db):
    row = db.execute("""SELECT t.id,t.business_id FROM chat_turns t
        JOIN chat_conversations c ON c.id=t.conversation_id
        LEFT JOIN web_jobs j ON j.id=t.job_id
        WHERE c.deleted_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM chat_turns earlier WHERE earlier.conversation_id=t.conversation_id AND earlier.ordinal<t.ordinal AND earlier.status<>'completed')
        AND (t.status IN ('queued','routing') OR (t.status='processing' AND j.status IN ('completed','waiting','failed','blocked')))
        ORDER BY t.created_at LIMIT 1""").fetchone()
    if not row:
        return False
    Conversations(workspace.scoped(row['business_id'])).run(row['id'])
    return True
