"""Accuracy condition of the engine's step-3 gate (preregistration v4, section 6.3).

An independent auditor, blind to the system, records every figure of each report as in the
step-1 audit (cita, valor_informe, clase, sostiene_prioridad_v3, ...). The auditor decides the
denominator; the engine's own verification only says how each figure was labelled. This module
joins the two and computes, per report and per arm:

- every calculable figure that supports a priority is verified and correct;
- at least 95 % of the other calculable figures are verified;
- no erroneous figure is labelled verified.

Engine labels follow the export contract (reports/verification_contract.py): a figure is an
occurrence (JSON Pointer path + Unicode span) in draft.verified.json with a boolean `verified`;
`corrected` alone does not mean verified. An auditor entry joins one occurrence: the one whose
span lies inside the auditor's quote, located in that field. No match, or more than one match,
counts as not verified; the join never picks a duplicate by value nor spreads a label to several.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

CORRECT = ('correcta', 'redondeo')
CALCULABLE = ('correcta', 'redondeo', 'error', 'ambigua')
OTHERS_THRESHOLD = 0.95
SAME_LENGTH = str.maketrans({'\u00a0': ' ', '\u202f': ' ', '\u2009': ' ', '\u2212': '-', '\u2013': '-'})


def normal(text):
    text = unicodedata.normalize('NFKC', str(text or '')).translate(SAME_LENGTH).lower()
    return re.sub(r'\s+', ' ', text).strip()


def within(part, text):
    """part appears in text as whole tokens: '4 %' is not inside '14 %' nor '4,5 %'."""
    return bool(part) and re.search(r'(?<![\w.,])' + re.escape(part) + r'(?![\w]|[.,]\d)', text) is not None


def pointer(document, path):
    value = document
    for part in path[1:].split('/') if path else []:
        part = part.replace('~1', '/').replace('~0', '~')
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def quoted(cita, field):
    """Character ranges of field where the auditor's quote appears, ignoring case and spacing."""
    words = str(cita or '').translate(SAME_LENGTH).split()
    if not words or not isinstance(field, str):
        return []
    pattern = r'\s+'.join(re.escape(w) for w in words)
    return [m.span() for m in re.finditer(pattern, field.translate(SAME_LENGTH), flags=re.I)]


def label(entry, figures, document=None):
    """Engine state of one auditor entry: 'verified', the status of an unverified occurrence,
    'unmarked' (no occurrence) or 'ambiguous' (several and no way to tell them apart)."""
    cita, value = normal(entry.get('cita')), normal(entry.get('valor_informe'))
    shown = lambda f: within(value, normal(f.get('text'))) if value else within(normal(f.get('text')), cita)
    found = []
    if document is not None:
        for f in figures:
            try:
                ranges = quoted(entry.get('cita'), pointer(document, f['path']))
            except (KeyError, IndexError, ValueError, TypeError):
                continue
            if shown(f) and any(a <= f['span']['start'] and f['span']['end'] <= b for a, b in ranges):
                found.append(f)
    if not found:  # the quote spans several fields or was not located: fall back to visible text
        found = [f for f in figures if within(normal(f.get('text')), cita) and shown(f)]
    if not found:
        return 'unmarked'
    if len(found) > 1:
        return 'ambiguous'
    return 'verified' if found[0].get('verified') is True else found[0].get('status') or 'unverified'


def report(entries, figures, document=None):
    rows = [{**e, 'estado_motor': label(e, figures, document)} for e in entries]
    calculable = [r for r in rows if r.get('clase') in CALCULABLE]
    priority = [r for r in calculable if r.get('sostiene_prioridad_v3')]
    others = [r for r in calculable if not r.get('sostiene_prioridad_v3')]
    verified = lambda r: r['estado_motor'] == 'verified'
    priority_ok = [r for r in priority if verified(r) and r['clase'] in CORRECT]
    others_verified = [r for r in others if verified(r)]
    errors = [r for r in rows if r.get('clase') == 'error']
    share = len(others_verified) / len(others) if others else None
    result = {
        'figures': len(rows), 'calculable': len(calculable),
        'priority': len(priority), 'priority_verified_correct': len(priority_ok),
        'others': len(others), 'others_verified': len(others_verified), 'others_share': share,
        'errors': len(errors), 'errors_labelled_verified': sum(verified(r) for r in errors),
        'uncertain': sum(r['estado_motor'] == 'uncertain' for r in rows),
        'unmarked': sum(r['estado_motor'] == 'unmarked' for r in rows),
        'ambiguous': sum(r['estado_motor'] == 'ambiguous' for r in rows),
        'not_calculable': sum(r.get('clase') == 'no_calculable' for r in rows),
        'by_status': {s: sum(r['estado_motor'] == s for r in rows) for s in sorted({r['estado_motor'] for r in rows})},
        'error_rows': [{k: r.get(k) for k in ('cita', 'valor_informe', 'valor_esperado', 'severidad', 'estado_motor')}
                       for r in errors],
    }
    result['conditions'] = {
        'priority_all_verified_correct': len(priority_ok) == len(priority),
        'others_at_least_95': share is None or share >= OTHERS_THRESHOLD,
        'no_error_labelled_verified': result['errors_labelled_verified'] == 0,
    }
    result['passed'] = all(result['conditions'].values())
    return result


def arm(reports):
    """reports: {job: (auditor entries, engine figures, verified document)}. The arm passes only if
    every report does and every report was audited; totals are informative."""
    per = {job: report(*parts) for job, parts in sorted(reports.items())}
    keys = ('figures', 'calculable', 'priority', 'priority_verified_correct', 'others', 'others_verified',
            'errors', 'errors_labelled_verified', 'uncertain', 'unmarked', 'ambiguous')
    totals = {k: sum(r[k] for r in per.values()) for k in keys}
    totals['others_share'] = totals['others_verified'] / totals['others'] if totals['others'] else None
    return {'reports': per, 'totals': totals, 'audited': len(per),
            'passed': bool(per) and all(r['passed'] for r in per.values()),
            'note': 'Accuracy condition only; the gate also needs readers, the signal judge and zero lost reports.'}


def load(audit_path, batch, jobs=None):
    """audit_path: the auditor's JSON, {job: {'registro_cifras': [...]}} after unblinding.
    Each job's engine labels come from jobs/<job>/engine/verification.json and its verified
    document from draft.verified.json beside it; a missing export leaves every figure unmarked."""
    audit = json.loads(Path(audit_path).read_text())
    reports = {}
    for job, body in audit.items():
        if jobs and job not in jobs:
            continue
        export = Path(batch) / 'jobs' / job / 'engine'
        read = lambda name, default: json.loads((export / name).read_text()) if (export / name).exists() else default
        reports[job] = (body['registro_cifras'], read('verification.json', {}).get('figures', []),
                        read('draft.verified.json', None))
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('audit', type=Path, help='Unblinded auditor register, kept outside the batch')
    parser.add_argument('batch', type=Path)
    parser.add_argument('--job', action='append', help='Restrict to these engine jobs')
    args = parser.parse_args()
    print(json.dumps(arm(load(args.audit, args.batch, args.job)), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
