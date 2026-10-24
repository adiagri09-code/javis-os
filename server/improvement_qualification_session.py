"""Host-owned private engineering run storage; no launch/runtime consumer yet.

Candidate review permits preparation of this disposable engineering domain. It
does not register a native release or prove account readiness. Native launch,
typed verification, attempt/call joins and mandatory domain authentication at
publication/cold read must be integrated before any qualifier can execute.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
from pathlib import Path
import secrets
import sys
import tempfile
import time

from cryptography.fernet import Fernet

import improvement_store as IM
from improvement_blobs import AssetUnavailable, RevisionBlobs, check_ancestry
from improvement_claude import _runtime_identity
from improvement_native_formats import NATIVE_PROFILE_VERSION
from improvement_native_protocol import _canonical, _digest, _fields, _parse
from improvement_native_release import _pin, observe_release
from improvement_qualification_environment import _endpoint, dummy_environment
from improvement_sandbox import _private_directory, worker_environment
from resonance_store import GoalStore, Principal

_TOKEN = object()


class QualificationSession:
    def __init__(self, token):
        if token is not _TOKEN:
            raise TypeError('host_qualification_factory_required')

    @classmethod
    def open(cls, *, pin, endpoint, expected_fingerprint, lifetime_seconds, maximum_queries):
        pin = _pin(pin)
        endpoint = _endpoint(endpoint); _digest(expected_fingerprint)
        if (pin['profile_version'] != NATIVE_PROFILE_VERSION
                or type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= 3600
                or type(maximum_queries) is not int or not 1 <= maximum_queries <= 32):
            raise ValueError('qualification_scope_invalid')
        from improvement_native_qualifications import REVIEWED_QUALIFICATION_CANDIDATES
        key = (sys.platform, pin['cli_version'], pin['cli_hash'], pin['sdk_version'],
            pin['profile_version'], pin['profile_hash'], expected_fingerprint)
        review = REVIEWED_QUALIFICATION_CANDIDATES.get(key)
        if review is None:
            raise PermissionError('qualification_candidate_unreviewed')
        _digest(review)
        runtime = _runtime_identity(pin)
        if (type(runtime) is not dict or runtime.get('platform') != sys.platform
                or runtime.get('managed_policy') != 'absent'
                or any(runtime.get(name) != pin[name] for name in ('cli_hash', 'sdk_version', 'profile_hash'))):
            raise PermissionError('qualification_runtime_drift')
        release = observe_release(pin)
        if release['fingerprint'] != expected_fingerprint:
            raise PermissionError('qualification_source_drift')
        self = cls(_TOKEN)
        self._temporary = tempfile.TemporaryDirectory(prefix='jnqual-')
        self._root = Path(self._temporary.name).absolute()
        self._closed = self._cleaned = False
        self._owners = set()
        try:
            _private_directory(self.root)
            brain = self.root / 'brain'; brain.mkdir(mode=0o700)
            self.principal = Principal('owner', 'owner', str(brain))
            key_bytes = Fernet.generate_key()
            # New fixture-only encryption material, never copied host auth.
            key_path = self.root / 'fixture-encryption.key'
            with key_path.open('xb') as handle: handle.write(key_bytes)
            key_path.chmod(0o600)
            codec = Fernet(key_bytes)
            blobs = RevisionBlobs(self.root / 'assets',
                encrypt=lambda text: 'enc:' + codec.encrypt(text.encode()).decode(),
                decrypt=lambda text: codec.decrypt(text.removeprefix('enc:').encode()).decode())
            self.assets = IM.ImprovementStore(GoalStore(self.root / 'state' / 'resonance.sqlite3'), blobs)
            IM.ensure(self.assets.store)
            from agent_ledger import CallLedger
            self.ledger = CallLedger(self.assets.store)
            created = time.time()
            self._scope = {'version': 1, 'domain': 'qualification', 'account_ready': False,
                'run_nonce': secrets.token_hex(32), 'root': str(self.root), 'brain_id': self.principal.brain_id,
                'pin_hash': IM._hash(pin), 'release_fingerprint': expected_fingerprint, 'review_hash': review,
                'endpoint': endpoint, 'maximum_queries': maximum_queries,
                'created_at': created, 'deadline_at': created + lifetime_seconds}
            self.run_hash = IM._hash(self._scope)
            self._event_key = 'native-qualification:' + self.run_hash
            self._pin = _parse(_canonical(pin))
            self._release = release
            raw = _canonical(self._scope)
            blob = self.assets.blobs.write(self.principal.brain_id, raw)
            with self.assets.store._Tx(self.assets.store) as connection:
                IM.ImprovementStore._event(connection, self.principal, self._event_key,
                    'native_qualification_session', {'run_hash': self.run_hash},
                    {'version': 1, 'run_hash': self.run_hash, 'blob_hash': blob})
            return self
        except BaseException:
            self._temporary.cleanup()
            raise

    @property
    def root(self):
        return self._root

    def scope(self):
        return _parse(_canonical(self._scope))

    def read_scope(self):
        if self._cleaned: raise PermissionError('qualification_session_unavailable')
        with closing(self.assets.store._conn()) as connection:
            record = IM.ImprovementStore._replay(connection, self.principal.brain_id, self._event_key,
                'native_qualification_session', {'run_hash': self.run_hash})
        if record is None: raise PermissionError('qualification_session_unavailable')
        _fields(record, {'version', 'run_hash', 'blob_hash'})
        if type(record['version']) is not int or record['version'] != 1 or record['run_hash'] != self.run_hash:
            raise AssetUnavailable('qualification_session_changed')
        _digest(record['blob_hash'])
        raw = self.assets.blobs.read(self.principal.brain_id, record['blob_hash'])
        if (hashlib.sha256(raw).hexdigest() != self.run_hash or raw != _canonical(self._scope)):
            raise AssetUnavailable('qualification_session_changed')
        return _parse(raw)

    def environment(self, cwd):
        if self._closed or self._cleaned:
            raise PermissionError('qualification_session_closed')
        scope = self.read_scope()
        if time.time() >= scope['deadline_at']:
            raise PermissionError('qualification_session_expired')
        supplied = Path(cwd)
        if '..' in supplied.parts:
            raise PermissionError('qualification_workspace_foreign')
        cwd = supplied.absolute()
        check_ancestry(cwd)
        if not cwd.is_relative_to(self.root) or not cwd.is_dir():
            raise PermissionError('qualification_workspace_foreign')
        homes = self.root / 'homes'; homes.mkdir(exist_ok=True, mode=0o700)
        check_ancestry(homes)
        home = homes / secrets.token_hex(16)
        home.mkdir(mode=0o700)
        check_ancestry(home)
        if tuple(home.iterdir()): raise PermissionError('qualification_home_not_empty')
        return dummy_environment(worker_environment(cwd, auth_home=home), endpoint=scope['endpoint'])

    def close(self):
        # No launch consumer is installed in this component. Future owned native
        # sessions must attach before acquisition and detach only after real drain.
        self._closed = True
        self._temporary._finalizer.detach()

    def cleanup(self):
        self.close()
        if self._owners:
            raise RuntimeError('qualification_native_owners_unsettled')
        if not self._cleaned:
            self._temporary.cleanup()
            self._cleaned = True
