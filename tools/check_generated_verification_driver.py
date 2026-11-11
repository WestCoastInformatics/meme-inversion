#!/usr/bin/env python3
"""Exercise the actual detached verification driver without server access."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import types
from unittest.mock import patch

DRIVER = Path(__file__).parent / 'evidence/run_generated_verification_20261110.py'


def scenario(kind):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        driver = root / 'verification-driver.py'
        driver.write_bytes(DRIVER.read_bytes())
        verifier = root / 'independent-verifier.py'
        verifier.write_bytes(b'# independent verifier fixture\n')
        (root / 'verification-request.json').write_text(json.dumps({
            'verifier_sha256': hashlib.sha256(verifier.read_bytes()).hexdigest()}))
        (root / 'status.json').write_text(json.dumps({'status': 'running'}))
        if kind == 'changed-verifier':
            verifier.write_bytes(b'# changed after request was frozen\n')
        calls, sleeps = [], []

        def save(path, value):
            path.write_text(json.dumps(value))

        def sleep(seconds):
            sleeps.append(seconds)
            if kind == 'complete':
                save(root / 'status.json', {'status': 'complete'})
            elif kind == 'failed':
                save(root / 'status.json', {'status': 'failed', 'error': 'native failure'})

        def execute(command, **options):
            assert json.loads((root / 'status.json').read_text())['status'] == 'complete'
            assert Path(command[-1]).resolve() == verifier.resolve()
            assert options['namespace_user'] == 'current'
            calls.append(command)
            report = {'status': 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION'}
            options['stdout'].write_text('BEGIN_COMMON_REPLAY_RESULT\n' + json.dumps(report) + '\nEND_COMMON_REPLAY_RESULT\n')
            return {'exit_status': 0}

        fake_worker = types.SimpleNamespace(guard=lambda: None, now=lambda: 'fixture-time', save=save)
        fake_time = types.SimpleNamespace(monotonic=lambda: 21601 if kind == 'timeout' and sleeps else 0,
                                          sleep=sleep)
        with patch.dict(sys.modules, inversion_worker=fake_worker,
                        replay_process=types.SimpleNamespace(execute=execute), time=fake_time):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                runpy.run_path(str(driver))
        state = json.loads((root / 'verification-status.json').read_text())
        report = root / 'final-verification.json'
        if kind == 'complete':
            assert len(calls) == 1 and sleeps == [15]
            assert state['status'] == 'complete' and report.is_file()
            assert report.stat().st_mode & 0o777 == 0o444
        else:
            assert not calls and state['status'] == 'failed' and not report.exists()
            assert json.loads((root / 'status.json').read_text())['status'] != 'complete'
            assert 'Traceback' in errors.getvalue()
        return kind


if __name__ == '__main__':
    for name in ('complete', 'failed', 'timeout', 'changed-verifier'):
        print('PASS actual driver: ' + scenario(name))
    print('4 detached verification-driver scenarios passed')
