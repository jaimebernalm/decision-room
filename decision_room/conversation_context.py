"""Versioned chat attachments and bounded, read-only access to their original text.

A selection freezes an ordinal cutoff, not a recursive copy of attached sources.
Earlier assistant prose is historical dialogue, never verified business evidence.
"""
import re
import json

from .web.errors import WebError

CHUNK_CHARS = 1200
USE = 'Historical dialogue only. Owner messages can be questions or hypotheses; assistant replies may be wrong. Verify business claims against current original sources.'


def head(db, business, chat_id, cutoff=None):
    return db.execute('''SELECT c.id,c.title,COUNT(t.id) AS turns,
        COALESCE(MAX(t.ordinal),0) AS cutoff,
        md5(COALESCE(string_agg(md5(t.payload::text || COALESCE(t.response::text,'')), '' ORDER BY t.ordinal),'')) AS version
        FROM chat_conversations c LEFT JOIN chat_turns t ON t.conversation_id=c.id
          AND t.business_id=c.business_id AND (%s::int IS NULL OR t.ordinal<=%s)
        WHERE c.id=%s AND c.business_id=%s AND c.deleted_at IS NULL
        GROUP BY c.id''', (cutoff, cutoff, chat_id, business)).fetchone()


def reference(row):
    return dict(source_id=str(row['id']), source_version=f"{row['cutoff']}:{row['version']}",
                kind='conversation', element_key='conversation')


def validate(db, business, ref):
    match = re.fullmatch(r'([1-9][0-9]{0,8}):([a-f0-9]{32})', ref['source_version'])
    if ref['element_key'] != 'conversation' or not match:
        raise WebError('La referencia de conversación no es válida.', 409)
    row = head(db, business, ref['source_id'], int(match[1]))
    if not row or reference(row) != ref:
        raise WebError('La conversación seleccionada ha cambiado o se ha eliminado. Vuelve a seleccionarla.', 409)
    return row


def attachment(db, business, ref):
    row = validate(db, business, ref)
    excerpts = db.execute('''SELECT ordinal,left(payload->>'text',240) AS text FROM chat_turns
        WHERE business_id=%s AND conversation_id=%s AND ordinal IN (1,%s) ORDER BY ordinal''',
        (business, ref['source_id'], row['cutoff'])).fetchall()
    preview = '\n'.join(f"{'Inicio' if r['ordinal'] == 1 else 'Último mensaje'}: {r['text']}" for r in excerpts)
    return dict(**ref, title=row['title'], report_title='Conversación', href='#chat/' + ref['source_id'],
                status='available', authority='historical_dialogue', selection_scope='conversation_snapshot',
                turn_count=row['turns'], cutoff=row['cutoff'], preview_only=True, use=USE,
                content=dict(key='conversation', title=row['title'], statement=f"{row['turns']} intercambios · Vista previa\n{preview}"),
                retrieval='open_chat: id=source_id; query="" for first page, returned next_query for subsequent pages, or literal words to search; limit=1..10 fragments.')


def listing_reference(db, business, chat_id):
    row = head(db, business, chat_id)
    return attachment(db, business, reference(row)) if row and row['turns'] else None


def assistant_text(response):
    """Visible prose only; no hidden prompts, tool payloads or recursive attachments."""
    if not response:
        return ''
    parts = [response.get('text', '')]
    kind = response.get('kind')
    if kind == 'evidence':
        parts += response.get('paragraphs') or [p for c in response.get('claims', [])
                                               for p in (c.get('statement', ''), c.get('interpretation', ''))]
    elif kind == 'memory':
        parts += [f"{i['status']}: {i['content']['statement']}" for i in response.get('items', [])]
    elif kind == 'questions':
        parts += [i['text'] for i in response.get('questions', [])]
    elif kind == 'catalog':
        parts += [' · '.join([i.get('description', ''), ', '.join(i.get('names', [])),
                              ', '.join(i.get('columns', []))]) for i in response.get('items', [])]
    return '\n'.join(p for p in parts if p)


def fragments(db, business, ref, cutoff, query):
    # Keyset batches bound Python memory even for very long histories.
    after = 0
    while True:
        rows = db.execute('''SELECT id,ordinal,payload,response FROM chat_turns
            WHERE business_id=%s AND conversation_id=%s AND ordinal>%s AND ordinal<=%s
            ORDER BY ordinal LIMIT 25''', (business, ref['source_id'], after, cutoff)).fetchall()
        if not rows:
            return
        for row in rows:
            after = row['ordinal']
            response = row['response'] or {}
            for role, text in (('user', row['payload']['text']), ('assistant', assistant_text(response))):
                # Overlap keeps literal search phrases up to the request's 300-char limit intact.
                for start in range(0, len(text), CHUNK_CHARS - 300):
                    excerpt = text[start:start + CHUNK_CHARS]
                    if query and query.casefold() not in excerpt.casefold():
                        continue
                    yield dict(message_id=str(row['id']), ordinal=row['ordinal'], role=role,
                               start=start, end=min(start + CHUNK_CHARS, len(text)), text=excerpt,
                               message_characters=len(text),
                               report_id=response.get('report_id') if role == 'assistant' else None,
                               report_version=response.get('report_version') if role == 'assistant' else None)
                    if start + CHUNK_CHARS >= len(text):
                        break


def read(db, manifest, request):
    refs = [r for r in manifest.get('context_references', [])
            if r.get('kind') == 'conversation' and r.get('source_id') == request.id]
    if not refs:
        refs = [r for r in manifest.get('conversation_references', [])
                if r.get('source_id') == request.id]
    if len(refs) != 1:
        raise ValueError('Select exactly one version of this conversation before opening it.')
    ref = refs[0]
    try:
        row = validate(db, manifest['business_id'], ref)
    except WebError as exc:
        raise ValueError(str(exc)) from exc
    # The cursor carries the search and an offset over matching fragments; it is
    # data, not authorization. Access is always revalidated against the selection.
    cursor = re.fullmatch(r'page:(\d{1,9}):(.*)', request.query, re.DOTALL)
    offset, query = (int(cursor[1]), cursor[2]) if cursor else (0, request.query)
    matches = fragments(db, manifest['business_id'], ref, row['cutoff'], query)
    items = []
    byte_count = 0
    more = False
    for index, item in enumerate(matches):
        if index < offset:
            continue
        size = len(json.dumps(item, ensure_ascii=False).encode())
        if len(items) >= request.limit or (items and byte_count + size > 10000):
            more = True
            break
        items.append(item)
        byte_count += size
    next_query = f'page:{offset + len(items)}:{query}' if more else None
    # No unbounded query/cursor can grow the model request schema.
    if next_query and len(next_query) > 300:
        raise ValueError('Use a shorter search phrase to paginate this conversation.')
    return dict(id=request.id, version=ref['source_version'], title=row['title'], use=USE,
                items=items[:request.limit], more=more, next_query=next_query,
                search=query, partial=bool(query or offset or more),
                scope='Only the selected conversation up to its captured cutoff; not other chats or later messages.'), [
                    dict(kind='conversation_selection', reference=ref)]
