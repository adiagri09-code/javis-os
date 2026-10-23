# Durable skill experiments, M2B

This boundary stores proposed experiment identity and immutable comparison
lineage in the existing resonance database. It is not a new Goal, monetary
ledger, execution grant or production activation pointer. M2B is being implemented
in six units; this document records the implemented storage unit first.

## Schema5 and recovery

Known improvement schemas1–4 upgrade transactionally to5. Only absent schema
blocks run: schema3 trial DDL and schema4 candidate DDL/triggers are not replayed.
Unknown/newer versions fail before backup or migration. Before an existing
improvement store upgrades, one serialized SQLite backup is retained at
`resonance.sqlite3.pre-improvement-m2-experiments.bak`. It contains the actual
pre-upgrade version and WAL-visible data. Fresh stores retain the M0 backup policy.
Earlier `.pre-improvement-m2-candidates.bak` backups remain historical; they are
not overwritten or removed. Restore only with stopped writers and compatible
application code, preserving encrypted blobs and their existing encryption key.

The actual released0.292.0 store reader rejects schema5 before an improvement
write. Its exact released source is fetched explicitly by CI for this test;
missing history is a failure, not a skipped assertion. Migration tests construct
actual schema4 with the four released DDL blocks and retain real encrypted A
proposals, M1 context/case/contract/holdout history, trial requests and ledger calls.

New tables hold experiments, proposal arms, comparisons, real trial links,
irreversible final selection and report references. Composite brain foreign keys,
immutable history triggers and scope checks protect their relationships. The
single active-brain index includes `blocked` and `stopping`. A recorded stop is
not proof that a process ended. Terminal state cannot be written directly from
an active phase; actual service drainage/finalization belongs to the later unit.

## Proposed metadata and explicit state changes

`ExperimentRecords` requires a concrete existing ImprovementStore and owner
principal. `get/list` never migrate, decrypt blobs, observe native sources,
read settings/authentication, refresh usage or recover work. Public metadata
omits canonical brain paths and labels current authority `not_checked`.

`create` persists a closed host-built definition in the `proposed` phase. It
checks exact context/grant/target/base/bundle/contract/case-set association and
current SQL generations. This is metadata validation; the later Plans service
must also observe actual source bytes/permissions before committing new work.
HTTP must not accept a caller-supplied definition as that host authority.

The definition freezes context/source/config hashes, baseline, declared endpoint,
evaluator, repeat/timeout and decision policy. B currently labels evidence
`technical`; caller strings cannot assert an accepted business dataset. Distinct
family keys alone do not prove real-world statistical independence. New
experiments require fresh compatible contexts and proposals when source or
evaluator code changes. Historical metadata stays readable.

`block`, host-preflight `resume` and `begin_stop` use generations and existing
owner events atomically. Resume requires a changed observed blocker fingerprint
and still-current SQL authority; the fingerprint is a trusted host output, never
an HTTP authority field. Source/native observations remain mandatory before
dispatch. Stop is available after policy-off or source revocation so cleanup
cannot be prevented by a missing improvement grant.

Event replay returns the original acknowledgment. It does not reset phase,
restore a grant or dispatch a query. `begin_stop` retains the active capacity
fence; later service code must settle actual worker/checker/workspace ownership
before finalizing. No automatic recovery, model retry or activation exists in
this storage unit. A candidate's immutable semantic status remains `unreviewed`.

## Host plans and frozen comparisons

The internal ExperimentPlans path derives definition pins from an existing exact
Host context, contract, associated case set and canonical baseline bundle. It
observes current sources around slow reads and before commit. Owner inputs cannot
assert hashes, evaluator identity, accepted-business evidence or repeat counts.
The fixed multiple-test family is two proposals, frozen before any results.

Each bound arm verifies actual encrypted A bytes, patch, provenance and original
owner event, and pins one explicitly chosen active region/exact-diff authority.
Revoking that chosen authority makes new comparison work unavailable; another
active grant cannot silently replace it. Historical metadata replay grants no
new authority. Semantic status remains unreviewed.

Tuning freezes every tuning case/repeat as a complete compact encrypted schedule,
with two complementary variant cells per pair and balanced ordering. Each arm
gets its own fresh baseline identity. No call, trial, holdout claim or answer
projection occurs during planning. Maximum1000-case/two-repeat matrices fit the
exact1MiB byte bound without truncation.

KEEP_BASE commits the irreversible selection and stopping intent together,
including when sources are revoked or improvement policy is off. It retains
capacity pending actual worker cleanup. New staging/region/diff writes reject
after sealing; prior replay, private authorized history and revoke remain.
Candidate selection is unavailable until exact complete tuning reports exist;
final freezing requires that stored selection. HTTP/service wiring remains a
later unit, so these internal checkpoints expose no new owner API.

## Closed request-v2 and actual baseline execution

V1 parsing, hashes and logical identity remain unchanged for existing M1 work.
New execution owned by a B experiment must use v2; removing lineage or changing
the version cannot bypass a stop fence. Historical event replay/read remains
available and never restarts an execution.

V2 retains the nine pins and adds exact context/definition/comparison/matrix,
challenger/arm and pair/cell identity. Its candidate_bundle_hash explicitly means
the verified A envelope hash; baseline materialization still uses the actual
canonical baseline bundle. The pure parser performs no host, case-store or
engine operations. Scoped immutable lineage checks verify the full frozen
schedule, exact expected cell and chosen grant; current SQL fences are refreshed
after slow reads. Host guards reobserve actual sources and then refresh SQL
without reopening a decryption window.

ExperimentAdmission accepts an internal host-selected slot, performs actual
source/arm/config preflight and native availability verification, then commits
the real trial, existing CallLedger reservation, attempt, cell link and event
atomically. The deadline starts after preflight. An owner service must choose
the next frozen slot, never expose arbitrary cell selection or skip unavailable
candidates; that scheduler/lifetime wiring remains Task6.

Only tuning-baseline mechanics are available in this unit. Candidate slots
reject before decryption, native probes, trial/call reservation or workspace
creation. Final qualification/regression execution remains unavailable until
both variants' actual semantic/effective-view prerequisites exist. A baseline
technical result cannot substitute for the paired comparison or final pilot.

The unchanged actual Runner, encrypted store, workspace and NativeUsageRecorder
carry v2 through engine marker, artifact and immutable result. V2 reports retain
the exact full request hash and experiment lineage. Synthetic packet tests prove
this integration and stop-during-checker cleanup; incomplete native receipts
retain fail/unknown and missing request coverage remains null. They are not
native-model or business-effectiveness evidence. Historical v2 results and
authorized private artifacts remain readable after stopping; source revocation
still controls private plaintext reads.

The Dashboard verifier caches only pure compilation of public application source,
keyed by freshly read exact bytes and the exact compile filename. Each scan still
performs stable source reads; every callable still passes module/global/name/
closure/path/live-code checks. The immutable-code cache keeps one digest per path,
at most32 paths, under a lock. No source-permission, grant or match verdict is
cached. Independent cached/uncached captures match; measured revalidation improved
5.352->0.699s and the old owner E2E288->40s on this development machine. These
timings are diagnostic evidence, not a latency guarantee.

Qualification ownership also applies at the lower CaseStore boundary. Bare nine
pins cannot reserve or freshly consume a B-owned holdout, even with a renamed
experiment, case set or family, or a qualification case relabeled tuning. The
guard follows brain-scoped source/family fingerprints across all incoming splits
and retains stopped history. It does not blanket-disable unrelated M1 work.
Historical reserve/consume event replay remains cold and readable; existing
global claims and exposures are never reset. Legacy owner admission rejects
aliases before source/native preflight. Full-v2 final qualification/regression
still has no positive execution path before actual C+D readiness; the lower v2
allocation/consumption integration is intentionally unfinished, not enabled by a
caller readiness flag. A CaseStore source change also changes EVALUATOR_PIN;
historical records do not become fresh execution authority automatically.

ComparisonResults creates immutable encrypted reports over the entire frozen
matrix, including explicit missing slots. It snapshots the actual linked trial,
attempt and result pointer, reads each selected result with an explicit immutable
result ID/hash, and rejects pointer changes before publication. Reports also
verify actual call markers, artifact bytes, output manifests, product criteria
and evaluator pins. Historical reports keep their old references after genuine
product reevaluation; a newer result cannot silently replace an old reference.

Native integrity, product verdicts, repeat stability and regression are separate.
Unknown executions never make a candidate win; a known critical failure is not
erased by another unknown repeat. The exact integer sign test counts cases rather
than repeats and applies the frozen multiple-test correction. Qualification
overlap with tuning/regression and observed regression losses prevent a passing
pilot gate. Missing or corrupt encrypted evidence stays incomplete. Numerical
success over synthetic fixtures remains technical, with business eligibility and
real-world independence unverified. Report creation is not activation.

Candidate selection requires the latest published complete report for every
declared arm, exact current result references and policy, and fresh source/edit
authority. The chosen arm must support tuning improvement; a complete losing or
tying counterpart is retained as evidence. Immutable report ID/hash pairs are
sealed in ordinal order. Selection cannot abandon another partial tuning branch
after observing a favorable output. Publication order uses append-only event IDs,
including explicit republication of identical report bytes; wall time is not an
ordering authority. KEEP_BASE can still stop without spending final qualification.
Selecting a candidate seals further editing/tuning but does not open final
execution, allocate a holdout, activate anything or certify business eligibility.
