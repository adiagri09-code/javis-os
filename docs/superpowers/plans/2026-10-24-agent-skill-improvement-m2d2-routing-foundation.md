# M2D2 routing-state foundation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make discovery and actual skill reads agree when an authoritative skill
is disabled, before adding production effective-view/task/session integration.

**Architecture:** Keep the existing canonical → Claude mirror → legacy precedence.
A disabled skill at an earlier or equal source suppresses enabled copies there
and at lower-priority sources. Reuse skill_router for ordinary hub reads and
existing lazy discovery; do not introduce an activation pointer or an overlay.

**Tech Stack:** Existing Python, pathlib, CapabilityRegistry, LazySkillSource,
actual mcp_hub built-in handler and skill_usage sidecar. No model calls.

## Authority and scope

Full Goal M0–M8 and Goal section12 remain authoritative. This independently
testable repair is one prerequisite of full D2, not completion of production
effective views. D1 stable head999c207a has approved whole/scoped reviews and
exact native qualification81/958527ac; full CI39990661065 is running. Its account
pair, eligible final and owner/business/live gates remain open. Keep that evidence
source-bound and preserve the actual failed selected-account attempt.

Reuse the attached M2 worktree and reserved0.299 draftPR803. Main remains
d3d7cb36/0.298.0; no new release reservation is needed for this continuation.
Do not change the original D:/Project checkout, native adapter, schema, grants,
candidate status, owner semantics or any live setting. This unit changes no
PROFILE_SOURCES file; verify that fact rather than re-running qualified native20.

## Actual gap and callers

- `server/skill_router.py:resolve_skill_file` searches only enabled paths. A
  canonical `.disabled/<slug>/SKILL.md` does not stop a stale mirror from loading.
- `list_skill_manifests` already gives disabled entries precedence, while
  `list_skills` visits enabled entries first within each source. A same-source
  enabled/disabled collision can therefore disagree across discovery APIs.
- `mcp_hub._builtin_tools` resolves and reads the file inside the real
  `javis_use_skill` handler, then bumps usage only on successful loading.
- LazySkillSource refreshes manifests by stat signature and the real capability
  registry. Disabling an active canonical skill must invalidate its warmed
  selection even when an enabled stale mirror remains.

## Files and responsibilities

Modify `server/skill_router.py` only for source-state precedence. Add
`tests/python/test_skill_resolution_state.py` with isolated brain/state roots,
real file states, actual registry/cache and actual hub handler. Existing
`test_skill_usage.py`, `test_skill_caps.py`, `test_skill_da_ngon_ngu.py`,
`test_adaptive_context_phase8.py` and `test_skill_subtree_ship.py` are affected
regressions. Update the operator/progress/changelog records after evidence exists.

## Task 1 — authoritative disabled state through discovery and loading

- [ ] Record the exact source/consumer/test impact and initial native81 hashes.
- [ ] Add behavioral tests: disabled canonical suppresses each enabled fallback;
  same-source enabled/disabled collision stays off; disabled Claude source
  suppresses `.agents`; legacy-only enabled fallback still works; canonical
  enabled wins normally; a warmed hub handler refuses after disable without
  incrementing usage; a warmed LazySkillSource drops the disabled skill.
- [ ] Run `python tests/python/test_skill_resolution_state.py -v` and retain RED
  showing actual body resolution/discovery disagreement, not fixture errors.
- [ ] Make resolver check an authoritative disabled file before the enabled
  file at each source. Keep slug validation and source precedence. Resolve
  unreadable state conservatively; never continue into a stale lower source.
- [ ] Make list_skills suppress enabled copies with an authoritative disabled
  entry at the same source, without reordering unrelated ordinary entries.
  Use the same declared source ordering for legacy disabled state as manifests.
  Do not read bodies during manifest-only discovery or change frontmatter.
- [ ] Run new GREEN and the five affected scripts sequentially. For the pytest
  Phase8 module, use the repository runner or the exact supported pytest command.
  Record every actual exit/log and full source map. No fake runtime/usage call.
- [ ] Review the narrow source delta and real handler/cache evidence; scope any
  independent review to this new routing change. Do not repeat whole D1 review.
- [ ] Commit/push the complete unit and run final-head CI when the delivery
  source is stable. Existing999 CI is historical for later source changes.
  No D2 completion or live activation claim from this repair.

## Full D2 still required after this unit

Production support still needs immutable ordinary task assets, same-store
durable host task/session pins, qualified activation selectors (E dependency),
per-view capability/cache projection, common router/lazy/hub/helper resolution,
task-specific native materialization, exact telemetry and incompatible-resume
handling. Scope conflict must keep the baseline and notify; missing/foreign host
identity never selects an overlay. Do not use D1 comparison context as ordinary
production authority or manufacture an M0 revision from an A candidate body.

Read-only inventory is retained in the task's `d2_integration_map.md`. The existing
CapabilityRegistry has a single mutable skill source per brain, so task overlays
cannot overwrite it. Dashboard run_turn binds actual host session/message/agent
identity; context_runtime owns existing task/step IDs. Native sessions retain a
Claude session_id across turns and cannot silently reload a changed view.

SDK0.2.116 locally exposes setting_sources, skills, plugins, cwd and resume.
Official [SDK skills](https://code.claude.com/docs/en/agent-sdk/skills) documents
filesystem discovery governed by setting sources; [SDK plugins](https://code.claude.com/docs/en/agent-sdk/plugins)
documents local plugin directories. A per-task plugin with filtered discovery is
only a design candidate. It needs actual qualification of duplicate/global skill
exclusion, protected settings/permission parity, helpers and resumed sessions.
Do not disable user policy or copy credentials to make it work. Keep unsupported
adapters/selectors unavailable until demonstrated. Resolve these interfaces in
the next full D2 implementation plan before writing dependent source code.

## Self-review

This unit is ready to execute: concrete mismatch, actual callers and bounded
behavioral tests are known; no activation or native architecture decision is
needed to repair it. Full D2 design remains open and cannot be called complete
with baseline-only routing. E/F and M3–M8 remain mandatory under the full Goal.
