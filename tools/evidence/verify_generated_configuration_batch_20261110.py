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
REVIEW = ROOT / 'qa/replay-requests/common-mth-generated-finalization-20261110'
FINALIZATION_ERROR = "module 'mth_configuration' has no attribute 'verify_generated'"
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
    assert len(controller['runs']) == 2
    reviewed = controller['status'] == 'failed'
    review_request = None
    if reviewed:
        assert controller['error'] == 'MTH failed: ' + FINALIZATION_ERROR
        assert load(BATCH / 'verification-status.json')['status'] == 'failed'
        assert not (BATCH / 'final-verification.json').exists()
        assert load(REVIEW / 'status.json')['status'] == 'complete'
        review_request = load(REVIEW / 'recovery-request.json')
        assert review_request['parent_run_id'] == CASES[1][2]
        assert review_request['review_id'] == REVIEW.name
        assert sha(REVIEW / 'recovery-driver.py') == review_request['driver_sha256']
        for item in review_request['parent_records'].values():
            assert sha(Path(item['path'])) == item['sha256']
    else:
        assert controller['status'] == 'complete'
    verified = []
    for filename, source, run_id, expected_lock, verdict, output_count, generated_count in CASES:
        run = ROOT / 'qa/replay-requests' / run_id
        lock = load(run / 'case.lock.json')
        state = load(run / 'status.json')
        evidence_run = REVIEW if reviewed and source == 'MTH' else run
        result = load(evidence_run / 'result.json')
        if evidence_run == REVIEW:
            assert state['status'] == 'failed' and state['error'] == FINALIZATION_ERROR
            assert not (run / 'result.json').exists() and not (run / 'raw-result.json').exists()
            assert result['mode'] == 'generated-mth-finalization-review'
            assert result['review_id'] == REVIEW.name and result['parent_run_id'] == run_id
            assert result['original_common_run_status'] == 'failed'
            assert result['native_conversion_repeated'] is False and result['preparation_repeated'] is False
            assert result['finalization_apparatus_ref'] == review_request['code_ref']
            assert result['original_native_result_sha256'] == review_request['parent_records']['native-result.json']['sha256']
            assert sha(REVIEW / 'native-result.json') == result['original_native_result_sha256']
            assert load(REVIEW / 'native-result.json')['comparison'] == result['comparison']
        else:
            assert state['status'] == 'complete'
        assert result['acceptance']['status'] == verdict
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
        if evidence_run == REVIEW:
            assert set(review_request['module_sha256']) == set(lock['modules_b64'])
            for name, encoded in lock['modules_b64'].items():
                original = base64.b64decode(encoded, validate=True)
                actual = (REVIEW / 'apparatus' / name).read_bytes()
                assert hashlib.sha256(actual).hexdigest() == review_request['module_sha256'][name]
                if name == 'inversion_worker.py':
                    before = (b'            import mth_configuration\n'
                              b'            mth_configuration.execution_recipe_from_lock(lock)\n'
                              b'            mth_configuration.verify_generated(package(lock), target)')
                    after = (b'            import mth_configuration\n'
                             b'            import replay_mth_core\n'
                             b'            mth_configuration.execution_recipe_from_lock(lock)\n'
                             b'            replay_mth_core.verify_generated(package(lock), target)')
                    assert original.count(before) == 1 and actual == original.replace(before, after)
                else:
                    assert actual == original
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
            assert result['raw_result_sha256'] == sha(evidence_run / 'raw-result.json')
            assert result['correction_audit'] == load(evidence_run / 'correction-audit.json')
            assert result['correction_audit_execution'] == load(evidence_run / 'correction-audit-execution.json')
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
        if evidence_run == REVIEW:
            verified[-1].update(original_common_run_status='failed', finalization_review_id=REVIEW.name,
                                finalization_apparatus_ref=review_request['code_ref'], native_conversion_repeated=False)
    report = {'status': 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION',
              'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'apparatus_ref': APPARATUS, 'runs': verified, 'production_eligible': False,
              'insertion_executed': False, 'runtime_activation_performed': False}
    if reviewed:
        report['status'] = 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION_WITH_FINALIZATION_REVIEW'
        report['mth_finalization_review'] = {'review_id': REVIEW.name, 'code_ref': review_request['code_ref'],
                                           'original_common_run_status': 'failed',
                                           'original_failure_preserved': True, 'native_conversion_repeated': False,
                                           'parent_records_reverified': review_request['parent_records']}
    retention = ROOT / 'qa/replay-requests/dev-retention-20261110.controller'
    assert sha(retention / 'archive-results.json') == '1e976f38ccf9c5263f2a9a1babf8064d2328d4c23e2c758ff8dba03a29deb1de'
    archived = load(retention / 'archive-results.json')
    retired = load(retention / 'retirement-status.json')
    assert retired['status'] == 'complete' and len(retired['retired']) == len(archived) == 3
    assert {item['receipt_sha256'] for item in retired['retired']} == {item['receipt_sha256'] for item in archived}
    retained_hashes = {}
    for item in archived:
        receipt_path = Path(item['receipt'])
        assert sha(receipt_path) == item['receipt_sha256']
        receipt = load(receipt_path)
        assert receipt['status'] == 'VERIFIED' and receipt['verification']['status'] == 'PASS_FULL_ARCHIVE_VERIFICATION'
        assert receipt['tool_sha256'] == '5130d4b0e736758ff5217297566c5bc22edc1a845de71ef90d25321d41320a5b'
        assert sha(receipt_path.parent / 'manifest.json') == receipt['manifest_sha256']
        assert sha(Path(item['archive'])) == receipt['archive_sha256']
        assert not Path(item['source']).exists() and not Path(item['source']).is_symlink()
        retained_hashes[Path(item['source']).name] = receipt['archive_sha256']
    report['older_tree_retention'] = {'verified_archives_retained': 3, 'expanded_copies_retired': 3,
                                    'archive_hashes_verified_after_retirement': retained_hashes}
    print('BEGIN_COMMON_REPLAY_RESULT')
    print(json.dumps(report))
    print('END_COMMON_REPLAY_RESULT', flush=True)
