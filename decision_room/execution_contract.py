"""Validate bounded, untrusted results without importing or executing them."""
import base64
import json
import math
import re

from .docker_backend import LIMITS


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key.')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('Non-finite JSON number.')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, RecursionError, OverflowError, json.JSONDecodeError) as error:
        raise ValueError('Malformed JSON output.') from error


def validate_result(raw, tables):
    result = strict_json(raw)
    if not isinstance(result, dict) or set(result) != {'schema_version', 'metrics', 'evidence', 'notes'} or type(result['schema_version']) is not int or result['schema_version'] != 1:
        raise ValueError('Invalid result schema.')
    metrics, evidence, notes = result['metrics'], result['evidence'], result['notes']
    if not isinstance(metrics, dict) or not 1 <= len(metrics) <= 256:
        raise ValueError('Provide between 1 and 256 metrics.')
    for key, value in metrics.items():
        if not isinstance(key, str) or not 1 <= len(key) <= 100 or type(value) not in (str, int, float, bool, type(None)):
            raise ValueError('Metrics must contain named scalar values.')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Metric is not finite.')
        if isinstance(value, str) and len(value) > 1000:
            raise ValueError('Metric text too long.')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 512:
        raise ValueError('Missing or excessive evidence.')
    covered = set()
    for item in evidence:
        if not isinstance(item, dict) or not {'metric', 'tables', 'operation'} <= set(item) or set(item) - {'metric', 'tables', 'operation', 'source_records'}:
            raise ValueError('Invalid evidence schema.')
        if not isinstance(item['metric'], str) or item['metric'] not in metrics:
            raise ValueError('Evidence refers to an unknown metric.')
        aliases = item['tables']
        if not isinstance(aliases, list) or not aliases or any(not isinstance(a, str) or a not in tables for a in aliases):
            raise ValueError('Evidence refers to an unauthorized table.')
        if not isinstance(item['operation'], str) or not 1 <= len(item['operation']) <= 16000:
            raise ValueError('Evidence must describe the operation, including filters.')
        records = item.get('source_records', {})
        if not isinstance(records, dict):
            raise ValueError('Invalid source record references.')
        for alias, ids in records.items():
            if alias not in aliases or not isinstance(ids, list) or len(ids) > 1000 or any(type(i) is not int or not 1 <= i <= tables[alias]['row_count'] for i in ids):
                raise ValueError('Source record outside the authorized table.')
        covered.add(item['metric'])
    if covered != set(metrics):
        raise ValueError('Every metric must have evidence.')
    if not isinstance(notes, list) or len(notes) > 100 or any(not isinstance(n, str) or len(n) > 4000 for n in notes):
        raise ValueError('Invalid notes.')
    return {'verification': 'pending', **result}


def validate_payload(raw, tables):
    payload = strict_json(raw)
    if not isinstance(payload, dict) or set(payload) != {'protocol', 'status', 'exit_code', 'logs', 'files'} or payload['protocol'] != 1:
        raise ValueError('Invalid worker protocol.')
    status = payload['status']
    if not isinstance(status, str) or status not in {'completed', 'failed', 'timed_out', 'invalid_output'}:
        raise ValueError('Invalid worker state.')
    if payload['exit_code'] is not None and type(payload['exit_code']) is not int:
        raise ValueError('Invalid exit code.')
    if status == 'completed' and payload['exit_code'] != 0:
        raise ValueError('Completed computation has a nonzero exit code.')
    logs = payload['logs']
    if not isinstance(logs, dict) or set(logs) != {'stdout', 'stderr', 'stdout_truncated', 'stderr_truncated'}:
        raise ValueError('Invalid log schema.')
    for key in ('stdout', 'stderr'):
        if not isinstance(logs[key], str) or len(logs[key].encode('utf-8')) > 3 * LIMITS['log_bytes'] + 1024 or type(logs[key + '_truncated']) is not bool:
            raise ValueError('Invalid or excessive logs.')
        logs[key] = logs[key][:LIMITS['log_bytes']]
    if not isinstance(payload['files'], list) or len(payload['files']) > LIMITS['artifact_count']:
        raise ValueError('Too many artifacts.')
    files, total = {}, 0
    for item in payload['files']:
        if not isinstance(item, dict) or set(item) != {'name', 'base64'}:
            raise ValueError('Invalid artifact schema.')
        name = item['name']
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,95}\.(json|csv|png|parquet)', name) or name in files:
            raise ValueError('Invalid or duplicate artifact filename.')
        if not isinstance(item['base64'], str) or len(item['base64']) > (LIMITS['file_bytes'] + 2) // 3 * 4:
            raise ValueError('Artifact too large.')
        try:
            content = base64.b64decode(item['base64'], validate=True)
        except (ValueError, UnicodeError) as error:
            raise ValueError('Invalid artifact encoding.') from error
        total += len(content)
        if len(content) > LIMITS['file_bytes'] or total > LIMITS['artifact_bytes']:
            raise ValueError('Artifact size limit exceeded.')
        if name.endswith('.png') and not content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid PNG signature.')
        if name.endswith('.parquet') and not (len(content) >= 12 and content.startswith(b'PAR1') and content.endswith(b'PAR1')):
            raise ValueError('Invalid Parquet signature.')
        files[name] = content
    result = None
    if status == 'completed':
        if 'result.json' not in files:
            raise ValueError('Missing result.json.')
        result = validate_result(files['result.json'], tables)
    return status, logs, files, result
