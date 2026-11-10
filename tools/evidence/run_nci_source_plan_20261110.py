#!/usr/bin/env python3
"""Detached dev-only controller; use the frozen worker and restore its runtime."""
import json
from pathlib import Path
import time
import traceback

import inversion_worker as worker

CONTROL = Path(__file__).resolve().parent
worker.guard()
lock = json.loads((CONTROL / 'case.lock.json').read_text())
original = json.loads((CONTROL / 'original-runtime.lock.json').read_text())
state = {'run_id': lock['run_id'], 'status': 'preflight', 'started_at': worker.now(),
         'engine_ref': lock['request']['engine_ref'], 'apparatus_ref': lock['apparatus_ref']}
activated = False


def save():
    state['updated_at'] = worker.now()
    worker.save(CONTROL / 'status.json', state)


save()
try:
    worker.guard()
    worker.verify_lock(lock)
    worker.verify_lock(original)
    assert lock['request']['source'] == 'NCI' and lock['request']['case_variant'] == 'source-plan'
    assert original['runtime_ref'] == '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
    worker.runtime(original)
    previous = worker.inspect_current('NCI')
    worker.save(CONTROL / 'previous-source-receipt.json', previous)
    activation = worker.activate_runtime(lock)
    activated = True
    worker.save(CONTROL / 'runtime-activation.json', activation)
    launch = worker.launch(lock, previous)
    worker.save(CONTROL / 'launch.json', launch)
    state.update(status='running', worker_pid=launch['worker_pid'], run_directory=launch['run_directory'])
    save()
    run = Path(launch['run_directory'])
    deadline = time.monotonic() + 14400
    while True:
        native = json.loads((run / 'status.json').read_text())
        state['worker_status'] = native
        progress = run / 'progress.json'
        if progress.is_file():
            state['worker_progress'] = json.loads(progress.read_text())
        save()
        if native['status'] in ('complete', 'failed'):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('Controller deadline reached; restoration still obeys the runtime lock/idle guards')
        time.sleep(5)
    if native['status'] != 'complete':
        raise RuntimeError('Worker failed: ' + native.get('error', 'see worker evidence'))
    result = json.loads((run / 'result.json').read_text())
    if result['acceptance']['status'] != 'PASS_EQUIVALENT':
        raise RuntimeError('Full comparison did not pass: ' + str(result['acceptance']))
    state.update(status='verified-worker-complete', acceptance=result['acceptance'])
except BaseException as error:
    state.update(status='failed', error=str(error))
    traceback.print_exc()
finally:
    save()
    if activated:
        try:
            restoration = worker.activate_runtime(original)
            worker.runtime(original)
            worker.save(CONTROL / 'runtime-restoration.json', restoration)
            state['restored_original_runtime_files_verified'] = 169
        except BaseException as error:
            state.update(status='restoration-failed', restoration_error=str(error))
            traceback.print_exc()
    if state['status'] == 'verified-worker-complete':
        state['status'] = 'complete'
    state['completed_at'] = worker.now()
    save()
