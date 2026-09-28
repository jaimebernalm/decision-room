"""Shared selection/delivery criteria; the agent interprets the owner's free text."""
GOAL_QUALITY = """
QUALITY BY OWNER INTENT (interpret the actual request, not file names or keywords):
- Organize / dashboard: cover the requested measures, dimensions and periods with
  concise, usable comparisons. Prefer clear tables over forced surprises. Do not
  open speculative drilldowns that displace requested coverage.
  Before selecting visuals, check every requested measure against every requested
  breakdown/period. Allocate the available chart/table slots across that coverage;
  concise prose and cited values can supply small comparisons. A chart limit is
  not missing source data and does not justify silently dropping a core measure.
  Review the owner's original request against the delivered views, not just the
  analyst's narrower investigation titles or declarations of coverage.
- Discover / prioritize: choose a material supported signal, quantify its parts
  and investigate one useful finer breakdown when feasible. Explain why it merits
  attention relative to other signals. Name the segment and evidence to check next;
  distinguish an arithmetic contribution from an unproven commercial cause.
  Highest volume alone is not an explanation of why to act there first. State why
  the selected contrast merits attention relative to other observed signals.
  A useful next check names the segment/period, the specific missing operational
  fact and how it could change the decision or distinguish possible explanations.
  Conditional hypotheses are allowed when clearly unconfirmed; never state them
  as causes. Repeating 'verify source records/coverage' for every finding does not
  fulfil a request for business opportunities or problems. If context is unknown,
  give that concrete conditional check instead of inventing it or asking again.
- Concrete question: answer each requested component directly, including changes
  in amounts versus percentage points where applicable. Extra exploration is
  optional, never a substitute for the requested answer.
- Evolution: check whether periods have comparable observed exposure. If dates or
  durations differ and the interpretation is about performance, compute a rate
  using the stated observed exposure as a sensitivity check, alongside totals.
  Observed dates are not certified opening days or complete coverage. Do not send
  a feasible exposure calculation back to the owner as the next step.
- Free text / mixed goals: combine the applicable criteria and resolve competing
  priorities from the accepted scope; explain any incomplete component honestly.
- Forecast request: this product currently delivers historical analysis, not a
  validated prediction service. Do not fit a predictive model or fabricate future
  values; state the limit and analyse history only within the accepted scope.

The final delivery should lead with the answer or priority, place each visual
beside the finding it supports, and avoid two claims that repeat the same point.
A second view of a finding can support the first claim instead of adding a new one.
An optional stylistic improvement is not a material blocker. Missing an expressly
requested computable result, misleading exposure or an unsupported recommendation
is material. Missing definitions justify a useful explicitly partial delivery,
not guessing; a broad narrowed agent plan does not erase the owner's original goal.
"""
