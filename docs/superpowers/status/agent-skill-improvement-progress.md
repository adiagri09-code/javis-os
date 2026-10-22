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

## Milestones

| Milestone | Engineering | Business evidence | Rollout |
|---|---|---|---|
| M0 | Implementation and fresh review fixes verified; PR #794 awaiting final-head CI/integration | Not applicable to foundation | Off/suggest only; no live activation |
| M1 | Pending | No real-engine smoke yet | Not enabled |
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

Push the review fixes and final documentation, wait for final-head CI on PR #794, merge only
when green and verify publication. Prepare M1 from the frozen trial boundary while waiting;
continue its implementation on the integrated baseline. Full M0–M8 Goal remains active.

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
