"""Small, evidence-backed projection of an approved report for the home page."""

from ..agent.review_contract import ReportDraft, checks
from ..client_report import formatted, metric
from ..series import saved_series


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
            'label': item['label'],
            'value': formatted(metric(data, item['value']), item['decimals']),
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
            charts.append({
                'key': chart['key'], 'kind': chart['kind'], 'title': chart['title'],
                'unit': chart['unit'], 'caption': chart['caption'],
                'claim_key': chart['claim_key'],
                'points': [{'label': point['label'], 'value': str(point['value']),
                            'formatted': formatted(point['value'], chart['decimals'])}
                           for point in points],
            })
    except (ValueError, KeyError, ArithmeticError):
        return None
    return {
        'title': report['title'], 'summary': report['summary'],
        'scope': report['scope'], 'highlights': highlights,
        'claims': [{'key': claim['key'], 'title': claim['title'],
                    'statement': claim['statement']} for claim in report['claims'][:3]],
        'charts': charts, 'limitations': report['limitations'],
    }
