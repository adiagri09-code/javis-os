"""Real Windows executable-file guards; own files, no CLI/model/account execution."""
from _paths import ROOT, SERVER  # noqa: F401

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.name == 'nt', 'Windows native file sharing')
class NativeImageGuardTests(unittest.TestCase):
    def setUp(self):
        import improvement_native_image as image
        self.image = image
        self.temp = tempfile.TemporaryDirectory(prefix='image-guard-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'parent' / 'selected.exe'
        self.path.parent.mkdir()
        self.path.write_bytes(b'OWNED_INERT_BYTES')
        self.digest = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def guard(self, digest=None):
        return self.image.ImageReadGuard(self.path, digest or self.digest)

    def junction(self, path, target):
        self.assertTrue(path.is_relative_to(self.root) and target.is_relative_to(self.root))
        process = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(path), str(target)],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(path.is_junction())

    def test_exact_bytes_are_held_until_close_then_writer_can_succeed(self):
        with self.guard() as guard:
            self.assertEqual(guard.snapshot()['sha256'], self.digest)
            self.assertEqual(guard.snapshot()['filesystem'], 'NTFS')
            with self.assertRaises(PermissionError):
                self.path.write_bytes(b'CHANGED')
        self.path.write_bytes(b'CHANGED')
        guard.close()
        with self.assertRaisesRegex(ValueError, 'closed'):
            guard.snapshot()

    def test_replacement_and_ancestor_rename_are_denied_then_released(self):
        replacement = self.root / 'replacement.exe'
        replacement.write_bytes(b'REPLACEMENT')
        renamed = self.root / 'renamed'
        with self.guard():
            with self.assertRaises(PermissionError):
                os.replace(replacement, self.path)
            with self.assertRaises(PermissionError):
                self.path.parent.rename(renamed)
        self.path.parent.rename(renamed)
        os.replace(replacement, renamed / self.path.name)

    def test_hash_mismatch_closes_every_guard_before_returning_error(self):
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.guard('0' * 64)
        self.path.parent.rename(self.root / 'released')
        self.root.rename(self.root.with_name(self.root.name + '-released'))
        self.root.with_name(self.root.name + '-released').rename(self.root)

    def test_preexisting_file_writer_refuses_guard_without_leaking_ancestors(self):
        with self.path.open('r+b'):
            with self.assertRaises(OSError):
                self.guard()
        self.path.parent.rename(self.root / 'released')

    def test_existing_junction_ancestor_is_refused_even_for_exact_bytes(self):
        real = self.root / 'real'
        self.path.parent.rename(real)
        self.junction(self.path.parent, real)
        try:
            with self.assertRaisesRegex(ValueError, 'reparse'):
                self.guard()
        finally:
            os.rmdir(self.path.parent)
            real.rename(self.path.parent)

    def test_ancestor_guards_block_a_swap_during_later_component_acquisition(self):
        original = self.image._open
        parent, held = self.path.parent, self.root / 'held'
        state = {'attempted': False, 'blocked': False}

        def changed(path):
            if Path(path) == parent and not state['attempted']:
                state['attempted'] = True
                try:
                    parent.rename(held)
                except PermissionError:
                    state['blocked'] = True
                else:
                    held.rename(parent)
            return original(path)

        with patch.object(self.image, '_open', side_effect=changed), self.guard():
            self.assertEqual(state, {'attempted': True, 'blocked': True})
        parent.rename(held)  # Same attack becomes possible after ownership ends.
        held.rename(parent)

    def test_swap_before_first_handle_is_detected_on_actual_reparse_handle(self):
        original = self.image._open
        parent, held = self.path.parent, self.root / 'held'
        state = {'swapped': False}

        def changed(path):
            if not state['swapped']:
                parent.rename(held)
                self.junction(parent, held)
                state['swapped'] = True
            return original(path)

        try:
            with patch.object(self.image, '_open', side_effect=changed), \
                    self.assertRaisesRegex(ValueError, 'reparse'):
                self.guard()
        finally:
            if state['swapped']:
                os.rmdir(parent)
                held.rename(parent)

    def test_hash_reads_the_retained_handle_instead_of_reopening_a_path(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('Path hash is not retained-handle proof')):
            with self.guard() as guard:
                self.assertEqual(guard.snapshot()['sha256'], self.digest)

    def test_failed_close_retains_ownership_for_a_successful_retry(self):
        guard = self.guard()
        with patch.object(self.image, '_close', side_effect=OSError('controlled_close_failure')):
            with self.assertRaisesRegex(OSError, 'controlled_close_failure'):
                guard.close()
        self.assertFalse(guard._closed)
        self.assertTrue(guard._handles)
        with self.assertRaises(PermissionError):
            self.path.write_bytes(b'CHANGED')
        guard.close()
        self.path.write_bytes(b'CHANGED')

    def test_partial_close_cannot_return_a_guarded_snapshot(self):
        guard, original = self.guard(), self.image._close
        calls = []

        def partial(handle):
            calls.append(handle)
            if len(calls) == 2:
                raise OSError('controlled_partial_close')
            return original(handle)

        try:
            with patch.object(self.image, '_close', side_effect=partial):
                with self.assertRaisesRegex(OSError, 'controlled_partial_close'):
                    guard.close()
            self.path.write_bytes(b'NO_LONGER_GUARDED')
            with self.assertRaisesRegex(ValueError, 'closed|closing'):
                guard.snapshot()
        finally:
            guard.close()

    def test_closed_guard_cannot_be_reentered_as_an_owned_context(self):
        guard = self.guard()
        guard.close()
        with self.assertRaisesRegex(ValueError, 'closed'):
            with guard:
                self.fail('A closed guard cannot claim an active ownership scope')

    def test_entry_failure_releases_handles_without_requiring_an_exit_call(self):
        import stat
        guard = self.guard()
        try:
            self.path.chmod(stat.S_IREAD)
            with self.assertRaisesRegex(ValueError, 'identity'):
                with guard:
                    self.fail('Drift must refuse entry')
            self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
            self.path.write_bytes(b'RELEASED')
        finally:
            self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
            guard.close()

    def test_entry_cleanup_failure_retains_guard_on_exception_for_retry(self):
        import stat
        guard = self.guard()
        try:
            self.path.chmod(stat.S_IREAD)
            with patch.object(self.image, '_close', side_effect=OSError('entry_cleanup_failed')):
                with self.assertRaisesRegex(OSError, 'entry_cleanup_failed') as caught:
                    with guard:
                        self.fail('Drift must refuse entry')
            self.assertIs(caught.exception.guard, guard)
        finally:
            self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
            guard.close()

    def test_exit_cleanup_failure_retains_guard_on_exception_for_retry(self):
        guard = self.guard()
        try:
            with patch.object(self.image, '_close', side_effect=OSError('exit_cleanup_failed')):
                with self.assertRaisesRegex(OSError, 'exit_cleanup_failed') as caught:
                    with guard:
                        pass
            self.assertIs(caught.exception.guard, guard)
        finally:
            guard.close()

    def test_snapshot_detects_metadata_drift_but_does_not_claim_mutation_exclusion(self):
        import stat
        with self.guard() as guard:
            try:
                self.path.chmod(stat.S_IREAD)
                with self.assertRaisesRegex(ValueError, 'identity'):
                    guard.snapshot()
            finally:
                self.path.chmod(stat.S_IREAD | stat.S_IWRITE)
            self.assertEqual(guard.snapshot()['metadata_mutation_exclusion'], 'unknown')
            self.assertEqual(guard.snapshot()['loaded_image_identity'], 'unknown')

    def test_other_child_file_writes_still_work_during_guard(self):
        unrelated = self.path.parent / 'other.bin'
        with self.guard():
            unrelated.write_bytes(b'UNRELATED')
            unrelated.unlink()
            self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), self.digest)

    def test_leaf_junction_or_directory_cannot_masquerade_as_executable(self):
        self.path.unlink()
        self.path.mkdir()
        with self.assertRaisesRegex(ValueError, 'kind'):
            self.guard()


if __name__ == '__main__':
    unittest.main()
