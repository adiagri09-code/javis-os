"""One fresh typed role process; model output never enters production dispatch."""
from __future__ import annotations

import sys
from pathlib import Path

_SERVER_DIR = str(Path(__file__).resolve().parent)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)


async def run_request(payload, read_control, emit, *, adapter_factory=None, engine_factory=None):
    from improvement_cases import _digest, _fields, _frozen
    from improvement_claude import ClaudeTrialAdapter
    from improvement_operation_profile import OperationProfile
    from improvement_operation_workspace import OperationWorkspace
    from improvement_sandbox import TrialWorkspace
    from improvement_store import _hash, _json
    from improvement_worker import _sdk_hidden_processes

    payload = _frozen(payload)
    _fields(payload, {"version", "config_pin", "workspace_root", "receipt", "capability_hash"})
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ValueError("unsupported_operation_worker_protocol")
    _digest(payload["capability_hash"])
    root = Path(payload["workspace_root"])
    workspace = OperationWorkspace(root, brain_barrier=TrialWorkspace(root.parent / "trials"))
    receipt = payload["receipt"]
    manifest = workspace.validate(receipt)
    pin = payload["config_pin"]
    if manifest["engine_config_hash"] != _hash(pin):
        raise ValueError("operation_configuration_drift")
    verified = (adapter_factory or ClaudeTrialAdapter)(pin).verify()
    if not verified.get("supported") or verified.get("capability_hash") != payload["capability_hash"]:
        raise ValueError("operation_capability_drift")
    identity = {key: receipt[key] for key in ("operation_id", "attempt", "role", "purpose", "input_hash")}
    await emit({"type": "worker_ready", **identity, "capability_hash": payload["capability_hash"]})

    async def before_query():
        await emit({"type": "engine_start_requested", **identity})
        acknowledgement = await read_control()
        if type(acknowledgement) is not dict or _json(acknowledgement) != _json({"type": "engine_start_ack", **identity}):
            raise ValueError("operation_engine_start_not_acknowledged")

    profile = OperationProfile(pin, workspace, receipt, payload["capability_hash"], before_query=before_query)
    if engine_factory is None:
        from claude_cli import claude_engine
        engine_factory = claude_engine
    engine = engine_factory(system_prompt=profile.system_prompt, cwd=receipt["path"],
        tag=f"improvement-operation:{receipt['operation_id']}:{receipt['attempt']}", allowed_tools=[], model=pin["model"])
    engine.trial_profile = profile
    with _sdk_hidden_processes():
        async for event in engine.query(profile.user_prompt()):
            await emit({"type": "engine_event", **identity, "event": event})
    await emit({"type": "worker_complete", **identity, "tool_denials": profile.denials})


def main():
    import asyncio
    import contextlib
    import json
    maximum = 8 * 1024 * 1024
    output, sequence = sys.stdout.buffer, 0

    def read_packet():
        raw = sys.stdin.buffer.readline(maximum + 1)
        if not raw or len(raw) > maximum or not raw.endswith(b"\n"):
            raise ValueError("invalid_operation_worker_packet")
        value = json.loads(raw)
        if type(value) is not dict:
            raise ValueError("invalid_operation_worker_packet")
        return value

    async def emit(event):
        nonlocal sequence
        sequence += 1
        raw = json.dumps({"version": 1, "sequence": sequence, **event}, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode() + b"\n"
        if len(raw) > maximum:
            raise ValueError("operation_worker_event_too_large")
        output.write(raw)
        output.flush()

    async def read_control():
        return await asyncio.to_thread(read_packet)

    try:
        payload = read_packet()
        with contextlib.redirect_stdout(sys.stderr):
            asyncio.run(run_request(payload, read_control, emit))
    except Exception as error:
        asyncio.run(emit({"type": "worker_error", "reason": "operation_worker_failed", "error_type": type(error).__name__}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
