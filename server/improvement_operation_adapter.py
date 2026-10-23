"""Selected native engine adapter for actual operation identities."""
from __future__ import annotations

import asyncio
import math
import time

from improvement_cases import _digest, _fields, _frozen
from improvement_claude import ClaudeTrialAdapter
from improvement_operation_workspace import OperationWorkspace
from improvement_store import _hash


class ClaudeOperationAdapter:
    def __init__(self, config_pin, *, workspace=None, before_engine_start=None):
        # Reuse the actual selected runtime verification; this creates no Trial.
        self._native = ClaudeTrialAdapter(config_pin)
        self.pin = self._native.pin
        if workspace is not None and type(workspace) is not OperationWorkspace:
            raise TypeError("concrete_operation_workspace_required")
        self.workspace, self.before_engine_start = workspace, before_engine_start

    def verify(self):
        return self._native.verify()

    async def execute(self, request, workspace):
        if self.workspace is None or not callable(self.before_engine_start):
            raise ValueError("operation_start_boundary_unbound")
        request, receipt = _frozen(request), _frozen(workspace)
        _fields(request, {"version", "operation_id", "attempt", "role", "purpose", "deadline_at",
                          "engine_config_hash", "capability_hash"})
        if (type(request["version"]) is not int or request["version"] != 1 or type(request["attempt"]) is not int
                or request["attempt"] not in (1, 2)):
            raise ValueError("invalid_operation_execution_request")
        deadline = request["deadline_at"]
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= time.time():
            raise ValueError("operation_deadline_expired")
        for key in ("engine_config_hash", "capability_hash"):
            _digest(request[key])
        manifest = await asyncio.to_thread(self.workspace.validate, receipt)
        if (any(request[key] != receipt[key] for key in ("operation_id", "attempt", "role", "purpose"))
                or request["engine_config_hash"] != manifest["engine_config_hash"]
                or request["engine_config_hash"] != _hash(self.pin)):
            raise ValueError("operation_configuration_drift")
        verified = await asyncio.to_thread(self.verify)
        if not verified.get("supported") or verified.get("capability_hash") != request["capability_hash"]:
            raise ValueError("operation_capability_drift")
        from improvement_native_transport import execute_worker
        from contextlib import aclosing
        async with aclosing(execute_worker("operation", request, receipt, config_pin=self.pin,
                workspace_root=self.workspace.root, before_engine_start=self.before_engine_start)) as packets:
            async for packet in packets:
                yield packet
