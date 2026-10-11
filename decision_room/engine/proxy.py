"""Responses-only model proxy core with exact preflight and durable reservations.

The HTTP adapter supplies only a job ID/token and bytes. Provider URL, API key,
model and limits are trusted service configuration, never request arguments.
"""
import json
import time

import httpx

from ..database import connect
from . import admission, costs, diagnostics
from .transport_trace import TransportTrace

UPSTREAM = 'https://api.openai.com/v1'
SERVICE_TIER = 'default'  # Trusted Standard policy; never inherit project auto/Fast.
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
    if request.get('service_tier', SERVICE_TIER) != SERVICE_TIER:
        raise admission.Denied('The engine requires Standard processing.')
    request['service_tier'] = SERVICE_TIER
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
        self.response = None

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
                        self.response = response
                        self.usage = usage_from(response.get('usage'))
                        self.status = response.get('status')
            elif line.startswith(b'data:'):
                self.data.append(line[5:].lstrip())


def provider_timeout(remaining_seconds):
    """Idle read allowance, bounded by the run; other phases stay short."""
    read = max(0.001, min(300.0, remaining_seconds))
    return httpx.Timeout(connect=min(10.0, read), write=min(30.0, read),
                         pool=min(10.0, read), read=read)


def forward(config, run_id, token, raw, *, api_key, send_headers, write, transport=None):
    """Stream one request, recording uncertainty even when the client disconnects.

    No retries are performed. `transport` exists for offline integration tests;
    the HTTP service never accepts it from the agent.
    """
    job = admission.authenticate(config, run_id, token, allow_checker=True)
    request, count_request = prepare(raw, job)
    if not api_key:
        raise admission.Denied('Provider service is not configured.')
    call_id = admission.begin_call(config, run_id, token, admission.sha(admission.canonical(request)),
                                   requested_model=job['model'], requested_tier=SERVICE_TIER)
    usage, reason, settled = None, None, False
    measured = None
    parser = None
    body = bytearray()
    count_trace, generation_trace = TransportTrace(), TransportTrace()
    def transport_receipt():
        return {'connection_policy': 'no_keepalive' if transport is None else 'injected_transport',
                'input_count': count_trace.snapshot(), 'generation': generation_trace.snapshot()}
    def billing():
        return costs.capture(measured or (parser.response if parser else None),
                             requested_model=job['model'], requested_tier=SERVICE_TIER)
    started = time.monotonic()
    stage = 'count_input'
    try:
        from ..agent import api_budget
        from . import provider_budget
        guarded = api_budget.transport(transport, identifier='engine:'+str(run_id))
        guarded = provider_budget.transport(config, job, guarded)
        with httpx.Client(transport=guarded, trust_env=False, follow_redirects=False,
                          http2=False, limits=httpx.Limits(max_keepalive_connections=0),
                          timeout=provider_timeout(job['remaining_seconds']),
                          headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'}) as client:
            counted = client.post(UPSTREAM + '/responses/input_tokens', json=count_request,
                                  extensions={'trace': count_trace})
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
            stage = 'reserve_tokens'
            admission.reserve(config, run_id, token, call_id, value, request['max_output_tokens'])
            current = admission.authenticate(config, run_id, token, allow_checker=True)
            stage = 'open_provider_response'
            with client.stream('POST', UPSTREAM + '/responses', json=request,
                               extensions={'trace': generation_trace},
                               timeout=provider_timeout(current['remaining_seconds'])) as response:
                if response.status_code != 200:
                    reason = 'provider_http_error'
                    raise admission.Aborted('Provider request failed.')
                is_sse = response.headers.get('content-type', '').split(';')[0] == 'text/event-stream'
                if bool(request.get('stream')) != is_sse:
                    reason = 'provider_transport_mismatch'
                    raise admission.Aborted('Provider transport mismatch.')
                stage = 'write_downstream_headers'
                send_headers(200, 'text/event-stream' if is_sse else 'application/json')
                parser, body = EventUsage(), bytearray()
                checked = 0
                stage = 'read_provider_stream'
                for chunk in response.iter_bytes():
                    if time.monotonic() - checked >= 1:
                        stage = 'check_stream_job'
                        admission.authenticate(config, run_id, token, check_snapshot=False, allow_checker=True)
                        checked = time.monotonic()
                    stage = 'parse_provider_stream'
                    if is_sse:
                        parser.feed(chunk)
                    else:
                        body.extend(chunk)
                        if len(body) > MAX_EVENT_BYTES:
                            raise ValueError('Provider response exceeds the byte limit.')
                    stage = 'write_downstream_chunk'
                    write(chunk)
                    stage = 'read_provider_stream'
                stage = 'parse_provider_completion'
                if is_sse:
                    parser.feed(b'\n\n')
                    usage, status = parser.usage, parser.status
                    measured = parser.response
                else:
                    result = json.loads(body)
                    measured = result
                    usage, status = usage_from(result.get('usage')), result.get('status')
                if status != 'completed':
                    reason = 'provider_response_incomplete'
        stage = 'settle_model_call'
        with connect(config) as db:
            admission._event(db, run_id, 'model_call_transport', {
                'call_id': str(call_id), 'transport': transport_receipt()})
        reason = admission.settle(config, run_id, call_id, usage=usage, reason=reason, billing=billing())
        settled = True
        if usage is None or reason:
            raise admission.Aborted('Provider response ended without confirmed completion.')
    except BaseException as error:
        # Capture the failing boundary before settlement changes the job state.
        # Only fixed descriptions and exception class names leave this boundary.
        detail = diagnostics.describe_proxy(error, stage)
        failure_reason = reason or 'provider_usage_unknown'
        try:
            with connect(config) as db:
                stopped = db.execute('SELECT abort_reason FROM engine_runs WHERE id=%s', (run_id,)).fetchone()
                failure_reason = reason or (stopped['abort_reason'] if stopped else None) or failure_reason
                admission._event(db, run_id, 'proxy_issue', {
                    'code': failure_reason, 'call_id': str(call_id), **detail,
                    'transport': transport_receipt()})
        finally:
            # Diagnostic persistence must not prevent the conservative settlement.
            if not settled:
                # A terminal SSE receipt remains billable evidence even when writing
                # that chunk to a disconnected downstream client fails.
                if measured is None and body:
                    try:
                        measured = json.loads(body)
                        usage = usage or usage_from(measured.get('usage'))
                    except (ValueError, AttributeError):
                        measured = None
                usage = usage or (parser.usage if parser else None)
                admission.settle(config, run_id, call_id, usage=usage, reason=failure_reason, billing=billing())
        raise
    return call_id
