"""F5 trial data: two synthetic businesses distinct from the earlier trials, with planted signals.

Usage: python scripts/f5/generate.py OUT_DIR

Writes OUT_DIR/<business>/datos/*.csv (what the product ingests), OUT_DIR/oracle.json
(planted signals with their measured magnitudes) and OUT_DIR/spec.json for
scripts/checks/product_trial.py (owner description and goal from PROFILE, 6 repetitions,
24 USD ledger). The oracle is for the judge only and must never be uploaded or reach an
agent. Deterministic for a fixed seed.
"""
import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 20261011
FILES = {'herbolario': ['ventas.csv', 'productos.csv', 'canales.csv'], 'clinica': ['citas.csv', 'encuestas.csv', 'profesionales.csv']}
PROFILE = {
    'herbolario': dict(
        name='Herbolario Saúco',
        description=('Herbolario Saúco es una tienda de productos naturales en Zaragoza. Vendemos en la tienda física, '
                     'en nuestra web propia y a distribuidores (otras tiendas y farmacias que nos compran al por mayor). '
                     'Trabajamos infusiones, aceites esenciales, suplementos, cosmética natural y miel. En ventas.csv cada '
                     'fila es un día, un producto y un canal: unidades vendidas, precio de tarifa, el descuento aplicado en % '
                     'y el importe neto en euros de esa fila, ya descontado. En productos.csv está el nombre, la categoría y '
                     'el coste unitario de compra de cada producto; en canales.csv, el nombre de cada canal.'),
        goal='Quiero saber qué ha funcionado y qué no este año frente al anterior, y en qué me debería centrar el próximo trimestre.',
        title='Cómo va el año'),
    'clinica': dict(
        name='Clínica de fisioterapia Arce',
        description=('Clínica de fisioterapia Arce, en Valladolid. Somos cuatro fisioterapeutas. En citas.csv cada fila es una '
                     'cita: fecha y hora, profesional, tipo de sesión, por dónde se reservó (web, teléfono, nuestra app de '
                     'reservas o derivación de una mutua), estado (realizada, cancelada o no presentado), duración en minutos '
                     'y si es primera visita. En encuestas.csv está la puntuación de 1 a 10 que dan algunos pacientes después '
                     'de la cita. En profesionales.csv, el nombre, las horas semanales de cada profesional y su fecha de alta.'),
        goal='Quiero entender cómo va la clínica este año: dónde perdemos citas o pacientes, cómo está cada profesional y qué debería cambiar.',
        title='Cómo va la clínica'),
}


def days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# --------------------------------------------------------------------------- herbolario
def herbolario(out, rnd):
    start, end = date(2024, 1, 1), date(2026, 9, 21)
    channels = [('TF', 'Tienda física'), ('WB', 'Web propia'), ('DS', 'Distribuidores')]
    cats = ['Infusiones', 'Aceites esenciales', 'Suplementos', 'Cosmética natural', 'Miel y apicultura']
    names = {
        'Infusiones': ['Manzanilla dulce', 'Tila de montaña', 'Rooibos vainilla', 'Menta poleo', 'Té verde jazmín'],
        'Aceites esenciales': ['Lavanda 15 ml', 'Eucalipto 15 ml', 'Árbol del té 10 ml', 'Romero 15 ml', 'Naranja dulce 15 ml'],
        'Suplementos': ['Magnesio 60 cáps.', 'Vitamina D3 90 cáps.', 'Colágeno 300 g', 'Levadura de cerveza', 'Espirulina 120 comp.'],
        'Cosmética natural': ['Crema de caléndula', 'Jabón de aloe', 'Bálsamo labial karité', 'Champú de ortiga', 'Aceite de rosa mosqueta'],
        'Miel y apicultura': ['Miel de azahar 500 g', 'Miel de brezo 500 g', 'Propóleo spray', 'Jalea real 20 g', 'Polen 250 g'],
    }
    products, i = [], 1
    for c in cats:
        for n in names[c]:
            price = round(rnd.uniform(4.5, 24.0), 2)
            products.append(dict(id=f'H{i:03d}', name=n, cat=c, price=price, cost=round(price * rnd.uniform(0.38, 0.55), 2)))
            i += 1
    by_id = {p['id']: p for p in products}
    base = {p['id']: {ch: rnd.uniform(0.6, 4.0) * {'TF': 1.0, 'WB': 0.55, 'DS': 0.9}[ch] for ch, _ in channels} for p in products}
    web_stars = ['H013', 'H021']  # grow on the web in 2026
    stockout_product = 'H011'  # Magnesio, best seller
    base[stockout_product] = {'TF': 7.5, 'WB': 6.0, 'DS': 5.5}
    stock_from, stock_to = date(2026, 7, 6), date(2026, 7, 26)
    promo_from, promo_to = date(2026, 3, 2), date(2026, 3, 29)
    rows = []
    for d in days(start, end):
        doy = d.timetuple().tm_yday
        weekday = d.weekday()
        for p in products:
            for ch, _ in channels:
                lam = base[p['id']][ch]
                if ch == 'TF':
                    lam *= 0.25 if weekday == 6 else (1.35 if weekday == 5 else 1.0)
                if ch == 'DS' and weekday >= 5:
                    continue  # distributors order on weekdays only
                if p['cat'] == 'Infusiones':  # winter seasonality (decoy for a trend)
                    lam *= 1.0 + 0.7 * max(0.0, __import__('math').cos((doy - 15) / 365 * 6.283))
                year_factor = 1.0 + (0.03 if d.year == 2025 else 0.06 if d.year == 2026 else 0.0)
                lam *= year_factor
                if ch == 'WB' and d.year == 2026:
                    lam *= 1.18
                    if p['id'] in web_stars:
                        lam *= 2.2
                if ch == 'DS' and d.year == 2026 and p['cat'] == 'Suplementos':
                    lam *= 0.45
                if p['id'] == stockout_product and stock_from <= d <= stock_to:
                    continue
                discount = 0
                if ch == 'WB' and promo_from <= d <= promo_to:
                    discount = 25
                    lam *= 1.9
                units = sum(1 for _ in range(int(lam * 3)) if rnd.random() < lam / max(1, int(lam * 3))) if lam > 0 else 0
                if units == 0:
                    continue
                net = round(units * p['price'] * (1 - discount / 100), 2)
                rows.append((d.isoformat(), p['id'], ch, units, f"{p['price']:.2f}", discount, f'{net:.2f}'))
    folder = out / 'herbolario' / 'datos'
    write(folder / 'ventas.csv', ['fecha', 'producto', 'canal', 'unidades', 'precio_unitario', 'descuento_pct', 'importe_neto'], rows)
    write(folder / 'productos.csv', ['producto', 'nombre', 'categoria', 'coste_unitario'],
          [(p['id'], p['name'], p['cat'], f"{p['cost']:.2f}") for p in products])
    write(folder / 'canales.csv', ['canal', 'nombre'], channels)
    return rows, by_id


def herbolario_oracle(rows, by_id):
    from collections import defaultdict
    ytd_end = (9, 21)

    def in_ytd(d, year):
        return d.year == year and (d.month, d.day) <= ytd_end
    units = defaultdict(int)
    net = defaultdict(float)
    for f, p, ch, u, price, disc, n in rows:
        d = date.fromisoformat(f)
        for y in (2025, 2026):
            if in_ytd(d, y):
                units[(y, ch)] += u
                units[(y, 'ALL')] += u
                units[(y, ch, by_id[p]['cat'])] += u
                units[(y, ch, p)] += u
                net[(y, 'ALL')] += float(n)
    def pct(a, b):
        return round(100 * (a - b) / b, 1)
    promo = defaultdict(lambda: [0, 0.0, 0.0])
    for f, p, ch, u, price, disc, n in rows:
        d = date.fromisoformat(f)
        if ch == 'WB' and d.year == 2026 and d.month in (2, 3, 4):
            k = 'marzo' if d.month == 3 else 'feb_abr'
            promo[k][0] += u
            promo[k][1] += float(n)
            promo[k][2] += float(n) - u * by_id[p]['cost']
    margin = {k: dict(units=v[0], margen_por_unidad=round(v[2] / v[0], 2)) for k, v in promo.items()}
    return {
        'business': 'herbolario', 'period': '2024-01-01..2026-09-21 (dato parcial de septiembre de 2026)',
        'signals': [
            dict(id='S1', title='La web propia crece con fuerza en 2026, impulsada por dos productos',
                 detail=f"Unidades web YTD 2026 vs 2025 (1 ene–21 sep): {pct(units[(2026,'WB')], units[(2025,'WB')])} %; "
                        f"{by_id['H013']['name']} (H013) {pct(units[(2026,'WB','H013')], units[(2025,'WB','H013')])} %, "
                        f"{by_id['H021']['name']} (H021) {pct(units[(2026,'WB','H021')], units[(2025,'WB','H021')])} %."),
            dict(id='S2', title='Rotura de stock del producto más vendido',
                 detail='Magnesio 60 cáps. (H011) sin ningún registro en los tres canales del 6 al 26 de julio de 2026 (21 días); antes y después vende a diario.'),
            dict(id='S3', title='Distribuidores cae en 2026, concentrado en Suplementos',
                 detail=f"Unidades Distribuidores YTD {pct(units[(2026,'DS')], units[(2025,'DS')])} %; Suplementos en Distribuidores "
                        f"{pct(units[(2026,'DS','Suplementos')], units[(2025,'DS','Suplementos')])} %; resto de categorías en Distribuidores crece levemente."),
            dict(id='S4', title='La promoción web de marzo de 2026 sube unidades pero reduce el margen por unidad',
                 detail=f"Web, 2026: marzo (25 % de descuento) {margin['marzo']['units']} uds con margen bruto/ud {margin['marzo']['margen_por_unidad']} € "
                        f"frente a febrero+abril {margin['feb_abr']['units']} uds con {margin['feb_abr']['margen_por_unidad']} €/ud (importe neto − coste unitario de productos.csv)."),
            dict(id='S5', title='Total del negocio crece moderadamente',
                 detail=f"Unidades YTD totales {pct(units[(2026,'ALL')], units[(2025,'ALL')])} %; importe neto YTD {pct(net[(2026,'ALL')], net[(2025,'ALL')])} %."),
            dict(id='S6', title='SEÑUELO: estacionalidad de Infusiones y septiembre parcial',
                 detail='Infusiones sube cada invierno y baja en verano todos los años (estacional, no tendencia). Septiembre de 2026 solo tiene datos hasta el día 21; presentarlo como caída frente a meses completos es un error.'),
        ]}


# --------------------------------------------------------------------------- clínica
def clinica(out, rnd):
    start, end = date(2025, 1, 2), date(2026, 9, 30)
    pros = [('P1', 'Laura Méndez', 40, date(2020, 1, 1)), ('P2', 'Andrés Soler', 40, date(2020, 1, 1)),
            ('P3', 'Marta Quiroga', 32, date(2020, 1, 1)), ('P4', 'Iván Rojas', 40, date(2026, 2, 2))]
    types = [('Fisioterapia general', 45), ('Suelo pélvico', 60), ('Deportiva', 45), ('Rehabilitación postquirúrgica', 60)]
    origins = ['web', 'telefono', 'app', 'mutua']
    rows, surveys, cid = [], [], 1
    for d in days(start, end):
        wd = d.weekday()
        if wd == 6:
            continue
        if wd == 5 and d < date(2026, 5, 2):
            continue
        if d.month == 8 and 4 <= d.day <= 17:
            continue  # two-week summer closure every year (decoy)
        for pid, pname, hours, since in pros:
            if d < since:
                continue
            if wd == 5 and pid not in ('P1', 'P4'):
                continue
            capacity = 4 if wd == 5 else round(hours / 5 / 0.75)
            occ = 0.86
            if pid == 'P4':
                occ = 0.42
            if d.month == 8:
                occ *= 0.7
            slots = sum(1 for _ in range(capacity) if rnd.random() < occ)
            for k in range(slots):
                t, dur = rnd.choices(types, weights=[50, 15, 20, 15])[0]
                weights = [30, 30, 20, 20]
                if d.year == 2026:
                    weights = [33, 30, 25, 11]
                origin = rnd.choices(origins, weights=weights)[0]
                first = rnd.random() < (0.34 if origin == 'mutua' else 0.18)
                p_cancel, p_noshow = 0.07, 0.04
                if origin == 'app' and d >= date(2026, 4, 6):
                    p_noshow = 0.15
                if pid == 'P3' and d >= date(2026, 6, 1):
                    p_cancel = 0.16
                if wd == 5:
                    p_noshow = 0.02
                r = rnd.random()
                state = 'cancelada' if r < p_cancel else 'no_presentado' if r < p_cancel + p_noshow else 'realizada'
                hour = f'{(9 + k) % 21:02d}:{rnd.choice(["00", "30"])}' if wd != 5 else f'{9 + k:02d}:00'
                rows.append((f'C{cid:06d}', d.isoformat(), hour, pid, t, origin, state, dur, 'si' if first else 'no'))
                if state == 'realizada' and rnd.random() < 0.45:
                    mean = 8.6
                    if pid == 'P3' and d >= date(2026, 6, 1):
                        mean = 6.8
                    if wd == 5:
                        mean = 9.1
                    score = max(1, min(10, round(rnd.gauss(mean, 1.0))))
                    surveys.append((f'C{cid:06d}', score))
                cid += 1
    folder = out / 'clinica' / 'datos'
    write(folder / 'citas.csv', ['cita_id', 'fecha', 'hora', 'profesional', 'tipo_sesion', 'origen_reserva', 'estado', 'duracion_min', 'primera_visita'], rows)
    write(folder / 'profesionales.csv', ['profesional', 'nombre', 'horas_semana', 'alta'], [(p, n, h, s.isoformat()) for p, n, h, s in pros])
    write(folder / 'encuestas.csv', ['cita_id', 'puntuacion'], surveys)
    return rows, surveys


def clinica_oracle(rows, surveys):
    from collections import defaultdict
    score = dict(surveys)
    def rate(filt, state):
        sel = [r for r in rows if filt(r)]
        return round(100 * sum(r[6] == state for r in sel) / len(sel), 1), len(sel)
    def avg(filt):
        sel = [score[r[0]] for r in rows if r[0] in score and filt(r)]
        return round(sum(sel) / len(sel), 2), len(sel)
    D = date.fromisoformat
    app_before = rate(lambda r: r[5] == 'app' and D(r[1]) < date(2026, 4, 6) and D(r[1]).weekday() != 5, 'no_presentado')
    app_after = rate(lambda r: r[5] == 'app' and D(r[1]) >= date(2026, 4, 6) and D(r[1]).weekday() != 5, 'no_presentado')
    other_after = rate(lambda r: r[5] != 'app' and D(r[1]) >= date(2026, 4, 6) and D(r[1]).weekday() != 5, 'no_presentado')
    p3_before = avg(lambda r: r[3] == 'P3' and D(r[1]) < date(2026, 6, 1))
    p3_after = avg(lambda r: r[3] == 'P3' and D(r[1]) >= date(2026, 6, 1))
    p3_cancel = (rate(lambda r: r[3] == 'P3' and D(r[1]) < date(2026, 6, 1), 'cancelada'), rate(lambda r: r[3] == 'P3' and D(r[1]) >= date(2026, 6, 1), 'cancelada'))
    def count(filt):
        return sum(1 for r in rows if filt(r))
    ytd = lambda r, y: D(r[1]).year == y and D(r[1]) <= date(y, 9, 30)
    mutua = (count(lambda r: r[5] == 'mutua' and ytd(r, 2025)), count(lambda r: r[5] == 'mutua' and ytd(r, 2026)))
    first = (count(lambda r: r[8] == 'si' and ytd(r, 2025)), count(lambda r: r[8] == 'si' and ytd(r, 2026)))
    total = (count(lambda r: ytd(r, 2025)), count(lambda r: ytd(r, 2026)))
    weekdays_2026 = lambda pid: [r for r in rows if r[3] == pid and D(r[1]) >= date(2026, 3, 1) and D(r[1]).weekday() < 5 and D(r[1]).month != 8]
    per_day = {pid: round(len(weekdays_2026(pid)) / len({r[1] for r in weekdays_2026(pid)}), 1) for pid in ('P1', 'P2', 'P3', 'P4')}
    sat = [r for r in rows if D(r[1]).weekday() == 5]
    sat_noshow = round(100 * sum(r[6] == 'no_presentado' for r in sat) / len(sat), 1)
    sat_score = avg(lambda r: D(r[1]).weekday() == 5)
    wk_score = avg(lambda r: D(r[1]).weekday() < 5 and D(r[1]) >= date(2026, 5, 2))
    pct = lambda a, b: round(100 * (a - b) / b, 1)
    return {
        'business': 'clinica', 'period': '2025-01-02..2026-09-30',
        'signals': [
            dict(id='S1', title='Las ausencias sin aviso de las reservas por app se disparan desde abril de 2026',
                 detail=f'No presentados en reservas por app (lunes–viernes): {app_before[0]} % antes del 6-abr-2026 → {app_after[0]} % después; resto de orígenes después: {other_after[0]} %.'),
            dict(id='S2', title='Marta Quiroga (P3): caída de satisfacción y más cancelaciones desde junio de 2026',
                 detail=f'Puntuación media P3 {p3_before[0]} → {p3_after[0]} (n={p3_after[1]}); cancelaciones P3 {p3_cancel[0][0]} % → {p3_cancel[1][0]} %; resto de profesionales estables.'),
            dict(id='S3', title='Caen las citas derivadas por mutuas mientras el total crece',
                 detail=f'Citas de origen mutua ene–sep {mutua[0]} (2025) → {mutua[1]} (2026), {pct(mutua[1], mutua[0])} %, mientras el total de citas pasa de {total[0]} a {total[1]} ({pct(total[1], total[0])} %) por la incorporación de P4 y los sábados. Las mutuas aportan más primeras visitas que otros orígenes; primeras visitas {first[0]} → {first[1]}.'),
            dict(id='S4', title='El profesional incorporado en febrero de 2026 (Iván Rojas, P4) tiene la agenda a medio llenar',
                 detail=f'Citas por día laborable desde marzo de 2026: {per_day}. P4 está en torno a la mitad que los demás con la misma jornada.'),
            dict(id='S5', title='Los sábados (desde mayo de 2026) funcionan muy bien',
                 detail=f'Sábados: no presentados {sat_noshow} %, satisfacción media {sat_score[0]} (n={sat_score[1]}) frente a {wk_score[0]} entre semana en el mismo periodo.'),
            dict(id='S6', title='SEÑUELO: el cierre de verano',
                 detail='Del 4 al 17 de agosto no hay citas en 2025 ni en 2026 (cierre por vacaciones, mismo patrón ambos años). Presentarlo como caída de actividad o problema es un error.'),
        ]}


def main(out):
    out = Path(out)
    rnd = random.Random(SEED)
    h_rows, by_id = herbolario(out, rnd)
    c_rows, surveys = clinica(out, rnd)
    oracle = [herbolario_oracle(h_rows, by_id), clinica_oracle(c_rows, surveys)]
    (out / 'oracle.json').write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    spec = dict(version=1, repetitions=6, owner_today='11 de octubre de 2026', cap_micro_usd=23_000_000, scope_cap_micro_usd=2_500_000,
                scope_quotas=dict(input_tokens=40_000_000, output_tokens=1_000_000, calls=400, seconds=3600),
                budget_path=str((out / 'budget-test.sqlite').resolve()),
                businesses=[dict(key=key, files=[f'{key}/datos/{name}' for name in FILES[key]], **PROFILE[key]) for key in PROFILE])
    (out / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(len(h_rows), 'ventas;', len(c_rows), 'citas;', len(surveys), 'encuestas')


if __name__ == '__main__':
    main(sys.argv[1])
