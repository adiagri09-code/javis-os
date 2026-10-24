# Incremental Harness² reuse decisions

Goal sections12–14 apply. Upstream repository google-research/harness2 is pinned
to1cfe254e8d25b15f37048c3730134686abe60335. Assess only the next unwritten unit
and its immediate dependencies; append an actionable decision before writing it.
No code has been copied/imported by the first decision below. A future vendor
must retain Apache-2.0/copyright/NOTICE as applicable plus exact provenance and
changes; separately assess dependencies and never implicitly copy datasets.
Goal§15 additionally authorizes a narrow useful delta to existing proposer
prompt/evidence rendering, after the current D2 task unit is preserved. Inspect
the exact prompt functions before coding, preserve execution/domain_process,
JSON/patch/limits/owner and authorized-data boundaries. Link edit→permitted
evidence→observed difference→helped/hurt/no effect/confounded; allow KEEP_BASE.
No rewrite of infrastructure, schema/history or whole-library prompt loading.
This is the next targeted reuse assessment, not an integration claim.

| Needed Javis behavior | Inspected upstream file/function and Git blob SHA | Decision | Reason and contract checks |
|---|---|---|---|
| Ordinary Dashboard API task skill snapshot lifecycle; lazy/hub metadata and exact body ownership | `harness2/substrate/base.py` `Install`, `RunRequest`, `Substrate.materialise/execute`,19ef1dac7c07e1788e1a99fbdd1e7b833da44a41; `harness2/core/context.py` `build`, `_copy_tree`, `ContextTree`,72f2868b06c13e30c031cb91c0f04dcd80293ec9 | Write narrow Javis host lifecycle using existing TaskSkillScope/M0/runtime/turn ownership | Upstream protocol models benchmark staging/launcher, not live Javis turn token, runtime rows or cancellation. Its evidence builder deletes/recreates destination and copies mutable files; it cannot authorize or pin a live task. Import would pull benchmark spec/tree without supplying the missing ownership. Reuse completed Javis core, never duplicate executor/usage ledger. Test default/native/off zero capture, current actual owner binding, same-task lazy/hub bytes, frozen fallback metadata, failure/Stop closure and copied-context revocation. |

Upcoming components must inspect their relevant exact upstream functions before
implementation: Propose/Compose/Reflection/evidence prompts (`core/prompts.py`),
Propose–Probe–Compose orchestration (`core/recursion.py`), pure selection helpers
(`core/selection.py`), recipes/index (`core/library.py`) and bundle tree/helpers.
This is a queue, not a claim that those modules have been integrated or reviewed.
For selection specifically preserve Javis baseline and inconclusive→baseline;
the source spec already records upstream finals-only selection_pool divergence.

The library preview (blob39e50684b4044e483a3c16a447958044d4b5e6de) confirms direct
context/tree dependencies and mutable directory/index storage. Full integration
decision is deferred until the recipe/library unit; no blanket rejection of reuse.
