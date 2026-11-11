#!/usr/bin/env python3
"""Verify and audit one retained native result without changing its failed parent."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import traceback

import inversion_worker as worker
import replay_mth_core as native
from replay_process import available_memory, runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
PARENT_ID = 'common-mth-generated-20261110'
REVIEW_ID = 'common-mth-generated-finalization-20261110'
PARENT = ROOT / 'qa/replay-requests' / PARENT_ID
CONTROL = ROOT / 'qa/replay-requests' / REVIEW_ID
TARGET = ROOT / 'sources/MTH_2026AA'
APPARATUS = '79df69fe5b0b45d4f3c10550c16cb62cb9e8199e'
LOCK_SHA = '21666001b0d80639b88ddb9ef4efac4a427bad84840beba739b0ba220647642c'
ERROR = "module 'mth_configuration' has no attribute 'verify_generated'"
PATHS = {name: PARENT / name for name in ('case.lock.json', 'status.json', 'preparation.json',
         'acquisition.json', 'previous-source-receipt.json')}
PATHS.update({'native-result.json': TARGET / 'qa/replay-runs' / PARENT_ID / 'result.json',
              'native-active.json': TARGET / 'replay-active-run.json'})


def snapshot(request):
    assert set(request['parent_records']) == set(PATHS)
    values = {}
    for name, path in PATHS.items():
        item = request['parent_records'][name]
        assert item['path'] == str(path) and not path.is_symlink() and path.is_file()
        raw = path.read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256'], name
        values[name] = json.loads(raw)
    return values


def check_modules(lock, request):
    assert set(request['module_sha256']) == set(lock['modules_b64']) and len(lock['modules_b64']) == 23
    for name, encoded in lock['modules_b64'].items():
        original = base64.b64decode(encoded, validate=True)
        current = (CONTROL / 'apparatus' / name).read_bytes()
        assert hashlib.sha256(current).hexdigest() == request['module_sha256'][name]
        assert (PARENT / 'apparatus' / name).read_bytes() == original
        if name == 'inversion_worker.py':
            before = (b'            import mth_configuration\n'
                      b'            mth_configuration.execution_recipe_from_lock(lock)\n'
                      b'            mth_configuration.verify_generated(package(lock), target)')
            after = (b'            import mth_configuration\n'
                     b'            import replay_mth_core\n'
                     b'            mth_configuration.execution_recipe_from_lock(lock)\n'
                     b'            replay_mth_core.verify_generated(package(lock), target)')
            assert original.count(before) == 1 and current == original.replace(before, after)
        else:
            assert current == original, name


state = {'status': 'preflight', 'source': 'MTH', 'run_id': REVIEW_ID, 'parent_run_id': PARENT_ID,
         'mode': 'generated-mth-finalization-review', 'started_at': worker.now(),
         'native_conversion_repeated': False, 'preparation_repeated': False,
         'insertion_executed': False, 'production_eligible': False}
authorized = False


def save():
    state['updated_at'] = worker.now()
    worker.save(CONTROL / 'status.json', state)


try:
    worker.guard()
    assert CONTROL.resolve() == CONTROL and CONTROL.is_dir() and not CONTROL.is_symlink()
    assert PARENT.resolve() == PARENT and TARGET.resolve() == TARGET
    assert all(not (CONTROL / name).exists() for name in
               ('status.json', 'result.json', 'raw-result.json', 'native-result.json', 'correction-audit.json'))
    authorized = True
    request = json.loads((CONTROL / 'recovery-request.json').read_text())
    assert request['parent_run_id'] == PARENT_ID and request['review_id'] == REVIEW_ID
    assert worker.sha(Path(__file__)) == request['driver_sha256']
    assert not (CONTROL / 'result.json').exists()
    save()
    with runtime_lock(ROOT):
        worker.idle()
        values = snapshot(request)
        lock, raw = values['case.lock.json'], values['native-result.json']
        assert values['status.json']['status'] == 'failed' and values['status.json']['error'] == ERROR
        assert values['native-active.json']['status'] == 'complete'
        assert all(not (PARENT / name).exists() for name in ('raw-result.json', 'result.json', 'correction-audit.json'))
        assert lock['run_id'] == PARENT_ID and lock['lock_sha256'] == LOCK_SHA and lock['apparatus_ref'] == APPARATUS
        assert lock['request']['case_variant'] == 'generated-configuration'
        assert lock['configuration_generation']['profile'] == 'mth-prepared-spec-v1'
        assert worker.verify_lock(lock) == TARGET and worker.correction_profile(lock)
        assert raw['run_id'] == PARENT_ID and raw['engine_ref'] == worker.MTH_CORRECTION_ENGINE
        assert raw['acceptance']['status'] == 'DIFFERENCES_REQUIRE_REVIEW'
        assert raw['comparison']['validation']['passed'] and raw['comparison']['validation']['identity_state']['passed']
        assert raw['input_engine_runtime_and_output_hashes_verified_after_run'] is True
        assert len(raw['comparison']['files']) == 23
        check_modules(lock, request)
        # This operation stages no source tree and performs no conversion. Its
        # scratch budget covers all extracted references, generous context-sort
        # copies, a 2 GiB margin and the unchanged 12 GiB execution reserve.
        references = lock['case']['legacy_case']['reference_files']
        reference_bytes = sum(item['bytes'] for item in references)
        context_bytes = sum(item['bytes'] for item in references if item['output_name'] in
                            ('contexts.src', 'attributes.contexts-all.src'))
        required = reference_bytes + 6 * context_bytes + 14 * 1024 ** 3
        assert shutil.disk_usage(ROOT).free >= required and available_memory() >= 24 * 1024 ** 3
        state['capacity'] = {'free_disk_bytes': shutil.disk_usage(ROOT).free, 'required_disk_bytes': required,
                             'reference_bytes': reference_bytes, 'context_bytes': context_bytes,
                             'execution_disk_reserve_bytes': 12 * 1024 ** 3,
                             'native_launch_floors_changed': False}
        before = {item['path']: item for item in values['previous-source-receipt.json']['manifest'] if item['kind'] == 'file'}
        assert all(before['src/' + name]['sha256'] == item['candidate']['sha256']
                   for name, item in raw['comparison']['files'].items())
        (CONTROL / 'native-result.json').write_bytes(PATHS['native-result.json'].read_bytes())
        (CONTROL / 'native-result.json').chmod(0o444)
        data = worker.package(lock)
        native.configure_case(data)
        state.update(status='verifying-retained-outputs');save()
        native.verify_inputs(data, TARGET)
        result = copy.deepcopy(raw)
        worker.verify_after(lock, TARGET, result)
        snapshot(request)
        state.update(status='auditing');save()
        worker.review_corrections(lock, TARGET, CONTROL, result)
        assert result['acceptance']['status'] == 'PASS_REVIEWED_CORRECTIONS'
        snapshot(request)
        assert result['comparison'] == raw['comparison']
        result.update(common_request=lock['request'], lock_sha256=LOCK_SHA, apparatus_ref=APPARATUS,
                      conversion_apparatus_ref=APPARATUS, finalization_apparatus_ref=request['code_ref'],
                      parent_run_id=PARENT_ID, review_id=REVIEW_ID, mode=state['mode'],
                      original_common_run_status='failed', native_conversion_repeated=False,
                      preparation_repeated=False, complete_ID_range_verified=True,
                      original_native_result_sha256=request['parent_records']['native-result.json']['sha256'],
                      native_completed_at=raw['completed_at'], completed_at=worker.now(),
                      all_23_outputs_identical_to_previous_accepted_candidate=True,
                      ID_range_verification_scope={'bound_kind': lock['configuration']['source_atom_ids'].get('bound_kind', 'reserved-historical-range'), 'new_production_allocation_performed': False},
                      insertion_executed=False, production_eligible=False)
        worker.save(CONTROL / 'result.json', result);(CONTROL / 'result.json').chmod(0o444)
        state.update(status='complete', acceptance=result['acceptance'], completed_at=worker.now(),
                     finalization_apparatus_ref=request['code_ref'], parent_records_unchanged=True)
except BaseException as error:
    state.update(status='failed', error=str(error), completed_at=worker.now())
    traceback.print_exc()
finally:
    if authorized:
        save()
