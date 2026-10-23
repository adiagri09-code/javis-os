"""Pure complete baseline preparation schedule; no candidate or execution grant."""
from improvement_experiment_protocol import definition, _id
from improvement_store import _hash


def preparation_schedule(value, case_ids, case_seed):
    value = definition(value)
    if (type(case_ids) is not list or not 1 <= len(case_ids) <= 1000
            or any(type(item) is not str for item in case_ids) or len(set(case_ids)) != len(case_ids)
            or type(case_seed) is not int):
        raise ValueError("invalid_preparation_schedule")
    for identifier in case_ids:
        _id(identifier)
    seed = _hash(["javis-preparation-schedule-v1", _hash(value), case_seed])
    ordered = sorted(case_ids, key=lambda identifier: (_hash([seed, identifier]), identifier))
    return {"version": 1, "experiment_id": value["experiment_id"], "definition_hash": _hash(value),
            "context_id": value["context_id"], "case_set_id": value["case_set_id"],
            "case_set_hash": value["case_set_hash"], "repeat_policy": value["repeat_policy"], "schedule_seed": seed,
            "cells": [{"case_id": identifier, "repeat": repeat} for identifier in ordered
                      for repeat in range(1, value["repeat_policy"]["repeats"] + 1)]}
