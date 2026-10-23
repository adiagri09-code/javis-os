"""Host-only native IPC supervisor shared by genuine Trial and operation adapters."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import winproc
from improvement_cases import _fields
from improvement_claude import _settled_owned
from improvement_sandbox import _private_directory, worker_environment
from improvement_store import _json


async def execute_worker(kind_namespace, request, receipt, *, config_pin, workspace_root, before_engine_start):
    from improvement_worker import WorkerGroup, process_flags
    if kind_namespace == "trial":
        worker_file, identity_keys = "improvement_worker.py", ("trial_id", "attempt", "input_hash")
    elif kind_namespace == "operation":
        worker_file, identity_keys = "improvement_operation_worker.py", ("operation_id", "attempt", "role", "purpose", "input_hash")
    else:
        raise ValueError("unsupported_native_worker_namespace")
    if not callable(before_engine_start):
        raise ValueError("native_start_boundary_unbound")
    prefix = kind_namespace + "_"
    deadline = request["deadline_at"]
    await asyncio.to_thread(_private_directory, Path(receipt["path"]) / "tmp")
    environment = worker_environment(Path(receipt["path"]))
    identity = {key: receipt[key] for key in identity_keys}
    process = guard = None
    stderr_task = None
    maximum = 8 * 1024 * 1024

    async def send(packet):
        raw = _json(packet).encode("utf-8") + b"\n"

        def write():
            process.stdin.write(raw)
            process.stdin.flush()

        await asyncio.to_thread(write)

    async def drain_stderr():
        # Drain to avoid a pipe deadlock; raw stderr is never a public result or artifact.
        while await asyncio.to_thread(process.stderr.read, 4096):
            pass

    async def close_worker():
        if guard is not None:
            await asyncio.to_thread(guard.close)
        elif process is not None and process.poll() is None:
            await asyncio.to_thread(winproc.kill_tree, process.pid)
        if process is not None:
            try:
                await asyncio.to_thread(process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        if stderr_task is not None:
            await asyncio.gather(stderr_task, return_exceptions=True)

    try:
        async with asyncio.timeout(max(0.0, deadline - time.time())):
            spawn = asyncio.create_task(asyncio.to_thread(subprocess.Popen,
                [sys.executable, "-I", "-X", "utf8", str(Path(__file__).with_name(worker_file))],
                cwd=receipt["path"], env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=sys.platform != "win32", creationflags=process_flags()))
            spawned, cancelled = await _settled_owned(asyncio.gather(spawn, return_exceptions=True))
            if isinstance(spawned[0], BaseException):
                raise spawned[0]
            process = spawned[0]
            # The child blocks on its first input until its whole lifetime is owned.
            guard = WorkerGroup(process.pid)
            if cancelled is not None:
                raise cancelled
            stderr_task = asyncio.create_task(drain_stderr())
            await send({"version": 1, "config_pin": config_pin, "workspace_root": str(workspace_root),
                        "receipt": receipt, "capability_hash": request["capability_hash"]})
            sequence, state = 0, "starting"
            while True:
                raw = await asyncio.to_thread(process.stdout.readline, maximum + 1)
                if not raw or len(raw) > maximum or not raw.endswith(b"\n"):
                    raise ValueError(prefix + "worker_protocol_incomplete")
                packet = json.loads(raw)
                sequence += 1
                if (not isinstance(packet, dict) or type(packet.get("sequence")) is not int
                        or packet.get("sequence") != sequence or type(packet.get("version")) is not int
                        or packet.get("version") != 1):
                    raise ValueError("invalid_" + kind_namespace + "_worker_packet")
                kind = packet.get("type")
                if kind == "worker_error":
                    _fields(packet, {"version", "sequence", "type", "reason", "error_type"})
                    yield packet
                    raise RuntimeError(prefix + "worker_failed")
                extras = {"worker_ready": {"capability_hash"}, "engine_start_requested": set(),
                          "engine_event": {"event"}, "worker_complete": {"tool_denials"}}
                if kind_namespace == "trial":
                    extras["fixture_event"] = {"event"}
                    extras["worker_complete"].add("fixture_events")
                if kind not in extras:
                    raise ValueError("invalid_" + kind_namespace + "_worker_packet")
                _fields(packet, {"version", "sequence", "type", *identity, *extras[kind]})
                if _json({key: packet[key] for key in identity}) != _json(identity):
                    raise ValueError(prefix + "worker_identity_drift")
                if kind == "worker_ready":
                    if state != "starting" or packet["capability_hash"] != request["capability_hash"]:
                        raise ValueError(prefix + "capability_drift")
                    state = "ready"
                elif kind == "engine_start_requested":
                    if state != "ready":
                        raise ValueError(prefix + "worker_start_repeated")
                    await before_engine_start()
                    await send({"type": "engine_start_ack", **identity})
                    state = "running"
                elif state != "running":
                    raise ValueError(prefix + "worker_event_before_start")
                yield packet
                if kind == "worker_complete":
                    break
            if await asyncio.to_thread(process.wait, timeout=5) != 0:
                raise RuntimeError(prefix + "worker_failed")
    finally:
        closed, cancelled = await _settled_owned(asyncio.gather(
            asyncio.create_task(close_worker()), return_exceptions=True))
        if isinstance(closed[0], BaseException):
            raise closed[0]
        if cancelled is not None:
            raise cancelled
