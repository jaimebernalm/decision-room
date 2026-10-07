"""Signal judge for the engine's step-3 gate (preregistration v4, section 6.2).

The judge knows the planted truth of Albor (the oracle, passed only at scoring time) but not
which system wrote each report. The kit holds Albor's delivered reports from every arm, with
fresh codes and the same neutral presentation; the key stays in the batch, outside the kit.

Scale per report, as in section 18 of the trials document: S1-S5 score 0 (not found), 1 (found,
but the figure or the reading contradicts what the files allow) or 2 (found, with a correct figure
and a reading the files support). The decoy S6 scores 1 if the report presents the seasonal rise
as news, else 0. The gate asks the engine for a mean of at least 11/3 points in S1-S5 per report
and S6 = 0 in every report.

python -m decision_room.evaluation.trial_judge kit BATCH OUT [--dataset albor]
python -m decision_room.evaluation.trial_judge score BATCH JUDGE.json --kit OUT_NAME
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import random
from uuid import uuid4

from .trial_kit import neutralize
from .trial_pairs import delivered
from .trials import read, text_of, write

SIGNALS = ('S1', 'S2', 'S3', 'S4', 'S5')
DECOY = 'S6'
THRESHOLD = Fraction(11, 3)

INSTRUCTIONS = '''# Juez de señales (paso 3 del motor)

Hay {count} informes de {dataset} en `informes/`, con códigos aleatorios y la misma
presentación. No sabes qué sistema escribió cada uno; no intentes deducirlo.

Recibes el oráculo aparte, al puntuar. Úsalo solo para esto: nunca lo copies a
esta carpeta ni lo compartas con agentes, producto o lectores.

## Escala por informe

Para cada señal real (S1-S5), según lo **deducible de los archivos** que dice el
oráculo (no la causa plantada, que no es exigible):

- **0:** el informe no la menciona, o la menciona sin relación con lo plantado.
- **1:** la encuentra, pero la cifra o la lectura contradicen lo que permiten los
  archivos (por ejemplo, presenta un hueco de registros como caída de ventas segura).
- **2:** la encuentra con una cifra correcta y una lectura que los archivos sostienen.

Para el señuelo S6: **1** si el informe presenta la subida estacional como novedad;
**0** si no la menciona o la presenta como estacional.

Anota además, por señal, si está **entre las prioridades** del informe (lo que pide
revisar o hacer), y una cita breve que justifique la puntuación.

## Entrega

Rellena `plantilla.json` y guárdala fuera de esta carpeta como `juez-<nombre>.json`.
'''


def kit(batch, out, dataset='albor'):
    batch, out = Path(batch).resolve(), Path(out).resolve()
    key_path = batch / f'kit-key-{out.name}.json'
    if key_path.exists() or out.exists():
        raise SystemExit('Kit already built; keep its codes so the judge stays aligned.')
    if out.is_relative_to(batch):
        raise SystemExit('Build the kit outside the batch, so the judge never browses attempts or keys.')
    manifest = read(batch / 'manifest.json')
    jobs = [name for name in manifest['order']
            if read(batch / 'jobs' / name / 'state.json')['dataset'] == dataset and delivered(batch, name)]
    if not jobs:
        raise SystemExit(f'No delivered {dataset} reports to judge.')
    random.Random(uuid4().int).shuffle(jobs)
    codes = {uuid4().hex[:6]: job for job in jobs}
    (out / 'informes').mkdir(parents=True)
    for code, job in codes.items():
        html = neutralize(delivered(batch, job))
        (out / 'informes' / f'{dataset}-{code}.html').write_text(html, encoding='utf-8')
        (out / 'informes' / f'{dataset}-{code}.txt').write_text(text_of(html) + '\n', encoding='utf-8')
    signal = lambda: {'puntos': None, 'entre_prioridades': None, 'cita': ''}
    write(out / 'plantilla.json', {'juez': '', 'informes': {
        f'{dataset}-{code}': {**{s: signal() for s in SIGNALS}, DECOY: signal(), 'notas': ''} for code in codes}})
    (out / 'INSTRUCCIONES.md').write_text(INSTRUCTIONS.format(count=len(codes), dataset=dataset), encoding='utf-8')
    write(key_path, {'created_at': datetime.now(timezone.utc).isoformat(), 'out': str(out), 'dataset': dataset,
                     'codes': {f'{dataset}-{code}': job for code, job in codes.items()}})
    return {'reports': len(codes)}


def score(batch, judged, kit_name, system='engine'):
    """Unblind a judge's sheet and check the gate condition for one arm."""
    batch = Path(batch)
    key = read(batch / f'kit-key-{kit_name}.json')['codes']
    sheet = json.loads(Path(judged).read_text())['informes']
    if set(sheet) != set(key):
        raise SystemExit('The judge sheet does not cover exactly the kit reports.')
    rows = {}
    for code, job in key.items():
        marks = sheet[code]
        points = [marks[s]['puntos'] for s in (*SIGNALS, DECOY)]
        if any(p not in (0, 1, 2) for p in points[:-1]) or points[-1] not in (0, 1):
            raise SystemExit(f'{code}: every signal needs a score on its scale.')
        rows[job] = {'system': read(batch / 'jobs' / job / 'state.json')['system'],
                     **{s: marks[s]['puntos'] for s in (*SIGNALS, DECOY)},
                     'total': sum(points[:-1]),
                     'in_priorities': sum(bool(marks[s]['entre_prioridades']) for s in SIGNALS)}
    by_system = {}
    for row in rows.values():
        by_system.setdefault(row['system'], []).append(row)
    summary = {s: {'reports': len(r), 'mean_total': float(Fraction(sum(x['total'] for x in r), len(r))),
                   'by_signal': {k: sum(x[k] for x in r) for k in (*SIGNALS, DECOY)},
                   'in_priorities': sum(x['in_priorities'] for x in r)} for s, r in sorted(by_system.items())}
    arm = by_system.get(system, [])
    mean = Fraction(sum(x['total'] for x in arm), len(arm)) if arm else None
    return {'reports': rows, 'by_system': summary,
            'gate': {'system': system, 'mean_total': float(mean) if mean is not None else None,
                     'threshold': float(THRESHOLD), 'decoy_total': sum(x[DECOY] for x in arm),
                     'passed': bool(arm) and mean >= THRESHOLD and all(x[DECOY] == 0 for x in arm)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    k = commands.add_parser('kit')
    k.add_argument('batch', type=Path)
    k.add_argument('out', type=Path)
    k.add_argument('--dataset', default='albor')
    s = commands.add_parser('score')
    s.add_argument('batch', type=Path)
    s.add_argument('judged', type=Path)
    s.add_argument('--kit', required=True, help='Name of the kit folder, to find its key')
    args = parser.parse_args()
    result = kit(args.batch, args.out, args.dataset) if args.command == 'kit' else score(args.batch, args.judged, args.kit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
