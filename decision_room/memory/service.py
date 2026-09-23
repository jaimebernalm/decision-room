"""Transactional knowledge maintenance. Model proposals never execute SQL."""
import hashlib
import json
from datetime import date
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from ..database import connect
from .contracts import Content


class MemoryError(ValueError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def require_business(db, business_id):
    if not db.execute('SELECT 1 FROM businesses WHERE id=%s', (business_id,)).fetchone():
        raise MemoryError('El negocio no existe.', 404)


def lock(db, business_id):
    require_business(db, business_id)
    db.execute('INSERT INTO memory_heads(business_id) VALUES (%s) ON CONFLICT DO NOTHING', (business_id,))
    return db.execute('SELECT revision FROM memory_heads WHERE business_id=%s FOR UPDATE', (business_id,)).fetchone()['revision']


def validate_scope(db, business_id, scope, scope_id):
    if scope == 'business' and scope_id is None:
        return
    if scope not in ('analysis', 'source') or scope_id is None:
        raise MemoryError('Ámbito de memoria no válido.', 400)
    try:
        scope_id = UUID(str(scope_id))
    except (ValueError, TypeError):
        raise MemoryError('Identificador de ámbito no válido.', 400) from None
    table = 'analyses' if scope == 'analysis' else 'sources'
    if not db.execute(f'SELECT 1 FROM {table} WHERE id=%s AND business_id=%s', (scope_id, business_id)).fetchone():
        raise MemoryError('La fuente no pertenece a este negocio.', 404)


def capture(db, business_id, origin_key, *, text, kind, question='', disposition='answered',
            default_scope='business', scope_id=None, allow_business=False, profile_revision=None, model_settings=None):
    """Use the caller's transaction: original answer/profile and queue commit together."""
    require_business(db, business_id)
    if kind not in ('profile', 'planning_answer', 'review_answer', 'manual'):
        raise MemoryError('Origen no válido.', 400)
    if not isinstance(text, str) or len(text) > 6000 or not isinstance(question, str) or len(question) > 6000:
        raise MemoryError('Texto original fuera de límites.', 400)
    if disposition not in ('answered', 'unknown', 'declined'):
        raise MemoryError('Respuesta no válida.', 400)
    if not isinstance(origin_key, str) or not 1 <= len(origin_key) <= 240:
        raise MemoryError('Clave de origen no válida.', 400)
    validate_scope(db, business_id, default_scope, scope_id)
    payload = dict(kind=kind, text=text, question=question, disposition=disposition,
                   default_scope=default_scope, scope_id=str(scope_id) if scope_id else None,
                   allow_business=bool(allow_business), profile_revision=profile_revision)
    if model_settings is not None:
        payload['model_settings'] = model_settings
    db.execute('''INSERT INTO memory_sources(id,business_id,origin_key,payload)
        VALUES (%s,%s,%s,%s) ON CONFLICT (business_id,origin_key) DO NOTHING''',
               (uuid4(), business_id, origin_key, Jsonb(payload)))
    source = db.execute('SELECT * FROM memory_sources WHERE business_id=%s AND origin_key=%s',
                        (business_id, origin_key)).fetchone()
    if source['payload'] != payload:
        raise MemoryError('Este origen ya se guardó con otro contenido.')
    return source


def current(db, business_id):
    return db.execute('''SELECT DISTINCT ON (fact_id) * FROM memory_revisions
        WHERE business_id=%s ORDER BY fact_id,revision DESC''', (business_id,)).fetchall()


def append(db, business_id, fact_id, content, status, source_id, quote, alternatives=None):
    revision = db.execute('''UPDATE memory_heads SET revision=revision+1 WHERE business_id=%s
        RETURNING revision''', (business_id,)).fetchone()['revision']
    latest = db.execute('SELECT coalesce(max(revision),0)+1 AS n FROM memory_revisions WHERE fact_id=%s', (fact_id,)).fetchone()['n']
    db.execute('''INSERT INTO memory_revisions(business_id,fact_id,revision,business_revision,content,status,source_id,quote,alternatives)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
               (business_id, fact_id, latest, revision, Jsonb(content), status, source_id, quote, Jsonb(alternatives or [])))
    return {'fact_id': str(fact_id), 'revision': latest, 'business_revision': revision, 'status': status}


def overlap(a, b):
    return not ((a['valid_until'] and b['valid_from'] and a['valid_until'] < b['valid_from']) or
                (b['valid_until'] and a['valid_from'] and b['valid_until'] < a['valid_from']))


def same_subject(a, b):
    return (a['topic'], a['scope'], a['scope_id']) == (b['topic'], b['scope'], b['scope_id']) and overlap(a, b)


def validate_content(db, business_id, data):
    content = Content.model_validate(data).model_dump(mode='json')
    validate_scope(db, business_id, content['scope'], content['scope_id'])
    if content['result_id']:
        try:
            result_id = UUID(content['result_id'])
        except ValueError:
            raise MemoryError('Referencia de resultado no válida.', 400) from None
        if not db.execute('SELECT 1 FROM agent_reviews WHERE business_id=%s AND id=%s', (business_id, result_id)).fetchone():
            raise MemoryError('El resultado no pertenece a este negocio.', 404)
    return content


def change(config, business_id, *, action, request_key, content=None, fact_id=None, expected_revision=None,
           original_text='', reason=''):
    """Explicit owner operations, shared by future onboarding/chat/profile adapters."""
    if action not in ('propose', 'declare', 'confirm', 'correct', 'withdraw'):
        raise MemoryError('Operación de memoria no válida.', 400)
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 180:
        raise MemoryError('Clave de petición no válida.', 400)
    if not isinstance(reason, str) or len(reason) > 2000:
        raise MemoryError('Motivo fuera de límites.', 400)
    signature = digest(dict(action=action, content=content, fact_id=fact_id, expected_revision=expected_revision,
                            original_text=original_text, reason=reason))
    with connect(config) as db, db.transaction():
        lock(db, business_id)
        old_command = db.execute('SELECT * FROM memory_commands WHERE business_id=%s AND request_key=%s', (business_id, request_key)).fetchone()
        if old_command:
            if old_command['signature'] != signature:
                raise MemoryError('Esta petición ya se ejecutó con otro contenido.')
            return old_command['result']
        facts = current(db, business_id)
        prior = next((f for f in facts if str(f['fact_id']) == str(fact_id)), None)
        if action in ('propose', 'declare'):
            if fact_id is not None or expected_revision is not None:
                raise MemoryError('Un recuerdo nuevo no sustituye otro implícitamente.', 400)
            value = validate_content(db, business_id, content)
            # An explicit correction must name its target and expected revision.
            if any(same_subject(f['content'], value) and f['status'] != 'superseded' for f in facts):
                raise MemoryError('Este tema ya existe: corrige el recuerdo indicando su revisión.')
            fact_id = uuid4()
            db.execute('INSERT INTO memory_facts(id,business_id) VALUES (%s,%s)', (fact_id, business_id))
            status = 'proposed' if action == 'propose' or value['temporal_scope'] == 'unresolved' else 'declared'
        else:
            if not prior:
                raise MemoryError('El recuerdo no pertenece a este negocio.', 404)
            if type(expected_revision) is not int or prior['revision'] != expected_revision:
                raise MemoryError('El recuerdo ha cambiado. Consulta su última revisión.')
            if prior['status'] in ('withdrawn', 'superseded') and action != 'correct':
                raise MemoryError('El recuerdo está retirado; restaurarlo requiere una corrección explícita.')
            if action == 'correct':
                value = validate_content(db, business_id, content)
                if any(f['fact_id'] != prior['fact_id'] and same_subject(f['content'], value) and f['status'] != 'superseded' for f in facts):
                    raise MemoryError('La corrección coincide con otro recuerdo. Resuelve primero ese tema.')
            else:
                if content is not None:
                    raise MemoryError('Para cambiar contenido utiliza una corrección explícita.', 400)
                value = prior['content']
            if action == 'confirm' and prior['status'] == 'conflicted':
                raise MemoryError('Hay una contradicción: indica el contenido correcto mediante una corrección.')
            if action == 'confirm' and value['temporal_scope'] == 'unresolved':
                raise MemoryError('Aclara la fecha mediante una corrección antes de confirmar.')
            status = 'withdrawn' if action == 'withdraw' else ('proposed' if value['temporal_scope'] == 'unresolved' else 'declared')
        text = original_text or reason or value['statement']
        source = capture(db, business_id, 'manual:' + request_key, text=text, kind='manual',
                         default_scope=value['scope'], scope_id=value['scope_id'])
        db.execute("UPDATE memory_sources SET status='applied' WHERE id=%s", (source['id'],))
        result = append(db, business_id, fact_id, value, status, source['id'], text)
        db.execute('INSERT INTO memory_commands(business_id,request_key,signature,result) VALUES (%s,%s,%s,%s)',
                   (business_id, request_key, signature, Jsonb(result)))
        return result


def read(config, business_id, *, history=False, fact_id=None, applicable_on=None, analysis_id=None, source_id=None):
    """Without applicable_on return maintenance state; with it select declared scoped facts."""
    if history and applicable_on is not None:
        raise MemoryError("El historial no representa memoria vigente.", 400)
    with connect(config) as db, db.transaction():
        lock(db, business_id)
        if analysis_id is not None:
            validate_scope(db, business_id, 'analysis', analysis_id)
        if source_id is not None:
            validate_scope(db, business_id, 'source', source_id)
        if history:
            rows = db.execute('SELECT * FROM memory_revisions WHERE business_id=%s ORDER BY business_revision', (business_id,)).fetchall()
            latest = {r['fact_id']: r['revision'] for r in current(db, business_id)}
            rows = [{**r, 'effective_status': r['status'] if r['revision'] == latest[r['fact_id']] else 'superseded'} for r in rows]
        else:
            rows = current(db, business_id)
        if fact_id is not None:
            rows = [r for r in rows if str(r['fact_id']) == str(fact_id)]
            if not rows:
                raise MemoryError('El recuerdo no pertenece a este negocio.', 404)
        if applicable_on is not None:
            day = date.fromisoformat(str(applicable_on)).isoformat()
            rows = [r for r in rows if r['status'] == 'declared' and r['content']['temporal_scope'] != 'unresolved' and
                    (not r['content']['valid_from'] or r['content']['valid_from'] <= day) and
                    (not r['content']['valid_until'] or r['content']['valid_until'] >= day) and
                    (r['content']['scope'] == 'business' or
                     r['content']['scope'] == 'analysis' and r['content']['scope_id'] == str(analysis_id) or
                     r['content']['scope'] == 'source' and r['content']['scope_id'] == str(source_id))]
        return rows


def status(config, business_id):
    if business_id is None:
        return {'pending': 0, 'failed': 0, 'uncertain': 0, 'applied': 0, 'needs_review': 0}
    with connect(config) as db:
        rows = db.execute('SELECT status,count(*) AS n FROM memory_sources WHERE business_id=%s GROUP BY status', (business_id,)).fetchall()
        counts = {r['status']: r['n'] for r in rows}
        return {'pending': sum(counts.get(s, 0) for s in ('pending', 'extracting', 'extracted')),
                'failed': counts.get('failed', 0), 'uncertain': counts.get('uncertain', 0),
                'applied': counts.get('applied', 0),
                'needs_review': sum(f['status'] in ('proposed', 'conflicted') for f in current(db, business_id))}


def capture_answer(db, session, answer_id, *, kind, text, question, disposition):
    """New answers only; a single-file clarification stays attached to that file."""
    sources = db.execute('SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s',
                         (session['business_id'], session['analysis_id'])).fetchall()
    scope, target = ('source', sources[0]['id']) if len(sources) == 1 else ('analysis', session['analysis_id'])
    return capture(db, session['business_id'], f'{kind}:{answer_id}', text=text, kind=kind,
                   question=question, disposition=disposition, default_scope=scope, scope_id=target,
                   model_settings=session['model_settings'])
