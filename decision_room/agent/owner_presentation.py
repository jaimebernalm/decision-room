"""P3 editorial instructions and feedback; no new business inference or acceptance gate."""
import re

VERSION = 'owner-presentation-v3'
TECHNICAL = r'\b(?:TRY_CAST|CAST\s*\(|SQL|resultados guardados|saved results|contribuciones firmadas|signed contributions|pares focales|liderazgo aritmético|residual de meses sin pareja|concilia con el cambio neto|mitades cronológicas|unidades por fecha observada|conciliar (?:captura|mapeo)(?:/mapeo)?|imputar ceros|meses emparejados)\b'
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
technical evidence to a SEPARATE technical file or PDF appendix, not hidden HTML.
Use method for ONE short source explanation in the report language (Spanish by
default): what quantity was calculated, from which data and period. At most 40
words; never list intermediate metrics, daily rows, SQL or execution descriptions.
Do not refer readers to a hidden evidence dump. Scope must remain honest.
Use the owner's language, not analytical jargon: say which products/channels you
compare, which contributes most, what months are missing, or whether the parts add
to the total. Avoid phrases such as "pares focales", "liderazgo aritmético",
"residual de meses sin pareja" and "concilia con el cambio neto".
Instead of "mitades cronológicas", explain the two date ranges and why they
answer the question. Instead of "unidades por fecha observada", say the average
per day WITH records and explicitly distinguish it from all calendar days.
Instead of "conciliar captura/mapeo", name the records or product assignments to
check. Instead of "imputar ceros", explain that days without records are not days
with zero sales. Instead of "meses emparejados", name the same months compared.
If a comparison window is not obvious, give ONE short sentence explaining why it
was chosen. A label such as "first half" is not that explanation. Do not invent a
seasonal or business reason for a convenience/exploratory window.
State synthetic/simulated-data scope ONCE in limitations when supported by the
actual input context. Never infer synthetic provenance from unusual data alone.
Like the general causal caveat, remove semantic repetitions from other prose;
retain distinct local conditions and specific weaknesses in the data.
Do not print "Selección entregada" counters or "Anexo técnico" in owner prose.
Keep selection metadata in the audit; explain relevant subset/coverage honestly
and briefly in chart captions, never imply a selected subset is the whole business.
Do not discuss whether the report opens in a browser or whether that was verified
or accredited. Those are software audit notes, not business limitations.
Chart layer.name and coordinate series/category must be meaningful business names.
Layer.key is an internal ID; never copy key:period into a visible label or prose.
Reactions must describe DIFFERENT decisions for different outcomes. If all outcomes
lead to the same action (e.g. keeping a descriptive comparison), write that once;
do not manufacture differences or a decision tree. Do not prefix a condition twice.
General causal uncertainty belongs ONCE in limitations. Remove paraphrases of that
same caveat from summary, claims, methods and captions during rewriting. Retain
specific decision conditions and distinct uncertainties; do not claim causality.
Software delivery status (HTML export, browser verification, version numbers) is
technical audit information, not a business limitation. Keep it out of prose and
limitations; never remove a real data limitation or claim an export was verified.
CONTROLLER OWNERSHIP: controller_annotations contains system-generated coverage
and selection audit notes, not editable writer prose. Legacy drafts may still
contain these exact notes in limitations. NEVER revise/reject solely for their
wording, counters or technical style: the writer cannot fix controller insertion.
Do not copy them into prose. Inspect owner_coverage, question_coverage, delivery
selections and evidence for substantive gaps, false completeness or wrong numbers;
those still require correction. This exemption covers only the supplied exact
controller notes, not arbitrary limitations or genuine unanswered business goals.
Reviewer: inspect the owner-visible reading as well as the evidence. Ask for concrete
editorial corrections when labels, numeric precision, repeated caveats or unexplained
period choices obscure the decision. owner_reading_feedback is diagnostic, not a
business claim or an automatic approval rule. Do not reject valid source names merely
because a heuristic flags them. All existing accuracy and coverage checks still apply.
'''


def feedback(report, controller_annotations=None):
    """Point to likely leaks for judgment, without silently editing reviewed prose."""
    passages = []
    annotations = controller_annotations or {}
    controlled = {annotations.get('coverage_note'), *annotations.get('selection_notes', [])}
    def add(path, text):
        if isinstance(text, str) and text.strip() and text not in controlled:
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
            for j, layer in enumerate(item.get('layers') or []):
                add(f'{prefix}.layers[{j}].name', layer['name'])
            for j, point in enumerate(item.get('points') or []):
                add(f'{prefix}.points[{j}].label', point['label'])
            for field, value in (item.get('orientation') or {}).items():
                add(prefix + '.orientation.' + field, value)
            for j, reaction in enumerate((item.get('orientation') or {}).get('reactions', [])):
                add(f'{prefix}.reactions[{j}].condition', reaction['condition'])
                add(f'{prefix}.reactions[{j}].reaction', reaction['reaction'])
    patterns = {
        'technical_language': TECHNICAL,
        'software_delivery_note': r'\b(?:HTML|exportación|versión \d+)\b',
        'internal_identifier': r'\b[a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+\b',
        'excess_decimal_precision': r'(?<!\w)\d+[.,]\d{3,}(?!\w)',
    }
    return {'purpose': 'Editorial hints only; retain evidence, conditions and valid source names.',
            'locations': [{ 'path': path, 'issue': issue} for path, text in passages
                          for issue, pattern in patterns.items() if re.search(pattern, text, re.I)][:40],
            'synthetic_caveat_locations': [path for path, text in passages if re.search(r'sintétic|simulad', text, re.I)],
            'repeated_causal_caveat_locations': [path for path, text in passages if re.search(r'causal|causa|demuestra.*demanda', text, re.I)],
            'identical_reactions': [c['key'] for c in report.get('claims', [])
                if len((c.get('orientation') or {}).get('reactions', [])) > 1
                and len({' '.join(r['reaction'].split()).casefold().rstrip('.')
                         for r in c['orientation']['reactions']}) == 1],
            'review_reactions': [c['key'] for c in report.get('claims', []) if (c.get('orientation') or {}).get('reactions')],
            'review_period_rationale': [c['key'] for c in report.get('charts', [])],
            'instruction': 'Review period rationale and semantic repetition yourself. Rewrite duplicated causal and synthetic-data caveats once in limitations, and merge equivalent reactions without inventing differences. Keep distinct uncertainties and conditional safeguards. The locations are hints, not facts or an automatic rejection rule.'}
