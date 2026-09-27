"""Persistent material objections and an explicit audit of the client delivery."""
from typing import Literal

from pydantic import Field

from .contracts import Strict


class ReviewIssue(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    severity: Literal['blocker', 'suggestion']
    status: Literal['open', 'resolved']
    target: str = Field(min_length=1, max_length=200)
    detail: str = Field(min_length=1, max_length=800)
    resolution: str = Field(max_length=800)
    introduced_because: str = Field(max_length=800)


class DeliveryAudit(Strict):
    numbers: Literal['pass', 'fail']
    meaning: Literal['pass', 'fail']
    charts: Literal['pass', 'fail', 'not_applicable']
    coverage: Literal['pass', 'fail']
    files: Literal['pass', 'fail']


class ReviewAssessment(Strict):
    report_step: int = Field(ge=1)
    issues: list[ReviewIssue] = Field(max_length=16)
    delivery: DeliveryAudit


def ledger(conversation):
    """Latest state of every objection; nothing is erased by omission."""
    issues = {}
    for event in conversation:
        assessment = event['action'].get('assessment')
        if event.get('role') == 'reviewer' and assessment:
            for issue in assessment['issues']:
                previous = issues.get(issue['key'], {})
                issues[issue['key']] = {**issue, 'first_step': previous.get('first_step', event['step']),
                                        'last_step': event['step']}
    return list(issues.values())


def delivery_manifest(report, observations):
    if not report:
        return None
    charts = []
    for chart in report.get('charts', []):
        ref = chart.get('series')
        count = len(chart['points'])
        if ref:
            from ..series import saved_series
            try:
                count = len(saved_series(observations, ref)['points'])
            except (KeyError, ValueError, TypeError):
                count = None
        charts.append({'key': chart['key'], 'kind': chart['kind'], 'points': count, 'unit': chart['unit']})
    return {'claim_keys': [c['key'] for c in report['claims']], 'charts': charts,
            'question_coverage': report.get('question_coverage', []),
            'downloadable_execution_files': [],
            'note': 'Only report prose, cited values, highlights and these charts reach the client. Sandbox artifacts are not attachments.'}


def validate_assessment(action, role, context):
    assessment = action.assessment
    decisive = role == 'reviewer' and action.action in ('revise', 'approve', 'reject')
    if not decisive:
        if assessment is not None:
            raise ValueError('Only reviewer revise/approve/reject may supply assessment.')
        return
    if not context.get('review_policy'):
        return  # Historical runs retain their saved contract.
    if assessment is None or assessment.report_step != context['report_step']:
        raise ValueError('Review requires assessment of the exact current report_step.')
    issues = {i.key: i for i in assessment.issues}
    if len(issues) != len(assessment.issues):
        raise ValueError('Review issue keys must be unique.')
    previous = {i['key']: i for i in context.get('review_issues', [])}
    if not previous.keys() <= issues.keys():
        raise ValueError('Retain every prior issue key; explicitly resolve it with evidence instead of omitting it.')
    for key, issue in issues.items():
        if issue.status == 'resolved' and not issue.resolution.strip():
            raise ValueError('Resolved issues require an evidence-based resolution.')
        prior = previous.get(key)
        if prior and (prior['severity'] != issue.severity or prior['status'] == 'resolved' and issue.status == 'open') and not issue.introduced_because.strip():
            raise ValueError('Reopening or changing severity requires a concrete reason.')
        if not prior and any(e['role'] == 'reviewer' and e['action'].get('assessment') for e in context['conversation']) and not issue.introduced_because.strip():
            raise ValueError('A later new issue must explain the new evidence, changed draft or previously missed material defect.')
    blockers = [i for i in issues.values() if i.severity == 'blocker' and i.status == 'open']
    if action.action in ('revise', 'reject') and not blockers:
        raise ValueError('revise/reject requires an open material blocker; optional suggestions must not block approval.')
    if action.action == 'approve':
        if blockers or 'fail' in assessment.delivery.model_dump().values():
            raise ValueError('Cannot approve open material blockers or a failed delivery audit.')
        if context['report'].get('charts') and assessment.delivery.charts != 'pass':
            raise ValueError('Existing charts require an explicit passing chart audit.')
