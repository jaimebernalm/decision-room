"""Responses-only model proxy core with exact preflight and durable reservations.

The HTTP adapter supplies only a job ID/token and bytes. Provider URL, API key,
model and limits are trusted service configuration, never request arguments.
"""
import json
import time

import httpx

from ..database import connect
from . import admission

UPSTREAM = 'https://api.openai.com/v1'
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_EVENT_BYTES = 8 * 1024 * 1024
COUNT_FIELDS = {'model', 'input', 'instructions', 'tools', 'tool_choice', 'text',
                'reasoning', 'parallel_tool_calls'}
GENERATION_FIELDS = {'max_output_tokens', 'stream', 'store', 'include', 'metadata',
                     'prompt_cache_key', 'prompt_cache_retention', 'temperature', 'top_p', 'service_tier'}


def prepare(raw, job):
    if len(raw) > MAX_REQUEST_BYTES:
        raise admission.Denied('Model request exceeds the byte limit.')
    try:
        request = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise admission.Denied('Invalid model request.') from None
    if not isinstance(request, dict) or set(request) - COUNT_FIELDS - GENERATION_FIELDS:
        raise admission.Denied('Unsupported model request fields.')
    if request.get('model') != job['model'] or 'input' not in request:
        raise admission.Denied('Model or input does not match the job.')
    if not isinstance(request.get('tools', []), list):
        raise admission.Denied('Invalid tool list.')
    if type(request.get('stream', False)) is not bool:
        raise admission.Denied('Invalid streaming option.')
    if any(not isinstance(t, dict) or t.get('type') != 'function' for t in request.get('tools', [])):
        raise admission.Denied('Only local function tools are allowed.')
    items = request['input']
    if not isinstance(items, (str, list)):
        raise admission.Denied('Unsupported model input.')
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get('type', 'message') not in {
            'message', 'function_call', 'function_call_output', 'reasoning', 'compaction'
        }:
            raise admission.Denied('Remote input references and media are not supported.')
        content = item.get('content', item.get('output', ''))
        if isinstance(content, list) and any(not isinstance(c, dict) or c.get('type') not in {
            'input_text', 'output_text', 'refusal', 'reasoning_text'
        } for c in content):
            raise admission.Denied('Only explicit text content is supported.')
    output = request.get('max_output_tokens', job['limits']['output_per_call'])
    if type(output) is not int or output <= 0:
        raise admission.Denied('Invalid output limit.')
    request['max_output_tokens'] = min(output, job['limits']['output_per_call'])
    request['store'] = False
    # Count the exact same supported input representation, including schemas.
    count = {k: v for k, v in request.items() if k in COUNT_FIELDS}
    return request, count


def usage_from(value):
    if not isinstance(value, dict):
        return None
    try:
        usage = {'input': value['input_tokens'], 'output': value['output_tokens'],
                 'cached': (value.get('input_tokens_details') or {}).get('cached_tokens', 0)}
        if any(type(v) is not int or v < 0 for v in usage.values()) or usage['cached'] > usage['input']:
            return None
        return usage
    except (KeyError, TypeError, AttributeError):
        return None


class EventUsage:
    """Bounded incremental SSE parser; handles CRLF and split UTF-8/chunks."""
    def __init__(self):
        self.pending = b''
        self.data = []
        self.usage = None
        self.status = None

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) + sum(map(len, self.data)) > MAX_EVENT_BYTES:
            raise ValueError('Provider event exceeds the byte limit.')
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            line = line.rstrip(b'\r')
            if not line:
                if self.data:
                    try:
                        value = json.loads(b'\n'.join(self.data))
                    except ValueError:
                        value = {}
                    self.data = []
                    if value.get('type') in {'response.completed', 'response.incomplete', 'response.failed'}:
                        response = value.get('response') or {}
                        self.usage = usage_from(response.get('usage'))
                        self.status = response.get('status')
            elif line.startswith(b'data:'):
                self.data.append(line[5:].lstrip())


def forward(config, run_id, token, raw, *, api_key, send_headers, write, transport=None):
    """Stream one request, recording uncertainty even when the client disconnects.

    No retries are performed. `transport` exists for offline integration tests;
    the HTTP service never accepts it from the agent.
    """
    job = admission.authenticate(config, run_id, token)
    request, count_request = prepare(raw, job)
    if not api_key:
        raise admission.Denied('Provider service is not configured.')
    call_id = admission.begin_call(config, run_id, token, admission.sha(admission.canonical(request)))
    usage, reason, settled = None, None, False
    started = time.monotonic()
    try:
        with httpx.Client(transport=transport, trust_env=False, follow_redirects=False,
                          timeout=min(120.0, job['remaining_seconds']),
                          headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}) as client:
            counted = client.post(UPSTREAM + '/responses/input_tokens', json=count_request)
            if counted.status_code != 200:
                reason = 'input_count_failed'
                raise admission.Aborted('Input counting failed.')
            value = counted.json().get('input_tokens')
            if type(value) is not int or value < 0:
                reason = 'input_count_invalid'
                raise admission.Aborted('Input counting returned an invalid count.')
            with connect(config) as db:
                db.execute('UPDATE engine_model_calls SET count_seconds=%s WHERE id=%s',
                           (time.monotonic() - started, call_id))
            admission.reserve(config, run_id, token, call_id, value, request['max_output_tokens'])
            current = admission.authenticate(config, run_id, token)
            with client.stream('POST', UPSTREAM + '/responses', json=request,
                               timeout=min(120.0, current['remaining_seconds'])) as response:
                if response.status_code != 200:
                    reason = 'provider_http_error'
                    raise admission.Aborted('Provider request failed.')
                is_sse = response.headers.get('content-type', '').split(';')[0] == 'text/event-stream'
                if bool(request.get('stream')) != is_sse:
                    reason = 'provider_transport_mismatch'
                    raise admission.Aborted('Provider transport mismatch.')
                send_headers(200, 'text/event-stream' if is_sse else 'application/json')
                parser, body = EventUsage(), bytearray()
                checked = 0
                for chunk in response.iter_bytes():
                    if time.monotonic() - checked >= 1:
                        admission.authenticate(config, run_id, token, check_snapshot=False)
                        checked = time.monotonic()
                    if is_sse:
                        parser.feed(chunk)
                    else:
                        body.extend(chunk)
                        if len(body) > MAX_EVENT_BYTES:
                            raise ValueError('Provider response exceeds the byte limit.')
                    write(chunk)
                if is_sse:
                    parser.feed(b'\n\n')
                    usage, status = parser.usage, parser.status
                else:
                    result = json.loads(body)
                    usage, status = usage_from(result.get('usage')), result.get('status')
                if status != 'completed':
                    reason = 'provider_response_incomplete'
        reason = admission.settle(config, run_id, call_id, usage=usage, reason=reason)
        settled = True
        if usage is None or reason:
            raise admission.Aborted('Provider response ended without confirmed completion.')
    except BaseException:
        if not settled:
            admission.settle(config, run_id, call_id, usage=usage, reason=reason or 'provider_usage_unknown')
        raise
    return call_id
