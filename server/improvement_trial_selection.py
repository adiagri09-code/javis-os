"""Strict read-only selection capture; never load decrypted config or execute a runtime.

The ordinary Claude factory always uses the SDK. This reader deliberately rejects
its implicit model/provider fallbacks: trials need an explicit persisted selection.
Runtime versions below come from the verified hash allowlist, not a CLI invocation.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import stat
import sys
from pathlib import Path

import improvement_claude as native

MAX_SETTINGS_BYTES = 1024 * 1024
MAX_BINARY_BYTES = 512 * 1024 * 1024
_FIELDS = {"provider", "model", "reasoning", "auth_mode", "fast"}


def _identity(info):
    # Python 3.12 Windows lstat still exposes creation time as ctime, while fstat
    # exposes change time. birthtime is the comparable identity field on both.
    # Windows lstat also infers executable permission bits from a .exe suffix;
    # fstat does not. The file kind and Windows attributes remain comparable.
    return (info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode), info.st_size, info.st_mtime_ns,
            getattr(info, "st_birthtime_ns", info.st_ctime_ns), getattr(info, "st_file_attributes", 0))


def _path_info(path):
    info = None
    for component in reversed((path, *path.parents)):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("trial_selection_linked_source")
    if info is None or not stat.S_ISREG(info.st_mode):
        raise ValueError("trial_selection_nonregular_source")
    return info


def _read_stable(path, limit, *, digest=False):
    """Bind opened bytes to the same regular path identity before and after reading."""
    try:
        path = Path(path).absolute()
        before = _path_info(path)
        if not 0 <= before.st_size <= limit:
            raise ValueError("trial_selection_source_size")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            if _identity(os.fstat(handle.fileno())) != _identity(before):
                raise ValueError("trial_selection_source_changed")
            result = hashlib.sha256() if digest else bytearray()
            size = 0
            while True:
                block = handle.read(min(1024 * 1024, limit - size + 1))
                if not block:
                    break
                size += len(block)
                if size > limit:
                    raise ValueError("trial_selection_source_size")
                if digest:
                    result.update(block)
                else:
                    result.extend(block)
            after = os.fstat(handle.fileno())
            if (_identity(after) != _identity(before) or size != before.st_size
                    or _identity(_path_info(path)) != _identity(before)):
                raise ValueError("trial_selection_source_changed")
        return (result.hexdigest() if digest else bytes(result)), _identity(before)
    except (OSError, TypeError, OverflowError):
        raise ValueError("trial_selection_source_unavailable") from None


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("trial_selection_duplicate_key")
        value[key] = item
    return value


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("trial_selection_nonfinite_json")
    return number


def _constant(value):
    raise ValueError("trial_selection_nonfinite_json")


def _text(value, limit=512):
    if (not isinstance(value, str) or not 1 <= len(value) <= limit or not value.strip()
            or any(ord(character) < 32 for character in value)):
        raise ValueError("trial_selection_invalid_field")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ValueError("trial_selection_invalid_field") from None
    return value


def _closed(value):
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("trial_selection_invalid_fields")
    for field in ("provider", "model", "reasoning", "auth_mode"):
        _text(value[field])
    if type(value["fast"]) is not bool or value["auth_mode"] not in {"subscription", "api_key"}:
        raise ValueError("trial_selection_invalid_field")
    return dict(value)


def _selection(settings_path):
    content, identity = _read_stable(settings_path, MAX_SETTINGS_BYTES)
    try:
        settings = json.loads(content.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant, parse_float=_finite)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("trial_selection_invalid_json") from None
    if not isinstance(settings, dict) or not isinstance(settings.get("model"), dict):
        raise ValueError("trial_selection_model_missing")
    model = settings["model"]
    main = model.get("main")
    if main is None:
        main = {}
    if not isinstance(main, dict):
        raise ValueError("trial_selection_invalid_main")
    provider, selected_model = main.get("provider", ""), main.get("model", "")
    if provider == "" and selected_model == "":
        if model.get("engine") != "cli":
            raise ValueError("trial_selection_legacy_engine_unsupported")
        provider, selected_model = "anthropic-cli", model.get("claude_model")
    value = _closed({"provider": provider, "model": selected_model,
                     "reasoning": model.get("reasoning", "off"), "fast": model.get("fast", False),
                     "auth_mode": model.get("claude_auth", "subscription")})
    return value, identity


def read_selection(settings_path):
    """Return only persisted nonsecret routing semantics; failures never become defaults."""
    return _selection(settings_path)[0]


def selection_hash(value):
    """Hash exactly the five semantic fields, independent of unrelated secret changes."""
    raw = json.dumps(_closed(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_pin(settings_path, cli_path):
    """Build the adapter's closed pin using a known binary hash; no auth or CLI probes."""
    selected, source_identity = _selection(settings_path)
    if (selected["provider"] != "anthropic-cli" or selected["auth_mode"] != "subscription"
            or selected["fast"] or selected["reasoning"] not in {"low", "medium", "high", "xhigh", "max"}):
        raise ValueError("unsupported_trial_configuration")
    try:
        binary = Path(cli_path)
        if not binary.is_absolute():
            raise ValueError("trial_selection_binary_not_absolute")
        digest, binary_identity = _read_stable(binary, MAX_BINARY_BYTES, digest=True)
        sdk_version = importlib.metadata.version("claude-agent-sdk")
        matches = [runtime for runtime in native.VERIFIED_NATIVE_RUNTIMES
                   if runtime[0] == sys.platform and runtime[2:] == (digest, sdk_version)]
        if len(matches) != 1:
            raise ValueError("trial_selection_runtime_unverified")
        profile = native.profile_hash()
        pin = {"version": 1, "provider": selected["provider"], "engine_id": "claude-sdk",
               "model": selected["model"], "reasoning": selected["reasoning"], "cli_path": str(binary),
               "cli_hash": digest, "cli_version": matches[0][1], "sdk_version": sdk_version,
               "profile_version": native.PROFILE_VERSION, "profile_hash": profile}
        # Validate only the closed schema: verify() executes native version/auth probes.
        native.ClaudeTrialAdapter(pin)
        if importlib.metadata.version("claude-agent-sdk") != sdk_version or native.profile_hash() != profile:
            raise ValueError("trial_selection_capture_changed")
        current, current_identity = _selection(settings_path)
        if (current != selected or current_identity != source_identity
                or _identity(_path_info(binary)) != binary_identity):
            raise ValueError("trial_selection_capture_changed")
        return pin
    except (OSError, TypeError, importlib.metadata.PackageNotFoundError):
        raise ValueError("trial_selection_runtime_unavailable") from None
