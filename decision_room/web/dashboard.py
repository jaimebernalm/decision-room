"""Small, evidence-backed projection of an approved report for the home page."""
from ..series import evidence_key, evidence_label

import hashlib
import json

from ..agent.review_contract import ReportDraft, checks
from ..client_report import formatted, metric
from ..series import saved_series
from ..chart_layout import panels, series_colors
from ..periods import infer_grain


def client_orientation(claim):
    value = claim.get('orientation')
    return {k: v for k, v in value.items() if k != 'evidence'} if value else None


def projection(data):
    """Return only reviewed content; callers must also check current publication."""
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
            'value': formatted(metric(data, item['value']), item['decimals']),
            'raw_value': str(metric(data, item['value'])), 'decimals': item['decimals'],
            'unit': item['unit'],
            'claim_key': item['claim_key'],
        } for item in report.get('highlights', [])]
        charts = []
        for chart in report['charts']:
            points = (saved_series(data['observations'], chart['series'])['points']
                      if chart.get('series') else [
                          {'label': point['label'], 'value': metric(data, point['value'])}
                          for point in chart['points']
                      ])
            grain = (chart.get('encoding') or {}).get('temporal_grain') or chart.get('temporal_grain')
            if chart['kind'] == 'line' and not chart.get('encoding'):
                grain = saved_series(data['observations'], chart['series'])['grain'] if chart.get('series') else grain or infer_grain([p['label'] for p in points])
            charts.append({
                'key': chart['key'], 'kind': chart['kind'], 'title': chart['title'], 'scale': chart.get('scale', 'zero'),
                'unit': chart['unit'], 'caption': chart['caption'], 'decimals': chart['decimals'],
                'claim_key': chart['claim_key'],
                'temporal_grain': grain,
                'panels': panels(chart, points),
                'details': [{**{k: d.get(k) for k in ('point_label','claim_key','detail_chart_key')},
                    'values': [{'label': v['label'], 'unit': v['unit'], 'formatted': formatted(metric(data,v['value']),v['decimals'])} for v in d['values']]}
                    for d in chart.get('details', [])],
                'points': [{'label': point['label'], 'value': str(point['value']),
                            'formatted': formatted(point['value'], chart['decimals'])}
                           for point in points],
            })
        colors = series_colors(s for chart in charts for panel in chart['panels'] for s in panel['series_order'])
        for chart in charts:
            for panel in chart['panels']:
                panel['colors'] = {s: colors[s] for s in panel['series_order']}
    except (ValueError, KeyError, ArithmeticError):
        return None
    return {
        'title': report['title'], 'summary': report['summary'],
        'partial': (any(q['status'] != 'complete' for q in report['owner_coverage']) if report.get('owner_coverage')
                    else any(q['status'] != 'answered' for q in report.get('question_coverage', []))),
        'scope': report['scope'], 'highlights': highlights,
        'claims': [{'key': claim['key'], 'title': claim['title'],
                    'statement': claim['statement'], 'orientation': client_orientation(claim)} for claim in report['claims'][:3]],
        'charts': charts, 'limitations': report['limitations'],
    }


def presentation(data):
    """Complete React report, derived only from the approved evidence contract."""
    result = projection(data)
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
        files = sorted({name for o in data['observations'] if o['execution_id'] in selected
                        for item in o['inputs'].values() for name in item['original_names']})
        metrics, seen = [], set()
        for ref in refs:
            key = evidence_key(ref)
            if key not in seen:
                seen.add(key)
                metrics.append({'label': evidence_label(ref), 'value': str(metric(data, ref))})
        operations = [saved_series(data['observations'], c['series'])['evidence']['operation']
                      for c in charts if c.get('series')]
        claims.append({**{key: claim[key] for key in ('key', 'title', 'statement', 'interpretation', 'method', 'next_step')},
                       'orientation': client_orientation(claim),
                       'evidence_details': dict(files=files, metrics=metrics, operations=operations)})
    identity = dict(report_id=str(data['id']), report_version=data['approved_sha256']) if data.get('id') and data.get('approved_sha256') else {}
    return {**result, **identity, 'claims': claims, 'no_chart_reason': report['no_chart_reason'], 'question_coverage': report.get('question_coverage', []), 'owner_coverage': report.get('owner_coverage', [])}
