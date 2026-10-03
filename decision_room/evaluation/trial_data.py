"""Deterministic multi-year synthetic business with planted, documented signals.

python -m decision_room.evaluation.trial_data albor OUTPUT [--seed N]
python -m decision_room.evaluation.trial_data bruma SOURCE OUTPUT

Writes OUTPUT/datos/*.csv and OUTPUT/prompt.txt for the agents, and
OUTPUT/oracle.json for evaluators only. For Bruma, SOURCE is a folder with the
frozen datos/ and prompt.txt; their hashes are checked against the published ones. The oracle is computed from the written
CSV rows, never from the generator's expected values, and must never be placed
next to the agents' inputs. Albor Café is fictitious; all values are synthetic.
"""
import argparse
import csv
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
import math
from pathlib import Path
import random

START = date(2021, 9, 1)
END = date(2026, 8, 31)
SEED = 20261003
PREFIX = 'Albor-Cafe-datos-'

CHANNELS = [
    ('TI', 'Tienda física', 'Zaragoza'),
    ('WE', 'Web propia', 'España peninsular'),
    ('MA', 'Marketplace', 'España peninsular'),
    ('HO', 'Hostelería', 'Zaragoza y alrededores'),
]
# Annual growth by channel; the store is deliberately flat.
GROWTH = {'TI': 0.0, 'WE': 0.18, 'MA': 0.28, 'HO': 0.05}
# Monday..Sunday multipliers. Hostelería orders arrive on Monday and Thursday.
WEEKDAY = {
    'TI': (0.85, 0.9, 0.95, 1.0, 1.15, 1.45, 0.7),
    'WE': (1.15, 1.1, 1.05, 1.0, 0.95, 0.85, 0.9),
    'MA': (1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 0.95),
    'HO': (3.5, 0.0, 0.0, 3.5, 0.0, 0.0, 0.0),
}

# id, name, category, daily base units, channel weights TI/WE/MA/HO, unit price, launch
PRODUCTS = [
    ('P01', 'Café de la casa 250 g', 'Café en grano', 9.0, (1.0, 0.7, 0.9, 0.0), 8.5, None),
    ('P02', 'Café de la casa 1 kg', 'Café en grano', 3.0, (0.3, 0.4, 0.5, 2.2), 28.0, None),
    ('P03', 'Etiopía Yirgacheffe 250 g', 'Café en grano', 3.5, (0.8, 0.9, 0.7, 0.0), 13.5, None),
    ('P04', 'Colombia Huila 250 g', 'Café en grano', 4.0, (0.9, 0.8, 0.8, 0.0), 12.0, None),
    ('P05', 'Brasil Cerrado 1 kg', 'Café en grano', 2.0, (0.2, 0.3, 0.4, 2.0), 24.0, None),
    ('P06', 'Guatemala Antigua 250 g', 'Café en grano', 2.5, (0.8, 0.7, 0.6, 0.0), 12.5, None),
    ('P07', 'Kenia AA 250 g', 'Café en grano', 1.5, (0.7, 0.9, 0.5, 0.0), 15.0, None),
    ('P08', 'Espresso Albor 1 kg', 'Café en grano', 2.5, (0.2, 0.3, 0.3, 2.5), 26.0, None),
    ('P09', 'Café molido filtro 250 g', 'Café molido', 5.0, (1.0, 0.6, 0.9, 0.0), 8.0, None),
    ('P10', 'Café molido espresso 250 g', 'Café molido', 4.5, (0.9, 0.6, 1.0, 0.0), 8.0, None),
    ('P11', 'Descafeinado 250 g', 'Café molido', 2.5, (0.9, 0.7, 0.8, 0.0), 8.5, None),
    ('P12', 'Descafeinado 1 kg', 'Café molido', 1.8, (0.4, 0.6, 0.8, 1.0), 27.0, None),
    ('P13', 'Cápsulas compatibles x10', 'Café molido', 6.0, (0.5, 0.9, 1.4, 0.0), 3.9, None),
    ('P14', 'Monodosis ESE x20', 'Café molido', 1.5, (0.3, 0.5, 0.8, 0.6), 7.5, None),
    ('P15', 'Cold brew en botella 330 ml', 'Café frío', 3.0, (1.2, 0.5, 0.7, 0.4), 3.5, None),
    ('P16', 'Concentrado cold brew 1 l', 'Café frío', 1.2, (0.6, 0.8, 0.9, 0.5), 11.0, None),
    ('P17', 'Filtros de papel V60 x100', 'Accesorios', 3.0, (0.8, 0.9, 1.1, 0.0), 6.0, None),
    ('P18', 'Cafetera V60', 'Accesorios', 0.8, (0.8, 1.0, 1.0, 0.0), 24.0, None),
    ('P19', 'Prensa francesa 600 ml', 'Accesorios', 0.7, (0.7, 0.9, 1.1, 0.0), 29.0, None),
    ('P20', 'Molinillo manual', 'Accesorios', 0.6, (0.8, 1.0, 1.0, 0.0), 45.0, None),
    ('P21', 'Molinillo eléctrico compacto', 'Accesorios', 0.6, (0.6, 1.0, 1.0, 0.0), 69.0, None),
    ('P22', 'Báscula con temporizador', 'Accesorios', 0.4, (0.6, 1.0, 1.0, 0.0), 35.0, None),
    ('P23', 'Taza de cerámica Albor', 'Accesorios', 1.0, (1.4, 0.6, 0.5, 0.0), 12.0, None),
    ('P24', 'Hervidor cuello de cisne', 'Accesorios', 0.4, (0.5, 1.0, 1.1, 0.0), 49.0, None),
    ('P25', 'Kit de iniciación V60', 'Kits y regalo', 0.8, (0.9, 1.0, 0.9, 0.0), 39.0, None),
    ('P26', 'Caja regalo degustación', 'Kits y regalo', 0.6, (1.0, 1.0, 0.7, 0.0), 32.0, None),
    ('P27', 'Suscripción mensual de café', 'Kits y regalo', 1.2, (0.0, 1.5, 0.0, 0.0), 22.0, date(2023, 3, 1)),
    ('P28', 'Té verde sencha 100 g', 'Té y otros', 1.2, (0.9, 0.7, 0.8, 0.2), 7.0, None),
    ('P29', 'Chai especiado 100 g', 'Té y otros', 0.9, (0.9, 0.7, 0.8, 0.2), 7.5, None),
    ('P30', 'Cacao a la taza 500 g', 'Té y otros', 1.0, (1.0, 0.6, 0.6, 0.6), 9.0, None),
]

STORE_SUNDAY_BREAK = date(2026, 6, 7)          # S1
HO_LOSS = ('P02', date(2026, 4, 1))            # S2
WEB_BREAKOUT = ('P21', date(2026, 6, 15), 2.6)  # S3
MARKETPLACE_GAP = (date(2026, 3, 10), date(2026, 3, 18))  # S4, inclusive
EROSION = ('P12', date(2025, 3, 1), 0.975)     # S5, monthly factor
COLD = 'Café frío'                             # S6, seasonal decoy

OWNER_FIRST = ('Mi negocio es Albor Café, una tostadora y tienda de café de especialidad en Zaragoza. '
               'Vendemos en tienda física, web propia, marketplace y a hostelería. Los CSV están en la carpeta '
               'datos y son datos sintéticos. «Unidades» es la cantidad registrada por fecha, producto y canal. '
               'No sé si los importes son por unidad o por fila, así que no uses importes, márgenes ni retorno '
               'de marketing. Tampoco tengo información adicional sobre apertura, disponibilidad, cobertura '
               'completa o causas externas, y no quiero predicciones.')
# Paragraphs 2-5 are byte-identical to the Bruma round-2 prompt.
OWNER_REST = '''Quiero saber cómo evolucionan las unidades durante el periodo disponible y qué productos y canales conviene revisar primero. Hazme un informe que me ayude a decidir qué revisar y qué comprobar después, usando estos datos.

Incluye gráficos en el informe; elige los que mejor ayuden a entender los resultados. Guarda el informe con sus gráficos en informe.html, listo para abrir localmente en un navegador.

Profundiza en las señales relevantes: busca qué combinaciones de producto, canal y fechas las explican y cuánto contribuyen. Haz las comprobaciones que permiten los CSV antes de proponerlas como tarea pendiente. Elige pocas prioridades y explica qué decisión justifica revisarlas antes que una alternativa relevante. Para cada prioridad, indica qué comprobar después y cómo cambiaría la reacción según el resultado. Si falta información, nombra la fuente o registro concreto que haría falta y mantén la conclusión parcial, sin inventar causas.

Comprueba que todas las cifras de la prosa, tablas y gráficos proceden de tus cálculos y coinciden en periodo, segmento, unidad y denominador. Verifica también que los gráficos representen las magnitudes correctas, tengan etiquetas legibles y se abran correctamente. Añade interacción para consultar valores exactos cuando ayude a leerlos. Presenta primero las conclusiones. Calcula con los archivos y muestra solo los resúmenes necesarios, sin imprimir todos los CSV.
'''
PROMPT = OWNER_FIRST + '\n\n' + OWNER_REST


def days():
    day = START
    while day <= END:
        yield day
        day += timedelta(days=1)


def months_between(a, b):
    return (b.year - a.year) * 12 + b.month - a.month


def season(category, day):
    angle = 2 * math.pi * (day.timetuple().tm_yday - 15) / 365.25
    winter = math.cos(angle)  # +1 mid-January, -1 mid-July
    if category == COLD:
        return {6: 3.0, 7: 3.2, 8: 2.9, 5: 1.5, 9: 1.4}.get(day.month, 0.6)
    if category in ('Café en grano', 'Café molido'):
        return 1 + 0.15 * winter
    if category == 'Té y otros':
        return 1 + 0.3 * winter
    if category == 'Accesorios':
        return {12: 1.8, 11: 1.15}.get(day.month, 1.0)
    return {12: 2.5, 11: 1.3}.get(day.month, 1.0)  # Kits y regalo


def expected(product, channel_index, day):
    pid, _name, category, base, weights, _price, launch = product
    channel = CHANNELS[channel_index][0]
    if launch and day < launch:
        return 0.0
    value = base * weights[channel_index]
    value *= (1 + GROWTH[channel]) ** ((day - START).days / 365.25)
    value *= season(category, day) * WEEKDAY[channel][day.weekday()]
    if launch:
        value *= min(1.0, 0.25 + months_between(launch, day) / 12)
    if channel == 'TI' and day >= STORE_SUNDAY_BREAK and day.weekday() == 6:
        value *= 0.06
    if (pid, channel) == (HO_LOSS[0], 'HO') and day >= HO_LOSS[1]:
        value = 0.0
    if (pid, channel) == (WEB_BREAKOUT[0], 'WE') and day >= WEB_BREAKOUT[1]:
        value *= WEB_BREAKOUT[2]
    if pid == EROSION[0] and day >= EROSION[1]:
        value *= EROSION[2] ** months_between(EROSION[1], day)
    return value


def poisson(rng, mean):
    if mean <= 0:
        return 0
    if mean > 40:
        return max(0, round(rng.gauss(mean, math.sqrt(mean))))
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def generate(seed=SEED):
    """Return activity rows; rows with zero units are absent, as in many exports."""
    rng = random.Random(seed)
    prices = {p[0]: p[5] for p in PRODUCTS}
    rows = []
    for day in days():
        for index, (channel, _, _) in enumerate(CHANNELS):
            if channel == 'MA' and MARKETPLACE_GAP[0] <= day <= MARKETPLACE_GAP[1]:
                continue
            for product in PRODUCTS:
                units = poisson(rng, expected(product, index, day))
                if not units:
                    continue
                price = prices[product[0]]
                gross = round(units * price, 2)
                discount = round(gross * rng.choice((0, 0, 0, 0.05, 0.1)), 2)
                rows.append((day, channel, product[0], units, gross, discount, round(gross - discount, 2)))
    return rows


def write_csv(path, header, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


def marketing(seed):
    rng = random.Random(seed + 1)
    month, rows = START, []
    while month <= END:
        for channel, base in (('TI', 150), ('WE', 400), ('MA', 500), ('HO', 80)):
            rows.append((month.isoformat() + ' 00:00:00', channel, round(base * rng.uniform(0.7, 1.4))))
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return rows


def read_activity(folder, prefix=PREFIX):
    rows = []
    with (folder / f'{prefix}000.csv').open(encoding='utf-8-sig') as handle:
        for record in csv.DictReader(handle):
            rows.append((date.fromisoformat(record['fecha'][:10]), record['canal_id'],
                         record['producto_id'], int(record['unidades'])))
    return rows


def window_sum(rows, start, end, keep=lambda r: True):
    return sum(r[3] for r in rows if start <= r[0] <= end and keep(r))


def oracle(folder):
    """Facts recomputed from the written CSV rows. Evaluators only."""
    rows = read_activity(folder)
    names = {p[0]: p[1] for p in PRODUCTS}
    summer, last_summer = (date(2026, 6, 1), date(2026, 8, 31)), (date(2025, 6, 1), date(2025, 8, 31))
    spring = (date(2026, 3, 1), date(2026, 5, 31))
    store = lambda r: r[1] == 'TI'
    sunday = lambda r: r[1] == 'TI' and r[0].weekday() == 6

    by_day = defaultdict(int)
    for r in rows:
        if sunday(r):
            by_day[r[0]] += r[3]
    # Absent rows mean zero recorded units on that Sunday, so walk every Sunday.
    sundays = [d for d in days() if d.weekday() == 6]
    earlier = sorted(by_day[d] for d in sundays if date(2026, 3, 1) <= d < date(2026, 6, 1))
    median = earlier[len(earlier) // 2]
    break_day = min(d for d in sundays if d >= date(2026, 6, 1) and by_day[d] < 0.2 * median)
    store_now, store_before = window_sum(rows, *summer, store), window_sum(rows, *last_summer, store)
    sunday_now, sunday_before = window_sum(rows, *summer, sunday), window_sum(rows, *last_summer, sunday)

    ho = lambda r: r[1] == 'HO' and r[2] == HO_LOSS[0]
    ho_months = defaultdict(int)
    for r in rows:
        if ho(r) and r[0] >= date(2025, 9, 1):
            ho_months[r[0].strftime('%Y-%m')] += r[3]
    ho_last = max(r[0] for r in rows if ho(r))

    web = lambda r: r[1] == 'WE' and r[2] == WEB_BREAKOUT[0]
    after = (WEB_BREAKOUT[1], END)
    before = (date(2026, 3, 1), WEB_BREAKOUT[1] - timedelta(days=1))
    rate = lambda span, keep: window_sum(rows, *span, keep) / ((span[1] - span[0]).days + 1)

    ma_days = {r[0] for r in rows if r[1] == 'MA'}
    gap = [d.isoformat() for d in days() if d not in ma_days]
    ma = lambda r: r[1] == 'MA'
    month_total = lambda y, m, keep: window_sum(rows, date(y, m, 1), date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1), keep)

    decaf = lambda r: r[2] == EROSION[0]
    cold = lambda r: r[2] in [p[0] for p in PRODUCTS if p[2] == COLD]
    total_now, total_before = window_sum(rows, *summer), window_sum(rows, *last_summer)

    return {
        'business': 'Albor Café (ficticio)', 'period': [START.isoformat(), END.isoformat()],
        'rows': len(rows), 'products': len(PRODUCTS), 'channels': len(CHANNELS),
        'totals': {'jun_aug_2026': total_now, 'jun_aug_2025': total_before},
        'signals': [
            {'key': 'S1', 'priority_rank': 1, 'kind': 'hidden decline',
             'segment': 'Tienda física, domingos', 'first_affected_date': break_day.isoformat(),
             'facts': {'store_jun_aug_2026': store_now, 'store_jun_aug_2025': store_before,
                       'store_change': store_now - store_before,
                       'store_sunday_jun_aug_2026': sunday_now, 'store_sunday_jun_aug_2025': sunday_before,
                       'sunday_change': sunday_now - sunday_before,
                       'total_change': total_now - total_before},
             'correct_reading': 'La tienda cae frente al año anterior aunque el total crece; la caída se concentra en domingos desde la fecha indicada. Comprobar horario o apertura dominical.',
             'hints': [['domingo'], ['tienda']]},
            {'key': 'S2', 'priority_rank': 2, 'kind': 'disappearing combination',
             'segment': f'{names[HO_LOSS[0]]} × Hostelería', 'first_affected_date': HO_LOSS[1].isoformat(),
             'facts': {'last_recorded_date': ho_last.isoformat(), 'monthly_units': dict(sorted(ho_months.items()))},
             'correct_reading': 'La combinación deja de registrar unidades desde abril de 2026. Comprobar cliente o pedido recurrente perdido.',
             'hints': [['hostelería'], ['1 kg', 'casa']]},
            {'key': 'S3', 'priority_rank': 3, 'kind': 'breakout opportunity',
             'segment': f'{names[WEB_BREAKOUT[0]]} × Web propia', 'first_affected_date': WEB_BREAKOUT[1].isoformat(),
             'facts': {'daily_rate_after': round(rate(after, web), 3), 'daily_rate_before': round(rate(before, web), 3),
                       'window_after': [a.isoformat() for a in after], 'window_before': [b.isoformat() for b in before]},
             'correct_reading': 'Aumento escalonado en web desde mediados de junio. Comprobar stock, origen del tráfico o pedidos.',
             'hints': [['molinillo eléctrico'], ['web']]},
            {'key': 'S4', 'priority_rank': 4, 'kind': 'data gap',
             'segment': 'Marketplace, todos los productos', 'first_affected_date': gap[0] if gap else None,
             'facts': {'missing_dates': gap, 'march_2026': month_total(2026, 3, ma),
                       'february_2026': month_total(2026, 2, ma), 'april_2026': month_total(2026, 4, ma)},
             'correct_reading': 'Fechas sin ningún registro del canal: hueco de datos, no caída de demanda. Comprobar extracción.',
             'hints': [['marketplace'], ['marzo'], ['sin registro', 'hueco', 'faltan', 'ausen']]},
            {'key': 'S5', 'priority_rank': 5, 'kind': 'slow erosion',
             'segment': f'{names[EROSION[0]]}, todos los canales', 'first_affected_date': EROSION[1].isoformat(),
             'facts': {'mar_may_2025': window_sum(rows, date(2025, 3, 1), date(2025, 5, 31), decaf),
                       'mar_may_2026': window_sum(rows, *spring, decaf),
                       'jun_aug_2025': window_sum(rows, *last_summer, decaf),
                       'jun_aug_2026': window_sum(rows, *summer, decaf)},
             'correct_reading': 'Descenso sostenido de un producto en todos los canales, visible solo con horizonte largo.',
             'hints': [['descafeinado 1 kg']]},
            {'key': 'S6', 'priority_rank': None, 'kind': 'seasonal decoy',
             'segment': 'Café frío', 'first_affected_date': None,
             'facts': {'may_2026': month_total(2026, 5, cold), 'june_2026': month_total(2026, 6, cold),
                       'jun_aug_2025': window_sum(rows, *last_summer, cold), 'jun_aug_2026': window_sum(rows, *summer, cold)},
             'correct_reading': 'El salto de mayo a junio se repite cada verano; no es una novedad ni una prioridad por sí misma.',
             'hints': [['cold brew', 'café frío'], ['estacional', 'cada verano', 'cada año', 'año anterior']]},
        ],
    }


def bruma_oracle(folder):
    """Reference facts for the frozen Bruma Café inputs (three months, small)."""
    rows = read_activity(Path(folder), 'Bruma-Cafe-datos-')
    month = lambda r: r[0].strftime('%Y-%m')
    cells = defaultdict(int)
    for r in rows:
        cells[month(r), r[1], r[2]] += r[3]
    channel = lambda m, c: sum(v for (mm, cc, _), v in cells.items() if (mm, cc) == (m, c))
    store_products = sorted({k[2] for k in cells if k[1] == 'TI'})
    falling = [p for p in store_products if cells['2026-08', 'TI', p] < cells['2026-07', 'TI', p]]
    return {
        'business': 'Bruma Café (sintético)', 'rows': len(rows),
        'signals': [
            {'key': 'B1', 'priority_rank': 1, 'kind': 'hidden decline', 'segment': 'Tienda física',
             'facts': {'july': channel('2026-07', 'TI'), 'august': channel('2026-08', 'TI'),
                       'products_falling': len(falling), 'store_products': len(store_products)},
             'correct_reading': 'La tienda cae de julio a agosto en casi todos sus productos mientras web y marketplace crecen.',
             'hints': [['tienda'], ['cae', 'caída', 'baja', 'descen', 'retroced', '−93', '-93']]},
            {'key': 'B2', 'priority_rank': 2, 'kind': 'breakout', 'segment': 'Kit de iniciación × Web propia',
             'facts': {'july': cells['2026-07', 'WE', 'P06'], 'august': cells['2026-08', 'WE', 'P06']},
             'correct_reading': 'Mayor aumento individual de julio a agosto.',
             'hints': [['kit'], ['web']]},
            {'key': 'B3', 'priority_rank': 3, 'kind': 'sustained growth', 'segment': 'Café de la casa 250 g × Marketplace',
             'facts': {'june': cells['2026-06', 'MA', 'P01'], 'august': cells['2026-08', 'MA', 'P01']},
             'correct_reading': 'Mayor aumento acumulado de junio a agosto.',
             'hints': [['café de la casa'], ['marketplace']]},
        ],
    }


def build(output, seed=SEED):
    output = Path(output)
    data = output / 'datos'
    data.mkdir(parents=True)
    rows = generate(seed)
    write_csv(data / f'{PREFIX}000.csv',
              ['fecha', 'canal_id', 'producto_id', 'unidades', 'venta_tarifa_eur', 'descuento_eur', 'venta_neta_eur'],
              [(d.isoformat() + ' 00:00:00', *rest) for d, *rest in rows])
    write_csv(data / f'{PREFIX}001.csv', ['producto_id', 'nombre', 'categoria', 'fuente'],
              [(p[0], p[1], p[2], 'Datos sintéticos para probar Decision Room') for p in PRODUCTS])
    write_csv(data / f'{PREFIX}002.csv', ['canal_id', 'nombre', 'mercado'], CHANNELS)
    write_csv(data / f'{PREFIX}003.csv', ['mes', 'canal_id', 'gasto_marketing_eur'], marketing(seed))
    (output / 'prompt.txt').write_text(PROMPT, encoding='utf-8')
    facts = oracle(data)
    facts['seed'] = seed
    facts['inputs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(data.glob('*.csv'))}
    facts['prompt_sha256'] = hashlib.sha256(PROMPT.encode()).hexdigest()
    (output / 'oracle.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return facts


BRUMA_INPUTS = {
    'Bruma-Cafe-datos-000.csv': 'f8322199f217133be01b78a59e2c7f3265266466b04c98ae8abea27f6e1b82f3',
    'Bruma-Cafe-datos-001.csv': '22f8f1d157e7e96d52c35e2c3b43dc197c04c038cfa4c74e2366eb828582127d',
    'Bruma-Cafe-datos-002.csv': 'a14f6911f080af3d02ce91bd9efbe84368411f15b980da58d9f8139107aece2d',
    'Bruma-Cafe-datos-003.csv': 'e10c1aec1776d7f86b641310b681aa0a4ee11760a77a8b96ce3d738b0466d7b0',
}
BRUMA_PROMPT = '906ffd097108352e1e4f0656138748f1533c6246fb7701216f81c87f75480e06'


def build_bruma(source, output):
    source, output = Path(source), Path(output)
    found = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((source / 'datos').glob('*.csv'))}
    prompt = (source / 'prompt.txt').read_bytes()
    if found != BRUMA_INPUTS or hashlib.sha256(prompt).hexdigest() != BRUMA_PROMPT:
        raise SystemExit('Bruma inputs differ from the frozen published hashes.')
    (output / 'datos').mkdir(parents=True)
    for name in found:
        (output / 'datos' / name).write_bytes((source / 'datos' / name).read_bytes())
    (output / 'prompt.txt').write_bytes(prompt)
    facts = {**bruma_oracle(output / 'datos'), 'inputs': found, 'prompt_sha256': BRUMA_PROMPT}
    (output / 'oracle.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='dataset', required=True)
    albor = commands.add_parser('albor')
    albor.add_argument('output', type=Path)
    albor.add_argument('--seed', type=int, default=SEED)
    bruma = commands.add_parser('bruma')
    bruma.add_argument('source', type=Path)
    bruma.add_argument('output', type=Path)
    args = parser.parse_args()
    facts = build(args.output, args.seed) if args.dataset == 'albor' else build_bruma(args.source, args.output)
    print(json.dumps({'rows': facts['rows'], 'inputs': facts['inputs']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
