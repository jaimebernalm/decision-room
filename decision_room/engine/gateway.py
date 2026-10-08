"""Stateless MCP boundary for a fixed job snapshot and its own executions."""
from copy import deepcopy
from uuid import UUID
import re

from .. import execution
from ..database import connect
from ..reports.contract import format_feedback
from . import admission, store, panorama, numbers, questions, calculations, exploration

VERSIONS = {'2025-03-26', '2025-06-18'}
TOOLS = [
    {'name': 'calculo', 'description': (
        'Server-owned scalar recipes on one permitted table; usable as numbers/facts with the returned execution_id and recipe key as metric. '
        'No SQL or agent code. Up to 32 recipes: count rows (column=null), sum, mean, min or max of one existing numeric column. '
        'Each recipe fits in 4 KiB; up to 8 AND filters per recipe: in uses exact strings; date_between uses two inclusive canonical YYYY-MM-DD dates. '
        'date_between accepts source ISO dates or complete naive ISO timestamps (space/T separator, seconds, optional 1–6 fractional digits), selecting their calendar day without timezone conversion. Zoned or malformed values remain unavailable. '
        'No joins, deduplication, locale parsing, inferred units or imputation. Null filter values are excluded; numeric nulls are excluded and their count is visible. '
        'Empty numeric selections and malformed dates/numbers are unavailable, not zero. Mean uses the non-null record count, not calendar days. '
        'Bounded to 200000 input rows, 128 MiB Parquet and 30 s; no truncated result is certified. Values rounded to 12 decimal places. '
        'Follow next_call for all result pages, generated display scopes and issues. Use consulta for unsupported analysis and retain its uncertainty. '
        'Example recipe: {"key":"units","operation":"sum","column":"quantity","filters":[{"column":"channel","operator":"in","values":["Local"]}]}. '
        'A retry requires identical input; changed recipes require a new request_key.'),
     'inputSchema': {'type':'object','properties': {
         'table_id':{'type':'string'}, 'request_key':{'type':'string'}, 'cursor':{'type':'integer','minimum':0},
         'recipes':{'type':'array','minItems':1,'maxItems':32,'items':{'type':'object','properties': {
             'key':{'type':'string'}, 'operation':{'type':'string','enum':['count','sum','mean','min','max']},
             'column':{'type':['string','null']}, 'filters':{'type':'array','maxItems':8,'items':{'type':'object','properties':{
                 'column':{'type':'string'}, 'operator':{'type':'string','enum':['in','date_between']},
                 'values':{'type':'array','minItems':1,'maxItems':16,'items':{'type':'string'}}},
                 'required':['column','operator','values'],'additionalProperties':False}}},
             'required':['key','operation','column','filters'],'additionalProperties':False}}},
         'required':['table_id','request_key','recipes'],'additionalProperties':False}},
    {'name': 'preguntar_propietario', 'description': 'Persist a question and pause the job without keeping an HTTP request open. Wait for an explicit owner answer before further work. An identical retry retrieves the same question.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'text': {'type': 'string'}, 'reason': {'type': 'string'},
         'options': {'type': 'array', 'maxItems': 8, 'items': {'type': 'string'}}},
         'required': ['request_key', 'text', 'reason'], 'additionalProperties': False}},
    {'name': 'verify_numbers', 'description': 'Resolve 1–32 metric references within this job. Recalculate deterministic panorama and calculo scopes; agent calculations remain unverified without a server recipe. Does not verify prose attribution, owner units, causes or priority. Results and corrections are durable and paged. Follow next_call: reuse previous arguments and replace cursor with next_cursor; do not reset it to zero.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'cursor': {'type': 'integer', 'minimum': 0},
         'numbers': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': {
             'type': 'object', 'properties': {k: {'type': 'string'} for k in ('key', 'execution_id', 'metric')},
             'required': ['key', 'execution_id', 'metric'], 'additionalProperties': False}}},
         'required': ['request_key', 'numbers'], 'additionalProperties': False}},
    {'name': 'panorama', 'description': 'Calculate the deterministic sales overview for one permitted table. The summary is paged by JSON pointer. requested_cursor is the current offset; next_cursor is the NEXT offset. Follow next_call by reusing previous arguments and replacing cursor. For example, next_cursor=100 means call panorama with cursor=100, not 0. Keep table_id, mapping and request_key unchanged; null means no more pages. Observation IDs work with resultado. Describes recorded quantities and missing rows, not revenue, causes or approved priorities. Keep tables separate. The summary ratios section includes server-derived percentage changes and group shares with bound metric references and explicit zero/negative-base limits. Use those references rather than inventing metric names.',
     'inputSchema': {'type': 'object', 'properties': {
         'table_id': {'type': 'string'}, 'request_key': {'type': 'string'},
         'mapping': {'type': 'object', 'properties': {k: {'type': 'string'} for k in ('date', 'product', 'channel', 'quantity')},
                     'required': ['date', 'product', 'channel', 'quantity'], 'additionalProperties': False},
         'cursor': {'type': 'integer', 'minimum': 0}},
         'required': ['table_id', 'request_key'], 'additionalProperties': False}},
    {'name': 'entregar_informe', 'description': 'Persist exact draft JSON text before validation. Malformed or empty text is retained. After saving, format.valid=false returns isError with a field path and expected shape: correct the complete JSON and deliver with a new request_key. limitations and scope are strings, not lists. format.valid=true validates shape only. The receipt is pending verification, not approval or completion. Continue investigation after a checkpoint draft; deliver a revised final report before ending your turn. Calculations do not automatically appear in the report: put supported recipe references in numbers and their keys in facts of the relevant finding. Do not invent references; keep necessary unsupported figures and explain their uncertainty. Repeat the same key and bytes to retrieve the same revision.',
     'inputSchema': {'type': 'object', 'properties': {
         'request_key': {'type': 'string'}, 'draft_json': {'type': 'string'}},
         'required': ['request_key', 'draft_json'], 'additionalProperties': False}},
    {'name': 'consulta', 'description': (
        'Run Python in an isolated calculation sandbox. The tables ARGUMENT maps aliases to prepared-table UUIDs from /inputs/manifest.json; '
        'Check column types from the manifest: a numeric-looking CSV field may be text and need validated explicit casting before SUM/arithmetic. '
        'There is NO implicit Python variable named tables. Import from dr_runtime: connect() returns a DuckDB connection with one read-only Parquet view per alias; '
        'table_path(alias) returns the Parquet path if you need pandas.read_parquet; TABLES is alias -> metadata, not dataframes, and DEFINITIONS holds the supplied definitions. '
        'Use write_result(metrics, evidence=[{metric, tables:[aliases], operation}], notes=[strings]) to write /output/result.json. '
        'metrics is a dict of 1–256 named scalars: keys 1–100 characters, values string/int/float/bool/null; '
        'strings at most 1000 characters and numeric values finite. Lists, dicts, DataFrames and JSON-encoded tables are not metrics. '
        'Every metric needs matching evidence; convert Decimal values to strings. Printing or assigning result alone does not deliver a result. '
        'For grouped results use named scalar metrics per group (within limits) or series, not a nested table in metrics. '
        'series is a dict of up to 4 named series; each has unit, grain="category", points:[{label:string,value:number}], '
        'evidence:{tables:[aliases],operation:string}. Category labels are 1–100 characters. Use 2–366 uniquely labelled points per series, at most 800 points total. '
        'Keep at least one scalar metric (e.g. group_count) with evidence when using series. A one-point result is a scalar. '
        'notes contains at most 100 strings of at most 4000 characters. Write additional CSV/Parquet tables under /output '
        'only as retained artifacts; resultado currently pages result.json, not those artifact contents. '
        'For an explicit top-N, include full group count and the selection/ordering rule; do not pass a truncated subset as a total. '
        'On failed/invalid_output read diagnostic and submit corrected code with a NEW request_key. '

        'Example with tables={"data":"UUID_FROM_MANIFEST"}:\n'
        'from dr_runtime import connect, write_result\n'
        'with connect() as db:\n    rows = db.execute("SELECT COUNT(*) FROM data").fetchone()[0]\n'
        'write_result({"rows": rows}, evidence=[{"metric":"rows","tables":["data"],"operation":"COUNT(*) FROM data"}])\n'
        'Returns execution_id, status, and paged result leaves (path, part, value). Follow the returned next_call with resultado; next_cursor is the NEXT offset, null only at the end. '
        'An identical request_key and program retrieves the same execution; a changed/fixed program needs a new request_key. '
        'Results are candidates, not analytically verified.'),
     'inputSchema': {'type': 'object', 'properties': {
         'code': {'type': 'string'}, 'tables': {'type': 'object', 'additionalProperties': {'type': 'string'}},
         'definitions': {'type': 'object'}, 'request_key': {'type': 'string'},
         'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 120}},
         'required': ['code', 'tables', 'request_key'], 'additionalProperties': False}},
    {'name': 'resultado', 'description': 'Read candidate result leaves as JSON pointer, part number and value. Long strings have consecutive parts of at most 512 characters; requested_cursor is the current row offset and next_cursor is the NEXT offset. Follow next_call until null, without restarting at zero. Only executions of this job are readable.',
     'inputSchema': {'type': 'object', 'properties': {
         'execution_id': {'type': 'string'}, 'cursor': {'type': 'integer', 'minimum': 0}},
         'required': ['execution_id'], 'additionalProperties': False}},
]


# R1 exploration views reuse the same execution and snapshot boundaries.
_explore = deepcopy(next(t for t in TOOLS if t['name']=='consulta'))
_explore['name']='explorar'
_explore['description']=('Explore with Python and print tables/series using the same scoped aliases and dr_runtime as consulta. '
    'Printed stdout is returned directly as unverified candidate material, with exact paging via salida. '
    'write_result is optional for exploration; completed only means the program exited successfully, not that output was verified. '
    'Check retention_truncated: lost log bytes cannot be paged back. Print selected columns, counts and selection rules; narrow oversized output. '
    'Use consulta/write_result for structured metrics; use calculo for server-owned recipes. '
    + _explore['description'])
TOOLS.append(_explore)
_readable = deepcopy(next(t for t in TOOLS if t['name']=='panorama'))
_readable['name']='panorama_lectura'
_readable['description']=('Read the deterministic panorama as complete readable table/signal blocks, including all compact gap/change signals. '
    'References R1, R2, etc. are expanded to execution_id/metric in the final reference section; do not use R labels as metric IDs. '
    'cursor is a Unicode character offset. Follow next_call with the same table/request key and mapping. '
    'For all detailed totals and ratios use panorama. This overview does not certify interpretation or priorities.')
TOOLS.append(_readable)
TOOLS.append({'name':'salida','description':'Read retained stdout from a sandbox execution of this job only. Unverified exploration text, never a certified metric. Follow next_call; retention_truncated means some output was lost before paging.',
    'inputSchema':{'type':'object','properties':{'execution_id':{'type':'string'},'cursor':{'type':'integer','minimum':0}},
                   'required':['execution_id'],'additionalProperties':False}})


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


# Expose only known contract diagnostics, never raw exceptions, logs or paths.
_RESULT_ERRORS = {
    'Missing result.json.': ('missing_result', 'Call dr_runtime.write_result(metrics, evidence=...) before the program exits.'),
    'Metrics must contain named scalar values.': ('non_scalar_metric', 'Use a dict of named scalar values; move grouped numeric points to series. Lists, dicts and DataFrames are not scalar metrics.'),
    'Metric text too long.': ('metric_text_too_long', 'Each metric string is at most 1000 characters. Do not encode a table as one metric; use named scalars or series.'),
    'Provide between 1 and 256 metrics.': ('metric_count', 'Provide 1–256 named scalar metrics, including when using series.'),
    'Invalid result schema.': ('result_schema', 'Use write_result(metrics, evidence=..., notes=..., series=...) to produce schema_version 1.'),
    'Metric is not finite.': ('nonfinite_metric', 'Remove NaN/Infinity; represent unavailable values as null with an explicit limitation.'),
    'Missing or excessive evidence.': ('evidence_count', 'Provide 1–512 evidence entries and cover every metric.'),
    'Invalid evidence schema.': ('evidence_schema', 'Each evidence entry needs metric, tables (aliases) and operation.'),
    'Evidence refers to an unknown metric.': ('evidence_metric', 'Match each evidence.metric to a key in metrics.'),
    'Evidence refers to an unauthorized table.': ('evidence_table', 'Use only the aliases in this consulta tables argument.'),
    'Invalid notes.': ('notes_shape', 'Use at most 100 note strings, each at most 4000 characters.'),
    'At most four saved series per execution.': ('series_count', 'Use at most four series per execution.'),
    'Series require unit, grain, points and evidence.': ('series_shape', 'Each series needs unit, grain, points and evidence; arbitrary table columns are not series.'),
    'Invalid series unit or grain.': ('series_unit_grain', 'Use a nonempty unit of at most 80 characters and a supported grain, such as category.'),
    'Series points need label and value.': ('series_point_shape', 'Each point has exactly label and value.'),
    'Series labels must be unique; dates must be ordered.': ('series_labels', 'Use unique category labels, or ordered dates for calendar grains.'),
}


def diagnostic(record):
    if record['status'] not in {'failed', 'invalid_output', 'timed_out', 'interrupted'}:
        return None
    issue = record.get('issue')
    known = _RESULT_ERRORS.get(issue) if isinstance(issue, str) else None
    if known is None and isinstance(issue, str) and issue.startswith('Every metric must have evidence. Missing: '):
        known = ('metric_without_evidence', 'Add matching evidence for every metric key; the list must cover all metrics.')
    if known is None and record['status'] == 'failed':
        hints = {
            'NameError': 'Import the dr_runtime helpers explicitly. There is no implicit tables variable; use connect() or table_path(alias). Check other variable definitions.',
            'BinderException': 'Check prepared column types and SQL signatures. Numeric-looking CSV columns may still be text; validate values and cast explicitly before arithmetic.',
            'ConversionException': 'Check input formats before casting; report invalid values rather than replacing them silently with zero.',
            'SyntaxError': 'Correct the Python syntax and submit the changed program with a new request_key.',
            'ModuleNotFoundError': 'Use libraries available in the isolated sandbox, such as duckdb and pandas; runtime package downloads are not supported.',
        }
        stderr = (record.get('logs') or {}).get('stderr', '')
        names = re.findall(r'(?m)^(?:[a-zA-Z_]\w*\.)?('+'|'.join(hints)+r'):', stderr) if isinstance(stderr,str) else []
        if names:
            known = ('python_'+names[-1].lower(), hints[names[-1]])
    if known is None:
        known = ('calculation_'+record['status'], 'Check the Python program, sandbox API and output contract. The result is unavailable; do not treat missing output as zero.')
    return {'code': known[0], 'message': known[1],
            'retry': 'Identical input and request_key retrieve this execution. Use a new request_key for corrected code or arguments.'}


def page_result(record, cursor=0, *, repeat_tool=None):
    if type(cursor) is not int or cursor < 0:
        raise ValueError('Invalid result cursor.')
    rows = list(_leaves(record.get('result')))
    if cursor > len(rows):
        raise ValueError('Cursor exceeds the result.')
    page = {'execution_id': str(record['id']), 'status': record['status'],
            'verification': 'pending', 'result_sha256': admission.sha(admission.canonical(record.get('result'))),
            'columns': ['path', 'part', 'value'], 'rows': [], 'total_rows': len(rows),
            'truncated': False, 'requested_cursor': cursor, 'cursor': None,
            'next_cursor': None, 'next_call': None}
    problem = diagnostic(record)
    if problem:
        page['diagnostic'] = problem
    for row in rows[cursor:cursor+100]:
        candidate = {**page, 'rows': page['rows'] + [row]}
        # Leave space for MCP/JSON-RPC framing, including escaped string content.
        if len(admission.canonical(candidate)) > 23 * 1024:
            break
        page['rows'].append(row)
    next_cursor = cursor + len(page['rows'])
    more = next_cursor < len(rows)
    page.update(truncated=more, cursor=next_cursor if more else None,
                next_cursor=next_cursor if more else None)
    if more:
        # Recipe inputs can be large. Refer to the preceding call instead of
        # echoing them and consuming the bounded output budget on every page.
        page['next_call'] = ({'name': repeat_tool, 'arguments': {'cursor': next_cursor},
                              'reuse_previous_arguments': True} if repeat_tool else
                             {'name': 'resultado', 'arguments': {
                                 'execution_id': str(record['id']), 'cursor': next_cursor},
                              'reuse_previous_arguments': False})
    return page


def consulta(config, job, token, args, *, backend=None, printed=False):
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
                               timeout=args.get('timeout', 30), request_key=key, backend=backend, result_required=not printed)
    # A tool that finishes after waiting/revocation may retain durable evidence,
    # but cannot send it into the paused/new turn.
    admission.authenticate(config, job['id'], token)
    with connect(config) as db:
        db.execute('''INSERT INTO engine_executions(business_id,run_id,execution_id)
            VALUES (%s,%s,%s) ON CONFLICT DO NOTHING''', (job['business_id'], job['id'], record['id']))
    return exploration.stdout_page(record) if printed else page_result(record)


def salida(config, job, args):
    if set(args) - {"execution_id", "cursor"}: raise ValueError("Unexpected salida arguments.")
    execution_id=UUID(str(args["execution_id"]))
    with connect(config) as db:
        linked=db.execute("SELECT execution_id FROM engine_executions WHERE business_id=%s AND run_id=%s AND execution_id=%s",
                          (job["business_id"],job["id"],execution_id)).fetchone()
    if not linked: raise admission.Denied("Execution is outside this job.")
    return exploration.stdout_page(execution.get_execution(config,job["business_id"],execution_id),args.get("cursor",0))


def resultado(config, job, args):
    if set(args) - {'execution_id', 'cursor'}:
        raise ValueError('Unexpected resultado arguments.')
    execution_id = UUID(str(args['execution_id']))
    with connect(config) as db:
        linked = db.execute('''SELECT execution_id FROM engine_executions
            WHERE business_id=%s AND run_id=%s AND execution_id=%s''',
                            (job['business_id'], job['id'], execution_id)).fetchone()
    if not linked:
        scoped = calculations.observation(config, job['business_id'], job['id'], execution_id)
        if scoped:
            return {**page_result({'id': execution_id, 'status': 'completed', 'result': scoped['body']['result']}, args.get('cursor', 0)),
                    'origin': 'deterministic_calculation', 'table_ids': [scoped['body']['specification']['table_id']]}
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
                value = page_result({'id': row['id'], 'status': 'completed', 'result': row['body']}, args.get('cursor', 0), repeat_tool='verify_numbers')
                value['verification_id'] = value.pop('execution_id')
            elif params.get('name') == 'calculo':
                if set(args) - {'table_id', 'request_key', 'recipes', 'cursor'} or not {'table_id', 'request_key', 'recipes'} <= set(args):
                    raise ValueError('Invalid calculation arguments.')
                row = calculations.calculate(config, run_id, token, **{k: v for k, v in args.items() if k != 'cursor'})
                value = {**page_result({'id': row['id'], 'status': 'completed', 'result': row['body']['result']}, args.get('cursor', 0)),
                         'origin': 'deterministic_calculation', 'table_ids': [args['table_id']]}
            elif params.get('name') == 'panorama_lectura':
                if set(args) - {'table_id','request_key','mapping','cursor'}: raise ValueError('Invalid panorama arguments.')
                row=panorama.calculate(config,run_id,token,**{k:v for k,v in args.items() if k!='cursor'})
                value=exploration.text_page(exploration.panorama_text(row['body']),args.get('cursor',0),
                    tool='panorama_lectura',arguments={k:v for k,v in args.items() if k!='cursor'},
                    identity={'panorama_id':str(row['id']),'origin':'deterministic_panorama','verification':'scoped_calculations_only'})
            elif params.get('name') == 'panorama':
                if set(args) - {'table_id', 'request_key', 'mapping', 'cursor'} or not {'table_id', 'request_key'} <= set(args):
                    raise ValueError('Invalid panorama arguments.')
                row = panorama.calculate(config, run_id, token, **{k: v for k, v in args.items() if k != 'cursor'})
                page = page_result({'id': row['id'], 'status': 'completed', 'result': {'tables': row['body']['tables']}}, args.get('cursor', 0), repeat_tool='panorama')
                page['panorama_id'] = page.pop('execution_id')
                value = {**page, 'origin': 'deterministic_panorama',
                         'observation_ids': [o['execution_id'] for o in row['body']['observations']]}
            elif params.get('name') == 'entregar_informe':
                if set(args) != {'request_key', 'draft_json'} or not isinstance(args['draft_json'], str):
                    raise ValueError('Invalid delivery arguments.')
                value = store.receive_document(config, run_id, token, **args)
                # The immutable raw revision is committed before any parsing.
                value['format'] = format_feedback(args['draft_json'].encode('utf-8'))
            elif params.get('name') == 'explorar':
                value=consulta(config,job,token,args,backend=backend,printed=True)
            elif params.get('name') == 'salida':
                value=salida(config,job,args)
            elif params.get('name') == 'consulta':
                value = consulta(config, job, token, args, backend=backend)
            elif params.get('name') == 'resultado':
                value = resultado(config, job, args)
            else:
                return {**response, 'error': {'code': -32602, 'message': 'Unknown tool.'}}
            result = {'content': [{'type': 'text', 'text': admission.canonical(value).decode()}]}
            if params.get('name') == 'entregar_informe' and not value['format']['valid']:
                result['isError'] = True
        except admission.Denied:
            raise
        except (ValueError, KeyError, TypeError):
            # Execution errors may contain private storage paths; never echo them.
            result = {'isError': True, 'content': [{'type': 'text', 'text': 'Invalid or unsuccessful calculation. Check the arguments. Identical input may reuse its request key; changed code or arguments require a new request key.'}]}
    else:
        return {**response, 'error': {'code': -32601, 'message': 'Method not found.'}}
    encoded = admission.canonical({**response, 'result': result})
    if len(encoded) > 64 * 1024:
        raise ValueError('MCP response exceeds 64 KiB.')
    return {**response, 'result': result}
