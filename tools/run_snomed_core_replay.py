#!/usr/bin/env python3
"""Launch a pinned, network-isolated SNOMED core replay and comparison on dev."""
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
from replay_process import runtime_lock

import compare_snomed_core
from prepare_snomed_candidate import BASELINE, CORE_NAMES, ROOT, TARGET, VERSION, guard, info, now, require_hash, save, selected_inputs

RUN_ID = 'baseline-core-20261104'
RUN = TARGET / 'etc/qa/replay-runs' / RUN_ID
ACTIVE = TARGET / 'etc/replay-active-run.json'


def memory_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise RuntimeError('Cannot measure available memory')


def require_idle():
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts = (entry / 'cmdline').read_bytes().split(b'\0')
            if not parts or not parts[0].endswith(b'perl'):
                continue
            if {Path(os.fsdecode(x)).name for x in parts[1:] if x} & {'invert_NCI.pl', 'invert_rf2.pl'}:
                if (entry / 'cwd').resolve().is_relative_to(ROOT / 'sources'):
                    raise RuntimeError('Another inversion is using the shared dev runtime')
        except (FileNotFoundError, PermissionError):
            pass


def runtime_files(package, before=False):
    for item in package['runtime_files']:
        expected = item['sha256']
        if before and item['relative_path'] == 'INV/lib/Hierarchy.pm':
            expected = package['previous_hierarchy_sha256']
        require_hash(ROOT / item['relative_path'], expected)


def verify_case(package):
    contract = package['contract']
    if contract['run_id'] != RUN_ID or contract['engine_ref'] != BASELINE:
        raise RuntimeError('Unexpected pinned SNOMED request')
    require_hash(Path(contract['reference']['archive_path']), contract['reference']['archive_sha256'])
    for name, item in selected_inputs(contract).items():
        require_hash(ROOT / 'sources' / name, item['sha256'])
    verify_generated_configuration(package)
    for item in package['code_files']:
        if package.get('generated_configuration') is not None and item['relative_path'] == 'etc/sct.cfg':
            continue
        require_hash(TARGET / item['relative_path'], item['sha256'])


def verify_generated_configuration(package):
    """Recompute the transported recipe and inspect the actual operational cfg."""
    recipe = package.get('generated_configuration')
    inputs = package.get('configuration_generation_inputs')
    if recipe is None:
        if inputs is not None:
            raise ValueError('Configuration-generation inputs require a recipe')
        return
    import snomed_configuration
    snomed_configuration.validate_execution_recipe(recipe, inputs, contract=package['contract'],
                                                   code_files=package['code_files'])
    snomed_configuration.verify_generated(recipe, TARGET)


def activate_baseline(package):
    """Preserve the current tested library and receipt before restoring Git bytes."""
    if package.get('runtime_already_verified'):
        runtime_files(package)
        return
    require_idle()
    runtime_files(package, before=True)
    previous = RUN / 'runtime-before'
    previous.mkdir()
    library = ROOT / 'INV/lib/Hierarchy.pm'
    receipt = ROOT / 'candidate-runtime.json'
    for source in [library, receipt]:
        destination = previous / source.name
        shutil.copy2(source, destination)
        require_hash(destination, info(source)['sha256'])
        destination.chmod(0o444)
    previous.chmod(0o555)
    raw = base64.b64decode(package['baseline_hierarchy_b64'], validate=True)
    desired = next(x for x in package['runtime_files'] if x['relative_path'] == 'INV/lib/Hierarchy.pm')
    if hashlib.sha256(raw).hexdigest() != desired['sha256']:
        raise RuntimeError('Invalid baseline shared library payload')
    temporary = library.with_name('.Hierarchy.pm.snomed-baseline')
    with temporary.open('xb') as handle:
        handle.write(raw)
    temporary.chmod(library.stat().st_mode & 0o777)
    os.replace(temporary, library)
    runtime_files(package)
    save(receipt, {'engine_ref': BASELINE, 'activated_at': now(), 'reason': 'Unchanged production SNOMED replay',
                   'runtime_files': package['runtime_files'], 'previous_runtime_preserved': str(previous),
                   'source_run': str(RUN), 'initial_installation_receipt_unchanged': True})


def terminate(process):
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def isolated(command, stage, stdout_path, timeout=14400):
    """Bound just this child process and monitor dev capacity; retain partial output."""
    started = time.monotonic()
    lowest_available = memory_available()
    peak_rss = 0
    def limit():
        resource.setrlimit(resource.RLIMIT_AS, (22 * 1024 ** 3, 22 * 1024 ** 3))
    with stdout_path.open('xb') as output, (RUN / (stage + '.stderr.log')).open('xb') as errors:
        process = subprocess.Popen(['unshare', '--user', '--map-root-user', '--net'] + command,
                                   cwd=TARGET / 'bin', stdout=output, stderr=errors,
                                   start_new_session=True, preexec_fn=limit)
        try:
            while process.poll() is None:
                available = memory_available()
                lowest_available = min(lowest_available, available)
                if available < 2 * 1024 ** 3 or shutil.disk_usage(TARGET).free < 12 * 1024 ** 3:
                    raise RuntimeError('Development capacity reserve reached; stopped only this replay')
                if time.monotonic() - started > timeout:
                    raise RuntimeError('Stage timeout; partial artifacts retained')
                try:
                    status = (Path('/proc') / str(process.pid) / 'status').read_text()
                    rss = int(next(line for line in status.splitlines() if line.startswith('VmRSS:')).split()[1]) * 1024
                    peak_rss = max(peak_rss, rss)
                except (OSError, StopIteration):
                    pass
                save(RUN / 'progress.json', {'stage': stage, 'pid': process.pid, 'observed_at': now(),
                     'elapsed_seconds': round(time.monotonic() - started), 'resident_bytes': peak_rss,
                     'available_memory_bytes': available,
                     'output_bytes': {name: (TARGET / 'src' / name).stat().st_size for name in sorted(CORE_NAMES) if (TARGET / 'src' / name).exists()}})
                time.sleep(10)
        finally:
            terminate(process)
    return {'exit_status': process.returncode, 'elapsed_seconds': round(time.monotonic() - started, 2),
            'sampled_peak_resident_bytes': peak_rss, 'minimum_available_memory_bytes': lowest_available,
            'child_max_rss_bytes': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024}


def worker(package_path, inherited_lock=None):
    guard()
    package = json.loads(Path(package_path).read_text())
    started = now()
    state = {'run_id': RUN_ID, 'source': 'SNOMEDCT_US', 'version': VERSION, 'engine_ref': BASELINE,
             'started_at': started, 'status': 'running', 'run_directory': str(RUN), 'worker_pid': os.getpid()}
    save(ACTIVE, state)
    try:
        with runtime_lock(ROOT, inherited_lock):
            verify_case(package)
            if any((TARGET / 'src' / name).exists() for name in CORE_NAMES):
                raise RuntimeError('Generated outputs already exist; this worker will not overwrite them')
            if memory_available() < 24 * 1024 ** 3 or shutil.disk_usage(TARGET).free < 50 * 1024 ** 3:
                raise RuntimeError('Preflight capacity reserve is unavailable')
            activate_baseline(package)
            print('PHASE: baseline runtime verified; compiling original SNOMED scripts offline', flush=True)
            for script in ['invert_rf2.pl', 'rmdanglingattrs.pl']:
                subprocess.run(['unshare', '--user', '--map-root-user', '--net', '/usr/bin/perl', '-c', str(TARGET / 'bin' / script)],
                               cwd=TARGET / 'bin', check=True, timeout=30)
            contract = package['contract']
            core = {'source': 'SNOMEDCT_US', 'version': VERSION, 'engine_ref': BASELINE, 'run_id': RUN_ID,
                    'started_at': now(), 'network': 'disabled for conversion and cleanup',
                    'metadata_acquisition': 'archived sources/termgroups and ICD inventories used as declared inputs',
                    'insertion_executed': False, 'memory_address_space_limit_bytes': 22 * 1024 ** 3}
            save(TARGET / 'etc/replay-core.json', core)
            print('PHASE: running unchanged invert_rf2.pl', flush=True)
            core['conversion'] = isolated(['/usr/bin/perl', 'invert_rf2.pl'], 'conversion', RUN / 'conversion.stdout.log')
            core['exit_status'] = core['conversion']['exit_status']
            save(TARGET / 'etc/replay-core.json', core)
            if core['exit_status']:
                raise RuntimeError('Original RF2 converter exited nonzero; outputs and logs retained')
            verify_generated_configuration(package)
            for name in CORE_NAMES:
                path = TARGET / 'src' / name
                if path.is_symlink() or not path.is_file() or not path.stat().st_size:
                    raise RuntimeError('Missing or empty generated core file: ' + name)
            unfiltered = RUN / 'attributes.src.before-cleanup'
            os.rename(TARGET / 'src/attributes.src', unfiltered)
            core['before_attribute_cleanup'] = info(unfiltered)
            unfiltered.chmod(0o444)
            print('PHASE: original rmdanglingattrs.pl cleanup, preserving unfiltered attributes', flush=True)
            core['cleanup'] = isolated(['/usr/bin/perl', 'rmdanglingattrs.pl', str(unfiltered)], 'cleanup', TARGET / 'src/attributes.src', timeout=1800)
            core['cleanup_exit_status'] = core['cleanup']['exit_status']
            if core['cleanup_exit_status']:
                save(TARGET / 'etc/replay-core.json', core)
                raise RuntimeError('Original dangling-attribute cleanup exited nonzero')
            verify_generated_configuration(package)
            if package.get('generated_configuration') is not None:
                import snomed_configuration
                core['configuration_generation'] = snomed_configuration.receipt(package['generated_configuration'])
            core['files'] = {name: info(TARGET / 'src' / name) for name in sorted(CORE_NAMES)}
            core['attribute_cleanup_removed_rows'] = core['before_attribute_cleanup']['newline_count'] - core['files']['attributes.src']['newline_count']
            core['completed_at'] = now()
            save(TARGET / 'etc/replay-core.json', core)
            state.update(status='comparing', core_completed_at=core['completed_at'])
            save(ACTIVE, state)
            print('PHASE: core complete; comparing fresh files with the frozen official archive', flush=True)
            comparison = compare_snomed_core.compare(contract, core)
            verify_case(package)
            runtime_files(package)
            for name, item in core['files'].items():
                require_hash(TARGET / 'src' / name, item['sha256'])
            result = {'run_id': RUN_ID, 'engine_ref': BASELINE, 'completed_at': now(), 'core': core,
                      'comparison': comparison, 'acceptance': comparison['acceptance'],
                      'inputs_engine_runtime_and_outputs_verified_after_run': True, 'insertion_executed': False,
                      'apparatus_sha256': package['apparatus_sha256']}
            if package.get('generated_configuration') is not None:
                result['configuration_generation'] = core['configuration_generation']
            save(RUN / 'result.json', result)
            state.update(status='complete', acceptance_status=result['acceptance']['status'], completed_at=result['completed_at'], result_path=str(RUN / 'result.json'))
            save(ACTIVE, state)
            print('RESULT: ' + result['acceptance']['status'], flush=True)
    except BaseException as error:
        state.update(status='failed', completed_at=now(), error=str(error))
        save(ACTIVE, state)
        traceback.print_exc()
        raise


def launch(package, modules):
    guard()
    verify_case(package)
    require_idle()
    if RUN.exists() or ACTIVE.exists():
        raise RuntimeError('A replay already exists; preserve and review it before another attempt')
    RUN.mkdir(parents=True)
    apparatus = RUN / 'apparatus'
    apparatus.mkdir()
    package['apparatus_sha256'] = {}
    for name, raw in modules.items():
        if Path(name).name != name or not name.endswith('.py'):
            raise RuntimeError('Invalid apparatus filename')
        (apparatus / name).write_bytes(raw)
        (apparatus / name).chmod(0o444)
        package['apparatus_sha256'][name] = hashlib.sha256(raw).hexdigest()
    package_path = apparatus / 'request-lock.json'
    save(package_path, package)
    package_path.chmod(0o444)
    entry = apparatus / 'worker.py'
    entry.write_text('import run_snomed_core_replay as replay\nreplay.worker(' + repr(str(package_path)) + ')\n')
    entry.chmod(0o444)
    with (RUN / 'worker.log').open('xb') as log:
        process = subprocess.Popen([sys.executable, '-B', str(entry)], stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    return {'run_id': RUN_ID, 'engine_ref': BASELINE, 'status': 'worker-launched', 'worker_pid': process.pid,
            'run_directory': str(RUN), 'worker_log': str(RUN / 'worker.log'), 'launched_at': now(),
            'apparatus_sha256': package['apparatus_sha256']}
