# Exact native read outcomes and qualified client dispatch

Full M0–M8 Goal/section12 applies. Base ea74d62e/PR803/reserved0.299.0.
This follows the terminal native skill qualification20/93.952s, exact profile
04c8c77b and independent review. It does not authorize a new account retry.

## Evidence and smallest remaining gap

Actual CLI309/SDK116 paired controls returned exact host skill bytes and denied
the foreign asset. Success ToolResultBlock.is_error was None; denial was True.
The strict manifest3/receipt3 reader therefore retained UNKNOWN. Keep that
historical behavior and all18 gates; do not globally replace missing flags with
False or reinterpret old receipt summaries under a newer proof policy.

The primary [tool-result protocol](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
describes an optional error flag and associates results through tool_use_id.
The installed SDK116 parser uses block.get('is_error'), so omission and JSON
null both become None. A typed SDK object alone cannot distinguish them.
Accordingly a new outcome can only be derived from exact successful host
response delivery, not from assuming either wire representation was observed.
Raw optional flags stay unchanged and separately visible.

The existing native-observations plan defines actual_reasoning proof as
qualified_client_configuration: observed native image/dispatch model, effort,
fast mode and prompt bound to the session and exact qualification. Provider
acceptance, private reasoning and instruction comprehension remain UNKNOWN.
This unit retains that existing distinction; it does not inspect private thoughts.

## Version and impact boundary

Use new input manifest4/receipt4 when the complete new dispatch/outcome boundary
is ready. Request protocol remains v4; input/receipt versions are separate
namespaces. Preserve manifest1/2/3 prompts, tool responses, receipt field sets,
hashes and historical UNKNOWN behavior. An old reader rejects unsupported input4.
The new manifest retains the strict single immutable skill, context, contract,
fixtures and exact effective_view descriptor. No source/grant/owner policy change.

New standalone components may first consume an existing validated immutable
manifest for synthetic component checks. They are not reachable from execution
or added to PROFILE_SOURCES until actual integration. Do not repeatedly
requalify native20 after each standalone edit. At integration, every reachable
new module joins the exact footprint, then one frozen boundary is qualified.

Affected consumers at integration:

- improvement_sandbox/materialization: new input version and prompt identity;
  reuse source checks before/after decryption and old version renderers.
- TrialProfile/options/handlers/observe/installation receipt: version4-only
  read envelopes and sanitized actual dispatch observations. Unbound roles and
  legacy trials keep their existing fixture-only behavior.
- FixtureBroker: retain existing source events, grant/fixture validation and
  history summaries. New envelopes wrap its actual return; do not invent a
  second source ledger or bypass misses. Skill bytes remain preloaded only.
- Trial evidence/protocol/checks/results: encrypted raw events plus a closed
  receipt4, independent outcome/dispatch validators, same18 check IDs. Shared
  operation-check helper signatures/default inventory remain compatible.
- Native transport/worker/lifetime guardian: actual ready-state spawn ACK,
  retained exact process/job/image ownership and full debug/job drain. Preserve
  the existing inference accounting ACK and cancellation/exposure semantics.

## Read-outcome foundation, then native integration

1. Design one closed host read envelope for the two authorized readonly tools.
   Bind trial/attempt/input/effective view, tool kind, exact arguments, pinned
   payload/content hash and a unique unpredictable response identity. Retain
   canonical emitted text/hash as immutable host observations. Failed requests
   remain content-free and never read canonical paths or live sources.
2. Use the existing FixtureBroker for actual fixture decisions/events and the
   selected immutable skill for skill reads. Keep host response observations
   detached from caller mutation, including equal parallel requests. A broker
   return alone is not native delivery or business proof.
3. Pure correlation joins every response identity/text to a unique native result
   and its actual call ID/name/input in the one initialized client stream.
   Reject duplicate/orphan/replay/wrong-tool/foreign-session/changed bytes.
   Do not join by timing, FIFO, equal arguments or a receipt-only assertion.
4. For input4 only, exact successful host response plus matching native delivery
   may establish outcome basis exact_host_success_and_native_delivery when the
   raw optional flag is False or None. Explicit native error, contradictory host
   status, malformed/truncated content or absent correlation cannot pass. Keep
   native_error_value raw; never write a fabricated raw false flag.
5. Independently verify denied reads too. A matched explicit native error plus
   actual host denial is safe boundary evidence, not a successful asset read.
   Missing or ambiguous denied outcome stays UNKNOWN. Source coverage, business
   quality and owner acceptance still have their own existing checks.
6. Receipt4 contains only closed summaries recomputed from raw records.
   event_coverage/side_effects may recognize the version4 derived basis only
   after independent validation. Generic missing telemetry, legacy fixture
   traces and unknown tools retain their existing UNKNOWN/fail behavior.

Meaningful RED/GREEN cases: success with False; exact host/native delivery with
None; None without host response; explicit error contradicting successful host
return; genuine denial; altered/foreign/missing/truncated/replayed envelopes;
parallel equal requests delivered in reverse order; mixed valid+orphan/wrong-tool
replay; caller mutation; old manifest/receipt UNKNOWN byte compatibility.
Native local-provider controls must retain actual omitted-success/explicit-error
evidence and exercise both asset and fixture tools. No model/account retry to
manufacture a successful proof or candidate win.

Standalone foundation API is PinnedReadOutcomeBroker(manifest, *, trial_id,
attempt, input_hash, fixture_broker=None). It reuses exact existing immutable
SkillAssetBroker and concrete FixtureBroker decisions, with a whole-read lock.
Its read(tool_name,args) returns a defensive envelope with exactly version1,
observation_id, trial_id, attempt, input_hash, effective_view, tool_name,
request_hash, outcome(hit/miss), result. Hit result is the unchanged underlying
broker result; miss result is only generic read_miss status/reason. Unknown
tool names or non-JSON inputs fail closed. No additional runtime source is read.

Observations have exactly version1, observation_id, trial_id, attempt,
input_hash, effective_view, tool_name, request, response_text, response_hash.
Both response and observations are retained as immutable canonical JSON and
returned defensively. Actual fixture events remain in the existing FixtureBroker
and are exposed defensively, rather than synthesized by the wrapper.

The standalone correlate_read_outcomes(manifest,workspace,events) validator
accepts only new trial_read_broker_observation records, never old asset records.
It returns verdict/reason/proofs. Successful proof basis is
exact_host_success_and_native_delivery; verified denial basis is
exact_host_denial_and_native_error. Summaries retain raw native_error_value,
tool/call/session/attempt/view/input identity, request/response hashes and outcome.
Both raw error fields must be present and agree; None is an observed SDK value,
not a substitute for an absent trace field. A successful hit requires exact
pinned underlying payload; fixture sequence is a positive unique integer.
No partial proof list escapes if another recorded read is uncorrelated.
This API remains unreachable until version4 integration; accepting a validated
old manifest in a standalone fixture is not permission to reinterpret old trials.

## Native dispatch/image foundation

The raw debug probe V1 failed before initial resume. V2 instead assigned the
actual job, used bootstrap Resume1, and held the documented pre-user-mode CREATE
event during actual image hFile identity/hash checks. Accepted code rearmed
Suspend0, continued CREATE, then final Resume1. Denied identical-byte foreign
image had no accepted continuation or post-attestation resume. This is a distinct
lifecycle, not a repaired report for V1.

First prove the SDK-imported anyio.open_process creator thread can own a
persistent debug pump through CREATE/EXIT without preventing pipe setup,
cancellation or process wait. A bounded inert compatibility probe now passes
three cases: selected image, identical-byte foreign image, cancel before local
ACK. Driver2.516s, actual same-thread CREATE/EXIT and anyio wait/aclose/job drain;
independent limited static review verifies29 artifact/runtime/source pins.
No guardian IPC/death/full SDK transport proof exists. The next small experiment
is an inert two-process receipt/ACK/drain boundary with exact worker incarnation;
no production integration precedes that evidence. Keep actual copied executable,
own job/marker, empty HOME and hidden process; no Claude/account/provider call.

Guardian must not receive model input, auth or the actual configured SDK argv/env.
Two recorded designs remain: a qualified worker-owned capture with duplicated
actual handles checked by the guardian, or a guardian-owned fixed Python worker
DEBUG_PROCESS descendant chain with opaque direct host-worker data pipes.
DuplicateHandle alone does not prove the supplied image handle originated in
the claimed CREATE event; explicitly retain the trusted capture-code assumption
or use direct guardian kernel events. Select after compatibility evidence.

At integration require actual retained worker/native incarnations, exact job,
actual debug image file ID/hash versus guardian-held read guard, closed launch
nonce and state transitions. Capture sanitized actual SDK launch arguments at
the OS dispatch boundary, not merely requested options. Reject duplicate model/
effort overrides, fast mode, resume, unsupported command shape and runtime drift.
Capture only the required values/hashes; no raw auth environment, secrets or
account files. Tie actual prompt/configuration to init/session and qualification.

Native image ACK in ready state precedes allowed execution/SDK query. The
existing engine_start_requested/ACK still marks inference/accounting separately.
On denial/cancel/death/timeout keep pumping owned debug EXIT before blocking job
drain; require independent process handles signaled and job quiescence before
workspace/slot/fence/guard release. A lost pump never authorizes cleanup success.

## Verification and exit from this unit

Self-review: version4 is necessary to preserve the newly committed version3
UNKNOWN semantics. Derived delivery is based on actual unique host/native bytes,
not a generic optional-flag default. Configuration proof is not private model
reasoning. Exact same two readonly tools for both paired arms; source/grant,
contract, owner/holdout, usage and all18 gates remain intact.

Run affected checks sequentially with frozen source pins; reuse unchanged
source-qualified component/reader/ledger proof. Review the actual changed
interfaces/lifetimes, then qualify the frozen native boundary with two effort
values, ambient override negatives, both read kinds/variants and cleanup/death
controls. Register exact evidence only after it passes. Final-head CI and scoped
independent review precede integration. Only then assess one bounded configured-
account pipeline under existing Goal authority/current selected configuration.
Continue independent full D2/E/F/M3–M8 work; business/live gates stay open.

## Dispatch consumer audit and next pure component

Read against committed df0e24b1 and installed SDK116. Adapter.verify runs native
`--version` and `auth status --json` in the host and again in the worker, before
worker_ready. SDK connect separately runs `-v`, then spawns the query process
before TrialProfile.before_query requests the existing inference ACK. A query
image gate alone cannot cover those other invocations. Keep separate explicit
purposes for bounded version/auth preflight and query, with no query capability
or reasoning proof inferred from a successful version check. Each actual native
invocation needs owned image/lifetime verification at integration.

SDKClient replaces permission_prompt_tool_name with stdio when can_use_tool is
present. The actual query grammar therefore includes --permission-prompt-tool
stdio, --permission-mode default, empty --tools, the exact allowedTools list,
literal --system-prompt, selected --model/--effort, inline --settings with exactly
fastMode:false/disableAllHooks:true, inline --mcp-config containing only the
fixture/skill SDK server descriptors, --strict-mcp-config, --setting-sources=,
and the existing five restrictive extra flags. SDK116 strips the in-process
server instance; each CLI descriptor is exactly type:sdk/name:<server>. It ends
with --input-format stream-json. Reject unknown/duplicate/override flags,
file/preset prompts, ambient setting sources, extra servers, resume/fallback,
partial/hook output, plugins and thinking overrides. Do not silently repair
an unsupported argument shape.

Next standalone component: a pure closed query-dispatch validator, unreachable
from execution and outside PROFILE_SOURCES until integration. Its input includes
the actual argument vector captured around SDK open_process and the actual raw
Windows CreateProcess command line, executable parameter, cwd and creationflags.
Require exact subprocess.list2cmdline agreement and an explicit expected pin
(CLI path, selected model/effort, prompt hash, workspace cwd and exact two-tool
inventory). Validate inline JSON with duplicate-key rejection and strict boolean
types. Preserve only sanitized selected values/hashes in its result; never emit
argv, prompt, raw settings/environment, auth or paths to guardian control IPC.
The result proves argument consistency only, not that this function ran at an
OS boundary, that an image was loaded, or that the provider accepted reasoning.

RED/GREEN cases cover actual SDK116 command construction without connect or a
native child, two efforts, raw-command mismatch, executable/cwd/flag drift,
duplicates/foreign flags, changed prompt/model/effort, JSON duplicate keys and
boolean-number confusion, external MCP servers and nonempty source lists.
No account/native qualification is justified by this unreachable parser alone.

The ready-state protocol also needs explicit evolution. Existing engine_event
requires a usage recorder and is illegal before inference ACK; do not encode
native launch controls as early engine events. Use a closed new packet/control
state for input4, persist its raw host evidence, and keep operation/legacy packet
semantics unchanged. A parent image allow decision must precede native execution;
the separate before_engine_start callback still marks exposure/accounting before
query submission. Cancellation or storage failure cannot discard ownership.

The first two-process V4 probe refused the venv redirector: retained launcher PID
15128 differed from actual trusted worker PID23332. No remote duplication or ACK
was attempted. Exact outer job drain preceded image-guard release; failed report
e9e73a48 and its separate frozen manifest54ed1d8a remain preserved. A distinct V5
probe will test direct hash-pinned base Python with -I -S and a fixed explicit
trusted site-package bootstrap. Never accept a receipt-supplied worker PID or
reopen a bare PID to bypass this refusal. This is not yet production transport.

V5 failed before any valid worker receipt. Its stderr was DEVNULL and the rejected
frame/exit code was not saved, so the historical startup cause is UNKNOWN.
The outer job drained before guard release. Subsequent static tracing establishes
an unsupported dependency in that bootstrap: SDK imports mcp, whose package
initializer imports client.stdio and then mcp.os.win32.utilities. That module
imports pywintypes, win32api, win32con and win32job. Installed pywin32.pth normally
adds win32 and win32/lib and runs its DLL bootstrap; the V5 fixed -S path list
omits them. The next diagnostic is import-only, with early startup/error capture,
fixed explicit paths/DLL directory and process creation disabled inside the
imported worker. It tests a concrete import hypothesis without another native
image run. Preserve V5 unchanged; no automatic follow-up image probe.

Future three-actor transport must transfer a retained worker capability into the
guardian while both source/target processes are retained, rather than pass a
receipt-supplied PID for reopen. The guardian retains only native runtime/image
identity and closed handle/nonce metadata. Host-to-worker input remains direct.
Treat the direct-base bootstrap and its DLL/import dependencies as a changed
runtime boundary requiring qualification, not an alias for old venv execution.
Never patch CreateProcess globally in the shared server; creator instrumentation
belongs in an isolated fixed worker or a purpose-specific owned preflight helper.

The separate import-only diagnostic V1 also stopped before SDK imports: early
direct-base worker PID/birth matched the retained process, but native job
accounting reported total2/active2 rather than its assumed total1. Parent refused
the import ACK, drained the exact job (active0), and saved exit91/stderr0 plus the
first raw frame. The second variant was not run. No SDK import outcome or second
member identity was observed. Preserve report c4b5d553 and the failed assumption.
Do not label the extra member conhost or an SDK child without actual evidence.

This now requires revising the experimental measurement boundary before another
run, rather than another bootstrap guess. The actual requirement is no SDK
process creation during imports; a fixed total1 was an added experimental
assumption. A bounded next diagnostic can capture the exact native-job startup
member set with retained process identities, birth times and observed image
paths before import ACK, then verify cumulative birth count/membership do not
change during imports and the rejecting CreateProcess counter remains0.
Inventory originates in the actual owned job, never a worker-supplied PID; any
query-opened member handle must be rechecked for exact job/incarnation and held
through terminal drain. Unknown identity or incomplete inventory stays unknown
and never authorizes a native image ACK. This is not a relaxation of the final
query process/image/guardian identity or lifetime requirements.
