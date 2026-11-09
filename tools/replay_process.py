#!/usr/bin/env python3
"""Execute a dev replay stage offline with bounded resources and retained logs."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time


@contextmanager
def runtime_lock(root, inherited=None):
    """Keep one shared-runtime lock across preparation, conversion and comparison."""
    path = Path(root) / '.replay-runtime.lock'
    if path.is_symlink():
        raise RuntimeError('Runtime lock must not be a symlink')
    if inherited is not None:
        expected, actual = path.stat(), os.fstat(inherited.fileno())
        if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
            raise RuntimeError('Inherited runtime lock belongs to another file')
        fcntl.flock(inherited, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield inherited
    else:
        with path.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield handle


def available_memory():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('Cannot measure memory availability')


def stop(process):
    code = process.poll()
    if code is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    elif code:
        # A failed shell/Perl parent may have left a sort child behind.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def group_resident(group):
    total = 0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) != group:
                continue
            status = (entry / 'status').read_text()
            total += int(next(x for x in status.splitlines() if x.startswith('VmRSS:')).split()[1]) * 1024
        except (OSError, StopIteration):
            pass
    return total


def execute(command, *, cwd, stdout, stderr, env, progress, timeout=14400, namespace_user='root'):
    if namespace_user not in ('root', 'current'):
        raise ValueError('Unsupported user-namespace mapping')
    started = time.monotonic()
    peak = 0
    minimum_available = available_memory()
    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (22 * 1024 ** 3, 22 * 1024 ** 3))
    with Path(stdout).open('xb') as out, Path(stderr).open('xb') as err:
        mapping = '--map-root-user' if namespace_user == 'root' else '--map-current-user'
        process = subprocess.Popen(['unshare', '--user', mapping, '--net'] + command,
                                   cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   start_new_session=True, preexec_fn=limit)
        try:
            while process.poll() is None:
                available = available_memory()
                minimum_available = min(minimum_available, available)
                if available < 2 * 1024 ** 3 or shutil.disk_usage(cwd).free < 12 * 1024 ** 3:
                    raise RuntimeError('Replay stopped at the dev capacity reserve')
                if time.monotonic() - started > timeout:
                    raise RuntimeError('Stage timeout; partial output and logs retained')
                peak = max(peak, group_resident(process.pid))
                progress({'pid': process.pid, 'elapsed_seconds': round(time.monotonic() - started),
                          'sampled_peak_resident_bytes': peak, 'available_memory_bytes': available})
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            stop(process)
    result = {'exit_status': process.returncode, 'seconds': round(time.monotonic() - started, 2),
              'sampled_peak_process_group_resident_bytes': peak, 'minimum_available_memory_bytes': minimum_available,
              'network': 'disabled', 'namespace_user': namespace_user,
              'address_space_limit_bytes_per_child': 22 * 1024 ** 3}
    if process.returncode:
        raise RuntimeError('Stage exited ' + str(process.returncode) + '; see ' + str(stderr))
    return result
