"""Opt-in actual CLI enforcement on genuine temporary v2 paired materializations.

Preparation/reviewer fixtures are simulated. Native queries use dummy auth and a
local provider; this is not selected-account, TrialRunner or business evidence.
"""
import sys
from pathlib import Path

if '--qualification-worker' in sys.argv:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import ROOT, SERVER  # noqa: F401,E402

import asyncio
import copy
import gzip
import hashlib
import http.server
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_claude as native
import improvement_worker as worker
from improvement_sandbox import FixtureBroker, TrialWorkspace, trial_system_prompt
from improvement_store import _hash, _json
import test_improvement_runtime_qualification as runtime

EVIDENCE = []


def native_view_worker(root):
    """Called inside the existing pinned/dummy/hidden qualification wrapper."""
    payload = json.loads((root / 'view-input.json').read_bytes())
    manifest, pin, trial_id = (payload[key] for key in ('manifest', 'pin', 'trial_id'))
    if manifest['version'] != 2 or manifest['engine_config_hash'] != _hash(pin):
        raise ValueError('qualification_view_configuration_changed')
    if pin['profile_hash'] != native.profile_hash() or pin['cli_path'] != os.environ['JAVIS_TEST_NATIVE_CLI']:
        raise ValueError('qualification_view_profile_changed')

    async def run():
        workspace = TrialWorkspace(root / 'trial-workspaces').prepare(trial_id, 1, manifest)
        actual_root = Path(workspace['path'])
        shutil.copytree(root / '.claude', actual_root / '.claude')
        for name in ('CLAUDE.md', '.mcp.json'):
            shutil.copyfile(root / name, actual_root / name)
        broker = FixtureBroker(manifest['case']['fixtures'], manifest['grant_hash'])

        async def ack():
            pass  # Explicit native-only qualification, never a production call-start claim.

        profile = native.TrialProfile({key: pin[key] for key in ('provider', 'model', 'reasoning', 'cli_path', 'sdk_version')},
            broker, trial_system_prompt(manifest), before_query=ack)
        profile.bind_installation(manifest, workspace, hashlib.sha256(b'qualification-view-capability').hexdigest())
        from claude_cli import claude_engine
        engine = claude_engine(cwd=str(actual_root), tag='improvement:view-native-qualification', model=pin['model'])
        engine.trial_profile = profile
        prompt = _json({'task': manifest['case']['task'], 'fixtures': [
            {'snapshot_id': item['snapshot_id'], 'source': item['source']} for item in manifest['case']['fixtures']]})
        events = []
        async for event in engine.query(prompt):
            events.append(event)
        print(json.dumps({'label': 'synthetic/native-local-fake-provider', 'production_billing': False,
            'events': events, 'broker_events': broker.events, 'denials': profile.denials}), flush=True)

    asyncio.run(run())


def spawn_for_view(manifest, pin, trial_id):
    """Keep the existing blackbox but own the actual paired Trial identities."""
    def spawn(command, **kwargs):
        if '--native-worker' not in command:
            raise AssertionError('Only the gated local qualification worker may be spawned')
        root = Path(command[-1])
        (root / 'view-input.json').write_text(json.dumps({'manifest': manifest, 'pin': pin, 'trial_id': trial_id}), encoding='utf-8')
        command = [sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve()), '--qualification-worker', str(root)]
        original = spawn.original
        workspace = TrialWorkspace(root / 'trial-workspaces')
        with patch.object(subprocess, 'Popen', original):
            lifetime = workspace.acquire_execution(manifest['brain_id'], trial_id, 1)
        if lifetime is None:
            raise RuntimeError('qualification_view_lifetime_unavailable')
        kwargs.update(stdin=subprocess.PIPE, creationflags=worker.process_flags() | (4 if os.name == 'nt' else 0))
        process = original(command, **kwargs)
        try:
            with patch.object(subprocess, 'Popen', original):
                group = worker.WorkerGroup(process.pid, recovery_fences=tuple(handle.name for handle in lifetime), suspended=os.name == 'nt')
        except BaseException:
            process.kill()
            process.communicate(timeout=5)
            workspace.release_execution(lifetime)
            raise
        spawn.roots.append(root)
        process.stdin.write('qualification_start\n')
        process.stdin.flush()
        communicate = process.communicate

        def owned_communicate(*args, **options):
            try:
                stdout, stderr = communicate(*args, **options)
                if stdout:
                    spawn.observations.append(json.loads(stdout))
                return stdout, stderr
            finally:
                group.close()
                with patch.object(subprocess, 'Popen', original):
                    try:
                        workspace.cleanup(trial_id, 1)
                    finally:
                        workspace.release_execution(lifetime)
                    if not workspace.cleanup_proven(trial_id, 1, None):
                        raise AssertionError('Paired native plaintext survived actual job drain')

        process.communicate = owned_communicate
        process.qualification_group = group
        return process

    return spawn


if '--qualification-worker' not in sys.argv:
    import test_improvement_view_sources as sources
    import test_improvement_view_materialization as materialization
    import test_improvement_host_snapshots as host_fixtures
    from test_improvement_experiment_execution import _REAL_RUN, _REAL_POPEN
    from test_improvement_role_qualification import qualification_directory

    @unittest.skipUnless(os.environ.get('JAVIS_TEST_NATIVE_QUALIFICATION_CLI'), 'Explicit pinned local native qualification only')
    class ViewNativeQualificationTests(sources.SourceFixture, unittest.IsolatedAsyncioTestCase):
        request = materialization.ViewMaterializationTests.request
        load = materialization.ViewMaterializationTests.load
        bound = materialization.ViewMaterializationTests.bound
        live_request = materialization.ViewMaterializationTests.live_request
        materialize = materialization.ViewMaterializationTests.materialize

        def setUp(self):
            binary = runtime.candidate(os.environ['JAVIS_TEST_NATIVE_QUALIFICATION_CLI'])
            self.pin = {'version': 1, 'provider': 'anthropic-cli', 'engine_id': 'claude-sdk',
                'model': 'claude-opus-5-5', 'reasoning': 'medium', 'cli_path': str(binary),
                'cli_hash': runtime.CANDIDATE_HASH, 'cli_version': runtime.CANDIDATE_VERSION,
                'sdk_version': runtime.SDK_VERSION, 'profile_version': native.PROFILE_VERSION, 'profile_hash': native.profile_hash()}
            original = host_fixtures.HostSnapshotTests.setUp

            def selected_fixture(fixture):
                original(fixture)
                # AssociationTests captures its NEW context after this setup returns.
                # Preserve the unrelated original fixture context without relabelling it.
                fixture.engine = copy.deepcopy(self.pin)

            with patch.object(host_fixtures.HostSnapshotTests, 'setUp', selected_fixture):
                sources.SourceFixture.setUp(self)

        async def test_actual_pair_native_installations_are_distinct_exact_and_isolated(self):
            trials, binding = self.bound()
            original = self.f.f.f.skill.read_bytes()
            before_profile = native.profile_hash()
            materials, sessions = {}, []
            for position in (0, 1):
                request, claimed, manifest = self.materialize(trials, binding, position, 'native-view-materialize-' + str(position))
                self.assertEqual(request['engine_config'], self.pin)
                self.assertEqual(manifest['engine_config_hash'], _hash(self.pin))
                materials[request['variant']] = (claimed['trial_id'], manifest)
            for variant, (trial_id, manifest) in materials.items():
                started, bodies = time.monotonic(), []
                spawn = spawn_for_view(manifest, self.pin, trial_id)
                real_server, real_mkdtemp = http.server.ThreadingHTTPServer, tempfile.mkdtemp
                fixture = manifest['case']['fixtures'][0]

                with qualification_directory(prefix='view-native-qualification-') as scratch:
                    def directory(*args, **kwargs):
                        if kwargs.get('prefix') == 'improvement-native-local-':
                            return str(scratch)
                        return real_mkdtemp(*args, **kwargs)

                    def server(address, handler):
                        post, reply = handler.do_POST, handler.reply

                        def observed_post(instance):
                            raw = instance.rfile.read(min(int(instance.headers.get('Content-Length', 0)), 4_000_000))
                            instance.rfile = io.BytesIO(raw)
                            content = gzip.decompress(raw) if instance.headers.get('Content-Encoding') == 'gzip' else raw
                            bodies.append((instance.path.split('?', 1)[0], json.loads(content or b'{}')))
                            return post(instance)

                        def actual_fixture_reply(instance, status, body, content_type='application/json'):
                            if content_type == 'text/event-stream':
                                lines = []
                                for line in body.decode().splitlines(keepends=True):
                                    if line.startswith('data: '):
                                        value = json.loads(line[6:])
                                        delta = value.get('delta', {})
                                        if delta.get('type') == 'input_json_delta':
                                            arguments = json.loads(delta['partial_json'])
                                            if arguments.get('snapshot_id') == 'fixture-allowed':
                                                arguments.update(snapshot_id=fixture['snapshot_id'], source_version=fixture['source']['source_version'])
                                                delta['partial_json'] = json.dumps(arguments)
                                        line = 'data: ' + json.dumps(value) + '\n'
                                    lines.append(line)
                                body = ''.join(lines).encode()
                            return reply(instance, status, body, content_type)

                        handler.do_POST, handler.reply = observed_post, actual_fixture_reply
                        return real_server(address, handler)

                    # Reuse the full pinned blackbox: ambient plugin/skill/agent,
                    # outside Read/Bash/Web/MCP, Task/Agent/Skill/deferred tools,
                    # actual hidden SDK launches, job exit and transcript checks.
                    with patch.object(subprocess, 'run', _REAL_RUN), patch.object(subprocess, 'Popen', _REAL_POPEN), \
                            patch.object(runtime, '_spawn', spawn), \
                            patch.object(http.server, 'ThreadingHTTPServer', side_effect=server), \
                            patch.object(tempfile, 'mkdtemp', side_effect=directory):
                        method = runtime.CandidateNativeTests.test_candidate_reuses_full_native_blackbox_with_extra_tool_and_ambient_canaries
                        method(runtime.CandidateNativeTests())
                    self.assertEqual(len(spawn.observations), 1)
                    events = spawn.observations[0]['events']
                    receipts = [event['receipt'] for event in events if event['type'] == 'installation_receipt']
                    self.assertEqual(len(receipts), 1)
                    receipt = receipts[0]
                    self.assertEqual(receipt['version'], 2)
                    self.assertEqual(receipt['effective_view'], manifest['effective_view'])
                    self.assertEqual(receipt['trial_id'], trial_id)
                    self.assertEqual(receipt['engine_config_hash'], _hash(self.pin))
                    self.assertEqual([{key: asset[key] for key in ('id', 'path', 'hash')} for asset in receipt['asset_revisions']],
                        [{key: asset[key] for key in ('id', 'path', 'hash')} for asset in manifest['assets']])
                    sessions.append(receipt['session_id'])
                    requests = [body for path, body in bodies if path == '/v1/messages']
                    self.assertEqual(len(requests), 2)
                    system = '\n'.join(block.get('text', '') for block in requests[0]['system'])
                    self.assertIn(trial_system_prompt(manifest), system)
                    self.assertNotIn('private-owner-answer', json.dumps(requests))
                    self.assertNotIn('"expected"', system)
                    EVIDENCE.append({'scenario': 'actual-v2-view-native-local-enforcement', 'variant': variant,
                        'production_billing': False, 'profile_hash': before_profile,
                        'seconds': round(time.monotonic() - started, 3), 'view': manifest['effective_view'],
                        'manifest_hash': _hash(manifest), 'engine_config_hash': _hash(self.pin),
                        'receipt_hash': _hash(receipt), 'request_hashes': [_hash(body) for body in requests],
                        'native_session_hash': hashlib.sha256(receipt['session_id'].encode()).hexdigest(),
                        'all_owned_processes_closed': True, 'plaintext_cleaned_after_job_drain': True,
                        'observed_reasoning': 'unknown', 'observed_asset_use': 'unknown'})
                self.assertFalse(scratch.exists())
            self.assertNotEqual(sessions[0], sessions[1])
            self.assertNotEqual(materials['baseline'][1]['assets'], materials['candidate'][1]['assets'])
            self.assertEqual(materials['baseline'][1]['baseline_context'], materials['candidate'][1]['baseline_context'])
            self.assertEqual(materials['baseline'][1]['case'], materials['candidate'][1]['case'])
            self.assertEqual(self.f.f.f.skill.read_bytes(), original)
            self.assertEqual(native.profile_hash(), before_profile)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--qualification-worker':
        import test_improvement_native as existing
        with patch.object(existing, 'worker', side_effect=native_view_worker):
            runtime.qualification_worker(Path(sys.argv[2]))
    else:
        result = unittest.main(exit=False)
        if EVIDENCE and os.environ.get('JAVIS_TEST_NATIVE_VIEW_QUALIFICATION_EVIDENCE'):
            Path(os.environ['JAVIS_TEST_NATIVE_VIEW_QUALIFICATION_EVIDENCE']).write_text(json.dumps({
                'version': 1, 'evidence_class': 'technical', 'label': 'native-view-local-enforcement-only',
                'passed': result.result.wasSuccessful(), 'profile_hash': native.profile_hash(),
                'production_billing': False, 'selected_account_calls': 0, 'native_trialrunner_proof': False,
                'business_proof': False, 'positive_final_exercised': False, 'scenarios': EVIDENCE}, indent=2) + '\n', encoding='utf-8')
        raise SystemExit(not result.result.wasSuccessful())
