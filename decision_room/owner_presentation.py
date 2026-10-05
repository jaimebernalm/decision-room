"""Deterministic P3 reading projection. Original report and evidence stay unchanged."""
from decimal import Decimal, InvalidOperation
from copy import deepcopy
import re


def enabled(data):
    return bool(data.get('options', data.get('budgets', {})).get('owner_presentation'))


def readable_number(value):
    from .client_report import formatted
    # Saved evidence can describe a dimension, date or missing value. Only
    # finite numbers receive numeric formatting; preserve everything else.
    original = value
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        return original
    if not value.is_finite():
        return original
    if not value:
        return '0'
    decimals = 2
    if value and abs(value) < Decimal('0.01'):
        # Keep two significant digits for tiny values instead of implying zero.
        decimals = max(2, 1 - value.adjusted())
        if decimals > 8:
            return f'{value:.1E}'.replace('.', ',')
    result = formatted(value, decimals)
    return result.rstrip('0').rstrip(',') if ',' in result else result


def limits(report, observations=None):
    """Move only explicitly marked limitations; never strip sentences from findings."""
    result, seen = [], set()
    def add(text):
        key = ' '.join(text.split())
        if key and key not in seen:
            seen.add(key)
            result.append(text)
    selection = set()
    if observations is not None:
        from .agent.delivery_selection import selection_notes
        selection = set(selection_notes(report, observations))
    controller_note = None
    if report.get('owner_coverage'):
        from .agent.research_agenda import limitation
        controller_note = ' '.join(limitation({}, report).split())
    for text in report.get('limitations', []):
        # Replace only the exact controller-generated counter. The complete
        # pending explanations are added below from structured owner coverage;
        # this also recovers text truncated in the 1600-character scope note.
        if text in selection or (controller_note and ' '.join(text.split()) == controller_note):
            continue
        if not delivery_note(text):
            add(text)
    for claim in report.get('claims', []):
        add((claim.get('orientation') or {}).get('limitation', ''))
    entries = report.get('owner_coverage') or report.get('question_coverage', [])
    for entry in entries:
        if entry['status'] not in ('complete', 'answered'):
            add(entry['explanation'])
    return result


def evidence_rows(data, refs):
    from .series import evidence_key, evidence_label, evidence_value
    rows, seen = [], set()
    names = {evidence_key(h['value']): h['label'] for h in data['report'].get('highlights', [])}
    for ref in refs:
        key = evidence_key(ref)
        if key in seen:
            continue
        seen.add(key)
        raw = str(evidence_value(data['observations'], ref))
        rows.append(dict(label=names.get(key, f'Cifra de apoyo {len(rows)+1}'), value=readable_number(raw),
                         raw_value=raw, reference=dict(ref), original_label=evidence_label(ref)))
    return rows


def delivery_note(text):
    """Only standalone software notes; never discard a mixed business paragraph."""
    text = text.strip()
    patterns = [
        r'Versión \d+[.]?',
        r'(?:La |El )?(?:exportación (?:HTML|del informe|del documento)|archivo HTML|HTML|renderizado)\b[^.!?;]*(?:no (?:ha sido |se ha |fue |está )?(?:verificad|validad|comprobad)[^.!?;]*|sin verificar)[.]?',
        r'No (?:se (?:ha )?(?:comprobó|comprobado|acredita|acreditó|acreditado|verificó|verificado)|consta|está acreditado)\b[^.!?;]*\b(?:informe|HTML)\b[^.!?;]*\bnavegador[.]?',
        r'(?:(?:Ver|Véase|Consultar) (?:el )?)?Anexo técnico[.]?',
    ]
    return any(re.fullmatch(pattern, text, re.I) for pattern in patterns)


def generic_caveat(text):
    """Narrow standalone caveats only; local qualifications stay with their claims."""
    if re.fullmatch(r'(?:(?:Estos |Los )?datos (?:son )?(?:sintéticos|simulados)|(?:Son |Se usan |Se utilizan )datos (?:sintéticos|simulados))[.]?', text, re.I):
        return 'synthetic'
    if re.fullmatch(r'(?:No (?:se puede (?:inferir|establecer)|demuestra|demuestran) causalidad|(?:Estos |Los )?datos no permiten (?:establecer|inferir) causalidad)[.]?', text, re.I):
        return 'causal'
    return None


def clean_reading(view):
    """Project known audit sentences out of owner prose; source report stays intact."""
    if not view.get('owner_presentation'):
        return view
    result = deepcopy(view)
    technical = list(result.get('technical_notes', []))
    caveats = {}
    def clean(text):
        kept = []
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÜÑ¿¡])', text.strip()):
            if delivery_note(sentence):
                if sentence not in technical:
                    technical.append(sentence)
            elif kind := generic_caveat(sentence):
                caveats.setdefault(kind, sentence)
            elif sentence:
                kept.append(sentence)
        return ' '.join(kept)
    for key in ('summary', 'no_chart_reason'):
        if result.get(key): result[key] = clean(result[key])
    result['scope']['coverage'] = clean(result['scope']['coverage'])
    for claim in result.get('claims', []):
        for field in ('statement', 'interpretation', 'next_step'):
            if claim.get(field): claim[field] = clean(claim[field])
        orientation = claim.get('orientation') or {}
        for field in ('signal', 'relative_priority', 'next_check', 'decision_value', 'limitation'):
            if orientation.get(field): orientation[field] = clean(orientation[field])
    for chart in result.get('charts', []):
        chart['caption'] = clean(chart['caption'])
    limits = [clean(text) for text in result.get('limitations', [])]
    result['limitations'] = list(dict.fromkeys(text for text in [*limits, *caveats.values()] if text))
    result['technical_notes'] = technical
    return result


def orientation(value):
    result = deepcopy(value)
    if not result:
        return result
    for reaction in result['reactions']:
        reaction['condition'] = re.sub(r'^(?:(?:si|if)\s+)+', '', reaction['condition'].strip(), flags=re.I).rstrip(':').strip()
    same = {' '.join(r['reaction'].split()).casefold().rstrip('.') for r in result['reactions']}
    if len(result['reactions']) > 1 and len(same) == 1:
        result['reaction_summary'] = 'Si ' + ' o si '.join(r['condition'] for r in result['reactions']) + ': ' + result['reactions'][0]['reaction']
        result['reactions'] = []
    return result


def guidance(claim):
    from .agent.delivery_contract import orientation_sections
    value = orientation(claim.get('orientation'))
    sections = [(heading, text) for heading, text in orientation_sections(value)
                if heading != 'Señal' or text != claim['statement']]
    if value and value.get('reaction_summary'):
        sections.append(('En los casos descritos', value['reaction_summary']))
    return sections


def source_summary(files, period):
    """A bounded source note, never a dump of metrics, SQL or daily rows."""
    names = ', '.join(files)
    source = names if len(names) <= 180 else ('1 archivo del análisis' if len(files) == 1 else f'{len(files)} archivos del análisis')
    parts = [f'Datos utilizados: {source}.'] if source else []
    if period and len(period) <= 140:
        parts.append(f'Periodo: {period}.')
    return ' '.join(parts)


def business_point_labels(chart):
    """Replace layer-generated IDs using reviewed series names and periods."""
    mapping = {c['label']: c['series'] + ' · ' + c['category']
               for panel in chart['panels'] for c in panel['coordinates']}
    if len(set(mapping.values())) != len(mapping):
        return  # Never merge distinct coordinates.
    for point in chart['points']:
        point['original_label'] = point['label']
        point['label'] = mapping.get(point['label'], point['label'])
    for panel in chart['panels']:
        for coordinate in panel['coordinates']:
            coordinate['label'] = mapping.get(coordinate['label'], coordinate['label'])
    for detail in chart['details']:
        detail['point_label'] = mapping.get(detail['point_label'], detail['point_label'])
