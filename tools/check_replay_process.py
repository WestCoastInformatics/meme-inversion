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
        assert command[:4] == ['unshare', '--user', '--map-root-user', '--net']
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
    return passed


if __name__ == '__main__':
    checks = check()
    for label in checks:
        print('PASS ' + label)
    print(str(len(checks)) + ' process-control checks passed')
