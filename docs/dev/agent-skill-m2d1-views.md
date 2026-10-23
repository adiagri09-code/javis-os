# M2D1 immutable view controls

Draft implementation for reserved version 0.299.0, PR803. This document extends
the [released M2C operations](agent-skill-m2c-operations.md); it does not declare
this draft released, native-qualified, or enabled for ordinary tasks.

An immutable comparison view pins the existing baseline skill body and one
actual A candidate body separately, together with their exact source, context,
grant, policy and semantic evidence. D1 supports one primary skill body per
view. It does not install a candidate into the canonical skill or create a new
canonical revision. Protected textual dependencies remain common context.

## Owner API

Use the existing Dashboard owner session and CSRF protection. An API token
alone cannot authorize these routes. The server resolves the `brain` parameter
to its existing scope; the comparison must belong to the URL experiment and
that brain. Read the current experiment generation from
`GET /improvement-experiments/{experiment_id}` before a control request.

POST paths are relative to `/improvement-experiments/{experiment_id}/`:

| Action | Exact JSON body fields | Behavior |
| --- | --- | --- |
| `view-freeze` | `comparison_id`, `expected_generation`, `event_key` | Freeze the actual baseline/candidate pair for an existing comparison. Source and semantic evidence must be current. No comparison cell may already exist without this binding. The publication advances the experiment generation once. |
| `view-evidence` | `comparison_id`, `expected_generation`, `event_key` | Recheck the existing pair's current sources, semantic authority, scope and experiment generation; return metadata and the remaining observational unknowns. A final comparison additionally requires current selected-report qualification evidence. |

`expected_generation` is the experiment generation, not the candidate, source,
policy, or operation generation. `event_key` is a string of 8–160 characters.
The JSON object is closed: no body text, paths, view hashes, variant selection,
caller grants, `allow_unknown`, `native_ready`, or native/semantic pass flags.
Malformed, duplicate, oversized and deeply nested bodies use the existing
transport validation.

For a freeze retry, reuse exactly the same key, comparison and expected
generation. Its actual recorded publication can replay after off/revoke without
decrypting the source. A different intent with the same key conflicts. A
completed `view-evidence` request is an inspection, not a durable readiness
receipt: repeating it rechecks current authority, including after off/revoke.

Both POSTs return the existing `{ok,result}` envelope. Current evidence includes
`view_binding`, `evidence_scope: "current_view_sources_and_semantics"`,
`current_generation`, `checked_at` and `observational_unknowns`. It exposes no
source body, protected answer, auth data, or native executable path.
`actual_reasoning` and `actual_input_use` remain unknown under the current
observations. This projection does not declare model readiness or eligibility.

`GET /improvement-experiments/{experiment_id}/views/{comparison_id}` returns
`{ok,view_binding}` from stored metadata. A valid comparison without a binding
returns a null binding. History stays available after off/revoke. It does not
construct an execution service, read source/plaintext blobs, refresh context,
probe native availability, dispatch work, or regain permission for execution.
An absent/older store uses the existing cold-read behavior; unavailable scope
is denied. Request errors use the existing localized safe error envelopes.

## Explicit execution and stopping

Freezing or inspecting a view never automatically calls `next`, queries a model,
selects a candidate or activates a skill. The existing explicit `next` control
uses the host-owned comparison schedule; a bound view uses request version4,
workspace/receipt version2 and result version4. Baseline and candidate share
the same runner, CallLedger and full 18-check integrity policy, while their
installed skill bytes and effective hashes remain distinct. Usage stays tied
to actual calls; unavailable usage stays unknown.

Source, grant, policy, context, dependency or semantic changes can make a
frozen view unusable for a new call without changing its historical metadata.
The current-evidence result is not a bypass around those admission fences.
Final admission requires the actual selected candidate, immutable reports,
current full integrity/selection evidence, and the shared qualification-family
registry. Qualification cases are consumed by actual materialization;
regression cases retain normal exposure/reuse rules and cannot be relabelled
qualification families. Keep the baseline when evidence is inconclusive.

The existing `cancel`/`recover` controls remain explicit. The service owns view
source-reading threads before starting them. HTTP cancellation does not detach
that ownership, and stop joins these threads before final settlement or
capacity release. Off/revoke does not prevent stop/recovery. A stopping state
can remain pending while actual work/cleanup is still owned; a terminal SQL
row by itself is not proof that all threads or native workers have ended.

A replacement in-process experiment service refuses construction when the
retained view's semantic workflow is closed but its exact original Trial owner
has not completed successful closure. The old resolver remains bound. Complete
both original service lifetimes through their owning shutdown/cleanup path
before rebuilding; successful closure of both permits a fresh usable resolver.
Missing, pending, cancelled or failed close futures cannot authorize replacement.
Clearing a reference or forcing a rebind does not establish cleanup.

## Storage and evidence limits

Schema 7 adds immutable view, asset, comparison-binding, Trial-link and final
qualification-link metadata. Before upgrading an existing C/schema 6 store,
the migration preserves `.pre-improvement-m2-views.bak` through the existing
writer serialization. The released C reader refuses schema 7. Restore the
preserved schema 6 backup for that reader using the established offline recovery
procedure; pointing it at the schema 7 database is not a downgrade. Earlier
unreleased schema 7 prototypes with incomplete guards are not repaired into
execution authority. Unknown future schemas are refused.

The D1 profile `4d346a3a` is registered only for Windows CLI 2.1.309, binary
SHA `5441781f`, and SDK 0.2.116, with full source/runtime hashes in the
[qualification artifact](../superpowers/evidence/2026-10-23-m2d1-native-qualification-final.json).
Its 20-test enforcement proof uses dummy authentication and local providers.
The actual CLI version is checked inside the owned hidden qualification job.
Changing source/runtime requires matching new qualification; historical C
qualification cannot authorize this changed tree. Registration does not attest
selected-account readiness or business quality. Technical tests use isolated
temporary stores and explicitly simulated adapters where stated.
The paired-view opt-in test separately passed with the actual pinned CLI and
dummy local provider: exact baseline/candidate prompts and receipts, distinct
sessions, denied ambient tools and plaintext cleanup after native job drain.
Its preparation/reviewer fixtures remain simulated. This proves direct native
profile enforcement, without asserting a native TrialRunner/account call.
Genuine selected-final positive execution and native TrialRunner/account
feasibility remain open. Production router/lazy/hub/task integration belongs
to D2; atomic activation/rollback and the complete operator flow belong to
later E/F work. Business pilots and live rollout require their own evidence
and scope. No deployment, restart, live activation or business acceptance is
implied by these controls.
