# M2C owner operations

This document describes the unreleased 0.294.0 implementation. Published M2B is
0.293.0. These controls do not enable candidate/final execution, activation,
compose, arbitrary helper execution, or a business/live acceptance claim.

All routes use the existing Dashboard owner session and CSRF policy. An API token
alone cannot authorize them. The server resolves `brain`; callers cannot submit
native readiness, capability receipts, config pins, arbitrary commands, source
grants, schedule positions, or successful assessment flags.

## Explicit preparation and roles

Read the current experiment generation from
`GET /improvement-experiments/{experiment_id}`. The `expected_generation` below
is this experiment generation, rather than an A candidate/base generation or an
operation's own generation. Every POST has a bounded `event_key`. Reuse exactly
the same key and body for retries; changing an already recorded owner's intent
with the same key conflicts. No action automatically dispatches the next phase.

POST paths below are relative to `/improvement-experiments/{experiment_id}/`:

| Action | Exact fields besides `event_key` | Result |
| --- | --- | --- |
| `preparation-freeze` | `expected_generation` | Freeze the host-derived tuning-only baseline schedule; phase becomes `preparing`. |
| `preparation-next` | `expected_generation` | Admit the next actual baseline Trial and hand it to the shared Trial supervisor. It returns stored metadata without waiting for the model result. |
| `preparation-complete` | `expected_generation` | Seal exact published result references after all preparation workers/checkers and plaintext cleanup have settled; phase becomes `proposing`. Unknown results remain unknown. |
| `propose` | `expected_generation` | Run the isolated improver on actual completed tuning evidence. Stage at most the remaining two A slots, atomically. A malformed batch gets at most one structural repair automatically. |
| `semantic-review` | `candidate_id`, `expected_generation` | Run an isolated reviewer on this experiment's exact A before/after/provenance, protected context, and granted declared dependencies; store an immutable separate receipt. |
| `semantic-arbitrate` | `candidate_id`, `receipt_id`, `expected_generation`, `expected_binding_hash`, `verdict`, `reason` | Record owner interpretation of the exact receipt/binding. Verdict is `pass`, `fail`, or `unknown`; the concise reason is encrypted. |
| `semantic-evidence` | `candidate_id`, `expected_generation` | Explicitly recheck current source/grants/receipt/native linkage and return assessments. This is an owned source-reading operation, not an ordinary metadata GET. It does not create a successful qualification. |

Proposer and reviewer are genuine `improve_propose` and `improve_evaluate` calls in
the existing CallLedger. They are not solver Trials or Team executions. A model
assessment, dependency verdict, owner interpretation, and native coverage remain
separate. Owner confirmation cannot erase a model failure, waive dependency or
native unknowns, mint an edit grant, or change A's immutable `unreviewed` status.
An executable dependency remains unsupported until its actual later isolation
and runtime qualification exist. Declared-reference coverage is not a proof of
all executable imports or dynamic dependencies.

The current source footprint has 33 files and no qualified runtime registration.
Default native execution therefore refuses before version/auth/model probes.
Qualification of the final stable profile and selected runtime belongs to Task9.
Injected test engines and the installed SDK DTO library are not that evidence.

## Cold history and stopping

These owner GETs read stored metadata. They do not create an execution service,
decrypt model/source text, capture current context, probe native availability,
refresh usage, recover work, or dispatch:

- `/improvement-experiments/{experiment_id}/preparation`
- `/improvement-experiments/{experiment_id}/operations`
- `/improvement-operations/{operation_id}`
- `/improvement-candidates/{candidate_id}/semantic-history`

History can remain readable after off/revoke. It does not restore permission for
current semantic inspection or a new model call. The explicit stopping/recovery
routes still work after off/revoke so existing ownership and usage can settle.

`POST .../cancel` takes `expected_generation` and `event_key`. Its immutable
`acknowledgment` records the original stopping fence; `current` separately shows
the state after draining. `stopping` is a valid unfinished response when a real
brain execution lock or cleanup proof is still busy. Database terminal status
alone does not prove that a native worker, checker, or result/publication thread
has ended. Cancellation fences actual native roles before joining their complete
workflows, and retains synchronous decision threads through repeated HTTP
cancellation.

`POST .../recover` takes only `event_key`. It touches this experiment's actual
comparison/preparation links, role operations, and every recorded attempt. It
does not scan/settle unrelated reservations or clean unrelated journals. Recovery
and explicit resume never dispatch automatically or regrant a revoked source.
An interrupted stop preserves capacity until exact cleanup is proven under the
shared brain kernel lock and the final SQL state still matches. A replay retains
the original acknowledgment and can return a newer `current` state.

Shared finite limits are 12,000 comparison cells plus 2,000 preparation cells,
14,000 distinct Trials / 28,000 attempts, and four role operations / eight role
attempts. Separate comparison/preparation limits cannot be exchanged. Full-size
SQL tests establish bounded query/cardinality behavior; genuine small-scope
integration tests establish actual lineage, workers, calls, cleanup and replay.
Structural SQL fixtures are not evidence of model execution.

Application shutdown closes the concrete role supervisors/workflows and owned
controller operations before the shared Trial service and underlying sources.
A cleanup failure is not a successful shutdown/readiness proof.

## Errors, evidence and pilots

Errors use fixed bilingual text and fixed machine reasons. Invalid closed JSON
is HTTP400, oversized bodies413, stale state/identity conflicts409, unavailable
owner/source scope403, and unavailable native/service capability503. Raw native
exceptions, source bodies, credentials, and CLI paths do not enter error text.

VI: “Không thể thực hiện yêu cầu cải tiến trong phạm vi hiện tại.”

EN: “The improvement request is unavailable in the current scope.”

Usage retains actual call/attempt identities. Missing observations stay null or
partial/unknown. A marked call is never refunded as if it had not started.
Subscription-equivalent USD is not cash charged. Technical feasibility results
do not establish business ROI or permit live activation.

The owner delegated pilot selection: reconciliation first, document processing
second, with Python bug-fix/testing as an additional technical pilot. Independent
business data, business acceptance, qualified effective-view execution, and live
canary/activation gates still require their actual evidence in later milestones.
