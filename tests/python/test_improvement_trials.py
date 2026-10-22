"""Durable trial and existing call reservation use real isolated SQLite, without models."""
from _paths import ROOT, SERVER  # noqa: F401

import copy
import importlib.util
import json
import sqlite3
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

import test_improvement_cases as fixtures
import improvement_store as IM
from agent_ledger import CallLedger

if importlib.util.find_spec("improvement_trials"):
    import improvement_trials as IT
else:
    IT = None


class TrialStoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(IT, "Durable trials are not implemented")
        fixture = fixtures.ImprovementCaseTests()
        fixture.setUp()
        self.root, self.rs = fixture.root, fixture.rs
        self.assets, self.cases = fixture.assets, fixture.cases
        self.owner, self.other = fixture.owner, fixture.other
        case_set, _ = fixture.case_set()
        pins = fixture.pins(case_set)
        engine = {"version": 1, "provider": "anthropic-cli", "engine_id": "claude-sdk",
            "model": "claude-opus-5-5", "reasoning": "medium", "cli_path": "synthetic-unused-cli",
            "cli_hash": "a" * 64, "cli_version": "2.1.304", "sdk_version": "0.2.116",
            "profile_version": "fixture", "profile_hash": "b" * 64}
        pins["engine_config_hash"] = IM._hash(engine)
        targets = {target["id"]: target["generation"] for target in self.assets.targets(self.owner)}
        self.context = {"content": "Complete synthetic owner instructions",
                        "hash": fixtures.digest("Complete synthetic owner instructions"), "coverage": "complete"}
        self.request = {"version": 1, "pins": pins, "case_set_id": case_set["case_set_id"], "case_id": "case-1",
            "variant": "baseline", "repeat": 1, "engine_config": engine,
            "baseline_context_hash": IM._hash(self.context),
            "target_generations": targets, "deadline_at": time.time() + 300}
        self.trials = IT.TrialStore(self.assets)
        self.ledger = CallLedger(self.rs)

    def reserve(self, key="trial-reserve-0001", **changes):
        return self.trials.reserve(self.owner, {**copy.deepcopy(self.request), **changes}, event_key=key)

    def prepared(self):
        trial = self.reserve()
        claimed = self.trials.claim(self.owner, trial["trial_id"], expected_generation=1)
        manifest = self.trials.materialize(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
            lease_token=claimed["lease_token"], baseline_context=self.context)
        receipt = self.trials.workspace.prepare(trial["trial_id"], 1, manifest)
        prepared = self.trials.prepared(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
            lease_token=claimed["lease_token"], receipt=receipt)
        return prepared, claimed["lease_token"]

    def test_reservation_and_call_are_one_transaction_and_replay_does_not_duplicate(self):
        trial = self.reserve()
        self.assertEqual(trial, self.reserve())
        current = self.trials.get(self.owner, trial["trial_id"])
        self.assertEqual((current["status"], current["generation"], current["attempt"]), ("reserved", 1, 1))
        call = self.ledger.get(current["attempts"][0]["call_id"])
        self.assertEqual(call["purpose"], "improve_probe")
        self.assertEqual(call["context_ref"], "improvement:experiment-1")
        self.assertEqual(call["mirror_ref"], "improvement_trial:" + trial["trial_id"])
        with self.rs._conn() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM goals").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM agent_calls").fetchone()[0], 1)
        self.assertFalse((self.root / "team.sqlite3").exists())
        self.assertNotIn("private-answer", json.dumps(current))

    def test_simultaneous_logical_reservations_share_one_trial_and_call(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.reserve, ("parallel-trial-0001", "parallel-trial-0002")))
        self.assertEqual(results[0]["trial_id"], results[1]["trial_id"])
        with self.rs._conn() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM agent_calls").fetchone()[0], 1)

    def test_stale_policy_target_and_foreign_scope_cannot_reserve_or_read(self):
        for changes in ({"pins": {**self.request["pins"], "policy_version": 999}},
                        {"target_generations": {key: 999 for key in self.request["target_generations"]}},
                        {"pins": {**self.request["pins"], "engine_config_hash": "c" * 64}}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, IM.ConflictError)):
                self.reserve(**changes)
        trial = self.reserve()
        with self.assertRaises(PermissionError):
            self.trials.get(self.other, trial["trial_id"])

    def test_unsupported_provider_or_invalid_execution_identity_is_rejected_before_reservation(self):
        engine = {**self.request["engine_config"], "provider": "openai"}
        for index, changes in enumerate(({"engine_config": engine, "pins": {**self.request["pins"], "engine_config_hash": IM._hash(engine)}},
                                        {"pins": {**self.request["pins"], "experiment_id": "unscoped/experiment"}})):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.reserve("invalid-request-" + str(index), **changes)

    def test_boolean_generation_cannot_claim_and_exhausted_call_capacity_leaves_no_trial(self):
        trial = self.reserve()
        with self.assertRaises(IM.ConflictError):
            self.trials.claim(self.owner, trial["trial_id"], expected_generation=True)
        from unittest.mock import patch
        with patch.object(fixtures.RS, "_under_ceiling", return_value=False), self.assertRaises(IM.ConflictError):
            self.reserve("capacity-empty-trial", repeat=2)
        with self.rs._conn() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM improvement_trials").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM agent_calls").fetchone()[0], 1)

    def test_cancel_before_engine_refunds_and_invalidates_a_claimed_lease(self):
        trial = self.reserve()
        claimed = self.trials.claim(self.owner, trial["trial_id"], expected_generation=1)
        self.assertNotIn("lease_token", self.trials.get(self.owner, trial["trial_id"]))
        cancelled = self.trials.cancel(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
                                       event_key="trial-cancel-0001")
        self.assertEqual(cancelled["status"], "cancelled")
        current = self.trials.get(self.owner, trial["trial_id"])
        self.assertEqual(self.ledger.get(current["attempts"][0]["call_id"])["status"], "refunded")
        with self.assertRaises(IM.ConflictError):
            self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
                                     lease_token=claimed["lease_token"])

    def test_recovery_before_engine_refunds_without_creating_another_attempt(self):
        trial = self.reserve()
        self.trials.claim(self.owner, trial["trial_id"], expected_generation=1, now=100, lease_seconds=10)
        result = self.trials.recover(self.owner, now=111)
        self.assertEqual(result["not_run"], 1)
        current = self.trials.get(self.owner, trial["trial_id"])
        self.assertEqual((current["status"], len(current["attempts"])), ("not_run", 1))
        self.assertEqual(self.ledger.get(current["attempts"][0]["call_id"])["status"], "refunded")
        self.assertEqual(self.trials.recover(self.owner, now=112)["not_run"], 0)

    def test_engine_marker_and_trial_transition_rollback_together_then_cancel_is_counted(self):
        trial, token = self.prepared()
        with self.rs._conn() as connection:
            connection.execute("CREATE TRIGGER fail_trial_start BEFORE UPDATE ON improvement_trial_attempts "
                "WHEN NEW.status='running' BEGIN SELECT RAISE(ABORT,'injected_atomic_failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=trial["generation"], lease_token=token)
        call = trial["attempts"][0]["call_id"]
        self.assertIsNone(self.ledger.get(call)["engine_at"])
        self.assertEqual(self.trials.get(self.owner, trial["trial_id"])["status"], "prepared")
        with self.rs._conn() as connection:
            connection.execute("DROP TRIGGER fail_trial_start")
        running = self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=trial["generation"], lease_token=token)
        self.trials.cancel(self.owner, trial["trial_id"], expected_generation=running["generation"], event_key="cancel-after-engine")
        self.assertEqual(self.ledger.get(call)["status"], "interrupted")
        self.assertIsNotNone(self.ledger.get(call)["engine_at"])
        self.assertFalse(self.ledger.refund(call))

    def test_post_engine_recovery_is_unknown_and_keeps_the_same_attempt(self):
        trial, token = self.prepared()
        self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=trial["generation"], lease_token=token)
        recovered = self.trials.recover(self.owner, now=time.time() + 61)
        self.assertEqual(recovered["unknown"], 1)
        current = self.trials.get(self.owner, trial["trial_id"])
        self.assertEqual((current["status"], len(current["attempts"])), ("unknown", 1))
        self.assertEqual(self.ledger.get(current["attempts"][0]["call_id"])["status"], "interrupted")

    def test_policy_revocation_after_prepare_blocks_query_marker_but_allows_cancellation(self):
        trial, token = self.prepared()
        self.assets.set_policy(self.owner, "off", expected_version=0, event_key="off-after-prepare")
        with self.assertRaises(PermissionError):
            self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=trial["generation"], lease_token=token)
        self.trials.cancel(self.owner, trial["trial_id"], expected_generation=trial["generation"], event_key="cancel-revoked-trial")
        self.assertEqual(self.ledger.get(trial["attempts"][0]["call_id"])["status"], "refunded")

    def test_qualification_is_consumed_before_fixture_visibility_and_context_pin_is_complete(self):
        claim = self.cases.reserve_qualification(self.owner, self.request["case_set_id"], self.request["pins"],
                                                 event_key="qualification-for-trial")
        trial = self.reserve(case_id="case-2", qualification_id=claim["reservation_id"])
        claimed = self.trials.claim(self.owner, trial["trial_id"], expected_generation=1)
        with self.assertRaises(IM.ConflictError):
            self.trials.materialize(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
                lease_token=claimed["lease_token"], baseline_context={**self.context, "coverage": "unknown"})
        with self.rs._conn() as connection:
            self.assertEqual(connection.execute("SELECT status FROM improvement_qualification").fetchone()[0], "reserved")
        manifest = self.trials.materialize(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
            lease_token=claimed["lease_token"], baseline_context=self.context)
        with self.rs._conn() as connection:
            self.assertEqual(connection.execute("SELECT status FROM improvement_qualification").fetchone()[0], "consumed")
        self.assertEqual(manifest["learning_origin"], "qualification")
        self.assertNotIn("private-answer", json.dumps(manifest))
        self.assertNotIn("host-checker-v1", json.dumps(manifest))

    def test_forged_effective_hash_cannot_be_attested_by_changing_the_workspace_journal(self):
        trial = self.reserve()
        claimed = self.trials.claim(self.owner, trial["trial_id"], expected_generation=1)
        manifest = self.trials.materialize(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
            lease_token=claimed["lease_token"], baseline_context=self.context)
        receipt = self.trials.workspace.prepare(trial["trial_id"], 1, manifest)
        receipt["effective_hash"] = "f" * 64
        _, journal = self.trials.workspace._paths(trial["trial_id"], 1)
        record = json.loads(journal.read_text())
        record["receipt"] = receipt
        journal.write_text(IM._json(record))
        with self.assertRaises((ValueError, IM.ConflictError)):
            self.trials.prepared(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
                lease_token=claimed["lease_token"], receipt=receipt)
        self.assertIsNone(self.ledger.get(trial["attempts"][0]["call_id"])["engine_at"])

    def test_schema_two_metadata_reads_do_not_migrate_and_failed_upgrade_rolls_back(self):
        from unittest.mock import patch
        import improvement_trial_schema as schema
        self.assets.set_policy(self.owner, "off", expected_version=0, event_key="off-before-upgrade")
        with self.rs._conn() as connection:
            contract = connection.execute("SELECT id FROM improvement_contracts").fetchone()[0]
            for table in ("improvement_trial_observations", "improvement_trial_attempts", "improvement_trials"):
                connection.execute("DROP TABLE " + table)
            connection.execute("UPDATE improvement_schema SET version=2")
        self.assertEqual(self.cases.get_contract(self.owner, contract)["contract"]["version"], 1)
        with self.assertRaises(PermissionError):
            self.trials.get(self.owner, "missing-trial")
        self.assertEqual(IM._schema_version(self.rs), 2)
        with patch.object(schema, "SCHEMA", (*schema.SCHEMA, "INVALID TRIAL DDL")), self.assertRaises(sqlite3.OperationalError):
            IM.ensure(self.rs)
        self.assertEqual(IM._schema_version(self.rs), 2)
        with self.rs._conn() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='improvement_trials'").fetchone())
        IM.ensure(self.rs)
        self.assertEqual(IM._schema_version(self.rs), 3)
        self.assertEqual(self.assets.get_policy(self.owner), {"mode": "off", "version": 1})

    def test_preparation_requires_committed_exposure_before_the_input_can_be_used(self):
        trial = self.reserve()
        claimed = self.trials.claim(self.owner, trial["trial_id"], expected_generation=1)
        # Simulate a host bypassing the exposure transaction but obtaining the same bytes.
        with self.rs._conn() as connection:
            row = self.trials._row(connection, self.owner.brain_id, trial["trial_id"])
            manifest = self.trials._materialization(connection, row, self.context)
        receipt = self.trials.workspace.prepare(trial["trial_id"], 1, manifest)
        with self.assertRaises(IM.ConflictError):
            self.trials.prepared(self.owner, trial["trial_id"], expected_generation=claimed["generation"],
                lease_token=claimed["lease_token"], receipt=receipt)

    def test_waiting_for_database_cannot_authorize_a_query_after_the_lease_expires(self):
        trial, token = self.prepared()
        with self.rs._conn() as connection:
            expires = connection.execute("SELECT lease_until FROM improvement_trial_attempts").fetchone()[0]
        clock = [expires - 1]
        transaction = self.rs._Tx

        @contextmanager
        def delayed(store):
            with transaction(store) as connection:
                clock[0] = expires + 1
                yield connection

        with patch.object(self.rs, "_Tx", delayed), patch("time.time", side_effect=lambda: clock[0]):
            with self.assertRaises(IM.ConflictError):
                self.trials.start_engine(self.owner, trial["trial_id"], expected_generation=trial["generation"], lease_token=token)
        self.assertIsNone(self.ledger.get(trial["attempts"][0]["call_id"])["engine_at"])


if __name__ == "__main__":
    unittest.main()
