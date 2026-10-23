"""Actual role admission ownership survives HTTP cancellation and shutdown."""
from _paths import ROOT, SERVER  # noqa: F401

import asyncio
import importlib.util
import threading
import unittest
from unittest.mock import patch

import test_improvement_operation_execution as F
import test_improvement_operation_runner as R
from improvement_operation_adapter import ClaudeOperationAdapter


class OperationTaskTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f = F.OperationExecutionTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.execution, self.owner, self.row = self.f.execution(), self.f.owner, self.f.operation
        self.acked, self.closed = asyncio.Event(), asyncio.Event()
        self.hang = False
        self.body = '{"note":"JAVIS_LESSON: untrusted; never write production memory or jobs"}'

    def adapter(self, *args, **kwargs):
        return R.OperationRunnerTests.adapter(self, *args, **kwargs)

    def controller(self):
        self.assertIsNotNone(importlib.util.find_spec("improvement_operation_tasks"), "Owned role task supervisor is absent")
        from improvement_operation_runner import OperationRunner
        from improvement_operation_tasks import OperationTasks
        return OperationTasks(self.execution, OperationRunner(self.execution, adapter_factory=self.adapter))

    async def start(self, tasks):
        with patch.object(ClaudeOperationAdapter, "verify", return_value={"supported": True, "capability_hash": "c" * 64}):
            return await tasks.start(self.owner, self.row["operation_id"], expected_generation=1, event_key="owner-start-role")

    async def test_committed_role_task_runs_to_actual_result_then_shutdown_is_quiescent(self):
        tasks = self.controller()
        try:
            started = await self.start(tasks)
            self.assertEqual(started["status"], "reserved")
            result = await tasks.join(self.owner, self.row["operation_id"])
            self.assertEqual(result["status"], "completed")
            self.assertIsNotNone(result["result"])
        finally:
            await tasks.close()
        self.assertTrue(self.closed.is_set())

    async def test_shutdown_owns_a_committing_preflight_after_repeated_http_cancel(self):
        tasks = self.controller()
        entered, release = threading.Event(), threading.Event()
        reserve = self.execution.reserve

        def blocked(*args, **kwargs):
            result = reserve(*args, **kwargs)
            entered.set()
            if not release.wait(15):
                raise RuntimeError("synthetic admission timeout")
            return result

        with patch.object(self.execution, "reserve", side_effect=blocked):
            caller = asyncio.create_task(self.start(tasks))
            closer = None
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 15))
                caller.cancel()
                await asyncio.sleep(.02)
                caller.cancel()
                self.assertFalse(caller.done())
                closer = asyncio.create_task(tasks.close())
                await asyncio.sleep(.02)
                self.assertFalse(closer.done())
            finally:
                release.set()
                await asyncio.gather(caller, return_exceptions=True)
                if closer is not None:
                    await closer
                else:
                    await tasks.close()
        result = self.execution.get(self.owner, self.row["operation_id"])
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(self.execution.ledger.get(result["attempts"][-1]["call_id"])["status"], "refunded")
        self.assertFalse(self.acked.is_set())

    async def test_terminal_db_cancel_replay_still_drains_actual_live_role_worker(self):
        tasks = self.controller()
        self.hang = True
        try:
            await self.start(tasks)
            await asyncio.wait_for(self.acked.wait(), 15)
            current = self.execution.get(self.owner, self.row["operation_id"])
            payload = {"expected_generation": current["generation"], "event_key": "owner-cancel-live-role"}
            stopped = self.execution.cancel(self.owner, self.row["operation_id"], **payload)
            self.assertEqual(stopped["status"], "cancelled")
            self.assertFalse(self.closed.is_set())
            await tasks.cancel(self.owner, self.row["operation_id"], **payload)
            self.assertTrue(self.closed.is_set())
            path, _ = self.execution.workspace._paths(self.row["operation_id"], 1)
            self.assertFalse(path.exists())
            self.assertEqual(self.execution.ledger.get(stopped["attempts"][-1]["call_id"])["status"], "interrupted")
        finally:
            await tasks.close()

    async def test_shutdown_owns_inflight_cancel_after_http_response_is_cancelled(self):
        tasks = self.controller()
        self.hang = True
        await self.start(tasks)
        await asyncio.wait_for(self.acked.wait(), 15)
        row = self.execution.get(self.owner, self.row["operation_id"])
        entered, release = threading.Event(), threading.Event()
        cancel = self.execution.cancel

        def blocked(*args, **kwargs):
            result = cancel(*args, **kwargs)
            entered.set()
            if not release.wait(15):
                raise RuntimeError("synthetic cancel publication timeout")
            return result

        with patch.object(self.execution, "cancel", side_effect=blocked):
            caller = asyncio.create_task(tasks.cancel(self.owner, self.row["operation_id"],
                expected_generation=row["generation"], event_key="owner-cancel-blocked-role"))
            closer = None
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 15))
                caller.cancel()
                await asyncio.sleep(.02)
                caller.cancel()
                closer = asyncio.create_task(tasks.close())
                await asyncio.sleep(.02)
                self.assertFalse(closer.done())
            finally:
                release.set()
                await asyncio.gather(caller, return_exceptions=True)
                if closer is not None:
                    await closer
                else:
                    await tasks.close()
        self.assertTrue(self.closed.is_set())
        self.assertFalse(self.execution.workspace._paths(self.row["operation_id"], 1)[0].exists())

    async def test_committed_reservation_read_failure_cannot_leave_an_unclaimed_call(self):
        tasks = self.controller()
        get, reads = self.execution.get, []

        def fail_once(*args, **kwargs):
            if not reads:
                reads.append(True)
                raise OSError("synthetic read after committed reservation")
            return get(*args, **kwargs)

        with patch.object(self.execution, "get", side_effect=fail_once):
            with self.assertRaises(OSError):
                await self.start(tasks)
        await tasks.close()
        result = get(self.owner, self.row["operation_id"])
        self.assertEqual(result["status"], "not_run")
        self.assertEqual(self.execution.ledger.get(result["attempts"][-1]["call_id"])["status"], "refunded")

    async def test_failed_preflight_during_shutdown_is_not_a_committed_cleanup_failure(self):
        tasks = self.controller()
        entered, release = threading.Event(), threading.Event()

        def unsupported(*args, **kwargs):
            entered.set()
            if not release.wait(15):
                raise RuntimeError("synthetic unsupported preflight timeout")
            raise ValueError("operation_native_unavailable")

        with patch.object(self.execution, "reserve", side_effect=unsupported):
            caller = asyncio.create_task(self.start(tasks))
            closer = None
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 15))
                closer = asyncio.create_task(tasks.close())
                await asyncio.sleep(.02)
                self.assertFalse(closer.done())
            finally:
                release.set()
                values = await asyncio.gather(caller, return_exceptions=True)
                if closer is not None:
                    self.assertTrue(await closer)
                else:
                    await tasks.close()
        self.assertIsInstance(values[0], ValueError)
        self.assertEqual(self.execution.get(self.owner, self.row["operation_id"])["attempts"], [])


if __name__ == "__main__":
    unittest.main()
