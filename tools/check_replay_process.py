#!/usr/bin/env python3
"""Run tiny private child processes to check stage failure and reserve handling."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import replay_process as replay


def check():
    passed = []
    original = subprocess.Popen
    children = []
    def private_child(command, **kwargs):
        assert command[:2] == ['unshare', '--user'] and command[2] in ('--map-root-user', '--map-current-user') and command[3] == '--net'
        # The test host need not support Linux namespaces. Exercise the real
        # process-group/resource/error logic around only these synthetic jobs.
        if sys.platform != 'linux':
            kwargs.pop('preexec_fn')  # Linux RLIMIT_AS is exercised on dev.
        child = original(command[4:], **kwargs)
        children.append(child)
        return child
    with tempfile.TemporaryDirectory(prefix='replay-process-check-') as directory:
        root = Path(directory)
        for mode in ['success', 'failure', 'capacity']:
            output, errors = root / (mode + '.out'), root / (mode + '.err')
            code = "print('fixture result')" if mode == 'success' else ("import sys;sys.stderr.write('fixture failure');sys.exit(7)" if mode == 'failure' else 'import time;time.sleep(60)')
            available = (1 if mode == 'capacity' else 30) * 1024 ** 3
            with patch.object(replay.subprocess, 'Popen', side_effect=private_child), patch.object(replay, 'available_memory', return_value=available), patch.object(replay, 'group_resident', return_value=1024), patch.object(replay.shutil, 'disk_usage', return_value=type('Space', (), {'free': 80 * 1024 ** 3})()):
                try:
                    result = replay.execute([sys.executable, '-c', code], cwd=root, stdout=output, stderr=errors,
                                            env=dict(os.environ), progress=lambda metrics: None, timeout=20)
                except RuntimeError:
                    if mode == 'success':
                        raise
                    if mode == 'failure':
                        assert errors.read_text() == 'fixture failure'
                        passed.append('nonzero stage rejected with diagnostic log retained')
                    else:
                        assert children[-1].poll() is not None
                        passed.append('capacity reserve stops the private process group')
                else:
                    assert mode == 'success' and result['exit_status'] == 0 and output.read_text() == 'fixture result\n'
                    passed.append('successful stage retains exact output and zero exit')
        with patch.object(replay.subprocess, 'Popen', side_effect=private_child), patch.object(replay, 'available_memory', return_value=30 * 1024 ** 3), patch.object(replay, 'group_resident', return_value=1024), patch.object(replay.shutil, 'disk_usage', return_value=type('Space', (), {'free': 80 * 1024 ** 3})()):
            result = replay.execute([sys.executable, '-c', "print('current mapping')"], cwd=root, stdout=root/'current.out', stderr=root/'current.err',
                                    env=dict(os.environ), progress=lambda metrics: None, timeout=20, namespace_user='current')
            assert result['namespace_user'] == 'current'
            passed.append('current-user namespace is explicitly selected and recorded')
        try:
            replay.execute([], cwd=root, stdout=root/'invalid.out', stderr=root/'invalid.err', env=dict(os.environ), progress=lambda metrics: None, namespace_user='unreviewed')
        except ValueError:
            assert not (root/'invalid.out').exists()
            passed.append('unknown namespace mapping rejected before any stage starts')
        else:raise AssertionError('Unknown namespace mapping accepted')
    return passed


if __name__ == '__main__':
    checks = check()
    for label in checks:
        print('PASS ' + label)
    print(str(len(checks)) + ' process-control checks passed')
