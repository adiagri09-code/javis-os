"""Retained Windows/NTFS read-sharing handles and observed executable bytes.

Component only: the native guardian must own this through actual job drain before
it can attest a launch. Sharing does not exclude metadata-only mutation; a fresh
snapshot detects observed drift but does not prove future loaded-image identity.
No account configuration or model input enters here.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import threading


class _FileInfo(ctypes.Structure):
    _fields_ = [('attributes', wintypes.DWORD), ('creation', wintypes.FILETIME),
        ('access', wintypes.FILETIME), ('write', wintypes.FILETIME), ('volume', wintypes.DWORD),
        ('size_high', wintypes.DWORD), ('size_low', wintypes.DWORD), ('links', wintypes.DWORD),
        ('index_high', wintypes.DWORD), ('index_low', wintypes.DWORD)]


@lru_cache(maxsize=1)
def _kernel():
    if os.name != 'nt':
        raise OSError('native_image_windows_required')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.GetVolumeInformationByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetVolumeInformationByHandleW.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.ReadFile.restype = wintypes.BOOL
    return kernel


def _open(path):
    # Real read access is required: metadata-only opens bypass sharing checks.
    handle = _kernel().CreateFileW(str(path), 0x80000000, 1, None, 3, 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _close(handle):
    if not _kernel().CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _info(handle):
    value = _FileInfo()
    if not _kernel().GetFileInformationByHandle(handle, ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value


def _identity(value):
    return (value.volume, value.index_high, value.index_low, value.size_high, value.size_low,
        value.attributes, value.write.dwHighDateTime, value.write.dwLowDateTime)


def _final_path(handle):
    buffer = ctypes.create_unicode_buffer(32768)
    count = _kernel().GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if not 0 < count < len(buffer):
        raise OSError('native_image_path_unavailable')
    path = buffer.value
    if path.startswith('\\\\?\\'):
        path = path[4:]
    return os.path.normcase(os.path.normpath(path))


class ImageReadGuard:
    """Own every ancestor and the exact hashed leaf until successful explicit close."""

    def __init__(self, path, expected_hash):
        self._handles = []
        self._bindings = []
        self._lock = threading.RLock()
        self._closed = False
        self._closing = False
        if type(expected_hash) is not str or re.fullmatch('[0-9a-f]{64}', expected_hash) is None:
            raise ValueError('native_image_hash_invalid')
        path = Path(path)
        if (not path.is_absolute() or len(path.drive) != 2 or path.drive[1] != ':'
                or any(part in ('.', '..') or part.endswith((' ', '.')) or ':' in part for part in path.parts[1:])):
            raise ValueError('native_image_path_unsupported')
        self._path = path
        try:
            for component in [*reversed(path.parents), path]:
                handle = _open(component)
                self._handles.append(handle)
                value = _info(handle)
                if value.attributes & 0x400:
                    raise ValueError('native_image_reparse_forbidden')
                if bool(value.attributes & 0x10) != (component != path):
                    raise ValueError('native_image_kind_invalid')
                if _final_path(handle) != os.path.normcase(os.path.normpath(str(component))):
                    raise ValueError('native_image_namespace_changed')
                self._bindings.append((component, (value.volume, value.index_high, value.index_low)))
            leaf = self._handles[-1]
            filesystem = ctypes.create_unicode_buffer(260)
            serial, maximum, flags = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            if not _kernel().GetVolumeInformationByHandleW(leaf, None, 0, ctypes.byref(serial),
                    ctypes.byref(maximum), ctypes.byref(flags), filesystem, len(filesystem)):
                raise ctypes.WinError(ctypes.get_last_error())
            if filesystem.value != 'NTFS':
                raise ValueError('native_image_filesystem_unsupported')
            before = _info(leaf)
            size = (before.size_high << 32) | before.size_low
            if not 0 < size <= 512 * 1024 * 1024:
                raise ValueError('native_image_size_invalid')
            digest, total = hashlib.sha256(), 0
            buffer, count = ctypes.create_string_buffer(1024 * 1024), wintypes.DWORD()
            while True:
                if not _kernel().ReadFile(leaf, buffer, len(buffer), ctypes.byref(count), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not count.value:
                    break
                total += count.value
                if total > size:
                    raise ValueError('native_image_size_changed')
                digest.update(buffer.raw[:count.value])
            if total != size or _identity(_info(leaf)) != _identity(before):
                raise ValueError('native_image_identity_changed')
            if digest.hexdigest() != expected_hash:
                raise ValueError('native_image_hash_mismatch')
            self._snapshot = {'sha256': expected_hash, 'filesystem': filesystem.value,
                'volume_serial': serial.value, 'identity': list(_identity(before)), 'size': size,
                'path': str(path), 'ancestor_count': len(self._handles) - 1,
                'proof_basis': 'retained_read_sharing_and_observed_identity',
                'metadata_mutation_exclusion': 'unknown', 'loaded_image_identity': 'unknown'}
        except BaseException as error:
            try:
                self.close()
            except OSError as cleanup:
                cleanup.guard = self  # Retain retryable ownership on an unproven close.
                raise cleanup from error
            raise

    def snapshot(self):
        with self._lock:
            if self._closed or self._closing:
                raise ValueError('native_image_guard_closed')
            for handle, (component, identity) in zip(self._handles, self._bindings):
                value = _info(handle)
                if (value.attributes & 0x400 or (value.volume, value.index_high, value.index_low) != identity
                        or _final_path(handle) != os.path.normcase(os.path.normpath(str(component)))):
                    raise ValueError('native_image_identity_changed')
            if list(_identity(_info(self._handles[-1]))) != self._snapshot['identity']:
                raise ValueError('native_image_identity_changed')
            return {**self._snapshot, 'identity': list(self._snapshot['identity'])}

    def close(self):
        with self._lock:
            self._closing = True  # A partial close irreversibly invalidates attestation.
            while self._handles:
                _close(self._handles[-1])
                self._handles.pop()  # An unsuccessful close retains ownership.
            self._closed = True

    def __enter__(self):
        try:
            self.snapshot()
        except BaseException as error:
            try:
                self.close()
            except OSError as cleanup:
                cleanup.guard = self
                raise cleanup from error
            raise
        return self

    def __exit__(self, *_):
        try:
            self.close()
        except OSError as cleanup:
            cleanup.guard = self
            raise
