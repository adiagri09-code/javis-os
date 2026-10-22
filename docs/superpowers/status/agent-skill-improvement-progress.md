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
| M0 | In progress: baseline, gap audit, immutable asset/policy plan | Not applicable to foundation | Off/suggest only; no live activation |
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

Write/review M0 plan, add failing foundation tests, implement immutable storage and guarded source capture, then add lazy owner routes and verify auth/CSRF/schema recovery. Finish PR #794 with a fresh implementation review and green CI before merging. Continue M1 afterwards; full Goal remains active.
