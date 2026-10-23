"""Owned proposal/one-repair workflow over actual native role and A staging rows."""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import closing

import improvement_store as IM
from improvement_experiments import _generation, _identifier
from improvement_generation_protocol import input_bytes, parse_generation_output
from improvement_improver_inputs import ImproverInputs
from improvement_operation_adapter import ClaudeOperationAdapter
from improvement_operation_execution import OperationExecution
from improvement_operation_results import OperationResults
from improvement_operation_schema import TERMINAL, assert_installed
from improvement_operation_tasks import OperationTasks
from improvement_trial_records import _brain
from improvement_trial_runner import _settled_call

_REQUIRED = {'materialization', 'worker_protocol', 'installation', 'tool_inventory', 'side_effects',
             'completion', 'actual_model', 'native_session'}
_UNOBSERVED = {'actual_reasoning', 'actual_input_use'}


class ProposalService:
    def __init__(self, execution, tasks):
        if (type(execution) is not OperationExecution or type(tasks) is not OperationTasks
                or tasks.execution is not execution):
            raise TypeError('concrete_proposal_dependencies_required')
        self.execution, self.tasks, self.plans = execution, tasks, execution.plans
        self.assets, self.store, self.blobs = execution.assets, execution.store, execution.blobs
        self.inputs, self.products = ImproverInputs(self.plans), OperationResults(execution)
        self._operations, self._closed, self._closing, self._loop = {}, False, None, None

    def _bind(self):
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError('proposal_loop_changed')

    def _open(self):
        if self._closed:
            raise RuntimeError('proposal_service_closed')

    @staticmethod
    def _start_key(brain, event_key):
        return 'proposal-start-' + IM._hash([brain, event_key])

    def _fence(self, connection, principal, state, generation, *, candidates=None):
        """SQL-only final CAS after the last slow native/blob/source observation."""
        self._open()
        assert_installed(connection)
        brain = _brain(principal)
        value = state['prepared'][0]
        row = self.plans.records._row(connection, brain, value['experiment_id'])
        if (row['phase'] != 'proposing' or row['generation'] != generation
                or row['definition_hash'] != IM._hash(value)):
            raise IM.ConflictError('proposal_experiment_changed')
        self.plans.records._bound_in(connection, brain, value, value['context_generation'])
        self.inputs._holdout(connection, brain, value['case_set_id'])
        if connection.execute('SELECT 1 FROM improvement_experiment_selections WHERE experiment_id=? AND brain_id=?',
                              (row['id'], brain)).fetchone():
            raise IM.ConflictError('experiment_sealed')
        current = self.inputs.preparation._completion_snapshot(connection, brain, state['preparation'])
        if current != (state['links'], state['attempts']):
            raise IM.ConflictError('proposal_preparation_changed')
        actual = [dict(item) for item in connection.execute('SELECT id,ordinal FROM improvement_skill_candidates '
            'WHERE experiment_id=? AND brain_id=? ORDER BY ordinal', (row['id'], brain))]
        if actual != (state['candidates'] if candidates is None else candidates):
            raise IM.ConflictError('proposal_slots_changed')
        for ref, saved in zip(state['completion']['result_refs'], state['evidence']):
            identity = (ref['trial_id'], brain, ref['attempt'])
            trace = [dict(item) for item in connection.execute('SELECT * FROM improvement_trial_observations '
                'WHERE trial_id=? AND brain_id=? AND attempt=? ORDER BY sequence', identity)]
            if trace != saved['trace']:
                raise IM.ConflictError('proposal_tuning_trace_changed')
            for name in ('artifacts', 'receipts'):
                item = connection.execute('SELECT * FROM improvement_trial_' + name + ' WHERE trial_id=? AND brain_id=? AND attempt=?', identity).fetchone()
                if (dict(item) if item is not None else None) != saved[name]:
                    raise IM.ConflictError('proposal_tuning_product_changed')

    def _begin(self, principal, payload, event_key):
        brain, identifier = _brain(principal), payload['experiment_id']
        with closing(self.store._conn()) as connection:
            replay = self.assets._replay(connection, brain, event_key, 'proposal_generate', payload)
            if replay is not None:
                return {'replay': replay}
            old = self.assets._replay(connection, brain, self._start_key(brain, event_key), 'proposal_generate_start', payload)
            if old is not None:
                # Interrupted/historical request is not authority to resume work.
                row = self.execution._row(connection, principal, old['operation_id'])
                return {'replay': {**old, 'status': 'operation_recorded', 'operation_status': row['status']}}
            state = self.inputs._snapshot(connection, principal, identifier, payload['expected_generation'])
        built = self.inputs.build(principal, identifier, expected_generation=payload['expected_generation'])
        self._open()
        binding = state['prepared'][1]
        available = ClaudeOperationAdapter(binding['engine_config']).verify()
        if type(available) is not dict or available.get('supported') is not True:
            raise ValueError('operation_native_unavailable')
        self.plans.host._snapshot_observe(principal, binding)
        with self.store._Tx(self.store) as connection:
            replay = self.assets._replay(connection, brain, event_key, 'proposal_generate', payload)
            if replay is not None:
                return {'replay': replay}
            old = self.assets._replay(connection, brain, self._start_key(brain, event_key), 'proposal_generate_start', payload)
            if old is not None:
                return {'replay': {**old, 'status': 'operation_recorded'}}
            if self.inputs._snapshot(connection, principal, identifier, payload['expected_generation']) != state:
                raise IM.ConflictError('proposal_input_changed')
            self.plans.host._snapshot_observe(principal, binding)
            self._fence(connection, principal, state, payload['expected_generation'])
            data = built['data']
            request = {'version': 1, 'experiment_id': identifier, 'context_id': data['context_id'],
                'definition_hash': data['definition_hash'], 'kind': 'propose', 'role': 'improver', 'purpose': 'improve_propose',
                'candidate_id': None, 'parent_id': None, 'input_hash': built['input_hash']}
            row = self.execution.records._create_in(connection, principal, request, built['input_blob_hash'],
                expected_generation=payload['expected_generation'], event_key='proposal-operation-' + IM._hash([brain, event_key]))
            generation = payload['expected_generation'] + 1
            start = {'experiment_id': identifier, 'operation_id': row['operation_id'], 'input_hash': built['input_hash'], 'generation': generation}
            self.assets._event(connection, principal, self._start_key(brain, event_key), 'proposal_generate_start', payload, start)
            return {'state': state, 'data': data, 'operation_id': row['operation_id'], 'generation': generation}

    def _product(self, connection, principal, identifier):
        row = self.execution._row(connection, principal, identifier)
        if row['kind'] not in ('propose', 'repair') or row['status'] != 'completed':
            raise IM.ConflictError('proposal_operation_incomplete')
        if connection.execute("SELECT 1 FROM improvement_events WHERE brain_id=? AND operation='operation_owner_cancel' "
            "AND json_extract(result_json,'$.operation_id')=?", (row['brain_id'], identifier)).fetchone():
            raise IM.ConflictError('proposal_operation_cancelled')
        attempt = self.execution._attempt(connection, row)
        call = self.execution.bound_call(connection, row, attempt)
        context = self.plans.host._row(connection, row['brain_id'], row['experiment_id'])
        pin = self.plans.host._decode(context)['engine_config']
        if (attempt['status'] != 'completed' or attempt['engine_at'] is None or call['engine_at'] != attempt['engine_at']
                or call['status'] != 'ok' or call['engine'] != pin['provider'] or call['model'] != pin['model']):
            raise IM.ConflictError('proposal_call_incomplete')
        records = [dict(item) for item in connection.execute('SELECT * FROM improvement_operation_results '
            'WHERE operation_id=? AND brain_id=? AND attempt=?', (identifier, row['brain_id'], row['attempt']))]
        if len(records) != 1:
            raise IM.ConflictError('proposal_result_unavailable')
        report = self.products.read(principal, identifier, row['attempt'])
        if (IM._hash(report) != records[0]['result_hash'] or attempt['result_json'] != IM._json(report)
                or report['materialization_hash'] != attempt['materialization_hash'] or report['engine_config_hash'] != IM._hash(pin)):
            raise IM.ConflictError('proposal_result_changed')
        checks = {item['id']: item['verdict'] for item in report['checks']}
        if (len(checks) != len(report['checks']) or set(checks) != _REQUIRED | _UNOBSERVED
                or any(checks[key] != 'pass' for key in _REQUIRED)
                or any(checks[key] not in ('pass', 'unknown') for key in _UNOBSERVED)):
            raise PermissionError('proposal_native_evidence_unavailable')
        trace = [dict(item) for item in connection.execute('SELECT * FROM improvement_operation_observations '
            'WHERE operation_id=? AND brain_id=? AND attempt=? ORDER BY sequence', (identifier, row['brain_id'], row['attempt']))]
        if any(item['late'] for item in trace) or [item['payload_hash'] for item in trace] != report['trace_hashes']:
            raise IM.ConflictError('proposal_native_trace_changed')
        raw = self.products.artifact(principal, identifier, row['attempt']).decode('utf-8')
        return {'row': dict(row), 'attempt': dict(attempt), 'call': call, 'record': records[0], 'report': report, 'trace': trace, 'raw': raw}

    def _product_fence(self, connection, principal, product):
        row = self.execution._row(connection, principal, product['row']['id'])
        attempt = self.execution._attempt(connection, row)
        if (dict(row) != product['row'] or dict(attempt) != product['attempt']
                or self.execution.bound_call(connection, row, attempt) != product['call']):
            raise IM.ConflictError('proposal_operation_changed')
        if connection.execute("SELECT 1 FROM improvement_events WHERE brain_id=? AND operation='operation_owner_cancel' "
                "AND json_extract(result_json,'$.operation_id')=?", (row['brain_id'], row['id'])).fetchone():
            raise IM.ConflictError('proposal_operation_cancelled')
        trace = [dict(item) for item in connection.execute('SELECT * FROM improvement_operation_observations '
            'WHERE operation_id=? AND brain_id=? AND attempt=? ORDER BY sequence', (row['id'], row['brain_id'], row['attempt']))]
        if trace != product['trace']:
            raise IM.ConflictError('proposal_native_trace_changed')

    def _read_product(self, principal, identifier):
        with closing(self.store._conn()) as connection:
            return self._product(connection, principal, identifier)

    def _repair(self, principal, begun, product, event_key):
        self._open()
        state, data = begun['state'], begun['data']
        brain, value = _brain(principal), state['prepared'][0]
        repair = {'version': 1, 'kind': 'authorized_structural_repair', 'authorized_input': data,
            'candidate_limit': data['candidate_limit'], 'invalid_output': product['raw'],
            'invalid_artifact_hash': product['report']['artifact']['hash'], 'validation_code': 'invalid_generation_structure',
            'parent_operation_id': product['row']['id'], 'parent_result_id': product['record']['id']}
        blob = self.blobs.write(brain, input_bytes(repair))
        self.plans.host._snapshot_observe(principal, state['prepared'][1])
        with self.store._Tx(self.store) as connection:
            self._product_fence(connection, principal, product)
            self._fence(connection, principal, state, begun['generation'])
            request = {'version': 1, 'experiment_id': value['experiment_id'], 'context_id': value['context_id'],
                'definition_hash': IM._hash(value), 'kind': 'repair', 'role': 'improver', 'purpose': 'improve_propose',
                'candidate_id': None, 'parent_id': product['row']['id'], 'input_hash': blob}
            row = self.execution.records._create_in(connection, principal, request, blob,
                expected_generation=begun['generation'], event_key='proposal-repair-' + IM._hash([brain, event_key]))
            self.assets._event(connection, principal, 'proposal-repair-basis-' + IM._hash([brain, event_key]),
                'proposal_repair_basis', {'parent_id': product['row']['id']},
                {'operation_id': row['operation_id'], 'result_id': product['record']['id'], 'artifact_hash': repair['invalid_artifact_hash'], 'input_hash': blob})
            return row['operation_id'], begun['generation'] + 1

    def _finish(self, connection, principal, payload, event_key, result):
        old = self.assets._replay(connection, _brain(principal), event_key, 'proposal_generate', payload)
        if old is not None:
            return old
        self.assets._event(connection, principal, event_key, 'proposal_generate', payload, result)
        return result

    def _outcome(self, principal, payload, event_key, identifier, status):
        with self.store._Tx(self.store) as connection:
            row = self.execution._row(connection, principal, identifier)
            if row['status'] not in TERMINAL:
                raise IM.ConflictError('proposal_operation_incomplete')
            return self._finish(connection, principal, payload, event_key,
                {'experiment_id': payload['experiment_id'], 'operation_id': identifier, 'status': status, 'candidates': []})

    def _publish(self, principal, payload, event_key, begun, product, batch, basis=None):
        state, brain = begun['state'], _brain(principal)
        self.plans.host._snapshot_observe(principal, state['prepared'][1])
        observed, raw = self.plans.authoring.observe(principal, state['authoring']['target'])
        with self.store._Tx(self.store) as connection:
            old = self.assets._replay(connection, brain, event_key, 'proposal_generate', payload)
            if old is not None:
                return old
            self._fence(connection, principal, state, begun['generation'])
            self._product_fence(connection, principal, product)
            if basis is not None:
                self._product_fence(connection, principal, basis)
            if self._product(connection, principal, product['row']['id']) != product:
                raise IM.ConflictError('proposal_product_changed')
            batch = parse_generation_output(product['raw'], begun['data'])
            candidates = []
            for index, patch in enumerate(batch.get('patches', []), 1):
                candidates.append(self.plans.authoring._stage_in(connection, principal, payload['experiment_id'], patch,
                    event_key='generated-candidate-' + IM._hash([brain, event_key, index]),
                    state=state['authoring'], observed=observed, raw=raw))
            expected = state['candidates'] + [{'id': item['candidate_id'], 'ordinal': item['ordinal']} for item in candidates]
            self.plans.host._snapshot_observe(principal, state['prepared'][1])
            self._fence(connection, principal, state, begun['generation'], candidates=expected)
            self._product_fence(connection, principal, product)
            if basis is not None:
                self._product_fence(connection, principal, basis)
            connection.execute('INSERT INTO improvement_proposal_publications VALUES(?,?,?,?,?,?)',
                (payload['experiment_id'], brain, product['row']['id'], product['record']['id'], IM._hash(batch), time.time()))
            for item in candidates:
                connection.execute('INSERT INTO improvement_generated_candidates VALUES(?,?,?,?,?,?,?)',
                    (payload['experiment_id'], brain, item['ordinal'], item['candidate_id'], product['row']['id'], product['record']['id'], time.time()))
            connection.execute('UPDATE improvement_experiments SET generation=generation+1,updated_at=? WHERE id=? AND brain_id=?',
                               (time.time(), payload['experiment_id'], brain))
            return self._finish(connection, principal, payload, event_key,
                {'experiment_id': payload['experiment_id'], 'operation_id': product['row']['id'], 'result_id': product['record']['id'],
                 'status': 'proposals_staged' if candidates else 'not_a_target_defect', 'candidates': candidates,
                 'batch_hash': IM._hash(batch), 'generation': begun['generation'] + 1,
                 'native_verdict': product['report']['verdict'], 'business_proof': False})

    async def _generate(self, principal, payload, event_key):
        begun = await _settled_call(self._begin, principal, payload, event_key)
        if 'replay' in begun:
            return begun['replay']
        identifier, basis = begun['operation_id'], None
        try:
            for repair in (False, True):
                self._open()
                await self.tasks.start(principal, identifier, expected_generation=1,
                    event_key='proposal-native-' + IM._hash([_brain(principal), event_key, repair]))
                result = await self.tasks.join(principal, identifier)
                self._open()
                if result['status'] != 'completed':
                    return await _settled_call(self._outcome, principal, payload, event_key, identifier, 'native_incomplete')
                product = await _settled_call(self._read_product, principal, identifier)
                try:
                    batch = parse_generation_output(product['raw'], begun['data'])
                except (ValueError, TypeError, PermissionError, KeyError, UnicodeError, RecursionError):
                    if repair:
                        return await _settled_call(self._outcome, principal, payload, event_key, identifier, 'invalid_output')
                    basis = product
                    identifier, begun['generation'] = await _settled_call(self._repair, principal, begun, product, event_key)
                    continue
                return await _settled_call(self._publish, principal, payload, event_key, begun, product, batch, basis)
        finally:
            if self._closed:
                # A slow admission may have committed after tasks.close's snapshot.
                row = await asyncio.to_thread(self.execution.get, principal, identifier)
                if row['status'] not in TERMINAL:
                    await _settled_call(self.execution.cancel, principal, identifier,
                        expected_generation=row['generation'], event_key='proposal-close-' + IM._hash([_brain(principal), identifier]))

    async def generate(self, principal, experiment_id, *, expected_generation, event_key):
        self._bind()
        self._open()
        brain = _brain(principal)
        _identifier(experiment_id)
        _generation(expected_generation)
        if type(event_key) is not str or not 8 <= len(event_key) <= 160:
            raise ValueError('invalid_event_key')
        payload = {'experiment_id': experiment_id, 'expected_generation': expected_generation}
        key, digest = (brain, event_key), IM._hash(payload)
        previous = self._operations.get(key)
        if previous is not None:
            if previous[0] != digest:
                raise IM.ConflictError('proposal_event_conflict')
            return await self.tasks._join(previous[1])
        task = asyncio.create_task(self._generate(principal, payload, event_key))
        self._operations[key] = digest, task, experiment_id, principal

        def finished(done):
            if self._operations.get(key, (None, None))[1] is done:
                self._operations.pop(key)
            self.tasks._consume(done)

        task.add_done_callback(finished)
        return await self.tasks._join(task)

    async def close(self):
        self._bind()
        if self._closing is None:
            self._closed = True
            self._closing = asyncio.create_task(self._close())
        return await self.tasks._join(self._closing)

    async def _close(self):
        failure = None
        try:
            await self.tasks.close()
        except BaseException as error:
            failure = error
        await asyncio.gather(*(entry[1] for entry in list(self._operations.values())), return_exceptions=True)
        if failure is not None:
            raise failure
        return True
