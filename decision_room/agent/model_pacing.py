"""Conservative local TPM admission across roles and processes, without prompts."""
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time


def estimate_tokens(payload):
    # Explicit estimate, not billed usage or an exact provider tokenizer. Include
    # schema/corrections and reserve the whole output allowance. Three UTF-8
    # bytes/token is deliberately conservative for the usual Spanish/JSON input.
    content = {k: v for k, v in payload.items() if k not in ('max_tokens', 'max_completion_tokens', 'max_output_tokens')}
    size = len(json.dumps(content, ensure_ascii=False).encode())
    output = next((payload[k] for k in ('max_completion_tokens', 'max_tokens', 'max_output_tokens') if k in payload), 0)
    return math.ceil(size / 3) + output


def reserve(path, bucket, tokens, limit, now):
    """Atomically reserve a 60-second rolling window, or return a minimum wait."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with sqlite3.connect(path, timeout=1) as db:
        db.execute('CREATE TABLE IF NOT EXISTS reservations (bucket TEXT, at REAL, tokens INTEGER)')
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM reservations WHERE at <= ?', (now - 60,))
        rows = db.execute('SELECT at,tokens FROM reservations WHERE bucket=? ORDER BY at', (bucket,)).fetchall()
        total = sum(r[1] for r in rows)
        for at, count in rows:
            if total + tokens <= limit:
                break
            total -= count
            wait = at + 60 - now
        if sum(r[1] for r in rows) + tokens > limit:
            return max(.01, wait)
        db.execute('INSERT INTO reservations VALUES (?,?,?)', (bucket, now, tokens))
    path.chmod(0o600)
    return 0


async def admit(settings, tokens):
    limit = settings.tokens_per_minute
    if settings.protocol != 'openai' or not limit:
        return 0
    if tokens > limit:
        raise ValueError(f'Estimated request ({tokens} tokens including output) exceeds configured TPM ({limit}); reduce context or increase the configured limit.')
    from ..config import ROOT
    storage = Path(os.environ.get('DECISION_ROOM_STORAGE', ROOT / '.local/storage'))
    path = storage / 'model-rate-reservations.sqlite3'
    # Explicit pool allows models sharing a provider limit to share this bucket.
    pool = os.environ.get('DECISION_ROOM_AGENT_RATE_POOL', settings.model)
    bucket = hashlib.sha256((settings.base_url + ':' + pool).encode()).hexdigest()
    waited = 0
    while True:
        delay = reserve(path, bucket, tokens, limit, time.time())
        if not delay:
            return waited
        await asyncio.sleep(delay)
        waited += delay
