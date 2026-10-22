"""Encrypted host context and revocable source authority, never asserted by trial JSON."""
from __future__ import annotations

import hashlib
import inspect
import json
import secrets
import time
from contextlib import closing

import improvement_cases as IC
import improvement_store as IM
from evidence_store import redact
from improvement_blobs import MAX_ASSET_BYTES, AssetUnavailable
from improvement_claude import ClaudeTrialAdapter
from resonance_store import Principal

MAX_BINDING_BYTES = 8 * MAX_ASSET_BYTES
TARGET_FIELDS = ("id", "generation", "kind", "canonical_ref", "identity", "source_hash", "protected_hash", "ownership")


def _brain(principal):
    if not isinstance(principal, Principal):
        raise PermissionError("owner_required")
    return IM._brain(principal)


def _capture(value):
    capture = IC._frozen(value)
    IC._fields(capture, {"version", "surface", "plan_hash", "sources", "baseline_context"})
    if type(capture["version"]) is not int or capture["version"] != 1 or not isinstance(capture["surface"], dict) or not capture["surface"]:
        raise ValueError("invalid_host_context")
    IC._digest(capture["plan_hash"])
    context = capture["baseline_context"]
    IC._fields(context, {"content", "hash", "coverage"})
    if (not isinstance(context["content"], str) or not context["content"].strip()
            or len(context["content"].encode("utf-8")) > MAX_ASSET_BYTES
            or context["hash"] != hashlib.sha256(context["content"].encode("utf-8")).hexdigest()):
        raise ValueError("invalid_host_context")
    if context["coverage"] != "complete":
        raise PermissionError("trial_context_incomplete")
    sources = capture["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 1000:
        raise ValueError("invalid_host_context_sources")
    refs = set()
    for source in sources:
        IC._fields(source, {"ref", "root", "relative", "required", "present", "identity", "hash"})
        IC._text(source["ref"], 256)
        IC._text(source["root"], 4000)
        IC.output_path(source["relative"])
        if source["ref"] in refs or type(source["required"]) is not bool or type(source["present"]) is not bool:
            raise ValueError("invalid_host_context_sources")
        refs.add(source["ref"])
        if source["present"]:
            IC._digest(source["hash"])
            IC._digest(source["identity"])
        elif source["required"] or source["hash"] is not None or source["identity"] is not None:
            raise ValueError("invalid_host_context_sources")
    if redact(capture) != capture:
        raise ValueError("insufficient_source: trial_input_contains_credentials")
    return capture


class HostContextStore:
    def __init__(self, assets, *, context_capture, selected_engine, target_observer, fixture_observer):
        for callback in (context_capture, selected_engine, target_observer, fixture_observer):
            if (not callable(callback) or inspect.iscoroutinefunction(callback)
                    or inspect.iscoroutinefunction(getattr(callback, "__call__", None))):
                raise ValueError("host_trial_dependencies_required")
        self.assets, self.store, self.blobs = assets, assets.store, assets.blobs
        self.context_capture, self.selected_engine, self.target_observer = context_capture, selected_engine, target_observer
        self.fixture_observer = fixture_observer

    @staticmethod
    def _row(connection, brain, experiment):
        row = connection.execute("SELECT * FROM improvement_trial_contexts WHERE brain_id=? AND experiment_id=?",
                                 (brain, experiment)).fetchone()
        if row is None:
            raise PermissionError("trial_context_unavailable")
        return row

    @staticmethod
    def _grant(connection, row):
        grant = connection.execute("SELECT * FROM improvement_trial_context_grants WHERE context_id=? AND brain_id=?",
                                   (row["id"], row["brain_id"])).fetchone()
        if grant is None:
            raise PermissionError("trial_context_unavailable")
        return grant

    def _decode(self, row):
        try:
            hashes = json.loads(row["blob_hashes_json"])
            if not isinstance(hashes, list) or not 1 <= len(hashes) <= MAX_BINDING_BYTES // MAX_ASSET_BYTES:
                raise AssetUnavailable("invalid_trial_context_chunks")
            raw = b"".join(self.blobs.read(row["brain_id"], digest) for digest in hashes)
            if len(raw) > MAX_BINDING_BYTES or hashlib.sha256(raw).hexdigest() != row["binding_hash"]:
                raise AssetUnavailable("trial_context_hash_mismatch")
            binding = json.loads(raw)
            if (IM._hash(binding["capture"]["baseline_context"]) != row["context_hash"]
                    or IM._hash(binding["engine_config"]) != row["engine_config_hash"]
                    or IM._hash(binding["grant"]) != row["grant_hash"]
                    or IM._hash(binding["scope"]) != row["scope_hash"]):
                raise AssetUnavailable("trial_context_reference_mismatch")
            return binding
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise AssetUnavailable("trial_context_unavailable") from error

    def _public(self, connection, row):
        grant, binding = self._grant(connection, row), self._decode(row)
        return {"context_id": row["id"], "experiment_id": row["experiment_id"],
                "baseline_context_hash": row["context_hash"], "scope_hash": row["scope_hash"], "grant_hash": row["grant_hash"],
                "engine_config_hash": row["engine_config_hash"], "engine_config": binding["engine_config"],
                "target_generations": json.loads(row["target_generations_json"]), "policy_version": row["policy_version"],
                "grant_status": grant["status"], "generation": grant["generation"]}

    def get(self, principal, experiment_id):
        brain = _brain(principal)
        if IM._schema_version(self.store) < 3:
            raise PermissionError("trial_context_unavailable")
        with closing(self.store._conn()) as connection:
            return self._public(connection, self._row(connection, brain, experiment_id))

    def _targets(self, connection, brain, identifiers):
        targets = []
        for identifier in identifiers:
            row = self.assets._target(connection, brain, identifier)
            if row["status"] != "live" or row["ownership"] not in {"user_protected", "user_managed"}:
                raise IM.ConflictError("trial_live_target_changed")
            targets.append({key: row[key] for key in TARGET_FIELDS})
        return targets

    def _existing(self, connection, principal, payload):
        row = connection.execute("SELECT * FROM improvement_trial_contexts WHERE brain_id=? AND experiment_id=?",
                                 (_brain(principal), payload["experiment_id"])).fetchone()
        if row is not None:
            if row["request_hash"] != IM._hash(payload):
                raise IM.ConflictError("trial_context_identity_conflict")
            return self._public(connection, row)
        return None

    def _observe(self, principal, surface, expected_targets, source_refs, frozen_inventory=None):
        from improvement_trial_sources import validate_inventory
        identifiers = [target["id"] for target in expected_targets]
        targets = IC._frozen(self.target_observer(principal, identifiers))
        if not isinstance(targets, list) or len(targets) != len(expected_targets):
            raise IM.ConflictError("trial_live_target_changed")
        for target in targets:
            IC._fields(target, TARGET_FIELDS)
        targets.sort(key=lambda item: item["id"])
        if targets != expected_targets:
            raise IM.ConflictError("trial_live_target_changed")
        engine = IC._frozen(self.selected_engine())
        ClaudeTrialAdapter(engine)  # Shape only; no subprocess, authentication or inference.
        if engine["provider"] != "anthropic-cli" or engine["engine_id"] != "claude-sdk":
            raise ValueError("unsupported_trial_configuration")
        capture = _capture(self.context_capture(principal, IC._frozen(surface), IC._frozen(targets)))
        inventory = validate_inventory(self.fixture_observer(principal, list(source_refs),
            frozen_inventory=IC._frozen(frozen_inventory) if frozen_inventory is not None else None))
        if {entry["source_ref"] for entry in inventory} != set(source_refs):
            raise PermissionError("trial_fixture_scope_unavailable")
        fixture_hashes = {entry[key] for entry in inventory for key in ("source_hash", "fixture_hash")}
        if any(source["hash"] in fixture_hashes for source in capture["sources"] if source["present"]):
            raise ValueError("trial_case_context_overlap")
        if frozen_inventory is not None and inventory != frozen_inventory:
            raise IM.ConflictError("trial_fixture_permission_changed")
        # A target body belongs in the variant bundle, never the immutable common baseline.
        if any(source["relative"] in {target["canonical_ref"] for target in targets} for source in capture["sources"]):
            raise ValueError("trial_target_context_overlap")
        if (IC._frozen(self.target_observer(principal, identifiers)) != targets
                or IC._frozen(self.selected_engine()) != engine):
            raise IM.ConflictError("trial_host_authority_changed")
        return {"capture": capture, "engine_config": engine, "targets": targets, "fixture_inventory": inventory}

    def create(self, principal, experiment_id, surface, target_ids, *, source_refs, event_key):
        brain = _brain(principal)
        if (not isinstance(experiment_id, str) or not IC._ID.fullmatch(experiment_id)
                or not isinstance(surface, dict) or not surface or not isinstance(target_ids, list)
                or not 1 <= len(target_ids) <= 100 or any(not isinstance(item, str) or not IC._ID.fullmatch(item) for item in target_ids)
                or len(set(target_ids)) != len(target_ids) or not isinstance(source_refs, list)
                or not 1 <= len(source_refs) <= 1000
                or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 256 for ref in source_refs)
                or len(set(source_refs)) != len(source_refs)):
            raise ValueError("invalid_host_context_request")
        payload = IC._frozen({"experiment_id": experiment_id, "surface": surface, "target_ids": sorted(target_ids), "source_refs": sorted(source_refs)})
        IM.ensure(self.store)
        with self.store._Tx(self.store) as connection:
            replay = self.assets._replay(connection, brain, event_key, "trial_context_create", payload)
            if replay is not None:
                return replay
            existing = self._existing(connection, principal, payload)
            if existing is not None:
                self.assets._event(connection, principal, event_key, "trial_context_create", payload, existing)
                return existing
            policy = self.assets._policy(connection, brain)
            if policy["mode"] == "off":
                raise PermissionError("improvement_disabled")
            targets = self._targets(connection, brain, payload["target_ids"])
        observed = self._observe(principal, payload["surface"], targets, payload["source_refs"])
        capture = observed["capture"]
        with self.store._Tx(self.store) as connection:
            replay = self.assets._replay(connection, brain, event_key, "trial_context_create", payload)
            if replay is not None:
                return replay
            existing = self._existing(connection, principal, payload)
            if existing is not None:
                self.assets._event(connection, principal, event_key, "trial_context_create", payload, existing)
                return existing
            current_policy = self.assets._policy(connection, brain)
            if current_policy["mode"] == "off":
                raise PermissionError("improvement_disabled")
            if current_policy != policy or self._targets(connection, brain, payload["target_ids"]) != targets:
                raise IM.ConflictError("trial_host_authority_changed")
            if self._observe(principal, capture["surface"], targets, payload["source_refs"], observed["fixture_inventory"]) != observed:
                raise IM.ConflictError("trial_host_authority_changed")
            scope = {"version": 1, "brain_id": brain, "experiment_id": experiment_id, "surface": capture["surface"],
                     "target_ids": payload["target_ids"], "source_plan_hash": capture["plan_hash"], "source_refs": payload["source_refs"]}
            grant = {"version": 1, "scope_hash": IM._hash(scope), "sources": capture["sources"], "targets": targets,
                     "engine_config_hash": IM._hash(observed["engine_config"]), "baseline_context_hash": IM._hash(capture["baseline_context"]),
                     "policy_version": policy["version"], "actor": principal.by, "fixture_inventory": observed["fixture_inventory"]}
            binding = {**observed, "scope": scope, "grant": grant}
            raw = IM._json(binding).encode("utf-8")
            if len(raw) > MAX_BINDING_BYTES:
                raise ValueError("insufficient_source: trial_context_too_large")
            hashes = [self.blobs.write(brain, raw[offset:offset + MAX_ASSET_BYTES]) for offset in range(0, len(raw), MAX_ASSET_BYTES)]
            identifier = "ic_" + secrets.token_hex(12)
            generations = {item["id"]: item["generation"] for item in targets}
            connection.execute("INSERT INTO improvement_trial_contexts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (identifier, brain, experiment_id, IM._hash(payload), IM._hash(capture["baseline_context"]),
                 hashlib.sha256(raw).hexdigest(), IM._json(hashes), IM._hash(scope), IM._hash(grant),
                 IM._hash(observed["engine_config"]), policy["version"], IM._json(generations), time.time()))
            connection.execute("INSERT INTO improvement_trial_context_grants VALUES(?,?,1,'active',NULL)", (identifier, brain))
            result = self._public(connection, self._row(connection, brain, experiment_id))
            self.assets._event(connection, principal, event_key, "trial_context_create", payload, result)
            return result

    def _bound(self, connection, principal, request):
        brain = _brain(principal)
        row = self._row(connection, brain, request["pins"]["experiment_id"])
        if self._grant(connection, row)["status"] != "active":
            raise PermissionError("trial_source_grant_revoked")
        policy = self.assets._policy(connection, brain)
        if policy["mode"] == "off":
            raise PermissionError("improvement_disabled")
        binding = self._decode(row)
        if (any(request["pins"][key] != row[key] for key in ("scope_hash", "grant_hash", "engine_config_hash", "policy_version"))
                or request["baseline_context_hash"] != row["context_hash"] or policy["version"] != row["policy_version"]
                or request["target_generations"] != json.loads(row["target_generations_json"])
                or self._targets(connection, brain, sorted(request["target_generations"])) != binding["targets"]
                or request["engine_config"] != binding["engine_config"]):
            raise IM.ConflictError("trial_host_binding_drift")
        from improvement_trial_sources import authorize_case
        authorize_case(connection, brain, request, binding["fixture_inventory"], blobs=self.blobs)
        return row, binding

    def context_loader(self, principal, request):
        request = IC._frozen(request)
        with closing(self.store._conn()) as connection:
            _, binding = self._bound(connection, principal, request)
            return binding["capture"]["baseline_context"]

    def live_guard(self, principal, request):
        request = IC._frozen(request)
        with closing(self.store._conn()) as connection:
            row, binding = self._bound(connection, principal, request)
            targets = self._targets(connection, row["brain_id"], sorted(request["target_generations"]))
        if targets != binding["targets"] or self._observe(principal, binding["capture"]["surface"], targets,
                binding["scope"]["source_refs"], binding["fixture_inventory"]) != {
                key: binding[key] for key in ("capture", "engine_config", "targets", "fixture_inventory")}:
            raise IM.ConflictError("trial_host_authority_changed")
        # Recheck revocation/policy after potentially slow source/config I/O.
        with closing(self.store._conn()) as connection:
            self._bound(connection, principal, request)
        return {**{key: row[key] for key in ("scope_hash", "grant_hash", "engine_config_hash")},
                "baseline_context_hash": row["context_hash"], "target_generations": request["target_generations"]}

    def revoke(self, principal, experiment_id, *, expected_generation, event_key):
        brain = _brain(principal)
        if IM._schema_version(self.store) < 3:
            raise PermissionError("trial_context_unavailable")
        payload = {"experiment_id": experiment_id, "expected_generation": expected_generation}
        with self.store._Tx(self.store) as connection:
            replay = self.assets._replay(connection, brain, event_key, "trial_context_revoke", payload)
            if replay is not None:
                return replay
            row = self._row(connection, brain, experiment_id)
            grant = self._grant(connection, row)
            if type(expected_generation) is not int or grant["generation"] != expected_generation or grant["status"] != "active":
                raise IM.ConflictError("trial_context_grant_stale")
            connection.execute("UPDATE improvement_trial_context_grants SET status='revoked',generation=generation+1,revoked_at=? WHERE context_id=?",
                               (time.time(), row["id"]))
            result = self._public(connection, row)
            self.assets._event(connection, principal, event_key, "trial_context_revoke", payload, result)
            return result
