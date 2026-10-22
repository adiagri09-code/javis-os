"""A closed trial profile for the existing Claude engine; release capability is gated separately."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from improvement_blobs import MAX_ASSET_BYTES, check_ancestry
from improvement_cases import _digest, _fields, _frozen, _text
from improvement_store import _hash

PROFILE_VERSION = "claude-isolated-trial-v1"
VERIFIED_NATIVE_RUNTIMES = {("win32", "2.1.304",
    "019e5174d5d954585edb1a946fe280e44a973050b4897034adf0e16306f85fdd", "0.2.116")}


def profile_hash():
    root = Path(__file__).parent
    return _hash({name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in
                  ("improvement_claude.py", "improvement_sandbox.py", "improvement_worker.py", "claude_sdk_engine.py")})


def _managed_policy():
    """Detect policy presence without reading policy contents or login files."""
    roots = {"win32": Path(r"C:\Program Files\ClaudeCode"),
             "darwin": Path("/Library/Application Support/ClaudeCode"), "linux": Path("/etc/claude-code")}
    if sys.platform not in roots:
        return "unknown"
    paths = [roots[sys.platform] / name for name in ("managed-settings.json", "managed-settings.d", "managed-mcp.json")]
    paths.append(Path.home() / ".claude" / "remote-settings.json")
    try:
        for path in paths:
            try:
                path.lstat()
                return "present"
            except FileNotFoundError:
                pass
        if sys.platform == "win32":
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
                    try:
                        with winreg.OpenKey(hive, r"SOFTWARE\Policies\ClaudeCode", 0, winreg.KEY_READ | view):
                            return "present"
                    except FileNotFoundError:
                        pass
        elif sys.platform == "darwin":
            # No macOS native runtime has been verified; do not infer MDM absence from files.
            return "unknown"
    except OSError:
        return "unknown"
    return "absent"


def _runtime_observation(pin):
    from improvement_sandbox import worker_environment
    binary = Path(pin["cli_path"])
    if not binary.is_absolute():
        raise ValueError("invalid_trial_binary")
    check_ancestry(binary)
    with binary.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    managed = _managed_policy()
    result = {"platform": sys.platform, "cli_hash": digest,
              "sdk_version": importlib.metadata.version("claude-agent-sdk"),
              "profile_hash": profile_hash(), "managed_policy": managed, "auth": {}}
    known = (sys.platform, pin["cli_version"], digest, result["sdk_version"])
    if (managed != "absent" or digest != pin["cli_hash"] or known not in VERIFIED_NATIVE_RUNTIMES
            or result["profile_hash"] != pin["profile_hash"]):
        return result
    with tempfile.TemporaryDirectory(prefix="improvement-verify-") as scratch:
        environment = worker_environment(Path(scratch))
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        version = subprocess.run([str(binary), "--version"], env=environment, capture_output=True,
                                 text=True, timeout=10, check=True, **flags)
        result["cli_version"] = version.stdout.strip().split()[0]
        auth = subprocess.run([str(binary), "auth", "status", "--json"], env=environment, capture_output=True,
                              text=True, timeout=15, check=True, **flags)
        status = json.loads(auth.stdout)
        result["auth"] = {"logged_in": status.get("loggedIn") is True, "method": status.get("authMethod"),
                          "provider": status.get("apiProvider"), "plan": status.get("subscriptionType")}
    return result


class ClaudeTrialAdapter:
    def __init__(self, config_pin):
        self.pin = _frozen(config_pin)
        _fields(self.pin, {"version", "provider", "engine_id", "model", "reasoning", "cli_path", "cli_hash",
                           "cli_version", "sdk_version", "profile_version", "profile_hash"})
        if type(self.pin["version"]) is not int or self.pin["version"] != 1:
            raise ValueError("unsupported_trial_configuration")
        for name in ("cli_hash", "profile_hash"):
            _digest(self.pin[name])
        for name, value in self.pin.items():
            if name != "version":
                _text(value)

    def verify(self):
        requested = {key: self.pin[key] for key in ("provider", "engine_id", "model", "reasoning")}

        def unsupported(reason):
            return {"supported": False, "reason": reason, "requested": requested}

        if (self.pin["provider"] != "anthropic-cli" or self.pin["engine_id"] != "claude-sdk"
                or self.pin["profile_version"] != PROFILE_VERSION
                or self.pin["reasoning"] not in ("low", "medium", "high", "xhigh", "max")):
            return unsupported("unsupported_trial_configuration")
        try:
            observed = _runtime_observation(self.pin)
        except (OSError, ValueError, IndexError, subprocess.SubprocessError, importlib.metadata.PackageNotFoundError):
            return unsupported("runtime_unavailable")
        if observed.get("managed_policy") != "absent":
            return unsupported("managed_policy_unverified")
        if any(observed.get(field) != self.pin[field] for field in ("cli_hash", "cli_version", "sdk_version", "profile_hash")):
            return unsupported("trial_runtime_drift")
        runtime = tuple(observed.get(key) for key in ("platform", "cli_version", "cli_hash", "sdk_version"))
        if runtime not in VERIFIED_NATIVE_RUNTIMES:
            return unsupported("native_enforcement_unverified")
        if observed.get("auth") != {"logged_in": True, "method": "claude.ai", "provider": "firstParty", "plan": "max"}:
            return unsupported("native_auth_policy_unverified")
        return {"supported": True, "reason": None, "requested": requested,
                "capability_hash": _hash({"pin": self.pin, "runtime": observed}), "runtime": observed}


class TrialProfile:
    """Host-created options and raw telemetry, used only in an isolated child process."""

    def __init__(self, pin, broker, system_prompt, *, before_query=None):
        self.pin = _frozen(pin)
        _fields(self.pin, {"provider", "model", "reasoning", "cli_path", "sdk_version"})
        if self.pin["provider"] != "anthropic-cli" or self.pin["reasoning"] not in ("low", "medium", "high", "xhigh", "max"):
            raise ValueError("unsupported_trial_configuration")
        for value in self.pin.values():
            _text(value)
        if not isinstance(system_prompt, str) or len(system_prompt.encode()) > MAX_ASSET_BYTES:
            raise ValueError("invalid_trial_system_prompt")
        self.broker, self.system_prompt = broker, system_prompt
        self._before_query = before_query
        self._started = False
        self.observed_models = set()
        self.actual_reasoning_coverage = "unknown"
        self.denials = []

    async def before_query(self):
        if self._started:
            raise ValueError("trial_profile_already_used")
        self._started = True
        if self._before_query is None:
            raise RuntimeError("host_engine_start_not_acknowledged")
        await self._before_query()

    def options(self, engine):
        from claude_agent_sdk import ClaudeAgentOptions, PermissionResultDeny, create_sdk_mcp_server, tool
        if engine.session_id:
            raise ValueError("trial_resume_forbidden")

        @tool("fixture_read", "Read a pinned authorized fixture by snapshot identity and source version",
              {"snapshot_id": str, "source_version": str})
        async def fixture_read(args):
            if isinstance(args, dict) and set(args) == {"snapshot_id", "source_version"}:
                result = self.broker.read("fixture.read", {"snapshot_id": args["snapshot_id"]},
                                          args["source_version"], self.broker.grant_hash)
            else:
                result = self.broker.read("fixture.read", {}, None, self.broker.grant_hash)
            return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                    "is_error": result["status"] != "fixture_hit"}

        async def deny(name, args, context):
            self.denials.append({"type": "tool_denied", "name": str(name), "reason": "outside_trial_fixture_grant"})
            return PermissionResultDeny(message="Only the pinned fixture tool is authorized in this trial")

        return ClaudeAgentOptions(cli_path=self.pin["cli_path"], cwd=engine.cwd,
            system_prompt=self.system_prompt, model=self.pin["model"], effort=self.pin["reasoning"],
            tools=[], skills=[], setting_sources=[], plugins=[], agents={}, hooks={}, add_dirs=[],
            mcp_servers={"fixture": create_sdk_mcp_server("fixture", tools=[fixture_read])}, strict_mcp_config=True,
            allowed_tools=["mcp__fixture__fixture_read"], permission_mode="default", can_use_tool=deny,
            settings='{"fastMode":false,"disableAllHooks":true}',
            extra_args={"no-session-persistence": None, "disable-slash-commands": None, "no-chrome": None,
                        "restricted": None, "safe-mode": None},
            stderr=engine._on_stderr)

    def observe(self, message):
        """Never fabricate a missing usage field or assemble an artifact from narration."""
        from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, ToolUseBlock, UserMessage, ToolResultBlock
        events = []
        if isinstance(message, SystemMessage):
            events.append({"type": "native_system", "subtype": message.subtype, "data": _frozen(message.data)})
        elif isinstance(message, AssistantMessage):
            if message.model:
                self.observed_models.add(message.model)
            events.append({"type": "observation", "model": message.model, "message_id": message.message_id,
                           "usage": _frozen(message.usage), "session_id": message.session_id})
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    events.append({"type": "tool_call", "name": block.name, "id": block.id})
        elif isinstance(message, UserMessage) and isinstance(message.content, list):
            for block in message.content:
                if isinstance(block, ToolResultBlock):
                    events.append({"type": "tool_result", "id": block.tool_use_id, "is_error": block.is_error})
        elif isinstance(message, ResultMessage):
            events.append({"type": "usage", "usage": _frozen(message.usage), "cost_usd": message.total_cost_usd,
                           "model_usage": _frozen(message.model_usage), "session_id": message.session_id})
            content = message.result
            artifact_status = "unknown"
            if isinstance(content, str) and len(content.encode("utf-8")) <= MAX_ASSET_BYTES:
                events.append({"type": "artifact", "content": content,
                               "hash": hashlib.sha256(content.encode("utf-8")).hexdigest()})
                artifact_status = "observed"
            events.append({"type": "terminal", "subtype": message.subtype, "is_error": message.is_error,
                           "artifact_status": artifact_status, "session_id": message.session_id,
                           "actual_models": sorted(self.observed_models), "actual_reasoning_coverage": "unknown"})
        return events
