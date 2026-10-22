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
reads are a later M2A unit and must revalidate current source and permission before
returning content. The owner staging service below observes that authority before
every new authoring write.

## Explicit owner staging

`SkillCandidates(assets, pack_state_dir=...)` uses the actual canonical source
observer and native file/ancestor permission projection. It checks enabled state,
ownership, current revision/generation and immutable source bytes, and rechecks
after encrypted publication before committing. Candidate bodies, patches and
provenance remain encrypted outside the canonical source; source files, mirrors
and current asset revision pointers do not change.

- `declare_region` records one explicit UTF-8 byte interval, tied to the current
  base and source-authority hash. The interval excludes protected metadata and
  the implicit routing description when the skill lacks an explicit description.
- `stage` creates at most two candidate slots per experiment and one primary
  component/base. Without an active matching region it creates only a diff
  proposal. The host adds its own same-context owner-request event atomically;
  caller evidence refs must resolve to that event type or a completed, associated
  tuning trial. Qualification/regression and arbitrary paths are not evidence.
- `authorize_diff` binds a fresh explicit owner decision to complete before/after
  hashes. Its `expected_generation` is the baseline target generation, distinct
  from an edit grant's revocation generation. It verifies encrypted provenance,
  patch and exact bytes, and requires the original source-authority hash. A valid
  edit decision leaves semantic status `unreviewed` and dependency status
  `unresolved`.

Historical idempotent replay returns its original decision without source/blob
reads, even after revocation or policy-off. Always refresh current cold metadata
after replay: that historical response does not reactivate an edit/context grant.
New writes fail when their context grant, policy version, source identity or
permission no longer matches.

The pure `body_layout/validate_body_patch` validator preserves exact UTF-8 bytes,
CRLF and all untouched prefix/suffix bytes. It freezes YAML metadata and the first
body line used by discovery as an implicit description. BOM plain text is retained;
BOM followed by YAML is rejected because current discovery does not recognize
that header consistently. Ambiguous YAML, split code points and over-limit bodies
are rejected. Lexical helper/script references cannot change, including Windows
path separators; that inventory is explicitly incomplete and does not certify
dependency semantics or obedience to owner rules. M2A never turns these structural
checks into executable admission or activation authority.

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
