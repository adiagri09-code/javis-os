# Agent and skill improvement M2D1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a real isolated baseline/candidate comparison using exact immutable
skill views and the existing Trial ownership/usage chain, preserving every
legacy protocol and all unknown/owner/live gates.

**Architecture:** One byte-exact host-derived view resolver constructs baseline
and candidate assets without writing canonical files, M0 target pointers or a
global native mirror. Append-only comparison bindings join these views to actual
source/semantic/edit authority. A deliberately new v4 request and v2 workspace
manifest traverse all existing Trial/native/evidence/result/stop consumers.

**Tech:** Current Python3.12, FastAPI, same resonance SQLite, RevisionBlobs,
existing native process supervision and actual CallLedger/usage. No second
runtime ledger, fake Trial/Operation, arbitrary shell or provider switch.

**Spec/authority:** Full agent-skill spec9–14/22–24 and Goal3/5/6/12. Published source is C2727edcc, tree5712b6ba, identical to tested d05f4881.
Preserve engineering/business/rollout evidence separately. D1 is an engineering
subproject; D remains OPEN until the same resolver is integrated and verified
through production router/lazy/hub/native task/resume paths. E still owns atomic
manual live-pointer apply/revert/canary; F owns the complete6/6/6 operator flow.
This delivery split does not reduce D or full M0-M8.

Source update: C is now published0.296.0, actual merge
2727edcc5cdfab6f2dcf2e2871164f22f2771f92. Its tree
5712b6ba79720a5a44a43d3cecd85cff84f3cd21 exactly matches the independently reviewed
and tested d05f4881; CI39929264818 and actual publication39933347548 passed.
D1's exclusive branch now reserves0.297.0 in draftPR803 before code; reservation
c4991ec8 passed the bilingual changelog test. No source/runtime change yet.

## Global constraints and release preflight

- [x] Verify C finalCI39929264818, actual squash tree, and publication, then fetch
  main/open reservations and reserve the next free version in its own draft PR.
  Use the suitable existing managed worktree; preserve both synthetic histories
  and generated test keys. Never alter the original D:/Project checkout.
- [x] Resolve the actual published C commit for schema6 old-reader verification
  before any schema7 code or CI-fetch pin is written.
- Preserve old v1/v2/v3 request hashes, logical slots, historical replay and
  rejection of changed candidates/final runtime through those legacy versions.
- Only one user skill body changes; retain protected bytes/meaning, frontmatter,
  identity, disabled state, dependencies, model/reasoning, grants and ownership.
- Native enforcement/source/config qualification precedes real account inference.
  New source invalidates the old9dcf7184 registration; no readiness stub or
  generic environment/HTTP exemption can enable an unknown profile.
- Missing reasoning, semantic input use, asset use or telemetry remain unknown.
  Never upgrade C's combined verdict, A's immutable unreviewed status, or a
  comparison integrity unknown. An inconclusive comparison keeps baseline.
- Task impact and source-qualified reuse first; focused RED/GREEN, affected
  sequential regression at task end, early Linux paths/SQLite feedback, one
  independent whole-D1 review at stability and scoped fix verification only.

## Probe authority and preserved unknowns

The existing C native report deliberately retains `actual_reasoning` and
`actual_input_use` unknown. Its combined semantic/native verdict therefore cannot
be treated as a positive eligibility proof. D must not simply change that result
to pass in order to execute a candidate.

Define a separate host-derived **authorization for an isolated technical probe**:
current owner experiment/source/edit grants, exact before/after/provenance and
dependencies, settled protected-meaning assessment, exact qualified isolation,
matched model/session/installation and complete ownership must all be validated.
Known native failures or missing security/isolation/source evidence block before
call reservation. Unknown protected meaning remains owner-required; an owner
cannot erase a negative model assessment or native security failure. Any allowed
observational unknown must remain in receipts, result integrity, reports and
eligibility. Never infer a quality win or live permission from probe execution.

The permitted observation-only unknown IDs below follow spec10.3/13.1 and the
actual C check inventory; record this ruling in the task ledger. Do not introduce a public
`allow_unknown`, `candidate_ready`, `semantic_ok` or test-only production flag.
Fixtures may simulate an owner only in explicitly synthetic disposable scopes;
they are not human business/semantic acceptance of a real brain.

Self-review ruling under Goal3/5/6/12: the only observation-only
native unknowns a technical probe may retain are `actual_reasoning` with reason
`native_reasoning_unobserved`, and `actual_input_use` with reason
`semantic_input_use_unobserved`. Require the exact current ten-ID operation
check inventory with no duplicate/missing IDs; every other check must pass.
Either of those two IDs failing still blocks. A missing/mismatched model,
session, installation, tool inventory, side-effect boundary, protocol or complete
result cannot be waived. Require semantic assessment pass, or an unknown/
owner-required semantic component resolved by an exact current owner pass;
negative assessment or finding remains rejected. Dependencies must pass with
unchanged exact source/authority and no executable/unresolved node. This yields
only an internal `ProbeAuthority`, never a changed C combined verdict, semantic
eligibility flag, comparison integrity pass or live grant.

The source/spec self-review retains the following mandatory tests: observation-only unknown permits a labeled isolated probe and still
produces unknown/inconclusive comparison; every other native unknown/failure,
missing observation row, semantic failure/unresolved owner gate, changed grant
and dependency unknown denies before reservation. No public bypass parameter.
This rule preserves B's full native-check quality gate; it does not remove
actual_reasoning/asset_observed_use from comparison projection. Final independent
D1 review must judge this behavior and the exact actual evidence, not infer
approval from the existence of this plan.

## Task decomposition

## Review Focus

1. Cross-brain aliases, same-name paths, disabled canonical shadowing, UTF-8/BOM/
   CRLF and changed native ACL/file incarnation must not load a different view
   or promote a historical receipt (Tasks1/2/4).
2. Terminal SQL before published result/actual cleanup, concurrent owner-next,
   and cancelled admission handoff must not burn an immutable later cell or
   release owned capacity (Task3).
3. A source/grant/config edit during slow encrypted I/O, native spawn or result
   publication must fence current work and preserve actual cleanup/usage rather
   than replace a frozen baseline with a newly captured source (Tasks2–4).
4. Observation-only unknowns, stale semantic proof, owner-required protected
   meaning and model failures must stay distinct; no probe permission may
   become a quality win, rewritten A status or live eligibility (Tasks2/4).
5. Qualification consumption/crash/late retry and new runtime-format links must
   preserve every expected pair, old history and sealed answers without extra
   final candidates, double-counted cells or unrelated cleanup (Tasks3–5).

### Task 1 — immutable effective-view identity and schema7

**Files:** new `server/improvement_view_protocol.py`,
`server/improvement_view_schema.py`; modify `server/improvement_store.py`;
new `tests/python/test_improvement_views.py` and
`tests/python/test_improvement_view_schema.py` (actual SQL/backup/old reader).

**Interfaces:** `view_manifest(value)->dict` validates closed version1 data and
`view_hash(value)->str` hashes that canonical projection. It contains exact brain,
target/base/candidate identity, source/context/grant/config/semantic proof hashes,
ordered asset refs/hashes and protected dependency identities. IDs/blob hashes
that would create a self-reference stay in the outer SQL record. No caller
declares coverage, successful review, native readiness or authority.

Store immutable views, immutable ordered view assets, and one immutable
comparison-view binding in the same resonance DB. Bindings reference the actual
brain/comparison plus baseline/candidate view IDs, v4 runtime, encrypted proof and
current semantic receipt. Composite FKs/triggers prevent cross-brain/experiment
joins; cold readers neither migrate, decrypt nor probe. Do not create M0
canonical revisions or move target.current_revision_id for a candidate.

Preserve the exact released B/C table and guard definitions. A fourth additive
`improvement_view_trial_links` table belongs to Task3's actual v4 runtime, rather
than widening or repurposing legacy v2 links. Its comparison must already have
the exact immutable view binding. Additional guards prevent any legacy link
after a view binding and prevent binding after any legacy link. Every stop/
report/recovery/bounds consumer must deliberately resolve the comparison's one
runtime format, never double its allowed cells or omit its new actual links.
Do not fake a v4 Trial row to make Task1's metadata tests positive; genuine
Trial/call/link publication is Task3's completion gate.

- [x] RED: schema6 lacks view tables; forged body/hash/source/variant identity,
  mutable/foreign links, duplicate view variants/bindings and unknown schema reject.
  Legacy/v4 runtime exclusion remains Task3 as explicitly separated above.
- [x] GREEN: real encrypted metadata save/cold read, concurrent
  one-time byte-preserved migration backup, crash rollback and old-reader refusal.
- [x] Verify actual published C reader refuses schema7 and its backup restores
  exact historical schema6. Preserve all earlier backup boundaries.
- [x] Commit verified task; record exact source/test/command/runtime evidence.

Task1 local implementation evidence: six sequential affected scripts passed104
tests in221.921s, source/runtime/log-bound in
`../evidence/2026-10-23-m2d1-task1-verification.json` (SHA256
b9d7c51fd9725111678365f667b4af2168738b73329e89475ba2d700d52f76f8).
The actual task-done verifier checks committed bytes against the full retained
dependency/log evidence, without repeating already-passed tests. This is local
foundation completion; checkpoint Linux CI and full D1 review/runtime/final CI
remain open. WSL is unavailable; use the existing PR's automatic Linux workflow.

Task boundary ruling: positive atomic pair publication/CAS/event replay belongs
to Task2's concrete host publisher, which owns current source/semantic authority.
Task1 proves the schema/immutable scoped metadata and pure identity without
inventing a publish API or pretending metadata is execution authority. Task2
must prove the same event key returns its exact stored pair, changed payload
conflicts, and a second insert/source-CAS failure rolls back both views/binding.

### Task 2 — current host view capture and source authority

**Files:** new `server/improvement_views.py`,
`server/improvement_view_sources.py`; use actual SkillCandidates, ExperimentPlans
and SemanticReview; new `tests/python/test_improvement_view_sources.py` and
`tests/python/test_improvement_view_authority.py` (actual permissions, links,
source incarnation, line endings and owner-meaning integration).

**Interfaces:** `EffectiveViews(plans, semantic)` accepts concrete same-store
dependencies. `freeze_comparison(principal, comparison_id, *,
expected_generation,event_key)->metadata` derives both views under actual current
authority, then commits view rows/binding/event atomically. `read_existing`
returns cold metadata; `load_current` explicitly rechecks current authority.
Host interfaces are private; HTTP receives only the explicit closed control
fields and never constructs a ResolvedView/ProbeAuthority. The shared resolver returns exact bytes and identity for a given frozen
view/asset; no fallback to canonical, root-relative same-name or global mirror.

Task2 implementation checkpoint: first12 source/atomic/policy tests passed95.073s.
Actual same-event concurrent publication RED exposed stale-generation failure
after the first writer committed; replay now rechecks the exact immutable event
on source/generation denial, without granting new work. Pure RED also exposed
missing-verdict KeyError and ignored native aggregate failure; both now deny.
The service derives meaning/dependency/native observations only from actual
current C evidence, keeps its combined unknown and A unreviewed unchanged, and
stores the exact actual owner-event reference when required. This metadata/source
boundary is not D native qualification or real Trial admission. Task2 remains
open through its further authority/mutation tests and affected regression.

- [x] RED: changing/replacing/deleting/disabling/revoking source during encrypted
  I/O cannot publish or resolve a view. Actual native-preflight changes must deny
  before CallLedger reservation/query in Tasks3/4's real consumers; that integration
  remains mandatory rather than being simulated by Task2 metadata tests.
- [x] RED: existing comparison cells prevent retrospective runtime binding; a
  third candidate, unrelated semantic receipt, changed protected meaning or an
  executable/ungranted dependency cannot expand the view.
- [x] GREEN: baseline/candidate differ at exactly the owner-authorized body;
  all other protected/context/dependency bytes and identities match. UTF-8/BOM/
  CRLF remain exact, with no canonical or global mirror write.
- [x] Actual host pair publication is one writer/event with current generation
  CAS, cold exact replay, conflicting-payload rejection and complete rollback
  when a second view/binding/source fence fails. No partial eligible view exists.
- [x] Add actual ACL, directory/file incarnation, symlink/junction and Linux
  case-distinct brain tests using shared stable readers. No lowercase hash as
  authorization. Verify deterministic replays after off/revoke remain historical.
- [x] Commit verified source capture and exact-byte resolver.

Task2 local verification: five sequential affected scripts passed76 tests in
392.830s. Portable report `../evidence/2026-10-23-m2d1-task2-verification.json`,
SHA256588f7dba351d6d4253039819179207e467306163b14bfb7447d8c700d08fc41e.
Task-done validates actual committed source/runtime/log hashes without repeating
passed tests. New D native integration and Linux source/authority branches remain
unverified until their actual consumers/CI run. Earlier Task1 LinuxCI39938959026
passed the new schema15/protocol11 but failed three older migration fixtures;
correct those exact fixture expectations/drop lists next, before pushing this
checkpoint. No branch integration, new native qualification or live claim.

The three Linux-feedback fixtures are now corrected locally and their74 tests
passed sequentially34.537s. Evidence SHA256
641a71c203e8e42d2a09ee51c17195bcf2b1ce2af999fe2f8dc043a73bdaa5e0.
Only three named test methods changed; AST comparison verifies all imports,
fixture helpers and other methods unchanged from verified Task2 commit68dc6c26.
Application and all Task2 selected source bytes remain exact. Reuse its scoped
76-test evidence; require fresh Linux CI after this checkpoint is pushed.

Task2 completion scope: run the two new source/authority scripts, pure view
protocol, existing dependency-identity and comparison-plan regression sequentially.
Reuse Task1's exact schema7/migration/store evidence and C's source-qualified
structural/candidate/semantic implementation evidence: those source/helper bytes
are unchanged and the new tests traverse their actual concrete services. Full
final-head CI still runs every mandatory script. No blanket improvement sweep.

Additional REDs: view capture initially used the plan's all-case source projection;
the actual holdout-blob spy caught that read. It now requests the existing tuning
projection, including for common source resolution of a final view; actual final
case admission owns its separate qualification grant. Another negative fixture
constructed valid scoped encrypted SQL metadata without a real publication event;
load_current now requires the exact immutable event/result/request-hash/generation
history as well as current source/semantic proof. Cold metadata remains historical.
The source fence after both inserts rolls back all view/binding/event rows.

Supported byte tests retain existing discovery semantics: YAML CRLF and plain BOM
are byte-exact; BOM plus YAML remains rejected as ambiguous by unchanged M2A.
Windows native DACL mutation/rejection/restoration is actual. The first fixture's
icacls /restore cleanup lacked privilege; DACL-only native restoration now restores
the exact original descriptor hash without changing owner/group or requesting
privilege. This changes only disposable test cleanup, not source authority policy.

### Task 3 — explicit v4 admission and full paired/final lineage

**Files:** new `server/improvement_view_admission.py`; extend the actual Trial
request/host/lineage/SQL-trigger consumers, ExperimentService and comparison
runtime integration; focused new `test_improvement_view_admission.py`.

**Interfaces:** host-derived v4 preserves explicit comparison cell/case/repeat
lineage and adds exact frozen view/binding identity. Owner HTTP still cannot
select a cell, issue a pin/grant or submit an authority verdict. Only the
concrete service chooses the next frozen slot and reserves through the SAME
TrialStore/CallLedger transaction and real TrialTasks handoff. No fake baseline
or regenerated deadline for an existing admission. Legacy versions remain closed.

- [ ] RED: a valid-looking v4 caller cannot bypass the actual view binding;
  candidate/final requests through v1/v2/v3 remain rejected without decryption.
- [ ] RED: pending, terminal-without-result or SQL-completed-but-still-closing
  prior cells cannot burn the next immutable comparison link/call. Hold the
  actual brain execution barrier across slow admission and final SQL CAS, as
  preparation already does; historical replay precedes slow work.
- [ ] GREEN: genuine two-arm Trial/call/link admission, concurrent next callers,
  stop/off/revoke during preflight, cancelled HTTP handoff, crash and late result.
- [ ] Extend actual sealed final qualification reservation/consumption links;
  one final candidate only, no tuning fingerprint alias or reused consumed
  holdout, no private answers in solver/improver/view. Refund/usage rules unchanged.
- [ ] Verify current v1/v2/v3 metadata/reports and older reader histories remain
  exact; commit the complete new admission boundary.

### Task 4 — actual workspace/native view and result evidence

**Files:** new `server/improvement_view_materialization.py`; extend actual
TrialStore.materialize, sandbox/worker/TrialProfile, receipts/checks/results/
views/products/comparison projection. Add all new native-path sources to the
profile footprint. New `test_improvement_view_execution.py` and native opt-in
view qualification using exact pinned candidate and local dummy provider.

**Interfaces:** a closed v2 workspace manifest contains the resolved view assets
and exact common context/contract/fixture pins. Old v1 manifests render identical
old bytes. Installation/evidence records expose v4 view hash and exact revisions;
model-issued receipt text is never authority. New result projection validates
actual linked view/attempt/call/receipt before comparison; unknown observations
remain unknown rather than being omitted from mandatory integrity.

- [ ] RED: wrong view, stale source, missing installation, leaked host paths,
  mirror alias, ungranted tool, reused session or forged native event cannot
  produce successful installation/coverage or a report winner.
- [ ] GREEN: real Runner/workspace/Fernet/broker/kernel/CallLedger execution of
  baseline and candidate with identical common inputs; canonical/mirrors and
  all ordinary production learning/task/session stores remain untouched.
- [ ] Actual native local-provider qualification proves the selected engine saw
  the exact separate baseline/candidate installation and could not reach host
  brain/checkers/answers/shell/web/ambient source. Include actual worker/host/
  supervisor death, repeated cancellation and complete plaintext cleanup fences.
- [ ] Save full source/runtime/scenario hashes; register only the final exact
  qualified profile outside its hash. Perform necessary selected-model technical
  feasibility only afterward, with genuine usage and no rerun-until-win.
- [ ] Commit actual view execution/evidence, not an empty adapter or readiness
  flag. An inconclusive/rejected outcome is valid and keeps baseline.

### Task 5 — owned public controls, regressions and publication

**Files:** extend actual experiment owner API/service/requests/route snapshot,
operator guide, bilingual changelogs and progress; focused owner route/stop tests.

- [ ] Explicit owner view-freeze/current-evidence control is closed and CSRF/
  session protected; history stays cold after off/revoke. No API-token-only
  authoring, caller native proof or automatic next/model dispatch.
- [ ] Stop/recovery owns new view/admission/materialization/result threads,
  every actual Trial and native lifetime. No broad settlement of unrelated work
  or plaintext deletion based only on terminal SQL/PID state.
- [ ] Source-qualified affected regressions; early Linux checks before final
  stabilization; one independent whole-D1 review and scoped RED/GREEN fixes.
- [ ] Exact final-head full CI, fresh version/main, straight authorized merge,
  identical merged tree and actual publication. No deploy/restart/live activation.
- [ ] Record D1 engineering status and actual model/business/rollout separately;
  continue D2 production router/lazy/hub/native/task-pin integration. Do not
  call D, M2, M3-M8 or full Goal complete because this subproject ships.

## Self-review and interface freeze

Task1 metadata fields, SQL names, bounds and test commands are frozen below.
The probe-authority rule above retains all quality gates and old combined
verdicts. Finalize later task-specific internal field projections from these
closed contracts before each task's code; record any necessary interface ruling.
Check all new cross-version joins, immutable rows, old-reader gates and source
footprint; list affected callers before each task under Goal12. Production paths
must eventually serve this SAME resolver; a trial-only resolver is not the final
requested system and is not an acceptable replacement for D2/E/F.

## Concrete source-derived bounds and cross-version decisions

- Current C `MAX_ASSET_BYTES=1048576`; workspace assets have at most100 records,
  each at most that many bytes, and the rendered prompt is also bounded by this
  constant. v4 request metadata retains the current65536-byte limit. Keep these
  exact existing bounds; reject missing/oversized required input before a call,
  never drop protected data or truncate it to make a trial run.
- D1 still materializes one primary skill body. Existing textual protected
  dependencies remain part of the pinned common capture/semantic evidence, not
  newly executable files. No new helper path or script grant is introduced.
- Workspace v2 is the current v1 closed manifest plus one `effective_view`
  projection, with version2 explicit. Assets retain `{id,path,hash,content}`;
  baseline uses the real baseline revision ID and candidate the real A candidate
  identity, never a fabricated canonical revision. Its view asset descriptor
  must match every materialized asset exactly. Preserve old v1 rendering/hashes.
- Keep `bundle_hash` bound to existing experiment baseline/arm pins; store a
  separate `view_hash`, do not relabel an A envelope as an M0 bundle. The v2
  effective hash includes that view hash and all original context/contract/
  fixture/asset pins. Installation/result versions expose the same exact view.
- v4 keeps explicit comparison lineage and adds a closed `view` object with
  `{version:1,view_id,view_hash,binding_hash}`. The actual comparison binding maps
  the correct baseline/candidate view. Pure shape validation is never authority;
  current SQL/blob/source checks, immutable links and kernel barriers remain
  mandatory. Preserve exact v2/v3 validators, hashes and actual historical gates.
- A comparison without an explicit new view binding keeps its old metadata/
  baseline-only behavior. Do not retrofit a binding after any comparison cell
  exists. Preparation v3 results remain separate evidence and cannot fill paired
  v4 comparison slots. Scope/default policy capabilities remain fail-closed.
- Current C native operation checks are materialization, worker_protocol,
  installation, tool_inventory, side_effects, completion, actual_model,
  actual_reasoning, native_session and actual_input_use. `actual_reasoning` and
  `actual_input_use` are explicitly unknown by current implementation even when
  other observations match. B `project_result` requires its full18-check native
  set, including asset_observed_use/actual_reasoning, before successful integrity.
  Keep that unknown result; do not remove checks from B or claim the actual C
  role report can currently be entirely pass. A new technical probe authorization
  must be separately justified and must not become native/quality eligibility.
- Production D2 cannot claim support merely because these isolated views work.
  Its concrete ordinary Dashboard surface currently has exact keys
  `{kind:'dashboard',session_id,language}` and host-bound current session/config/
  SQL/file sources. Agent/Team/Coding contexts require their own later coverage,
  not an opaque caller descriptor or ordinary brain fallback.

## Frozen Task1 metadata contract

Pure version1 view manifest has exact fields:
`version,evidence_class,brain_id,experiment_id,context_id,context_generation,
comparison_id,comparison_hash,definition_hash,arm_ordinal,arm_hash,candidate_id,
variant,target,engine_config_hash,baseline_context_hash,contract_hash,case_set_hash,
grant_hash,scope_hash,policy_version,source_authority_hash,semantic,assets`.
`evidence_class` is exactly `technical`; `variant` is `baseline|candidate`.
The opaque view ID, manifest hash and manifest blob hash are outside the hashed
manifest. No field declares execution readiness, success, live status or owner
acceptance. Hashes are64 lowercase hex; actual IDs use existing128-character
identifier validation, brain ID uses the existing1000-character bound. Integer
version/generation/policy/ordinal checks reject booleans.

`target` has exact fields
`target_id,base_revision_id,base_hash,base_generation,canonical_ref,identity,
protected_hash,ownership`; ownership is `user_protected|user_managed`, and the
canonical ref is one user `skills/<slug>/SKILL.md`, with the existing slug/device
and traversal guards. `semantic` has exact fields
`receipt_id,binding_hash,assessment_hash,dependency_hash,owner_event_key`;
owner_event_key is null or the actual bounded owner event key, not an approval
boolean. Actual row and current proof matching is Task2, not this pure validator.
Its non-null length is8..160, matching the actual ImprovementStore event contract.

`assets` is exactly one primary body asset in D1, with exact fields
`id,canonical_ref,before_hash,content_hash,identity,authority_hash,origin`.
The path/identity/before hash match the target. Baseline origin is `baseline`,
ID equals the actual base revision and content hash equals base hash; candidate
origin is `candidate`, ID equals the actual candidate ID. Empty or identical
candidate body is handled by actual authoring policy, never by inventing a new
canonical revision. Protected dependencies remain unchanged common context.
Manifest JSON is bounded by MAX_ASSET_BYTES and preserves canonical JSON hashes.

Task1 schema names: `improvement_effective_views`,
`improvement_effective_view_assets`, `improvement_comparison_views`, each immutable
and scoped by actual brain/experiment/comparison/target/HostContext/A candidate
FKs. Views are unique per `(comparison_id,brain_id,variant)`; assets per
`(view_id,brain_id,position)` with position0 only; the comparison binding is unique
per `(comparison_id,brain_id)`, references the exact baseline/candidate views and
actual semantic receipt, and stores one encrypted binding hash/blob. Composite
FKs plus actual join triggers prevent matching individually valid foreign rows.
The extra v4 link table/legacy-link exclusion guards are Task3.

Task1 SQL columns are frozen before implementation: views store `id,brain_id,
experiment_id,target_id,context_id,comparison_id,variant,candidate_id,
base_revision_id,base_hash,base_generation,source_authority_hash,
semantic_receipt_id,manifest_hash,manifest_blob_hash,created_at`. Both variants
identify the comparison's actual A candidate and semantic receipt. Assets store
`view_id,brain_id,position,asset_id,canonical_ref,before_hash,content_hash,identity,
authority_hash,origin`. Bindings store `comparison_id,brain_id,base_view_id,
candidate_view_id,semantic_receipt_id,binding_hash,binding_blob_hash,created_at`.
Content-addressed manifest/binding hashes equal their encrypted blob addresses.
SQL joins enforce actual comparison/arm/candidate/base/context/receipt lineage
and asset identity/hash/origin, plus complete matching assets before binding.
SQL cannot authenticate encrypted plaintext: Task2 must revalidate exact manifest,
blob bytes, current grants/source/semantic authority and pair proof before use.
No runtime version, Trial link, eligibility or live activation flag is stored here.

Migration7 adds `.pre-improvement-m2-views.bak`, keyed by absence of
`improvement_effective_views`. Run it through the SAME writer serialization;
retain all prior backups and accepted known versions1..6 explicitly. Fresh DBs
retain pre-M0 behavior. Unknown8/999 versions reject before backup/write. C's
actual2727edcc reader refuses7; restoring the byte-preserved backup restores its
actual6 history. Current metadata test expectations advance from6 to7 only for
current migration results; historical backup versions stay exact. Existing
concurrent-boundary tests add precisely the new one-time backup, not a relaxed
count. Preserve C's same-number-prototype refusal before any role/view authority.

Task1 commands, sequential:
`python tests/python/test_improvement_views.py -v`,
`python tests/python/test_improvement_view_schema.py -v`,
`python tests/python/test_improvement_store.py -v`,
`python tests/python/test_improvement_operations.py -v`, and
`python tests/python/test_improvement_experiments.py -v`, and
`python tests/python/test_improvement_operation_execution.py -v`.
The sixth script is affected because its future-schema test used literal7;
schema7 is now known, so the same refusal test must exercise actual future8.
RED must prove the view protocol/schema are absent; GREEN must exercise real
SQL/encrypted metadata, old-reader refusal, exact backup/rollback, cross-scope and
immutable guards. No native/auth/model calls in Task1. The CI workflow must fetch
published C2727edcc for its actual schema6 reader just as it fetches A/B today.
