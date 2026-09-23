SERIES_TOOL = '''
SAVE VISUAL EVIDENCE DURING RESEARCH, not only summary scalars or PNG files.
For evolution, save an ordered daily/monthly series and comparable-period metrics.
For category comparisons, save the relevant breakdown; disclose top-N selection.
write_result accepts an optional series dictionary, separate from scalar metrics:
write_result(metrics, evidence=evidence, notes=notes, series={
  'sales_by_month': {'unit':'moneda no especificada', 'grain':'month',
    'points':[{'label': label, 'value': str(value)} for label,value in computed_rows],
    'evidence': {'tables':['t1'], 'operation':'Actual SQL/Python aggregation, filters and selection'}}
})
Replace example keys, aliases, unit and operation with actual definitions/results.
Each series needs unit, grain ('day', 'month' or 'category'), points and evidence.
Each point has label and finite numeric value (Decimal as string). Daily labels
are YYYY-MM-DD, monthly YYYY-MM; dates ordered and unique. Category labels unique.
No null/NaN values and no invented zero for missing dates. At most 4 series,
2–366 points each, 800 points total. Aggregate longer intervals in Python;
bars/tables can display at most 36 points. Never silently truncate to fit a limit.
Check the number of groups BEFORE including each series. A single product,
category or period is a scalar metric, not a one-point series: omit that series
and save its value and identity as evidenced scalar metrics. Do not duplicate or
invent points. With zero groups explain the absence; aggregating further cannot
fix a series that already has fewer than two points.
The series evidence describes all its points; do NOT duplicate every point into
scalar metrics. Keep scalar summaries for findings, highlights and checks.
Series keys are NOT scalar metric_keys when recording a research candidate;
they remain available to the reviewer through saved execution observations.
'''
