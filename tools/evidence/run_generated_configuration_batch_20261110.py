#!/usr/bin/env python3
"""Detach two serialized dev inversions using frozen generated-settings locks."""
import json
from pathlib import Path
import time
import traceback

import inversion_worker as worker
from replay_process import runtime_lock

CONTROL = Path(__file__).resolve().parent
ORIGINAL = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
CASES = [('snomed', 'SNOMEDCT_US', ORIGINAL, 'PASS_EXACT'),
         ('mth', 'MTH', 'b2611abcf929981628bb2e5051afb450b8525b70', 'PASS_REVIEWED_CORRECTIONS')]
state = {'status': 'preflight', 'started_at': worker.now(), 'runs': [],
         'insertion_executed': False, 'production_eligible': False,
         'execution': 'serialized on existing dev worker; runtime activation is not used'}


def save():
    state['updated_at'] = worker.now()
    worker.save(CONTROL / 'status.json', state)


def idle_after_completion():
    deadline = time.monotonic() + 120
    while True:
        try:
            with runtime_lock(worker.ROOT):
                worker.idle()
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Completed worker did not release its runtime lock')
            time.sleep(1)


try:
    worker.guard()
    for filename, source, engine, verdict in CASES:
        lock = json.loads((CONTROL / (filename + '.lock.json')).read_text())
        worker.verify_lock(lock)
        assert lock['request']['source'] == source
        assert lock['request']['case_variant'] == 'generated-configuration'
        assert lock['request']['engine_ref'] == engine and lock['runtime_ref'] == ORIGINAL
        worker.runtime(lock)
    save()
    for filename, source, engine, verdict in CASES:
        lock = json.loads((CONTROL / (filename + '.lock.json')).read_text())
        idle_after_completion()
        current = {'source': source, 'run_id': lock['run_id'], 'engine_ref': engine,
                   'apparatus_ref': lock['apparatus_ref'], 'lock_sha256': lock['lock_sha256'],
                   'status': 'inspecting-previous-source'}
        state['runs'].append(current)
        state.update(status='running', current_source=source)
        save()
        previous = worker.inspect_current(source)
        worker.save(CONTROL / (filename + '-previous-source.json'), previous)
        launch = worker.launch(lock, previous)
        worker.save(CONTROL / (filename + '-launch.json'), launch)
        current.update(status='running', **launch)
        save()
        run = Path(launch['run_directory'])
        deadline = time.monotonic() + 21600
        while True:
            observed = json.loads((run / 'status.json').read_text())
            current['worker_status'] = observed
            progress = run / 'progress.json'
            if progress.is_file():
                current['progress'] = json.loads(progress.read_text())
            save()
            if observed['status'] in ('complete', 'failed'):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('Controller wait limit reached; worker evidence remains at ' + str(run))
            time.sleep(5)
        if observed['status'] != 'complete':
            raise RuntimeError(source + ' failed: ' + observed.get('error', 'see worker evidence'))
        result = json.loads((run / 'result.json').read_text())
        if result['acceptance']['status'] != verdict:
            raise RuntimeError(source + ' comparison failed: ' + str(result['acceptance']))
        if result['lock_sha256'] != lock['lock_sha256'] or result['apparatus_ref'] != lock['apparatus_ref']:
            raise RuntimeError('Result does not belong to this locked generated-settings run')
        before = {item['path']: item for item in previous['manifest'] if item['kind'] == 'file'}
        changes = []
        for name, item in result['comparison']['files'].items():
            old = before.get('src/' + name)
            if old is None or old['sha256'] != item['candidate']['sha256']:
                changes.append(name)
        if changes:
            raise RuntimeError('Generated-settings output differs from preceding accepted candidate: ' + ', '.join(changes))
        current.update(status='complete', acceptance=result['acceptance'],
                       previous_candidate_hashes_identical=len(result['comparison']['files']), completed_at=worker.now())
        idle_after_completion()
        worker.runtime(lock)
        current['original_runtime_files_verified'] = 169
        save()
    state.update(status='complete', completed_at=worker.now())
except BaseException as error:
    state.update(status='failed', error=str(error), completed_at=worker.now())
    traceback.print_exc()
finally:
    save()
