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


def limits(report):
    """Move only explicitly marked limitations; never strip sentences from findings."""
    result, seen = [], set()
    def add(text):
        key = ' '.join(text.split())
        if key and key not in seen:
            seen.add(key)
            result.append(text)
    controller_note = None
    if report.get('owner_coverage'):
        from .agent.research_agenda import limitation
        controller_note = ' '.join(limitation({}, report).split())
    for text in report.get('limitations', []):
        # Replace only the exact controller-generated counter. The complete
        # pending explanations are added below from structured owner coverage;
        # this also recovers text truncated in the 1600-character scope note.
        if controller_note and ' '.join(text.split()) == controller_note:
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
    """Recognize standalone software delivery notes, never general data caveats."""
    return bool(re.match(r'^(?:Versión \d+\b|(?:La |El )?(?:exportación (?:HTML|del informe|del documento)|archivo HTML|HTML|renderizado)\b.*(?:no (?:ha sido |se ha |fue |está )?(?:verificad|validad|comprobad)|sin verificar))', text.strip(), re.I))


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
