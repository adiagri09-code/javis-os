# Skill candidate records, M2A

This is the authoring-storage boundary of M2A. It does not enable changed-candidate
execution, semantic acceptance, comparison, apply or production activation. A
candidate is not an `improvement_revisions` row or an executable bundle.

Schema4 extends the existing resonance database with:

- `improvement_skill_candidates`: immutable original base revision/hash/generation,
  host context/experiment, ordinal1 or2, exact resulting content hash/byte size,
  encrypted patch/provenance references and originating owner event.
- `improvement_candidate_authorities`: immutable explicit body-region or exact
  before/after diff authority, tied to the same brain/context/target/base. A
  region declaration never certifies the meaning of its replacement.
- `improvement_candidate_authority_grants`: the current generation and one-way
  active-to-revoked transition. History cannot be deleted or reactivated.

Foreign keys and triggers bind proposals to an existing skill base and active
context grant. Two immutable ordinal slots exist per brain/experiment; no new
agent call, Goal or monetary ledger is introduced. A candidate's initial semantic
status is `unreviewed`; later semantic evidence must be separate immutable data.
Staging content must use the existing encrypted `RevisionBlobs`, outside canonical
files, global mirrors and current asset pointers.

`CandidateRecords.get/list/contexts` are cold metadata reads. They do not migrate
schema3, decrypt bodies or context bindings, initialize sources, read settings,
probe authentication or call an engine. Context objectives come only from the
existing immutable owner case-set/contract association. Contexts without that
association report an empty objective list. Metadata may remain visible after a
grant is revoked; current context and edit-grant statuses are separate fields.
Viewing metadata creates no private-content authority.

`revoke_authority` uses the existing serialized writer transaction and owner event
ledger. It validates expected generation and event-key payload, records revocation
and its event atomically, and replays historical results without restoring a grant.
Revocation is allowed even when the improvement policy is off. Private exact-text
reads and owner staging are later M2A units and must revalidate current source and
permission before returning content or committing changes.

## Upgrade and recovery

Cold reads of known schemas1/2/3 remain compatible. The first improvement writer
upgrades through only the absent schema blocks in one existing `BEGIN IMMEDIATE`
transaction. It never replays installed schema3 tables or immutable triggers.
Unknown/newer schema is rejected before backup or improvement writes.

For an installed older improvement schema, the serialized first writer saves
`resonance.sqlite3.pre-improvement-m2-candidates.bak` before any new DDL. The
existing SQLite backup mechanism includes WAL data and does not overwrite a prior
backup. A fresh improvement installation retains the original M0 backup behavior.
Failed DDL rolls back all new candidate tables and leaves the old schema usable.

Schema4 is intentionally unsupported by the previous M1 reader. Do not run an old
binary against the live shared database. Restore a backup only as an explicit
operator recovery with all writers stopped, after preserving the current database
and its WAL: it is a backup of the whole shared store, so restoration also discards
other writes made after that backup. There is no automatic downgrade or rollback
that deletes candidate history.

## Verification

`test_improvement_candidate_records.py` uses actual scratch SQLite, encrypted host
bindings, cases, contracts, a trial and the existing call ledger. It covers schema3
cold reads, preservation of all previous rows, serialized concurrent upgrade,
failed upgrade rollback, immutable scope/history, bounded ordinals, foreign-brain
isolation, generation/replay revocation and public-objective pagination. The
existing store/case/trial/admission transaction suites remain required regressions.
This evidence establishes storage behavior only; it is not a business pilot.
