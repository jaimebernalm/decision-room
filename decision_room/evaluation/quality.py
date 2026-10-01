"""Independent, fail-closed report acceptance and paired mode comparison."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from statistics import median

from .assess import token_accounting

RUBRIC = ('meaning', 'coverage', 'depth', 'priority', 'next_checks',
          'comparability', 'clarity', 'nonduplication', 'narrative_numbers')
RUBRIC_39 = (*RUBRIC, 'decision_support', 'visual_integrity', 'source_uncertainty')
REQUIRED = {'organize': ('meaning', 'coverage', 'clarity', 'narrative_numbers'),
            'question': ('meaning', 'coverage', 'narrative_numbers'),
            'discover': ('meaning', 'depth', 'priority', 'next_checks', 'narrative_numbers')}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def ref_key(ref):
    return json.dumps(ref, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def delivered_values(review):
    """Expand every delivered reference, including orientation and saved tooltip values."""
    report = review.get('report') or {}
    observations = {str(o['execution_id']): o for o in review.get('observations', [])}
    refs = [r for c in report.get('claims', []) for r in c['evidence']]
    refs += [r for c in report.get('claims', [])
             for r in (c.get('orientation') or {}).get('evidence', [])]
    refs += [h['value'] for h in report.get('highlights', [])]
    for chart in report.get('charts', []):
        refs += [v['value'] for detail in chart.get('details', []) for v in detail['values']]
        if chart.get('series'):
            r = chart['series']
            o = observations[r['execution_id']]
            series = o['result']['series'][r['series']]
            if chart['unit'] != series['unit']:
                raise ValueError('Chart unit disagrees with source')
            refs += [{**r, 'label': p['label']} for p in series['points']]
        else:
            refs += [p['value'] for p in chart['points']]
    values = {}
    for ref in refs:
        o = observations[ref['execution_id']]
        if o['status'] != 'completed' or not o.get('current') or o.get('result_omitted'):
            raise ValueError('Unavailable/stale evidence')
        if 'metric' in ref:
            value = o['result']['metrics'][ref['metric']]
        else:
            points = o['result']['series'][ref['series']]['points']
            found = [p['value'] for p in points if p['label'] == ref['label']]
            if len(found) != 1:
                raise ValueError('Missing or duplicate series label')
            value = found[0]
        values[ref_key(ref)] = value
    return values


def expected_value(binding, metrics):
    """Only declared oracle keys and arithmetic; no agent code or literal answers."""
    if isinstance(binding, str):
        return metrics[binding]
    op, args = binding['op'], binding['args']
    if not isinstance(args, list) or not 1 <= len(args) <= 100:
        raise ValueError('Invalid reference expression')
    if op == 'format':
        # Some saved citations contain several labelled values in one string.
        # Every value still comes from oracle expressions, never literal answers.
        from string import Formatter
        template = binding.get('template', '')
        if not isinstance(template, str) or len(template) > 16000:
            raise ValueError('Invalid reference text template')
        used, parts = set(), []
        for literal, field, spec, conversion in Formatter().parse(template):
            if any(c.isdigit() for c in literal) or conversion:
                raise ValueError('Reference text cannot embed literal numbers or conversions')
            parts.append(literal)
            if field is None:
                continue
            if not field.isdigit() or int(field) >= len(args) or spec not in ('', *[f'.{n}f' for n in range(13)]):
                raise ValueError('Use positional source values and bounded decimal formatting')
            index = int(field); used.add(index)
            value = expected_value(args[index], metrics)
            parts.append(format(Decimal(str(value)), spec) if spec else str(value))
        if used != set(range(len(args))):
            raise ValueError('Every reference value must appear in the text')
        return ''.join(parts)
    if op == 'text':
        if len(args) != 1 or not isinstance(args[0], str) or not isinstance(metrics[args[0]], str):
            raise ValueError('Text must come from a source reference value')
        return metrics[args[0]]
    if op == 'name':
        if len(args) != 1 or not isinstance(args[0], str) or args[0] not in metrics:
            raise ValueError('Name must come from a source reference key')
        key = args[0]
        if '|' in key:
            return key.split('|')[1]
        parts = key.split(':')
        if parts[0] in ('product', 'category', 'customer') or parts[0] == 'change' and parts[1] in ('product', 'category', 'customer'):
            return ':'.join(parts[2:-1])
        raise ValueError('Unknown name dimension')
    if op == 'join_names':
        separator = binding.get('separator', ' × ')
        if separator not in (' × ', ' | ', ' · ', ' - ', ' / ', ' + '):
            raise ValueError('Unsupported label separator')
        return separator.join(str(expected_value(a, metrics)) for a in args)
    values = [Decimal(str(expected_value(a, metrics))) for a in args]
    if op == 'count':
        return len(values)
    if op == 'positive_count':
        return sum(v > 0 for v in values)
    if op == 'negative_count':
        return sum(v < 0 for v in values)
    if op == 'sum':
        return sum(values)
    if len(values) != 2:
        raise ValueError('Binary reference expression needs two operands')
    a, b = values
    if op == 'difference':
        return b - a
    if op == 'equal':
        return a == b
    if op == 'ratio':
        return a / b
    if op == 'ratio_percent':
        return a / b * 100
    if op == 'percent_change':
        return (b - a) / a * 100
    raise ValueError('Unsupported oracle operation')


def reference_keys(binding):
    """Source anchors may support a directly requested change or ratio, too."""
    if isinstance(binding, str):
        return {binding}
    if isinstance(binding, dict) and isinstance(binding.get('args'), list):
        return set().union(*(reference_keys(arg) for arg in binding['args']))
    return set()


def assess(state, review, oracle, assessment=None):
    checks = {}
    checks['source_stable'] = state.get('source_stable') is True
    checks['completed'] = state.get('status') == 'completed'
    checks['approved'] = review.get('publishable') is True and review.get('status') == 'approved'
    checks['recovery'] = state.get('resume_idempotent') is True
    checks['mechanical'] = bool(review.get('checks')) and all(c['passed'] for c in review.get('checks', []))
    try:
        values = delivered_values(review)
        checks['resolvable'] = bool(values)
    except (KeyError, TypeError, ValueError):
        values = {}; checks['resolvable'] = False
    if assessment is None:
        return dict(accepted=False, status='needs_independent_review' if all(checks.values()) else 'failed', checks=checks)
    checks['exact_delivery'] = assessment.get('report_sha256') == digest(review.get('report'))
    checks['independent_review'] = assessment.get('reviewer') == 'development_review' and bool(assessment.get('notes', '').strip())
    rubric = assessment.get('rubric', {})
    version = assessment.get('rubric_version', 1)
    criteria = RUBRIC_39 if version == 2 else RUBRIC
    checks['rubric_complete'] = version in (1, 2) and set(rubric) == set(criteria) and all(
        type(v.get('score')) is int and 0 <= v['score'] <= 2 and bool(v.get('reason', '').strip()) for v in rubric.values())
    # 0 = material failure, 1 = useful but limited, 2 = meets the criterion fully.
    checks['no_material_failure'] = checks['rubric_complete'] and all(v['score'] >= 1 for v in rubric.values())
    checks['intent_quality'] = checks['rubric_complete'] and all(rubric[k]['score'] == 2 for k in REQUIRED[state['intent']])
    if version == 2:
        # Semantic review applies equally to historical and new contracts. Fields
        # alone cannot establish an appropriate visual, reaction or source basis.
        required = ('visual_integrity', 'source_uncertainty')
        if state['intent'] == 'discover':
            required += ('decision_support', 'clarity')
        checks['delivery_quality'] = checks['rubric_complete'] and all(rubric[k]['score'] == 2 for k in required)
    bindings = assessment.get('bindings', {})
    checks['all_delivered_values_bound'] = bool(values) and set(bindings) == set(values)
    targets = set()
    for key, value in values.items():
        binding = bindings.get(key, {})
        target = binding.get('reference')
        targets.update(reference_keys(target))
        passed = False
        try:
            # Explicit semantic mapping required; matching one convenient number is not acceptance.
            expected = expected_value(target, {**oracle['metrics'], **{'count|' + k: v for k, v in oracle.get('counts', {}).items()}})
            if isinstance(expected, bool):
                passed = type(value) is bool and value == expected and bool(binding['meaning'].strip())
            elif isinstance(target, dict) and target.get('op') in ('name', 'join_names', 'text', 'format'):
                passed = value == expected and bool(binding['meaning'].strip())
            else:
                actual, wanted = Decimal(str(value)), Decimal(str(expected))
                passed = actual.is_finite() and wanted.is_finite() and abs(actual - wanted) <= Decimal('0.011') and bool(binding['meaning'].strip())
        except (KeyError, InvalidOperation, TypeError, ValueError, ZeroDivisionError):
            pass
        checks['value:' + key] = passed
    if version == 2 and state['intent'] == 'discover':
        # Discovery permits evidence-backed selections. A fixed list of global
        # totals must not reject a useful category/product comparison merely
        # because its source anchors have a different shape. The independent
        # reviewer judges requested scope and periods; all delivered values
        # still require exact source bindings. Factual/dashboard anchors and
        # the historical instrument retain their original checks.
        checks['required_results'] = (checks['rubric_complete'] and bool(values)
            and rubric['coverage']['score'] >= 1 and rubric['comparability']['score'] == 2)
    else:
        checks['required_results'] = bool(oracle.get('required')) and set(oracle['required']) <= targets
    accepted = all(checks.values())
    coverage = (review.get('report') or {}).get('owner_coverage')
    partial = (any(q['status'] != 'complete' for q in coverage) if coverage
               else any(q['status'] != 'answered' for q in (review.get('report') or {}).get('question_coverage', [])))
    return dict(accepted=accepted, status='passed' if accepted else 'failed', checks=checks,
                rubric=rubric, rubric_version=version, partial=partial)


def resources(calls, complete=True, rates=None):
    """USD estimate only with explicit dated rates; unknown usage never becomes zero."""
    result = dict(calls=len(calls), **token_accounting(calls, complete), estimated_cost=None)
    if rates is None:
        return result
    if not rates.get('source') or not rates.get('as_of') or any(
        Decimal(str(rates[k])) < 0 for k in ('input_per_million', 'cached_input_per_million', 'output_per_million')):
        raise ValueError('Provide nonnegative rates, provenance and date')
    if not result['token_usage_complete']:
        return result
    cached = 0
    for call in calls:
        usage = call['usage']
        count = usage.get('prompt_tokens_details', {}).get('cached_tokens')
        if type(count) is not int or not 0 <= count <= usage.get('prompt_tokens', 0):
            return result
        cached += count
    cost = ((Decimal(result['input_tokens'] - cached) * Decimal(str(rates['input_per_million'])))
            + Decimal(cached) * Decimal(str(rates['cached_input_per_million']))
            + Decimal(result['output_tokens']) * Decimal(str(rates['output_per_million']))) / 1000000
    result.update(estimated_cost=str(cost), rate_source=rates['source'], rate_date=rates['as_of'])
    return result


def compare(rows, pair_modes=('serial', 'parallel')):
    """Keep missing/failed jobs in denominator; matched results aren't causal evidence."""
    groups = defaultdict(list)
    for row in rows:
        groups[row['mode']].append(row)
    modes = {}
    for mode, group in groups.items():
        durations = [r['seconds'] for r in group if isinstance(r.get('seconds'), (float, int))]
        accepted = [r['seconds'] for r in group if r.get('accepted') and isinstance(r.get('seconds'), (float, int))]
        modes[mode] = dict(total=len(group), accepted=sum(r.get('accepted', False) for r in group),
                           published=sum(r.get('publishable', False) for r in group),
                           median_terminal_seconds=median(durations) if durations else None,
                           timed_runs=len(durations), median_accepted_seconds=median(accepted) if accepted else None,
                           known_input_tokens=sum(r.get('known_input_tokens', 0) for r in group),
                           known_output_tokens=sum(r.get('known_output_tokens', 0) for r in group),
                           usage_complete=bool(group) and all(r.get('token_usage_complete', False) for r in group))
    pairs = defaultdict(dict)
    for row in rows:
        key = (row['case'], row['repetition'])
        if row['mode'] in pairs[key]:
            raise ValueError('Duplicate paired observation')
        pairs[key][row['mode']] = row
    matched = []
    for (case, repetition), pair in pairs.items():
        a, b = (pair.get(mode, {}) for mode in pair_modes)
        comparable = bool(a.get('accepted') and b.get('accepted'))
        matched.append(dict(case=case, repetition=repetition, both_accepted=comparable,
            **{('parallel_minus_serial_seconds' if pair_modes==('serial','parallel') else
                'new_minus_base_seconds' if pair_modes==('base','new') else 'planner_minus_control_seconds'):
               b['seconds'] - a['seconds'] if comparable else None}))
    return dict(modes=modes, pairs=matched, recommendation='No automatic mode promotion; inspect paired utility, failures and resources. Small stochastic sample, not a causal speed benchmark.')
