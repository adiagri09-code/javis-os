# M2B implementation plan: durable experiments and comparisons

Date: 2026-10-23 (Asia/Saigon).

Execution authority: docs/superpowers/AGENT-SKILL-IMPROVEMENT-GOAL.md and the full
29-section spec. Inline implementation, self-reviewed plans and independent final
review; no routine approval stop under the Goal's explicit authorization.

Actual baseline: published main cbef2f464932e533825512e8e11c2299e6b3bf4f,
version0.292.0, PR799. Required CI39862650038 passed on d4703f34, merged tree
identical; publication39865749261 succeeded on the actual merge. Original checkout
remains untouched. Reuse the existing managed M2 worktree with new branch
codex/agent-skill-improvement-m2b; retain ignored private evidence and worksheets.

Before code: reserve next free VERSION and both changelogs, push reservation and
open/attach draft PR. Engineering only until all required checks/review/publication;
no real-brain activation, production deploy/restart or live canary authorization.

## Outcome and explicit support

An owner can create one durable experiment for an existing exact Host context,
bind at most two actual A proposals, freeze complete counterbalanced comparisons,
execute actual tuning baseline slots, obtain immutable complete-pair reports and
seal KEEP_BASE or one final challenger. V1 requests/hashes/history stay unchanged.
B adds closed v2 lineage, not an alternate runtime/ledger/goal or generic model role.
Changed-arm execution remains unavailable before C semantic/dependency evidence
and D verified effective view. Qualification preflights BOTH variants before ANY
trial/call/global holdout claim/exposure. Until then it is blocked with zero evidence.
No compose, activation, eligibility from manual edit grant or alternate model.

## Review focus

1. Real schema4 migration/history/backup/old-reader refusal, no replayed DDL.
2. Exact context/contract/case-set/arm authority and immutable whole matrix.
3. V1 unchanged; v2 baseline has real trial/call/workspace/receipt/result lineage.
4. No early qualification call/claim/exposure; no renamed-family reset.
5. Stop retains worker/checker/process ownership through terminal cleanup.
6. Complete expected-slot accounting: unknown never disappears or becomes win.

## Task1 — schema5, records and state CAS

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


New server/improvement_experiment_schema.py, improvement_experiments.py and
Python test_improvement_experiments.py; modify improvement_store.py migration.
Reuse existing ImprovementStore._replay/_event and actual GoalStore._Tx.

Schema5 explicitly accepts known1/2/3/4/5, candidate DDL only<4, experiment only<5.
Unknown/newer rejects before backup/write. Fresh store preserves M0 backup policy;
installed store gets one serialized pre-experiment backup with documented contents.
Preserve exact old rows/events/request JSON/hashes/FKs/immutable triggers.

Tables: experiments immutable definition+mutable phase/generation/typed blocker/
resume_from/stop intent; immutable arms (actual A ordinal1|2/candidate/envelope);
comparisons (exact matrix blob/hash); immutable cell->real trial/request links;
one irreversible final selection; immutable report refs. Composite brain FKs and
context->experiment identity triggers. No delete or candidate replacement. Partial
unique active-brain index includes blocked and stopping.

Records require actual owner principal. Cold get/list do not ensure schema,
decrypt sources, warm native/auth/settings/usage or infer current authority.
All writer helpers require existing serialized transaction. Host-built verified
definitions only; caller IDs/policy are requests, not authorization assertions.
Terminal transitions releasing active capacity require stopping protocol in Task6.

RED/GREEN: real4->5 migration preserving actual A/M1 encrypted history; rollback,
concurrent ensure, serialized backup, cold old reads, unknown5+ refusal, same-brain
active conflict/foreign brain, immutable rows/CAS/event replay. Install actual4
using released four DDL blocks, never fake downgrade by editing version only.
Test actual released A reader refuses5 before writes; use repo's existing pinned
historical git-fetch pattern in CI if needed, missing history is failure not skip.
Older fixture installers must not leave B tables behind. Latest-version assertions
may use current constant; historical fixture/backup assertions retain literal4.

## Task2 — host definition, arms, matrix and irreversible selection

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


New improvement_comparison_plans.py and tests; narrowly extend A new-write guards.
ExperimentPlans(host,skill_candidates,checker_registry=None) requires actual
HostContextStore. prepare/create takes existing experiment/contract/case_set/
base_bundle IDs, expected context generation, feasibility|pilot repeat policy and
existing bounded timeout, event key. Host derives all pins/definition/hash.

Reuse TrialCaseAssociations._authority for context/grant/contract, then explicitly
repeat TrialAdmission._prepare's exact _association/context/experiment/contract/
grant/case_set-manifest checks. _authority alone does NOT authorize a case set.
Actual Host methods are _decode/_snapshot_binding/_grant. Verify full case membership,
actual current target/revision/bundle bytes and checker registry. Recheck after
slow reads and before final transaction commit. Definition freezes endpoint all_pass,
evaluator/decision policy/multiple-test count/source/config/grant/runtime fingerprints.
No task/answer/private paths in public metadata.

Bind actual A proposal via SkillCandidates._state/observe/read_proposal/_guard,
including original source authority, owner event, patch/provenance and ordinal.
New B context means explicit new owner staging/authorization: no transplant of
immutable old A proposals or rebind of case sets to a different contract. Changing
store/cases changes EVALUATOR_PIN; old contract/results remain readable history,
not permission to execute. Prepare fresh explicit contracts/context/cases.

One tuning comparison per challenger. Fresh baseline for each challenger, never
reuse diagnostic baseline. Final comparison spans qualification+regression for
one irreversible selected arm. Freeze full schedule before dispatch: repeats1
(feasibility) or2 (pilot), deterministic counterbalance from frozen host seed.
Compact ordered pairs {pair_id64,case_id<=128,repeat,first_variant}; position and
complement define both cell orders. <=1000 cases =>2000 pairs/4000 cells, ~518KiB
manifest; exact canonical UTF-8 bound1MiB, no task duplication/truncation/chunking.

KEEP_BASE is valid final outcome without holdout consumption. Selection seals
staging/region/diff grants before publication; revocation remains available.
Historical replay returns history, cannot restore grants or reopen comparisons.
A semantic_status stays immutable unreviewed; C adds separate evidence later.

RED/GREEN: unrelated same-brain case set; wrong context/contract/grant/hash;
manifest/current source/ACL drift during slow read/commit; old proposal under new
context; second-arm collision/third slot; duplicate freeze; max-size exact matrix;
source/seed/order substitution; stage/authorize after seal; KEEP_BASE/replay.

## Task3 — closed v2 and actual tuning-baseline execution

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


New improvement_experiment_protocol.py (pure), improvement_experiment_lineage.py
(scoped SQL/blob reads), improvement_experiment_admission.py and tests. Deliberate
version branches in trials/host/checks/service/results/views/private review.
Protocol imports no Host/TrialStore/CaseStore. Lineage imports no Host/TrialStore/
SkillCandidates/CandidateRecords backedge. Higher Plans verifies actual A bytes.

validate_request_v2 and validate_lineage verify full closed shape/hash/equality.
Keep v1 parser/hash/logical expression verbatim. V2 carries same nine pins plus
exact definition/comparison/challenger/pair hashes and identity. Both variants
share challenger identity; variant selects actual assets. Namespaced logical key
includes comparison/pair/case/repeat/variant. candidate_bundle_hash in v2 is typed
verified A envelope hash, never a claim it is an installed canonical bundle.

_current resolves actual baseline and trusted arm envelope; baseline materializes
actual revisions. Changed variant rejects before reservation/plaintext/worker
until C+D. Host._bound validates full v2 lineage before/after source observation.
Never strip fields/recast v1. Native baseline worker/receipt protocol stays exact:
comparison ->request hash ->real trial ID ->materialization ->worker input ->result.
Commit slot link/trial/call/event in same writer transaction. Mint actual deadline
after preflight, not matrix queue creation. Existing CallLedger usage IDs remain;
arm attribution joins immutable links. No new telemetry money ledger.

RED/GREEN: exact v1 regression/replay; v2 substitution/cross-brain/source drift;
actual baseline-v2 E2E with synthetic availability/query, real workspace/Fernet/SQL/
ledger; second challenger no identity collision; changed arm fails lower reserve
before call/plaintext/trial evidence; historical v2 reads without native probes.

## Task4 — one final qualification and both-variant readiness

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


Extend existing CaseStore qualification branch; no parallel registry. Preserve
shared fingerprint claims, case-set uniqueness and consumption-at-materialization.
New experiment-aware lower-store guard cannot be bypassed with legacy nine-pin
shape/version omission. Current M1 checks actual bundle existence; v2 substitutes
only the explicitly verified selected proposal branch, never global relaxation.

Both selected variants must be ready before any final comparison dispatch, claim
or exposure, and after slow preflight/inside first claim+lineage+reservation commit.
Use same final nine-pin set for both; full extra lineage binds frozen comparison.
Regression cells also require final readiness. Until C+D actual profile ready,
no baseline qualification call/claim/exposure. Label synthetic readiness tests only.
Consumption/drift keeps original claims/final arm; fixed-candidate resume only.
No hidden ordinary wrong-answer retry or renamed experiment/case-family reuse.

RED/GREEN: direct lower-store unavailable candidate blocks baseline too; version
omission bypass; drift at claim/materialization; renamed families/case sets; wrong
final arm; duplicate consumption; KEEP_BASE zero claims; consumed source drift and
explicit recovery. Preserve owner-private artifact reads versus model projections.

## Task5 — pure comparator and immutable exact-result reports

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


New improvement_comparison_results.py and tests. Enumerate expected cells first.
Select exact linked trial/attempt/result_id/result_hash, read via TrialResults.read
with explicit result ID. Verify brain/request/comparison/pair/variant/arm/contract/
case/evaluator pins before/after slow work. Latest pointer changes cannot alter
old reports. Missing/corrupt/stale result is incomplete, not silently dropped.

Separate execution integrity, product criteria, required regression and repeat
stability. Baseline infrastructure failure is unknown/incomplete, not challenger
win. Binary all_pass only until real numeric metrics exist. Per-criterion required
loss rejects regardless primary gain. Complete W/L/tie/unknown and conservative
one-sided exact sign test only after integrity/coverage. Pilot requires >=20 real
independent qualification families, >=12 regression cases, two repeats/variant,
>=5 discordants and p<=0.05/M with declared M, no required loss. Feasibility6/6/6
cannot satisfy pilot. Unknown/unstable blocks completeness. No endpoint switching.

Report stores ordered [cell_position,result_id,result_hash] (~819KiB max plus
bounded aggregate); exact1MiB canonical byte limit. Full details stay immutable
TrialResults. Experiment summary references comparison reports, never flattens
all detailed criteria into one oversize blob. Reevaluation appends new report.
Encrypted report+event publishes under CAS after authority revalidation. No report
activates or certifies present runtime from historical source hashes.

RED/GREEN: baseline win/tie/unknown/rejection/inconclusive; missing critical/regression,
repeat disagreement; wrong result attempt/arm/pair; mutable pointer races; corrupt
refs/byte bounds; exact statistical boundary and multiple-test correction.

## Task6 — owner API, stopping/recovery, qualification and release

- [ ] Reproduce the named behavioral RED cases.
- [ ] Implement this unit and inspect its exact source/authority boundaries.
- [ ] Run named GREEN/regression checks, record actual evidence and commit the unit.


New improvement_experiment_api.py/tests; concrete service/main lifetime wiring;
intentional route snapshot, runbook/status/vi-en errors. Full prep/navigation is F.
Closed owner controls: metadata list/get, create, bind arm, freeze comparison,
next slot, report, final selection, cancel/resume/recover. Host chooses next slot,
not caller cherry-picking. B no compose/apply/activation action. Reuse bounded
JSON/owner-session-before-body/CSRF/cross-brain/CAS/event semantics and lazy startup.

begin_stop(...expected_generation,kind,reason,event_key)->StopTicket commits durable
stopping fence/desired terminal; retains active index. Every v2 reserve/claim/
heartbeat/start/finish guard rejects stopping. Service drains pending admissions,
cancels actual linked nonterminal trials through existing service and drains all
owned tasks including DB-terminal rows OUTSIDE writer transactions. Expose
TrialTasks.drain_owned(principal,trial_ids). Foreign worker is not locally owned.
finish_stop nonblocking-acquires existing brain execution lock, cleans linked
terminal workspaces outside SQL writer, then short final CAS while holding lock.
Busy foreign worker or cleanup failure remains stopping; explicit recover retries
closure without dispatch. No fabricated trial ID for brain-only lock helper.
Never call public TrialStore.cancel inside experiment writer (nested transaction/
postcommit FS cleanup). Shutdown cleans own tasks, not implicit foreign cancellation.
All capacity-releasing terminal outcomes, including KEEP_BASE/stale/rejected/
inconclusive, use stop/drain/finalize. Late checker result cannot reopen stopped
experiment. Persist observations and genuine usage settlement through abort/recovery.

Tests: owner/token/CSRF/bounds/cold no-probe GET; stale/concurrent next; repeated
HTTP cancellation; cancel during native launch/checker/write/cleanup; DB terminal
but process alive; foreign live lock; restart/recovery no dispatch; lazy import.

Exposing TrialWorkspace brain-only lock changes improvement_sandbox.py and thus
native four-file profile hash. Rerun exact selected runtime qualification using
existing dummy HOME/auth+localhost fake-provider test protocol and save current
sanitized evidence; oldc3b is historical, not new-source proof. No real account
needed for that technical qualification. Real baseline-v2 smoke only after exact
selected config/runtime verified, with usage and unknown coverage honest; never
rerun to obtain a win. No arbitrary model-generated Python execution: command_ok
needs independently verified isolated runtime, remains unsupported before that.

Run relevant migration/permission/prompt/security/ledger/learning/Team/lifetime/
UI/route checks. Fresh whole-B independent review, fix actual reproduced issues,
final exact-head Linux CI, fresh version/main checks, straight merge and publication
success. Preserve M1 encrypted smoke history/key. Continue C against actual published
source, old B contexts may legitimately become stale after C/D code changes.

## Arm edit authority detail

SkillCandidates.read_proposal verifies original immutable authoring bytes, not a
current execution grant (private reads deliberately survive edit revocation).
B arm binding must additionally choose and pin one actual active edit authority:
original editable-region grant or an exact-diff grant bound to this candidate's
before/after bytes/context/target/source authority. Pin authority ID/generation/hash
in the immutable envelope, revalidate status and complete identity at dispatch/
qualification/query/publication. Never trust CandidateRecords' display-priority
edit_authority alone, never auto-switch to another grant after pinned revocation.
An explicitly later exact-diff authorization can authorize actual bytes after an
older region was revoked; this does not revive that older region. After sealing,
no new authorize/stage/region action can refresh the pinned experiment. Tests must
separate historical readable proposal, unauthorized proposal, revoked chosen grant,
explicit fresh exact-diff grant, and revocation during slow arm publication.

## Report evidence-class boundary

Distinct family keys/source fingerprints enforce declared case separation, not a
proof of real-world statistical independence. B source inputs have no accepted
business-dataset attestation today. Reports must preserve that limitation and the
technical/synthetic evidence label; a hypothetical complete synthetic20/12 matrix
may pass the pure numerical gate in tests, never become business eligibility.
Freeze evidence class/provenance in definition; do not accept a caller/model string
as an accepted real dataset. Until actual M3 owner/data review exists, persisted
reports expose mechanical coverage/statistics separately and business eligibility
unverified. E cannot use a technically passing report to bypass real dataset/
semantic/runtime/scope prerequisites. No invented independence from distinct IDs,
multiple rows/repeats or multiple examples of one historical bug family.

## Transport projection detail

Principal.brain_id is the canonical absolute source root internally. New public
experiment/list/status projections must omit it and any native root/paths/raw
bindings; use authenticated requested brain label/opaque IDs/hash/status instead.
A already does this. Stored phase/metadata on GET is not a fresh source/native
availability claim: expose not_checked/unavailable where appropriate. Explicit
owner preflight/write may observe source/config; cold lists never warm source or
probe auth/model. Keep cryptography/native service imports inside actual operations;
run existing khoi_dong_nhe after API wiring, not only at final full CI.

Task6 concrete service file: create server/improvement_experiment_service.py and
its lifetime tests instead of growing main or admission with async ownership code.
TrialWorkspace.try_cleanup returns False for both already-absent and busy lifetime;
finish_stop must prove linked terminal workspace/journal absent or successfully
cleaned under the actual existing brain lock, not interpret every False as success.
Do not delete unrelated journals/workspaces. Terminal finish replay never resumes
or creates a new stop intent; retain original stop event/generation and historical
acknowledgment, refresh current metadata separately. Add failure-between-cleanup/
final-CAS and repeated cancellation of stop tests.


## Self-review and implementation gates

- [x] Actual published A source and final-head CI/publication verified; no assumed
  API names substitute for source. Reused M0/M1/A pieces are identified per task.
- [x] Independent draft-review findings corrected: exact case-set association,
  fresh context/proposal lineage, immutable result refs, chosen active edit grant,
  real stop ownership and explicit technical/business evidence distinction.
- [x] V1/source/owner/grant/model/runtime invariants retained. Unknown effort and
  semantic use are not promoted to pass. Later C/D changes may stale B contexts.
- [ ] Complete six units with meaningful RED/GREEN, current-source qualification
  and required scope/migration/lifetime regressions.
- [ ] Fresh independent whole-branch review; fix reproduced findings and verify.
- [ ] Final exact-head Linux CI; fresh main/version/head checks; straight merge
  and actual build/publication success. Continue C on integrated source.

No mock-only result, planned matrix, manual edit approval or technical statistic
fulfills the complete M2/business/rollout milestones. Preserve all three statuses.
