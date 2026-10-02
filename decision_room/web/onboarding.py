"""Versioned onboarding, sharing the existing conversational and report workers."""
from dataclasses import asdict
from uuid import uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from ..memory import service as memory
from .business import profile
from .dossier import available
from .errors import WebError, bounded, identifier

ENGLISH_GOALS = {
    'discover': 'Discover opportunities and problems', 'organize': 'Organize my figures',
    'evolution': 'Understand business trends', 'question': 'Answer a specific question',
    'help': 'Help me decide where to start',
}
GOALS = {
    'discover': 'Descubrir oportunidades y problemas',
    'organize': 'Tener mis cifras organizadas',
    'evolution': 'Entender cómo evoluciona el negocio',
    'question': 'Resolver una pregunta concreta',
    'help': 'Ayúdame a decidir por dónde empezar',
}


def current(db, business, *, lock=False):
    return db.execute('SELECT * FROM onboarding_sessions WHERE business_id=%s' +
                      (' FOR UPDATE' if lock else ''), (business,)).fetchone()


def chat_state(db, business, chat_id):
    row = current(db, business)
    if not row or str(row['conversation_id']) != str(chat_id) or row['stage'] == 'complete':
        return None
    return dict(revision=row['revision'], stage=row['stage'], goal=row['goal'],
                capabilities=dict(confirm_scope_button='Crear mi informe', predictions=False, delivery='reviewed_report'),
                analysis_id=str(row['analysis_id']) if row['analysis_id'] else None,
                optional_questions_asked=db.execute("""SELECT count(*) AS n FROM chat_turns
                    WHERE conversation_id=%s AND response->'onboarding'->'question'->>'optional'='true'""",
                    (chat_id,)).fetchone()['n'])


def _guard(ws, db, data):
    b = ws.business_id()
    selected = db.execute('SELECT active_business_id FROM web_workspace WHERE singleton FOR SHARE').fetchone()
    if not b or identifier(data.get('business_id')) != b or selected['active_business_id'] != b:
        raise WebError('El negocio activo ha cambiado. Recarga la página.', 409)
    return b


def _turn(ws, db, row, text, *, event, job=None):
    chat = row['conversation_id']
    db.execute('SELECT id FROM chat_conversations WHERE id=%s FOR UPDATE', (chat,))
    ordinal = db.execute('SELECT COALESCE(max(ordinal),0)+1 AS n FROM chat_turns WHERE conversation_id=%s', (chat,)).fetchone()['n']
    turn = uuid4()
    db.execute('''INSERT INTO chat_turns(id,business_id,conversation_id,ordinal,request_key,payload,status,model_settings,job_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
        (turn, row['business_id'], chat, ordinal, turn,
         Jsonb(dict(text=text, disposition='answered', question_id='', question='', phase=None,
                    onboarding_event=event, onboarding_revision=row['revision'])),
         'processing' if job else 'queued', Jsonb(asdict(ws.settings)), job))
    return turn


def start(ws, data):
    with connect(ws.config) as db, db.transaction():
        b = _guard(ws, db, data)
        db.execute('SELECT business_id FROM web_businesses WHERE business_id=%s FOR UPDATE', (b,))
        row = current(db, b)
        if row:
            return row
        if ws.settings is None:
            raise WebError('Configura el modelo para continuar. Tu presentación está guardada.', 409)
        legacy = db.execute('SELECT * FROM web_onboarding WHERE business_id=%s', (b,)).fetchone()
        if legacy and legacy['job_id']:
            raise WebError('Continúa el informe que ya habías empezado.', 409)
        p = profile(db, b)
        chat = uuid4()
        db.execute('''INSERT INTO chat_conversations(id,business_id,request_key,title)
            VALUES (%s,%s,%s,%s)''', (chat, b, chat, ('First analysis of ' if ws.settings.response_language == 'en' else 'Primer análisis de ') + p['name']))
        db.execute('INSERT INTO onboarding_sessions(business_id,conversation_id) VALUES (%s,%s)', (b, chat))
        row = current(db, b)
        turn = _turn(ws, db, row, p['description'], event='business')
        # Resolve the original profile before taking the first chat snapshot,
        # even when a caller drives chat turns without the background worker.
        source = db.execute('SELECT id FROM memory_sources WHERE business_id=%s AND origin_key=%s',
                            (b, f"profile:{p['profile_revision']}")).fetchone()
        if source:
            db.execute('UPDATE chat_turns SET memory_source_id=%s WHERE id=%s', (source['id'], turn))
    ws.wake.set()
    return row


def read(ws):
    with connect(ws.config) as db:
        row = current(db, ws.business_id())
        if row and row['job_id']:
            job = ws.detail(row['job_id'])
            row['publishable'] = job['publishable']
            row['job_status'] = job['status']
            row['context_stale'] = bool(job.get('context_stale'))
        return row


def change(ws, data):
    from ..conversations import dependencies_current
    with connect(ws.config) as db, db.transaction():
        b = _guard(ws, db, data)
        row = current(db, b, lock=True)
        if not row:
            raise WebError('Primero inicia la conversación.', 409)
        key = identifier(data.get('request_key'))
        old = db.execute('SELECT payload FROM onboarding_events WHERE business_id=%s AND request_key=%s', (b, key)).fetchone()
        if old:
            if old['payload'] != data:
                raise WebError('Este envío ya contiene otros datos.', 409)
            return row
        if type(data.get('revision')) is not int or data['revision'] != row['revision']:
            raise WebError('El recorrido ha cambiado. Recarga antes de continuar.', 409)
        action = data.get('action')
        db.execute('SELECT id FROM chat_conversations WHERE id=%s FOR UPDATE', (row['conversation_id'],))
        if action == 'complete':
            if not row['job_id'] or not ws.detail(row['job_id'])['publishable']:
                raise WebError('El informe todavía no está listo.', 409)
            db.execute("UPDATE onboarding_sessions SET stage='complete',revision=revision+1 WHERE business_id=%s", (b,))
            db.execute('UPDATE web_onboarding SET completed=true,completed_at=now() WHERE business_id=%s AND job_id=%s', (b, row['job_id']))
        else:
            if row['stage'] in ('report', 'complete'):
                raise WebError('Este encargo ya está en marcha. Continúa en la conversación.', 409)
            if db.execute("SELECT 1 FROM chat_turns WHERE conversation_id=%s AND status<>'completed'", (row['conversation_id'],)).fetchone():
                raise WebError('Espera a la respuesta o reintenta el mensaje pendiente.', 409)
            if ws.settings is None:
                raise WebError('Configura el modelo para continuar.', 409)
            if action == 'goal':
                text = bounded(data.get('text', ''), 'el objetivo', 2000, False)
                choices = data.get('choices', [])
                if not isinstance(choices, list) or any(not isinstance(c, str) or c not in GOALS for c in choices) or len(choices) > 5:
                    raise WebError('Elige objetivos válidos.')
                if not text and not choices:
                    raise WebError('Cuéntanos qué quieres conseguir o elige una idea.')
                goal = dict(text=text, choices=list(dict.fromkeys(choices)))
                db.execute('''UPDATE onboarding_sessions SET goal=%s,brief=NULL,proposal_turn_id=NULL,
                    stage=%s,revision=revision+1 WHERE business_id=%s''',
                    (Jsonb(goal), 'scope' if row['analysis_id'] else 'data', b))
                row = current(db, b)
                _turn(ws, db, row, '\n'.join([(ENGLISH_GOALS if ws.settings.response_language == 'en' else GOALS)[c] for c in goal['choices']] + ([text] if text else [])), event='goal')
            elif action == 'data':
                if not row['goal']:
                    raise WebError('Elige primero qué quieres conseguir.', 409)
                analysis = identifier(data.get('analysis_id'))
                if not available(db, b, analysis):
                    raise WebError('Los archivos todavía no están preparados.', 409)
                db.execute('''UPDATE onboarding_sessions SET analysis_id=%s,stage='scope',brief=NULL,
                    proposal_turn_id=NULL,revision=revision+1 WHERE business_id=%s''', (analysis, b))
                db.execute('UPDATE chat_conversations SET analysis_id=%s WHERE id=%s', (analysis, row['conversation_id']))
                row = current(db, b)
                _turn(ws, db, row, ('I have shared the files for my first analysis.' if ws.settings.response_language == 'en' else 'He compartido los archivos para preparar mi primer análisis.'), event='data')
            elif action == 'confirm':
                if not row['brief'] or not row['analysis_id'] or row['stage'] != 'scope':
                    raise WebError('Necesitamos preparar el alcance antes de confirmarlo.', 409)
                proposal = db.execute('SELECT * FROM chat_turns WHERE id=%s', (row['proposal_turn_id'],)).fetchone()
                from ..conversations import Conversations
                memory.lock(db, b)
                if not dependencies_current(ws.config, db, proposal['snapshot'], Conversations(ws).events(db, proposal)):
                    raise WebError('Los datos o el contexto han cambiado. Pide actualizar el alcance en el chat.', 409)
                # Scope changes go through a new reviewed proposal, never an unchecked form.
                confirmed = dict(goal=row['goal'], brief=row['brief'], analysis_id=str(row['analysis_id']),
                                 revision=row['revision'], proposal_turn_id=str(row['proposal_turn_id']))
                job = uuid4()
                p = profile(db, b)
                declarations = [dict(question=t['payload'].get('question', ''), text=t['payload']['text'],
                                     disposition=t['payload']['disposition']) for t in db.execute(
                    'SELECT payload FROM chat_turns WHERE conversation_id=%s ORDER BY ordinal',
                    (row['conversation_id'],)).fetchall() if not t['payload'].get('onboarding_event')]
                confirmed['owner_declarations'] = declarations
                confirmed['business_description'] = p['description']
                goal_text = '\n'.join([row['brief']['objective'], *row['brief']['questions'],
                                      'Límites conocidos:', *row['brief']['limitations']])
                goal_text += '\nContexto original declarado por el propietario:\n' + p['description']
                if declarations:
                    goal_text += '\nAclaraciones del propietario (desconocidas/omitidas NO confirman hechos):\n' + memory.encoded(declarations)
                if len(goal_text) > 12000:
                    raise WebError('El alcance y las aclaraciones superan el tamaño de este informe. Reduce el alcance antes de confirmar.', 409)
                db.execute('''INSERT INTO web_jobs(id,request_key,request_sha256,business_id,analysis_id,
                    title,context,goal,filename,upload_key,byte_count,model_settings,status,phase,business_name,origin)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'','',0,%s,'queued','planning',%s,'chat')''',
                    (job, key, memory.digest(confirmed), b, row['analysis_id'], ('First report for ' if ws.settings.response_language == 'en' else 'Primer informe de ') + p['name'],
                     memory.encoded(dict(context=dict(onboarding_brief=confirmed), dependencies=[dict(kind='chat', id=str(proposal['id']), snapshot=proposal['snapshot'])])), goal_text,
                     Jsonb(asdict(ws.settings)), p['name']))
                _turn(ws, db, row, ('Create my first report: ' if ws.settings.response_language == 'en' else 'Crear mi primer informe: ') + row['brief']['objective'], event='confirm', job=job)
                db.execute("UPDATE onboarding_sessions SET stage='report',job_id=%s,confirmed=%s,revision=revision+1 WHERE business_id=%s",
                           (job, Jsonb(confirmed), b))
                db.execute("UPDATE web_businesses SET onboarding_status='analysis_started',updated_at=now() WHERE business_id=%s", (b,))
                db.execute('UPDATE web_onboarding SET job_id=%s WHERE business_id=%s AND NOT completed', (job, b))
            else:
                raise WebError('Acción de onboarding no válida.')
        db.execute('INSERT INTO onboarding_events(business_id,request_key,payload) VALUES (%s,%s,%s)', (b, key, Jsonb(data)))
        result = current(db, b)
    ws.wake.set()
    return result


def before_message(db, business, chat, previous):
    """Serialize setup edits against proposal publication and capture the exact question."""
    row = current(db, business, lock=True)
    if not row or row['conversation_id'] != chat['id'] or row['stage'] in ('report', 'complete'):
        return None
    if previous and previous['status'] != 'completed':
        raise WebError('Espera a la respuesta o reintenta el mensaje pendiente.', 409)
    db.execute('UPDATE onboarding_sessions SET brief=NULL,proposal_turn_id=NULL,revision=revision+1 WHERE business_id=%s', (business,))
    question = (((previous or {}).get('response') or {}).get('onboarding') or {}).get('question')
    return dict(revision=row['revision'] + 1, question=question, question_turn_id=str(previous['id']) if question else None)


def publish(db, business, turn, response, context):
    guide = response.get('onboarding')
    if not guide:
        return
    row = current(db, business, lock=True)
    if not row or row['revision'] != context['onboarding']['revision']:
        raise ValueError('Onboarding changed before publication.')
    if guide.get('brief'):
        db.execute('UPDATE onboarding_sessions SET brief=%s,proposal_turn_id=%s WHERE business_id=%s',
                   (Jsonb(guide['brief']), turn['id'], business))
