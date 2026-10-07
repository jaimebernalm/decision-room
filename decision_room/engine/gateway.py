"""Stateless MCP boundary for a fixed job snapshot and its own executions."""
from uuid import UUID

from .. import execution
from ..database import connect
from . import admission, store, panorama, numbers, questions

VERSIONS = {'2025-03-26', '2025-06-18'}
TOOLS = [
    {'name': 'preguntar_propietario', 'description': 'Persist a question and pause the job without keeping an HTTP request open. Wait for an explicit owner answer before further work. An identical retry retrieves the same question.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'text': {'type': 'string'}, 'reason': {'type': 'string'},
         'options': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string'}}},
         'required': ['request_key', 'text', 'reason'], 'additionalProperties': False}},
    {'name': 'verify_numbers', 'description': 'Resolve 1–32 metric references within this job. Recalculate deterministic panorama scopes; agent calculations remain unverified without a server recipe. Does not verify prose attribution, owner units, causes or priority. Results and corrections are durable and paged; repeat unchanged input with cursor.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'cursor': {'type': 'integer', 'minimum': 0},
         'numbers': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': {
             'type': 'object', 'properties': {k: {'type': 'string'} for k in ('key', 'execution_id', 'metric')},
             'required': ['key', 'execution_id', 'metric'], 'additionalProperties': False}}},
         'required': ['request_key', 'numbers'], 'additionalProperties': False}},
    {'name': 'panorama', 'description': 'Calculate the deterministic sales overview for one permitted table. The summary is paged by JSON pointer; follow cursor without changing input. Observation IDs work with resultado. Describes recorded quantities and missing rows, not revenue, causes or approved priorities. Keep tables separate.',
     'inputSchema': {'type': 'object', 'properties': {
         'table_id': {'type': 'string'}, 'request_key': {'type': 'string'},
         'mapping': {'type': 'object', 'properties': {k: {'type': 'string'} for k in ('date', 'product', 'channel', 'quantity')},
                     'required': ['date', 'product', 'channel', 'quantity'], 'additionalProperties': False},
         'cursor': {'type': 'integer', 'minimum': 0}},
         'required': ['table_id', 'request_key'], 'additionalProperties': False}},
    {'name': 'entregar_informe', 'description': 'Persist exact draft JSON text before validation. Malformed or empty text is retained. The receipt is pending verification, not approval or completion. Repeat the same key and bytes to retrieve the same revision.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'draft_json': {'type': 'string'}},
         'required': ['request_key', 'draft_json'], 'additionalProperties': False}},
    {'name': 'consulta', 'description': 'Run Python over permitted prepared tables. Results are candidates, not analytically verified. Write result.json using the existing execution contract; use resultado to page through the full result.',
     'inputSchema': {'type': 'object', 'properties': {
         'code': {'type': 'string'}, 'tables': {'type': 'object', 'additionalProperties': {'type': 'string'}},
         'definitions': {'type': 'object'}, 'request_key': {'type': 'string'},
         'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 120}},
         'required': ['code', 'tables', 'request_key'], 'additionalProperties': False}},
    {'name': 'resultado', 'description': 'Read candidate result leaves as JSON pointer, part number and value. Long strings have consecutive parts of at most 512 characters; cursor is the next row offset. Only executions of this job are readable.',
     'inputSchema': {'type': 'object', 'properties': {
         'execution_id': {'type': 'string'}, 'cursor': {'type': 'integer', 'minimum': 0}},
         'required': ['execution_id'], 'additionalProperties': False}},
]


def _leaves(value, path=''):
    if isinstance(value, (dict, list)) and not value:
        yield {'path': path, 'part': 0, 'value': value}
    elif isinstance(value, dict):
        for key, child in value.items():
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            yield from _leaves(child, path + '/' + escaped)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _leaves(child, path + '/' + str(i))
    else:
        if len(path) > 512:
            raise ValueError('Result path exceeds the cell limit.')
        parts = [value[i:i+512] for i in range(0, len(value), 512)] if isinstance(value, str) and value else [value]
        for i, part in enumerate(parts):
            yield {'path': path, 'part': i, 'value': part}


def page_result(record, cursor=0):
    if type(cursor) is not int or cursor < 0:
        raise ValueError('Invalid result cursor.')
    rows = list(_leaves(record.get('result')))
    if cursor > len(rows):
        raise ValueError('Cursor exceeds the result.')
    page = {'execution_id': str(record['id']), 'status': record['status'],
            'verification': 'pending', 'result_sha256': admission.sha(admission.canonical(record.get('result'))),
            'columns': ['path', 'part', 'value'], 'rows': [], 'total_rows': len(rows),
            'truncated': False, 'cursor': None}
    for row in rows[cursor:cursor+100]:
        candidate = {**page, 'rows': page['rows'] + [row]}
        # Leave space for MCP/JSON-RPC framing, including escaped string content.
        if len(admission.canonical(candidate)) > 24 * 1024:
            break
        page['rows'].append(row)
    next_cursor = cursor + len(page['rows'])
    page.update(truncated=next_cursor < len(rows), cursor=next_cursor if next_cursor < len(rows) else None)
    return page


def consulta(config, job, token, args, *, backend=None):
    if set(args) - {'code', 'tables', 'definitions', 'request_key', 'timeout'}:
        raise ValueError('Unexpected consulta arguments.')
    if not isinstance(args.get('tables'), dict) or not isinstance(args.get('request_key'), str) or not 1 <= len(args['request_key']) <= 128:
        raise ValueError('Invalid consulta scope or request key.')
    allowed = {t['id'] for t in job['snapshot']}
    tables = {alias: str(UUID(str(value))) for alias, value in args['tables'].items()}
    if not tables or not set(tables.values()) <= allowed:
        raise admission.Denied('Tables are outside this job snapshot.')
    # Namespace each execution key by job, never by untrusted business arguments.
    key = 'engine-' + admission.sha(admission.canonical([str(job['id']), args['request_key']]))
    record = execution.execute(config, job['business_id'], job['analysis_id'],
                               code=args.get('code'), tables=tables, definitions=args.get('definitions'),
                               timeout=args.get('timeout', 30), request_key=key, backend=backend)
    # A tool that finishes after waiting/revocation may retain durable evidence,
    # but cannot send it into the paused/new turn.
    admission.authenticate(config, job['id'], token)
    with connect(config) as db:
        db.execute('''INSERT INTO engine_executions(business_id,run_id,execution_id)
            VALUES (%s,%s,%s) ON CONFLICT DO NOTHING''', (job['business_id'], job['id'], record['id']))
    return page_result(record)


def resultado(config, job, args):
    if set(args) - {'execution_id', 'cursor'}:
        raise ValueError('Unexpected resultado arguments.')
    execution_id = UUID(str(args['execution_id']))
    with connect(config) as db:
        linked = db.execute('''SELECT execution_id FROM engine_executions
            WHERE business_id=%s AND run_id=%s AND execution_id=%s''',
                            (job['business_id'], job['id'], execution_id)).fetchone()
    if not linked:
        frozen = panorama.observation(config, job['business_id'], job['id'], execution_id)
        if frozen:
            return {**page_result({'id': execution_id, 'status': frozen['status'], 'result': frozen['result']}, args.get('cursor', 0)),
                    'origin': 'deterministic_panorama', 'table_ids': [t['id'] for t in frozen['inputs'].values()]}
        raise admission.Denied('Execution is outside this job.')
    return page_result(execution.get_execution(config, job['business_id'], execution_id), args.get('cursor', 0))


def dispatch(config, run_id, token, message, *, backend=None):
    admission.check_credential(config, run_id, token)
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
        raise ValueError('Expected one JSON-RPC message.')
    method, params = message.get('method'), message.get('params', {})
    if 'id' not in message:
        if method != 'notifications/initialized':
            raise ValueError('Unsupported notification.')
        return None
    if type(message['id']) not in (str, int) or not isinstance(params, dict):
        raise ValueError('Invalid JSON-RPC request.')
    response = {'jsonrpc': '2.0', 'id': message['id']}
    # Only an identical owner-question receipt may be replayed while paused.
    question_call = method == 'tools/call' and params.get('name') == 'preguntar_propietario'
    job = None if question_call else admission.authenticate(config, run_id, token)
    if method == 'initialize':
        result = {'protocolVersion': params.get('protocolVersion') if params.get('protocolVersion') in VERSIONS else '2025-06-18',
                  'capabilities': {'tools': {}}, 'serverInfo': {'name': 'decision-room-engine', 'version': '0.1'}}
    elif method == 'ping':
        result = {}
    elif method == 'tools/list':
        result = {'tools': TOOLS}
    elif method == 'tools/call':
        args = params.get('arguments', {})
        if not isinstance(args, dict):
            raise ValueError('Invalid tool arguments.')
        try:
            if params.get('name') == 'preguntar_propietario':
                if set(args) - {'request_key', 'text', 'reason', 'options'} or not {'request_key', 'text', 'reason'} <= set(args):
                    raise ValueError('Invalid owner question arguments.')
                value = questions.request(config, run_id, token, **args)
            elif params.get('name') == 'verify_numbers':
                if set(args) - {'request_key', 'numbers', 'cursor'} or not {'request_key', 'numbers'} <= set(args):
                    raise ValueError('Invalid verification arguments.')
                row = numbers.verify(config, run_id, token, request_key=args['request_key'], numbers=args['numbers'])
                value = page_result({'id': row['id'], 'status': 'completed', 'result': row['body']}, args.get('cursor', 0))
                value['verification_id'] = value.pop('execution_id')
            elif params.get('name') == 'panorama':
                if set(args) - {'table_id', 'request_key', 'mapping', 'cursor'} or not {'table_id', 'request_key'} <= set(args):
                    raise ValueError('Invalid panorama arguments.')
                row = panorama.calculate(config, run_id, token, **{k: v for k, v in args.items() if k != 'cursor'})
                page = page_result({'id': row['id'], 'status': 'completed', 'result': {'tables': row['body']['tables']}}, args.get('cursor', 0))
                page['panorama_id'] = page.pop('execution_id')
                value = {**page, 'origin': 'deterministic_panorama',
                         'observation_ids': [o['execution_id'] for o in row['body']['observations']]}
            elif params.get('name') == 'entregar_informe':
                if set(args) != {'request_key', 'draft_json'} or not isinstance(args['draft_json'], str):
                    raise ValueError('Invalid delivery arguments.')
                value = store.receive_document(config, run_id, token, **args)
            elif params.get('name') == 'consulta':
                value = consulta(config, job, token, args, backend=backend)
            elif params.get('name') == 'resultado':
                value = resultado(config, job, args)
            else:
                return {**response, 'error': {'code': -32602, 'message': 'Unknown tool.'}}
            result = {'content': [{'type': 'text', 'text': admission.canonical(value).decode()}]}
        except admission.Denied:
            raise
        except (ValueError, KeyError, TypeError):
            # Execution errors may contain private storage paths; never echo them.
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'Invalid or unsuccessful calculation. Check the arguments and retry with the same request key.'}]}
    else:
        return {**response, 'error': {'code': -32601, 'message': 'Method not found.'}}
    encoded = admission.canonical({**response, 'result': result})
    if len(encoded) > 64 * 1024:
        raise ValueError('MCP response exceeds 64 KiB.')
    return {**response, 'result': result}
