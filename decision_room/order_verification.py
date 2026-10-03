"""Metamorphic check of computed evidence, independent of business/column names.

Physical row order is not a business definition. Preserve every column (including
explicit sequence/lineage columns) and rerun in the same isolated backend. This
bounded counterexample test detects order dependence; it is not a proof over all
permutations or of analytical correctness.
"""
import hashlib
import json
import shutil
from decimal import Decimal, InvalidOperation

import duckdb

from .execution_contract import validate_payload
from .storage import digest


def signature(result):
    def number(value):
        if isinstance(value, bool) or value is None:
            return value
        try:
            n = Decimal(str(value))
            if n.is_finite():
                if not n:
                    return ['number', 0, '0', 0]
                sign, digits, exponent = n.as_tuple()
                digits = list(digits)
                while digits[-1] == 0:
                    digits.pop()
                    exponent += 1
                # Canonical exact value without expanding enormous exponents.
                return ['number', sign, ''.join(map(str, digits)), exponent]
        except (InvalidOperation, ValueError):
            pass
        return value
    series = {}
    for key, value in result.get('series', {}).items():
        series[key] = {'unit': value['unit'], 'grain': value['grain'],
                       'points': sorted([(p['label'], number(p['value'])) for p in value['points']])}
    evidence = {'metrics': {k: number(v) for k, v in result['metrics'].items()}, 'series': series}
    return hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def reverse_inputs(stage, target_stage=None):
    """Copy the same typed rows in reverse physical order; never rewrite sources."""
    hashes = {}
    target_stage = target_stage or stage
    with duckdb.connect(config={'threads': 1, 'memory_limit': '128MB',
                               'temp_directory': str(target_stage / 'order-sort'),
                               'max_temp_directory_size': '512MB'}) as db:
        for source in sorted((stage / 'tables').glob('*.parquet')):
            columns = [c[0] for c in db.execute('SELECT * FROM read_parquet(?) LIMIT 0', [str(source)]).description]
            name = '__dr_order_check'
            while name in columns:
                name += '_'
            target = target_stage / 'tables' / (source.stem + '.reordered')
            db.execute(f'COPY (SELECT * EXCLUDE ("{name}") FROM '
                       f'(SELECT *, row_number() OVER () AS "{name}" FROM read_parquet($source)) '
                       f'ORDER BY "{name}" DESC) TO $target (FORMAT PARQUET)', {'source': str(source), 'target': str(target)})
            hashes[source.stem] = digest(target)
            destination = target_stage / 'tables' / source.name
            target.replace(destination)
            destination.chmod(0o444)
    return hashes


def verify(backend, execution_id, stage, timeout, inputs, original):
    details = {'policy': 'reverse-physical-rows-v1', 'status': 'unverified',
               'original_result_sha256': signature(original), 'program_runs': 2}
    # A fresh directory also avoids stale file handles in VM shared mounts.
    checked_stage = stage / 'order-check'
    checked_stage.mkdir(mode=0o755)
    (checked_stage / 'tables').mkdir(mode=0o755)
    details['input_sha256'] = reverse_inputs(stage, checked_stage)
    shutil.copyfile(stage / 'program.py', checked_stage / 'program.py')
    request = json.loads((stage / 'request.json').read_text())
    for alias, value in details['input_sha256'].items():
        request['tables'][alias]['parquet_sha256'] = value
    (checked_stage / 'request.json').write_text(json.dumps(request))
    for name in ('program.py', 'request.json'):
        (checked_stage / name).chmod(0o444)
    outcome = backend.run(execution_id, checked_stage, timeout)
    details['runtime'] = outcome['runtime']
    if outcome['forced_status']:
        details.update(status='unavailable', forced_status=outcome['forced_status'])
        return details, 'row_order_unverified: reordered execution stopped by resource control; no candidate accepted.'
    try:
        status, logs, files, result = validate_payload(outcome['payload'], inputs)
    except ValueError as error:
        details['status'] = 'unavailable'
        return details, 'row_order_unverified: reordered output invalid: ' + str(error)
    if status != 'completed':
        details.update(status='unavailable', logs=logs)
        return details, 'row_order_unverified: reordered program did not complete; no candidate accepted.'
    details['reordered_result_sha256'] = signature(result)
    if details['original_result_sha256'] != details['reordered_result_sha256']:
        details['status'] = 'different'
        for field in ('metrics', 'series'):
            before, after = original.get(field, {}), result.get(field, {})
            def item_signature(source, key):
                return signature({'metrics': {}, field: {key: source[key]} if key in source else {}})
            details['changed_' + field] = [key for key in sorted(set(before) | set(after))
                                          if item_signature(before, key) != item_signature(after, key)]
        return details, ('row_order_dependent: computed metrics or saved series change when the same rows are reordered. '
                         'Use order-independent aggregates (e.g. min/max for bounds), or explicitly sort by a meaningful '
                         'date/sequence column before order-sensitive operations. Physical file order is not evidence.')
    details['status'] = 'passed'
    return details, None
