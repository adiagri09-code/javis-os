"""Explicit owner compose consent and read-only current input authority.

Consent is immutable M0-linked history with a separately revocable grant. This
service never dispatches an operation/model or grants edit/activation authority.
Current checks reuse the complete existing input-basis hash rather than copying
the trial ledger into another authority store. Operation admission follows later.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import improvement_store as IM
from improvement_blobs import AssetUnavailable
from improvement_compose_inputs import ComposeInputs
from improvement_compose_protocol import render_compose_input
from improvement_experiment_protocol import _digest
from improvement_experiments import _generation, _identifier
from improvement_generation_protocol import input_bytes
from improvement_operation_schema import assert_installed
from improvement_qualification_records import require_product_store
from improvement_trial_records import _brain

_META = {'authorization_id', 'experiment_id', 'context_id', 'input_hash', 'basis_hash',
         'guard_blob_hash', 'experiment_generation', 'generation', 'status'}


class ComposePermissions:
    def __init__(self, plans):
        self.inputs = ComposeInputs(plans)
        self.plans, self.assets, self.store, self.blobs = plans, plans.assets, plans.store, plans.blobs

    def _installed(self):
        if IM._schema_version(self.store) < 8:
            raise PermissionError('compose_permission_unavailable')

    def _connection(self, connection):
        if type(connection) is not sqlite3.Connection:
            raise TypeError('concrete_compose_connection_required')
        databases = connection.execute('PRAGMA database_list').fetchall()
        if (len(databases) != 1 or databases[0][1] != 'main' or not databases[0][2]
                or Path(databases[0][2]).resolve() != self.store.path.resolve()):
            raise ValueError('compose_connection_mismatch')
        version = connection.execute('SELECT version FROM improvement_schema WHERE id=1').fetchone()
        if not version or version[0] != 8:
            raise IM.SchemaError('unsupported_improvement_schema')

    @staticmethod
    def _row(connection, brain, identifier):
        row = connection.execute('SELECT a.*,g.generation,g.status FROM improvement_compose_authorizations a '
            'JOIN improvement_compose_grants g ON g.authorization_id=a.id AND g.brain_id=a.brain_id '
            'WHERE a.id=? AND a.brain_id=?', (identifier, brain)).fetchone()
        if row is None:
            raise PermissionError('compose_permission_unavailable')
        return dict(row)

    def _metadata(self, connection, row):
        events = list(connection.execute("SELECT * FROM improvement_events WHERE brain_id=? AND operation='compose_authorize' "
            "AND json_extract(result_json,'$.authorization_id')=? LIMIT 2", (row['brain_id'], row['id'])))
        if len(events) != 1:
            raise AssetUnavailable('compose_permission_history_unavailable')
        event = events[0]
        value = json.loads(event['result_json'])
        if type(value) is not dict or set(value) != _META:
            raise AssetUnavailable('compose_permission_history_changed')
        _generation(value['experiment_generation'])
        for key in ('input_hash', 'basis_hash', 'guard_blob_hash'): _digest(value[key])
        expected = {'authorization_id': row['id'], **{key: row[key] for key in
            ('experiment_id', 'context_id', 'input_hash', 'basis_hash')}, 'generation': 1, 'status': 'active'}
        if any(value.get(key) != item for key, item in expected.items()) or event['actor'] != row['actor']:
            raise AssetUnavailable('compose_permission_history_changed')
        payload = {'experiment_id': row['experiment_id'], 'expected_generation': value['experiment_generation']}
        if self.assets._replay(connection, row['brain_id'], event['event_key'], 'compose_authorize', payload) != value:
            raise AssetUnavailable('compose_permission_history_changed')
        return {**value, 'generation': row['generation'], 'status': row['status']}

    def get(self, principal, authorization_id):
        brain = _brain(principal); _identifier(authorization_id); self._installed()
        with closing(self.store._conn()) as connection:
            return self._metadata(connection, self._row(connection, brain, authorization_id))

    def list(self, principal, experiment_id):
        brain = _brain(principal); _identifier(experiment_id)
        if IM._schema_version(self.store) < 8: return []
        with closing(self.store._conn()) as connection:
            identifiers = [row[0] for row in connection.execute('SELECT id FROM improvement_compose_authorizations '
                'WHERE experiment_id=? AND brain_id=? ORDER BY created_at,id', (experiment_id, brain))]
            return [self._metadata(connection, self._row(connection, brain, identifier)) for identifier in identifiers]

    def revoke(self, principal, authorization_id, *, expected_generation, event_key):
        brain = _brain(principal); _identifier(authorization_id); _generation(expected_generation); self._installed()
        payload = {'authorization_id': authorization_id, 'expected_generation': expected_generation}
        with self.store._Tx(self.store) as connection:
            old = self.assets._replay(connection, brain, event_key, 'compose_revoke', payload)
            if old is not None: return old
            row = self._row(connection, brain, authorization_id)
            if row['generation'] != expected_generation or row['status'] != 'active':
                raise IM.ConflictError('compose_permission_stale')
            connection.execute("UPDATE improvement_compose_grants SET generation=generation+1,status='revoked',revoked_at=? "
                'WHERE authorization_id=? AND brain_id=?', (time.time(), authorization_id, brain))
            result = self._metadata(connection, self._row(connection, brain, authorization_id))
            self.assets._event(connection, principal, event_key, 'compose_revoke', payload, result)
            return result

    def _capture(self, connection, principal, experiment_id, generation):
        before = self.inputs._snapshot(connection, principal, experiment_id, generation)
        for comparison in before['comparisons']:
            comparison['policy'] = self.inputs.reports._policy(before['prepared'][0])
        return before

    @staticmethod
    def _authority_hash(before):
        # Exactly the producer's stable basis: retain complete current SQL
        # history, definition and binding, not process-local checker identities.
        stable = {key: value for key, value in before.items() if key != 'prepared'}
        stable['definition'] = before['prepared'][0]
        stable['binding_hash'] = before['prepared'][0]['binding_hash']
        return IM._hash(stable)

    def _load(self, brain, digest):
        _digest(digest)
        raw = self.blobs.read(brain, digest)
        try:
            value = json.loads(raw)
            if type(value) is not dict or IM._json(value).encode('utf-8') != raw:
                raise ValueError('noncanonical_compose_permission_blob')
        except (ValueError, UnicodeError, TypeError, RecursionError) as error:
            raise AssetUnavailable('compose_permission_blob_unavailable') from error
        return value

    def _input_history(self, connection, brain, metadata):
        payload = {'experiment_id': metadata['experiment_id'], 'expected_generation': metadata['experiment_generation']}
        key = 'compose-input-' + IM._hash([brain, payload])
        actual = self.assets._replay(connection, brain, key, 'compose_input', payload)
        expected = {key: metadata[key] for key in ('input_hash', 'basis_hash')}
        expected.update(input_blob_hash=metadata['input_hash'], basis_blob_hash=metadata['basis_hash'])
        if actual != expected:
            raise AssetUnavailable('compose_authorized_input_unavailable')

    def _links(self, row, metadata, guard, basis, data, before, observed, baseline):
        value = before['prepared'][0]
        if (set(guard) != {'version', 'kind', 'experiment', 'input_hash', 'basis_hash'}
                or type(guard['version']) is not int or guard['version'] != 1 or guard['kind'] != 'compose_permission_guard'
                or guard['experiment'] != before['experiment'] or guard['input_hash'] != row['input_hash']
                or guard['basis_hash'] != row['basis_hash']):
            raise IM.ConflictError('compose_permission_basis_changed')
        expected = {'version': 1, 'kind': 'compose_input_basis', 'experiment_id': row['experiment_id'],
            'context_id': row['context_id'], 'definition_hash': row['definition_hash'],
            'generation': metadata['experiment_generation'], 'source_authority_hash': observed['source_authority_hash'],
            'authority_snapshot_hash': self._authority_hash(before),
            'candidate_refs': [{key: item[key] for key in ('id', 'content_hash', 'patch_hash', 'provenance_hash')}
                               for item in before['candidates']],
            'report_refs': [{key: item['saved'][key] for key in ('id', 'report_hash', 'publication_id')}
                            for item in before['comparisons']]}
        if (basis != expected or row['definition_hash'] != IM._hash(value)
                or row['context_generation'] != value['context_generation'] or row['policy_version'] != value['policy_version']
                or any(data.get(key) != row[key] for key in ('experiment_id', 'context_id', 'definition_hash'))
                or data.get('baseline', {}).get('content', '').encode('utf-8') != baseline):
            raise IM.ConflictError('compose_authorized_input_changed')
        render_compose_input(data)

    def _fence(self, connection, principal, before, observed):
        self.inputs._fence(connection, principal, before)
        value = before['prepared'][0]
        for comparison in before['comparisons']:
            if self.inputs.reports._policy(value) != comparison['policy']:
                raise IM.ConflictError('compose_policy_changed')
            self.inputs.reports._guard(connection, principal, comparison['metadata'], before['experiment']['generation'])
        self.plans.authoring._guard(connection, principal, before['authoring'], observed)
        self.inputs._fence(connection, principal, before)

    def current(self, connection, principal, authorization_id):
        brain = _brain(principal); _identifier(authorization_id); self._connection(connection)
        require_product_store(self.assets, principal, connection=connection)
        assert_installed(connection)
        row = self._row(connection, brain, authorization_id)
        if row['status'] != 'active' or row['generation'] != 1:
            raise PermissionError('compose_permission_revoked')
        metadata = self._metadata(connection, row)
        before = self._capture(connection, principal, row['experiment_id'], metadata['experiment_generation'])
        data, basis, guard = (self._load(brain, metadata[key]) for key in ('input_hash', 'basis_hash', 'guard_blob_hash'))
        self._input_history(connection, brain, metadata)
        observed, baseline = self.plans.authoring.observe(principal, before['authoring']['target'])
        self._links(row, metadata, guard, basis, data, before, observed, baseline)
        # Capturing includes policy-file reads. Finish all such reads before
        # the source guards and final SQL-only consent/state checks.
        if self._capture(connection, principal, row['experiment_id'], metadata['experiment_generation']) != before:
            raise IM.ConflictError('compose_authority_changed')
        self._fence(connection, principal, before, observed)
        self.inputs._fence(connection, principal, before)
        # No further policy/blob/host observations after this final SQL fence.
        if self._row(connection, brain, authorization_id) != row:
            raise IM.ConflictError('compose_permission_changed')
        require_product_store(self.assets, principal, connection=connection)
        return {'authorization': metadata, 'data': data, 'basis': basis, 'prepared': before['prepared']}

    def authorize(self, principal, experiment_id, *, expected_generation, event_key):
        brain = _brain(principal); _identifier(experiment_id); _generation(expected_generation); self._installed()
        require_product_store(self.assets, principal)
        payload = {'experiment_id': experiment_id, 'expected_generation': expected_generation}
        with closing(self.store._conn()) as connection:
            old = self.assets._replay(connection, brain, event_key, 'compose_authorize', payload)
            if old is not None:
                return self._metadata(connection, self._row(connection, brain, old['authorization_id']))
            assert_installed(connection)
            before = self._capture(connection, principal, experiment_id, expected_generation)
            if connection.execute("SELECT 1 FROM improvement_operations WHERE experiment_id=? AND brain_id=? AND kind='compose'",
                                  (experiment_id, brain)).fetchone():
                raise IM.ConflictError('compose_already_recorded')
        built = self.inputs.build(principal, experiment_id, expected_generation=expected_generation)
        guard = {'version': 1, 'kind': 'compose_permission_guard', 'experiment': before['experiment'],
                 'input_hash': built['input_hash'], 'basis_hash': built['basis_hash']}
        guard_blob = self.blobs.write(brain, input_bytes(guard))
        value, stamp = before['prepared'][0], time.time()
        with self.store._Tx(self.store) as connection:
            old = self.assets._replay(connection, brain, event_key, 'compose_authorize', payload)
            if old is not None:
                return self._metadata(connection, self._row(connection, brain, old['authorization_id']))
            self.inputs._fence(connection, principal, before)
            identifier = 'icpa_' + secrets.token_hex(12)
            connection.execute('INSERT INTO improvement_compose_authorizations VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (identifier, brain, experiment_id, value['context_id'], IM._hash(value), built['input_hash'], built['basis_hash'],
                 value['context_generation'], value['policy_version'], principal.by, stamp))
            connection.execute("INSERT INTO improvement_compose_grants VALUES(?,?,1,'active',NULL)", (identifier, brain))
            metadata = {'authorization_id': identifier, 'experiment_id': experiment_id, 'context_id': value['context_id'],
                'input_hash': built['input_hash'], 'basis_hash': built['basis_hash'], 'guard_blob_hash': guard_blob,
                'experiment_generation': expected_generation, 'generation': 1, 'status': 'active'}
            self.assets._event(connection, principal, event_key, 'compose_authorize', payload, metadata)
            return self.current(connection, principal, identifier)['authorization']
