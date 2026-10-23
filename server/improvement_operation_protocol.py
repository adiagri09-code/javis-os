"""Closed host-issued role request metadata, never model or HTTP authority."""
from improvement_experiment_protocol import _freeze, _id, _digest

_FIELDS = {"version", "experiment_id", "context_id", "definition_hash", "kind", "role", "purpose",
           "candidate_id", "parent_id", "input_hash"}
_ROLES = {"propose": ("improver", "improve_propose"), "repair": ("improver", "improve_propose"),
          "semantic": ("semantic_reviewer", "improve_evaluate")}


def operation_request(value):
    value = _freeze(value)
    if type(value) is not dict or set(value) != _FIELDS:
        raise ValueError("invalid_operation_request")
    if (type(value["version"]) is not int or value["version"] != 1
            or type(value["kind"]) is not str or value["kind"] not in _ROLES
            or (value["role"], value["purpose"]) != _ROLES[value["kind"]]):
        raise ValueError("invalid_operation_role")
    for key in ("experiment_id", "context_id"):
        _id(value[key])
    for key in ("definition_hash", "input_hash"):
        _digest(value[key])
    for key, required in (("candidate_id", value["kind"] == "semantic"), ("parent_id", value["kind"] == "repair")):
        if required:
            _id(value[key])
        elif value[key] is not None:
            raise ValueError("invalid_operation_identity")
    return value
