"""Resolve job evidence and recalculate supported server-owned numerical scopes.

Only the deterministic panorama has a server-owned recipe in this first slice.
Arbitrary Python results remain traced/unverified even if they are numeric.
These checks do not certify how a writer attributes a figure in prose, units
confirmed by the owner, causality, business priorities or completeness of data.
"""
from pathlib import Path
from uuid import UUID, uuid4

import duckdb
from psycopg.types.json import Jsonb

from .. import execution, sales_panorama
from ..database import connect
from ..series import numeric
from ..reports import panorama_facts
from ..storage import Storage, digest
from . import admission, panorama

VERSION = 'engine-number-checks-v2'


def _references(numbers):
    if not isinstance(numbers, list) or not 1 <= len(numbers) <= 32:
        raise ValueError('Check 1–32 numerical references per request.')
    keys = set()
    for ref in numbers:
        if not isinstance(ref, dict) or set(ref) != {'key', 'execution_id', 'metric'}:
            raise ValueError('Provide key, execution_id and metric for every reference.')
        if any(not isinstance(ref[k], str) or not 1 <= len(ref[k]) <= 100 for k in ('key', 'metric')) or ref['key'] in keys:
            raise ValueError('Reference keys must be nonempty and unique.')
        UUID(str(ref['execution_id']))
        keys.add(ref['key'])


def _candidate(config, job, ref):
    frozen = panorama.observation(config, job['business_id'], job['id'], ref['execution_id'])
    if frozen:
        return frozen, 'deterministic_panorama'
    with connect(config) as db:
        linked = db.execute('SELECT execution_id FROM engine_executions WHERE business_id=%s AND run_id=%s AND execution_id=%s',
                            (job['business_id'], job['id'], ref['execution_id'])).fetchone()
    if not linked:
        return None, 'unavailable'
    row = execution.get_execution(config, job['business_id'], ref['execution_id'])
    expected = {t['id']: t['parquet_sha256'] for t in job['snapshot']}
    if (str(row['analysis_id']) != str(job['analysis_id']) or row['status'] != 'completed'
            or any(t['id'] not in expected or expected[t['id']] != t['parquet_sha256'] for t in row['inputs'].values())):
        return None, 'unavailable'
    return row, 'agent_calculation'


def _recalculate(config, job, frozen, cache):
    spec = frozen['specification']
    current_hash = admission.sha(Path(sales_panorama.__file__).read_bytes())
    if (spec['code_sha256'] != current_hash or spec['version'] != sales_panorama.VERSION
            or spec['engine_version'] != duckdb.__version__):
        return None
    table_id = spec['table_id']
    expected = next((t['parquet_sha256'] for t in job['snapshot'] if t['id'] == table_id), None)
    if expected is None or spec['parquet_sha256'] != expected:
        return None
    key = admission.sha(admission.canonical(spec))
    if key not in cache:
        with connect(config) as db:
            table = db.execute('''SELECT parquet_key,parquet_sha256,columns FROM prepared_tables
                WHERE business_id=%s AND analysis_id=%s AND id=%s''',
                (job['business_id'], job['analysis_id'], table_id)).fetchone()
        if not table or table['parquet_sha256'] != expected:
            return None
        path = Storage(config.storage).path(job['business_id'], table['parquet_key'])
        if digest(path) != expected:
            return None
        # Deliberately bypass sales_panorama_store's cached body: recompute from
        # the immutable Parquet with the server recipe and exact column mapping.
        result = sales_panorama.calculate(path, [c['name'] for c in table['columns']], spec.get('mapping'))
        if digest(path) != expected:
            return None
        cache[key] = result
    return cache[key]


def _check(config, job, ref, cache):
    result = {**ref, 'status': 'unavailable', 'value': None, 'original_value': None,
              'reason': 'reference_unavailable', 'scope': None}
    candidate, origin = _candidate(config, job, ref)
    if not candidate or candidate['status'] != 'completed':
        return result
    value = (candidate.get('result') or {}).get('metrics', {}).get(ref['metric'])
    try:
        numeric(value)
    except ValueError:
        return {**result, 'reason': 'metric_missing_or_non_numeric'}
    result.update(value=str(value), original_value=str(value), origin=origin,
                  status='unverified', reason='no_server_recipe')
    if origin != 'deterministic_panorama':
        return result
    actual = _recalculate(config, job, candidate, cache)
    if not actual or actual['status'] != 'available':
        return {**result, 'reason': 'recipe_unavailable'}
    expected = actual['result']['metrics'].get(ref['metric'])
    operation = [e for e in actual['result']['evidence'] if e['metric'] == ref['metric']]
    previous = [e for e in candidate['result']['evidence'] if e['metric'] == ref['metric']]
    if operation != previous or len(operation) != 1:
        return {**result, 'reason': 'scope_mismatch'}
    try:
        changed = numeric(expected) != numeric(value)
    except ValueError:
        return {**result, 'reason': 'recipe_value_unavailable'}
    summary = actual['summary']
    return {**result, 'status': 'corrected_in_scope' if changed else 'verified_in_scope',
            'value': str(expected), 'reason': 'server_recipe_recalculated',
            'display': panorama_facts.describe(summary, ref['metric']),
            'scope': {'table_id': candidate['specification']['table_id'],
                      'parquet_sha256': candidate['specification']['parquet_sha256'],
                      'code_sha256': candidate['specification']['code_sha256'],
                      'mapping': summary['mapping'], 'period': summary['period'],
                      'comparison': summary['comparison'], 'operation': operation[0]['operation'],
                      'semantic_status': 'prose_attribution_and_owner_units_not_checked'}}


def verify(config, run_id, token, *, request_key, numbers):
    _references(numbers)
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid verification request key.')
    job = admission.authenticate(config, run_id, token)
    fingerprint = admission.sha(admission.canonical([VERSION, admission.sha(Path(__file__).read_bytes()),
        admission.sha(Path(sales_panorama.__file__).read_bytes()), admission.sha(Path(panorama_facts.__file__).read_bytes()),
        duckdb.__version__, job['snapshot_sha256'], numbers]))
    with connect(config) as db:
        previous = db.execute('SELECT * FROM engine_number_checks WHERE run_id=%s AND request_key=%s',
                              (run_id, request_key)).fetchone()
    if previous:
        return _checked(previous, fingerprint)
    cache = {}
    body = {'version': VERSION, 'checks': [_check(config, job, ref, cache) for ref in numbers],
            'limitations': ['Numerical scope checks do not verify the prose, owner-confirmed units, causes or priorities.',
                            'Agent-authored calculations have no independent server recipe in this version.']}
    admission.authenticate(config, run_id, token)
    with connect(config) as db, db.transaction():
        run = admission._locked(db, run_id, token)
        error = admission._active(db, run)
        if not error:
            previous = db.execute('SELECT * FROM engine_number_checks WHERE run_id=%s AND request_key=%s',
                                  (run_id, request_key)).fetchone()
            if previous:
                return _checked(previous, fingerprint)
            row = db.execute('''INSERT INTO engine_number_checks
                (id,business_id,run_id,request_key,request_sha256,body,body_sha256)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (uuid4(), job['business_id'], run_id, request_key, fingerprint,
                 Jsonb(body), admission.sha(admission.canonical(body)))).fetchone()
            admission._event(db, run_id, 'numbers_checked', {'verification_id': str(row['id'])})
    if error:
        raise admission.Aborted(error)
    return row


def _checked(row, fingerprint):
    if row['request_sha256'] != fingerprint:
        raise ValueError('Verification key already used with different references.')
    if admission.sha(admission.canonical(row['body'])) != row['body_sha256']:
        raise ValueError('Verification ledger failed its integrity check.')
    return row
