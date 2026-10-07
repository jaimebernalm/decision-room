"""Engine-only percentage recipes; never alter the frozen legacy calculator.

Operands are selected by server rules on the same panorama/table/mapping. Zero or
negative bases are unavailable, not a fabricated percentage. Changes retain the
original calendar windows; they are not daily or seasonally adjusted rates.
"""
from copy import deepcopy
from decimal import localcontext
from hashlib import sha256
from pathlib import Path

from ..series import numeric

VERSION = 'engine-panorama-ratios-v1'


def identity():
    return {'version': VERSION, 'code_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}


def extend(body):
    body = deepcopy(body)
    if body['status'] != 'available':
        return body
    summary, result = body['summary'], body['result']
    ratios = []
    def add(kind, left, right, scope):
        a, b = numeric(result['metrics'][left]), numeric(result['metrics'][right])
        key = left + ('_change_pct' if kind == 'change' else '_share_pct')
        item = {'kind': kind, 'left': {'metric': left}, 'right': {'metric': right},
                'scope': scope, 'value': None, 'reason': None}
        if b <= 0:
            item['reason'] = 'La base es cero o negativa; no se publica un porcentaje.'
        elif kind == 'share' and (a < 0 or a > b):
            item['reason'] = 'La parte queda fuera del total positivo; no se interpreta como cuota.'
        else:
            with localcontext() as ctx:
                ctx.prec = 48
                value = (a-b)*100/b if kind == 'change' else a*100/b
                text = format(value, '.12f').rstrip('0').rstrip('.')
            result['metrics'][key] = text
            formula = f'({left} - {right}) / {right} * 100' if kind == 'change' else f'{left} / {right} * 100'
            result['evidence'].append({'metric': key, 'tables': ['source'],
                'operation': formula + '. Same frozen table and mapping. ' + scope})
            item['value'] = {'metric': key}
        ratios.append(item)
    comparison = summary['comparison']
    column = summary['mapping']['quantity']
    quantity = ' Columna «'+column+'»; suma de registros sin deduplicar ni imputar ausencias.'
    if comparison['status'] == 'available':
        scope = ('Actual: '+' — '.join(comparison['current'])+'; anterior: '+' — '.join(comparison['before'])+'.'+quantity+
                 ' No ajusta distinta duración, estacionalidad ni cobertura.')
        add('change', comparison['current_total']['metric'], comparison['before_total']['metric'], scope)
        for section in summary['changes'].values():
            for category in ('increases', 'decreases'):
                for item in section[category]:
                    group = '; '.join(('Producto' if k=='product' else 'Canal')+' «'+item[k]+'»' for k in ('product','channel') if k in item)
                    add('change', item['current']['metric'], item['before']['metric'], group+'. '+scope)
    for dimension, rows in summary['totals'].items():
        for item in rows:
            scope = ('Producto' if dimension=='product' else 'Canal')+' «'+item[dimension]+'». '
            scope += 'Parte y total del archivo, fechas: '+' — '.join(summary['period'])+'.'+quantity
            add('share', item['value']['metric'], summary['total']['metric'], scope)
    summary['ratios'] = ratios
    return body
