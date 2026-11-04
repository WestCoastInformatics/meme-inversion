#!/usr/bin/env python3
"""Preserve a completed dev NCIt replay and run a new pinned candidate in place.

Release paths remain the production paths. Completed run artifacts are retained
under that release's etc/qa/replay-runs directory before current output is reset.
This is a bounded October characterization, not the general lifecycle runner.
"""
import base64
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import tempfile

ROOT = Path('/local/content/MEME/MEME5/inv')
VERSION = 'NCI_2026_10D'
TARGET = ROOT / 'sources' / VERSION
RUNS = TARGET / 'etc/qa/replay-runs'
ACTIVE = TARGET / 'etc/replay-active-run.json'
LOCK = RUNS / 'active.lock.json'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4194304), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value, mode=0o644):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Only tomcata on dev may advance this bounded replay')
    for path in [ROOT, ROOT / 'sources', TARGET, TARGET / 'src', TARGET / 'etc/qa', RUNS]:
        if path.is_symlink():
            raise RuntimeError('Unexpected symlink: ' + str(path))


def require_hash(path, expected):
    if path.is_symlink() or not path.is_file() or digest(path) != expected:
        raise RuntimeError('Unexpected artifact bytes: ' + str(path))


def publish_directory(staging, destination):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    libc.renameat2.restype = ctypes.c_int
    if libc.renameat2(-100, os.fsencode(staging), -100, os.fsencode(destination), 1):
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def core_is_running(shared_runtime=False):
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / 'cmdline').read_bytes().split(b'\0')
            if command and command[0].endswith(b'perl'):
                scripts = {Path(os.fsdecode(part)).name for part in command[1:] if part}
                cwd = (entry / 'cwd').resolve()
                if shared_runtime and scripts & {'invert_NCI.pl', 'invert_rf2.pl'} and cwd.is_relative_to(ROOT / 'sources'):
                    return True
                if 'invert_NCI.pl' in scripts and cwd == TARGET / 'bin':
                    return True
        except OSError:
            pass
    return False


def start(package, modules):
    guard()
    contract = package['contract']
    run_id = contract['run_id']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', run_id):
        raise RuntimeError('Invalid run ID')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', package['preserve_as']) or package['preserve_as'] == run_id:
        raise RuntimeError('Invalid preservation ID')
    if contract['version'] != VERSION or not re.fullmatch(r'[0-9a-f]{40}', contract['engine_ref']):
        raise RuntimeError('A pinned Git engine revision is required')
    current = json.loads((TARGET / 'etc/replay-core.json').read_text())
    expected_previous = package['previous_core']
    for key in ['engine_ref', 'started_at', 'completed_at', 'exit_status']:
        if current.get(key) != expected_previous.get(key):
            raise RuntimeError('Completed previous run does not match reviewed evidence')
    if current['exit_status'] != 0:
        raise RuntimeError('Only a completed successful inversion can be advanced')
    archive = Path(contract['reference']['archive_path'])
    if archive != ROOT / 'sources' / (VERSION + '.tgz'):
        raise RuntimeError('The frozen reference must use the standard archive path')
    require_hash(archive, contract['reference']['archive_sha256'])
    for item in contract['native_inputs'] + contract['archived_metadata_inputs'] + contract['preparation_reference_files']:
        require_hash(ROOT / 'sources' / item['path'], item['sha256'])
    previous_runtime = package.get('previous_runtime_files', package['runtime_files'])
    for item in previous_runtime:
        require_hash(Path(item['path']), item['sha256'])
    expected_output = {Path(item['path']).name: item['sha256'] for item in expected_previous['comparison']}
    if set(expected_output) != {'classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src'}:
        raise RuntimeError('Reviewed previous output manifest is incomplete')
    for name, expected in expected_output.items():
        require_hash(TARGET / 'src' / name, expected)
    for item in package['previous_code']:
        require_hash(TARGET / item['relative_path'], item['sha256'])
    previous_code = {item['relative_path']: item for item in package['previous_code']}
    next_code = {item['relative_path']: item for item in package['engine_files']}
    if set(previous_code) != set(next_code):
        raise RuntimeError('This advance cannot add/remove engine files')
    changed = [name for name in next_code if next_code[name]['sha256'] != previous_code[name]['sha256']]
    old_runtime = {item['path']: item for item in previous_runtime}
    next_runtime = {item['path']: item for item in package['runtime_files']}
    if set(old_runtime) != set(next_runtime):
        raise RuntimeError('This advance cannot add/remove runtime files')
    runtime_changed = [name for name in next_runtime if next_runtime[name]['sha256'] != old_runtime[name]['sha256']]
    if changed == ['bin/invert_NCI.pl'] and not runtime_changed:
        install_path = TARGET / changed[0]
        raw = base64.b64decode(package['changed_script_b64'], validate=True)
        expected_sha = next_code[changed[0]]['sha256']
        previous_sha = previous_code[changed[0]]['sha256']
    elif not changed and runtime_changed == [str(ROOT / 'INV/lib/Hierarchy.pm')]:
        install_path = ROOT / 'INV/lib/Hierarchy.pm'
        raw = base64.b64decode(package['changed_runtime_b64'], validate=True)
        expected_sha = next_runtime[str(install_path)]['sha256']
        previous_sha = old_runtime[str(install_path)]['sha256']
    else:
        raise RuntimeError('Only a separate inverter or hierarchy change is allowed in this characterization')
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError('Candidate bytes do not match the pinned Git file')
    if core_is_running(shared_runtime=bool(runtime_changed)):
        raise RuntimeError('A core inversion is already running in the release folder')
    if shutil.disk_usage(TARGET).free < 8 * 1024 ** 3:
        raise RuntimeError('At least 8 GiB free is required for preservation, output and comparison')
    RUNS.mkdir(exist_ok=True)
    run_dir = RUNS / run_id
    snapshot = RUNS / package['preserve_as']
    if run_dir.exists() or snapshot.exists():
        raise RuntimeError('Run or preserved baseline already exists; no overwrite is permitted')
    with LOCK.open('x') as handle:
        json.dump({'run_id': run_id, 'launcher_pid': os.getpid(), 'created_at': now()}, handle)
    launched = False
    staging = None
    try:
        run_dir.mkdir()
        active = {'run_id': run_id, 'engine_ref': contract['engine_ref'], 'status': 'preserving-baseline',
                  'run_directory': str(run_dir), 'preserved_baseline': str(snapshot), 'started_at': now()}
        save(ACTIVE, active)
        staging = Path(tempfile.mkdtemp(prefix='.preserve-', dir=str(RUNS)))
        move_names = ['src/' + name for name in expected_output]
        move_names += ['etc/replay-core.json', 'etc/replay-comparison.json', 'etc/replay-atom-diagnosis.json',
                       'etc/replay-restart.json', 'etc/qa/replay-core-inversion.log',
                       'etc/qa/invert_NCI_2026_10D.log', 'etc/qa/replay-core-worker.py',
                       'etc/qa/replay-core-worker.log', 'etc/qa/replay-core-inputs.json']
        move_names += contract['auxiliary_outputs_to_regenerate']
        keep_names = ['bin/invert_NCI.pl', 'etc/replay-case.json', 'etc/nci.cfg', 'src/sources.src', 'src/termgroups.src']
        records = []
        for name in move_names + keep_names:
            original = TARGET / name
            if not original.exists():
                if name in keep_names or name.startswith('src/') or name == 'etc/replay-core.json':
                    raise RuntimeError('Required baseline artifact is missing: ' + name)
                continue
            if original.is_symlink() or not original.is_file():
                raise RuntimeError('Only regular baseline files may be preserved')
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            original_sha = digest(original)
            shutil.copy2(original, destination)
            require_hash(destination, original_sha)
            records.append({'relative_path': name, 'sha256': original_sha, 'bytes': original.stat().st_size,
                            'original_mode': oct(original.stat().st_mode & 0o777), 'reset_current': name in move_names})
            destination.chmod(0o444)
        # A shared-library update also preserves the changed runtime bytes and
        # any prior active-runtime receipt before installing the new revision.
        runtime_preserve = [Path(name) for name in runtime_changed]
        if runtime_changed and (ROOT / 'candidate-runtime.json').exists():
            runtime_preserve.append(ROOT / 'candidate-runtime.json')
        for original in runtime_preserve:
            if original.is_symlink() or not original.is_file():
                raise RuntimeError('Only regular runtime artifacts may be preserved')
            relative = 'engine/' + str(original.relative_to(ROOT))
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            original_sha = digest(original)
            shutil.copy2(original, destination)
            require_hash(destination, original_sha)
            destination.chmod(0o444)
            records.append({'relative_path': relative, 'original_path': str(original), 'sha256': original_sha,
                            'bytes': original.stat().st_size, 'original_mode': oct(original.stat().st_mode & 0o777), 'reset_current': False})
        manifest = {'run_id': current.get('run_id') or 'baseline-core-20261103', 'engine_ref': current['engine_ref'],
                    'preserved_at': now(), 'files': records, 'new_candidate_run_id': run_id,
                    'native_inputs_retained_at_standard_path': True, 'archive_sha256': contract['reference']['archive_sha256'],
                    'runtime_files': previous_runtime}
        save(staging / 'preservation.json', manifest, 0o444)
        for directory, _, _ in os.walk(staging, topdown=False):
            Path(directory).chmod(0o555)
        publish_directory(staging, snapshot)
        staging = None
        # Every reset is reversible from the verified, read-only preserved copy.
        for item in records:
            if item['reset_current']:
                path = TARGET / item['relative_path']
                require_hash(path, item['sha256'])
                path.unlink()
        require_hash(install_path, previous_sha)
        fd, temporary = tempfile.mkstemp(prefix='.candidate-', dir=str(install_path.parent))
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
        os.chmod(temporary, install_path.stat().st_mode & 0o777)
        os.replace(temporary, install_path)
        for item in package['engine_files']:
            require_hash(TARGET / item['relative_path'], item['sha256'])
        for item in package['runtime_files']:
            require_hash(Path(item['path']), item['sha256'])
        if runtime_changed:
            save(ROOT / 'candidate-runtime.json', {'engine_ref': contract['engine_ref'], 'run_id': run_id,
                                                  'updated_at': now(), 'runtime_files': package['runtime_files'],
                                                  'changed_paths': runtime_changed, 'previous_runtime_preserved': str(snapshot),
                                                  'initial_installation_receipt': str(ROOT / 'installation-receipt.json')})
        if {path.name for path in (TARGET / 'src').iterdir()} != {'sources.src', 'termgroups.src'}:
            raise RuntimeError('Generated candidate output was not completely reset')
        apparatus = run_dir / 'apparatus'
        apparatus.mkdir()
        module_hashes = {}
        for name, item in modules.items():
            if Path(name).name != name or not name.endswith('.py'):
                raise RuntimeError('Invalid apparatus filename')
            code = base64.b64decode(item['data_b64'], validate=True)
            if hashlib.sha256(code).hexdigest() != item['sha256']:
                raise RuntimeError('Apparatus module hash differs')
            (apparatus / name).write_bytes(code)
            module_hashes[name] = item['sha256']
        package['preserved_baseline_path'] = str(snapshot)
        package['apparatus_sha256'] = module_hashes
        save(run_dir / 'request.json', package)
        program = run_dir / 'worker.py'
        program.write_text("import sys\nfrom pathlib import Path\nsys.dont_write_bytecode=True\n"
                           "sys.path.insert(0,str(Path(__file__).parent/'apparatus'))\n"
                           "from advance_nci_replay import worker\nraise SystemExit(worker(Path(__file__).parent/'request.json'))\n")
        worker_log = run_dir / 'worker.log'
        with worker_log.open('xb') as handle:
            process = subprocess.Popen(['/usr/bin/python3', '-B', '-u', str(program)], cwd=TARGET / 'bin',
                                       stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
                                       start_new_session=True, close_fds=True)
        launched = True
        launch = dict(active, status='worker-launched', worker_pid=process.pid, worker_log=str(worker_log),
                      changed_path=str(install_path), changed_sha256=expected_sha,
                      apparatus_sha256=module_hashes, completed_at=now())
        save(run_dir / 'launch.json', launch)
        return launch
    except Exception as error:
        save(ACTIVE, {'run_id': run_id, 'engine_ref': contract['engine_ref'], 'status': 'setup-failed',
                      'error': str(error), 'run_directory': str(run_dir), 'preserved_baseline': str(snapshot), 'at': now()})
        raise
    finally:
        if staging is not None and staging.exists():
            for directory, _, files in os.walk(staging):
                Path(directory).chmod(0o700)
                for name in files:
                    (Path(directory) / name).chmod(0o600)
            shutil.rmtree(staging)
        if not launched:
            LOCK.unlink(missing_ok=True)


def verdict(core, comparison):
    files = comparison['files']
    metadata = {item['file']: item for item in comparison['other_reference_src'] if item['role'] == 'declared-metadata-input'}
    checks = {'core_exit_zero': core.get('exit_status') == 0,
              'metadata_unchanged': core.get('metadata_unchanged') is True,
              'atoms_exact': files['classes_atoms.src']['exact_match'],
              'relationships_exact': files['relationships.src']['exact_match'],
              'merges_exact': files['mergefacts.src']['exact_match'],
              'context_multiset_equal': files['contexts.src']['row_multiset']['equal_preserving_multiplicity'],
              'attribute_content_equal': files['attributes.src']['content_multiset_excluding_generated_attribute_id']['equal_preserving_multiplicity'],
              'structural_checks': set(comparison['structure']) == {'reference', 'candidate'} and all(item['checks_passed'] for item in comparison['structure'].values()),
              'termgroups_valid': all(item['termgroup_validation']['passed'] for item in comparison['structure'].values()),
              'metadata_matches_reference': set(metadata) == {'sources.src', 'termgroups.src'} and all(item.get('exact_match') for item in metadata.values())}
    attributes = files['attributes.src']
    views = [attributes['reference_id_view'], attributes['candidate_id_view']]
    checks['attribute_ids_unique_and_contiguous'] = all(not v['duplicate_ids'] and not v['invalid_ids'] and v['unique_ids'] == v['rows'] == v['maximum_id'] - v['minimum_id'] + 1 for v in views)
    checks['same_attribute_id_span'] = (views[0]['minimum_id'], views[0]['maximum_id']) == (views[1]['minimum_id'], views[1]['maximum_id'])
    checks['non_context_attributes_exact'] = views[0]['non_context_full_record_sha256'] == views[1]['non_context_full_record_sha256']
    known_types = {'SRC_ATOM_ID', 'SOURCE_CUI', 'CODE_SOURCE'}
    checks['no_attribute_id_or_unknown_reference_types'] = all(
        set(item['identifier_types']).issubset(known_types)
        for group in comparison['structure'].values() for item in group['files'].values())
    return {'status': 'PASS_EQUIVALENT' if all(checks.values()) else 'FAIL', 'checks': checks,
            'comparison_profile': 'nci-core-v1: exact atoms/relationships/merges; full context multiset; attribute row-ID diagnostic with unique equal allocations and no attribute-ID references',
            'scope': 'Five generated core src outputs with archived source metadata; not full release eligibility'}


def worker(request):
    guard()
    package = json.loads(request.read_text())
    contract = package['contract']
    run_id = contract['run_id']
    run_dir = request.parent
    if json.loads(LOCK.read_text())['run_id'] != run_id:
        raise RuntimeError('Run lock does not belong to this worker')
    active = {'run_id': run_id, 'engine_ref': contract['engine_ref'], 'worker_pid': os.getpid(),
              'run_directory': str(run_dir), 'worker_log': str(run_dir / 'worker.log'),
              'preserved_baseline': package['preserved_baseline_path'], 'started_at': now(), 'status': 'running'}
    save(ACTIVE, active)
    try:
        from run_nci_core_replay import run
        from compare_nci_core import compare
        from check_core_comparison import check
        checks = check()
        print('PHASE: ' + str(len(checks)) + ' comparison/negative fixtures passed', flush=True)
        core = run(contract, package['engine_files'], package['runtime_files'])
        save(run_dir / 'core-result.json', core)
        if core.get('exit_status') != 0:
            raise RuntimeError('Core inverter did not complete successfully')
        comparison = compare(contract, fixture_checks=checks)
        save(run_dir / 'comparison-result.json', comparison)
        acceptance = verdict(core, comparison)
        for item in package['engine_files']:
            require_hash(TARGET / item['relative_path'], item['sha256'])
        for item in package['runtime_files']:
            require_hash(Path(item['path']), item['sha256'])
        for item in contract['native_inputs'] + contract['archived_metadata_inputs'] + contract['preparation_reference_files']:
            require_hash(ROOT / 'sources' / item['path'], item['sha256'])
        result = {'run_id': run_id, 'engine_ref': contract['engine_ref'], 'preparation_engine_ref': contract['preparation_engine_ref'],
                  'completed_at': now(), 'acceptance': acceptance, 'core': core, 'comparison': comparison,
                  'preserved_baseline': package['preserved_baseline_path'], 'apparatus_sha256': package['apparatus_sha256'],
                  'engine_and_inputs_verified_after_run': True, 'insertion_executed': False}
        save(run_dir / 'result.json', result)
        active.update(status='complete', acceptance_status=acceptance['status'], completed_at=result['completed_at'], result_path=str(run_dir / 'result.json'))
        save(ACTIVE, active)
        print('RESULT: ' + acceptance['status'], flush=True)
        return 0 if acceptance['status'] == 'PASS_EQUIVALENT' else 1
    except Exception as error:
        active.update(status='failed', error=str(error), completed_at=now())
        save(ACTIVE, active)
        save(run_dir / 'failure.json', active)
        raise
    finally:
        if LOCK.exists() and json.loads(LOCK.read_text()).get('run_id') == run_id:
            LOCK.unlink()
