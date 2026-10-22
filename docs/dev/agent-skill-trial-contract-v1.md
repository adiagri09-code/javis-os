# Improvement trial boundary contract v1

This document freezes the M0 boundary for M1 implementation. It is a contract, not an
available trial runner. M0 advertises `trial=false` and has no engine execution endpoint.
Implementation must validate and pin these records before starting an engine; adding
optional metadata cannot weaken a required field or change a previously pinned hash.

## Canonical records

Host records are JSON objects serialized as UTF-8 with sorted keys, no insignificant
whitespace, no NaN/Infinity and no implicit datetime normalization. SHA-256 covers the
complete record excluding its own hash field. Byte assets use their raw SHA-256. Hashes
are host computed; a caller's asserted digest is checked against the referenced record.
All references carry the authorized brain identity. Missing references fail closed.

| Record | Required pinned content |
|---|---|
| Acceptance contract | `contract_version=1`, mandatory and business criteria with stable IDs and criticality, primary metric, better direction, aggregation, evaluator ID/version/hash, unknown conditions, output hashing policy, owner-confirmation requirements |
| Engine configuration | Requested provider/model/reasoning, selected engine ID, capability profile, host grant hash, operational deadline; actual configuration is observed separately, never inferred from the request |
| Source snapshot | Source identity/version, raw content hash, timezone, capture time, data period/cutoff, schema, read grant/freshness, redaction status and sufficient-source decision |
| Case set | Case IDs, source/family group keys, deduplication identity, immutable split assignments (`tuning`, `qualification`, `regression`), split seed and snapshot references; answers and checker references are evaluator-private |
| Trial request | Experiment/variant/case/repeat/attempt IDs, base and effective bundle hashes, contract/case-set/config/grant hashes, expected source/target generation, deadline, host learning origin |
| Installation receipt | Trial/session IDs, effective bundle/prompt/tool inventory/fixture/grant hashes, asset revisions available, selected and observed-used events, actual engine configuration and coverage |
| Trial result | Terminal execution state, artifact manifest/hash, receipt reference, per-criterion `pass`, `fail` or `unknown` with evidence/reason, observed usage and existing ledger references |

The acceptance adapter reuses `team_acceptance` criteria where applicable without creating
a Team job. A structural pass never implies a business or owner-confirmation pass. Owner
decisions bind the exact case/output hash. Checkers are host registered, pinned, and outside
the solver's filesystem, environment and tool inventory.

M1's acceptance record requires a public objective, a description for every criterion and
one declared UTF-8 text artifact `{kind:"text",path,media_type}`. The solver receives a
hash-pinned public projection of these requirements, without evaluator implementation
identities/hashes or answers. Structural requirements remain visible. Full and public
contract hashes are distinct pins; the host verifies their relationship. Missing public
intent is invalid, rather than permission to infer the owner's business requirements.

## Isolation and lifecycle

Every `(experiment, variant, case, repeat, attempt)` has a fresh workspace and context.
The solver receives the authorized task input, read-only snapshot fixtures and effective
assets. It receives no answers, checker internals, other arm outputs, live state, inherited
login files or production write capabilities. A missing fixture returns `fixture_miss`;
it never dispatches to a live connector. Native tools require host enforcement. An adapter
with unverified enforcement is unsupported and cannot instantiate a trial engine.

Qualification transitions `unseen -> reserved -> consumed` durably. Resumption preserves
the candidate/case/config pin; a new candidate cannot reuse consumed holdout evidence.
Leaked answers/checkers make the experiment contaminated. Redaction that destroys task
meaning yields `insufficient_source`, not a successful replay.

Trial states are `reserved -> prepared -> running -> evaluating -> completed`, with
alternative terminal states `failed`, `unknown`, `interrupted`, `cancelled`, `not_run`.
An execution can complete while the product fails a criterion. Host `engine_started`
is persisted at the existing ledger boundary; missing or late usage is unknown, never
silently zero. Cancellation and crash recovery retain attempt identity and artifacts.

Before each transition, host checks the pinned generation, permissions, source, contract
and selected engine configuration. Stale or late results cannot apply a new baseline.
Trial outputs carry host `learning_origin=trial|compose|qualification`; they cannot become
production lessons, tasks, messages or owner approvals. No state in this contract grants
activation. Baseline is always a valid selection; incomplete comparisons are inconclusive.

## M1 validation obligations

M1 implements the records and recovery behavior above with behavioral tests for C01–C05,
E01–E06, U01 and S02–S04 from the design. A fake runner is labeled synthetic. Real smoke
requires the owner's selected, verified model configuration and reports actual coverage
and usage. Supporting an API adapter never authorizes switching a CLI-selected user to API.

## M1 internal durable request and evaluator boundary

The unreleased request has the closed fields `version=1`, `pins`, `case_set_id`, `case_id`,
`variant=baseline|candidate`, positive `repeat`, `engine_config`, `baseline_context_hash`,
`target_generations`, `deadline_at`, and optional `qualification_id` for qualification only.
`pins` reuses CaseStore's exact experiment/base/candidate/contract/case-set/config/grant/
policy/scope pin shape. `engine_config` is the full adapter pin, never an alternative
provider chosen by the runner. `baseline_context_hash` binds the complete host context
record (content, raw content hash and coverage), not just its text. API clients must not
assert that host context collection was complete.

Schema3 adds trial/attempt/observation tables to the existing resonance database. Metadata
reads still support schemas1 and2 without migrating. A write upgrades in one transaction
after a serialized backup. Trial reservation and its real CallLedger reservation share
that transaction. The logical experiment/variant/case/repeat identity cannot produce two
calls through different idempotency keys.

Leases are internal host capabilities; ordinary trial reads omit their tokens. Input
materialization commits holdout consumption or tuning/regression exposure plus the exact
materialization hash before returning solver-visible input. Preparation validates the real
workspace journal and public projection against host records. Engine start changes the
trial and existing call marker atomically, before query acknowledgement. Cancellation
before that marker refunds; after it, the call remains counted and uncertain recovery is
`unknown`. Neither recovery path creates another attempt implicitly.

`evaluate_trial(contract, artifact_root, case_private, checker_registry)` consumes the exact
CaseStore private projection. Its optional keyword-only `owner_decisions` accepts typed
host records from authorized durable history, never answer/request JSON claiming owner
authority. Evaluator and registered checker ID/version/hash pins must match. Checkers get
immutable artifact data and private answers; they receive no executable or solver path.
Command/candidate-code execution remains unsupported without a separately verified isolated
checker. Structural, business and owner verdicts remain distinct, with exact raw output
hashes. The runner must additionally enforce execution/installation invariants; a standalone
artifact evaluator cannot attest native isolation, permission or actual configuration.

This boundary does not advertise a complete TrialRunner or an owner execution endpoint.
