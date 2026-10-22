"""Concrete owner-service dependencies; constructing them does not capture or query.

Only explicit write operations use this factory. Cold historical metadata routes
must use read_existing and their scoped readers, without warming these sources.
HTTP authorization, dispatch and lifespan registration are separate integration.
"""
from __future__ import annotations

import re
import sys
import types
from pathlib import Path

from evidence_store import redact
from improvement_assets import capture_source
from improvement_blobs import RevisionBlobs
from improvement_store import ImprovementStore
from improvement_trial_dashboard import DashboardContextCapture
from improvement_trial_file_sources import BrainFileFixtures, _root as owner_root
from improvement_trial_host import HostContextStore, TARGET_FIELDS
from improvement_trial_plugins import PluginCapabilityProjection
from improvement_trial_selection import create_pin, resolve_sdk_cli
from improvement_trial_sql_context import ExistingSQLiteSource, SQLiteContextProjection
from resonance_store import GoalStore, Principal

_SERVER = Path(__file__).resolve().parent
_SELECTION_FIELDS = {"source_ref", "timezone", "data_period", "cutoff", "schema"}
_SKILL = re.compile(r"skills/([a-z0-9][a-z0-9_-]{0,127})/SKILL\.md\Z")


class _RetainedDashboard:
    """Observe only while the captured sources are still the ordinary sources.

    Per-store SQL locks protect reads; these checks reject a singleton/member
    replacement before or during collection instead of switching authority.
    """
    def __init__(self, collector, check):
        self._collector, self._check = collector, check

    def __call__(self, *args):
        self._check()
        result = self._collector(*args)
        self._check()
        return result

    def revalidate(self, *args, frozen_capture):
        self._check()
        result = self._collector.revalidate(*args, frozen_capture=frozen_capture)
        self._check()
        return result


def _fixtures(selections):
    if selections is None:
        return BrainFileFixtures()
    if type(selections) is not list or not 1 <= len(selections) <= 1000:
        raise ValueError("invalid_trial_source_selections")
    mapping = {}
    for selection in selections:
        if (type(selection) is not dict or set(selection) != _SELECTION_FIELDS
                or type(selection["source_ref"]) is not str or selection["source_ref"] in mapping):
            raise ValueError("invalid_trial_source_selections")
        mapping[selection["source_ref"]] = {
            **{key: selection[key] for key in _SELECTION_FIELDS - {"source_ref"}},
            "freshness_policy": "require_current_version"}
    return BrainFileFixtures(mapping)


def dashboard_host(main, assets, *, source_selections=None):
    """Compose actual initialized production sources and strict host-only callbacks.

    No store constructor, mutable CLI finder, config reader, live prompt builder,
    native authentication or query executes here. Source observations happen only
    when the caller explicitly creates/guards a context through the returned host.
    """
    if (type(main) is not types.ModuleType or sys.modules.get("main") is not main
            or Path(main.__file__).resolve() != _SERVER / "main.py"
            or type(assets) is not ImprovementStore or type(assets.store) is not GoalStore
            or type(assets.blobs) is not RevisionBlobs):
        raise TypeError("concrete_trial_service_dependencies_required")
    for name, module in (("sessions", main.sessions), ("config", main.cfgmod),
                         ("workflow_runs", sys.modules.get("workflow_runs"))):
        if (type(module) is not types.ModuleType or sys.modules.get(name) is not module
                or Path(module.__file__).resolve() != _SERVER / (name + ".py")):
            raise TypeError("concrete_trial_service_dependencies_required")
    state = Path(main.cfgmod.STATE_DIR)
    if (not state.is_absolute() or Path(assets.store.path) != state / "resonance.sqlite3"
            or assets.blobs.root != state / "improvement" or main.cfgmod.SETTINGS_PATH != state / "settings.json"):
        raise ValueError("trial_service_store_mismatch")
    workflow_module = sys.modules.get("workflow_runs")
    cli, sdk, packs = (sys.modules.get(name) for name in ("claude_cli", "claude_sdk_engine", "packs"))
    sessions = main.sessions
    session_store = getattr(sessions, "_store", None)
    workflow_store = getattr(workflow_module, "_STORE", None)
    if (session_store is None or type(session_store) is not sessions.SessionStore
            or workflow_store is None or type(workflow_store) is not workflow_module.WorkflowRunStore
            or any(type(module) is not types.ModuleType for module in (cli, sdk, packs))):
        raise ValueError("trial_service_source_lifetime_unavailable")
    session_path, workflow_path = Path(session_store.db_path), Path(workflow_store.path)
    sql = SQLiteContextProjection(session_path, workflow_path, existing_sources={
        session_path: ExistingSQLiteSource(session_path, session_store._conn, session_store._lock),
        workflow_path: ExistingSQLiteSource(workflow_path, workflow_store._db, workflow_store._lock)},
        principal_type=Principal, redactor=redact)
    plugins = PluginCapabilityProjection(host=main.plugins_host, packs_host=packs, redactor=redact)
    collector = DashboardContextCapture(host=main, sql=sql, plugins=plugins,
        project_root=main.CLAUDE_MD_PATH.parent, state_root=state, native_user_root=Path.home() / ".claude")
    identities = ((main, "sessions", sessions), (main, "cfgmod", main.cfgmod),
                  (sessions, "_store", session_store), (workflow_module, "_STORE", workflow_store),
                  (session_store, "_conn", session_store._conn), (session_store, "_lock", session_store._lock),
                  (workflow_store, "_db", workflow_store._db), (workflow_store, "_lock", workflow_store._lock),
                  (assets, "store", assets.store), (assets, "blobs", assets.blobs))
    modules = {module.__name__: module for module in
               (main, sessions, main.cfgmod, workflow_module, cli, sdk, packs)}

    def current_sources():
        try:
            if (any(sys.modules.get(name) is not module for name, module in modules.items())
                    or any(getattr(obj, name, None) is not value for obj, name, value in identities)
                    or Path(session_store.db_path) != session_path or Path(workflow_store.path) != workflow_path
                    or Path(main.cfgmod.STATE_DIR) != state or main.cfgmod.SETTINGS_PATH != state / "settings.json"
                    or Path(assets.store.path) != state / "resonance.sqlite3"
                    or assets.blobs.root != state / "improvement"):
                raise ValueError("trial_service_source_lifetime_changed")
        except (AttributeError, TypeError, OSError):
            raise ValueError("trial_service_source_lifetime_changed") from None

    def selected_engine():
        current_sources()
        pin = create_pin(main.cfgmod.SETTINGS_PATH, resolve_sdk_cli(cli, sdk, state))
        current_sources()
        return pin

    def targets(principal, identifiers):
        current_sources()
        root = owner_root(principal)
        if (type(identifiers) is not list or not 1 <= len(identifiers) <= 20
                or any(type(identifier) is not str for identifier in identifiers)
                or len(set(identifiers)) != len(identifiers)):
            raise ValueError("invalid_trial_target_selection")
        rows = {row["id"]: row for row in assets.targets(principal)}
        result = []
        for identifier in identifiers:
            row = rows.get(identifier)
            match = _SKILL.fullmatch(row["canonical_ref"]) if row is not None else None
            if (row is None or row["status"] != "live" or row["kind"] != "skill" or match is None
                    or row["ownership"] not in ("user_protected", "user_managed")):
                raise PermissionError("trial_target_unavailable")
            source, _ = capture_source(root, "skill", match.group(1), pack_state_dir=state / "packs-state")
            observed = {key: row[key] for key in TARGET_FIELDS}
            for key in ("kind", "canonical_ref", "identity", "source_hash", "protected_hash", "ownership"):
                observed[key] = getattr(source, key)
            result.append(observed)
        current_sources()
        return sorted(result, key=lambda item: item["id"])

    current_sources()
    return HostContextStore(assets, context_capture=_RetainedDashboard(collector, current_sources), selected_engine=selected_engine,
                            target_observer=targets, fixture_observer=_fixtures(source_selections))
