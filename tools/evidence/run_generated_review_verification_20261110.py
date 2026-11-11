#!/usr/bin/env python3
"""Wait for the bounded MTH review, then independently verify both source runs."""
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
REVIEW = worker.ROOT / 'qa/replay-requests/common-mth-generated-finalization-20261110'
state = {'status': 'preflight', 'started_at': worker.now()}
authorized = False


def save():
    state['updated_at'] = worker.now()
    worker.save(CONTROL / 'verification-status.json', state)


try:
    worker.guard()
    assert CONTROL.name == 'generated-settings-reviewed-verification-20261110.controller'
    assert CONTROL.resolve() == CONTROL and not (CONTROL / 'verification-status.json').exists()
    authorized = True
    request = json.loads((CONTROL / 'verification-request.json').read_text())
    entry = CONTROL / 'independent-verifier.py'
    assert hashlib.sha256(entry.read_bytes()).hexdigest() == request['verifier_sha256']
    assert worker.sha(REVIEW / 'recovery-request.json') == request['recovery_request_sha256']
    state.update(status='waiting-for-finalization-review');save()
    deadline = time.monotonic() + 3600
    while True:
        path = REVIEW / 'status.json'
        observed = json.loads(path.read_text()) if path.exists() else {'status': 'launching'}
        if observed['status'] == 'complete':
            break
        if observed['status'] == 'failed' or time.monotonic() >= deadline:
            raise RuntimeError('MTH finalization review did not complete; native/failed evidence is unchanged')
        time.sleep(15)
    state.update(status='verifying', verifier_sha256=request['verifier_sha256']);save()
    metrics = execute([sys.executable, '-B', str(entry)], cwd=CONTROL,
                      stdout=CONTROL / 'verification.stdout.log', stderr=CONTROL / 'verification.stderr.log',
                      env=os.environ.copy(), timeout=1800, namespace_user='current',
                      progress=lambda values: worker.save(CONTROL / 'verification-progress.json', values))
    worker.save(CONTROL / 'verification-metrics.json', metrics)
    if metrics['exit_status'] != 0:
        raise RuntimeError('Independent reviewed verification failed; see retained logs')
    text = (CONTROL / 'verification.stdout.log').read_text()
    begin, end = 'BEGIN_COMMON_REPLAY_RESULT\n', '\nEND_COMMON_REPLAY_RESULT'
    assert text.count(begin) == text.count(end) == 1
    result = json.loads(text.split(begin, 1)[1].split(end, 1)[0])
    assert result['status'] == 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION_WITH_FINALIZATION_REVIEW'
    with (CONTROL / 'final-verification.json').open('x') as handle:
        json.dump(result, handle, indent=2);handle.write('\n')
    (CONTROL / 'final-verification.json').chmod(0o444)
    state.update(status='complete', result=result['status'], completed_at=worker.now())
except BaseException as error:
    state.update(status='failed', error=str(error), completed_at=worker.now())
    traceback.print_exc()
finally:
    if authorized:
        save()
