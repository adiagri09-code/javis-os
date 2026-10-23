# M2C generated proposals and semantic evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. The Goal explicitly selects inline
> execution with self-reviewed plans and an independent final review.

Status: design refinement / release reservation. No C product code has been
written. Complete the concrete schema/protocol/ownership contract audit and
self-review before taking Task1; an unfinished plan is not implementation.

**Goal:** Produce bounded real model-generated skill proposals and separately
pinned semantic/dependency assessments from authorized tuning evidence, with
honest per-role usage, durable cancellation/recovery and no premature activation.

**Architecture:** Extend the existing experiment ownership with genuine typed
preparation baseline Trials, then distinct proposer/reviewer operations backed by
the existing CallLedger and usage pipeline. Preserve A proposals and B comparison
lineage; semantic evidence is append-only, not an edit to A's immutable unreviewed
status. The same real brain execution barrier covers every enabled native role.

**Tech Stack:** Existing Python/FastAPI/SQLite/Fernet, asyncio supervisors,
Claude SDK/selected CLI fixture-only worker; standalone unittest scripts and
GitHub exact-head Linux CI. No new provider/account/money ledger/Goal.

**Spec:** docs/superpowers/specs/2026-10-22-agent-skill-evidence-improvement-design.md
sections9–12,18,23,26–29 and AGENT-SKILL-IMPROVEMENT-GOAL.md. Actual published B
baseline47f50f707268681dd4cbe8c7e443945155376237,0.293.0, PR800. Exact-head
CI39880551488 passed on2fe944ae; merged tree4e53048721ca658f620a73361b4281326852e3b6
is identical. Actual GHCR publication39882926274 and Build & push succeeded.
No deployment/restart/activation or complete M2/business/rollout acceptance.

## Global Constraints

- Keep the owner's selected engine/model/reasoning and existing quality gates.
  No monetary cap, alternate model or reduced source/validation to save usage.
- No qualification/regression/private answer material in improver input. Distinct
  family IDs do not prove business independence. Preserve technical labels.
- At most two actual proposals; at most one structural-repair request for a
  generated batch. No retry-until-win, invented candidate or placeholder arm.
- Trial/native operations never change canonical skills, protected owner rules,
  enabled state, source permission, mirrors or live memory. No host execution of
  arbitrary model-produced Python/commands/helpers. command_ok stays unsupported.
- Existing v1/v2 request/hash/history/replay semantics remain intact. New typed
  preparation execution must not become a legacy downgrade or readiness boolean.
- New native-role code belongs in the explicit profile source footprint and must
  pass exact selected-runtime fake-provider qualification before real execution.
- Actual effort/asset use/usage coverage remain unknown when not observable.
  Delivered request arguments and provider-effective behavior stay distinct.
- Owner product confirmation is not semantic/runtime/source acceptance or an
  activation grant. Candidate/final execution still requires D's actual view.
- Suggest mode never autonomously starts model work; owner intent must authorize
  every supported operation. Off/revoked blocks new work but permits settlement.
- Before product code, reserve next free VERSION/both changelogs and open/attach
  draft PR under repo rules. No production deploy/restart/live canary.

## Review Focus

1. Baseline-first workflow must work inside an existing durable experiment,
   without fake arms, hidden holdout use or orphan pre-B work.
2. A model cannot mint owner authority, role identity, arbitrary evidence refs,
   helpers, native flags or accepted semantic/runtime status.
3. Every preparation Trial and role call participates in stop/recovery ownership,
   even when its database row is terminal but a worker/checker is still alive.
4. Slow model/blob/source work cannot publish stale proposals or semantic receipts.
5. Limits/repair/idempotency cannot leak a third candidate or reset exposure after
   interruption; incomplete native evidence cannot silently become pass or zero.

## File/Interface Map

New focused modules (confirm names at canonicalization; no code stubs as output):
- improvement_preparation_protocol.py: pure closed request-v3/schedule identity.
- improvement_preparation.py: concrete host-derived preparation schedule/admission.
- improvement_operation_schema.py / improvement_operation_records.py: schema6
  immutable inputs/results/links, real call attempts/leases and bounded repair.
- improvement_operation_protocol.py: pure closed role requests/events/receipts.
- improvement_operation_workspace.py / improvement_operation_worker.py:
  real operation-ID workspace/native process boundary, not fake Trial receipts.
- improvement_operation_runner.py / improvement_operation_tasks.py:
  owned native role execution, actual usage settlement and cleanup.
- improvement_improver_inputs.py: fresh authorized tuning projection only.
- improvement_proposals.py: concrete bounded generation/repair/publication.
- improvement_semantic_review.py: pinned semantic/dependency assessment evidence.
- improvement_operation_api.py: closed owner controls/cold history projections.

Modify actual consumers: improvement_store.py; TrialStore request/current/reserve/
materialization; HostContextStore binding/context_loader/live_guard; trial result,
evidence/private/product/views; CallLedger purposes; turn_context/usage telemetry;
native profile source list; ExperimentService actual stop snapshots; main lazy
lifetime wiring. Keep files focused and avoid growing main with async ownership.

## Task 1 — schema6, preparation schedule and operation ownership

Interfaces: concrete PreparationRecords/OperationRecords(assets), cold metadata
reads, existing writer-owned transitions. Add immutable host-derived preparation
schedule/actual Trial links and role operation requests/attempts/results/evidence;
reuse agent_calls IDs. Exact schema/column names are finalized after reading the
current schema/CallLedger transaction contract, before writing migration code.

- [ ] Read current schema5, B final publication and source rules; reserve release.
- [ ] Write migration/old-reader/rollback/immutable-scope tests; run expected RED.
- [ ] Implement schema6 in existing DB with one serialized pre-migration backup,
  safe fresh schema path and actual released B old-reader refusal before writes.
- [ ] Preparation state uses B proposed→preparing CAS and retains brain capacity.
  Freeze complete tuning membership/repeats into a real schedule; no arm/candidate.
- [ ] Actual preparation-Trial links are immutable and atomic with real trial,
  attempt, CallLedger reservation and event. Don't UPDATE immutable schedule rows
  to attach later trials. Operation records reference actual call attempts.
- [ ] Close role/status/ordinal/repair constraints; cold GET cannot migrate/probe.
- [ ] GREEN scoped migration/permission/replay tests; commit with evidence.

## Task 2 — genuine preparation baseline through existing solver

Interfaces: validate_preparation_request_v3, logical_key_v3, load_preparation_lineage;
PreparationService.admit_next(owner, experiment_id, expected_generation,event_key)
returns the existing AdmittedTrial shape backed by real rows. A preparation
request has version3, baseline only, exact common source/config/definition pins,
host schedule/cell identity and no candidate/arm/comparison fiction. Choose exact
closed pins after auditing all consumers, retaining v1/v2 expressions unchanged.

- [ ] Behavioral RED: existing experiment/no candidate can prepare a real tuning
  baseline; arbitrary cell/qualification/alias/role/pin substitutions reject.
- [ ] Update every version consumer: TrialStore; Host binding/context/guard;
  materialization; engine markers/observations; TrialResults exact immutable refs;
  public/private/product/evidence views. A parser-only extension is insufficient.
- [ ] Host chooses next complete frozen tuning slot without gaps/cherry-picking;
  native preflight precedes atomic actual admission and late deadline minting.
- [ ] Use the SAME existing TrialTasks dispatcher/Runner/CallLedger/usage.
  Preparation results are tuning evidence and cannot be paired v2 report cells.
- [ ] Real synthetic-packet E2E proves workspace/output/result lineage and partial
  usage; replay stays exact after stopping/revoke, not a fresh execution grant.
- [ ] Test concurrent next, current-source/config/grant drift after slow IO,
  interruption before/after reserve/handoff and no holdout allocation/exposure.
- [ ] GREEN old v1/v2 parser/hash/authority/result regressions; commit.

## Task 3 — distinct real role/usage identities

Interfaces: closed operation metadata with operation_id/attempt/experiment_id,
actual host-issued role improver|semantic_reviewer and purpose improve_propose|
improve_evaluate; no fabricated trial_id/case_id. Native operation recorder verifies
the actual CallLedger purpose/mirror/brain/model/engine marker before persistence.

- [ ] RED: existing ledger/metadata rejects genuine role operations; forged
  model role/brain/call refs and cross-role result packets must still reject.
- [ ] Extend actual CallLedger purpose schema/allowlist and closed turn metadata,
  preserving Team and Trial formats and historical parsers byte-for-byte.
- [ ] Reuse usage events/index for operation-specific request/token/coverage
  attribution. Expose null for unknown counts; equivalent price is not cash billing.
- [ ] Preserve learning_origin filtering for every native role; source trials,
  semantic review and proposal messages cannot seed production lessons/jobs.
- [ ] Test engine-marker interruption/refund, late telemetry, replay, foreign
  call identity, mixed role/session packets, usage-index reads and Team regressions.
- [ ] GREEN meaningful role/usage/learning/ledger checks; commit.

## Task 4 — native role worker, workspace and owned lifecycle

Interfaces: concrete OperationRunner/OperationTasks over actual operation rows,
with typed operation-ID receipts/events. Share the real brain execution lock
with TrialWorkspace; keep distinct actual operation attempt lifetime locks.

- [ ] RED: prepare/launch/drain/recover real synthetic role operations using the
  existing selected engine adapter; arbitrary host/code/tool capability rejects.
- [ ] Implement bounded role input/output/event schema and native start handshake.
  Commit CallLedger engine marker before allowing actual query data through.
- [ ] Own preflight→reserve→handoff through repeated HTTP cancellation and shutdown;
  refund only genuine unused reservations, settle observed starts interrupted.
- [ ] No ambient hooks/plugins/skills/native Read/Bash/web/connectors; only actual
  preloaded fixture capability and immutable role input. No arbitrary evaluator
  code/script/registry from a model or HTTP body.
- [ ] Include every new role worker/renderer/workspace source in explicit native
  profile footprint; version the profile. Historical results remain historical.
- [ ] Test malformed packets, foreign live brain lock, lease expiry, cleanup
  failure, engine/checker/live-task after DB terminal and late result publication.
- [ ] GREEN lifecycle/legacy native boundary tests; commit; no real account yet.

## Task 5 — actual tuning projection and generation contract

Interfaces: ImproverInputs.build(owner,experiment_id,expected_generation) returns
bounded immutable data/hash/refs from actual preparation results and authorized
tuning snapshots; render_proposer_input is a pure data renderer.

- [ ] RED: private answers/qualification/regression/unrelated artifact cannot be
  substituted, even after case relabel/clone/shared qualification fingerprint.
- [ ] Load exact actual tuning result IDs/hashes, artifacts/source/public contract,
  baseline bytes and protected context. Never reuse PrivateReview as a model API.
- [ ] Separate infrastructure/native/usage unknown from task deficiency. No CoT;
  preserve authorized traces with timing/tool/result/artifact/error evidence only.
- [ ] Reject credential-bearing/insufficient source, stale grants/config/bytes and
  extra instructions outside the task. Pin recipe refs only when actually scoped
  and authorized; no whole recipe library or truncated required business input.
- [ ] Closed generation output: ≤2 genuine body patches, hypothesis/affected
  component/evidence refs and not_a_target_defect for infrastructure causes.
- [ ] Revalidate current authority after last slow read and before publication.
- [ ] GREEN data-minimization/source/fingerprint/injection tests; commit.

## Task 6 — bounded generated proposal and repair publication

Interfaces: ProposalService.generate(owner,experiment_id,expected_generation,
event_key) and actual durable batch/repair records. Connect real improve_propose
operations to A's existing validator/staging with immutable generated provenance.

- [ ] RED: native synthetic output becomes exact A proposals with actual role
  call/result refs; a malformed batch gets at most one durable structural repair.
- [ ] Validate the entire batch before publishing any proposals; crash/replay/
  repair cannot consume a third A slot or partially authorize invalid output.
- [ ] Factor a transaction-owned A stage primitive only where necessary; preserve
  existing manual API/replay/hash behavior. Publish original owner intent, real
  operation artifact hash and candidate link atomically under final source CAS.
- [ ] Keep A semantic_status=unreviewed immutable. An editable region authorizes
  only actual granted bytes; generation never mints exact-diff/source grants.
  Proposals without edit authority remain readable/staged and unavailable to run.
- [ ] Test protected/frontmatter/description/ownership/enabled/dependency escapes,
  stale source after native output, concurrent generate/repair and cancellation.
- [ ] GREEN genuine generation/repair/private-review/old-A regressions; commit.

## Task 7 — semantic/dependency evidence with exact provenance

Interfaces: SemanticReview.review(owner,candidate_id,expected_generation,event_key)
uses actual improve_evaluate operation(s); current_evidence validates concrete
immutable result refs, before/after bytes, protected context, dependency closure,
source authority and selected engine/evaluator/config. No generic readiness flag.

- [ ] RED: merely retaining protected text while adding contradictory instructions
  does not establish eligibility; missing helpers/changed closure remain unresolved.
- [ ] Deterministically verify body/frontmatter/paths/current dependency bytes and
  actual scope. A model's asserted helper or source path is never authority.
- [ ] Obtain genuine model semantic assessment over authorized exact before/after
  data; strict output schema and actual native/usage coverage remain separate from
  its claimed score. No majority vote or invented reviewer independence.
- [ ] Append receipts; do not UPDATE A's original provenance/status. Bind exact
  real operation input/output IDs/hashes and source/runtime/evaluator versions.
- [ ] Preserve unknown/disagreement/owner-required. Typed owner arbitration is
  exact artifact/scope; product owner-confirm cannot waive semantic/runtime drift.
- [ ] Revalidate after slow model/blob work and at consumption; stale/revoked
  receipts remain historical, never reactivate grants or accept changed bytes.
- [ ] Candidate/final execution still closed until actual D view enforcement;
  semantic assessment alone never allocates holdout, composes, applies or activates.
- [ ] GREEN protected-meaning/dependency/receipt/owner-scope tests; commit.

## Task 8 — owner controls and complete shared stop ownership

Interfaces: concrete owner preparation/proposal/semantic operations, cold lists/
history and current metadata; existing ExperimentService integrates all actual
preparation Trial links and native operation lifetimes in its final stop snapshot.

- [ ] RED owner/token/CSRF/bounds/cross-brain/CAS/event tests for every new route.
- [ ] Lazy main factories share existing TrialService and close operation services
  before underlying stores/sources. Ordinary GET does not capture/probe/recover.
- [ ] Commit stopping first, join all admission/handoff operations, cancel linked
  real Trials and owned role operations outside writer, drain DB-terminal live
  tasks/checkers, take actual brain lock, prove exact scoped cleanup, final CAS.
- [ ] No unrelated journal/reservation/role operation cleanup or settlement.
  Preserve B P2 regression, original acknowledgments and current metadata split.
- [ ] Derive combined limits: B12000 comparison cells + up to2000 preparation
  cells; update all drain/recovery/attempt bounds consistently and test full-bound
  valid ownership versus oversized inputs. Include real role call attempts too.
- [ ] Resume/recover never dispatches automatically or regrants. Frozen source
  drift/off/revoke closes new work while cancellation and usage settlement survive.
- [ ] Add vi/en fixed errors and operating docs; broader wizard/navigation is F.
- [ ] GREEN actual-main/lifetime/old owner/route/startup regressions; commit.

## Task 9 — current-profile qualification, whole review and publication

- [ ] Run exact selected CLI/SDK dummy-HOME/config/auth + localhost fake-provider
  blackbox qualification for actual solver/proposer/reviewer profiles, including
  ambient source/plugin/hook/tool canaries, request identity and cancellation tree.
- [ ] Save sanitized current source hashes and constraints; old real-smoke profile
  remains06e75, unknown reasoning/asset use stays unknown on all later profiles.
- [ ] Only after current configuration/runtime verified, perform a necessary real
  technical role feasibility in a disposable authorized brain, with genuine usage.
  No rerun-until-win, alternate model, accepted business/semantic claim or live grant.
- [ ] Run relevant migration/permissions/source/ledger/usage/learning/Team/prompt/
  UI/route/startup regressions and current old-v1/v2 baseline/report/lifetime checks.
- [ ] Fresh whole-C independent review. Reproduce actual Important findings RED,
  fix and verify; no fake readiness/adapter or scope reduction to obtain green.
- [ ] Rewrite both changelogs around the final verified implementation before the
  last CI run; reservation wording is not final release documentation.
- [ ] Exact final-head Linux CI, fresh main/version/head checks, authorized straight
  merge, merged-tree equality and actual publication success. No deploy/restart.
- [ ] Update engineering/business/rollout progress separately and continue D's
  real effective view. Positive final qualification, business pilot, activation,
  later agent/skill expansion and full M0–M8 remain open until actual evidence.

## Pre-flight interface audit for canonicalization

T1→T2: schedule identity/Trial link must be real, frozen and atomic; no fake arm.
T1→T3/T4: operation attempt/call/role identity must exist before native start.
T2→T5: preparation result lineage is not paired comparison evidence or holdout.
T3/T4→T6/T7: actual role events/usage/native result refs, never model authority.
T6→T7: immutable A proposal provenance stays unreviewed; receipts separate.
T1/T2/T4→T8: every actual owner participates in stop snapshot/locks/cleanup/CAS.
T4→T9: profile footprint includes new role-native code, not old proof inheritance.
T7→D: exact current semantic/source/dependency evidence cannot waive actual view,
runtime/config, qualification secrecy or owner activation prerequisites.

Before code, resolve concrete schema columns/parser fields/file names against
published source, freeze signatures in the canonical plan, self-review it under
the Goal's explicit inline/self-review authorization, then take Task1 with the
actual task-start script and a C-scoped ledger. No C implementation is complete
merely because this draft exists.
