"""Small, evidence-backed projection of an approved report for the home page."""
from ..owner_presentation import enabled, readable_number, limits, evidence_rows, delivery_note, source_summary, clean_reading
from ..series import evidence_key, evidence_label

import hashlib
import json

from ..agent.review_contract import ReportDraft, checks
from ..client_report import formatted, metric
from ..series import saved_series
from ..chart_layout import panels, series_colors
from ..periods import infer_grain
from ..chart_evidence import resolve_chart, series_refs


def client_orientation(claim, owner=False):
    value = claim.get('orientation')
    if owner:
        from ..owner_presentation import orientation
        value = orientation(value)
    return {k: ('' if owner and k == 'limitation' else v) for k, v in value.items() if k != 'evidence'} if value else None


def _projection(data):
    """Return only reviewed content; callers must also check current publication."""
    owner = enabled(data)
    number = (lambda value, decimals: readable_number(value)) if owner else formatted
    report = data.get('report')
    if not (data.get('publishable') and data.get('status') == 'approved' and report):
        return None
    try:
        ReportDraft.model_validate(report)
        if not all(check['passed'] for check in checks(report, data['observations'])):
            return None
        highlights = [{
            'key': hashlib.sha256(json.dumps([item['label'], item['unit'], item['claim_key']], sort_keys=True, default=str).encode()).hexdigest()[:16],
            'label': item['label'],
            'value': number(metric(data, item['value']), item['decimals']),
            'raw_value': str(metric(data, item['value'])), 'decimals': item['decimals'],
            'unit': item['unit'],
            'claim_key': item['claim_key'],
        } for item in report.get('highlights', [])]
        charts = []
        for chart in report['charts']:
            chart, points = resolve_chart(chart, data['observations'])
            grain = (chart.get('encoding') or {}).get('temporal_grain') or chart.get('temporal_grain')
            if chart['kind'] == 'line' and not chart.get('encoding'):
                grain = saved_series(data['observations'], chart['series'])['grain'] if chart.get('series') else grain or infer_grain([p['label'] for p in points])
            charts.append({
                **({'owner_presentation': True} if owner else {}),
                'key': chart['key'], 'kind': chart['kind'], 'title': chart['title'], 'scale': chart.get('scale', 'zero'),
                'unit': chart['unit'], 'caption': chart['caption'], 'decimals': chart['decimals'],
                'claim_key': chart['claim_key'],
                'temporal_grain': grain,
                'panels': panels(chart, points),
                'details': [{**{k: d.get(k) for k in ('point_label','claim_key','detail_chart_key')},
                    'values': [{'label': v['label'], 'unit': v['unit'], 'formatted': number(metric(data,v['value']),v['decimals'])} for v in d['values']]}
                    for d in chart.get('details', [])],
                'points': [{'label': point['label'], 'value': str(point['value']),
                            'formatted': number(point['value'], chart['decimals'])}
                           for point in points],
            })
            if owner and chart.get('layers'):
                from ..owner_presentation import business_point_labels
                business_point_labels(charts[-1])
        colors = series_colors(s for chart in charts for panel in chart['panels'] for s in panel['series_order'])
        for chart in charts:
            for panel in chart['panels']:
                panel['colors'] = {s: colors[s] for s in panel['series_order']}
    except (ValueError, KeyError, ArithmeticError):
        return None
    return {
        **({'owner_presentation': True} if owner else {}),
        'title': report['title'], 'summary': report['summary'],
        'partial': (any(q['status'] != 'complete' for q in report['owner_coverage']) if report.get('owner_coverage')
                    else any(q['status'] != 'answered' for q in report.get('question_coverage', []))),
        'scope': report['scope'], 'highlights': highlights,
        'claims': [{'key': claim['key'], 'title': claim['title'],
                    'statement': claim['statement'], 'orientation': client_orientation(claim, owner)} for claim in report['claims'][:3]],
        'charts': charts, 'limitations': limits(report, data['observations']) if owner else report['limitations'],
        **({'technical_notes': [t for t in report['limitations'] if delivery_note(t)]} if owner else {}),
    }


def projection(data):
    view = _projection(data)
    return clean_reading(view) if view is not None else None


def presentation(data):
    """Complete React report, derived only from the approved evidence contract."""
    result = _projection(data)
    if result is None:
        from .errors import WebError
        raise WebError('El informe necesita una nueva revisión.', 409)
    report = data['report']
    claims = []
    for claim in report['claims']:
        charts = [c for c in report['charts'] if c['claim_key'] == claim['key']]
        refs = claim['evidence'] + (claim.get('orientation') or {}).get('evidence', []) + [p['value'] for c in charts for p in c['points']]
        refs += [h['value'] for h in report.get('highlights', []) if h['claim_key'] == claim['key']]
        refs += [v['value'] for c in charts for d in c.get('details', []) for v in d['values']]
        selected = {ref['execution_id'] for ref in refs}
        selected.update(c['series']['execution_id'] for c in charts if c.get('series'))
        selected.update(ref['execution_id'] for c in charts for ref in series_refs(c))
        files = sorted({name for o in data['observations'] if o['execution_id'] in selected
                        for item in o['inputs'].values() for name in item['original_names']})
        metrics, seen = [], set()
        for ref in refs:
            key = evidence_key(ref)
            if key not in seen:
                seen.add(key)
                metrics.append({'label': evidence_label(ref), 'value': str(metric(data, ref))})
        operations = [saved_series(data['observations'], ref)['evidence']['operation']
                      for c in charts for ref in series_refs(c)]
        if enabled(data):
            metrics = evidence_rows(data, refs)
            operations += [entry['operation'] for observation in data['observations']
                           if observation['execution_id'] in selected
                           for entry in (observation.get('result') or {}).get('evidence', [])
                           if entry.get('operation')]
            operations = list(dict.fromkeys(operations))
        source = ({'source_summary': source_summary(files, (claim.get('orientation') or {}).get('period') or report['scope']['period'])}
                  if enabled(data) else {})
        claims.append({**source, **{key: claim[key] for key in ('key', 'title', 'statement', 'interpretation', 'method', 'next_step')},
                       'orientation': client_orientation(claim, enabled(data)),
                       'evidence_details': dict(files=files, metrics=metrics, operations=operations)})
    identity = dict(report_id=str(data['id']), report_version=data['approved_sha256']) if data.get('id') and data.get('approved_sha256') else {}
    return clean_reading({**result, **identity, 'claims': claims, 'no_chart_reason': report['no_chart_reason'], 'question_coverage': report.get('question_coverage', []), 'owner_coverage': report.get('owner_coverage', [])})
