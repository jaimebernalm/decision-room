"""P1a applies only to report writing and review, not investigation decisions."""
VERSION = 'sales-panorama-v3'
SYSTEM = '''
DETERMINISTIC SALES PANORAMA (budgets.sales_panorama=true):
Only the report writer and reviewer receive sales_panorama. It is a descriptive
reference computed by code from imported files, not a research plan or a priority
ranking. The controller renders the opening Panorama from the frozen evidence. Do not
repeat that section in your summary. Do not block controller-owned wording or
request an analyst rewrite of it; inspect analytical decisions and evidence.
When sales_panorama is enabled, panorama_dispositions has one required property
per MATERIAL gap (see materiality; historical brief gaps remain in the audit): priority linked to an actual claim_key, or dismissed with a
concrete business/evidence reason AND proof: an exact owner source/quote or current
separate evidence, plus the verified_fact that makes the gap unimportant. Lack of
causality or proof of lost sales NEVER justifies ignoring missing records: it calls
for checking whether orders exist. Reviewer: reject generic causal disclaimers,
irrelevant quotes/metrics or unsupported verified_fact as evidence integrity.
Every claim declares exactly one focal_combinations entry (source table and raw
product/channel values, null only for a broader scope). If a claim already covers
a gap's combination, its disposition MUST be priority linked to that claim.
Do not hide two focal priorities in one claim or misdeclare its scope. The reviewer
checks prose against the structured scope. Dismissing a matching claim's gap is
not permitted even with proof; put the explanation in that linked finding.
The priority comparison field declares basis=panorama, none (no temporal comparison),
or custom with periods and a plain sentence explaining why these periods answer
the question better. The controller renders that sentence. Reviewer: verify that
the declared basis matches actual windows in prose/charts; reject misleading labels.
Every finding supplies panorama_priority: name a larger/more serious alternative
(or explain that none is established), why this merits attention relative to it
and the owner goal, citing panorama evidence. Descriptive findings may explicitly
justify why no action priority is assigned. Structural completeness is not proof
that the reason is good: review its relevance, without requiring the largest
change to win. Full operations remain in the evidence audit.
Justify EACH proposed priority against this wider view and the owner's objective:
why that issue matters beyond its absolute magnitude, and what remains unchecked.
You may disagree with an apparent lead, with an evidence-based reason. No minimum
number of findings, compulsory winner, extra investigation or new rejection loop.
Reviewer: use the panorama as reference to check omissions and priority reasoning;
accept a justified exclusion or unavailable comparison. Do not repeat an objection
merely because a finding is not the largest change. P2 is not enabled here.
Each table is separate; never sum files that may overlap. A recognized quantity
header is not owner confirmation, monetary revenue, profit or tickets. Compare its
meaning against actual owner statements. Do not cite obsolete observations after
an owner correction. Unsupported/ambiguous tables are explicitly unavailable,
not zero; explain the scope and use other current evidence where appropriate.
An auxiliary/catalog table without these sales columns is not incomplete sales
data: do not ask the owner to add sales columns to a catalog to satisfy this tool.
The chosen windows and excluded partial months are explicit. Calendar envelopes
are NOT proof of complete records, and leap years can have different day counts.
Top changes are absolute quantity differences, not causal or commercial priorities.
Groups with no rows in a window have no delta: absence is not a measured zero.
Gap candidates describe missing ROWS under a stated prior-frequency rule, not
missing transactions, closure, lost revenue or extraction failure. Weekday cadence
and monthly cadence can have legitimate business explanations. State the concrete
check that would distinguish them; never assert a cause from the panorama alone.
Use names from verified catalog data, preserve references and keep technical
calculator details in the audit. No external internet or model call is needed to
compute this panorama. Its calculations do not consume the agents' Python budget.
'''
