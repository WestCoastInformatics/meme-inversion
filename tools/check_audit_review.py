#!/usr/bin/env python3
"""Check phase-only recovery, parent evidence binding and detached lock handoff."""
import base64
import copy
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

import inversion_worker as worker


def check():
    values = []
    def require(value, label):
        assert value, label
        values.append(label)
    def rejected(action, label):
        try:action()
        except (ValueError, RuntimeError, FileExistsError):values.append(label)
        else:raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='audit-review-fixtures-') as temporary:
        root = Path(temporary);control = root/'qa/replay-requests';parent = control/'parent-mth-run';parent.mkdir(parents=True)
        target = root/'sources/MTH_2026AA';target.mkdir(parents=True)
        request = {'source': 'MTH', 'version': 'MTH_2026AA', 'engine_ref': worker.MTH_CORRECTION_ENGINE,
                   'case_variant': 'consistent-retained-identities', 'comparison_profile': 'reviewed-corrections'}
        outputs = {str(number): {} for number in range(23)}
        lock = {'request': request, 'run_id': parent.name, 'apparatus_ref': '1'*40, 'lock_sha256': '2'*64,
                'runtime_ref': '3b125edc1d29f7c7a91673da2a8d752bb0adff44', 'modules_b64': {'audit_mth_corrections.py': ''},
                'case': {'correction_audit': worker.MTH_CORRECTION_AUDIT,
                         'legacy_case': {'execute_source_stages': True, 'validate_identity_state': True,
                                         'reference_files': [{'output_name': name} for name in outputs]}}}
        raw = {**{key: request[key] for key in ('source', 'version', 'engine_ref')}, 'run_id': parent.name,
               'completed_at': '2026-11-06T00:00:00+00:00', 'input_engine_runtime_and_output_hashes_verified_after_run': True,
               'comparison': {'files': outputs, 'validation': {'passed': True, 'identity_state': {'passed': True}}},
               'acceptance': {'status': 'DIFFERENCES_REQUIRE_REVIEW'}}
        failed = {'status': 'failed', 'error': 'Stage exited 1; correction-audit.stderr.log'}
        for name, data in [('case.lock.json', lock), ('raw-result.json', raw), ('status.json', failed)]:worker.save(parent/name, data)
        before = {path.name: path.read_bytes() for path in parent.iterdir()}
        capsule = {'schema_version': 1, 'artifact_type': 'ncimeta-mth-audit-review', 'parent_run_id': parent.name,
                   'review_id': 'review-mth-audit', 'apparatus_ref': '3'*40, 'modules_b64': {}, 'provenance': []}
        def rehash(value):value['capsule_sha256'] = worker.digest({k: v for k, v in value.items() if k != 'capsule_sha256'})
        rehash(capsule);worker.verify_audit_review(capsule);values.append('New review identity and immutable capsule accepted')
        bad = copy.deepcopy(capsule);bad['review_id'] = parent.name;rehash(bad)
        rejected(lambda: worker.verify_audit_review(bad), 'Review cannot reuse the failed parent identity')
        bad = copy.deepcopy(capsule);bad['apparatus_ref'] = 'HEAD';rehash(bad)
        rejected(lambda: worker.verify_audit_review(bad), 'Unpinned audit apparatus rejected')
        with patch.multiple(worker, ROOT=root, CONTROL=control), patch.object(worker, 'guard'), patch.object(worker, 'verify_lock', return_value=target):
            require(worker.audit_parent(parent.name)[0] == lock, 'Only completed matching parent correction evidence is selected')
            for field, value in [('status', 'complete'), ('error', 'conversion failed')]:
                changed = dict(failed);changed[field] = value;worker.save(parent/'status.json', changed)
                rejected(lambda: worker.audit_parent(parent.name), 'Ineligible parent status rejected: ' + field)
            worker.save(parent/'status.json', failed)
            for mutate, label in [(lambda x: x.update(run_id='another-run'), 'Mismatched parent raw run rejected'),
                                  (lambda x: x['comparison']['files'].pop('0'), 'Incomplete parent output set rejected'),
                                  (lambda x: x['comparison']['validation'].update(passed=False), 'Failed parent validation cannot be reviewed away')]:
                changed = copy.deepcopy(raw);mutate(changed);worker.save(parent/'raw-result.json', changed)
                rejected(lambda: worker.audit_parent(parent.name), label)
            worker.save(parent/'raw-result.json', raw)
            run = control/capsule['review_id'];run.mkdir();worker.save(run/'review-request.json', capsule)
            worker.save(run/'parent-records.json', worker.audit_parent(parent.name)[3])
            def review(lock, target, run, result):
                worker.save(run/'raw-result.json', result)
                result['raw_result_sha256'] = worker.sha(run/'raw-result.json')
                result['acceptance'] = {'status': 'PASS_REVIEWED_CORRECTIONS'}
            with patch.object(worker, 'idle'), patch.object(worker, 'package', return_value={}), \
                    patch('replay_mth_core.verify_inputs'), patch.object(worker, 'verify_after', side_effect=lambda lock, target, result: result.update(probe=True)), \
                    patch.object(worker, 'review_corrections', side_effect=review):
                worker.audit_review_worker(run/'review-request.json')
            result = json.loads((run/'result.json').read_text())
            require(result['conversion_apparatus_ref'] == lock['apparatus_ref'] and result['audit_apparatus_ref'] == capsule['apparatus_ref'],
                    'Conversion and retry apparatus identities remain separate')
            require(result['original_common_run_status'] == 'failed' and result['mode'] == 'correction-audit-only',
                    'Successful review does not relabel the original failed common job')
            require((run/'raw-result.json').read_bytes() == before['raw-result.json'] and all((parent/name).read_bytes() == raw_bytes for name, raw_bytes in before.items()),
                    'Review preserves original raw bytes, parent lock and failed status')
            require(not result['production_eligible'] and not result['insertion_executed'], 'Audit recovery cannot promote or insert data')
            bad_run = control/'changed-parent-review';bad_run.mkdir()
            changed_capsule = {**capsule, 'review_id': bad_run.name};rehash(changed_capsule)
            worker.save(bad_run/'review-request.json', changed_capsule)
            worker.save(bad_run/'parent-records.json', {'changed': 'snapshot'})
            with patch.object(worker, 'idle'), redirect_stderr(io.StringIO()):
                rejected(lambda: worker.audit_review_worker(bad_run/'review-request.json'), 'Parent snapshot changes block retry before auditing')
            require(json.loads((bad_run/'status.json').read_text())['status'] == 'failed' and not (bad_run/'result.json').exists(),
                    'Failed review leaves diagnostics and no accepted result')
            tiny = '''import fcntl,json,os,pathlib,subprocess,sys
def audit_review_worker(path,inherited_lock=None):
 root=pathlib.Path(path).parents[3]
 fcntl.flock(inherited_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 code="import fcntl,sys;f=open(sys.argv[1],'a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
 p=subprocess.run([sys.executable,'-c',code,str(root/'.replay-runtime.lock')],capture_output=True)
 pathlib.Path(path).with_name('handoff.json').write_text(json.dumps({'descriptor_open':os.fstat(inherited_lock.fileno()).st_ino>0,'competitor_blocked':p.returncode!=0}))
'''
            launch_capsule = {**capsule, 'review_id': 'detached-review', 'modules_b64': {'inversion_worker.py': base64.b64encode(tiny.encode()).decode()},
                              'provenance': [{'repository_path': 'tools/inversion_worker.py', 'sha256': hashlib.sha256(tiny.encode()).hexdigest()}]}
            rehash(launch_capsule)
            with patch.object(worker, 'idle'), patch.object(worker, 'runtime'), patch.object(worker, 'available_memory', return_value=32*1024**3), \
                    patch('inversion_worker.shutil.disk_usage', return_value=shutil._ntuple_diskusage(100*1024**3, 0, 100*1024**3)):
                launch = worker.launch_audit_review(launch_capsule)
                handoff = Path(launch['run_directory'])/'handoff.json'
                for _ in range(50):
                    if handoff.exists():break
                    time.sleep(.1)
                require(handoff.exists() and all(json.loads(handoff.read_text()).values()), 'Detached audit-only retry inherits the runtime lock without a gap')
                rejected(lambda: worker.launch_audit_review(launch_capsule), 'Existing review evidence cannot be reused or replaced')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'audit recovery checks passed')
