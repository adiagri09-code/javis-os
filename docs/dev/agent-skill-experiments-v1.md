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
