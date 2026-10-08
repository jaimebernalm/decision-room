"""Bounded views of retained exploration output; never numerical certification."""
import json

from . import admission
from ..panorama_presentation import compact


def text_page(text, cursor, *, tool, arguments, identity):
    if type(cursor) is not int or not 0 <= cursor <= len(text):
        raise ValueError('Invalid text cursor.')
    # Bound encoded bytes too: Unicode and JSON escaping are not character counts.
    stop = min(len(text), cursor + 12000)
    while len(admission.canonical({'text': text[cursor:stop], **identity})) > 18000:
        stop = cursor + (stop-cursor)//2
    more = stop < len(text)
    return {**identity, 'text': text[cursor:stop], 'text_sha256': admission.sha(text.encode()),
            'requested_cursor': cursor, 'next_cursor': stop if more else None,
            'total_characters': len(text), 'truncated': more,
            'cursor_unit': 'Unicode characters in retained text',
            'next_call': {'name':tool, 'arguments':{**arguments,'cursor':stop},
                          'reuse_previous_arguments':False} if more else None}


def stdout_page(record, cursor=0):
    logs = record.get('logs') or {}
    stdout = logs.get('stdout', '')
    if not isinstance(stdout,str): raise ValueError('Invalid retained stdout.')
    return text_page(stdout,cursor,tool='salida',arguments={'execution_id':str(record['id'])},
        identity={'execution_id':str(record['id']), 'status':record['status'],
                  'verification':'unverified', 'origin':'agent_exploration',
                  'retention_truncated':bool(logs.get('stdout_truncated')),
                  'note':'Salida impresa por código del agente. No certifica valores ni cobertura; si retention_truncated=true, lo omitido no es recuperable por paginación.'})


def panorama_text(body):
    """Keep all compact signals and scopes, resolving references without hiding IDs.

    Compact is an existing deterministic projection; no model selection of signals.
    Stable ref labels avoid repeated UUIDs in the readable body.
    """
    projected = compact({'tables':body['tables']},body['observations'])
    references = {}
    def replace(value):
        if isinstance(value,dict) and set(value)=={'reference','value'}:
            ref=value['reference']; key=(ref['execution_id'],ref['metric'])
            if key not in references: references[key]='R'+str(len(references)+1)
            return {'valor':value['value'],'referencia':references[key]}
        if isinstance(value,dict): return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list): return [replace(v) for v in value]
        return value
    def readable(value, depth=0):
        labels={'period':'Periodo','comparison':'Comparación','total':'Total','channels':'Canales',
                'product':'Producto','channel':'Canal','start':'Inicio','end':'Fin',
                'rows_in_gap':'Filas en el hueco','absent_expected_days':'Días esperados ausentes',
                'before':'Anterior','current':'Actual','change':'Cambio','materiality':'Ámbito y regla de selección'}
        if isinstance(value,dict) and set(value)=={'valor','referencia'}:
            return str(value['valor'])+' ['+value['referencia']+']'
        if isinstance(value,dict):
            return '\n'.join('  '*depth+'- '+labels.get(k,k)+': '+readable(v,depth+1) for k,v in value.items())
        if isinstance(value,list):
            if any(isinstance(v,(dict,list)) for v in value):
                return '\n'+'\n'.join(readable(v,depth+1) for v in value)
            return ', '.join(json.dumps(v,ensure_ascii=False) for v in value)
        return json.dumps(value,ensure_ascii=False)
    lines=['# Panorama de registros',
           'Cálculos deterministas con ámbito limitado. Los huecos no prueban ventas cero ni causas. Los códigos no son nombres de catálogo comprobados.']
    for table in projected['tables']:
        lines += ['## Tabla y periodos',readable(replace(table))]
    for signal in projected['signals']:
        lines += ['## '+('Hueco de registros' if signal['kind']=='gap' else 'Cambio entre periodos'),
                  readable(replace(signal))]
    lines += ['## Referencias para numbers / facts']
    for (execution_id,metric),key in references.items():
        lines.append(json.dumps({'referencia':key,'execution_id':execution_id,'metric':metric},ensure_ascii=False))
    lines.append('Este resumen conserva las señales de la proyección compacta. Para totales detallados, rankings completos y ratios usa panorama; no presupongas que el resumen sustituye toda la tabla.')
    return '\n\n'.join(lines)
