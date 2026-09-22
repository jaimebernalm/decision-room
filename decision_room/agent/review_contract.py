"""Typed dialogue and mechanical evidence checks; never proof of business meaning."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_UP
from typing import Literal

from pydantic import Field

from .contracts import Strict


class MetricRef(Strict):
    execution_id: str = Field(max_length=36)
    metric: str = Field(min_length=1, max_length=120)


class Claim(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    title: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=1800)
    evidence: list[MetricRef] = Field(min_length=1, max_length=12)
    interpretation: str = Field(min_length=1, max_length=1200)
    next_step: str = Field(max_length=1200)
    method: str = Field(min_length=1, max_length=1200)


class ReportScope(Strict):
    business: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=800)
    period: str = Field(min_length=1, max_length=200)
    coverage: str = Field(min_length=1, max_length=1200)


class ChartPoint(Strict):
    label: str = Field(min_length=1, max_length=100)
    value: MetricRef


class Chart(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    claim_key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    kind: Literal['bar', 'line', 'table']
    title: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=80)
    decimals: int = Field(ge=0, le=4)
    caption: str = Field(min_length=1, max_length=1200)
    points: list[ChartPoint] = Field(min_length=2, max_length=36)


class NumericCheck(Strict):
    key: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    operation: Literal['equal', 'sum', 'percent_change', 'ratio_percent', 'zero', 'nonnegative']
    actual: MetricRef
    operands: list[MetricRef] = Field(max_length=16)
    tolerance: str = Field(pattern=r'^0(?:\.\d{1,8})?$')


class ReportDraft(Strict):
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2400)
    scope: ReportScope
    charts: list[Chart] = Field(max_length=4)
    no_chart_reason: str = Field(max_length=600)
    claims: list[Claim] = Field(min_length=1, max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=12)
    checks: list[NumericCheck] = Field(max_length=16)


class ReviewAction(Strict):
    action: Literal['submit', 'revise', 'approve', 'reject', 'execute', 'ask_owner', 'withdraw']
    message: str = Field(min_length=1, max_length=2400)
    report: ReportDraft | None
    code: str = Field(max_length=48000)
    table_ids: list[str] = Field(max_length=8)
    question: str = Field(max_length=1200)


def checks(report, observations):
    """Resolve actual saved metrics and recompute declared numerical relationships."""
    if not report:
        return [{'check': 'report_present', 'passed': False, 'detail': 'No draft submitted.'}]
    available = {o['execution_id']: o for o in observations}
    result = []

    def value(ref):
        item = available.get(ref['execution_id'])
        if not item or not item['current'] or item['status'] != 'completed' or item.get('result_omitted'):
            raise ValueError('Evidence is missing, failed, obsolete or omitted.')
        payload = item['result']
        key = ref['metric']
        if key not in payload['metrics'] or not any(e['metric'] == key for e in payload['evidence']):
            raise ValueError('Metric or its source evidence does not exist.')
        return payload['metrics'][key]

    def number(ref):
        raw = value(ref)
        if isinstance(raw, bool) or raw is None or len(str(raw)) > 100:
            raise ValueError('Metric must be a finite numeric scalar.')
        v = Decimal(str(raw))
        if not v.is_finite() or (v and abs(v.adjusted()) > 100):
            raise ValueError('Numeric magnitude is outside comparison bounds.')
        return v

    for claim in report['claims']:
        try:
            for ref in claim['evidence']:
                value(ref)
            result.append({'check': 'evidence:' + claim['key'], 'passed': True, 'detail': 'Saved, current metrics with source evidence.'})
        except ValueError as error:
            result.append({'check': 'evidence:' + claim['key'], 'passed': False, 'detail': str(error)})
    for chart in report.get('charts', []):
        try:
            labels = [p['label'] for p in chart['points']]
            if len(set(labels)) != len(labels):
                raise ValueError('Chart labels must be unique.')
            if chart['claim_key'] not in {c['key'] for c in report['claims']}:
                raise ValueError('Chart must belong to an existing finding.')
            if chart['kind'] == 'line':
                dates = [date.fromisoformat(label) for label in labels]
                if dates != sorted(dates) or any(d.isoformat() != label for d, label in zip(dates, labels)):
                    raise ValueError('Line charts require ordered ISO dates.')
            for point in chart['points']:
                number(point['value'])
            result.append({'check': 'chart:' + chart['key'], 'passed': True, 'detail': 'Chart values resolve to finite, current saved metrics.'})
        except (ValueError, InvalidOperation, ArithmeticError) as error:
            result.append({'check': 'chart:' + chart['key'], 'passed': False, 'detail': str(error)})
    verified_percentages = set()
    for check in report['checks']:
        try:
            with localcontext() as ctx:
                ctx.prec = 40
                actual = number(check['actual'])
                values = [number(r) for r in check['operands']]
                if check['operation'] in ('zero', 'nonnegative'):
                    if values:
                        raise ValueError('zero/nonnegative require empty operands.')
                    expected = Decimal(0)
                elif check['operation'] == 'equal':
                    if len(values) != 1:
                        raise ValueError('equal requires one operand.')
                    if check['actual'] == check['operands'][0]:
                        raise ValueError('Comparing a metric with itself is not a check. Use zero/nonnegative or independent evidence.')
                    expected = values[0]
                elif check['operation'] == 'sum':
                    if not values or (len(values) == 1 and check['actual'] == check['operands'][0]):
                        raise ValueError('sum needs operands other than just the same metric.')
                    expected = sum(values)
                elif check['operation'] == 'ratio_percent':
                    if len(values) != 2 or not values[1]:
                        raise ValueError('ratio_percent requires [part, whole], with nonzero whole.')
                    expected = values[0] / values[1] * 100
                else:
                    if len(values) != 2 or not values[0]:
                        raise ValueError('percent_change requires [before, after], with nonzero before.')
                    expected = (values[1] - values[0]) / values[0] * 100
                passed = (actual >= -Decimal(check['tolerance']) if check['operation'] == 'nonnegative'
                          else abs(actual - expected) <= Decimal(check['tolerance']))
                if passed and check['operation'] in ('percent_change', 'ratio_percent'):
                    # Compare displayed text against recomputed arithmetic, not merely
                    # a stored value that passed an overly generous declared tolerance.
                    verified_percentages.add(expected)
            result.append({'check': check['key'], 'passed': passed, 'detail': f'Actual {actual}; recomputed {expected}.'})
        except (ValueError, InvalidOperation, ArithmeticError) as error:
            result.append({'check': check['key'], 'passed': False, 'detail': str(error)})
    def prose(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values(): yield from prose(item)
        elif isinstance(value, list):
            for item in value: yield from prose(item)
    for text in prose({k:v for k,v in report.items() if k != 'checks'}):
        for match in re.finditer(r'(?<![\w.,])([-+]?\d[\d.,]*)\s*%', text):
            raw = match.group(1)
            if ',' in raw and '.' in raw:
                decimal = ',' if raw.rfind(',') > raw.rfind('.') else '.'
                raw = raw.replace('.' if decimal == ',' else ',', '').replace(decimal, '.')
            else:
                raw = raw.replace(',', '.')
            try:
                with localcontext() as ctx:
                    ctx.prec = 120
                    value = Decimal(raw)
                    precision = Decimal(1).scaleb(value.as_tuple().exponent)
                    passed = any(value == expected.quantize(precision, rounding=ROUND_HALF_UP)
                                 for expected in verified_percentages)
            except InvalidOperation:
                passed = False
            result.append({'check': 'percentage_text', 'passed': passed,
                           'detail': match.group(0) + ': requires a matching recomputed percent_change/ratio_percent check.'})
    return result


def validate(raw, role, context):
    if isinstance(raw, dict):
        # Local models sometimes omit inapplicable empty fields. Supplying only
        # empty defaults never chooses an action, writes code or grants approval.
        raw = {'report': None, 'code': '', 'table_ids': [], 'question': '', **raw}
    action = ReviewAction.model_validate(raw)
    allowed = {'analyst': {'submit', 'execute', 'ask_owner', 'withdraw'},
               'reviewer': {'approve', 'revise', 'reject', 'execute', 'ask_owner'}}
    if action.action not in allowed[role]:
        raise ValueError('Only the reviewer may approve/reject/request changes; only the analyst submits drafts.')
    if action.action == 'submit':
        if action.report is None:
            raise ValueError('submit requires the complete updated report, including unchanged claims and limitations.')
        if not action.report.charts and not action.report.no_chart_reason.strip():
            raise ValueError('Explain why no chart is useful for this report.')
        chart_keys = [c.key for c in action.report.charts]
        if len(chart_keys) != len(set(chart_keys)) or sum(len(c.points) for c in action.report.charts) > 72:
            raise ValueError('Charts need unique keys and at most 72 points in total.')
        keys = [c.key for c in action.report.claims]
        check_keys = [c.key for c in action.report.checks]
        if len(keys) != len(set(keys)) or len(check_keys) != len(set(check_keys)):
            raise ValueError('Claim/check keys must be unique.')
        if any(len(s) > 1600 or not s.strip() for s in action.report.limitations):
            raise ValueError('Limitations must be nonempty, at most 1600 characters each.')
        structural = [c for c in checks(action.report.model_dump(), context['observations']) if c['check'].startswith(('evidence:', 'chart:'))]
        if any(not c['passed'] for c in structural):
            raise ValueError('Draft references unavailable evidence: ' + str(structural)[:1000])
    elif action.report is not None:
        raise ValueError('Only submit may include a report; the reviewer approves the exact current version.')
    if action.action == 'execute':
        permitted = {t['id'] for t in context['tables']}
        if not action.code.strip() or not action.table_ids or not set(action.table_ids) <= permitted or len(set(action.table_ids)) != len(action.table_ids):
            raise ValueError('execute requires code and unique authorized table IDs.')
        if context['budgets']['python_used'][role] >= context['budgets']['max_python_per_role']:
            raise ValueError('Python budget reached. Submit supported work, ask the owner or stop without approval.')
    elif action.code or action.table_ids:
        raise ValueError("Only action='execute' may include Python code or table_ids. If you intend to run Python, choose execute; otherwise clear both fields.")
    if action.action == 'ask_owner':
        if not action.question.strip():
            raise ValueError('ask_owner requires a concrete question.')
        if context['budgets']['questions_used'] >= context['budgets']['max_questions']:
            raise ValueError('Owner question budget reached; stop or use only supported evidence.')
        if any(e['action']['question'] == action.question for e in context['conversation'] if e['action']['action'] == 'ask_owner'):
            raise ValueError('This question was already asked. Read the stored answer or disposition.')
    elif action.question and not (role == 'reviewer' and action.action == 'revise'):
        raise ValueError('Only ask_owner or a reviewer revise may include a question; revise addresses the analyst.')
    if action.action == 'approve':
        if not context['report'] or not all(c['passed'] for c in context['checks']):
            raise ValueError('Cannot approve a missing report or one with failed mechanical checks.')
        # A new reviewer execution must be incorporated by the analyst before
        # approval so that its evidence or a failed check cannot be silently lost.
        draft_step = context['report_step']
        if any(e['step'] > draft_step and e['action']['action'] == 'execute' for e in context['conversation']):
            raise ValueError('New checks were executed after this draft. Request an updated draft before approval.')
    return action.model_dump()
