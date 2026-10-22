# Agent and skill improvement Goal progress

## Identity and authority

- Goal: execute the complete M0–M8 contract in `../AGENT-SKILL-IMPROVEMENT-GOAL.md`.
- Goal source SHA-256: `67061573b8c584d65d0ecf1daa4c56b536c78c07fcc5158cfa090d40ea299afd`.
- Agent/skill spec SHA-256: `fceea3d375388eeb0f0e3eada48cc2c74a611b2bfcad9978441a683052b108bc`.
- Team dependency spec SHA-256: `e01014f05bf3e090cc63a52e581049833b292dfe5e77a094bd75d8941504f2ff`.
- Authoritative baseline: `a9ee52ff0d3a1ce0eaa61d18c1b9c83081e21b26`, main 0.286.0.
- Worktree: `C:/Users/admin/.codex/worktrees/agent-skill-improvement-m0/Javis-OS`.
- Branch: `codex/agent-skill-improvement-m0`; release reservation: 0.287.0, commit `74ad991e`.
- Draft PR: https://github.com/blogminhquy/javis-os/pull/794 (attached to this chat).
- Original checkout remains untouched by implementation; only the three relevant source documents were copied.
- Current engineering branch: `codex/agent-skill-improvement-m1`; 0.288.0 reservation
  `884bfbca`, dependent draft https://github.com/blogminhquy/javis-os/pull/795 (attached).
  M0 merged as `0990331574e617fa1a79cd69fcd7b87d465448c5` after final-head CI passed;
  publication run39797072172 succeeded. M1 is now rebased onto published M0; current feature
  checkpointac27a182 before this progress update. PR795 remains draft pending the full M1 scope.

## Milestones

| Milestone | Engineering | Business evidence | Rollout |
|---|---|---|---|
| M0 | Complete: PR #794 merged09903315, CI39793439501 and publication39797072172 passed;0.287.0 | Not applicable to foundation | Metadata only; no live activation or production restart |
| M1 | Tasks1–2 complete as engineering components; shared ledger/usage, durable runner/evaluation/API pending | No real-engine smoke yet | Not enabled; base M0 integrated and published |
| M2 | Pending | No skill feasibility yet | Not enabled |
| M3 | Pending | No qualification or live canary | Not enabled |
| M4 | Pending | No adapter/routing pilot | Not enabled |
| M5 | Pending | No agent pilot | Not enabled |
| M6 | Pending | No bundle/helper pilot | Not enabled |
| M7 | Pending | No Team improvement pilot | Not enabled |
| M8 | Pending | No adaptive-library evidence | Not enabled |

## Existing -> missing -> evidence -> milestone

| Existing | Missing | Evidence on baseline | Owner |
|---|---|---|---|
| Same resonance SQLite, WAL and BEGIN IMMEDIATE transactions | Immutable target/revision/bundle metadata | `resonance_store.py`, `_conn`, `_Tx`; read-only audit | M0 |
| Owner-only stable agent registry and owner-rule guard | Dedicated improvement identity, exact raw-byte protection, policy version | `agent_rules.py`, `resonance_store.agent_register` | M0 |
| Skill inventory with disabled-canonical shadowing | Safe capture of canonical assets and durable revision bytes | `skill_router.list_skill_manifests`; resolver alone is insufficient | M0 |
| Evidence encryption primitives | Revision-owned blob lifetime outside evidence TTL/cleanup | `evidence_store._serialize/put/cleanup` redacts and expires content | M0 |
| METHODS compare/holdout and ledger | Arbitrary immutable bundles and isolated solver adapter | `resonance.py`, `agent_ledger.py` | M1–M3 |
| Team default acceptance/quality-first/usage released in 0.285.0 | Verify and reuse these dependencies; do not implement them again | Baseline changelog and `test_team_quality_*` files | M1/M7 |
| Main's permissive brain fallback | Strict existing-brain identity for improvement routes | `_brain_root/_brain_key`, `brain_ident.canonical` | M0 |

## Baseline verification

- `D:/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py learn_sua_skill -v`: PASS, 1 file.
- `... tests/run.py agent_rules -v`: PASS, 1 file.
- `... tests/run.py resonance_a3_learning -v`: PASS, 1 file in 132 seconds (session 92106 completed).
- Python env reused by explicit executable, not by copying `.venv` or production config. Main imports in new tests must set scratch state/brain roots first.
- No new model calls, business dataset reads or live activation so far.

## Decisions and review findings

- Ruling: use dedicated encrypted raw-byte revision blobs rather than normal EvidenceStore artifacts. EvidenceStore redacts content and applies a 14-day TTL, so it cannot prove an immutable original-byte revision. Cost if wrong: explicit blob migration/interface adaptation at M1.
- Ruling: M0 exposes authenticated capture/history/policy only, with no executable trial/apply controls. This delivers inspectable foundation while preserving later sandbox gates.
- Ruling: read-only missing policy/status must not create a DB, asset copy or model call. Store writes initialize schema atomically; registered reads use a lazy read path.
- Ruling: the user's Goal authorizes local planning/execution and PR integration without repeated approval; production rollout and business owner confirmation remain separate.
- Two independent read-only subagent audits completed, covering storage/identity and API/test infrastructure. These audits are not code reviews of implementation.

## Next action

Implement M1 shared ledger/usage, then durable lifecycle/evaluation and owner service.
PR795 stays draft on published main09903315; full M0–M8 Goal remains active.
Full M0–M8 Goal remains active; no business or live rollout gate is closed by a code merge.

## M0 implementation evidence

- Implemented immutable revisions/bundles and append-only events in the existing shared SQLite
  store, encrypted exact-byte blobs, owner-only policy/CAS/idempotency, canonical ownership
  capture and six authenticated metadata endpoints. No engine, canonical write or activation.
- Final focused command: `D:/Project/Javis-OS/.venv/Scripts/python.exe tests/run.py improvement
  route_table prompt_budget team_quality_contracts team_quality_usage agent_rules learn_sua_skill -v`:
  **PASS 9/9 files, 51 seconds**. The three improvement scripts contain **39 behavioral tests**
  (20 store, 10 assets, 9 API), including actual-main authentication/CSRF and read-only access.
- Localization: three i18n scripts passed. Route snapshot intentionally adds six routes.
- Earlier broad security selection: 8/9 files passed. The unrelated unchanged webhook test
  requires POSIX mode 0600; Windows reports 0666 after chmod(0600). Ran the exact test from
  an archived clean baseline `a9ee52ff` and reproduced the identical assertion failure.
  Proof is in the local ignored ledger's `baseline-webhook-windows.txt`. No assertion or
  production permissions were weakened. Linux full CI remains mandatory.
- Fresh independent whole-branch review of `a9ee52ff..6f0541de`: no Critical findings;
  three P2 findings, all reproduced RED then fixed in one pass: cold GET migrated legacy
  DB; revision C after A/B/restore-A had wrong parent; corrupt empty ciphertext was accepted.
  Fixes use an actual read-only SQLite reader, current revision pointer for parentage, and
  a nonempty encrypted envelope. New tests verify all three plus existing-schema reads.
- Frozen M0 trial boundary: `docs/dev/agent-skill-trial-contract-v1.md`. This is a contract
  for M1, not a runtime or supported adapter. M1–M8 remain pending.
- M0 acceptance: same-byte capture deduplicates; protected bytes preserved and never edited;
  off blocks new captures; migration interruption rolls back; future schema rejected;
  encrypted loss/corruption unavailable; two-connection CAS has exactly one winner;
  deleted/replaced targets never inherit identity. Tests use scratch roots, no model calls.
- CI run `39784692950` on the pre-fix head: Docker size succeeded; full Python suite still
  running when final fixes were prepared. Its result cannot certify the final head.
- That pre-fix run subsequently passed fully. Final-head run `39785987176` passed all
  improvement tests but failed the unchanged Team runner's reply-concurrency timing probe:
  peak was 1 instead of 2, while both replies completed. No Team runtime file had changed.
  Reproduced deterministically by delaying the second fake engine start by 0.2s; the old
  fixed 0.1s sleep falsely rejected the parallel runner. Replaced this timing assumption
  with a bounded rendezvous, retaining the peak=2 and both-done assertions and the delayed
  startup. Focused regression then passed 4/4 files in 36s. A separate negative control
  forced sequential replies and verified the same peak=2 assertion still rejects them.
  New final-head CI is required before integration; no red run was merged.
- Fresh-process restart probe passed: two independent processes preserved the encrypted
  bytes, revision identity and one idempotent event. No model call or live action occurred.
- M1's migration work exposed a first-writer backup race shared with M0: both writers
  could enter the backup helper and contend on its temporary file. Reproduced on the M0
  branch with two first migrations (two backup calls instead of one). Backported the small
  fix so backup happens after the transactional schema recheck under BEGIN IMMEDIATE.
  M0 regression passed **3/3 files, 40 tests, 19 seconds** (21 store + 10 assets + 9 API).
  This fix is isolated in the temporary `agent-skill-improvement-m0-race` managed worktree;
  the original implementation worktree is now used by the engineering-only M1 branch.
- Final head e6637d33 passed CI39793439501, including Python suite and Docker size. Fresh
  main0.286.0/version/PR checks passed; PR794 squash-merged as09903315 with expected-head CAS.
  Build/publication39797072172 subsequently passed, publishing0.287.0. No production restart,
  deploy, live canary or activation was performed. M0 engineering is complete; M1–M8 remain.

## M1 engineering evidence

- 0.288.0 was reserved in dependent draft #795 before code. One dependent draft only;
  final review/merge waits for integrated/published M0. The source checkout stays untouched.
- Task 1: immutable acceptance contracts with mandatory/business distinction; exact raw and
  redacted fixture hashes; encrypted raw inputs and private answers; pinned source periods,
  timezone/version; case family/content split guards; transactional qualification claim,
  consumption, clone/exposure prevention and same-candidate resumption. No engine executed.
- Schema2 reads schema1 M0 metadata without migration; explicit writes upgrade atomically,
  preserving M0 policy/history and backup. A failed upgrade rolls back all M1 tables.
  The two-writer backup race was reproduced and fixed under BEGIN IMMEDIATE; the same fix
  was backported to M0 in e6637d33 through its own managed worktree.
- New case tests cover 25 behaviors, including malformed nested JSON, caller mutation after
  hashing, business criteria versus structural keywords, raw loss with surviving fixture,
  concurrent migration/qualification, old-schema rollback and answer/checker privacy.
  Latest cases/store scripts PASS 2/2 (15s) after input freezing; earlier full improvement
  run PASS 4/4 (29s). Additional final Task 1 regression is recorded in the local ledger.
- Native research used SDK0.2.116/CLI2.1.304 and localhost dummy auth/provider only. Bash,
  Read, WebFetch, ToolSearch and unregistered MCP were rejected; exact fixture hit/miss
  worked, with no ambient hooks/MCP/memory or outside canary effects. Disabling tool search
  yielded exactly one declared fixture tool. This is synthetic enforcement research, not
  OAuth execution, business evidence, billing coverage or an OS sandbox.
- Actual host selection was read through non-secret fields only: anthropic-cli,
  claude-opus-5-5, medium. CLI auth status reports logged in; no account tokens were copied
  or output. Production adapter capability remains false until released-path verification.
- Task 2 workspace substep committed as e0acfe16: eleven scratch tests verify exact fixture
  capabilities, separate attempts, pinned hashes, credential-text rejection, concurrent prepare,
  actual Windows junction boundaries and cleanup preserving another attempt. No live dispatch.
- Dedicated Claude profile now has a narrow existing-engine seam: no inherited settings,
  built-in tools, hooks, skills, plugins, subagents, sessions, model fallback or cost cap.
  Host acknowledgement precedes native query; raw observations preserve null usage, observed
  models and exact final-result bytes. Seven profile tests and existing SDK/completion scripts
  passed; production worker and runtime verification are still in progress, capability=false.
- Formal opt-in native test uses this profile through the existing engine factory, dummy auth
  and a localhost fake provider. PASS1/1 in5s with SDK0.2.116/native2.1.304: exact fixture tool
  inventory, requested model/effort, real tool hit/miss, unknown tools denied, outside canary
  unchanged, ambient hook/MCP/memory absent. This is synthetic, not real-model business evidence.
  Initial RED found ambient CLI discovery despite an explicit binary pin; trial availability
  now checks only that pin. A later timeout was a test-server query-string parsing defect;
  fixed without changing product behavior. Timeout cleanup terminates the owned process tree.
- Owner delegated pilot selection on22October. Selected first additional pilot: Python bug
  fixes in Javis-OS, using isolated repository snapshots and independent behavioral/regression
  tests as the business criterion. Preserve source-family splits, frozen qualification and
  all attempts. This choice does not close the spec's data-reconciliation Pilot A or document
  Pilot B gates; no historical case or user skill has yet been selected or run.
- Fresh worker and parent IPC now validate pinned workspace/config/capability, bind every
  packet to trial/attempt/input hash and require a host start acknowledgement before query.
  The parent callback must be bound; Task3/4 will supply the shared durable ledger callback.
  Fresh allowlisted env reaches the child, never inherited server tokens or turn authority.
- Windows worker ownership uses a kill-on-close Job Object attached before the initial input;
  POSIX uses an owned process group and existing winproc cleanup. A real descendant was
  terminated after its worker deliberately crashed. These are process-lifetime boundaries,
  not a sandbox for candidate Python code or permission to run host-side checker scripts.
- Latest explicit-native improvement plus console checks: PASS9/9 files in55s; py_compile
  passed for sandbox/profile/worker. A pre-existing console test assumed POSIX even when run
  on Windows; reproduced the same two failures on M0. Updated its expected platform flag,
  retaining the source canary; a negative control forcing the Windows flag to0 failed both
  assertions. New runtime/ACL subprocess calls use the existing hidden-console helper.
- Historical coding catalog:18 provisional families plus2 reserves, no parent-fail/fix-pass
  validation yet;44-family pilot not established. Details and independent-checker isolation
  gate are in `docs/dev/agent-skill-python-pilot-catalog.md`. No system skill is a writable target.
- Rebased M1 onto published09903315. Resolved the shared migration by preserving schema2
  and its backup under the transactional schema recheck; retained M0's new first-writer test
  and progress evidence. Post-rebase cases/store PASS2/2 in20s; diff whitespace check passed.
- PR795 now targets main ataf45da49 and remains draft. The temporary M0 backport worktree
  was archived through the app with a recoverable snapshot and PR794 reference; do not
  reuse its old filesystem path. Active M1 worktree remains unchanged.
- Contract review found missing public objective/criterion descriptions and an undeclared
  final artifact destination. Added strict required intent/output fields, a safe public
  projection without checker implementation refs, and portable output-path validation.
  Behavioral RED -> GREEN, case suite now28 checks, PASS1/1 in8s. M1 has not been released
  or enabled, so this tightens the draft contract before external records exist. Worker
  materialization of this public projection and complete installation receipts remain next.
- Task2 subsequently completed its public materialization and receipt components. Workspace
  requires a hash-pinned public contract and rejects private checker fields, missing intent
  and hash drift. Worker assembles all baseline instructions, assets and public requirements;
  no source truncation. Receipt binds journal/input/effective/prompt/contract/grant/fixture
  hashes, selected revision IDs and actual native inventory/model observations. Asset
  observed_use and actual reasoning remain unknown when unobserved, regardless of model claims.
- The fixture inventory view is a defensive copy, its grant is immutable, and binding rejects
  another broker/grant. Unexpected native tools or successful outside tool results are
  isolation failures. Native unavailable tools get explicit denial events; provider quota
  envelopes retain error/status metadata and nullable usage. No fallback was added.
- Fresh Python uses `-I -X utf8`, restoring only the trusted server source directory. A real
  child ignored malicious workspace sitecustomize/winproc modules even with hostile PYTHONPATH.
  Final explicit-native improvement/console run passed9/9 files in33s; SDK/completion
  regression passed2/2 in17s with an empty auth HOME, not a real credential/model call.
  Task2 is complete as a component; the parent start callback still needs Task3/4's durable
  shared ledger binding. No owner run endpoint or production capability is enabled yet.
