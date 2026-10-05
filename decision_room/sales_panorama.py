"""P1a: deterministic descriptive sales overview; no model or business-specific rules."""
import calendar
import re
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, localcontext

import duckdb

from .csv_ingest import identifier

VERSION = 'sales-panorama-v1'
MAX_DAILY_GROUPS = 1_000_000
MAX_DIMENSION_GROUPS = 500
TOP = 5
ROLES = {
    'date': {'date', 'fecha', 'sale_date', 'sales_date', 'fecha_venta', 'day'},
    'product': {'product', 'producto', 'product_id', 'producto_id', 'sku', 'id_producto', 'product_code', 'codigo_producto'},
    'channel': {'channel', 'canal', 'channel_id', 'canal_id', 'id_canal', 'channel_code', 'codigo_canal'},
    'quantity': {'quantity', 'units', 'unidades', 'cantidad', 'qty'},
}


def normalized(value):
    return re.sub(r'[^a-z0-9]+', '_', ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                                            if not unicodedata.combining(c))).strip('_')


def mapping(columns, explicit=None):
    if explicit is not None:
        if not isinstance(explicit, dict) or set(explicit) != set(ROLES) or any(not isinstance(v, str) or len(v) > 500 or v not in columns for v in explicit.values()) or len(set(explicit.values())) != 4:
            raise ValueError('Panorama mapping needs four distinct existing columns: date, product, channel, quantity.')
        return dict(explicit)
    result = {}
    for role, aliases in ROLES.items():
        matches = [c for c in columns if normalized(c) in aliases]
        if len(matches) != 1:
            return None  # Missing or ambiguous meanings must not be guessed.
        result[role] = matches[0]
    return result


def month(day, offset=0):
    index = day.year * 12 + day.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def period_rule(first, last):
    start = month(first) if first.day == 1 else month(first, 1)
    end = last if last.day == calendar.monthrange(last.year, last.month)[1] else month(last) - timedelta(days=1)
    if start > end:
        return {'status': 'unavailable', 'reason': 'No hay un mes natural completo dentro del intervalo observado.'}
    year_start = date(end.year, 1, 1)
    if date(end.year - 1, 1, 1) >= start:
        before_start = date(end.year - 1, 1, 1)
        before_end = date(end.year - 1, end.month, calendar.monthrange(end.year - 1, end.month)[1])
        current_start = year_start
        reason = 'Año en curso hasta el último mes natural completo frente a los mismos meses del año anterior.'
        rule = 'year_to_date_same_months'
    elif month(end, -5) >= start:
        before_start, before_end = month(end, -5), month(end, -2) - timedelta(days=1)
        current_start = month(end, -2)
        reason = 'Últimos tres meses naturales completos frente a los tres inmediatamente anteriores; no ajusta estacionalidad.'
        rule = 'three_months_previous_three'
    elif month(end, -1) >= start:
        before_start, before_end = month(end, -1), month(end) - timedelta(days=1)
        current_start = month(end)
        reason = 'Último mes natural completo frente al anterior por no disponer de dos ventanas de tres meses; no ajusta estacionalidad.'
        rule = 'month_previous_month'
    else:
        return {'status': 'unavailable', 'reason': 'No hay dos periodos naturales comparables dentro del intervalo observado.'}
    return dict(status='available', rule=rule, reason=reason,
                before=[before_start.isoformat(), before_end.isoformat()],
                current=[current_start.isoformat(), end.isoformat()],
                boundary_rule='Se excluyen meses de borde parciales. Estar dentro del intervalo no certifica cobertura completa; febrero puede tener distinta duración.')


def spans(active, start, end):
    """Only interior/trailing absences, never absence before a group first appears."""
    previous = start
    for current in sorted(active) + [end + timedelta(days=1)]:
        if current > previous + timedelta(days=1):
            yield previous + timedelta(days=1), current - timedelta(days=1)
        previous = current


def record_gaps(days, end):
    """Freeze prior cadence at gap start: no lookahead or causal attribution."""
    found = []
    first = min(days)
    for start, stop in spans(days, first, end):
        baseline = start - timedelta(days=56)
        if baseline < first:
            continue
        counts = dict.fromkeys(range(7), 0)
        for offset in range(56):
            observed = baseline + timedelta(days=offset)
            if observed in days:
                counts[observed.weekday()] += 1
        expected = [w for w, count in counts.items() if count >= 6]
        missed = sum((start + timedelta(days=i)).weekday() in expected for i in range((stop-start).days+1))
        if missed >= 3:
            found.append(dict(start=start.isoformat(), end=stop.isoformat(), cadence='weekday',
                baseline=[baseline.isoformat(), (start-timedelta(days=1)).isoformat()],
                expected_weekdays=[('lunes','martes','miércoles','jueves','viernes','sábado','domingo')[w] for w in expected], habitual_active_days=sum(counts.values()),
                absent_expected_days=missed, calendar_days=(stop-start).days+1))
    # Sparse but recurring monthly groups can also disappear; exclude partial months.
    full_end = month(end) if end.day == calendar.monthrange(end.year, end.month)[1] else month(end, -1)
    months = {month(d) for d in days}
    cursor = month(min(days), 6)
    while cursor <= full_end:
        if cursor in months:
            cursor = month(cursor, 1)
            continue
        prior = [month(cursor, -n) for n in range(1, 7)]
        if sum(m in months for m in prior) < 4:
            cursor = month(cursor, 1)
            continue
        stop = cursor
        while month(stop, 1) <= full_end and month(stop, 1) not in months:
            stop = month(stop, 1)
        last = month(stop, 1) - timedelta(days=1)
        if not any(date.fromisoformat(g['start']) <= last and date.fromisoformat(g['end']) >= cursor for g in found):
            found.append(dict(start=cursor.isoformat(), end=last.isoformat(), cadence='month',
                baseline=[prior[-1].isoformat(), (cursor-timedelta(days=1)).isoformat()],
                habitual_active_months=sum(m in months for m in prior),
                absent_months=(stop.year-cursor.year)*12+stop.month-cursor.month+1,
                calendar_days=(last-cursor).days+1))
        cursor = month(stop, 1)
    return found


def calculate(path, columns, explicit=None):
    try:
        return _calculate(path, columns, explicit)
    except (duckdb.OutOfMemoryException, duckdb.OutOfRangeException):
        return dict(version=VERSION, status='unavailable', reason='El cálculo excede los límites de memoria o precisión del panorama. No se presenta un resultado parcial como total.')


def _calculate(path, columns, explicit=None):
    selected = mapping(columns, explicit)
    if not selected:
        return dict(version=VERSION, status='unavailable', reason='No se identifican sin ambigüedad fecha, producto, canal y cantidad. Se requiere mapeo explícito; no se suman importes de base desconocida.')
    d, p, c, q = [identifier(selected[k]) for k in ROLES]
    with duckdb.connect(config={'threads': 2, 'memory_limit': '512MB', 'max_temp_directory_size': '0B'}) as db:
        db.read_parquet(str(path)).create_view('source')
        db.execute(f'''CREATE TEMP VIEW parsed AS SELECT
            CASE WHEN regexp_full_match(trim({d}), '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') THEN TRY_CAST(trim({d}) AS DATE) END AS day,
            {p} AS product, {c} AS channel,
            CASE WHEN regexp_full_match(trim({q}), '[+-]?[0-9]+([.][0-9]{{1,8}})?') THEN TRY_CAST(trim({q}) AS DECIMAL(38,8)) END AS quantity
            FROM source''')
        total, invalid = db.execute("SELECT count(*),count(*) FILTER (WHERE day IS NULL OR day < DATE '0002-01-01' OR day > DATE '9998-12-31' OR quantity IS NULL OR product IS NULL OR trim(product)='' OR length(product)>500 OR channel IS NULL OR trim(channel)='' OR length(channel)>500) FROM parsed").fetchone()
        if not total or invalid:
            return dict(version=VERSION, status='unavailable', mapping=selected, row_count=total, invalid_rows=invalid,
                        reason='Se requieren fechas ISO entre los años 2 y 9998, dimensiones presentes de hasta 500 caracteres y cantidades decimales válidas (hasta 8 decimales). No se descartan ni convierten silenciosamente filas.')
        # Quantity is a column sum, not a claim of monetary revenue or tickets.
        rows = db.execute(f'SELECT day,product,channel,sum(quantity),count(*) FROM parsed GROUP BY ALL ORDER BY day,product,channel LIMIT {MAX_DAILY_GROUPS+1}').fetchall()
        if len(rows) > MAX_DAILY_GROUPS:
            return dict(version=VERSION, status='unavailable', mapping=selected, reason='El panorama supera 1.000.000 de grupos diarios; requiere agregación explícita. No se usa una muestra.')
    with localcontext() as ctx:
        ctx.prec = 80
        return summarize(rows, selected, total)


def summarize(rows, selected, row_count):
    first, last = min(r[0] for r in rows), max(r[0] for r in rows)
    comparison = period_rule(first, last)
    metrics, evidence = {}, []

    def metric(key, value, operation):
        metrics[key] = str(value)
        evidence.append(dict(metric=key, tables=['source'], operation=operation))
        return {'metric': key}  # Store binds this to an immutable observation ID.

    quantity = 'SUM(' + identifier(selected['quantity']) + ') sobre todas las filas incluidas, sin deduplicar ni imputar ceros.'
    summary = dict(version=VERSION, status='available', mapping=selected,
        measure={'column': selected['quantity'], 'definition': quantity, 'unit': 'cantidad registrada',
                 'semantic_status': 'header_mapping_not_owner_confirmation'},
        period=[first.isoformat(), last.isoformat()], comparison=comparison,
        row_count=metric('rows', row_count, 'COUNT(*) del archivo completo.'),
        total=metric('total', sum(r[3] for r in rows), quantity),
        gap_rule='Días: un día de semana con filas en al menos 6 de las 8 semanas anteriores, y al menos 3 días esperados ausentes en un tramo. Meses: actividad en al menos 4 de los 6 meses previos y ausencia durante al menos un mes completo. Solo después de aparecer el grupo; sin concluir cierre, fallo de extracción o ventas cero.',
        limitations=['Se describen registros del archivo, sin certificar cobertura ni causas.',
                     'Las tablas se calculan por separado; no se suman archivos que podrían solaparse.',
                     'La suma de cantidades no es facturación, beneficio ni número de tickets. Confirmar su significado frente al contexto del dueño.'],
        totals={}, changes={}, gaps=[])
    if comparison['status'] == 'available':
        before = tuple(date.fromisoformat(x) for x in comparison['before'])
        current = tuple(date.fromisoformat(x) for x in comparison['current'])
        # Whole missing months are reported as coverage, never made comparable by zeros.
        observed_months = {month(r[0]) for r in rows}
        required = set()
        for start, stop in (before, current):
            cursor = start
            while cursor <= stop:
                required.add(cursor); cursor = month(cursor, 1)
        if required - observed_months:
            comparison.update(status='unavailable', reason='La ventana elegida contiene meses sin ninguna fila; no se interpreta su ausencia como cero.', missing_months=sorted(m.isoformat()[:7] for m in required-observed_months))
        else:
            for name, bounds in [('before', before), ('current', current)]:
                comparison[name+'_total'] = metric('period_'+name, sum(r[3] for r in rows if bounds[0] <= r[0] <= bounds[1]), quantity + ' Periodo ' + str(comparison[name]))
            a, b = Decimal(metrics['period_before']), Decimal(metrics['period_current'])
            comparison['change'] = metric('period_change', b-a, 'period_current - period_before, mismas columnas y tabla.')
            comparison['before_days'] = metric('before_days', (before[1]-before[0]).days+1, 'Días naturales inclusivos del periodo anterior.')
            comparison['current_days'] = metric('current_days', (current[1]-current[0]).days+1, 'Días naturales inclusivos del periodo actual.')
    for dimension, indexes in [('channel', (2,)), ('product', (1,)), ('product_channel', (1,2))]:
        groups = defaultdict(list)
        for row in rows:
            groups[tuple(row[i] for i in indexes)].append(row)
        if len(groups) > MAX_DIMENSION_GROUPS:
            summary['limitations'].append(f'{dimension}: {len(groups)} grupos superan el límite de 500 del panorama; sección no calculada, sin seleccionar una muestra.')
            continue
        totals, changes, gaps = [], [], []
        for index, (group, items) in enumerate(sorted(groups.items())):
            key = f'{dimension}_{index}'
            label = dict(zip(['product','channel'] if len(indexes)==2 else [dimension], group))
            filt = ' Filtro exacto ' + repr(label) + '.'
            if dimension != 'product_channel':
                totals.append({**label, 'value': metric(key+'_total', sum(r[3] for r in items), quantity+filt)})
            if comparison['status'] == 'available' and dimension != 'product':
                earlier = [r for r in items if before[0] <= r[0] <= before[1]]
                later = [r for r in items if current[0] <= r[0] <= current[1]]
                # No rows is not a numeric zero. Preserve incomparable groups explicitly.
                changes.append({**label, '_key': key, '_filter': filt,
                    '_before': sum(r[3] for r in earlier) if earlier else None,
                    '_current': sum(r[3] for r in later) if later else None})
            if dimension != 'product':
                for gap in record_gaps({r[0] for r in items}, last):
                    gaps.append({**label, **gap, '_filter': filt})
        if totals:
            summary['totals'][dimension] = totals
        if changes:
            comparable = [v for v in changes if v['_before'] is not None and v['_current'] is not None]
            def delta(v): return v['_current']-v['_before']
            ordered = sorted(comparable, key=lambda v:(delta(v), v['_key']))
            selected_changes = [('decreases', [v for v in ordered if delta(v)<0][:TOP]),
                                ('increases', sorted([v for v in ordered if delta(v)>0], key=lambda v:(-delta(v),v['_key']))[:TOP]),
                                ('missing_window', [v for v in changes if v not in comparable][:TOP])]
            section = {'rule': 'Hasta cinco por signo, ordenados por cambio absoluto de cantidad; no es prioridad de negocio. Grupos sin filas en una ventana no reciben un delta.',
                       'group_count': metric(dimension+'_groups',len(changes),'COUNT de grupos distintos en todo el archivo.'),
                       'incomparable_count': metric(dimension+'_incomparable',len(changes)-len(comparable),'Grupos sin filas en al menos una ventana.')}
            for category, values in selected_changes:
                section[category] = []
                for value in values:
                    item = {k:v for k,v in value.items() if not k.startswith('_')}
                    for window in ('before','current'):
                        amount = value['_'+window]
                        item[window] = None if amount is None else metric(value['_key']+'_'+window, amount, quantity+value['_filter']+' Periodo '+str(comparison[window]))
                    if value in comparable:
                        item['change'] = metric(value['_key']+'_change',delta(value),'Cantidad actual menos anterior.'+value['_filter']+' Ventanas '+repr([comparison['before'],comparison['current']]))
                    section[category].append(item)
            summary['changes'][dimension] = section
        if gaps:
            summary[dimension+'_gap_count'] = metric(dimension+'_gaps',len(gaps),'Número de tramos detectados según gap_rule en todos los grupos de esta dimensión.')
            for index, gap in enumerate(sorted(gaps, key=lambda g:(-g['calendar_days'], g['start'], g.get('product',''),g['channel']))[:10]):
                item = {k:v for k,v in gap.items() if not k.startswith('_')}
                for field in ('calendar_days','habitual_active_days','absent_expected_days','habitual_active_months','absent_months'):
                    if field in item:
                        item[field] = metric(f'{dimension}_gap_{index}_{field}',item[field],f'{field}: regla {gap["cadence"]}; tramo {gap["start"]} a {gap["end"]}; base {gap["baseline"]}.'+gap['_filter'])
                item['rows_in_gap'] = metric(f'{dimension}_gap_{index}_rows',0,'COUNT(*) en tramo inclusivo '+gap['start']+' a '+gap['end']+gap['_filter'])
                summary['gaps'].append(item)
    summary['gap_selection'] = 'Hasta diez tramos por dimensión, ordenados por duración; el recuento conserva todos los detectados.'
    return {'version': VERSION, 'status': 'available', 'summary': summary, 'result': {'metrics': metrics, 'evidence': evidence, 'notes': [], 'series': {}}}
