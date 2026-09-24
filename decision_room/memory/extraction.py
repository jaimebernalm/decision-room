"""Durable extraction queue with explicit recovery of uncertain model calls."""
from uuid import uuid4

from pydantic import ValidationError
from psycopg.types.json import Jsonb

from ..database import connect
from ..agent.model import ModelRequestUncertain
from ..greetings import is_greeting
from .contracts import Extraction, PROMPT_VERSION
from .service import (MemoryError, append, current, digest, lock, overlap, same_subject,
                      validate_content)


def _context(db, source):
    facts = current(db, source['business_id'])
    # Do not silently omit conflicting/withdrawn facts to fit the context.
    if len(facts) > 200:
        raise MemoryError('La memoria supera el límite de extracción de esta versión (200 temas).')
    return {'source': source['payload'], 'memories': [dict(id=str(f['fact_id']), revision=f['revision'],
            status=f['status'], content=f['content']) for f in facts]}


def _unanswered(source):
    p = source['payload']
    return {'candidates': [{'content': dict(topic='unanswered_' + digest(p['question'])[:24],
            kind='open_question', statement=('Respuesta desconocida: ' if p['disposition'] == 'unknown' else
            'El cliente ha declinado responder: ') + p['question'][:1400],
            scope=p['default_scope'], scope_id=p['scope_id'], temporal_scope='unspecified', valid_from=None, valid_until=None, result_id=None),
            'evidence': 'uncertain', 'quote': p['text'], 'conflicts_with': []}]}


def _validate(db, source, response):
    candidates = Extraction.model_validate(response).candidates
    p, b = source['payload'], source['business_id']
    facts = {str(f['fact_id']): f for f in current(db, b)}
    for item in candidates:
        c = validate_content(db, b, item.content.model_dump(mode='json'))
        if item.quote not in p['text'] or (not item.quote.strip() and p['disposition'] == 'answered'):
            raise MemoryError('La extracción no cita el texto original.')
        if c['kind'] == 'result_reference':
            raise MemoryError('La extracción de declaraciones no crea resultados calculados.')
        if c['scope'] != p['default_scope'] or c['scope_id'] != p['scope_id']:
            if not (p['allow_business'] and c['scope'] == 'business'):
                raise MemoryError('La extracción amplía el ámbito autorizado.')
        if c['kind'] == 'definition' and c['scope'] == 'business':
            raise MemoryError('Una definición de datos requiere una fuente o análisis identificado.')
        if p['disposition'] != 'answered' and (c['kind'] != 'open_question' or item.evidence == 'explicit'):
            raise MemoryError('Una respuesta desconocida o declinada no confirma definiciones.')
        for ref in item.conflicts_with:
            if ref not in facts:
                raise MemoryError('Referencia de contradicción ajena o inexistente.')
            other = facts[ref]['content']
            if (other['scope'], other['scope_id']) != (c['scope'], c['scope_id']) or not overlap(other, c):
                raise MemoryError('Una contradicción requiere el mismo ámbito y periodos compatibles.')
    return candidates


def _chat_without_facts(source):
    # A greeting or pure question is not a new declaration or contradiction.
    # Explicit unknown/declined analytical answers use their own capture path.
    import re
    text = source['payload']['text'].strip()
    return source['origin_key'].startswith('chat_message:') and (
        is_greeting(text) or text.startswith('¿') and not re.sub(r'¿[^?]*\?', '', text).strip()
    )


def _validation_hint(error):
    if isinstance(error, ValidationError):
        return '; '.join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                         for item in error.errors(include_input=False))[:1000]
    return str(error)[:1000]


def _apply(db, source):
    b, p = source['business_id'], source['payload']
    revision = lock(db, b)
    if p['kind'] == 'profile':
        profile = db.execute('SELECT profile_revision FROM web_businesses WHERE business_id=%s FOR SHARE', (b,)).fetchone()
        if profile and profile['profile_revision'] != p['profile_revision']:
            db.execute("UPDATE memory_sources SET status='superseded',updated_at=now() WHERE id=%s", (source['id'],))
            return
    if revision != source['context_revision']:
        # The saved output is retained in memory_calls, but must be extracted
        # again with the corrected/withdrawn context on explicit retry.
        raise MemoryError('La memoria cambió durante la extracción. Reintenta con la revisión actual.')
    candidates = [] if _chat_without_facts(source) else _validate(db, source, source['response'])
    for item in candidates:
        content = item.content.model_dump(mode='json')
        facts = current(db, b)
        matches = [f for f in facts if same_subject(f['content'], content) or str(f['fact_id']) in item.conflicts_with]
        # A withdrawn topic cannot be reactivated by a rephrased source/summary.
        # Also retain tombstones from older revisions, even after explicit correction.
        withdrawn = db.execute("SELECT content FROM memory_revisions WHERE business_id=%s AND status='withdrawn'", (b,)).fetchall()
        if any(same_subject(f['content'], content) for f in withdrawn):
            continue
        state = 'declared' if (item.evidence == 'explicit' and content['kind'] != 'open_question'
                               and content['temporal_scope'] != 'unresolved') else 'proposed'
        if item.evidence == 'hypothetical':
            matches = [f for f in matches if f['status'] == 'proposed']
        if matches:
            # Do not auto-confirm a prior proposal because the same wording reappears.
            if all(f['content'] == content and f['status'] != 'conflicted' for f in matches):
                continue
            for prior in matches:
                if prior['status'] in ('withdrawn', 'superseded'):
                    continue
                alternatives = prior['alternatives'] or [dict(content=prior['content'], source_id=str(prior['source_id']), quote=prior['quote'])]
                candidate = dict(content=content, source_id=str(source['id']), quote=item.quote)
                if candidate not in alternatives:
                    alternatives = alternatives + [candidate]
                # Keep the previous content visible alongside the proposed replacement.
                append(db, b, prior['fact_id'], prior['content'], 'conflicted', source['id'], item.quote, alternatives)
        else:
            fact_id = uuid4()
            db.execute('INSERT INTO memory_facts(id,business_id) VALUES (%s,%s)', (fact_id, b))
            append(db, b, fact_id, content, state, source['id'], item.quote)
    db.execute("UPDATE memory_sources SET status='applied',issue=NULL,updated_at=now() WHERE id=%s", (source['id'],))


def process(config, business_id, source_id, model):
    """Process one original; return False if another process owns it."""
    with connect(config) as db:
        key = f'memory:{business_id}:{source_id}'
        if not db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,9)) AS locked', (key,)).fetchone()['locked']:
            return False
        source = db.execute('SELECT * FROM memory_sources WHERE id=%s AND business_id=%s', (source_id, business_id)).fetchone()
        if not source:
            raise MemoryError('El origen no pertenece a este negocio.', 404)
        if source['status'] not in ('pending', 'extracting', 'extracted'):
            return False
        if source['status'] == 'extracting':
            with db.transaction():
                db.execute("UPDATE memory_sources SET status='uncertain',issue='Extracción interrumpida; requiere reintento explícito.',updated_at=now() WHERE id=%s", (source_id,))
                db.execute("UPDATE memory_calls SET status='uncertain',finished_at=now() WHERE source_id=%s AND status='running'", (source_id,))
            return True
        call_id = None
        try:
            if source['status'] == 'pending':
                with db.transaction():
                    rev = lock(db, business_id)
                    context = _context(db, source)
                    db.execute("UPDATE memory_sources SET status='extracting',context_revision=%s,response=NULL,issue=NULL,updated_at=now() WHERE id=%s", (rev, source_id))
                    if source['payload']['disposition'] == 'answered' and not _chat_without_facts(source):
                        call_id = uuid4()
                        db.execute('''INSERT INTO memory_calls(id,business_id,source_id,model_settings,prompt_version,context,status)
                            VALUES (%s,%s,%s,%s,%s,%s,'running')''',
                                   (call_id, business_id, source_id, Jsonb(model.identity), PROMPT_VERSION, Jsonb(context)))
                if call_id:
                    response, usage = model.generate_memory(context)
                elif source['payload']['disposition'] == 'answered':
                    response, usage = {'candidates': []}, {}
                else:
                    response, usage = _unanswered(source), {}
                # Commit response independently: a later application failure never
                # loses the original/model output or announces a successful save.
                with db.transaction():
                    if call_id:
                        db.execute("UPDATE memory_calls SET status='completed',response=%s,usage=%s,finished_at=now() WHERE id=%s",
                                   (Jsonb(response), Jsonb(usage), call_id))
                    db.execute("UPDATE memory_sources SET status='extracted',response=%s,updated_at=now() WHERE id=%s", (Jsonb(response), source_id))
            source = db.execute('SELECT * FROM memory_sources WHERE id=%s', (source_id,)).fetchone()
            if call_id and not _chat_without_facts(source):
                try:
                    _validate(db, source, source['response'])
                except (ValidationError, MemoryError) as error:
                    # A schema-constrained model can still return an invalid
                    # scope or citation. Keep the first response for audit and
                    # make one bounded correction call before surfacing a failure.
                    correction = _validation_hint(error)
                    corrected_context = {**context, 'previous_response': source['response']}
                    call_id = uuid4()
                    with db.transaction():
                        db.execute("UPDATE memory_sources SET status='extracting',updated_at=now() WHERE id=%s", (source_id,))
                        db.execute('''INSERT INTO memory_calls(id,business_id,source_id,model_settings,prompt_version,context,status)
                            VALUES (%s,%s,%s,%s,%s,%s,'running')''',
                                   (call_id, business_id, source_id, Jsonb(model.identity), PROMPT_VERSION,
                                    Jsonb({**corrected_context, 'validation_issue': correction})))
                    response, usage = model.generate_memory(corrected_context, correction=correction)
                    with db.transaction():
                        db.execute("UPDATE memory_calls SET status='completed',response=%s,usage=%s,finished_at=now() WHERE id=%s",
                                   (Jsonb(response), Jsonb(usage), call_id))
                        db.execute("UPDATE memory_sources SET status='extracted',response=%s,updated_at=now() WHERE id=%s",
                                   (Jsonb(response), source_id))
                    source = db.execute('SELECT * FROM memory_sources WHERE id=%s', (source_id,)).fetchone()
            with db.transaction():
                _apply(db, source)
        except Exception as error:
            state = 'uncertain' if isinstance(error, ModelRequestUncertain) else 'failed'
            # Provider details and original text remain private; only a bounded
            # service diagnostic/class name is exposed in status metadata.
            issue = str(error)[:1000] if isinstance(error, MemoryError) else type(error).__name__
            with db.transaction():
                db.execute('UPDATE memory_sources SET status=%s,issue=%s,updated_at=now() WHERE id=%s', (state, issue, source_id))
                if call_id:
                    db.execute("UPDATE memory_calls SET status=%s,issue=%s,finished_at=now() WHERE id=%s AND status='running'", (state, issue, call_id))
        return True


def retry(config, business_id, source_id=None):
    """Explicitly authorize another attempt, including an uncertain provider call."""
    with connect(config) as db, db.transaction():
        lock(db, business_id)
        if source_id is not None and not db.execute('SELECT 1 FROM memory_sources WHERE business_id=%s AND id=%s', (business_id, source_id)).fetchone():
            raise MemoryError('El origen no pertenece a este negocio.', 404)
        # A completed, valid response can be reapplied after a transient SQL error.
        # Stale/invalid responses must be regenerated; calls retain their history.
        rows = db.execute("SELECT * FROM memory_sources WHERE business_id=%s AND status IN ('failed','uncertain') FOR UPDATE", (business_id,)).fetchall()
        for source in rows:
            if source_id is not None and str(source['id']) != str(source_id):
                continue
            valid = False
            if source['response'] is not None:
                try:
                    _validate(db, source, source['response'])
                    head = db.execute('SELECT revision FROM memory_heads WHERE business_id=%s', (business_id,)).fetchone()['revision']
                    valid = head == source['context_revision']
                except ValueError:
                    pass
            db.execute('UPDATE memory_sources SET status=%s,issue=NULL,updated_at=now() WHERE id=%s',
                       ('extracted' if valid else 'pending', source['id']))


def work_once(config, model_factory, settings):
    # The web worker only extracts sources enrolled in its local owner workspace.
    # CLI/evaluation sources remain available for explicit service processing.
    from ..agent.model import ModelSettings
    with connect(config) as db:
        sources = db.execute("""SELECT s.id,s.business_id,s.payload FROM memory_sources s
            JOIN web_businesses b ON b.business_id=s.business_id
            WHERE s.status IN ('pending','extracting','extracted') ORDER BY s.created_at LIMIT 20""").fetchall()
    for source in sources:
        identity = source['payload'].get('model_settings')
        model = model_factory(ModelSettings(**identity) if identity else settings)
        if process(config, source['business_id'], source['id'], model):
            return True
    return False
