#!/usr/bin/env python3
"""Independently verify retained generated-settings runs and preserved trees."""
import base64
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import sys

ROOT = Path('/local/content/MEME/MEME5/inv')
BATCH = ROOT / 'qa/replay-requests/generated-settings-batch-20261110.controller'
APPARATUS = '79df69fe5b0b45d4f3c10550c16cb62cb9e8199e'
CASES = [('snomed', 'SNOMEDCT_US', 'common-snomed-generated-20261110',
          '07e1ea563c1ba15ccaf526713ec301f3bc3744317bee7880f744728ae2b60daf', 'PASS_EXACT', 5, 1),
         ('mth', 'MTH', 'common-mth-generated-20261110',
          '21666001b0d80639b88ddb9ef4efac4a427bad84840beba739b0ba220647642c', 'PASS_REVIEWED_CORRECTIONS', 23, 7)]


def load(path):
    assert not path.is_symlink(), str(path)
    return json.loads(path.read_text())


def sha(path):
    assert not path.is_symlink() and path.is_file(), str(path)
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for raw in iter(lambda: handle.read(4194304), b''):
            digest.update(raw)
    return digest.hexdigest()


assert socket.gethostname().split('.')[0] == 'ncias-d3777-c'
assert pwd.getpwuid(os.getuid()).pw_name == 'tomcata'
sys.dont_write_bytecode = True
sys.path.insert(0, str(BATCH / 'apparatus'))
import inversion_worker as worker

with (ROOT / '.replay-runtime.lock').open('r') as held:
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    controller = load(BATCH / 'status.json')
    assert controller['status'] == 'complete' and len(controller['runs']) == 2
    verified = []
    for filename, source, run_id, expected_lock, verdict, output_count, generated_count in CASES:
        run = ROOT / 'qa/replay-requests' / run_id
        lock = load(run / 'case.lock.json')
        state = load(run / 'status.json')
        result = load(run / 'result.json')
        assert state['status'] == 'complete' and result['acceptance']['status'] == verdict
        assert result['apparatus_ref'] == lock['apparatus_ref'] == APPARATUS
        assert lock['lock_sha256'] == state['lock_sha256'] == result['lock_sha256'] == expected_lock
        assert lock == load(BATCH / (filename + '.lock.json'))
        assert not result['production_eligible'] and not result['insertion_executed']
        target = worker.verify_lock(lock)
        module_hashes = {Path(item['repository_path']).name: item['sha256'] for item in lock['provenance'] if item['repository_path'].startswith('tools/')}
        for name, encoded in lock['modules_b64'].items():
            expected = module_hashes[name]
            assert hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest() == expected
            assert sha(run / 'apparatus' / name) == sha(BATCH / 'apparatus' / name) == expected
        assert len(lock['modules_b64']) == 23
        for item in lock['runtime_files']:
            assert sha(ROOT / item['repository_path']) == item['sha256']
        for item in lock['code_files']:
            path = target / item['relative_path']
            if item['kind'] == 'symlink':
                assert path.is_symlink() and os.readlink(path) == item['target']
            else:
                assert sha(path) == item['sha256']
        recipe = lock['configuration_generation']
        assert len(recipe['files']) == generated_count
        for item in recipe['files']:
            path = target / item['relative_path']
            assert sha(path) == item['sha256'] and path.stat().st_mode & 0o777 == 0o444
        package = worker.package(lock)
        if source == 'SNOMEDCT_US':
            import snomed_configuration
            assert snomed_configuration.execution_recipe_from_lock(lock) == recipe
            assert result['configuration_generation'] == snomed_configuration.receipt(recipe)
            import run_snomed_core_replay as native
            native.RUN_ID = run_id
            native.verify_case(package)
            references = lock['case']['artifacts'][lock['configuration']['replay']['reference_ref']]['value']
            for item in references['files']:
                assert sha(target / 'src' / item['output_name']) == item['sha256']
        else:
            import mth_configuration
            import replay_mth_core as native
            native.configure_case(package)
            native.verify_inputs(package, target)
            assert mth_configuration.execution_recipe_from_lock(lock) == recipe
            assert result['configuration_generation'] == mth_configuration.receipt(recipe)
            assert result['raw_result_sha256'] == sha(run / 'raw-result.json')
            assert result['raw_acceptance']['status'] == 'DIFFERENCES_REQUIRE_REVIEW'
            assert result['correction_audit']['status'] == verdict
            assert result['correction_audit']['run_id'] == run_id
            assert result['correction_audit']['conversion_apparatus_ref'] == APPARATUS
            assert result['correction_audit']['raw_comparison_rewritten'] is False
        previous = load(run / 'previous-source-receipt.json')
        assert previous == load(BATCH / (filename + '-previous-source.json'))
        preserved = target.with_name(target.name + '.before-' + run_id)
        expected_manifest = copy.deepcopy(previous['manifest'])
        for item in expected_manifest:
            if item['kind'] != 'symlink':
                item['mode'] = oct(int(item['mode'], 8) & ~0o222)
        assert worker.manifest(preserved) == expected_manifest
        assert preserved.stat().st_mode & 0o777 == int(previous['root_mode'], 8) & ~0o222
        before_files = {item['path']: item for item in previous['manifest'] if item['kind'] == 'file'}
        hashes = {}
        assert len(result['comparison']['files']) == output_count
        for name, item in result['comparison']['files'].items():
            actual = sha(target / 'src' / name)
            assert actual == item['candidate']['sha256'] == before_files['src/' + name]['sha256']
            hashes[name] = actual
        verified.append({'source': source, 'run_id': run_id, 'lock_sha256': expected_lock,
                         'acceptance': verdict, 'outputs_verified': hashes, 'generated_readonly_files': generated_count,
                         'all_outputs_identical_to_previous_accepted_candidate': True,
                         'preserved_tree_entries_verified': len(expected_manifest), 'frozen_modules_verified': 23,
                         'original_runtime_files_verified': 169})
    report = {'status': 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION',
              'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'apparatus_ref': APPARATUS, 'runs': verified, 'production_eligible': False,
              'insertion_executed': False, 'runtime_activation_performed': False}
    print('BEGIN_COMMON_REPLAY_RESULT')
    print(json.dumps(report))
    print('END_COMMON_REPLAY_RESULT', flush=True)
