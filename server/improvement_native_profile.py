"""One qualified profile's actual SDK client and original-stdin write evidence.

Completed write is pipe delivery only. Native read/acceptance, provider use and
comprehension stay unknown; result consumers must independently join observed
dispatch/image/session evidence under the frozen pipeline qualification.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import replace

from improvement_native_protocol import _canonical, _parse, _fields, _digest, _uint, _identity, MAX_PRIVATE_BYTES


def _copy(value): return _parse(_canonical(value))
def _sha(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _frame(prompt):
    if type(prompt) is not str: raise ValueError('invalid_native_user_prompt')
    # Exact SDK116 string-query serialization, including its distinct wire
    # session namespace. It is never equated to the native init UUID.
    value = json.dumps({'type': 'user', 'message': {'role': 'user', 'content': prompt},
        'parent_tool_use_id': None, 'session_id': 'default'}) + '\n'
    if len(value.encode('utf-8')) > MAX_PRIVATE_BYTES: raise ValueError('native_user_frame_too_large')
    return value


_COVERAGE = {'stdin': 'completed_original_stream_write', 'native_read_ack': 'unknown',
    'provider_acceptance': 'unknown', 'comprehension': 'unknown'}


def validate_input_delivery(proof, *, kind, identity, data_hash, user_prompt):
    """Closed consistency only; supplied proof does not establish execution."""
    if type(kind) is not str or kind not in ('trial', 'operation'): raise ValueError('invalid_native_delivery')
    expected_identity = _identity(kind, identity)
    _fields(identity, expected_identity)
    _digest(data_hash)
    proof = _copy(proof)
    _fields(proof, {'version', 'basis', 'kind', 'identity', 'data_hash', 'user_prompt_hash', 'user_frame_hash',
        'write_nonce', 'wire_session_id', 'native_pid', 'native_birth', 'dispatch_nonce', 'dispatch_hash', 'coverage'})
    actual_identity = _identity(kind, proof['identity'])
    _fields(proof['identity'], actual_identity)
    if (type(proof['version']) is not int or proof['version'] != 1
            or proof['basis'] != 'qualified_original_stdin_write' or proof['kind'] != kind
            or actual_identity != expected_identity or proof['data_hash'] != data_hash
            or proof['wire_session_id'] != 'default' or proof['coverage'] != _COVERAGE
            or proof['user_prompt_hash'] != _sha(user_prompt) or proof['user_frame_hash'] != _sha(_frame(user_prompt))):
        raise ValueError('invalid_native_delivery')
    for name in ('data_hash', 'user_prompt_hash', 'user_frame_hash', 'write_nonce', 'dispatch_nonce', 'dispatch_hash'):
        _digest(proof[name])
    _uint(proof['native_pid'], 32); _uint(proof['native_birth'])
    if proof['write_nonce'] == proof['dispatch_nonce']: raise ValueError('invalid_native_delivery')
    return proof


class NativeProfileBinding:
    """Fresh client factory; the enclosing worker still owns runtime cleanup."""
    def __init__(self, runtime, *, kind, identity, data_hash, user_prompt, environment, query_policy):
        from improvement_native_sdk import NativeInvocationSet, _environment
        if type(runtime) is not NativeInvocationSet: raise TypeError('concrete_native_runtime_required')
        if runtime.closed or runtime._closing or runtime._poisoned: raise ValueError('native_runtime_unavailable')
        if type(kind) is not str or kind not in ('trial', 'operation'): raise ValueError('invalid_native_profile')
        self._identity = _identity(kind, identity)
        _fields(identity, self._identity)
        self._identity = _copy(self._identity)
        _digest(data_hash)
        environment = _environment(environment)
        if environment != runtime._environment: raise ValueError('native_profile_environment_drift')
        policy = _copy(query_policy)
        _fields(policy, {'version', 'cli_path', 'model', 'reasoning', 'prompt_hash', 'cwd', 'tools', 'tool_policy'})
        tool_policy = policy['tool_policy']
        valid_policy = ((kind == 'trial' and tool_policy in ('pinned_skill', 'baseline_inline'))
                        or (kind == 'operation' and tool_policy == 'fixture_only'))
        tools = ['mcp__fixture__fixture_read'] + (['mcp__skill__skill_asset_read'] if tool_policy == 'pinned_skill' else [])
        if (type(policy['version']) is not int or policy['version'] != 2 or policy['tools'] != tools
                or not valid_policy
                or any(policy[name] != runtime._pin[name] for name in ('cli_path', 'model', 'reasoning'))
                or policy['cwd'] != runtime._cwd):
            raise ValueError('native_profile_query_policy_drift')
        _digest(policy['prompt_hash'])
        self._frame, self._user_prompt = _frame(user_prompt), user_prompt
        self._runtime, self._kind, self._data_hash = runtime, kind, data_hash
        self._environment, self._policy = environment, policy
        self._write_nonce = secrets.token_hex(32)
        self._used, self._transport, self._delivery = False, None, None

    @property
    def completed_delivery(self):
        return None if self._delivery is None else _copy(self._delivery)

    def create_client(self, options):
        if self._used: raise ValueError('native_profile_client_already_used')
        self._used = True
        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
        policy = self._policy
        if (type(options) is not ClaudeAgentOptions or type(options.system_prompt) is not str
                or _sha(options.system_prompt) != policy['prompt_hash']
                or options.model != policy['model'] or options.effort != policy['reasoning']
                or str(options.cli_path) != policy['cli_path'] or str(options.cwd) != policy['cwd']
                or options.allowed_tools != policy['tools'] or options.tools != []):
            raise ValueError('native_profile_options_drift')
        effective = replace(options, env=dict(self._environment))
        self._transport = self._runtime.transport(effective, query_policy=_copy(policy), on_user_write=self._completed_user_write)
        # Original options retain the SDK's callbacks; only the preconstructed
        # native transport receives the copied exact child environment.
        return ClaudeSDKClient(options=options, transport=self._transport)

    async def _completed_user_write(self, data, *, process, stdin, creation, dispatch_nonce, dispatch_hash):
        transport = self._transport
        if self._delivery is not None or transport is None or data != self._frame:
            raise ValueError('native_input_delivery_refused')
        entry = transport._native_entry
        if (entry is None or transport._native_user is not True or transport._process is not process
                or process is not entry['capture'].process or process.stdin is not stdin
                or transport._stdin_stream is None or transport._stdin_stream.transport_stream is not stdin
                or _canonical(creation) != _canonical(entry['creation'])
                or dispatch_nonce != self._runtime._channels['query']._nonce
                or dispatch_hash != hashlib.sha256(_canonical(entry['dispatch'])).hexdigest()):
            raise ValueError('native_input_delivery_unbound')
        proof = {'version': 1, 'basis': 'qualified_original_stdin_write', 'kind': self._kind,
            'identity': _copy(self._identity), 'data_hash': self._data_hash,
            'user_prompt_hash': _sha(self._user_prompt), 'user_frame_hash': _sha(data),
            'write_nonce': self._write_nonce, 'wire_session_id': 'default',
            'native_pid': creation['native_pid'], 'native_birth': creation['native_birth'],
            'dispatch_nonce': dispatch_nonce, 'dispatch_hash': dispatch_hash, 'coverage': dict(_COVERAGE)}
        self._delivery = validate_input_delivery(proof, kind=self._kind, identity=self._identity,
            data_hash=self._data_hash, user_prompt=self._user_prompt)
