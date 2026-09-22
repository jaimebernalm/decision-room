# Small reference cases

These three examples define a small, checkable first target for Decision Room.
They are evaluation inputs, not mandatory customer templates. The integrated analyst, reviewer and evaluation runner are now implemented.
Passing the data checks below still does not establish agent performance; see
the [evaluation procedure](../../docs/technical/evaluation-plan.md).

The cases derive from Microsoft's fictional Wide World Importers wholesaler:
April 1–28, 2016, products 1–8, excluding invoices flagged as credit notes.
They are selected activity, not a complete shop export or real shop results.
The original source and its license remain in `../wide-world-importers/`.
`provenance.json` records source hashes, source row IDs and transformations.

| Case | Input | Expected behaviour |
|---|---|---|
| `01-daily-sales` | 24 date/amount rows | Compare recorded sales across two equal calendar periods. Do not invent product or ticket information. |
| `02-product-sales` | Sales aggregated by date/product | Analyse products. Do not count rows as tickets or calculate average ticket value. |
| `03-ambiguous-amount` | 12 item rows with quantity and an undefined amount | Ask whether amount is unit price or row total before reporting sales. Adapt to the answer. |

Each directory contains:

- `input/sales.csv` and `input/context.md`: the only material initially given to the agent.
- `variants/renamed-columns/sales.csv`: an alternate upload with renamed/reordered columns and reversed rows. Use it **instead of** the base CSV with the same context, never as extra sales.
- `evaluation/expected.json`: answer key and behavioural expectations, for the evaluator only.
- Case 3 also has `evaluation/owner-responses.json`, which the evaluator uses to answer the agent's question.

Do not give the agent this README, provenance, the original database, answer keys
or owner answers before it asks. The evaluation runner exposes only the chosen
case's inputs. Avoid testing an agent with unrestricted access to this repo:
it could read the answers. Cases 1 and 2 describe the same underlying activity
and must be run separately, not added together.

## Manual review

1. Start a fresh analysis with one case's CSV and context.
2. Review whether it understands what a row represents and chooses supported calculations.
3. Compare any reported metrics against the answer key; it does not need to report every available metric.
4. Check the case's prohibited claims. Correct arithmetic alone does not validate the narrative.
5. For case 3, confirm it asks about the amount before publishing the affected total. Run separate sessions for unit price, row total and “I don't know”. The row-total answer is a hypothetical alternative, not the original source meaning.
6. Repeat with the renamed-column variant. The interpretation and numerical results should remain equivalent.

Record the model/version, case, answer scenario, observed question, reported
figures, unsupported claims and your verdict. Human review judges usefulness,
wording and business sense. Known answers check arithmetic and regressions.
These three cases do not cover Excel ingestion, joins, refunds or all MVP needs.

Money comparisons should match to 0.01 in the case's currency units; displayed
percentage changes match to 0.01 percentage points. Counts and quantities match
exactly. Periods are April 1–14 and April 15–28, inclusive. Missing dates remain
unknown, not zero. Currency is deliberately unspecified: the context confirms
consistent units, but the agent must not invent a currency symbol.

## Check the reference data

From the repository root:

```sh
.venv/bin/python scripts/checks/check_reference_cases.py
```

This reads the original source exports and recomputes the expected answers
with SQLite and integer cents, separately from the Decimal-based preparation
script. It verifies all six CSVs and the numerical answer keys. It does **not**
grade an agent's report, questions or reasoning. The integrated evaluation runner checks cited numeric results, while an explicit
independent assessment still reviews semantics and usefulness.

## Rebuild

Run `scripts/datasets/prepare_reference_cases.py` using the repo environment. It produces
JSON intermediates and evaluator files. Then run
`scripts/datasets/build_reference_csvs.mjs` through the bundled Artifact Tool runtime
with `REFERENCE_REPO_ROOT` set to this repo's absolute directory. No new packages
are required. The JS builder authors the tables and writes UTF-8 BOM CSVs.
Run the check command after rebuilding; do not regenerate answer keys merely
to accept an unexpected result from an agent.
