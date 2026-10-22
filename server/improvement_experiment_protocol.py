"""Closed immutable experiment data; no host, trial, case-store or engine imports."""
from __future__ import annotations

import re

from improvement_store import _json

_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}")
_HASH = re.compile(r"[0-9a-f]{64}")
_DEFINITION = {"version", "experiment_id", "context_id", "target_id", "base_revision_id", "base_hash", "base_generation",
    "base_bundle_id", "base_bundle_hash", "contract_id", "contract_hash", "case_set_id", "case_set_hash",
    "baseline_context_hash", "binding_hash", "engine_config_hash", "grant_hash", "scope_hash", "policy_version",
    "context_generation", "repeat_policy", "timeout_seconds", "endpoint", "decision_policy", "evaluator", "evidence_class"}


def _fields(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise ValueError("invalid_experiment_definition")


def definition(value):
    """Validate metadata shape only; it is not live source or execution authority."""
    import json
    value = json.loads(_json(value))
    _fields(value, _DEFINITION)
    if type(value["version"]) is not int or value["version"] != 1 or value["evidence_class"] != "technical":
        raise ValueError("unsupported_experiment_definition")
    for name in ("experiment_id", "context_id", "target_id", "base_revision_id", "base_bundle_id", "contract_id", "case_set_id"):
        if type(value[name]) is not str or not _ID.fullmatch(value[name]):
            raise ValueError("invalid_experiment_definition")
    for name in ("base_hash", "base_bundle_hash", "contract_hash", "case_set_hash", "baseline_context_hash", "binding_hash",
                 "engine_config_hash", "grant_hash", "scope_hash"):
        if type(value[name]) is not str or not _HASH.fullmatch(value[name]):
            raise ValueError("invalid_experiment_definition")
    for name, minimum in (("base_generation", 1), ("context_generation", 1), ("policy_version", 0)):
        if type(value[name]) is not int or not minimum <= value[name] < 2 ** 63:
            raise ValueError("invalid_experiment_generation")
    repeat = value["repeat_policy"]
    _fields(repeat, {"kind", "repeats"})
    if (type(repeat["kind"]) is not str or repeat["kind"] not in {"feasibility", "pilot"}
            or type(repeat["repeats"]) is not int or repeat["repeats"] != (1 if repeat["kind"] == "feasibility" else 2)):
        raise ValueError("unsupported_experiment_repeat_policy")
    if type(value["timeout_seconds"]) is not int or not 1 <= value["timeout_seconds"] <= 300:
        raise ValueError("invalid_experiment_timeout")
    endpoint = value["endpoint"]
    _fields(endpoint, {"kind", "criterion_id", "direction"})
    if (endpoint["kind"] != "binary_all_pass" or endpoint["direction"] != "higher"
            or type(endpoint["criterion_id"]) is not str or not _ID.fullmatch(endpoint["criterion_id"])):
        raise ValueError("unsupported_experiment_endpoint")
    policy = value["decision_policy"]
    _fields(policy, {"id", "version", "multiple_tests"})
    if (policy["id"] != "paired-skill-v1" or type(policy["version"]) is not int or policy["version"] != 1
            or type(policy["multiple_tests"]) is not int or not 1 <= policy["multiple_tests"] <= 1000):
        raise ValueError("unsupported_experiment_decision_policy")
    evaluator = value["evaluator"]
    _fields(evaluator, {"id", "version", "hash"})
    if (any(type(evaluator[key]) is not str or not 1 <= len(evaluator[key]) <= 128 for key in ("id", "version"))
            or type(evaluator["hash"]) is not str or not _HASH.fullmatch(evaluator["hash"])):
        raise ValueError("invalid_experiment_evaluator")
    if len(_json(value).encode("utf-8")) > 16384:
        raise ValueError("experiment_definition_too_large")
    return value
