# Harness² prompt adaptation

Copyright 2026 Google LLC. Licensed under Apache-2.0; see LICENSE in this folder.
Upstream: https://github.com/google-research/harness2
Pinned commit:1cfe254e8d25b15f37048c3730134686abe60335.
Source: `harness2/core/prompts.py`, Git blob
9ccacf23b64ac15b06a1939f26224960f56d757c.

Adapted into `server/improvement_generation_protocol.py:_proposal_method`:
`propose` decision sequence, `_INV_TEMPLATE`/`_DOM_TEMPLATE` execution/domain
lenses, `_KEEP_BASE`, `experience` edit→evidence→observed difference attribution,
and `EVIDENCE_BOUNDARY`/`ANSWER_FREE` limits. This is a narrow structured prompt
adaptation, not an import or copy of the upstream runtime, executor, benchmark,
library, dataset or third_party code. The pinned repository tree has no upstream
NOTICE file; the original LICENSE and this copyright attribution are retained.
License Git blob:d645695673349e3947e8e5ae42332d0ac3164cd7.

Modifications for Javis: only existing authorized evidence may be cited; private
answers/holdout/checkers/raw reasoning/secrets remain unavailable. Execution and
domain_process retain their current angles. Only bounded UTF-8 body patches are
permitted; no upstream guardrail/system-prompt/plugin editing or permissions.
KEEP_BASE maps to the existing not_a_target_defect JSON outcome. Attribution
guidance uses existing explanation fields and adds no model output fields or
schema. Overall result remains separate from semantic/owner-rule review. No
full-library loading, causal quality claim or token-savings claim is introduced.

All upstream policy beyond these explicitly adapted methods is excluded. Javis
keeps baseline in its own comparisons and its independent comparator/thresholds;
upstream finals-only selection_pool is not reused.
