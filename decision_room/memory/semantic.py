"""Hybrid retrieval over current, authorized originals; vectors are only a cache.

Exact cosine search intentionally avoids approximate-index filtering losses. A bounded
corpus is rebuilt on demand, outside memory writer locks. Never query cached objects
without joining the caller's freshly scoped keys AND content hashes.
"""
import json
import math
import os
from uuid import uuid4

import httpx
from psycopg.types.json import Jsonb

from .service import digest

VERSION = 'hybrid-v1'
MAX_DOCUMENTS = 1000
MAX_CHUNKS = 512
BATCH = 32
CHUNK_BYTES = 4000
OVERLAP_BYTES = 400


class EmbeddingUnavailable(ValueError):
    """Safe diagnostic: never include provider response bodies or credentials."""


def chunks(text):
    # At most 4000 UTF-8 bytes (therefore <=4000 byte-BPE tokens) per input.
    # Preserve Unicode boundaries and overlap without discarding any text.
    result = []
    while text:
        fragment = text.encode()[:CHUNK_BYTES].decode('utf-8', errors='ignore')
        result.append(fragment)
        if len(fragment) == len(text):
            break
        overlap = fragment.encode()[-OVERLAP_BYTES:].decode('utf-8', errors='ignore')
        text = text[len(fragment) - len(overlap):]
    return result


def _validate_vectors(vectors, count, dimensions):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise EmbeddingUnavailable('Invalid embedding count.')
    for vector in vectors:
        if (not isinstance(vector, list) or len(vector) != dimensions or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in vector) or
                not 0 < sum(v * v for v in vector) < 1e20):
            raise EmbeddingUnavailable('Invalid embedding vector.')


def embed(config, texts):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise EmbeddingUnavailable('OPENAI_API_KEY is not configured.')
    try:
        # Dedicated official endpoint: never send this key to the agent's local URL.
        # No redirects, environment proxies or automatic retries of billable calls.
        with httpx.Client(timeout=30, trust_env=False) as client:
            with client.stream('POST', 'https://api.openai.com/v1/embeddings',
                               headers={'Authorization': 'Bearer ' + key},
                               json=dict(model=config.embedding_model, dimensions=config.embedding_dimensions,
                                         input=texts, encoding_format='float')) as response:
                if response.status_code != 200:
                    raise EmbeddingUnavailable(f'Embedding provider HTTP {response.status_code}.')
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > 8 * 1024**2:
                        raise EmbeddingUnavailable('Embedding response exceeds 8 MiB.')
        data = json.loads(body)
        if data['model'] != config.embedding_model:
            raise EmbeddingUnavailable('Embedding provider returned a different model.')
        ordered = sorted(data['data'], key=lambda item: item['index'])
        if [item['index'] for item in ordered] != list(range(len(texts))):
            raise EmbeddingUnavailable('Invalid embedding indices.')
        vectors = [item['embedding'] for item in ordered]
        _validate_vectors(vectors, len(texts), config.embedding_dimensions)
        return vectors, {k: data.get('usage', {}).get(k) for k in ('prompt_tokens', 'total_tokens')}
    except httpx.HTTPError as error:
        raise EmbeddingUnavailable(f'Embedding transport failed ({type(error).__name__}).') from None
    except (KeyError, TypeError, json.JSONDecodeError):
        raise EmbeddingUnavailable('Invalid embedding response.') from None


def _call(config, db, business_id, texts, purpose):
    identifier = uuid4()
    db.execute('''INSERT INTO semantic_calls
        (id,business_id,model,dimensions,purpose,input_hash,input_count,status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'running')''',
        (identifier, business_id, config.embedding_model, config.embedding_dimensions,
         purpose, digest(texts), len(texts)))
    try:
        vectors, usage = embed(config, texts)
        _validate_vectors(vectors, len(texts), config.embedding_dimensions)
    except EmbeddingUnavailable as error:
        db.execute("UPDATE semantic_calls SET status='failed',issue=%s,finished_at=now() WHERE id=%s",
                   (str(error), identifier))
        raise
    db.execute("UPDATE semantic_calls SET status='completed',usage=%s,finished_at=now() WHERE id=%s",
               (Jsonb(usage), identifier))
    return vectors


def _vector(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def _semantic(config, db, business_id, kind, documents, query):
    pieces = [(d, ordinal, fragment) for d in documents for ordinal, fragment in enumerate(chunks(d['text']))]
    if len(pieces) > MAX_CHUNKS:
        raise EmbeddingUnavailable('Semantic corpus exceeds 512 fragments; narrow the scope.')
    identities = [dict(key=d['key'], hash=d['hash']) for d in documents]
    present = db.execute('''SELECT c.object_key,c.content_hash,c.ordinal FROM semantic_chunks c
        JOIN jsonb_to_recordset(%s) AS wanted(key text,hash text)
        ON c.object_key=wanted.key AND c.content_hash=wanted.hash
        WHERE c.business_id=%s AND c.kind=%s AND c.model=%s AND c.dimensions=%s''',
        (Jsonb(identities), business_id, kind, config.embedding_model, config.embedding_dimensions)).fetchall()
    keys = {(r['object_key'], r['content_hash'], r['ordinal']) for r in present}
    missing = [(d, n, t) for d, n, t in pieces if (d['key'], d['hash'], n) not in keys]
    for offset in range(0, len(missing), BATCH):
        batch = missing[offset:offset + BATCH]
        vectors = _call(config, db, business_id, [p[2] for p in batch], 'documents')
        with db.transaction():
            for (d, ordinal, fragment), vector in zip(batch, vectors):
                db.execute('''INSERT INTO semantic_chunks
                    (business_id,kind,object_key,content_hash,model,dimensions,ordinal,fragment,embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING''',
                    (business_id, kind, d['key'], d['hash'], config.embedding_model,
                     config.embedding_dimensions, ordinal, fragment, _vector(vector)))
    vector = _call(config, db, business_id, [query], 'query')[0]
    rows = db.execute('''SELECT DISTINCT ON (c.object_key) c.object_key AS key,
        1 - (c.embedding <=> %s::vector) AS score,c.fragment
        FROM semantic_chunks c JOIN jsonb_to_recordset(%s) AS wanted(key text,hash text)
        ON c.object_key=wanted.key AND c.content_hash=wanted.hash
        WHERE c.business_id=%s AND c.kind=%s AND c.model=%s AND c.dimensions=%s
        ORDER BY c.object_key,score DESC,c.ordinal''',
        (_vector(vector), Jsonb(identities), business_id, kind, config.embedding_model, config.embedding_dimensions)).fetchall()
    return sorted(rows, key=lambda r: (-r['score'], r['key']))


def rank(config, db, business_id, kind, documents, query, limit):
    """Return keys and auditable search metadata; callers revalidate the originals.

Documents contain key/version/text. Similarity always supplies candidates, never a
claim of relevance or factual validity. RRF gives each retriever equal weight.
"""
    if len(documents) > MAX_DOCUMENTS:
        raise ValueError('Search corpus exceeds 1000 objects. Narrow the business/source scope.')
    docs = [{**d, 'hash': digest([VERSION, kind, d['key'], d['version'], d['text']])} for d in documents]
    if len({d['key'] for d in docs}) != len(docs):
        raise ValueError('Duplicate search object keys.')
    info = dict(version=VERSION, mode='catalog' if not query else 'text',
                model=config.embedding_model if config.semantic_search else None,
                dimensions=config.embedding_dimensions if config.semantic_search else None,
                corpus_count=len(docs), matches=[])
    if not query or not docs:
        return [d['key'] for d in docs[:limit]], info
    lexical = db.execute('''SELECT key,ts_rank(to_tsvector('spanish',text),plainto_tsquery('spanish',%s)) AS score
        FROM jsonb_to_recordset(%s) AS d(key text,text text)
        WHERE to_tsvector('spanish',text) @@ plainto_tsquery('spanish',%s)
        ORDER BY score DESC,key''', (query, Jsonb([dict(key=d['key'], text=d['text']) for d in docs]), query)).fetchall()
    semantic = []
    if config.semantic_search:
        try:
            semantic = _semantic(config, db, business_id, kind, docs, query)
            info['mode'] = 'hybrid'
        except EmbeddingUnavailable as error:
            info.update(mode='text_fallback', issue=str(error))
    else:
        info['issue'] = 'Semantic search is disabled.'
    # Cap each ranked contribution equally; otherwise a long vector tail can
    # promote weak lexical coincidences simply because every vector has a score.
    candidates = {}
    by_key = {d['key']: d for d in docs}
    for method, rows in [('lexical', lexical[:50]), ('semantic', semantic[:50])]:
        for position, row in enumerate(rows, 1):
            key = row['key']
            item = candidates.setdefault(key, dict(key=key, version=by_key[key]['version'], score=0))
            item['score'] += 1 / (60 + position)
            item[method + '_rank'] = position
            item[method + '_score'] = float(row['score'])
            if method == 'semantic':
                item['excerpt'] = row['fragment'][:500]
    ordered = sorted(candidates.values(), key=lambda item: (-item['score'], item['key']))
    info['matches'] = ordered[:limit]
    info['more'] = len(ordered) > limit or len(lexical) > 50 or len(semantic) > 50
    return [item['key'] for item in ordered[:limit]], info
