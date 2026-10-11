"""Opt-in durable provider ceiling shared by legacy and the isolated engine.

An integer USD envelope at frozen Standard catalogue rates, not an invoice.
Unknown/interrupted attempts retain their full reservation and stop new sends.
The ledger stores hashes and usage only, never prompts, responses or credentials.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from uuid import uuid4

import httpx

VERSION = 'gpt-6-luna-standard-envelope-2026-10-11'
MAX_INPUT = 1_050_000
MAX_OUTPUT = 128_000
# nano-USD per token: maximum cache-write/input and output catalogue prices.
INPUT_RATE, OUTPUT_RATE = 250, 750
_SCOPE = ContextVar('api_budget_scope', default='unattributed')


class BudgetStopped(ValueError):
    pass


@contextmanager
def scope(identifier):
    token = _SCOPE.set(str(identifier))
    try:
        yield
    finally:
        _SCOPE.reset(token)


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file():
            raise BudgetStopped('Provider budget ledger is unavailable.')

    @classmethod
    def create(cls, path, *, cap_micro_usd, scope_cap_micro_usd):
        if any(type(v) is not int or v <= 0 for v in (cap_micro_usd, scope_cap_micro_usd)):
            raise ValueError('Budgets must be positive integer micro-USD.')
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        ledger = cls(path)
        with ledger.db() as db:
            db.executescript('''CREATE TABLE policy (version TEXT, cap INTEGER, scope_cap INTEGER, stopped INTEGER);
                CREATE TABLE calls (id TEXT PRIMARY KEY, scope TEXT, request_sha256 TEXT,
                endpoint TEXT, state TEXT, reserved INTEGER, charged INTEGER, input_tokens INTEGER,
                output_tokens INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
                ''')
            db.execute('INSERT INTO policy VALUES (?,?,?,0)',
                       (VERSION, cap_micro_usd*1000, scope_cap_micro_usd*1000))
        return ledger

    @contextmanager
    def db(self):
        # mode=rw prevents creating a fresh budget after deletion or a typo.
        db = sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw', uri=True, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, identifier, digest, endpoint, output):
        amount = MAX_INPUT*INPUT_RATE + output*OUTPUT_RATE
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            policy = db.execute('SELECT * FROM policy').fetchone()
            total = db.execute('SELECT coalesce(sum(charged),0) FROM calls').fetchone()[0]
            own = db.execute('SELECT coalesce(sum(charged),0) FROM calls WHERE scope=?', (identifier,)).fetchone()[0]
            if (policy['version'] != VERSION or policy['stopped'] or total+amount > policy['cap']
                    or own+amount > policy['scope_cap']):
                raise BudgetStopped('Provider budget stopped before sending this request.')
            call = uuid4().hex
            db.execute('INSERT INTO calls(id,scope,request_sha256,endpoint,state,reserved,charged) VALUES (?,?,?,?,?,?,?)',
                       (call, identifier, digest, endpoint, 'reserved', amount, amount))
            return call

    def settle(self, call, result):
        usage = result.get('usage', {}) if isinstance(result, dict) else {}
        model = result.get('model') if isinstance(result, dict) else None
        tier = result.get('service_tier') if isinstance(result, dict) else None
        inp = usage.get('input_tokens', usage.get('prompt_tokens')) if isinstance(usage, dict) else None
        out = usage.get('output_tokens', usage.get('completion_tokens')) if isinstance(usage, dict) else None
        valid = (isinstance(model, str) and (model == 'gpt-6-luna' or model.startswith('gpt-6-luna-'))
                 and tier == 'default' and type(inp) is int and type(out) is int
                 and 0 <= inp <= MAX_INPUT and 0 <= out <= MAX_OUTPUT)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM calls WHERE id=?', (call,)).fetchone()
            if row['state'] != 'reserved':
                return
            # Charging every input token at cache-write rate needs no invented
            # cache-write count. Actual catalogue estimates remain separate.
            charge = inp*(250 if inp > 272000 else 125)+out*(750 if inp > 272000 else 500) if valid else row['reserved']
            if not valid or charge > row['reserved']:
                db.execute("UPDATE calls SET state='uncertain' WHERE id=?", (call,))
                db.execute('UPDATE policy SET stopped=1')
            else:
                db.execute("UPDATE calls SET state='settled',charged=?,input_tokens=?,output_tokens=? WHERE id=?",
                           (charge, inp, out, call))

    def stop(self):
        with self.db() as db:
            db.execute('UPDATE policy SET stopped=1')

    def snapshot(self):
        with self.db() as db:
            policy = dict(db.execute('SELECT * FROM policy').fetchone())
            calls = [dict(r) for r in db.execute('SELECT * FROM calls ORDER BY created_at,id')]
        return {'policy': policy, 'calls': calls, 'charged_nano_usd': sum(c['charged'] for c in calls),
                'uncertain': any(c['state'] != 'settled' for c in calls)}


class _Stream(httpx.SyncByteStream):
    def __init__(self, inner, ledger, call, sse):
        self.inner, self.ledger, self.call, self.sse = inner, ledger, call, sse
        self.done = False

    def __iter__(self):
        body = bytearray()
        try:
            for chunk in self.inner:
                body.extend(chunk)
                if len(body) > 32*1024*1024:
                    raise ValueError('Provider budget response limit exceeded.')
                yield chunk
            result = None
            if self.sse:
                for line in body.splitlines():
                    if line.startswith(b'data:') and line[5:].strip() != b'[DONE]':
                        value = json.loads(line[5:])
                        if value.get('type') == 'response.completed':
                            result = value.get('response')
            else:
                result = json.loads(body)
            self.ledger.settle(self.call, result)
            self.done = True
        finally:
            if not self.done:
                self.ledger.settle(self.call, None)

    def close(self):
        try:
            self.inner.close()
        finally:
            if not self.done:
                self.ledger.settle(self.call, None)


class BudgetTransport(httpx.BaseTransport):
    def __init__(self, ledger, inner, identifier):
        self.ledger, self.inner, self.identifier = ledger, inner, str(identifier)

    def handle_request(self, request):
        if (request.method != 'POST' or request.url.scheme != 'https' or request.url.host != 'api.openai.com'
                or request.url.port not in (None, 443) or request.url.query):
            raise BudgetStopped('Provider budget only permits the fixed OpenAI origin.')
        value = json.loads(request.read())
        if value.get('model') != 'gpt-6-luna':
            raise BudgetStopped('Provider budget only permits its frozen model.')
        if request.url.path == '/v1/responses/input_tokens':
            return self.inner.handle_request(request)
        if request.url.path not in ('/v1/responses', '/v1/chat/completions'):
            raise BudgetStopped('Provider budget only permits text generation.')
        if value.get('service_tier', 'default') != 'default':
            raise BudgetStopped('Provider budget only permits Standard service.')
        value['service_tier'] = 'default'
        output = value.get('max_output_tokens', value.get('max_completion_tokens'))
        if type(output) is not int or not 1 <= output <= MAX_OUTPUT:
            raise BudgetStopped('Provider budget requires an explicit output ceiling.')
        # Rebuild after forcing the tier; credentials remain exclusively in memory.
        body = json.dumps(value, ensure_ascii=False).encode()
        headers = dict(request.headers); headers['content-length'] = str(len(body))
        headers['accept-encoding'] = 'identity'
        request = httpx.Request(request.method, request.url, headers=headers, content=body, extensions=request.extensions)
        call = self.ledger.reserve(self.identifier, hashlib.sha256(body).hexdigest(), request.url.path, output)
        try:
            response = self.inner.handle_request(request)
            if response.status_code != 200:
                self.ledger.settle(call, None)
                return response
            return httpx.Response(response.status_code, headers=response.headers, extensions=response.extensions,
                                  stream=_Stream(response.stream, self.ledger, call,
                                      'text/event-stream' in response.headers.get('content-type', '')))
        except BaseException:
            self.ledger.settle(call, None)
            raise

    def close(self):
        self.inner.close()


def transport(inner=None, *, identifier=None):
    path = os.environ.get('DECISION_ROOM_API_BUDGET_PATH')
    if not path:
        return inner
    return BudgetTransport(Ledger(path), inner or httpx.HTTPTransport(trust_env=False,
        retries=0, limits=httpx.Limits(max_keepalive_connections=0)), identifier or _SCOPE.get())
