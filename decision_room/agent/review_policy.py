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


class QuestionUtility(Strict):
    investigation_key: str = Field(min_length=1, max_length=64)
    verdict: Literal['pass', 'fail', 'unavailable', 'deferred']
    claim_keys: list[str] = Field(max_length=6)
    reason: str = Field(min_length=1, max_length=1000)


class OwnerUtility(Strict):
    deliverable_index: int = Field(ge=0, le=11)
    verdict: Literal['pass', 'partial', 'unavailable', 'deferred', 'fail']
    claim_keys: list[str] = Field(max_length=6)
    reason: str = Field(min_length=1, max_length=1000)


class UsefulnessAudit(Strict):
    owner_deliverables: list[OwnerUtility] = Field(default_factory=list, max_length=12)
    decision_support: Literal['pass', 'fail', 'not_applicable'] = 'not_applicable'
    goal_alignment: Literal['pass', 'fail']
    reason: str = Field(min_length=1, max_length=1200)
    questions: list[QuestionUtility] = Field(max_length=24)


class ReviewAssessment(Strict):
    report_step: int = Field(ge=1)
    issues: list[ReviewIssue] = Field(max_length=16)
    delivery: DeliveryAudit
    usefulness: UsefulnessAudit | None = None


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
            'owner_coverage': report.get('owner_coverage', []),
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

    if context.get('review_policy', 0) >= 2:
        utility = assessment.usefulness
        if utility is None:
            raise ValueError('Review requires an explicit usefulness audit against the owner goal.')
        coverage = {q['investigation_key']: q for q in context['report']['question_coverage']}
        questions = {q.investigation_key: q for q in utility.questions}
        if len(questions) != len(utility.questions) or questions.keys() != coverage.keys():
            raise ValueError('Assess usefulness of every delivered question exactly once.')
        for key, item in questions.items():
            delivered = coverage[key]
            if set(item.claim_keys) != set(delivered['claim_keys']):
                raise ValueError('Usefulness must assess the actual delivered claim references.')
            if delivered['status'] == 'answered' and item.verdict in ('unavailable', 'deferred'):
                raise ValueError('An answered question cannot have unavailable usefulness.')
            if delivered['status'] != 'answered' and item.verdict == 'pass':
                raise ValueError('Undelivered work cannot pass as a useful delivered answer.')
            if ((item.verdict == 'deferred' and delivered['status'] != 'deferred') or
                    (delivered['status'] == 'deferred' and item.verdict not in ('deferred', 'fail'))):
                raise ValueError('Deferred work requires an explicit matching deferred usefulness assessment.')
        if action.action == 'approve' and (utility.goal_alignment != 'pass' or any(q.verdict == 'fail' for q in utility.questions)):
            raise ValueError('Cannot approve failed usefulness or misleading question coverage.')

    if context.get('review_policy', 0) >= 4:
        utility = assessment.usefulness
        delivered = {e['deliverable_index']: e for e in context['report']['owner_coverage']}
        audited = {e.deliverable_index: e for e in utility.owner_deliverables}
        if len(audited) != len(utility.owner_deliverables) or audited.keys() != delivered.keys():
            raise ValueError('Independently audit each owner deliverable exactly once.')
        verdicts = {'complete': ('pass', 'fail'), 'partial': ('partial', 'fail'),
                    'unavailable': ('unavailable', 'fail'), 'deferred': ('deferred', 'fail')}
        for key, item in audited.items():
            entry = delivered[key]
            if set(item.claim_keys) != set(entry['claim_keys']) or item.verdict not in verdicts[entry['status']]:
                raise ValueError('Owner usefulness must match actual delivered claims and partial/unavailable status.')
        oriented = any(c.get('orientation') for c in context['report']['claims'])
        if oriented and utility.decision_support == 'not_applicable':
            raise ValueError('Decision orientation requires an independent decision_support audit.')
        if action.action == 'approve' and (utility.decision_support == 'fail' or any(e.verdict == 'fail' for e in audited.values())):
            raise ValueError('Cannot approve unsupported reactions or failed owner deliverables.')


def prioritize_claims(report, synthesis):
    """Apply the principal's declared priority via explicit question/claim links.

    Stable order for ties and context-only claims. Never infer a priority from
    wording, chart size or numerical magnitude across incompatible measures.
    """
    if not synthesis:
        return
    ranks = {entry['investigation_key']: i for i, entry in enumerate(synthesis['priorities'])}
    linked = {}
    for entry in report['question_coverage']:
        if entry['investigation_key'] in ranks:
            for key in entry['claim_keys']:
                linked[key] = min(linked.get(key, len(ranks)), ranks[entry['investigation_key']])
    report['claims'].sort(key=lambda claim: linked.get(claim['key'], len(ranks)))
