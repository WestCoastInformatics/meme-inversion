#!/usr/bin/env python3
"""Run the independent verifier offline and retain its result across VPN loss."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

import inversion_worker as worker
from replay_process import execute

CONTROL = Path(__file__).resolve().parent
state = {'status': 'preflight', 'started_at': worker.now()}


def save():
    state['updated_at'] = worker.now()
    worker.save(CONTROL / 'verification-status.json', state)


def wait_for_batch():
    """Wait for the existing controller; never launch or replace its jobs."""
    deadline = time.monotonic() + 21600
    state.update(status='waiting-for-native-batch')
    save()
    while True:
        observed = json.loads((CONTROL / 'status.json').read_text())
        if observed['status'] == 'complete':
            return
        if observed['status'] != 'running':
            raise RuntimeError('Native batch is not running or complete; verification refused')
        if time.monotonic() >= deadline:
            raise RuntimeError('Native batch wait limit reached; existing jobs and evidence are unchanged')
        time.sleep(15)


try:
    worker.guard()
    request = json.loads((CONTROL / 'verification-request.json').read_text())
    entry = CONTROL / 'independent-verifier.py'
    assert hashlib.sha256(entry.read_bytes()).hexdigest() == request['verifier_sha256']
    assert not (CONTROL / 'final-verification.json').exists()
    wait_for_batch()
    state.update(status='verifying', verifier_sha256=request['verifier_sha256'])
    save()
    metrics = execute([sys.executable, '-B', str(entry)], cwd=CONTROL,
                      stdout=CONTROL / 'verification.stdout.log', stderr=CONTROL / 'verification.stderr.log',
                      env=os.environ.copy(), timeout=1800, namespace_user='current',
                      progress=lambda values: worker.save(CONTROL / 'verification-progress.json', values))
    worker.save(CONTROL / 'verification-metrics.json', metrics)
    if metrics['exit_status'] != 0:
        raise RuntimeError('Independent verification failed; see retained stdout/stderr')
    raw = (CONTROL / 'verification.stdout.log').read_text()
    begin, end = 'BEGIN_COMMON_REPLAY_RESULT\n', '\nEND_COMMON_REPLAY_RESULT'
    assert raw.count(begin) == raw.count(end) == 1
    result = json.loads(raw.split(begin, 1)[1].split(end, 1)[0])
    assert result['status'] == 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION'
    with (CONTROL / 'final-verification.json').open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    (CONTROL / 'final-verification.json').chmod(0o444)
    state.update(status='complete', result=result['status'], completed_at=worker.now())
except BaseException as error:
    state.update(status='failed', error=str(error), completed_at=worker.now())
    traceback.print_exc()
finally:
    save()
