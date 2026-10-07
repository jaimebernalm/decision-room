"""Independent accuracy audit for the engine's step-3 gate (preregistration v4, section 6.3).

The kit holds every delivered engine report in its content version (verification marks removed,
same neutral presentation as the readers' kit), the plain brief and CSVs of each business, frozen
instructions and a template. The auditor recalculates from the CSVs and classifies every figure;
the engine's labels are joined afterwards by trial_accuracy, so the auditor never sees them.

python -m decision_room.evaluation.trial_audit kit BATCH OUT
python -m decision_room.evaluation.trial_audit unblind BATCH AUDIT.json --kit OUT_NAME > register.json
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
from uuid import uuid4

from .trial_kit import neutralize
from .trial_pairs import CONTENT, content, delivered
from .trials import read, text_of, write

INSTRUCTIONS = '''# Auditoría de exactitud (paso 3 del motor)

Hay {count} informes en `informes/`, con códigos aleatorios y la misma presentación.
Recalcula sus cifras desde `entradas/<negocio>/datos/*.csv`, con un método propio.
El encargo exacto del propietario está en `entradas/<negocio>/prompt.txt`.

Antes de empezar, comprueba que el kit está intacto:

```
shasum -a 256 -c MANIFIESTO.sha256
```

## Reglas

- No abras nada fuera de esta carpeta: ni código, ni lotes de ensayo, ni claves,
  oráculos o registros. No necesitas saber qué sistema escribió cada informe.
- Tú decides qué cifras cuentan y cómo se clasifican; nadie más lo hace por ti.

## Alcance, en cada informe

- **todas** las cifras comparativas (variaciones, diferencias, cuotas, rankings,
  medias, cocientes), con su denominador y su periodo;
- **todas** las cifras citadas en una recomendación explícita del informe o en su
  justificación frente a alternativas, incluidos sus denominadores y las cifras
  enlazadas como soporte, en el puesto que estén;
- el resto de cifras, si es razonable; si no, deja constancia de qué no revisaste.

## Registro por cifra (`registro_cifras` en la plantilla)

```json
{{
  "cita": "texto exacto del informe donde aparece, sin recortar la cifra",
  "valor_informe": "tal como aparece",
  "valor_esperado": "tu recálculo, o null si no es calculable con los datos",
  "calculo": "operación, filtros, periodo y denominador usados",
  "fuente": "archivos y columnas",
  "sostiene_prioridad_v3": true,
  "sostiene_prioridad_principal": false,
  "prioridad_citada": "la recomendación que sostiene, si la sostiene",
  "clase": "correcta | error | redondeo | no_calculable | ambigua",
  "severidad": "ninguna | menor | material",
  "limites": "qué no se pudo comprobar o qué supuestos hiciste"
}}
```

- **sostiene_prioridad_v3:** la cifra está en una recomendación explícita o en su
  justificación frente a alternativas (con denominadores y cifras enlazadas), esté
  en el puesto que esté. Las descriptivas o históricas sin ese vínculo, no.
  Anota en `prioridad_citada` la recomendación que sostiene.
- **sostiene_prioridad_principal:** lo mismo, solo para las tres primeras
  prioridades del informe (diagnóstico).
- **cita:** copia la frase tal como se lee, de modo que contenga la cifra; si la
  misma cifra aparece varias veces en la frase, indica en `limites` cuál es.
- **error:** el valor no coincide con ningún cálculo razonable de lo que la frase dice.
- **redondeo:** coincide salvo por el redondeo mostrado.
- **ambigua:** la frase admite más de un cálculo y el informe no dice cuál usó;
  anota los valores posibles.
- **material:** cambiaría lo que el dueño entiende o decide; si no, **menor**.

Por informe, rellena además `cifras_revisadas_total` y `no_revisado`.

## Entrega

Guarda la plantilla rellena fuera de esta carpeta como `auditoria-<nombre>.json`.
'''


def kit(batch, out, system='engine'):
    batch, out = Path(batch).resolve(), Path(out).resolve()
    key_path = batch / f'kit-key-{out.name}.json'
    if key_path.exists() or out.exists():
        raise SystemExit('Kit already built; keep its codes so the audit stays aligned.')
    if out.is_relative_to(batch):
        raise SystemExit('Build the kit outside the batch, so the auditor never browses attempts or keys.')
    manifest = read(batch / 'manifest.json')
    jobs = [n for n in manifest['order'] if read(batch / 'jobs' / n / 'state.json')['system'] == system
            and delivered(batch, n)]
    if not jobs:
        raise SystemExit(f'No delivered {system} reports to audit.')
    random.Random(uuid4().int).shuffle(jobs)
    (out / 'informes').mkdir(parents=True)
    codes, marked = {}, []
    for job in jobs:
        dataset = read(batch / 'jobs' / job / 'state.json')['dataset']
        html = content(batch, job)
        if html is None:  # without the unmarked rendering the auditor would see the engine's own labels
            html, _ = delivered(batch, job), marked.append(job)
        code = f'{dataset}-{uuid4().hex[:6]}'
        codes[code] = job
        html = neutralize(html)
        (out / 'informes' / f'{code}.html').write_text(html, encoding='utf-8')
        (out / 'informes' / f'{code}.txt').write_text(text_of(html) + '\n', encoding='utf-8')
    for dataset in sorted({c.rsplit('-', 1)[0] for c in codes}):
        target = out / 'entradas' / dataset
        (target / 'datos').mkdir(parents=True)
        for path in sorted((batch / 'inputs' / dataset / 'datos').glob('*.csv')):
            shutil.copyfile(path, target / 'datos' / path.name)
        shutil.copyfile(batch / 'inputs' / dataset / 'prompt.txt', target / 'prompt.txt')
    write(out / 'plantilla.json', {'auditor': '', 'informes': {
        code: {'registro_cifras': [], 'cifras_revisadas_total': None, 'no_revisado': ''} for code in sorted(codes)}})
    (out / 'INSTRUCCIONES.md').write_text(INSTRUCTIONS.format(count=len(codes)), encoding='utf-8')
    frozen = sorted(p for p in out.rglob('*') if p.is_file() and p.name != 'plantilla.json')
    (out / 'MANIFIESTO.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n' for p in frozen))
    for path in frozen:
        path.chmod(0o444)
    write(key_path, {'created_at': datetime.now(timezone.utc).isoformat(), 'out': str(out), 'codes': codes,
                     'marks_not_removed': marked})
    return {'reports': len(codes), 'marks_not_removed': marked}


def unblind(batch, audited, kit_name):
    """The auditor's sheet keyed by job, in the shape trial_accuracy.load reads."""
    key = read(Path(batch) / f'kit-key-{kit_name}.json')['codes']
    sheet = json.loads(Path(audited).read_text())['informes']
    if set(sheet) != set(key):
        raise SystemExit('The audit does not cover exactly the kit reports.')
    missing = [code for code, body in sheet.items() if body.get('cifras_revisadas_total') is None]
    if missing:
        raise SystemExit(f'Reports without a reviewed-figures count: {", ".join(sorted(missing))}.')
    return {key[code]: body for code, body in sheet.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    k = commands.add_parser('kit')
    k.add_argument('batch', type=Path)
    k.add_argument('out', type=Path)
    u = commands.add_parser('unblind')
    u.add_argument('batch', type=Path)
    u.add_argument('audited', type=Path)
    u.add_argument('--kit', required=True)
    args = parser.parse_args()
    result = kit(args.batch, args.out) if args.command == 'kit' else unblind(args.batch, args.audited, args.kit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
