#!/usr/bin/env python3
"""Exercise real filesystem/lock handoffs and runtime rollback on tiny fixtures."""
import argparse
import base64
import copy
from contextlib import nullcontext, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

import inversion_worker as worker
import inversion_remote as remote
from replay_process import runtime_lock

BASE = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
ORDER = 'bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09'


def library_fixtures():
    root = Path(__file__).resolve().parents[1]
    return {ref: base64.b64encode(subprocess.check_output(['git', '-C', str(root), 'show', ref + ':INV/lib/Hierarchy.pm'])).decode()
            for ref in (BASE, ORDER)}


def fixture_lock(libraries, run_id='fixture-case'):
    runtime = []
    for number in range(168):
        raw = ('unchanged fixture ' + str(number)).encode()
        runtime.append({'repository_path': 'INV/fixture/' + str(number), 'mode': '0o640',
                        'sha256': hashlib.sha256(raw).hexdigest(), 'data_b64': base64.b64encode(raw).decode()})
    raw = base64.b64decode(libraries[ORDER])
    runtime.append({'repository_path': 'INV/lib/Hierarchy.pm', 'mode': '0o644', 'sha256': hashlib.sha256(raw).hexdigest(), 'data_b64': libraries[ORDER]})
    source = [{'relative_path': 'bin/invert_NCI.pl', 'kind': 'file', 'mode': '0o750',
               'sha256': hashlib.sha256(b'fixture').hexdigest(), 'data_b64': base64.b64encode(b'fixture').decode()}]
    request = {'schema_version': 1, 'source': 'NCI', 'version': 'NCI_2026_10D', 'engine_ref': ORDER,
               'case_variant': 'fixture', 'reference_stage': 'inversion-src', 'comparison_profile': 'semantic-strict'}
    config = {'engine_ref': ORDER, 'replay': {key: request[key] for key in ('case_variant', 'reference_stage', 'comparison_profile')}}
    case = {**request, 'adapter': 'nci-oct2026-v1', 'reviewed_engine_refs': [ORDER], 'configuration': config,
            'runtime_ref': ORDER, 'execution_enabled': True,
            'runtime_files': [{'relative_path': x['repository_path'], 'sha256': x['sha256'], 'mode': x['mode']} for x in runtime],
            'source_files': [{k: v for k, v in source[0].items() if k != 'data_b64'}]}
    lock = {'schema_version': 1, 'artifact_type': 'ncimeta-dev-replay-lock', 'run_id': run_id,
            'request': request, 'configuration': config, 'case': case, 'case_sha256': worker.digest(case),
            'runtime_files': runtime, 'runtime_ref': ORDER, 'code_files': source, 'execution_enabled': True,
            'provenance': [], 'modules_b64': {}}
    lock['lock_sha256'] = worker.digest(lock)
    return lock


def check(libraries):
    values = []
    def require(value, label):
        assert value, label
        values.append(label)
    def rejected(action, label):
        try:
            action()
        except (ValueError, RuntimeError, BlockingIOError, FileExistsError):
            values.append(label)
        else:
            raise AssertionError(label)
    def rehash(lock):
        lock['case_sha256'] = worker.digest(lock['case'])
        lock['lock_sha256'] = worker.digest({k: v for k, v in lock.items() if k != 'lock_sha256'})
    with tempfile.TemporaryDirectory(prefix='inversion-worker-fixtures-') as temporary:
        root = Path(temporary)
        control = root / 'qa/replay-requests'
        lock = fixture_lock(libraries)
        for item in lock['runtime_files']:
            path = root / item['repository_path'];path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(item['data_b64']))
        library = root / 'INV/lib/Hierarchy.pm'
        original = base64.b64decode(libraries[BASE])
        library.write_bytes(original)
        previous = root / 'candidate-runtime.json';previous.write_bytes(b'{"original":true}\n')
        with patch.multiple(worker, ROOT=root, CONTROL=control), patch.object(worker, 'guard'), patch.object(worker, 'idle'):
            worker.verify_lock(lock);values.append('Complete source/runtime inventories accepted')
            bad = copy.deepcopy(lock);bad['code_files'] = [];rehash(bad)
            rejected(lambda: worker.verify_lock(bad), 'Rehashed lock with missing source code rejected')
            bad = copy.deepcopy(lock);bad['runtime_files'][0]['repository_path'] = 'INV/other';rehash(bad)
            rejected(lambda: worker.verify_lock(bad), 'Rehashed lock with substituted runtime path rejected')
            before_receipt = previous.read_bytes()
            with patch.object(worker, 'runtime', side_effect=RuntimeError('injected post-write verification failure')):
                rejected(lambda: worker.activate_runtime(lock), 'Runtime verification failure rejects activation')
            require(library.read_bytes() == original and previous.read_bytes() == before_receipt, 'Failed activation restores original library and receipt bytes')
            lock['run_id'] = 'fixture-late-failure';rehash(lock)
            original_save = worker.save
            def fail_late(path, value):
                if path.name.endswith('.runtime-activation.json'):
                    raise RuntimeError('injected evidence publication failure')
                return original_save(path, value)
            with patch.object(worker, 'save', side_effect=fail_late):
                rejected(lambda: worker.activate_runtime(lock), 'Late activation evidence failure rejects operation')
            require(library.read_bytes() == original and previous.read_bytes() == before_receipt, 'Late activation failure restores library and previous receipt exactly')
            lock['run_id'] = 'fixture-activate';rehash(lock)
            with runtime_lock(root):
                rejected(lambda: worker.activate_runtime(lock), 'Active inversion blocks runtime activation before changes')
            result = worker.activate_runtime(lock)
            require(result['status'] == 'runtime-activated' and library.read_bytes() == base64.b64decode(libraries[ORDER]), 'Only the characterized shared-library change is activated')
            backup = Path(result['preserved_runtime'])
            require((backup / 'Hierarchy.pm').read_bytes() == original and (backup / 'candidate-runtime.json').read_bytes() == before_receipt,
                    'Original runtime bytes and receipt preserved together')
            require(not backup.stat().st_mode & 0o222 and not (backup / 'Hierarchy.pm').stat().st_mode & 0o222, 'Runtime backup is read-only')
            require(worker.activate_runtime(lock)['status'] == 'runtime-already-matches', 'Matching complete runtime is verified without rewriting it')
            library.write_bytes(b'unreviewed library')
            rejected(lambda: worker.activate_runtime(lock), 'Unknown installed runtime cannot be replaced implicitly')
            library.write_bytes(base64.b64decode(libraries[ORDER]))
            # The actual detached child verifies the inherited descriptor while
            # another process attempts a competing lock. No converter is run.
            tiny = '''import fcntl,json,os,pathlib,subprocess,sys
def worker(lock_path,receipt_path=None,inherited_lock=None):
 root=pathlib.Path(lock_path).parents[3]
 fcntl.flock(inherited_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 probe="import fcntl,sys;f=open(sys.argv[1],'a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
 p=subprocess.run([sys.executable,'-c',probe,str(root/'.replay-runtime.lock')],capture_output=True)
 pathlib.Path(lock_path).with_name('handoff.json').write_text(json.dumps({'descriptor_open':os.fstat(inherited_lock.fileno()).st_ino>0,'competitor_blocked':p.returncode!=0}))
'''
            lock['run_id'] = 'fixture-handoff'
            lock['modules_b64'] = {'inversion_worker.py': base64.b64encode(tiny.encode()).decode()}
            lock['provenance'] = [{'repository_path': 'tools/inversion_worker.py', 'sha256': hashlib.sha256(tiny.encode()).hexdigest()}]
            rehash(lock)
            with patch.object(worker, 'available_memory', return_value=32 * 1024 ** 3), patch('inversion_worker.shutil.disk_usage', return_value=shutil._ntuple_diskusage(200 * 1024 ** 3, 0, 200 * 1024 ** 3)):
                launch = worker.launch(lock)
            handoff = Path(launch['run_directory']) / 'handoff.json'
            for _ in range(50):
                if handoff.exists():break
                time.sleep(.1)
            require(handoff.exists() and all(json.loads(handoff.read_text()).values()), 'Detached worker inherits the runtime lock without an unlocked handoff')
            rejected(lambda: worker.launch(lock), 'A submitted run identity cannot be reused')
        # Actual Linux atomic publication is exercised on dev. The Mac version
        # injects a publisher only for this filesystem fixture.
        def publish(before, after):
            if after.exists() or after.is_symlink():raise FileExistsError(after)
            before.rename(after)
        publisher = nullcontext() if sys.platform.startswith('linux') else patch('prepare_snomed_candidate.publish', side_effect=publish)
        target = root / 'sources/MTH_2026AA';(target / 'qa/replay-runs/example-run').mkdir(parents=True)
        (target / 'etc').symlink_to('.')
        (target / 'qa/replay-runs/example-run/progress.json').write_text('{"stage":"fixture"}')
        program = remote.read_program('MTH', 'example-run', False).replace('/local/content/MEME/MEME5/inv', str(root))
        body = program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0]
        output = io.StringIO()
        with patch('socket.gethostname', return_value='ncias-d3777-c'), redirect_stdout(output):exec(compile(body, '<fixture-read>', 'exec'), {})
        require('fixture' in output.getvalue(), 'MTH etc-to-dot alias does not duplicate a status result')
        common = control / 'example-run';common.mkdir();(common / 'status.json').write_text('{"status":"common-control"}')
        output = io.StringIO()
        with patch('socket.gethostname', return_value='ncias-d3777-c'), redirect_stdout(output):exec(compile(body, '<fixture-read>', 'exec'), {})
        read_result = json.loads(output.getvalue().split('BEGIN_COMMON_REPLAY_RESULT\n', 1)[1].split('\nEND_COMMON_REPLAY_RESULT', 1)[0])
        require(read_result['records']['status.json']['status'] == 'common-control', 'Persistent common control status takes precedence over inner adapter status')
        require(read_result['records']['adapter_progress.json']['stage'] == 'fixture', 'Common status includes the actual inner adapter progress')
        (target / 'qa/replay-runs/example-run/progress.json').unlink()
        (target / 'qa/replay-runs/example-run').rmdir();(target / 'qa/replay-runs').rmdir();(target / 'qa').rmdir()
        (target / 'atoms').write_bytes(b'original')
        receipt = {'source': 'MTH', 'version': target.name, 'root_mode': oct(target.stat().st_mode & 0o777), 'manifest': worker.manifest(target)}
        receipt['receipt_sha256'] = worker.digest(receipt)
        with publisher:
            preserved = worker.preserve(target, 'preserved-fixture', receipt)
            require(not target.exists() and (preserved / 'atoms').read_bytes() == b'original', 'Actual platform publisher preserves a complete source tree')
            worker.restore(preserved, target, receipt)
            require(worker.manifest(target) == receipt['manifest'], 'Rollback restores exact source bytes, modes and aliases')
        for base, dirs, files in os.walk(root):
            Path(base).chmod(0o700)
            for name in files:
                path = Path(base) / name
                if not path.is_symlink():path.chmod(0o600)
    return values


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--libraries', type=Path, help='Explicit Git-derived library fixture bundle for dev without a Git checkout')
    args = parser.parse_args()
    values = check(json.loads(args.libraries.read_text()) if args.libraries else library_fixtures())
    for value in values:print('PASS', value)
    print(len(values), 'common worker checks passed')
