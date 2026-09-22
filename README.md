# Decision Room

Start with the [MVP](<docs/product/Decision Room - MVP.md>) and
[implementation plan](<docs/product/Decision Room - Plan de implementacion.md>).
The [documentation index](docs/README.md) groups product decisions, research,
technical guides and validation results. Downloaded datasets are in `data/`.

## Project structure

```text
decision_room/             Application Python code
sandbox/                   Isolated Python container and dependency versions
tests/                     Automated tests
examples/                  Example calculations
scripts/
  datasets/                Dataset inspection, preparation and conversion
  dev/                     Local PostgreSQL and sandbox management
  checks/                  Data, export and execution verification
data/
  wide-world-importers/    Selected sample and CSV/Excel exports
  reference-cases/         Small evaluation inputs and separate answer keys
  exploratory/            Other public datasets investigated earlier
docs/
  product/                Product definition, MVP and implementation plan
  research/               Sector research, dataset sources and inspections
  technical/              Architecture and operating guides
  validation/             Recorded acceptance results
.local/                    Private local database, storage and runtime state
.tools/                    Local development binaries and auxiliary tooling
.venv/                     Host Python development environment
```

Run commands below from the repository root. The last three directories are
local to this installation and ignored by Git. `decision_room/` contains source
code; it is not the database directory.

This public repository includes code, dependency locks, documentation, source
attribution and small reference fixtures. Downloaded datasets, their generated
exports, private runtime data, credentials and the original Word draft stay local.
On a fresh clone, download the originals from the sources in the
[WWI guide](data/wide-world-importers/README.md) and, when needed, the
[exploratory dataset guide](docs/research/2026-09-17/README.md), then follow the
preparation commands below. Full-data checks require those local downloads.

The [repository workflow](AGENTS.md) records the user's convention: create a local
commit after completing and checking each implementation-plan step. Publishing
those commits to GitHub is a separate action.

## MVP implementation

CSV batch ingestion is implemented: repo-local PostgreSQL metadata, private
original files, lossless text columns in Parquet, basic profiling, duplicate-batch
detection and resumable preparation. It has been exercised with all 48 WWI CSVs
as one business and one analysis, preserving 4,713,833 rows.

See the [local ingestion guide](docs/technical/ingestion.md) for setup and CLI commands and
the [acceptance results](docs/validation/2026-09-21-ingestion-check.md) for verification.
Controlled Python execution is also implemented (plan step 1.3): a disposable
Docker container inside a dedicated Colima VM, with fixed libraries, no network,
read-only inputs, resource limits and durable calculation evidence. See the
[sandbox guide](docs/technical/sandbox.md), [design plan](docs/technical/sandbox-plan.md) and
[sandbox acceptance results](docs/validation/2026-09-21-sandbox-check.md).
The LangGraph planning agent (1.4) now has a configurable model connection,
provisional interpretations, owner questions and PostgreSQL recovery. See the
[agent guide](docs/technical/agent.md), [implementation plan](docs/technical/agent-plan.md)
and [validation results](docs/validation/2026-09-21-agent-check.md). Infrastructure
tests and real-model quality checks are separate; inspect the validation results
before treating a model's proposals as usable.
Generated Python investigation (1.5) now connects the same agent to the sandbox,
with bounded correction, durable candidates and invalidation after owner context
changes. See the [research guide](docs/technical/research.md) and
[real-model checks](docs/validation/2026-09-21-research-check.md). Candidates remain
unverified; [known interpretation errors](docs/validation/known-agent-errors.md)
are still open. Reviewer-led dialogue and private HTML reports (1.6) are now implemented; see
the [review guide](docs/technical/review.md) and
[validation](docs/validation/2026-09-21-review-check.md). The analyst can justify or
correct findings, but only the reviewer can approve the exact report. An
independent validation hold can block a mistaken approval; the real-model checks
include an open reviewer failure (DR-002). Excel
ingestion and the web UI remain to be implemented.

## Python environment

A Python 3.12 development environment exists at `.venv/`, ignored by Git.
Python packages for the host are installed there; execution libraries are inside
the Docker image. Docker and Colima are installed with Homebrew. The `.venv`
itself is not a security sandbox for generated code.

```sh
source .venv/bin/activate
python -m pip install -r requirements.lock
```

To recreate the environment on a machine with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
```

The extraction and streaming conversion use the Python standard library.
`openpyxl` is used only to independently read and check the final Excel files.
Excel layouts and visual previews use the existing Codex spreadsheet runtime;
its packages are linked into `.tools/spreadsheets/node_modules`, not installed
globally or copied into the Python environment.

## Data

[Wide World Importers](data/wide-world-importers/README.md) contains the original
Microsoft sample and an `exports/` folder:

- `csv/`: one CSV per source table.
- `excel/`: workbooks grouped into Sales, Purchasing, Warehouse, and Application.
- `large-values/`: companion values too long for a single Excel cell.
- `metadata/`: export mapping, NULL masks, and validation reports.

These are full source exports. Microsoft’s fictional wholesaler is larger
and more complex than the eventual small-shop inputs.

Three small [reference cases](data/reference-cases/README.md) now provide daily
sales, product sales without tickets, and an ambiguous amount requiring an owner
answer. Each has a renamed-column variant and separate evaluator answer keys.
Check their data and numerical references with:

```sh
.venv/bin/python scripts/checks/check_reference_cases.py
```

This command validates the fixtures, not agent performance. The real-model checks
are in `scripts/checks/check_agent.py`; behaviour and report usefulness still need
separate review.

## Repeat the conversion

Run from the repository root:

```sh
.venv/bin/python scripts/datasets/inspect_bacpac.py
.venv/bin/python scripts/datasets/convert_bacpac.py
.venv/bin/python scripts/datasets/prepare_excel_plan.py
```

Build the Excel layouts using the Codex-provided Node.js runtime. The existing
`.tools/spreadsheets/build_excel_templates.mjs` symlink points to the tracked
builder in `scripts/datasets/`; the rendering link points into `scripts/checks/`.
Run it from `.tools/spreadsheets` using Node's
`--preserve-symlinks-main` option so it resolves the linked spreadsheet runtime.
When setting up a new checkout, recreate the two symlinks using paths returned
by Codex's workspace-dependency loader.

Then finish and verify the exports from the repository root:

```sh
.venv/bin/python scripts/datasets/fill_excel_workbooks.py
.venv/bin/python scripts/checks/verify_exports.py --relations
.venv/bin/python scripts/checks/verify_exports.py
.venv/bin/python scripts/checks/check_excel_reader.py
```

The converter handles the native data types in this particular BACPAC. It is
not the production ingestion implementation and does not claim to import
arbitrary SQL Server backups. SQL Server is not installed or run by these scripts.

Client reports and internal execution logs are separate exports. See the
[client report guide](docs/technical/client-report.md) for chart provenance,
business explanations and publication rules (step 1.6).

The [step 1.7 evaluation runner](docs/technical/evaluation-plan.md) executes the
complete pipeline against eight scenarios with three repetitions, retains failures
and requires an independent numeric and semantic assessment before acceptance.
Generated batches and reports stay under ignored local storage.
