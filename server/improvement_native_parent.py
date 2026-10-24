"""Actual parent preflight/query ownership under existing M0 authority.

The release registry authenticates declared source/runtime/import content. Native
image/lifetime owners establish their documented observations; neither hashes nor
these records claim loaded-page identity, provider acceptance or comprehension.
"""
from __future__ import annotations

import asyncio
from contextlib import aclosing
import hashlib
import inspect
from pathlib import Path
import secrets
import subprocess
import tempfile

import improvement_store as IM
from improvement_blobs import MAX_ASSET_BYTES
from improvement_native_decisions import NativeImageDecisionStore, attempt_scope
from improvement_native_protocol import _canonical, _digest, _fields, _parse
from improvement_native_release import qualified_launch
from improvement_native_transport import GuardianSessionV2, execute_worker_v2
from improvement_sandbox import worker_environment

_RETAINED_SCRATCH = set()
_PURPOSES = ('adapter_version', 'auth_status', 'sdk_version', 'query')


def _sha(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()


async def _settled(coroutine):
    from improvement_claude import _settled_owned
    results, interrupted = await _settled_owned(asyncio.gather(asyncio.create_task(coroutine), return_exceptions=True))
    if isinstance(results[0], BaseException): raise results[0]
    if interrupted is not None: raise interrupted
    return results[0]


def _dispatch(joined, pin, environment, cwd, query_policy):
    """Recheck captured summary against this exact host-selected launch scope."""
    dispatch, purpose = joined['dispatch'], joined['purpose']
    _fields(dispatch, {'version', 'purpose', 'basis', 'argument_consistency', 'environment_hash', 'source_policy_hash'})
    expected_environment = (dict(environment) if purpose != 'query' else {**environment,
        'CLAUDE_CODE_ENTRYPOINT': 'sdk-py', 'CLAUDE_AGENT_SDK_VERSION': pin['sdk_version'], 'PWD': cwd})
    if (dispatch['version'] != 1 or dispatch['basis'] != 'native_argument_consistency'
            or dispatch['source_policy_hash'] != pin['profile_hash']
            or dispatch['environment_hash'] != IM._hash(expected_environment)
            or joined['image']['comparison']['selected']['sha256'] != pin['cli_hash']):
        raise ValueError('native_parent_dispatch_drift')
    actual = dispatch['argument_consistency']
    if purpose != 'query':
        argv = [pin['cli_path'], *{'adapter_version': ['--version'], 'auth_status': ['auth', 'status', '--json'],
            'sdk_version': ['-v']}[purpose]]
        expected = {'version': 1, 'argv_hash': IM._hash(argv),
            'command_line_hash': _sha(subprocess.list2cmdline(argv)), 'cwd_hash': _sha(cwd), 'creationflags': 0x08000006}
        if _canonical(actual) != _canonical(expected): raise ValueError('native_parent_dispatch_drift')
        return
    if query_policy is None: raise ValueError('native_parent_query_forbidden')
    _fields(actual, {'version', 'verdict', 'basis', 'model', 'reasoning', 'prompt_hash', 'tools', 'argv_hash',
        'command_line_hash', 'cli_path_hash', 'cwd_hash', 'settings_hash', 'mcp_config_hash', 'expected_hash',
        'creationflags', 'coverage', 'tool_policy'})
    servers = ('fixture', 'skill') if query_policy['tool_policy'] == 'pinned_skill' else ('fixture',)
    expected = {'version': 2, 'verdict': 'pass', 'basis': 'query_argument_consistency',
        **{key: query_policy[key] for key in ('model', 'reasoning', 'prompt_hash', 'tools', 'tool_policy')},
        'cli_path_hash': _sha(pin['cli_path']), 'cwd_hash': _sha(cwd), 'expected_hash': IM._hash(query_policy),
        'settings_hash': IM._hash({'fastMode': False, 'disableAllHooks': True}),
        'mcp_config_hash': IM._hash({'mcpServers': {name: {'type': 'sdk', 'name': name} for name in servers}}),
        'creationflags': 0x08000006, 'coverage': dict.fromkeys(
            ('os_boundary', 'image', 'provider_acceptance', 'internal_reasoning'), 'unknown')}
    if any(_canonical(actual[key]) != _canonical(value) for key, value in expected.items()):
        raise ValueError('native_parent_dispatch_drift')
    for key in ('argv_hash', 'command_line_hash'): _digest(actual[key])


class NativeParentBoundary:
    def __init__(self, pin, assets, principal, *, scope_hash, current, lock=None):
        if type(assets) is not IM.ImprovementStore:
            raise TypeError('concrete_native_parent_store_required')
        IM._brain(principal); _digest(scope_hash)
        if (not callable(current) or inspect.iscoroutinefunction(current)
                or inspect.iscoroutinefunction(getattr(current, '__call__', None))
                or (lock is not None and type(lock) is not asyncio.Lock)):
            raise ValueError('native_parent_authority_required')
        self.pin = _parse(_canonical(pin))
        self.assets, self.principal, self.scope_hash = assets, principal, scope_hash
        self.current, self.lock = current, lock
        self.decisions = NativeImageDecisionStore(assets)
        self._verification_started = self._query_started = False

    async def _serialized(self, callback):
        if self.lock is None: return await _settled(asyncio.to_thread(callback))
        async with self.lock:
            return await _settled(asyncio.to_thread(callback))

    async def _current(self):
        def check():
            with self.assets.store._Tx(self.assets.store) as connection:
                if self.current(connection, None) != 'allow':
                    raise PermissionError('native_parent_authority_changed')
        await self._serialized(check)

    def _persist(self, *, environment, cwd, scope_hash, query_policy=None):
        environment, pin = dict(environment), self.pin
        async def persist(joined):
            def current(connection, value):
                _dispatch(value, pin, environment, cwd, query_policy)
                return self.current(connection, value)
            return await self._serialized(lambda: self.decisions.persist(self.principal, joined,
                scope_hash=scope_hash, current=current))
        return persist

    def _save_preflight(self, nonce, packets):
        raw = _canonical(packets)
        digest = hashlib.sha256(raw).hexdigest()
        payload = {'scope_hash': self.scope_hash, 'launch_nonce': nonce, 'trace_hash': digest,
                   'engine_config_hash': IM._hash(self.pin)}
        key = 'native-preflight:' + IM._hash([self.scope_hash, nonce])
        with self.assets.store._Tx(self.assets.store) as connection:
            previous = self.assets._replay(connection, IM._brain(self.principal), key, 'native_preflight_evidence', payload)
            if previous is not None: return previous
            hashes = [self.assets.blobs.write(IM._brain(self.principal), raw[offset:offset + MAX_ASSET_BYTES])
                for offset in range(0, len(raw), MAX_ASSET_BYTES)]
            record = {'version': 1, **payload, 'blob_hashes': hashes}
            self.assets._event(connection, self.principal, key, 'native_preflight_evidence', payload, record)
            return record

    @staticmethod
    def _scratch_close(scratch, error):
        owner = getattr(error, 'owner', None)
        if owner is not None and not owner.closed:
            _RETAINED_SCRATCH.add(scratch)
        else:
            scratch.cleanup()

    async def verify(self, adapter):
        if self._verification_started: raise ValueError('native_parent_preflight_already_used')
        self._verification_started = True
        admission = await _settled(asyncio.to_thread(adapter.admit_preflight))
        if type(admission) is not dict or admission.get('admitted') is not True:
            return {'supported': False, 'reason': admission.get('reason') if type(admission) is dict else 'native_preflight_refused',
                'requested': {key: self.pin[key] for key in ('provider', 'engine_id', 'model', 'reasoning')}}
        scratch = tempfile.TemporaryDirectory(prefix='jnp-')
        owner, error, packets, runtime = None, None, [], None
        nonce = secrets.token_hex(32)
        try:
            launch = await _settled(asyncio.to_thread(qualified_launch, self.pin, kind='preflight', scratch=scratch.name))
            await self._current()
            environment = worker_environment(Path(scratch.name))
            owner = GuardianSessionV2(launch['guardian_manifest'], launch['policy'], image_policy=launch['image_policy'],
                fences=[str(Path(scratch.name) / 'admission.lock'), str(Path(scratch.name) / 'preflight.lock')],
                launch_nonce=nonce, invocations=[{'purpose': purpose, 'nonce': secrets.token_hex(32)} for purpose in _PURPOSES[:2]],
                persist_before_allow=self._persist(environment=environment, cwd=scratch.name, scope_hash=self.scope_hash),
                timeout=30, close_timeout=8, lifetime_timeout=60)
            await owner.start({'kind': 'preflight', 'request': {'version': 1, 'config_pin': self.pin}, 'environment': environment})
            while True:
                packet = await owner.receive()
                packets.append(packet)
                if packet['body']['type'] == 'worker_error': raise RuntimeError('native_preflight_worker_failed')
                if packet['body']['type'] == 'preflight_complete':
                    runtime = packet['body']['runtime']
                    break
        except BaseException as caught:
            error = caught
        finally:
            if owner is not None:
                try:
                    await _settled(owner.aclose())
                except BaseException as caught:
                    error = caught
                packets.extend(owner.closing_observations)
                try:
                    await _settled(asyncio.to_thread(self._save_preflight, nonce, packets))
                except BaseException as caught:
                    if error is None: error = caught
            self._scratch_close(scratch, error)
        if error is not None: raise error
        if runtime is None or any(type(status) is not int or status != 0 for status in
                (owner._worker_exit_code, owner._guardian_exit_code)):
            raise RuntimeError('native_preflight_exit_failed')
        return await _settled(asyncio.to_thread(adapter.verify_observed, runtime))

    async def execute(self, kind, request, receipt, *, adapter, workspace_root, brain_id,
            before_engine_start, system_prompt, tool_policy, on_closing_observations):
        if type(kind) is not str or kind not in ('trial', 'operation') or tool_policy != (
                'pinned_skill' if kind == 'trial' else 'fixture_only'):
            raise ValueError('native_parent_query_policy_invalid')
        if self._query_started: raise ValueError('native_parent_query_already_used')
        self._query_started = True
        if not inspect.iscoroutinefunction(on_closing_observations):
            raise ValueError('native_parent_closing_evidence_required')
        admission = await _settled(asyncio.to_thread(adapter.admit_preflight))
        if type(admission) is not dict or admission.get('admitted') is not True:
            raise ValueError('native_parent_query_unqualified')
        scope = attempt_scope(kind=kind, brain_id=brain_id, receipt=receipt, config_pin=self.pin,
                              capability_hash=request['capability_hash'])
        scratch, error = tempfile.TemporaryDirectory(prefix='jnq-'), None
        try:
            launch = await _settled(asyncio.to_thread(qualified_launch, self.pin, kind=kind, scratch=scratch.name))
            await self._current()
            environment = worker_environment(Path(receipt['path']))
            tools = ['mcp__fixture__fixture_read'] + (['mcp__skill__skill_asset_read'] if tool_policy == 'pinned_skill' else [])
            policy = {'version': 2, **{key: self.pin[key] for key in ('cli_path', 'model', 'reasoning')},
                'prompt_hash': _sha(system_prompt), 'cwd': receipt['path'], 'tools': tools, 'tool_policy': tool_policy}
            async with aclosing(execute_worker_v2(kind, request, receipt, config_pin=self.pin,
                    workspace_root=workspace_root, brain_id=brain_id, before_engine_start=before_engine_start,
                    **{key: launch[key] for key in ('guardian_manifest', 'policy', 'image_policy')},
                    launch_nonce=secrets.token_hex(32), invocations=[{'purpose': purpose, 'nonce': secrets.token_hex(32)} for purpose in _PURPOSES],
                    persist_before_allow=self._persist(environment=environment, cwd=receipt['path'], scope_hash=scope, query_policy=policy),
                    on_closing_observations=on_closing_observations, environment=environment)) as packets:
                async for packet in packets: yield packet
        except BaseException as caught:
            error = caught
            raise
        finally:
            self._scratch_close(scratch, error)
