"""P3 editorial instructions and feedback; no new business inference or acceptance gate."""
import re

VERSION = 'owner-presentation-v1'
SYSTEM = '''
OWNER PRESENTATION EXPERIMENT (budgets.owner_presentation=true):
Write for a nontechnical business owner. Preserve the original question, findings,
evidence, causal uncertainty and conditional recommendations. Do not change the
investigation, priorities or standards of evidence to make the prose look better.
Lead with the answer and the next useful decision. Titles state the finding.
Never put internal delivery counts/status, execution IDs, metric/series/column keys,
SQL functions, casts, or engineering phrases in owner-facing prose. Explain what a
measure means instead. Keep exact references in evidence/checks, and technical
operations in saved execution evidence; method is a short plain-language explanation.
Use human-readable product/channel names from verified complete catalogues or saved
name-bearing evidence, never guessed from codes or a partial sample. If the mapping
is unavailable, disclose that once in limitations and retain the distinguishable code;
do not invent or merge entities. A name can be selected from an authorized source
with the existing calculation tools, but does not authorize changing the measure.
Use short, rounded numbers in prose, matching the saved quantities and units. Counts
are whole numbers when integral; other measures normally need at most two decimals.
Keep meaningful small differences and material precision (never round a nonzero
signal to zero). Exact values remain in evidence; do not round intermediate math.
Explain WHY these periods are compared in the caption or method, in plain language:
what baseline answers the owner's question, calendar lengths/coverage, and whether
it is an observed comparison or a chosen exploratory window. Never claim seasonality
or comparability without evidence. Keep enough time context to interpret each figure.
State each general caveat once in limitations. Do not repeat it in summary, every
finding, caption and next step. Preserve any condition needed to interpret a specific
claim or choose an action; centralizing caveats is not permission to overclaim.
A partial answer is described through the concrete unanswered question and what data
or check would answer it in limitations; do not print internal delivery counters.
The application keeps status/coverage and original identifiers in its audit and moves
technical evidence to optional details (PDF appendix). Scope must remain honest.
Reviewer: inspect the owner-visible reading as well as the evidence. Ask for concrete
editorial corrections when labels, numeric precision, repeated caveats or unexplained
period choices obscure the decision. owner_reading_feedback is diagnostic, not a
business claim or an automatic approval rule. Do not reject valid source names merely
because a heuristic flags them. All existing accuracy and coverage checks still apply.
'''


def feedback(report):
    """Point to likely leaks for judgment, without silently editing reviewed prose."""
    passages = []
    def add(path, text):
        if isinstance(text, str) and text.strip():
            passages.append((path, text))
    for key in ('title', 'summary'):
        add(key, report.get(key))
    for key, value in report.get('scope', {}).items():
        add('scope.' + key, value)
    for index, text in enumerate(report.get('limitations', [])):
        add(f'limitations[{index}]', text)
    for kind in ('claims', 'charts', 'highlights'):
        for index, item in enumerate(report.get(kind, [])):
            prefix = f'{kind}[{index}]'
            for field in ('title', 'label', 'statement', 'interpretation', 'method', 'next_step', 'caption'):
                add(prefix + '.' + field, item.get(field))
            for field, value in (item.get('orientation') or {}).items():
                add(prefix + '.orientation.' + field, value)
    patterns = {
        'technical_language': r'\b(?:TRY_CAST|CAST\s*\(|SQL|resultados guardados|saved results|contribuciones firmadas|signed contributions)\b',
        'internal_identifier': r'\b[a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+\b',
        'excess_decimal_precision': r'(?<!\w)\d+[.,]\d{3,}(?!\w)',
    }
    return {'purpose': 'Editorial hints only; retain evidence, conditions and valid source names.',
            'locations': [{ 'path': path, 'issue': issue} for path, text in passages
                          for issue, pattern in patterns.items() if re.search(pattern, text, re.I)][:40],
            'review_period_rationale': [c['key'] for c in report.get('charts', [])],
            'instruction': 'Review period rationale and semantic repetition yourself; regex cannot establish either.'}
