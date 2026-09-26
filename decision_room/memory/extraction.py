"""Durable extraction queue with explicit recovery of uncertain model calls."""
from difflib import SequenceMatcher
import re
import unicodedata
from uuid import uuid4

from pydantic import ValidationError
from psycopg.types.json import Jsonb

from ..database import connect
from ..agent.model import ModelRequestUncertain
from ..greetings import is_greeting
from .contracts import Extraction, PROMPT_VERSION
from .service import (MemoryError, append, capture, current, digest, lock, overlap, same_subject,
                      validate_content)


def _explicit_correction_request(text):
    normalized = unicodedata.normalize('NFKD', text.lower())
    normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    requests = {'cambia', 'cambiar', 'cambie', 'cambies', 'corrige', 'corregir',
                'corrija', 'corrijas', 'actualiza', 'actualizar', 'actualice',
                'sustituye', 'sustituir', 'reemplaza', 'reemplazar', 'rectifica',
                'rectificar', 'change', 'correct', 'update', 'replace'}
    return bool(set(re.findall(r'[a-z]+', normalized)) & requests)


def _context(db, source):
    facts = current(db, source['business_id'])
    # Do not silently omit conflicting/withdrawn facts to fit the context.
    if len(facts) > 200:
        raise MemoryError('La memoria supera el límite de extracción de esta versión (200 temas).')
    profile = db.execute('''SELECT b.description,w.profile_revision FROM businesses b
        JOIN web_businesses w ON w.business_id=b.id WHERE b.id=%s''',
                         (source['business_id'],)).fetchone()
    return {'source': source['payload'], 'memories': [dict(id=str(f['fact_id']), revision=f['revision'],
            status=f['status'], content=f['content']) for f in facts],
            'profile': dict(profile) if profile else None}


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
    corrected = set()
    profile_replacements = set()
    profile = db.execute('''SELECT b.description FROM businesses b JOIN web_businesses w
        ON w.business_id=b.id WHERE b.id=%s''', (b,)).fetchone()
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
        if item.correction_of is not None:
            prior = facts.get(item.correction_of)
            matches = [f for f in facts.values() if f['status'] not in ('withdrawn', 'superseded')
                       and (same_subject(f['content'], c) or str(f['fact_id']) in item.conflicts_with)]
            if (not source['origin_key'].startswith('chat_message:') or not _explicit_correction_request(p['text']) or
                item.evidence != 'explicit' or c['temporal_scope'] == 'unresolved' or
                not prior or prior['status'] not in ('declared', 'conflicted') or
                item.correction_of in corrected or
                item.correction_of not in item.conflicts_with or len(matches) != 1 or
                str(matches[0]['fact_id']) != item.correction_of or
                (prior['content']['topic'], prior['content']['kind'], prior['content']['scope'], prior['content']['scope_id']) !=
                (c['topic'], c['kind'], c['scope'], c['scope_id']) or
                not overlap(prior['content'], c) or
                any(ref != item.correction_of for ref in item.conflicts_with)):
                raise MemoryError('La corrección no identifica de forma inequívoca un dato vigente.')
            corrected.add(item.correction_of)
        if item.profile_replacement is not None:
            old = item.profile_replacement.old_text
            new = item.profile_replacement.new_text
            related = [f for f in facts.values() if f['status'] not in ('withdrawn', 'superseded')
                       and (same_subject(f['content'], c) or str(f['fact_id']) in item.conflicts_with)]
            if (not source['origin_key'].startswith('chat_message:') or
                not _explicit_correction_request(p['text']) or item.evidence != 'explicit' or
                not profile or profile['description'].count(old) != 1 or old in profile_replacements or
                old == new or new.casefold() not in p['text'].casefold() or
                new.casefold() not in c['statement'].casefold() or
                c['temporal_scope'] == 'unresolved' or
                (item.correction_of is None and any(f['content'] != c for f in related))):
                raise MemoryError('La sustitución del perfil no está respaldada por una corrección inequívoca.')
            profile_replacements.add(old)
    return candidates


def _chat_without_facts(source):
    # A greeting or pure question is not a new declaration or contradiction.
    # Explicit unknown/declined analytical answers use their own capture path.
    text = source['payload']['text'].strip()
    return source['origin_key'].startswith('chat_message:') and (
        is_greeting(text) or (text.startswith('¿') and not _explicit_correction_request(text)
                              and not re.sub(r'¿[^?]*\?', '', text).strip())
    )


def _validation_hint(error):
    if isinstance(error, ValidationError):
        return '; '.join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}"
                         for item in error.errors(include_input=False))[:1000]
    return str(error)[:1000]


def _replace_profile_text(db, business_id, old_text, new_text):
    """Save one exact profile substitution and its source in the same transaction."""
    profile = db.execute('''SELECT b.description,w.profile_revision FROM businesses b
        JOIN web_businesses w ON w.business_id=b.id WHERE b.id=%s FOR UPDATE OF b,w''',
                         (business_id,)).fetchone()
    if not profile or profile['description'].count(old_text) != 1:
        raise MemoryError('El texto que se quería corregir ya no aparece una sola vez en el perfil.')
    description = profile['description'].replace(old_text, new_text, 1)
    if len(description) > 6000:
        raise MemoryError('La descripción corregida supera el límite permitido.')
    revision = profile['profile_revision'] + 1
    db.execute('UPDATE businesses SET description=%s WHERE id=%s', (description, business_id))
    db.execute('UPDATE web_businesses SET profile_revision=%s,updated_at=now() WHERE business_id=%s',
               (revision, business_id))
    mirrored = capture(
        db, business_id, f'profile:{revision}', kind='profile', text=description,
        allow_business=True, profile_revision=revision)
    db.execute("UPDATE memory_sources SET status='applied',updated_at=now() WHERE id=%s", (mirrored['id'],))


def _sync_profile_wording(db, business_id, prior, replacement):
    """Mirror a single, exact wording change when the corrected fact came from the profile."""
    source_ids = [prior['source_id']] + [a.get('source_id') for a in prior['alternatives']]
    origins = db.execute('SELECT origin_key FROM memory_sources WHERE business_id=%s AND id=ANY(%s::uuid[])',
                         (business_id, [str(value) for value in source_ids if value])).fetchall()
    if not any(row['origin_key'].startswith('profile:') for row in origins):
        return
    before = prior['content']['statement'].split()
    after = replacement['statement'].split()
    changed = [op for op in SequenceMatcher(None, before, after).get_opcodes() if op[0] != 'equal']
    if len(changed) != 1 or changed[0][0] != 'replace':
        return
    _, first, last, new_first, new_last = changed[0]
    old_text = ' '.join(before[first:last]).strip('.,;:!?')
    new_text = ' '.join(after[new_first:new_last]).strip('.,;:!?')
    if not old_text or not new_text or old_text == new_text:
        return
    profile = db.execute('SELECT description FROM businesses WHERE id=%s', (business_id,)).fetchone()
    if not profile or profile['description'].count(old_text) != 1:
        return
    _replace_profile_text(db, business_id, old_text, new_text)


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
    profile_changes = [(item.profile_replacement.old_text, item.profile_replacement.new_text)
                       for item in candidates if item.profile_replacement is not None]
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
            if (item.correction_of and len(matches) == 1 and
                str(matches[0]['fact_id']) == item.correction_of):
                prior = matches[0]
                append(db, b, prior['fact_id'], content, 'declared', source['id'], item.quote)
                if item.profile_replacement is None:
                    _sync_profile_wording(db, b, prior, content)
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
    for old_text, new_text in profile_changes:
        _replace_profile_text(db, b, old_text, new_text)
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
