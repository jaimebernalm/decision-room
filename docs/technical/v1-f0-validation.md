# F0: HTML engine path and validation

Date: 2026-10-10. Base: master `5b11154`. Branch: `codex/v1-engine-path`.
Only F0 is implemented. Legacy remains the default. No model-provider calls,
push, merge or work on later phases were performed.

## Behavior delivered

Uploads, batch uploads, prepared-dataset jobs and chat investigations capture
`engine_kind` and an immutable configuration at creation. The OpenCode profile
records the model, low reasoning variant, pinned image, prompt/hash, input request
hash, token/call/time limits and runtime environment. Changing defaults does not
change existing jobs. The explicit request field is for the pilot/F5, not a new
UI selector.

The OpenCode branch enters before legacy model setup, memory extraction and
planning. Shared ingestion prepares data without a model call. A per-job lock and
stable business-scoped `web:<job>` key reconcile a run created before its web link
was saved. The web row has `engine_run_id`, phase `engine` and no fabricated legacy
investigation/review IDs. `report_document_id` stays null until F1.

The engine preserves exact received bytes before any parsing or display decision.
The database, store, MCP tool and file collector share a 256 KiB bound. Repeating
the same receipt key and bytes is idempotent; changing the bytes under that key is
rejected. Empty, malformed UTF-8 and truncated HTML remain retrievable. Oversize
attempts record size/hash/time/route without replacing a prior receipt. Export
returns raw bytes and hash, with presentation `not_evaluated` and verification
`not_requested`.

Delivery storage, permission to present, and execution completion are separate.
File collection reads only a regular `/work/informe.html` after stopping the agent,
inside a bounded networkless helper. Symlinks are rejected. MCP delivery is an
alternative, and the receipt records its route. Unknown provider usage keeps its
reservations, marks cost incomplete and aborts without submitting another call.
A controller exception after run creation, including a transient Docker/database
failure, fails the run conservatively and requires a new analysis.

## Commits and review

| Commit | Scope |
|---|---|
| `51ef049` | Selective transplant inventory, exclusions and schema boundary. |
| `cd6aa14` | Independent HTML profile, durable receipts, core engine and migration 31. |
| `981cc8d` | Immutable engine creation in web/chat and additive migration 32. |
| `da83a85` | Shared ingestion, early dispatch, stable run identity and worker recovery. |
| Final closure commit | Runtime state correction, native recovery/uncertain-use checks and this validation record. |

Claude reviewed the first four commits read-only through CC–CDX Bridge. The
creation/dispatch review had no blocking findings. Its notes about the provisional
prompt, pilot entry point, F1 status adapter and conservative failures are recorded
here and in `docs/technical/v1-f0-inventory.md`.

## Checks

- PostgreSQL fixtures use disposable databases. A populated master schema is
  migrated twice; existing library visibility and effective-request semantics are
  retained. Three old schema-version assertions were updated from 29 to 32. They
  already failed on master with `30 != 29`; this fixes prior failures rather than
  changing the migration acceptance criterion. The master-schema fixture requires a Git checkout because
  it reads `git show 5b11154:decision_room/schema.sql`.
- Creation checks cover all three web entry points, chat, legacy default,
  idempotency after a changed default and immutable selection/configuration.
- Worker/controller checks cover two workers, crash after run creation before
  linking, crash after receipt before web completion, no legacy calls, empty
  delivery, uncertain usage and denied automatic retries.
- Native Docker checks cover SIGKILL, checkpoint restore into a new container,
  session/work recovery, absent host/provider credentials and external DNS,
  exact partial/empty/oversize file collection and symlink rejection.
- Frontend: 302 tests pass; TypeScript, Vite production build and oxlint pass.
  Oxlint reports existing Fast Refresh warnings. No frontend source was changed.
- Full Python regression: 704 tests in 490.949 seconds, zero failures, zero
  errors and zero skipped. This includes native engine checks with the pinned
  image, database migrations, legacy regressions, web/chat and the million-row
  import. The suite's logged exceptions are expected fault-injection cases;
  the final unittest result is `OK`.

Use `python -m unittest discover -s tests` for complete discovery. The existing
tests import some helpers as top-level modules; `-t .` is not the documented
invocation. Build the sandbox runtime and frontend first, and set
`DECISION_ROOM_ENGINE_IMAGE_ID` to the pinned local image to include native engine
checks. Without that image, native checks are skipped explicitly. The final run
uses an empty `OPENAI_API_KEY` and synthetic model transports.

Native checks exposed a genuine runtime mismatch: the trial image lacked the
expected `XDG_DATA_HOME=/state` and its state mount root belonged to root. The
controller now sets the environment explicitly and prepares only state/work
volume roots for UID 10001 in a networkless helper. It never recursively changes
agent-controlled paths. The container module's four tests pass after this fix:
three native runtime checks and one archive-validation check.
Earlier attempts without the sandbox mount/build and the pre-fix runtime were
diagnostic failures, not successful validation. Claude's separate baseline run
on master and `981cc8d` had the same 177 environment failures from an unbuilt
sandbox, with no new failures; final validation uses a built isolated runtime.

## Boundaries and remaining phases

This is infrastructure validation, not evidence that product report quality equals
trial v1. `engine/opencode/prompts/informe.md` is a provisional F0 fixture. F2 must
replace it with the unchanged fixed v1 paragraphs and generated business brief.
Optional immutable panorama input is accepted but no panorama is generated here.

The runtime uses `serve` plus the product proxy/MCP rather than trial `run`.
Inputs are mounted read-only at `/inputs`, with a narrow external-directory
permission exception, rather than trial v1's `/work` layout. Runtime environment,
delivery route and these differences must be accounted for in F5 on the real
product path. Native transport/recovery tests make no claim about model quality.
The explicit `OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_DISABLE_DEFAULT_PLUGINS`,
`OPENCODE_DISABLE_EXTERNAL_SKILLS`, `OPENCODE_DISABLE_CLAUDE_CODE` and
`OPENCODE_DISABLE_MODELS_FETCH` flags are additional product restrictions absent
from trial v1 and belong in that comparison as well.

F1 must provide report registration/access and the read adapter: an engine job
can currently complete with no legacy review, and the adapter must recognize it.
F3 owns web waiting/owner questions (the internal protocol remains, disabled in
the HTML profile). F4 owns safe presentation and canonical text. PDF follows
later. Generated-brief generalisation, comparison against legacy and hard USD
admission before changing the default remain later gates with separate approval.
Rollback changes only the default for future jobs to legacy; existing runs and
receipts are preserved.
