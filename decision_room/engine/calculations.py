"""Bounded, server-owned scalar aggregations over one immutable prepared table.

No agent code, SQL, joins, inferred units or inferred business meaning. The visible
scope states exact filters and null handling; final verification reads Parquet
again rather than trusting the saved scalar. Arbitrary consulta stays unverified.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
import re
import threading
import time
from uuid import UUID, uuid4

import duckdb
from psycopg.types.json import Jsonb

from ..database import connect
from ..storage import Storage, digest
from . import admission

VERSION = 'engine-scoped-aggregates-v2'
MAX_ROWS = 200_000
MAX_FILE_BYTES = 128 * 1024 * 1024
SECONDS = 30
OPERATIONS = {'count', 'sum', 'mean', 'min', 'max'}


def identity():
    return {'version': VERSION, 'code_sha256': admission.sha(Path(__file__).read_bytes()), 'duckdb': duckdb.__version__}


def validate(recipes, columns):
    if not isinstance(recipes, list) or not 1 <= len(recipes) <= 32:
        raise ValueError('Provide 1–32 scalar recipes.')
    keys = set()
    for recipe in recipes:
        if not isinstance(recipe, dict) or set(recipe) != {'key', 'operation', 'column', 'filters'}:
            raise ValueError('Each recipe requires key, operation, column and filters.')
        if len(admission.canonical(recipe)) > 4096:
            raise ValueError('Each recipe must fit in 4 KiB.')
        key, operation, column, filters = (recipe[k] for k in ('key', 'operation', 'column', 'filters'))
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', key) or key in keys:
            raise ValueError('Metric keys must be distinct ASCII identifiers of at most 80 characters.')
        keys.add(key)
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError('Unsupported aggregate.')
        if (operation == 'count' and column is not None) or (operation != 'count' and column not in columns):
            raise ValueError('Count requires column=null; other aggregates need an existing column.')
        if not isinstance(filters, list) or len(filters) > 8:
            raise ValueError('At most eight AND filters per recipe.')
        for condition in filters:
            if not isinstance(condition, dict) or set(condition) != {'column', 'operator', 'values'} or condition['column'] not in columns:
                raise ValueError('Each filter needs an existing column, operator and values.')
            values = condition['values']; operator = condition['operator']
            if not isinstance(values, list) or not 1 <= len(values) <= 16 or any(not isinstance(v, str) or len(v) > 500 for v in values):
                raise ValueError('Filter values must be 1–16 strings of at most 500 characters.')
            if operator == 'in':
                if len(set(values)) != len(values): raise ValueError('Duplicate filter values.')
            elif operator == 'date_between':
                if len(values) != 2: raise ValueError('Date filter requires two inclusive ISO dates.')
                parsed = [date.fromisoformat(v) for v in values]
                if any(v.isoformat() != text for v, text in zip(parsed, values)) or parsed[0] > parsed[1]:
                    raise ValueError('Date interval must be ordered canonical ISO dates.')
            else:
                raise ValueError('Filters support in and date_between only.')


def _calendar_date(value):
    """Validate the entire naive ISO timestamp before selecting its calendar day.

    No prefix slicing, locale guessing or timezone conversion. Aware timestamps
    need an explicit business timezone contract and remain unsupported.
    """
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value).isoformat()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?', value):
        raise ValueError('Date or naive ISO timestamp required.')
    return datetime.fromisoformat(value).date().isoformat()


def _amount(value):
    if value is None:
        return None
    if len(str(value)) > 80:
        raise ValueError('Numeric field exceeds the supported text bound.')
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number.adjusted() > 25 or number.as_tuple().exponent < -12:
            raise ValueError('Numeric field exceeds supported finite precision.')
        return number
    except InvalidOperation:
        raise ValueError('Selected field contains a non-numeric value.') from None


def _text(number):
    value = format(number, '.12f').rstrip('0').rstrip('.')
    return value if value not in ('', '-0') else '0'


def evaluate(path, columns, recipes, source_label="tabla preparada"):
    """Bound both input size and wall time; never certify a truncated selection."""
    validate(recipes, columns)
    if len(source_label.encode()) > 2048:
        raise ValueError('Source labels exceed the visible scope bound.')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Prepared table exceeds the calculation byte bound.')
    selected = sorted({r['column'] for r in recipes if r['column'] is not None} |
                      {f['column'] for r in recipes for f in r['filters']})
    positions = {column: index for index, column in enumerate(selected)}
    fields = ','.join('CAST("'+c.replace('"', '""')+'" AS VARCHAR)' for c in selected) or '1'
    aggregates = {r['key']: {'rows': 0, 'valid': 0, 'total': Decimal(0), 'min': None, 'max': None, 'issue': None} for r in recipes}
    deadline = time.monotonic() + SECONDS
    with duckdb.connect(config={'threads': 1, 'memory_limit': '128MB'}) as db, localcontext() as ctx:
        ctx.prec = 80
        timer = threading.Timer(SECONDS, db.interrupt); timer.daemon = True; timer.start()
        try:
            cursor = db.execute(f'SELECT {fields} FROM read_parquet(?) LIMIT {MAX_ROWS+1}', [str(path)])
            total = 0
            while chunk := cursor.fetchmany(1024):
                total += len(chunk)
                if total > MAX_ROWS or time.monotonic() > deadline:
                    raise ValueError('Calculation exceeds row or time bound; no truncated result is returned.')
                for row in chunk:
                    for recipe in recipes:
                        state = aggregates[recipe['key']]
                        accepted = True
                        for condition in recipe['filters']:
                            actual = row[positions[condition['column']]]
                            if actual is None:
                                accepted = False; continue
                            if condition['operator'] == 'in':
                                accepted = accepted and actual in condition['values']
                            else:
                                try:
                                    day = _calendar_date(actual)
                                    accepted = accepted and condition['values'][0] <= day <= condition['values'][1]
                                except ValueError:
                                    # A malformed date may belong in the range. Never silently drop it.
                                    state['issue'] = 'date_value_not_canonical_iso'; accepted = False
                        if not accepted: continue
                        state['rows'] += 1
                        if recipe['operation'] == 'count': continue
                        try:
                            number = _amount(row[positions[recipe['column']]])
                        except ValueError:
                            state['issue'] = 'selected_value_not_supported_numeric'; continue
                        if number is None: continue
                        state['valid'] += 1; state['total'] += number
                        state['min'] = number if state['min'] is None else min(state['min'], number)
                        state['max'] = number if state['max'] is None else max(state['max'], number)
            metrics, displays, issues = {}, {}, {}
            names = {'count':'Filas seleccionadas', 'sum':'Suma registrada', 'mean':'Media por registro no nulo', 'min':'Mínimo registrado', 'max':'Máximo registrado'}
            for recipe in recipes:
                key, operation = recipe['key'], recipe['operation']; state = aggregates[key]
                issue = state['issue']
                if operation != 'count' and not state['valid']:
                    issue = issue or 'no_non_null_values'
                value = None
                if not issue:
                    if operation == 'count': value = str(state['rows'])
                    elif operation == 'mean': value = _text(state['total']/state['valid'])
                    else: value = _text(state['total'] if operation == 'sum' else state[operation])
                metrics[key] = value; issues[key] = issue
                scope = 'Fuente «'+source_label+'» del snapshot. '
                if recipe['column'] is not None: scope += 'Columna «'+recipe['column']+'». '
                for condition in recipe['filters']:
                    scope += '«'+condition['column']+'» '+('en {'+', '.join('«'+v+'»' for v in condition['values'])+'}' if condition['operator']=='in'
                        else 'entre '+condition['values'][0]+' y '+condition['values'][1]+' inclusive')+'. '
                if any(f['operator'] == 'date_between' for f in recipe['filters']):
                    scope += 'Fecha de calendario: fechas ISO o timestamps ISO sin zona, validados completos; hora descartada tras validar, sin conversión de zona. '
                if not recipe['filters']: scope += 'Todas las filas. '
                scope += 'Filtros unidos por Y; nulos del filtro excluidos. Sin deduplicar, unir tablas ni imputar ausencias.'
                displays[key] = {'label': names[operation], 'scope': scope,
                    'unit': 'filas' if operation=='count' else 'valor de la columna',
                    'limitation': 'No certifica unidad de negocio, causalidad, cobertura ni prioridad. '+
                        ('Cuenta filas, no ventas ausentes.' if operation=='count' else 'Nulos numéricos excluidos; no se sustituyen por cero.'),
                    'operands': [] if operation == 'count' else [{'label': 'Filas seleccionadas', 'value': str(state['rows']), 'unit':'filas'}]}
                if operation != 'count':
                    displays[key]['operands'].append({'label':'Registros no nulos usados', 'value':str(state['valid']), 'unit':'registros'})
                if operation == 'mean' and value is not None:
                    displays[key]['operands'].append({'label':'Suma (numerador)', 'value':_text(state['total']), 'unit':'valor de la columna'})
            return {'metrics': metrics, 'displays': displays, 'issues': issues}
        finally:
            timer.cancel(); timer.join()


def _source(config, job, table_id):
    expected = next((t for t in job['snapshot'] if t['id'] == str(table_id)), None)
    if expected is None: raise admission.Denied('Calculation table is outside this job.')
    with connect(config) as db:
        table = db.execute('''SELECT t.parquet_key,t.parquet_sha256,t.columns,s.original_names FROM prepared_tables t JOIN sources s ON s.id=t.source_id
            WHERE t.business_id=%s AND t.analysis_id=%s AND t.id=%s''',
            (job['business_id'], job['analysis_id'], table_id)).fetchone()
    if not table or table['parquet_sha256'] != expected['parquet_sha256']:
        raise ValueError('Calculation snapshot changed.')
    path = Storage(config.storage).path(job['business_id'], table['parquet_key'])
    if digest(path) != expected['parquet_sha256']: raise ValueError('Calculation snapshot bytes changed.')
    return path, [c['name'] for c in table['columns']], expected['parquet_sha256'], ' / '.join(sorted(table['original_names']))


def _checked(row):
    if row and admission.sha(admission.canonical(row['body'])) != row['body_sha256']:
        raise ValueError('Calculation observation failed its integrity check.')
    return row


def calculate(config, run_id, token, *, table_id, request_key, recipes):
    job = admission.authenticate(config, run_id, token); table_id = str(UUID(str(table_id)))
    path, columns, parquet_hash, label = _source(config, job, table_id); validate(recipes, columns)
    if not isinstance(request_key, str) or not 1 <= len(request_key) <= 128:
        raise ValueError('Invalid calculation key.')
    spec = {'identity': identity(), 'table_id': table_id, 'parquet_sha256': parquet_hash, 'recipes': recipes, 'source_label': label}
    fingerprint = admission.sha(admission.canonical(spec))
    lock = int.from_bytes(bytes.fromhex(admission.sha(admission.canonical(['calculation', str(run_id), request_key])))[:8], 'big', signed=True)
    with connect(config) as db, db.transaction():
        db.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
        prior = db.execute('SELECT * FROM engine_calculations WHERE run_id=%s AND request_key=%s', (run_id, request_key)).fetchone()
        if prior:
            if prior['request_sha256'] != fingerprint: raise ValueError('Calculation key already used with different input.')
            return _checked(prior)
        result = evaluate(path, columns, recipes, label)
        admission.authenticate(config, run_id, token)
        locked = admission._locked(db, run_id, token); error = admission._active(db, locked)
        if not error:
            body = {'specification': spec, 'result': result}
            row = db.execute('''INSERT INTO engine_calculations(id,business_id,run_id,request_key,request_sha256,body,body_sha256)
                VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (uuid4(), job['business_id'], run_id, request_key, fingerprint, Jsonb(body), admission.sha(admission.canonical(body)))).fetchone()
            admission._event(db, run_id, 'calculation_frozen', {'observation_id': str(row['id'])})
    if error: raise admission.Aborted(error)
    return row


def observation(config, business, run_id, observation_id):
    with connect(config) as db:
        return _checked(db.execute('SELECT * FROM engine_calculations WHERE business_id=%s AND run_id=%s AND id=%s',
                                   (business, run_id, observation_id)).fetchone())


def verify(config, job, row, metric, cache):
    body = row['body']; spec = body['specification']
    if spec['identity'] != identity(): return None
    path, columns, expected, label = _source(config, job, spec['table_id'])
    if spec['parquet_sha256'] != expected or spec['source_label'] != label: return None
    key = admission.sha(admission.canonical(spec))
    if key not in cache:
        actual = evaluate(path, columns, spec['recipes'], label)
        if digest(path) != expected: raise ValueError('Calculation snapshot changed during verification.')
        cache[key] = actual
    result = cache[key]; value = result['metrics'].get(metric)
    if value is None: return None
    if result['displays'].get(metric) != body['result']['displays'].get(metric): return None
    original = body['result']['metrics'].get(metric)
    return {'value': value, 'original_value': original,
            'status': 'verified_in_scope' if original == value else 'corrected_in_scope',
            'origin':'deterministic_calculation', 'reason':'server_recipe_recalculated',
            'display':result['displays'][metric], 'scope':spec}
