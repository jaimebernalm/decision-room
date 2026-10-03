"""Deterministic P3 reading projection. Original report and evidence stay unchanged."""
from decimal import Decimal


def enabled(data):
    return bool(data.get('options', data.get('budgets', {})).get('owner_presentation'))


def readable_number(value):
    from .client_report import formatted
    value = Decimal(str(value))
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
    for text in report.get('limitations', []):
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


def guidance(claim):
    from .agent.delivery_contract import orientation_sections
    return [(heading, text) for heading, text in orientation_sections(claim.get('orientation'))
            if heading != 'Señal' or text != claim['statement']]
