"""Deterministic v1 brief from product records. No model call; nothing business-specific in code.

The trial briefs were written by hand. Their last three paragraphs (charts, depth and
verification) are kept unchanged in engine/opencode/prompts/informe.md. The first two
paragraphs are generated here from the business profile, the owner's request, owner-
declared column meanings and declared memory. Differences from the trial wording are
listed in docs/technical/v1-f2-validation.md.
"""
from pathlib import Path

from ..memory import context

VERSION = 'v1-brief-1'
QUESTIONS_VERSION = 'v1-brief-1q'
QUESTIONS = ('Si te falta un dato que solo yo puedo darte y que cambiaría una conclusión, puedes hacerme una pregunta '
             'breve con preguntar_dueno, con su motivo y, si ayuda, opciones. Hazlo como mucho una vez y no sigas '
             'calculando mientras esperas. Si respondo «no lo sé» o prefiero no responder, mantén la conclusión parcial '
             'y dilo como límite. Mi respuesta es una declaración mía, no una cifra comprobada.')
FIXED = Path(__file__).resolve().parents[2] / 'engine/opencode/prompts/informe.md'
DATA = 'Los CSV están en la carpeta /inputs/datos; /inputs/manifest.json indica qué tabla es cada archivo.'
PANORAMA = ('En la carpeta /inputs/contexto tienes panorama.md, un resumen calculado automáticamente a partir de '
            'los CSV (totales, comparación con el periodo anterior, mayores cambios y huecos de registros). '
            'Úsalo como punto de partida y compruébalo con los datos antes de citar sus cifras.')
UNKNOWN = ('Si una columna no tiene aquí un significado confirmado, no supongas su unidad ni su base '
           '(por ejemplo, si un importe es por unidad o por fila) y dilo como límite.')
LIMITS = ('No tengo información adicional sobre apertura, disponibilidad, cobertura completa o causas externas, '
          'y no quiero predicciones.')
MEMORY = 'Ten en cuenta también lo que te he contado; son declaraciones mías, no resultados calculados:'
DEFAULT_GOAL = 'Quiero entender cómo evoluciona mi actividad durante el periodo disponible.'
REQUEST = 'Hazme un informe que me ayude a decidir qué revisar y qué comprobar después, usando estos datos.'
MEMORY_KINDS = ('context', 'priority', 'definition', 'availability')


def sentence(text):
    text = ' '.join(text.split())
    return text if not text or text[-1] in '.!?…' else text + '.'


def identity(name, description):
    name, description = ' '.join(name.split()), sentence(description or '')
    if not description:
        return f'Mi negocio es {name}.'
    if description[0].islower():
        return f'Mi negocio es {name}, {description}'
    return f'Mi negocio es {name}. {description}'


def period(value):
    start, end = (value or {}).get('from'), (value or {}).get('until')
    return (f' (desde {start} hasta {end})' if start and end else f' (desde {start})' if start else
            f' (hasta {end})' if end else '')


def meanings(model):
    """Owner-declared table, column and metric meanings only; technical profiling is not meaning."""
    declared, unknown = [], False
    tables = (model or {}).get('tables', [])
    names = {t.get('id'): t['name'] for t in tables}
    for table in tables:
        if table.get('semantic_status') == 'owner_declared':
            if table.get('description'):
                declared.append(f"La tabla «{table['name']}»: {sentence(table['description'])}")
            if table.get('grain'):
                declared.append(sentence(f"En «{table['name']}», cada fila es {' '.join(table['grain'].split())}"))
        where = f" en «{table['name']}»" if len(tables) > 1 else ''
        for column in table.get('columns', []):
            if column.get('semantic_status') != 'owner_declared':
                unknown = True
                continue
            meaning = ' '.join((column.get('meaning') or '').split())
            label = f"«{column['name']}»{where}"
            text = (f"{label} es {meaning}" if meaning[:1].islower() else
                    f"{label}: {meaning}" if meaning else label)
            if column.get('unit'):
                text += f" (unidad: {' '.join(column['unit'].split())})"
            if column.get('conversion'):
                text += f"; {' '.join(column['conversion'].split())}"
            declared.append(sentence(text))
    for metric in (model or {}).get('metrics', []):
        scope = ', '.join(f"«{names.get(t, t)}»" for t in metric.get('table_ids', []))
        text = f"Métrica «{metric.get('name') or metric['key']}»" + (f" (unidad: {metric['unit']})" if metric.get('unit') else '')
        text += (f', con {scope}' if scope else '') + period(metric.get('period'))
        definition = ' '.join((metric.get('definition') or '').split())
        declared.append(sentence(text + (f': {definition}' if definition else '')))
    return declared, unknown or not model


def facts(rows):
    """Declared statements with their effective period (a later change closes the earlier one)."""
    return [sentence(sentence(r['content']['statement'])[:-1] + period(r.get('period'))) for r in rows
            if r['status'] == 'declared' and r['content']['kind'] in MEMORY_KINDS
            and r['content'].get('temporal_scope') != 'unresolved']


def compose(*, name, description, goal, model, memory, panorama, questions=False):
    declared, unknown = meanings(model)
    first = [identity(name, description), DATA]
    if panorama:
        first.append(PANORAMA)
    first += declared
    if unknown:
        first.append(UNKNOWN)
    first.append(LIMITS)
    if questions:
        first.append(QUESTIONS)
    paragraphs = [' '.join(first)]
    remembered = facts(memory)
    if remembered:
        paragraphs.append(MEMORY + '\n' + '\n'.join('- ' + f for f in remembered))
    paragraphs.append(sentence(goal or '') + ' ' + REQUEST if (goal or '').strip() else DEFAULT_GOAL + ' ' + REQUEST)
    return '\n\n'.join(paragraphs) + '\n\n' + FIXED.read_text()


def build(db, business, analysis, *, goal, panorama, name=None, description=None, profile_revision=None, questions=False):
    """Read the product inputs once, under the caller's transaction, and return text + provenance.

    ``name``/``description`` come from the job when it froze them at creation; otherwise
    the current «Mi negocio» profile is read and its revision recorded.
    """
    from ..data_knowledge import service as knowledge
    owner = db.execute('''SELECT b.name,b.description,w.profile_revision FROM businesses b
        JOIN web_businesses w ON w.business_id=b.id WHERE b.id=%s''', (business,)).fetchone()
    if not owner:
        raise ValueError('Business profile not found.')
    frozen = name is not None and description is not None
    owner = dict(name=name, description=description, profile_revision=profile_revision) if frozen else owner
    head = knowledge.latest(db, business, analysis)
    model = head['body'] if head and knowledge.current(
        db, business, {'analysis_id': str(analysis), 'revision': head['revision']}) else None
    sources = [str(r['id']) for r in db.execute(
        'SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s', (business, analysis)).fetchall()]
    selection = dict(analysis_id=str(analysis), source_ids=sources, period=context.period())
    memory = context.scoped(context.effective(db, business), selection)
    text = compose(name=owner['name'], description=owner['description'], goal=goal,
                   model=model, memory=memory, panorama=panorama, questions=questions)
    provenance = dict(version=QUESTIONS_VERSION if questions else VERSION, profile='job' if frozen else 'current', profile_revision=owner['profile_revision'],
                      data_model=dict(analysis_id=str(analysis), revision=head['revision']) if model else None,
                      memory=sorted(r['reference'] for r in memory if facts([r])),
                      panorama=bool(panorama))
    return text, provenance
