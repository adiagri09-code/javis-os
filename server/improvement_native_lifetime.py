"""Windows native cleanup ownership survives the single querying host's death.

Only this supervisor owns the native job. EOF from its host requests termination;
durable fences disappear only after actual process-exit waits. A supervisor crash
leaves fences in place: recovery must remain blocked rather than guess quiescence.
No model input, account configuration or auth is sent to this supervisor.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path


def fence_directory(lock_path):
    return Path(str(lock_path) + '.native')


def fence_busy(lock_path):
    from improvement_blobs import check_ancestry
    directory = fence_directory(lock_path)
    check_ancestry(directory)
    return directory.exists() and any(directory.iterdir())


class NativeLifetime:
    def __init__(self, pid, fences, *, suspended=False):
        from improvement_sandbox import worker_environment
        import winproc
        self._lock = threading.Lock()
        self._closed = False
        paths = [str(Path(value).absolute()) for value in fences]
        if len(paths) != 2 or len(set(paths)) != 2:
            raise ValueError('native_lifetime_fences_invalid')
        self.process = subprocess.Popen([sys.executable, '-I', '-X', 'utf8', str(Path(__file__).resolve())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parent, env=worker_environment(Path(paths[0]).parent), creationflags=winproc.no_window())
        try:
            self.process.stdin.write((json.dumps({'pid': pid, 'locks': paths, 'suspended': suspended}) + '\n').encode())
            self.process.stdin.flush()
            ready = json.loads(self.process.stdout.readline(1024))
            if (type(ready) is not dict or set(ready) != {'type', 'pid'} or ready['type'] != 'ready'
                    or type(ready['pid']) is not int or ready['pid'] <= 0):
                raise ValueError('native_lifetime_ready_invalid')
            self.guardian_pid = ready['pid']
        except BaseException:
            self.process.stdin.close()
            self.process.wait()
            self.process.stdout.close()
            raise OSError('native_lifetime_start_unproven') from None

    def inventory(self):
        with self._lock:
            self.process.stdin.write(b'inventory\n')
            self.process.stdin.flush()
            value = json.loads(self.process.stdout.readline(128 * 1024))
            if type(value) is not list or any(type(pid) is not int or pid <= 0 for pid in value):
                raise OSError('native_lifetime_inventory_unproven')
            return value

    def close(self):
        from improvement_worker import WorkerGroupCleanupError
        with self._lock:
            if self._closed:
                return
            if not self.process.stdin.closed:
                self.process.stdin.close()
            result = self.process.stdout.readline(1024)
            code = self.process.wait()
            if result != b'closed\n' or code != 0:
                raise WorkerGroupCleanupError('native_lifetime_cleanup_unproven')
            self.process.stdout.close()
            self._closed = True


def supervise():
    from improvement_worker import WorkerGroup, WorkerGroupCleanupError
    from improvement_blobs import check_ancestry
    from improvement_sandbox import _private_directory
    packet = json.loads(sys.stdin.buffer.readline(32768))
    if (type(packet) is not dict or set(packet) != {'pid', 'locks', 'suspended'} or type(packet['suspended']) is not bool
            or type(packet['pid']) is not int or packet['pid'] <= 0
            or type(packet['locks']) is not list or len(packet['locks']) != 2):
        raise ValueError('native_lifetime_request_invalid')
    paths = [Path(value) for value in packet['locks']]
    if (any(not path.is_absolute() or path.suffix != '.lock' for path in paths)
            or len(set(paths)) != 2):
        raise ValueError('native_lifetime_fences_invalid')
    token = uuid.uuid4().hex + '.fence'
    markers = []
    group = WorkerGroup(packet['pid'])
    try:
        for path in paths:
            directory = fence_directory(path)
            check_ancestry(directory)
            _private_directory(directory)
            marker = directory / token
            with marker.open('xb') as output:
                output.write(b'native-cleanup-unproven\n')
                output.flush()
                os.fsync(output.fileno())
            markers.append(marker)
        if packet['suspended']:
            group._resume_initial_thread()
        emit(json.dumps({'type': 'ready', 'pid': os.getpid()}))  # Only now may the host release the worker input gate.
        for line in sys.stdin.buffer:
            if line != b'inventory\n':
                raise ValueError('native_lifetime_control_invalid')
            emit(json.dumps(group.inventory()))
    finally:
        while True:
            try:
                group.close()
                break
            except WorkerGroupCleanupError:
                time.sleep(.05)
        for marker in markers:
            marker.unlink()  # Any failure leaves recovery fail-closed.
    emit('closed')


def emit(value):
    sys.stdout.buffer.write(value.encode('ascii') + b'\n')
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    supervise()
