"""Editorial feedback from saved prose, never a numerical or approval check."""
from collections import defaultdict


def reading_feedback(report):
    if not report:
        return None
    passages = []

    def add(path, text, visible=True):
        if isinstance(text, str) and text.strip():
            passages.append((path, ' '.join(text.split()), visible))

    add('summary', report.get('summary'))
    add('scope.coverage', report.get('scope', {}).get('coverage'), False)
    for i, text in enumerate(report.get('limitations', [])):
        add(f'limitations[{i}]', text)
    for claim in report.get('claims', []):
        if not isinstance(claim, dict):
            continue
        prefix = f"claims.{claim['key']}"
        add(prefix + '.statement', claim.get('statement'))
        add(prefix + '.interpretation', claim.get('interpretation'), False)
        value = claim.get('orientation')
        if value:
            # Match the visible renderer: same signal and legacy next_step are
            # compatibility fields, not repeated text on the page.
            if value.get('signal') != claim.get('statement'):
                add(prefix + '.orientation.signal', value.get('signal'))
            for field in ('relative_priority', 'next_check', 'decision_value', 'limitation'):
                add(prefix + '.orientation.' + field, value.get(field))
            for i, reaction in enumerate(value.get('reactions', [])):
                for field in ('condition', 'reaction'):
                    add(f'{prefix}.orientation.reactions[{i}].{field}', reaction.get(field))
        else:
            add(prefix + '.next_step', claim.get('next_step'))
    for chart in report.get('charts', []):
        add(f"charts.{chart['key']}.caption", chart.get('caption'))
    repeated = defaultdict(list)
    for path, text, _ in passages:
        if len(text.split()) >= 6:
            repeated[text].append(path)
    return {
        'purpose': 'Editorial feedback only; counts are not business evidence. No automatic removal or approval blocker.',
        'summary_words': len((report.get('summary') or '').split()),
        'first_reading_words': sum(len(text.split()) for _, text, visible in passages if visible),
        'limitation_words': sum(len(text.split()) for path, text, _ in passages if path.startswith('limitations[')),
        'repeated_passages': [{'locations': paths} for paths in repeated.values() if len(paths) > 1][:20],
        'note': 'Exact repeated prose only; semantic overlap, clarity and material caveats require analyst/reviewer judgment. Preserve conditions and evidence.',
    }
