# F0: inventory and boundary of the HTML engine

Base: `5b11154` on `master`. Source: `claude/agent-engine-eval` at
`0075a5e`. This implements only F0 of the agreed v1 integration plan.
Legacy remains the default. Local commits only; no model API calls in validation.

## Selective transplant

| Files | Treatment |
|---|---|
| `decision_room/engine/{admission,checkpoint,client,container,control,costs,diagnostics,proxy,questions,server,transport,transport_trace,tunnel}.py` | Reuse job authentication, reservations, transport, durable state and checkpoint mechanics; adapt only where the HTML profile requires it. |
| `decision_room/engine/{__init__,api,store,export,gateway}.py` | Adapt to the `html-v1` profile: fixed inputs and prompt, durable raw HTML delivery, minimal export and owner-question tools. No structured report verification or projection. |
| `engine/opencode/{Dockerfile,.dockerignore,LICENSE.opencode,README.md,relay.py,vendor.py}` | Reuse pinned isolated runtime and local build instructions. No automatic downloads during jobs. |
| `engine/opencode/prompts/informe.md` | Provisional F0 HTML fixture, not equivalent to the frozen v1 brief. F2 replaces it with the unchanged fixed v1 paragraphs and the generated business brief. |
| `decision_room/schema.sql` | Append an additive migration after master's version 30 for admission, receipts, sessions/outbox and owner questions. Keep master's `analyses.library_hidden`. Do not copy the eval tail wholesale. |
| `decision_room/web/service.py`, job configuration and creation in chat | Add immutable engine selection, early dispatch and durable run linkage; preserve legacy ingestion and orchestration. |
| Existing core engine tests plus new profile/job tests | Retain applicable tests, remove structured-calculation assumptions and add HTML, migration, creation, recovery and no-hidden-call checks with synthetic models. |

The source inventory contains 22 engine modules and seven runtime files. Four
engine modules are deliberately excluded: `numbers`, `panorama`, `ratios` and
`calculations`. Their dependencies (`sales_panorama*`, `reports.panorama_facts`,
structured contracts/verification and `web.report_projection`) are not F0.
`execution.py` is not transplanted: v1 computes locally inside its isolated
container over immutable CSV copies. No evaluation launcher, R0/R1, posthoc
verifier or evaluation kits are product dependencies.

The 31 commits unique to `codex/agent-engine` were inspected by scope: they concern
R0/R1/posthoc interpretation, experiment accounting, exploration and Chrome export.
None is required by the reduced HTML-only gateway/export. The input manifest is
rendered readably in the HTML profile; no experimental verifier is imported for it.

## Schema and contracts

Master and eval reuse migration number 30 for different changes. Master's version
30 hides historical library inputs; eval's version 30 adds effective-request
observations. Preserve master and allocate new migration numbers. No migration is
run against the owner's product database during tests: tests create disposable
PostgreSQL databases, including a populated master-schema migration fixture.

`html-v1` retains exact delivery bytes and hashes before parsing, with a 256 KiB
receipt bound shared by storage, database and MCP. Oversize input is rejected
without replacing an earlier receipt. Empty, malformed and interrupted content
within the bound remains recoverable and never implies a permitted presentation.
Receipt, presentation eligibility and execution status remain distinct.

Migrations 31 and 32 add the engine tables and immutable web-job selection.
The explicit `engine_kind` request field is a pilot/F5 entry point, not a UI
option. Legacy remains the default and OpenCode requires a pinned image ID.

`engine_kind` and engine configuration are fixed at creation. Changing a default
affects only new jobs. Stable business/job request keys reconcile creation and
delivery after interruption. No automatic replay of uncertain model calls. Job
tokens never authorize owner-facing report access. `report_document_id` remains
null until F1; engine receipt IDs belong to the engine and are not legacy review IDs.
An engine job can be `completed` with phase `engine` and no review ID. F1 must
read that status through its report adapter rather than interpret it as a legacy
review. A controller exception after run creation, including a transient Docker
or database failure, conservatively fails the run: another analysis is required,
with no automatic retry.

The HTML profile accepts an optional immutable `contexto/panorama.md` input for
F2, without generating it. Canonical text, viewing, neutral report registry,
owner-answer web integration, PDF and generated briefs remain in their later
phases. The engine's existing internal owner-question protocol is preserved.
It is disabled in `html-v1` until F3. Added modules are
`decision_room/engine/{profile,file_delivery,job_profile}.py` and
`decision_room/web/engine_jobs.py`.

The runtime records its environment, explicitly places OpenCode state in `/state`,
and prepares only the state/work volume roots for the non-root runtime user.
CSV and context inputs use a read-only `/inputs` mount. The narrow
`external_directory` exception for `/inputs/*` differs from trial v1's writable
`/work` layout and must be included in F5's product-path comparison. Both stopped
`/work/informe.html` collection and MCP delivery preserve bytes before parsing;
oversize attempts retain metadata without replacing a prior receipt.

## Completed-step commits and validation

1. Inventory: reviewed source imports, branch deltas and schema collision.
2. Isolated HTML engine and migration: applicable core unit/transport tests,
   PostgreSQL receipts/admission and additive migration twice over populated master.
3. Immutable engine selection in all creation paths: synthetic-model web/chat tests
   and idempotent-request/configuration checks.
4. Shared ingestion and early engine dispatch: zero legacy/model calls in engine
   jobs, stable run links, status mapping and restart/concurrent-worker checks.
5. Recovery and regression closure: receipt/worker fault tests, uncertain-use
   admission, native Docker transport/checkpoint recovery, full master Python and
   frontend checks. Model quality and the effect of `run` to `serve`/MCP adaptation
   remain to be measured in F5.

Each code step gets a focused local commit after its checks, then Claude's
read-only review. A rollback changes the default for future jobs to legacy;
existing runs, immutable inputs and receipts remain preserved.
