"""Deterministic v1 brief from product records. No model call; nothing business-specific in code.

The trial briefs were written by hand. Their last three paragraphs (charts, depth and
verification) are kept unchanged in engine/opencode/prompts/informe.md. The first two
paragraphs are generated here from the business profile, the owner's request, owner-
declared column meanings and declared memory. Differences from the trial wording are
listed in docs/technical/v1-f2-validation.md.
"""
import json
from pathlib import Path

from ..memory import context

VERSION = 'v1-brief-2'
QUESTIONS_VERSION = 'v1-brief-2q'
QUESTIONS = ('Si te falta un dato que solo yo puedo darte y que cambiaría una conclusión, puedes hacerme una pregunta '
             'breve con preguntar_dueno, con su motivo y, si ayuda, opciones. Hazlo como mucho una vez y no sigas '
             'calculando mientras esperas. Si respondo «no lo sé» o prefiero no responder, mantén la conclusión parcial '
             'y dilo como límite. Mi respuesta es una declaración mía, no una cifra comprobada.')
FIXED = Path(__file__).resolve().parents[2] / 'engine/opencode/prompts/informe.md'


def native_fixed(fixed):
    paragraphs = fixed.split('\n\n')
    paragraphs[0] = ('Incluye gráficos y tablas; elige los que mejor ayuden a entender los resultados. '
        'Entrega el informe como datos JSON UTF-8 en /work/informe.json, usando el formato '
        'informe-bloques-1 descrito en /inputs/contexto/formato-informe.txt. Tú decides qué contar, '
        'el orden y la cantidad de bloques: la guía explica la entrega, no es una plantilla. '
        'No crees HTML, CSS ni código para presentarlo. Puedes comprobar el formato con '
        'python3 /inputs/herramientas/comprobar_informe.py /work/informe.json; corrige los errores antes de terminar.')
    paragraphs[1] = paragraphs[1].replace('qué combinaciones de producto, canal y fechas',
                                          'qué combinaciones de las dimensiones de los datos y de fechas')
    paragraphs[-1] = paragraphs[-1].replace(', tengan etiquetas legibles y se abran correctamente', ' y tengan etiquetas legibles').replace(
        ' Añade interacción para consultar valores exactos cuando ayude a leerlos.', '')
    paragraphs.insert(2, NARRATIVE)
    paragraphs.insert(3, PRESENTATION)
    return '\n\n'.join(paragraphs)


# Generic analysis and writing guidance for native reports (plan M, M2). Nothing here may
# name a business, a column or a finding of the trial data.
NARRATIVE = ('Compara cada segmento relevante con su propia evolución en el tiempo, por meses cuando los datos '
             'lo permitan, y di desde cuándo empieza un cambio, no solo cuánto difiere de otros segmentos. Si una '
             'cifra suma partes que se comportan de forma distinta, sepáralas. Cuenta el análisis en texto: en cada '
             'prioridad, explica primero qué pasa y por qué importa, después muestra la evidencia con una cifra, un '
             'gráfico o una tabla, y termina con qué comprobar y qué hacer según el resultado. Usa una tabla solo '
             'cuando su detalle ayude a decidir, no repitas en el texto lo que ya muestra un gráfico o una tabla y '
             'no añadas notas técnicas sobre cómo has calculado si no cambian la lectura.')

PRESENTATION = ('Usa portada, tarjetas y accion cuando ayuden a organizar el titular, el resumen, el balance y '
                'los siguientes pasos que ya ibas a contar; mueve el contenido a esos bloques, no lo dupliques '
                'ni añadas texto para rellenarlos. No son una plantilla obligatoria. Puedes dar rótulos propios '
                'a las partes de accion cuando los de la plataforma no encajen con la comprobación. Declara bueno en las '
                'variaciones y tono en series y tarjetas cuando los datos y el significado confirmado de la '
                'métrica permitan una lectura favorable, desfavorable o de aviso; si no, omítelos. '
                'Subir no siempre es bueno. Conserva los gráficos de evolución y las tablas cortas que aporten evidencia.')


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
CATALOG = ('Para que sepas que existen, el negocio tiene también estos otros conjuntos de datos. No están en '
           '/inputs y no puedes usarlos en este informe; no saques conclusiones de ellos:')
CHAT_BRIEF = ('Resumen del chat (propuesta del asistente a partir de nuestra conversación; es orientación, '
              'no hechos ni definiciones; si algo choca con los datos, mis definiciones o lo que te he contado, '
              'prevalecen estos):')
INDICATORS = ('Estos son indicadores que guardé: cada uno es una fórmula fija que confirmé y que se recalcula sin '
              'modelo con cada versión de los datos; no tienen comprobación independiente. Si usas una de sus cifras, '
              'di que es la del indicador guardado; si la recalculas con los datos, di si coincide:')
FOLLOW_UPS = ('Estos son temas abiertos que dejaron informes anteriores, copiados tal cual y con el estado que les di '
              '(«comprobado» quiere decir que yo lo di por comprobado, no que esté verificado). Dime qué muestran ahora '
              'los datos sobre ellos, sin dar por hecho lo que proponían:')
HISTORY = ('Estos son informes anteriores que me hiciste. Lo que dicen son afirmaciones de esos informes, no datos '
           'comprobados ahora, y sus acciones eran propuestas: no sé si se llevaron a cabo. Tienes su texto en '
           '/inputs/contexto/informes-anteriores/ (manifest.json indica cuál es cada uno). Si retomas algo de ellos, '
           'recalcúlalo con los datos actuales y di qué ha cambiado; si citas una cifra suya, deja claro que es lo '
           'que decía ese informe.')


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


def _metrics(metrics):
    return ', '.join(f'{key} = {value}' for key, value in metrics.items())


def _data(latest):
    period = latest.get('period') or {}
    span = f" (del {period['from']} al {period['until']})" if period.get('from') and period.get('until') else ''
    return f"la versión {latest['dataset_version']} de los datos{span}"


def indicator_lines(core):
    lines = []
    for item in (core or {}).get('items', []):
        latest = item.get('latest') or {}
        head = f"- {item['name']} (versión {item['version']} de la fórmula)"
        if latest.get('status') == 'completed':
            line = f"{head}: {_metrics(latest['metrics'])}, con {_data(latest)}."
            if latest.get('meanings'):
                line += ' ' + latest['meanings']
        elif latest.get('status') == 'unavailable':
            line = f"{head}: no disponible con {_data(latest)} ({latest['reason']})"
        elif latest:
            line = f"{head}: pendiente de recalcular con la versión {latest['dataset_version']} de los datos."
        else:
            line = f'{head}: sin valor todavía.'
        lines.append(sentence(line))
    if (core or {}).get('omitted'):
        lines.append(f"(No caben aquí {core['omitted']} indicador(es) más.)")
    return lines


def follow_up_lines(core):
    from ..follow_ups import STATE_LABELS
    from ..reports.history import CHECKS, STALE
    lines = []
    for item in (core or {}).get('items', []):
        parts = [f"{item['labels'][k]}: {' / '.join(item[k])}" for k in ('check', 'if_confirmed', 'if_not') if item.get(k)]
        line = f"- «{item['headline']}» ({item['date']}) · {item['priority']}: " + ' · '.join(parts)
        report = item.get('report') or {}
        stale = report.get('stale_reason')
        warnings = f" con {report['warnings']} aviso(s)" if report.get('warnings') else ''
        line += (f" [informe {'caducado: ' + STALE.get(stale, stale) if stale else 'vigente'}; comprobación independiente "
                 f"{CHECKS.get(report.get('check_state'), 'no disponible')}{warnings}]")
        line += f" [estado: {STATE_LABELS[item['state']]}]"
        if item.get('link'):
            link = item['link']
            line += f" [lo enlacé a un indicador: {link['metric_key']} = {link['value']} con la versión {link['dataset_version']} de los datos"
            line += f"; {link['meanings']}]" if link.get('meanings') else ']'
        lines.append(line)
    extra = []
    if (core or {}).get('omitted'):
        extra.append(f"{core['omitted']} tema(s) abierto(s) más no caben aquí")
    counts = (core or {}).get('counts') or {}
    if counts.get('closed'):
        extra.append(f"{counts['closed']} tema(s) cerrado(s) no se incluyen")
    if extra:
        lines.append('(' + '; '.join(extra) + '.)')
    return lines


def compose(*, name, description, goal, model, memory, panorama, questions=False, format='html', include_delivery=True,
            data_meanings=None, history=None, chat_brief=None, catalog=None, analysis=None, indicators=None, follow_ups=None):
    declared, unknown = data_meanings if data_meanings is not None else meanings(model)
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
    others = [i for i in (catalog or {}).get('items', []) if i['analysis_id'] != str(analysis)]
    if others:
        def when(period):
            return (f"del {period['from']} al {period['until']}" if period.get('from') and period.get('until')
                    else 'periodo declarado desconocido')
        paragraphs.append(CATALOG + '\n' + '\n'.join(
            f"- {' '.join((i['description'] or 'Sin título').split())[:120]} ({when(i['period'])})" for i in others))
    remembered = facts(memory)
    if remembered:
        paragraphs.append(MEMORY + '\n' + '\n'.join('- ' + f for f in remembered))
    measured = indicator_lines(indicators)
    if measured:
        paragraphs.append(INDICATORS + '\n' + '\n'.join(measured))
    pending = follow_up_lines(follow_ups)
    if pending:  # Also when every topic is closed or omitted: the counts are still said.
        paragraphs.append(FOLLOW_UPS + '\n' + '\n'.join(pending))
    prior = (history or {}).get('reports') or []
    if prior:
        paragraphs.append(HISTORY + '\n' + '\n\n'.join(r['summary'] for r in prior))
    paragraphs.append(sentence(goal or '') + ' ' + REQUEST if (goal or '').strip() else DEFAULT_GOAL + ' ' + REQUEST)
    if chat_brief:
        lines = [CHAT_BRIEF, '- Objetivo: ' + chat_brief['objective']]
        if chat_brief.get('reason'):
            lines.append('- Motivo: ' + chat_brief['reason'])
        lines += ['- ' + item['text'] for item in chat_brief.get('background', [])]
        paragraphs.append('\n'.join(lines))
    fixed = FIXED.read_text()
    if format == 'blocks':
        fixed = native_fixed(fixed)
    return '\n\n'.join(paragraphs) + ('\n\n' + fixed if include_delivery else '')


def build(db, business, analysis, **kwargs):
    """Text + provenance only (callers that do not install the prior-report files)."""
    text, provenance, _ = build_inputs(db, business, analysis, **kwargs)
    return text, provenance


def build_inputs(db, business, analysis, *, goal, panorama, name=None, description=None, profile_revision=None,
                 questions=False, format='html', investigation_brief=None):
    """Read the product inputs once, under the caller's transaction: text, provenance and frozen files.

    The prior-report summaries, files and manifest are selected in this same transaction.

    ``name``/``description`` come from the job when it froze them at creation; otherwise
    the current «Mi negocio» profile is read and its revision recorded.
    """
    from .. import business_knowledge
    owner = db.execute('''SELECT b.name,b.description,w.profile_revision FROM businesses b
        JOIN web_businesses w ON w.business_id=b.id WHERE b.id=%s''', (business,)).fetchone()
    if not owner:
        raise ValueError('Business profile not found.')
    frozen = name is not None and description is not None
    owner = dict(name=name, description=description, profile_revision=profile_revision) if frozen else owner
    sources = [str(r['id']) for r in db.execute(
        'SELECT id FROM sources WHERE business_id=%s AND analysis_id=%s', (business, analysis)).fetchall()]
    selection = dict(analysis_id=str(analysis), source_ids=sources, period=context.period())
    # The shared core: declared memory only, the same one the chat receives.
    core, files, manifest = business_knowledge.build_with_files(
        db, business, selection, profile=dict(name=owner['name'], description=owner['description']),
        explicit=(investigation_brief or {}).get('reports', ()))
    memory, data = core['memory'], core['data_model']
    model, data_meanings = None, (data['declared'], data['unknown'])
    prior = core['history']
    text = compose(name=owner['name'], description=owner['description'], goal=goal, model=model, memory=memory,
                   panorama=panorama, questions=questions, format=format, data_meanings=data_meanings, history=prior,
                   chat_brief=investigation_brief, catalog=core['catalog'], analysis=analysis,
                   indicators=core['indicators'], follow_ups=core['follow_ups'])
    provenance = dict(version=('blocks-brief-6q' if questions else 'blocks-brief-6') if format == 'blocks' else (QUESTIONS_VERSION if questions else VERSION), profile='job' if frozen else 'current', profile_revision=owner['profile_revision'],
                      data_model=dict(analysis_id=str(analysis), revision=data['revision']) if data['revision'] else None,
                      memory=sorted(r['reference'] for r in memory if facts([r])),
                      panorama=bool(panorama), knowledge=core['version'], chat_brief=bool(investigation_brief),
                      # Historical identity only: a prior report's later staleness never retires this one.
                      prior_reports=manifest['reports'],
                      # The exact indicator values and topic states this report received.
                      indicators=[dict(indicator_id=i['id'], **{k: i['latest'][k] for k in ('value_id', 'version_id', 'dataset_version', 'status')})
                                  for i in core['indicators']['items'] if i.get('latest')],
                      follow_ups=[dict(id=f['id'], state=f['state'],
                                       **({'link': {k: f['link'][k] for k in ('value_id', 'version_id')}} if f.get('link') else {}))
                                  for f in core['follow_ups']['items']])
    if format == 'blocks':
        provenance['checker_context'] = compose(name=owner['name'],description=owner['description'],goal=goal,
            model=model,memory=memory,panorama=False,questions=False,format=format,include_delivery=False,
            data_meanings=data_meanings,history=prior,catalog=core['catalog'],analysis=analysis,
            indicators=core['indicators'],follow_ups=core['follow_ups'])
    if files:
        files = {**files, 'informes-anteriores/manifest.json': json.dumps(manifest, ensure_ascii=False, indent=1)}
    return text, provenance, files
