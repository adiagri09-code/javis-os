"""Read-only Team usage views over the existing usage event/index pipeline.

Team turns and agent calls are execution references, never additional bills. A CLI total
remains partial until explicitly linked request detail reconciles its token counts.
"""
from __future__ import annotations

from collections import defaultdict
import sqlite3

import usage_index
import usage_store


def _execution_references(team_id, task_id=None):
    """Execution stores supply missing-telemetry evidence only; no tokens or costs are read."""
    refs, sources, errors = {}, [], 0
    root = usage_store._PATH.parent
    for name in ("team.sqlite3", "resonance.sqlite3"):
        path = root / name
        if not path.is_file():
            continue
        conn = None
        try:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
            if name == "team.sqlite3":
                where, args = "team_id=? AND engine_at IS NOT NULL", [team_id]
                if task_id is not None:
                    where += " AND task_id=?"
                    args.append(task_id)
                for turn, role in conn.execute("SELECT turn_id,role FROM team_turns WHERE " + where, args):
                    refs[turn] = {"role": role, "shared": False}
            elif task_id is None:
                for cid, purpose, reason, mirror, attempt in conn.execute(
                        "SELECT id,purpose,reason_ref,mirror_ref,attempt FROM agent_calls "
                        "WHERE context_ref=? AND engine_at IS NOT NULL", ("team:" + team_id,)):
                    key = mirror.split(":", 1)[1] if str(mirror).startswith("team_turn:") else reason
                    # A mirror is the same execution as team_turns. Attempts with a reason
                    # reused after an error remain distinct references until linked explicitly.
                    if not mirror and key in refs:
                        key = "call:" + str(cid)
                    refs.setdefault(key, {"role": purpose, "shared": not bool(mirror), "attempt": attempt})
            sources.append(name)
        except (OSError, sqlite3.Error):
            errors += 1
        finally:
            if conn is not None:
                conn.close()
    return refs, sources, errors


def _reconcile_executions(result, events, team_id, task_id=None):
    refs, sources, errors = _execution_references(team_id, task_id)
    observed = {e.get("execution", {}).get("turn_id") for e in events}
    missing = {key: value for key, value in refs.items() if key not in observed}
    coverage = result["coverage"]
    coverage.update(execution_sources=sources, execution_reference_errors=errors,
                    unobserved_by_role=dict(_counts(v["role"] or "unknown" for v in missing.values())),
                    unscoped_background="cross_context_review_not_allocated")
    coverage["unobserved_attempts"] += len(missing)
    result["attempts"] += len(missing)
    if missing or errors:
        coverage.update(status="partial", tokens_complete=False, money_complete=False, requests_complete=False)
        result["requests"] = None
    if task_id is None and "shared" in result:
        shared_missing = sum(bool(v["shared"]) for v in missing.values())
        result["shared"]["attempts"] += shared_missing
        result["shared"]["coverage"]["unobserved_attempts"] += shared_missing
        if shared_missing:
            result["shared"]["coverage"].update(status="partial", tokens_complete=False, money_complete=False,
                                                 requests_complete=False)
            result["shared"]["requests"] = None


def _counts(values):
    result = defaultdict(int)
    for value in values:
        result[value] += 1
    return result


def _attempt_key(event):
    ex = event.get("execution") or {}
    return (ex.get("execution_id") or ex.get("turn_id") or event.get("event_id"), ex.get("attempt"))


def _money(events):
    result = {"currency": "USD", "reported_usd": None, "estimated_usd": None,
              "subscription_equivalent_usd": None, "unknown_requests": 0,
              "subscription_requests": 0, "local_requests": 0}
    keys = {"provider_reported": "reported_usd", "estimated": "estimated_usd",
            "subscription_equivalent": "subscription_equivalent_usd"}
    for event in events:
        money = event.get("money") or {}
        key = keys.get(money.get("provenance"))
        amount = money.get("amount")
        if money.get("billing_mode") == "subscription":
            result["subscription_requests"] += 1
        if money.get("billing_mode") == "local":
            result["local_requests"] += 1
        if key and amount is not None and money.get("currency") == "USD":
            result[key] = round((result[key] or 0) + amount, 8)
        elif money.get("provenance") != "local":
            result["unknown_requests"] += 1
    return result


def _aggregate(events, details=(), telemetry_errors=0):
    groups = defaultdict(list)
    for event in events:
        groups[_attempt_key(event)].append(event)
    observed = []
    money_events = []
    unresolved = missing = missing_requests = persisted_errors = 0
    request_count = 0
    requests_complete = True
    statuses = defaultdict(int)
    for group in groups.values():
        lifecycle = [e for e in group if e.get("event_kind") == "execution"]
        fallback = [e for e in group if e.get("event_kind") == "cli_fallback"]
        requests = [e for e in group if e.get("event_kind") in ("request", "cli_detail")]
        expected = max((e.get("expected_requests") or 0 for e in lifecycle), default=0)
        persisted_errors += max((e.get("telemetry_errors") or 0 for e in group), default=0)
        if expected > len(requests):
            missing_requests += expected - len(requests)
            requests_complete = False
        for event in lifecycle + fallback:
            statuses[event.get("status") or "unknown"] += 1
        if fallback:
            # A new CLI session is safely attributable only to one host execution. Resumed
            # sessions have no request boundary, so their raw records stay unresolved.
            latest = fallback[-1]
            ex = latest.get("execution") or {}
            sid = ex.get("cli_session_id")
            same_session = {_attempt_key(e) for e in events
                            if e.get("execution", {}).get("cli_session_id") == sid}
            raw = [d for d in details if d.get("session_id") == sid] if (
                sid and ex.get("cli_session_new") and len(same_session) == 1) else []
            for d in raw:
                requests.append({"event_kind": "cli_detail", "execution": ex,
                                 "provider": latest.get("provider"), "request_id": d.get("request_id"),
                                 "in": d["input"] + d["cache_read"] + d["cache_create"],
                                 "out": d["output"], "tokens_known": True})
            # SDK observations and later CLI records can describe the same provider request.
            # Raw detail supersedes its earlier observation; never infer identity from totals.
            identified, anonymous = {}, []
            for request in requests:
                if request.get("request_id"):
                    key = (request.get("provider"), (request.get("execution") or {}).get("cli_session_id") or sid,
                           request["request_id"])
                    identified[key] = request
                else:
                    anonymous.append(request)
            requests = anonymous + list(identified.values())
            known = [e for e in requests if e.get("tokens_known")]
            reconciled = bool(known) and latest.get("tokens_known") and (
                sum(e.get("in") or 0 for e in known) == latest.get("in") and
                sum(e.get("out") or 0 for e in known) == latest.get("out"))
            if reconciled:
                observed.extend(known)
                request_count += len(known)
                # Provider summary owns its API-equivalent amount. Detail replaces tokens
                # and request count, never adds the same monetary observation again.
                money_events.append(latest)
            else:
                observed.append(latest)
                money_events.append(latest)
                requests_complete = False
                unresolved += len(requests)
                if not latest.get("tokens_known"):
                    missing += 1
        elif requests:
            observed.extend(requests)
            money_events.extend(requests)
            request_count += len(requests)
        else:
            missing += 1
            requests_complete = False
    known = [e for e in observed if e.get("tokens_known")]
    telemetry_errors = max(telemetry_errors, persisted_errors)
    tokens_complete = len(known) == len(observed) and missing == 0 and missing_requests == 0
    money = _money(money_events)
    coverage = {"status": "observed" if events and tokens_complete and requests_complete and not telemetry_errors
                and not money["unknown_requests"] else
                "partial" if events else "unknown", "observed_requests": request_count,
                "unobserved_attempts": missing, "unresolved_events": unresolved,
                "missing_requests": missing_requests,
                "telemetry_errors": telemetry_errors, "tokens_complete": bool(events) and tokens_complete,
                "money_complete": bool(events) and not missing and not missing_requests
                                  and money["unknown_requests"] == 0 and not telemetry_errors,
                "requests_complete": bool(events) and requests_complete,
                "scope": "instrumented_executions", "cli_detail": "linked_and_reconciled_only"}
    return {"attempts": len(groups), "requests": request_count if requests_complete and events else None,
            "tokens_in": sum(e["in"] for e in observed if e.get("in") is not None)
                         if any(e.get("in") is not None for e in observed) else None,
            "tokens_out": sum(e["out"] for e in observed if e.get("out") is not None)
                          if any(e.get("out") is not None for e in observed) else None,
            "money": money, "coverage": coverage, "statuses": dict(statuses), "cost_behavior": "observe_only"}


def _view(team_id, task_id=None):
    try:
        events, details = usage_index.execution_events(team_id, task_id)
        result = _aggregate(events, details, usage_store.telemetry_errors(team_id, task_id))
        roles = defaultdict(list)
        for e in events:
            roles[e.get("execution", {}).get("role") or "unresolved"].append(e)
        result["roles"] = {role: _aggregate(rows, details) for role, rows in sorted(roles.items())}
        if task_id is None:
            result["shared"] = _aggregate([e for e in events if not e.get("execution", {}).get("task_id")], details)
        _reconcile_executions(result, events, team_id, task_id)
        result.update(team_id=team_id, task_id=task_id)
        return result
    except Exception:
        result = _aggregate([], telemetry_errors=1)
        result.update(team_id=team_id, task_id=task_id, roles={})
        if task_id is None:
            result["shared"] = _aggregate([])
        return result


def task_usage(team_id, task_id) -> dict:
    return _view(team_id, task_id)


def team_usage(team_id) -> dict:
    return _view(team_id)
