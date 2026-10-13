"""Prior engine reports as frozen, labelled history for the chat and the report brief.

Separate from the current-report reader (reading.chat_document), which keeps returning
only current reports. Here a stale report is labelled, not excluded: replacing the data
is exactly when an earlier report matters. What a prior report said is that report's
statement, never a fact verified now; its actions are its proposals, not pending tasks.

Deterministic and bounded; no model call, no rendering, and the agent's HTML is never
read. Callers must hold a transaction: memory head first, then shared document locks in
stable id order, the same order the writers use.
"""
import hashlib
import json

from ..engine import blocks
from ..memory import service as memory
from . import store

VERSION = 'prior-reports-2'
MAX_REPORTS = 3
CANDIDATES = 50
SUMMARY_BYTES = 6 * 1024
FILE_BYTES = 64 * 1024
META_BYTES = 8 * 1024
ITEM_CHARS = 300
MAX_WARNINGS = 3
OMITTED = '(Sin espacio en este resumen para {} apartado(s).)'
CHECK_MARKER = '\nComprobación independiente de cifras: '
CHECK_BYTES = 16 * 1024
FOLDER = 'informes-anteriores'
RULE = ('Orden: referencias explícitas del encargo, mismo conjunto de datos (cualquier versión), mismo análisis '
        'y otros informes del negocio; dentro de cada grupo, del más reciente al más antiguo. Máximo 3.')
STALE = {'data_changed': 'los datos han cambiado desde entonces', 'definitions_changed': 'las definiciones han cambiado',
         'memory_changed': 'la memoria aplicable ha cambiado', 'data_unavailable': 'sus datos ya no están disponibles',
         'missing_context': 'falta su contexto de origen'}
CHECKS = {'complete': 'completada', 'incomplete': 'no completada', 'pending': 'en curso', 'unknown': 'no completada'}


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def size(text):
    return len(text.encode('utf-8'))


def clip(text, limit=ITEM_CHARS):
    text = ' '.join(text.split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def candidates(db, business, analysis, explicit=()):
    """Ordered by group and delivery date BEFORE the limit, so the limit never drops a relevant report."""
    return db.execute('''SELECT d.*,r.status AS run_status,w.title,w.goal,w.deleted_at AS job_deleted_at,
            rev.created_at AS delivered_at,v.dataset_id,v.version AS dataset_version,v.period_from,v.period_until,
            CASE WHEN d.id=ANY(%s::uuid[]) THEN 0
                 WHEN v.dataset_id IS NOT NULL AND v.dataset_id=cur.dataset_id THEN 1
                 WHEN d.analysis_id=%s::uuid THEN 2 ELSE 3 END AS grp
        FROM report_documents d
        JOIN engine_runs r ON r.business_id=d.business_id AND r.id=d.source_run_id
        JOIN report_document_revisions rev ON rev.business_id=d.business_id AND rev.document_id=d.id AND rev.id=d.current_revision_id
        LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
        LEFT JOIN dataset_versions v ON v.business_id=d.business_id AND v.analysis_id=d.analysis_id
        LEFT JOIN dataset_versions cur ON cur.business_id=d.business_id AND cur.analysis_id=%s::uuid
        WHERE d.business_id=%s AND d.deleted_at IS NULL AND w.deleted_at IS NULL
          AND d.origin IN ('engine_blocks','engine_html') AND r.status='delivered'
          AND rev.presentation_state<>'blocked'
        ORDER BY grp,rev.created_at DESC,d.id LIMIT %s''',
        ([str(i) for i in explicit], analysis, analysis, business, CANDIDATES)).fetchall()


def _label(row, check_state):
    period = (f"del {row['period_from']} al {row['period_until']}" if row['period_from'] and row['period_until']
              else 'periodo declarado desconocido')
    stale = row['stale_reason']
    state = f"caducado: {STALE.get(stale, stale)}" if stale else 'vigente'
    title = clip(row.get('title') or 'Informe', 120)
    return (f"Informe «{title}» del {row['delivered_at'].date().isoformat()} ({period}; {state}; "
            f"comprobación independiente {CHECKS.get(check_state, 'no disponible')}).")


def _warnings(derived):
    checks = derived.get('checks')
    if not checks:
        return []
    from ..engine import check_contract
    return [clip(i['message'] if i.get('coverage') else f"Cifra en revisión: {i['quote']} — {i['message']}", 200)
            for i in check_contract.visible(checks)['items']]


def _sections(row, derived):
    """Ordered optional sections; each is kept whole or dropped whole."""
    if row['origin'] != 'engine_blocks':
        return [['Extracto: ' + clip(derived['canonical_text'], 1200)]]
    projection = derived['document']
    sections = []
    for block in projection['blocks']:
        if block['type'] == 'cover':
            sections.append(['Titular: ' + clip(' '.join(blocks.block_lines(block)), 600)])
    if not sections:
        # Reports saved before the cover block usually open with a text.
        opening = next((b for b in projection['blocks'] if b['type'] == 'text'), None)
        if opening is not None:
            sections.append(['Apertura: ' + clip(' '.join(blocks.block_lines(opening)), 600)])
    for block in blocks.walk(projection['blocks']):
        if block['type'] != 'priority':
            continue
        lines = ['Prioridad: ' + clip(block['title'], 200)]
        # Reports without an action block state the diagnosis first and often the next
        # check last: keep the first and the last text of the priority, verbatim but clipped.
        texts = [c for c in blocks.walk(block['blocks']) if c['type'] == 'text']
        for label, text in (('Texto', texts[0] if texts else None), ('Texto final', texts[-1] if len(texts) > 1 else None)):
            if text is not None:
                lines.append(f'  {label}: ' + clip(' '.join(blocks.block_lines(text))))
        actions = sum(1 for child in blocks.walk(block['blocks']) if child['type'] == 'action')
        if actions:
            # Verbatim actions and their owner state live in the follow-up register, never repeated here as pending.
            lines.append(f'  Acciones propuestas: {actions}; están en el registro de seguimiento con el estado que les dio el propietario.')
        sections.append(lines)
    return sections


def _tail(warnings, shown):
    if not warnings:
        return []
    if not shown:
        return [f'Avisos de su comprobación: {len(warnings)}; ver la sección de comprobación de su fichero.']
    hidden = len(warnings) - shown
    more = [f'(y {hidden} aviso(s) más en la sección de comprobación de su fichero)'] if hidden else []
    return ['Avisos de su comprobación: ' + ' '.join(warnings[:shown] + more)]


def _summary(row, derived, check_state, budget):
    """Label, request and the existence of check warnings are always kept; sections fill the rest.

    The result never exceeds `budget` bytes: the omission note is reserved first, warnings
    beyond what fits are counted, not dropped silently, and sections are kept or dropped whole.
    """
    sections = _sections(row, derived)
    # Reserved for the largest possible omission count: every optional section.
    reserve = size(OMITTED.format(len(sections))) + 1 if sections else 0
    goal = row.get('goal') or ''
    for limit in (ITEM_CHARS, 100):
        head = [_label(row, check_state)] + (['Lo que se pidió: ' + clip(goal, limit)] if goal else [])
        warnings = _warnings(derived)
        shown = min(len(warnings), MAX_WARNINGS)
        while shown and size('\n'.join(head + _tail(warnings, shown))) + reserve > budget:
            shown -= 1
        tail = _tail(warnings, shown)
        if size('\n'.join(head + tail)) + reserve <= budget:
            break
    kept, omitted = [], 0
    used = size('\n'.join(head + tail)) + reserve
    for section in sections:
        cost = size('\n'.join(section)) + 1
        if used + cost > budget:
            omitted += 1
            continue
        kept += section
        used += cost
    if omitted:
        kept.append(OMITTED.format(omitted))
    return '\n'.join(head + kept + tail)


def _checks_section(checks):
    """The trailing check section, bounded; lines that do not fit are counted, never hidden."""
    if size(checks) <= CHECK_BYTES:
        return checks if checks.endswith('\n') else checks + '\n'
    lines, kept = checks.split('\n'), []
    for line in lines:
        if size('\n'.join(kept + [line])) > CHECK_BYTES - 120:
            break
        kept.append(line)
    dropped = sum(1 for line in lines[len(kept):] if line.strip())
    return '\n'.join(kept) + f'\n[{dropped} línea(s) de avisos no caben en este fichero.]\n'


def _file(text):
    """Full canonical text, or a truncated body that keeps its check section, with both hashes."""
    if size(text) <= FILE_BYTES:
        return text, False
    cut = text.rfind(CHECK_MARKER)
    body, checks = (text[:cut], _checks_section(text[cut:])) if cut >= 0 else (text, '')
    marker = ('\n[Texto recortado: el cuerpo del informe no cabe entero'
              + ('; se conserva su sección de comprobación' if checks else '')
              + f'. sha256 del texto completo: {sha(text)}]')
    fragment = '[sha256 de este fragmento: {}]\n'
    room = FILE_BYTES - size(marker) - size(checks) - size(fragment.format('0' * 64))
    raw = body.encode('utf-8')[:room].decode('utf-8', 'ignore')
    return raw + marker + checks + fragment.format(sha(raw)), True


def select(db, business, analysis, *, explicit=()):
    """The frozen, labelled prior-report history; locks are held until the caller commits."""
    with db.transaction():
        return _select(db, business, analysis, explicit)


def _select(db, business, analysis, explicit):
    memory.lock(db, business)
    rows = candidates(db, business, analysis, explicit)
    for row in sorted(rows, key=lambda r: str(r['id'])):
        store.lock(db, row['id'], shared=True)
    from . import reading
    chosen = []
    for row in rows:
        if len(chosen) == MAX_REPORTS:
            break
        current = db.execute('''SELECT d.deleted_at,d.current_revision_id FROM report_documents d WHERE d.business_id=%s AND d.id=%s''',
                             (business, row['id'])).fetchone()
        if not current or current['deleted_at'] or current['current_revision_id'] != row['current_revision_id']:
            continue
        revision = db.execute('SELECT * FROM report_document_revisions WHERE business_id=%s AND document_id=%s AND id=%s',
                              (business, row['id'], row['current_revision_id'])).fetchone()
        row['stale_reason'] = store.reason(db, row)
        derived = reading.derived_for(db, row, revision)
        if not derived or derived.get('status') != 'ready' or not derived.get('canonical_text'):
            continue
        # derived_for attaches the native check result; HTML reports have none.
        check_state = derived['checks']['state'] if derived.get('checks') else None
        chosen.append((row, revision, derived, check_state))
    budget = SUMMARY_BYTES // max(1, len(chosen))
    reports, files = [], {}
    for index, (row, revision, derived, check_state) in enumerate(chosen, 1):
        name = f'{FOLDER}/{index:02d}.txt'
        text, truncated = _file(derived['canonical_text'])
        files[name] = text
        reports.append(dict(
            file=name, document_id=str(row['id']), revision_id=str(revision['id']), origin=row['origin'],
            raw_sha256=revision['raw_sha256'], canonical_sha256=sha(derived['canonical_text']), file_sha256=sha(text),
            truncated=truncated, analysis_id=str(row['analysis_id']),
            dataset_id=str(row['dataset_id']) if row['dataset_id'] else None, dataset_version=row['dataset_version'],
            period={'from': str(row['period_from']) if row['period_from'] else None,
                    'until': str(row['period_until']) if row['period_until'] else None},
            delivered_at=row['delivered_at'].isoformat(), stale_reason=row['stale_reason'], check_state=check_state,
            group=row['grp'], summary=_summary(row, derived, check_state, budget)))
    manifest = dict(version=VERSION, rule=RULE,
                    reports=[{k: v for k, v in r.items() if k != 'summary'} for r in reports])
    if size(json.dumps(manifest, ensure_ascii=False)) > META_BYTES:
        raise ValueError('Prior report metadata exceeds its limit.')
    return dict(version=VERSION, rule=RULE, reports=reports), files, manifest


def current(db, business, history):
    """A saved history is still usable if each report keeps its revision and is not deleted.

    Later staleness of a prior report does not invalidate the history; it was labelled then.
    """
    for report in (history or {}).get('reports', []):
        row = db.execute('''SELECT d.deleted_at,d.current_revision_id,w.deleted_at AS job_deleted_at FROM report_documents d
            LEFT JOIN web_jobs w ON w.business_id=d.business_id AND w.report_document_id=d.id AND w.engine_run_id=d.source_run_id
            WHERE d.business_id=%s AND d.id=%s''', (business, report['document_id'])).fetchone()
        if not row or row['deleted_at'] or row['job_deleted_at'] or str(row['current_revision_id']) != report['revision_id']:
            return False
    return True
