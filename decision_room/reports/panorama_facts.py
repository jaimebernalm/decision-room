"""Visible scopes generated solely from a freshly recalculated panorama.

These captions certify a recorded-data quantity in its stated scope, not a cause,
owner-confirmed unit, completeness of extraction, or an adjacent recommendation.
"""


def describe(summary, metric, metrics=None):
    def matches(ref): return isinstance(ref, dict) and ref.get('metric') == metric
    column = summary['mapping']['quantity']
    period = summary['period']
    comparison = summary['comparison']
    def dates(bounds): return bounds[0] + ' — ' + bounds[1]
    def group(item):
        return '; '.join(('Producto' if k == 'product' else 'Canal') + ' «' + item[k] + '»'
                         for k in ('product', 'channel') if k in item)
    def result(label, scope, unit='cantidad registrada'):
        return {'label': label, 'scope': scope, 'unit': unit,
                'limitation': 'Describe registros del archivo; no certifica cobertura, causas ni prioridad de la acción.'}
    base = 'Fechas: ' + dates(period) + '. Columna sumada: «' + column + '», sin deduplicar ni imputar ausencias.'
    if matches(summary.get('total')):
        return result('Cantidad registrada total', base)
    if matches(summary.get('row_count')):
        return result('Filas del archivo', 'Archivo completo. Fechas observadas: ' + dates(period) + '.', 'filas')
    if comparison.get('status') == 'available':
        for window, word in (('before','anterior'), ('current','actual')):
            if matches(comparison.get(window+'_total')):
                return result('Cantidad registrada del periodo '+word,
                              'Fechas: '+dates(comparison[window])+'. Columna sumada: «'+column+'».')
            if matches(comparison.get(window+'_days')):
                return result('Duración del periodo '+word, 'Fechas inclusivas: '+dates(comparison[window])+'.', 'días naturales')
        both = 'Actual: '+dates(comparison['current'])+'; anterior: '+dates(comparison['before'])+'.'
        if matches(comparison.get('change')):
            return result('Diferencia de cantidad registrada', both+' Actual menos anterior; columna «'+column+'».')
    else:
        both = ''
    for dimension, rows in summary.get('totals', {}).items():
        for item in rows:
            if matches(item.get('value')):
                return result('Cantidad registrada del grupo', group(item)+'. '+base)
    for dimension, section in summary.get('changes', {}).items():
        label = {'channel':'canal','product':'producto','product_channel':'producto y canal'}[dimension]
        if matches(section.get('group_count')):
            return result('Grupos distintos por '+label, 'Archivo completo; incluye grupos sin filas en alguna ventana.', 'grupos')
        if matches(section.get('incomparable_count')):
            return result('Grupos sin registros en alguna ventana', 'Agrupación por '+label+'. '+both+' La ausencia no es cero ventas.', 'grupos')
        for category in ('increases', 'decreases', 'missing_window'):
            for item in section.get(category, []):
                for window, word in (('before','anterior'), ('current','actual')):
                    if matches(item.get(window)):
                        return result('Cantidad registrada del grupo en el periodo '+word,
                                      group(item)+'. Fechas: '+dates(comparison[window])+'. Columna sumada: «'+column+'».')
                if matches(item.get('change')):
                    return result('Diferencia de cantidad registrada del grupo', group(item)+'. '+both+
                                  ' Actual menos anterior; columna «'+column+'».')
    gap_fields = {'rows_in_gap': ('Filas en el tramo sin registros','filas'),
                  'calendar_days': ('Duración del tramo sin registros','días naturales'),
                  'habitual_active_days': ('Días con registros en la base previa','días'),
                  'absent_expected_days': ('Días habituales sin registros en el tramo','días'),
                  'habitual_active_months': ('Meses con registros en la base previa','meses'),
                  'absent_months': ('Meses sin registros en el tramo','meses')}
    for item in summary.get('gaps', []):
        for field, (label, unit) in gap_fields.items():
            if matches(item.get(field)):
                scope = group(item)+'. Tramo: '+dates([item['start'],item['end']])+'. Base previa: '+dates(item['baseline'])+'. '
                scope += summary['gap_rule']+' La ausencia de registros no prueba ventas cero ni un cierre.'
                return result(label, scope, unit)
    for dimension in ('channel','product_channel'):
        if matches(summary.get(dimension+'_gap_count')):
            return result('Tramos sin registros detectados', 'Agrupación por '+('canal' if dimension=='channel' else 'producto y canal')+'. '+summary['gap_rule'], 'tramos')
    for item in summary.get('ratios', []):
        if matches(item.get('value')) and metrics is not None:
            change = item['kind'] == 'change'
            display = result('Variación porcentual de cantidad registrada' if change else 'Porcentaje de cantidad registrada sobre el total',
                item['scope'] + (' Fórmula: actual menos anterior, dividido entre anterior y expresado en porcentaje.' if change
                                  else ' Fórmula: parte dividida entre total, expresada en porcentaje.'), '%')
            display['operands'] = [
                {'label': 'Actual' if change else 'Parte', 'value': metrics[item['left']['metric']], 'unit': 'cantidad registrada'},
                {'label': 'Anterior (base)' if change else 'Total (base)', 'value': metrics[item['right']['metric']], 'unit': 'cantidad registrada'}]
            return display
    return None
