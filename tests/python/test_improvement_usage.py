"""Improvement attribution uses the existing event/index/call pipeline, never synthetic Team bills."""
from _paths import ROOT, SERVER  # noqa: F401

import asyncio
import importlib.util
import sqlite3
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

TEST_ROOT = Path(tempfile.mkdtemp(prefix="improvement-usage-"))
for key, name in {"JAVIS_STATE_DIR": "state", "BRAINS_DIR": "brains", "OBSIDIAN_VAULT_PATH": "vault",
                  "BRAIN_PATH": "brain", "SOURCES_PATH": "sources", "JAVIS_CLAUDE_PROJECTS_DIR": "empty-claude",
                  "JAVIS_CODEX_SESSIONS_DIR": "empty-codex"}.items():
    os.environ[key] = str(TEST_ROOT / name)

import turn_context as TC
import usage_store as US
import usage_index as UI
import resonance_store as RS
from agent_ledger import CallLedger

if importlib.util.find_spec("improvement_usage"):
    import improvement_usage as IU
else:
    IU = None


def execution(trial="trial-1", **changes):
    return {"experiment_id": "experiment-1", "trial_id": trial, "case_id": "case-1", "variant": "baseline",
            "repeat": 1, "attempt": 1, "execution_id": "improvement_trial:" + trial, "role": "solver",
            "purpose": "improve_probe", "learning_origin": "trial", **changes}


class ExecutionMetadataTests(unittest.TestCase):
    def test_improvement_context_has_no_team_and_drops_prompt_or_credential_fields(self):
        metadata = execution()
        self.assertEqual(TC.execution_metadata({**metadata, "prompt": "private", "api_key": "private"}), metadata)
        self.assertNotIn("team_id", metadata)
        token = TC.bind(TC.make("improvement", execution=metadata))
        try:
            async def read():
                return await asyncio.to_thread(TC.current)
            got = asyncio.run(read())
            self.assertEqual(got["execution"], metadata)
            got["execution"]["trial_id"] = "caller-mutation"
            self.assertEqual(TC.current()["execution"], metadata)
        finally:
            TC.reset(token)

    def test_incomplete_or_malformed_improvement_identity_is_rejected(self):
        for changes in ({"attempt": True}, {"repeat": 0}, {"learning_origin": "production"},
                        {"trial_id": "../outside"}, {"execution_id": "unrelated-execution"},
                        {"purpose": "reply"}, {"team_id": "invented-team"}, {"case_id": None}):
            with self.subTest(changes=changes):
                self.assertIsNone(TC.execution_metadata(execution(**changes)))


class ImprovementUsageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(IU, "Improvement views are not bound to the existing usage pipeline")
        self.root = Path(tempfile.mkdtemp(prefix="case-", dir=TEST_ROOT))
        self.patches = [patch.object(US, "_PATH", self.root / "usage.json"),
                        patch.object(US, "_EVENTS_PATH", self.root / "events.jsonl"),
                        patch.object(US, "_TELEMETRY_ERRORS", {}),
                        patch.object(UI, "_EVENTS_PATH", self.root / "events.jsonl"),
                        patch.object(UI, "DB_PATH", self.root / "usage-index.db")]
        for item in self.patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in reversed(self.patches)])

    def record(self, tin=100, tout=15, **changes):
        US.record("anthropic-cli", "unpriced-selected-model", tin, tout, cost=changes.pop("cost", None),
                  execution=changes.pop("execution", execution()), source_id="improvement-native", **changes)

    def summary(self, trial="trial-1"):
        return IU.trial_usage("experiment-1", trial)

    def test_summary_and_late_requests_count_once_and_keep_missing_money_unknown(self):
        self.record(300, 30, event_kind="cli_fallback", event_id="summary")
        self.assertIsNone(self.summary()["requests"])
        for request_id, tin in (("msg-1", 100), ("msg-2", 200), ("msg-1", 100)):
            self.record(tin, 15, event_kind="cli_detail", event_id=request_id, request_id=request_id)
        result = self.summary()
        self.assertEqual((result["tokens_in"], result["tokens_out"], result["requests"]), (300, 30, 2))
        self.assertIsNone(result["money"]["reported_usd"])
        self.assertIsNone(result["money"]["subscription_equivalent_usd"])
        self.assertFalse(result["coverage"]["money_complete"])
        self.assertEqual(US.summary()["today"]["total"]["in"], 300)

    def test_sdk_and_late_raw_cli_request_identity_is_not_counted_twice(self):
        ex = execution(cli_session_id="native-session", cli_session_new=True)
        self.record(300, 30, execution=ex, event_kind="cli_fallback", event_id="summary")
        for request_id, tin in (("msg-1", 100), ("msg-2", 200)):
            self.record(tin, 15, execution=ex, event_kind="cli_detail", event_id=request_id, request_id=request_id)
        connection = UI._connect()
        try:
            UI._insert_events(connection, "synthetic-native-raw", [{"provider": "claude", "source": "synthetic-native",
                "activity": "background", "model": "unpriced-selected-model", "project": "synthetic-trial",
                "day": US._today(), "ts": int(time.time()), "input": tin, "output": 15, "cache_read": 0,
                "cache_create": 0, "turns": 1, "request_id": request_id, "session_id": "native-session"}
                for request_id, tin in (("msg-1", 100), ("msg-2", 200))])
            connection.commit()
        finally:
            connection.close()
        result = self.summary()
        self.assertEqual((result["tokens_in"], result["requests"]), (300, 2))
        self.assertTrue(result["coverage"]["requests_complete"])

    def test_unknown_usage_and_observed_zero_remain_distinct(self):
        self.record(None, None, event_kind="execution", event_id="interrupted", status="interrupted")
        self.assertIsNone(self.summary()["tokens_in"])
        self.assertEqual(self.summary()["coverage"]["unobserved_attempts"], 1)
        self.record(0, 0, cost=0.0, execution=execution("zero"), event_kind="cli_fallback", event_id="observed-zero")
        self.assertEqual(self.summary("zero")["tokens_in"], 0)
        self.assertEqual(self.summary("zero")["money"]["subscription_equivalent_usd"], 0.0)

    def test_old_projection_cursor_backfills_improvement_ids_without_cross_scope_rows(self):
        self.record(100, 15, event_kind="cli_detail", event_id="first-request")
        connection = sqlite3.connect(UI.DB_PATH)
        try:
            connection.execute("CREATE TABLE usage_observations(event_key TEXT PRIMARY KEY,team_id TEXT,task_id TEXT,payload TEXT)")
            connection.execute("CREATE TABLE files_seen(path TEXT PRIMARY KEY,size INTEGER,mtime REAL,offset INTEGER DEFAULT 0)")
            connection.execute("INSERT INTO files_seen VALUES(?,?,?,?)", ("__execution_events_v1__:" + str(UI._EVENTS_PATH),
                                                                       0, 0, UI._EVENTS_PATH.stat().st_size))
            connection.commit()
        finally:
            connection.close()
        self.record(999, 1, execution=execution("other", experiment_id="another-experiment"),
                    event_kind="cli_detail", event_id="other-request")
        events, details = UI.improvement_events("experiment-1", "trial-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["execution"]["trial_id"], "trial-1")
        self.assertNotIn("team_id", events[0]["execution"])
        self.assertEqual(UI.execution_events("invented-team"), ([], []))

    def test_telemetry_failure_is_scoped_and_persisted_error_is_not_zero_usage(self):
        US.note_telemetry_error(execution())
        self.assertEqual(US.improvement_telemetry_errors("experiment-1", "trial-1"), 1)
        self.assertEqual(US.telemetry_errors("experiment-1"), 0)
        self.record(None, None, event_kind="execution", event_id="lost-observation", telemetry_errors=1, status="interrupted")
        US._TELEMETRY_ERRORS.clear()
        result = self.summary()
        self.assertIsNone(result["tokens_in"])
        self.assertEqual(result["coverage"]["telemetry_errors"], 1)

    def test_shared_call_mirror_survives_generic_reconciliation_and_no_usage_is_unknown(self):
        store = RS.GoalStore(self.root / "resonance.sqlite3")
        ledger = CallLedger(store)
        call = ledger.reserve(purpose="improve_probe", reason_ref="improvement_trial:trial-1", brain_id="brain-a",
            context_ref="improvement:experiment-1", mirror_ref="improvement_trial:trial-1", obligation=True, now=100)
        self.assertIsNotNone(call)
        self.assertTrue(ledger.mark_engine(call, "anthropic-cli", "unpriced-selected-model", now=101))
        ledger.reconcile_stale(now=10000)
        self.assertEqual(ledger.get(call)["status"], "running")
        self.assertFalse(ledger.refund(call))
        result = self.summary()
        self.assertIsNone(result["tokens_in"])
        self.assertEqual(result["coverage"]["unobserved_attempts"], 1)
        self.assertFalse((self.root / "team.sqlite3").exists())
        with store._conn() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM goals").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
