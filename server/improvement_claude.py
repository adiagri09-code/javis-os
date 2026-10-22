"""A closed trial profile for the existing Claude engine; release capability is gated separately."""
from __future__ import annotations

import hashlib
import json

from improvement_blobs import MAX_ASSET_BYTES
from improvement_cases import _fields, _frozen, _text

PROFILE_VERSION = "claude-isolated-trial-v1"


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
