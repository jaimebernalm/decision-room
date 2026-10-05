"""Frozen overview projection; no model prose or guessed catalog labels."""
from copy import deepcopy
from hashlib import sha256
import json
import re

from .series import evidence_value
from .owner_presentation import readable_number


def signals(panorama, *, changes=False):
    result = []
    for table in (panorama or {}).get('tables', []):
        if table.get('status') != 'available':
            continue
        entries = [('gap', item) for item in table.get('gaps', [])]
        if changes:
            entries += [('change', item) for section in table.get('changes', {}).values()
                        for kind in ('increases', 'decreases') for item in section.get(kind, [])]
        for kind, item in entries:
            ref = item['rows_in_gap' if kind == 'gap' else 'change']
            key = kind + '_' + sha256(json.dumps(ref, sort_keys=True).encode()).hexdigest()[:16]
            result.append(dict(key=key, kind=kind, table_id=table['table_id'], **deepcopy(item)))
    return result


def refs(panorama):
    def walk(value):
        if isinstance(value, dict):
            if set(value) == {'execution_id', 'metric'}:
                yield value
            else:
                for child in value.values(): yield from walk(child)
        elif isinstance(value, list):
            for child in value: yield from walk(child)
    return list({(r['execution_id'], r['metric']): r for r in walk(panorama or {})}.values())


def compact(panorama, observations):
    """Keep mandatory signals and refs; do not repeat operation descriptions/code."""
    result = dict(version='panorama-contract-v2', tables=[], signals=signals(panorama, changes=True),
                  instruction='Panorama rendered by controller; address every gap, justify priorities against its evidence. Missing rows are not zero sales.')
    def with_values(value):
        if isinstance(value, dict):
            if set(value) == {'execution_id', 'metric'}:
                return dict(reference=value, value=evidence_value(observations, value))
            return {k: with_values(v) for k, v in value.items()}
        if isinstance(value, list): return [with_values(v) for v in value]
        return value
    for table in (panorama or {}).get('tables', []):
        if table.get('status') != 'available':
            result['tables'].append({k:table[k] for k in ('table_id','names','status','reason') if k in table})
            continue
        result['tables'].append(with_values({k:table[k] for k in ('table_id','names','period','comparison','total')}) |
                                {'measure': {k:table['measure'][k] for k in ('column','unit','semantic_status')}, 'channels': with_values(table.get('totals', {}).get('channel', [])),
                                 'gap_rule': table['gap_rule'], 'gap_selection':table['gap_selection']})
    result['signals'] = with_values(result['signals'])
    result['catalog_labels'] = [{k:label[k] for k in ('code','name')} for label in (panorama or {}).get('catalog_labels', [])]
    return result


def day(value):
    from datetime import date
    parsed = date.fromisoformat(value)
    months = ('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre').split()
    return f'{parsed.day} de {months[parsed.month-1]} de {parsed.year}'


def owner_sections(panorama, observations):
    labels = {item['code']:item['name'] for item in (panorama or {}).get('catalog_labels', [])}
    def name(raw, dimension):
        if raw in labels: return labels[raw]
        # Opaque codes without a verified catalog are not passed off as names.
        if re.fullmatch(r'(?:[A-Z]{1,5}[0-9]*|[0-9]+)', raw):
            return 'Canal sin nombre verificado' if dimension == 'channel' else 'Producto sin nombre verificado'
        return raw
    def group(item):
        return ' / '.join(name(item[k], k) for k in ('product','channel') if k in item)
    def amount(ref): return str(readable_number(evidence_value(observations, ref)))
    result = []
    for table in (panorama or {}).get('tables', []):
        if table.get('status') != 'available': continue
        period = 'Del ' + day(table['period'][0]) + ' al ' + day(table['period'][1])
        channel_totals = [f"{group(item)}: {amount(item['value'])}" for item in table.get('totals', {}).get('channel', [])]
        lines = [f"{period}: {amount(table['total'])} de cantidad registrada."]
        if channel_totals: lines.append('Por canal: ' + '; '.join(channel_totals) + '.')
        comparison = table['comparison']
        if comparison['status'] == 'available':
            rules = {'three_months_previous_three':'Comparamos los últimos tres meses completos con los tres anteriores para ver el cambio reciente.',
                     'year_to_date_same_months':'Comparamos el año hasta el último mes completo con los mismos meses del año anterior para respetar la temporada.'}
            rule = rules.get(comparison.get('rule'), 'Comparamos el último mes completo con el anterior porque no hay dos periodos completos de tres meses; no ajusta la temporada.')
            lines.append(rule + f" Del {day(comparison['before'][0])} al {day(comparison['before'][1])}: {amount(comparison['before_total'])}; del {day(comparison['current'][0])} al {day(comparison['current'][1])}: {amount(comparison['current_total'])}. Cambio: {amount(comparison['change'])}.")
        else:
            lines.append('No hay un periodo anterior comparable con registros suficientes.')
        for dimension in ('channel', 'product_channel'):
            section = table.get('changes', {}).get(dimension, {})
            for kind, heading in (('increases','Mayor aumento'),('decreases','Mayor descenso')):
                if section.get(kind):
                    item = section[kind][0]
                    lines.append(f"{heading}: {group(item)}, {amount(item['change'])} de cantidad registrada.")
        alerts = list(dict.fromkeys(f"{group(item)}: sin registros del {day(item['start'])} al {day(item['end'])}." for item in table.get('gaps', [])))
        result.append(dict(source=', '.join(table['names']), lines=lines, alerts=alerts,
                           note='Los huecos indican ausencia de registros, no ventas cero ni una causa confirmada.' if alerts else ''))
    return result


def render_html(sections):
    from html import escape
    if not sections: return ''
    body = '<section class="panorama" aria-label="Panorama"><h2>Panorama</h2>'
    for section in sections:
        if len(sections)>1: body += '<h3>' + escape(section['source']) + '</h3>'
        body += ''.join('<p>'+escape(line)+'</p>' for line in section['lines'])
        if section['alerts']: body += '<ul>' + ''.join('<li>'+escape(a)+'</li>' for a in section['alerts']) + '</ul>'
        if section['note']: body += '<p>'+escape(section['note'])+'</p>'
    return body + '</section>'
