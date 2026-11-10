#!/usr/bin/env python3
"""Dev-only execution of a frozen common request; no database, insertion or upload."""
import argparse
import base64
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback

from replay_process import available_memory, execute, runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
CONTROL = ROOT / 'qa/replay-requests'
VERSIONS = {'NCI': ('NCI_2026_10D', 'nci-oct2026-v1'),
            'SNOMEDCT_US': ('SNOMEDCT_US_2026_09_01', 'snomed-sep2026-v1'),
            'MTH': ('MTH_2026AA', 'mth-2026aa-v1'),
            'MDR':('MDR_29_1','mdr-29-1-v1'),'RADLEX':('RADLEX_4_3','radlex-4-3-v1')}
MTH_CORRECTION_ENGINE = 'b2611abcf929981628bb2e5051afb450b8525b70'
MTH_CORRECTION_AUDIT = {'profile': 'mth-retained-identities-v1', 'module': 'audit_mth_corrections.py'}
MDR_CORRECTION_ENGINE='dd7ae6610557074c1b7b66690538a0591987d056'
MDR_CORRECTION_AUDIT={'profile':'mdr-history-context-v1','module':'audit_mdr_corrections.py'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4194304), b''):
            value.update(block)
    return value.hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, value):
    import replay_mth_core
    replay_mth_core.save(path, value)


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Execution requires tomcata on ncias-d3777-c')
    for path in [ROOT, ROOT / 'sources', ROOT / 'qa', CONTROL]:
        if path.is_symlink():
            raise RuntimeError('Unexpected operational path symlink: ' + str(path))
    if os.environ.get('INV_HOME') != str(ROOT / 'INV') or os.environ.get('LC_COLLATE') != 'C':
        raise RuntimeError('Mirrored inversion environment is required')


def require_file(path, expected):
    if path.is_symlink() or not path.is_file() or sha(path) != expected:
        raise RuntimeError('Frozen artifact differs: ' + str(path))


def relative(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts or str(path) != name:
        raise ValueError('Unsafe artifact path: ' + name)
    return name


def correction_profile(lock):
    """A correction verdict is available only for this reviewed producer/case."""
    request, case = lock['request'], lock['case']
    if request['comparison_profile'] != 'reviewed-corrections':
        return False
    if request['source']=='MDR':
        expected=('MDR','MDR_29_1','consistent-history-context',MDR_CORRECTION_ENGINE)
        if tuple(request[key] for key in ('source','version','case_variant','engine_ref'))!=expected or case.get('correction_audit')!=MDR_CORRECTION_AUDIT or lock['runtime_ref']!='bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09':
            raise ValueError('Unreviewed MDR correction source/runtime/audit contract')
        if MDR_CORRECTION_AUDIT['module'] not in lock['modules_b64']:raise ValueError('Independent MDR audit is missing')
        if lock['configuration']['source_options']!={'language':'ENG'}:raise ValueError('Only the reviewed English MDR path is supported')
        return True
    expected = ('MTH', 'MTH_2026AA', 'consistent-retained-identities', MTH_CORRECTION_ENGINE)
    if tuple(request[key] for key in ('source', 'version', 'case_variant', 'engine_ref')) != expected:
        raise ValueError('Correction acceptance has no reviewed contract for this source/version/engine')
    if case.get('correction_audit') != MTH_CORRECTION_AUDIT or lock['runtime_ref'] != '3b125edc1d29f7c7a91673da2a8d752bb0adff44':
        raise ValueError('The MTH correction audit and production shared runtime must be pinned')
    if not all(case['legacy_case'].get(key) is True for key in ('execute_source_stages', 'validate_identity_state')):
        raise ValueError('Corrected producer stages and retained-identity validation are mandatory')
    if MTH_CORRECTION_AUDIT['module'] not in lock['modules_b64']:
        raise ValueError('The independent correction audit is missing from the frozen apparatus')
    return True


def verify_lock(lock):
    unsigned = {key: value for key, value in lock.items() if key != 'lock_sha256'}
    if lock.get('lock_sha256') != digest(unsigned):
        raise ValueError('Run lock content changed')
    if lock.get('artifact_type') != 'ncimeta-dev-replay-lock' or lock.get('schema_version') != 1:
        raise ValueError('Unsupported run lock')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', lock['run_id']):
        raise ValueError('Invalid run identity')
    request, config, case = lock['request'], lock['configuration'], lock['case']
    if VERSIONS.get(request['source']) != (request['version'], case['adapter']):
        raise ValueError('Unreviewed source/version adapter')
    if case['source'] != request['source'] or case['version'] != request['version']:
        raise ValueError('Case release identity differs')
    if lock['case_sha256'] != digest(case) or config != case['configuration']:
        raise ValueError('Resolved configuration differs from reviewed case')
    if request['engine_ref'] not in case['reviewed_engine_refs'] or config['engine_ref'] != request['engine_ref']:
        raise ValueError('Unreviewed engine revision')
    for key in ('case_variant', 'reference_stage', 'comparison_profile'):
        if request[key] != case[key] or config['replay'][key] != request[key]:
            raise ValueError('Request conflicts with case: ' + key)
    if request['reference_stage'] != 'inversion-src' or lock['execution_enabled'] != case['execution_enabled']:
        raise ValueError('Unsupported reference boundary or execution gate')
    if len(lock['runtime_files']) != 169:
        raise ValueError('Complete shared runtime inventory is required')
    if lock['runtime_ref'] != case['runtime_ref']:
        raise ValueError('Selected shared runtime revision differs from case')
    expected_runtime = {x['relative_path']: x for x in case['runtime_files']}
    expected_source = {x['relative_path']: x for x in case['source_files']}
    names = set()
    for item in lock['runtime_files']:
        name = relative(item['repository_path'])
        if not name.startswith(('INV/', 'ENV/')) or name in names:
            raise ValueError('Invalid runtime inventory')
        names.add(name)
        if name not in expected_runtime or item['sha256'] != expected_runtime[name]['sha256'] or item['mode'] != expected_runtime[name]['mode']:
            raise ValueError('Runtime inventory differs from reviewed case')
        if hashlib.sha256(base64.b64decode(item['data_b64'], validate=True)).hexdigest() != item['sha256']:
            raise ValueError('Runtime payload differs')
    if names != set(expected_runtime):
        raise ValueError('Runtime inventory is incomplete')
    names = set()
    for item in lock['code_files']:
        name = relative(item.get('relative_path') or str(PurePosixPath(item['repository_path']).relative_to('sources/' + request['version'])))
        if name in names:
            raise ValueError('Duplicate source code path')
        names.add(name)
        expected = expected_source.get(name)
        if expected is None or any(item.get(key) != expected.get(key) for key in ('kind', 'mode', 'sha256', 'target')):
            raise ValueError('Source inventory differs from reviewed case')
        if item.get('kind') != 'symlink' and hashlib.sha256(base64.b64decode(item['data_b64'], validate=True)).hexdigest() != item['sha256']:
            raise ValueError('Source payload differs')
    if names != set(expected_source) or not names:
        raise ValueError('Source inventory is incomplete')
    if (request['source'] == 'NCI' and request['case_variant'] in ('generated-configuration', 'source-plan')) or case.get('configuration_generation') or 'configuration_generation' in lock:
        if request['source'] != 'NCI' or request['case_variant'] not in ('generated-configuration', 'source-plan') or case.get('source_package') != 'engines/nci':
            raise ValueError('Unreviewed generated-configuration case')
        if any(x.get('repository_path') != 'engines/nci/' + x['relative_path'] for x in lock['code_files']):
            raise ValueError('Canonical source package path differs')
        import nci_configuration
        expected_profile = 'nci-properties-v1' if request['case_variant'] == 'generated-configuration' else 'nci-source-plan-v1'
        if case['configuration_generation']['profile'] != expected_profile:
            raise ValueError('NCIt case variant differs from the reviewed generator profile')
        nci_configuration.from_lock(lock)
    elif 'source_package' in case:
        raise ValueError('A canonical package requires its generated configuration contract')
    if request['source'] in ('MDR','RADLEX'):
        data=case['legacy_case'];bounds=config['source_atom_ids']
        if (bounds['start'],bounds['end'])!=(data['source_atom_ids']['start'],data['source_atom_ids']['end']):raise ValueError('Framework ID bounds differ from reviewed inputs')
        if config['replacement_baseline']!={'source':request['source'],'version':data['replacement_baseline']} or config['inputs']['source_data_stage']!=data['starting_stage']:
            raise ValueError('Framework input stage/replacement baseline differs')
        if request['source']=='MDR':
            if config['source_options']!={'language':'ENG'} or bounds.get('bound_kind')!='reserved-historical-range':raise ValueError('Unreviewed MDR language/ID provenance')
        elif config['source_options']!={} or bounds.get('bound_kind')!='historical-emitted-range' or data['source_atom_ids']['production_reservation_end_assessed']:
            raise ValueError('RADLEX emitted bounds cannot imply a production reservation')
    correction_profile(lock)
    return ROOT / 'sources' / request['version']


def runtime(lock):
    for item in lock['runtime_files']:
        require_file(ROOT / item['repository_path'], item['sha256'])


def capacity(lock):
    """Use only reviewed case budgets; retain the per-stage 12 GiB reserve."""
    profile=lock['case'].get('capacity_profile')
    minimum=50
    if profile is not None:
        reviewed={('MTH','MTH_2026AA','mth-2026aa-core-v1'):45,
                  ('NCI','NCI_2026_10D','nci-oct2026-core-v1'):18,
                  ('MDR','MDR_29_1','mdr-29-1-core-v1'):20,
                  ('RADLEX','RADLEX_4_3','radlex-4-3-core-v1'):18}
        key=(lock['request']['source'],lock['request']['version'],profile.get('id'))
        minimum=reviewed.get(key)
        if minimum is None or profile.get('minimum_free_disk_gib')!=minimum:
            raise RuntimeError('Unreviewed source/version capacity profile')
    if available_memory()<24*1024**3 or shutil.disk_usage(ROOT).free<minimum*1024**3:
        raise RuntimeError('Dev capacity reserve is unavailable')
    return {'minimum_free_disk_gib':minimum,'per_stage_reserve_gib':12}


def activate_runtime(lock):
    """Switch the one characterized shared-library difference while dev is idle."""
    guard()
    verify_lock(lock)
    if not lock['execution_enabled']:
        raise RuntimeError('Case execution remains gated')
    with runtime_lock(ROOT):
        idle()
        changed = []
        for item in lock['runtime_files']:
            path = ROOT / item['repository_path']
            if path.is_symlink() or not path.is_file():
                raise RuntimeError('Unexpected installed runtime path')
            current = sha(path)
            if current != item['sha256']:
                changed.append((item, current))
        if not changed:
            return {'status': 'runtime-already-matches', 'runtime_ref': lock['runtime_ref'], 'files_verified': 169}
        known = {'cf48727df7cebb3eb2b24510211c652519097b45a17381dae08ffe6b046732f0',
                 '0546741f832945df7c1230b8433058e6ceaea20d398f10d894a4131f67db07e5'}
        if len(changed) != 1 or changed[0][0]['repository_path'] != 'INV/lib/Hierarchy.pm' or changed[0][1] not in known or changed[0][0]['sha256'] not in known:
            raise RuntimeError('Runtime activation supports only the separately characterized production/stable-order Hierarchy.pm pair')
        item, previous_hash = changed[0]
        library = ROOT / item['repository_path']
        before = library.read_bytes()
        mode = library.stat().st_mode & 0o777
        CONTROL.mkdir(parents=True, exist_ok=True)
        preserved = CONTROL / (lock['run_id'] + '.runtime-before')
        preserved.mkdir()
        backup = preserved / 'Hierarchy.pm'
        backup.write_bytes(before)
        require_file(backup, previous_hash)
        backup.chmod(0o444)
        previous_receipt = ROOT / 'candidate-runtime.json'
        old_receipt = None
        old_receipt_mode = None
        if previous_receipt.exists():
            if previous_receipt.is_symlink():
                raise RuntimeError('Runtime receipt must not be a symlink')
            shutil.copy2(previous_receipt, preserved / 'candidate-runtime.json')
            old_receipt = previous_receipt.read_bytes()
            old_receipt_mode = previous_receipt.stat().st_mode & 0o777
            require_file(preserved / 'candidate-runtime.json', hashlib.sha256(old_receipt).hexdigest())
            (preserved / 'candidate-runtime.json').chmod(0o444)
        preserved.chmod(0o555)
        def replace(raw, destination=library, access=mode):
            descriptor, name = tempfile.mkstemp(prefix='.' + destination.name + '.common-', dir=str(destination.parent))
            temporary = Path(name)
            try:
                with os.fdopen(descriptor, 'wb') as out:
                    out.write(raw)
                temporary.chmod(access)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        receipt = {'status': 'runtime-activated', 'runtime_ref': lock['runtime_ref'], 'activated_at': now(),
                   'source': lock['request']['source'], 'lock_sha256': lock['lock_sha256'],
                   'preserved_runtime': str(preserved), 'previous_sha256': previous_hash,
                   'sha256': item['sha256'], 'files_verified': 169}
        try:
            replace(base64.b64decode(item['data_b64'], validate=True))
            runtime(lock)
            save(ROOT / 'candidate-runtime.json', receipt)
            save(CONTROL / (lock['run_id'] + '.runtime-activation.json'), receipt)
        except BaseException:
            replace(before)
            require_file(library, previous_hash)
            if old_receipt is not None:
                replace(old_receipt, previous_receipt, old_receipt_mode)
            else:
                previous_receipt.unlink(missing_ok=True)
            raise
        return receipt


def idle():
    import replay_mth_core
    replay_mth_core.idle()


def manifest(target):
    import replay_mth_core
    return replay_mth_core.tree_manifest(target)


def inspect_current(source):
    """A read-only receipt pins every file/link/mode before explicit preservation."""
    guard()
    if source not in VERSIONS:
        raise ValueError('No executable source adapter')
    target = ROOT / 'sources' / VERSIONS[source][0]
    with runtime_lock(ROOT):
        idle()
        if target.is_symlink() or not target.is_dir():
            raise RuntimeError('Expected existing regular source directory')
        for state_path in [target / 'replay-active-run.json', target / 'etc/replay-active-run.json']:
            if state_path.exists() and json.loads(state_path.read_text()).get('status') not in ('complete', 'failed'):
                raise RuntimeError('The existing release has an unfinished run')
        receipt = {'source': source, 'version': target.name, 'captured_at': now(),
                   'root_mode': oct(target.stat().st_mode & 0o777), 'manifest': manifest(target)}
        idle()
        receipt['receipt_sha256'] = digest(receipt)
        return receipt


def preserve(target, run_id, receipt, before_publish=lambda: None):
    if not target.exists():
        if receipt is not None:
            raise RuntimeError('Declared previous source folder is absent')
        return None
    if receipt is None:
        raise RuntimeError('Existing source folder requires an inspect-current receipt; nothing overwritten')
    raw = {k: v for k, v in receipt.items() if k != 'receipt_sha256'}
    if receipt['receipt_sha256'] != digest(raw) or receipt['version'] != target.name:
        raise RuntimeError('Previous source receipt differs')
    if oct(target.stat().st_mode & 0o777) != receipt['root_mode'] or manifest(target) != receipt['manifest']:
        raise RuntimeError('Previous source tree changed after inspection')
    destination = target.with_name(target.name + '.before-' + run_id)
    if destination.exists() or destination.is_symlink():
        raise RuntimeError('Preserved source directory already exists')
    before_publish()
    from prepare_snomed_candidate import publish
    publish(target, destination)
    try:
        if manifest(destination) != receipt['manifest']:
            raise RuntimeError('Previous source changed during preservation')
        for item in reversed(receipt['manifest']):
            if item['kind'] != 'symlink':
                (destination / item['path']).chmod(int(item['mode'], 8) & ~0o222)
        destination.chmod(int(receipt['root_mode'], 8) & ~0o222)
    except BaseException:
        restore(destination, target, receipt)
        raise
    return destination


def restore(preserved, target, receipt):
    if target.exists() or target.is_symlink():
        raise RuntimeError('Rollback would overwrite candidate data')
    preserved.chmod(int(receipt['root_mode'], 8))
    for item in receipt['manifest']:
        if item['kind'] != 'symlink':
            (preserved / item['path']).chmod(int(item['mode'], 8))
    from prepare_snomed_candidate import publish
    publish(preserved, target)


def source_files(lock):
    result = copy.deepcopy(lock['code_files'])
    for item in result:
        item['relative_path'] = item.get('relative_path') or str(PurePosixPath(item['repository_path']).relative_to('sources/' + lock['request']['version']))
        item['path'] = item.get('repository_path')
    return result


def acquire_inputs(lock, run):
    """Reuse verified caches or download only declared archives via existing tools."""
    import acquire_inversion_reference
    acquired = []
    case = lock['case']
    for item in case['acquisition']['archives']:
        archive = Path(item['archive_path'])
        version = archive.name.removesuffix('.tgz')
        if archive != ROOT / 'sources' / (version + '.tgz') or not version.startswith(lock['request']['source'] + '_'):
            raise ValueError('Archive is outside the reviewed source cache')
        downloaded = False
        if not archive.exists():
            receipt = acquire_inversion_reference.acquire({'source': lock['request']['source'], 'version': version,
                'engine_ref': lock['request']['engine_ref'], 'pull_helper_sha256': case['acquisition']['pull_helper_sha256'],
                'expected_code': []})
            downloaded = receipt['downloaded_this_run']
        require_file(archive, item['archive_sha256'])
        acquired.append({'archive_path': str(archive), 'sha256': item['archive_sha256'], 'downloaded_this_run': downloaded})
    if lock['request']['source'] == 'MTH':
        import acquire_mth_subset
        expected = case['legacy_case']['prepared_subset']
        receipt = acquire_mth_subset.acquire(expected['request'])
        if receipt['files'] != expected['files']:
            raise RuntimeError('Prepared subset differs from the case; input generation is not substituted')
    save(run / 'acquisition.json', {'archives': acquired, 'aws_profile': case['acquisition']['aws_profile'],
                                  'generated_outputs_restored': False})


def package(lock):
    data = copy.deepcopy(lock['case']['legacy_case'])
    request = lock['request']
    if request['source'] == 'NCI':
        data.update(run_id=lock['run_id'], engine_ref=request['engine_ref'], preparation_engine_ref=request['engine_ref'])
        if 'configuration_generation' in lock:
            data['generated_configuration'] = copy.deepcopy(lock['configuration_generation'])
        return data
    if request['source'] == 'SNOMEDCT_US':
        data['contract'].update(run_id=lock['run_id'], engine_ref=request['engine_ref'])
        data['code_files'] = source_files(lock)
        data['runtime_already_verified'] = True
    elif request['source']=='MTH':
        data.update(run_id=lock['run_id'], engine_ref=request['engine_ref'], runtime_ref=lock['runtime_ref'],
                    apparatus_ref=lock['apparatus_ref'],
                    code_files=source_files(lock), preserved_directory=request['version'] + '.before-unused-' + lock['run_id'])
    else:
        data.update(run_id=lock['run_id'],engine_ref=request['engine_ref'],runtime_ref=lock['runtime_ref'],apparatus_ref=lock['apparatus_ref'],
                    case_variant=request['case_variant'],code_files=source_files(lock),schema_version=1,artifact_type='ncimeta-framework-characterization')
    data['runtime_files'] = [{'relative_path': item['repository_path'], 'sha256': item['sha256']} for item in lock['runtime_files']]
    data['apparatus_sha256'] = {name: hashlib.sha256(base64.b64decode(raw)).hexdigest() for name, raw in lock['modules_b64'].items()}
    if request['source'] in ('MDR','RADLEX'):data['capsule_sha256']=digest(data)
    return data


def prepare(lock, target):
    data = package(lock)
    source = lock['request']['source']
    if source == 'NCI':
        import prepare_nci_candidate
        return prepare_nci_candidate.prepare(data, source_files(lock))
    if source == 'SNOMEDCT_US':
        import prepare_snomed_candidate
        return prepare_snomed_candidate.prepare(data['contract'], data['code_files'])
    if source in ('MDR','RADLEX'):
        import replay_framework_core
        return replay_framework_core.prepare(data)
    import replay_mth_core
    replay_mth_core.configure_case(data)
    return replay_mth_core.prepare(data)


def convert(lock, target, run, held_lock):
    data = package(lock)
    source = lock['request']['source']
    if source == 'NCI':
        import compare_nci_core
        from advance_nci_replay import verdict
        from run_nci_core_replay import info
        metrics = execute(['/usr/bin/perl', 'invert_NCI.pl'], cwd=target / 'bin',
                          stdout=run / 'conversion.stdout.log', stderr=run / 'conversion.stderr.log', env=os.environ.copy(),
                          progress=lambda values: save(run / 'progress.json', {'stage': 'conversion', **values}))
        core = {'source': source, 'version': target.name, 'engine_ref': data['engine_ref'], 'run_id': lock['run_id'],
                'exit_status': metrics['exit_status'], 'conversion': metrics,
                'metadata_unchanged': all(sha(ROOT / 'sources' / item['path']) == item['sha256'] for item in data['archived_metadata_inputs']),
                'comparison': [info(target / 'src' / Path(item['path']).name) for item in data['core_outputs_to_regenerate']]}
        save(target / 'etc/replay-core.json', core)
        comparison = compare_nci_core.compare(data)
        result = {'core': core, 'comparison': comparison, 'acceptance': verdict(core, comparison)}
        if 'configuration_generation' in lock:
            import nci_configuration
            result['configuration_generation'] = nci_configuration.receipt(lock['configuration_generation'])
            if lock['configuration_generation']['profile'] == 'nci-source-plan-v1':
                result['source_plan_preflight'] = json.loads((run / 'preparation.json').read_text())['source_plan_preflight']
                result['release_readiness'] = 'Historical compatibility only; declared findings require review before operational use'
        return result
    if source == 'SNOMEDCT_US':
        import run_snomed_core_replay as replay
        replay.RUN_ID = lock['run_id']
        replay.RUN = target / 'etc/qa/replay-runs' / lock['run_id']
        replay.ACTIVE = target / 'etc/replay-active-run.json'
    elif source in ('MDR','RADLEX'):
        import replay_framework_core as framework
        inner=target/'etc/qa/replay-runs'/lock['run_id'];inner.mkdir(parents=True)
        request_path=inner/'common-adapter-package.json';save(request_path,data);request_path.chmod(0o444)
        framework.worker(request_path,inherited_lock=held_lock,prepared_by_common=True,audit_corrections=False)
        return json.loads((inner/'result.json').read_text())
    else:
        import replay_mth_core as replay
        replay.configure_case(data)
    replay.RUN.mkdir(parents=True)
    request_path = replay.RUN / 'common-adapter-package.json'
    save(request_path, data)
    request_path.chmod(0o444)
    replay.worker(request_path, inherited_lock=held_lock)
    return json.loads((replay.RUN / 'result.json').read_text())


def verify_after(lock, target, result):
    runtime(lock)
    if lock['request']['source'] == 'NCI':
        data = package(lock)
        require_file(Path(data['reference']['archive_path']), data['reference']['archive_sha256'])
        for item in data['native_inputs'] + data['archived_metadata_inputs'] + data['preparation_reference_files']:
            require_file(ROOT / 'sources' / item['path'], item['sha256'])
        result['core']['metadata_unchanged'] = True
        if 'configuration_generation' in lock:
            import nci_configuration
            generated = nci_configuration.from_lock(lock)
            nci_configuration.verify_metadata(generated, target)
            nci_configuration.verify_files(generated, target)
    elif lock['request']['source'] in ('MDR','RADLEX'):
        import replay_framework_core
        replay_framework_core.verify_inputs(package(lock),target)
    for item in source_files(lock):
        path = target / item['relative_path']
        if item.get('kind') == 'symlink':
            if not path.is_symlink() or os.readlink(path) != item['target']:
                raise RuntimeError('Source topology changed')
        else:
            require_file(path, item['sha256'])
    bounds = lock['configuration']['source_atom_ids']
    bad = 0
    with (target / 'src/classes_atoms.src').open('rb') as handle:
        for row in handle:
            identifier = row.split(b'|', 1)[0]
            bad += not identifier.isdigit() or not bounds['start'] <= int(identifier) <= bounds['end']
    if bad:
        raise RuntimeError('Atoms outside the complete declared historical ID range: ' + str(bad))
    # A profile called exact can never inherit a broader adapter verdict.
    files = result['comparison']['files']
    for name, item in files.items():
        if Path(name).name != name:
            raise RuntimeError('Unexpected compared output name')
        require_file(target / 'src' / name, item['candidate']['sha256'])
    result['compared_output_hashes_verified_after_run'] = True
    exact = all(item.get('exact_match', item.get('raw_exact_match', False)) for item in files.values())
    if lock['request']['comparison_profile'] == 'exact' and not exact:
        result['acceptance'] = {**result['acceptance'], 'status': 'DIFFERENCES_REQUIRE_REVIEW', 'requested_profile': 'exact'}


def review_corrections(lock, target, run, result):
    """Preserve raw evidence, then independently adjudicate the reviewed delta."""
    if not correction_profile(lock):
        return
    expected_identity = {**{key: lock['request'][key] for key in ('source', 'version', 'engine_ref')},
                         'run_id': lock['run_id']}
    if any(result.get(key) != value for key, value in expected_identity.items()):
        raise RuntimeError('Raw correction result does not belong to this requested run')
    is_mdr=lock['request']['source']=='MDR'
    if is_mdr:
        validation=result['comparison']['structure']['candidate']
        if not validation.get('checks_passed') or not result['comparison']['files']['attributes.src']['attribute_diagnostics']['positive_unique_ids']:
            raise RuntimeError('MDR corrections require clean candidate validation and unique positive attribute IDs')
    else:
        validation = result['comparison']['validation']
        if not validation.get('passed') or not validation.get('identity_state', {}).get('passed'):
            raise RuntimeError('Correction acceptance requires clean core and retained-identity validation')
    if result['acceptance']['status'] != 'DIFFERENCES_REQUIRE_REVIEW':
        raise RuntimeError('Correction acceptance requires the preserved raw difference verdict')
    data = package(lock)
    names = {item['output_name'] for item in data['reference_files']}
    required=5 if is_mdr else 23
    if len(names) != required or set(result['comparison']['files']) != names:
        raise RuntimeError('The correction audit requires all '+str(required)+' characterized outputs')
    raw_path, package_path = run / 'raw-result.json', run / 'correction-audit-package.json'
    for path, value in ((raw_path, result), (package_path, data)):
        if path.exists() or path.is_symlink():
            raise FileExistsError('Correction evidence already exists: ' + str(path))
        save(path, value)
        path.chmod(0o444)
    raw_sha = sha(raw_path)
    audit_name = (MDR_CORRECTION_AUDIT if is_mdr else MTH_CORRECTION_AUDIT)['module']
    audit_path = Path(__file__).with_name(audit_name)
    expected_sha = hashlib.sha256(base64.b64decode(lock['modules_b64'][audit_name], validate=True)).hexdigest()
    require_file(audit_path, expected_sha)
    metrics = execute([sys.executable, '-B', str(audit_path), str(package_path), str(target), str(run),
                       '--result', str(raw_path)], cwd=target / 'src',
                      stdout=run / 'correction-audit.stdout.log', stderr=run / 'correction-audit.stderr.log',
                      env=os.environ.copy(), timeout=3600, namespace_user='current',
                      progress=lambda values: save(run / 'progress.json', {'stage': 'correction-audit', **values}))
    if metrics['exit_status'] != 0:
        raise RuntimeError('Independent correction audit failed')
    save(run / 'correction-audit-execution.json', metrics)
    (run / 'correction-audit-execution.json').chmod(0o444)
    report_path = run / 'correction-audit.json'
    if report_path.is_symlink() or not report_path.is_file():
        raise RuntimeError('Independent correction audit did not publish a regular report')
    report = json.loads(report_path.read_text())
    expected = {'status': 'PASS_REVIEWED_CORRECTIONS', 'engine_ref': data['engine_ref'], 'run_id': lock['run_id'],
                'conversion_apparatus_ref': lock['apparatus_ref'], 'audit_tool_sha256': expected_sha,
                'raw_comparison_status': 'DIFFERENCES_REQUIRE_REVIEW', 'independent_validation_passed': True,
                'raw_comparison_rewritten': False, 'production_eligible': False}
    if any(report.get(key) != value for key, value in expected.items()):
        raise RuntimeError('Correction audit identity, scope or verdict differs from this run')
    require_file(raw_path, raw_sha)
    if is_mdr:
        if report.get('runtime_ref')!=lock['runtime_ref'] or report.get('expected_attribute_sha256')!=result['comparison']['files']['attributes.src']['candidate']['sha256']:
            raise RuntimeError('MDR audit must predict the complete attribute file for the selected runtime')
        import replay_framework_core
        replay_framework_core.verify_inputs(data,target)
    else:
        import replay_mth_core
        replay_mth_core.verify_inputs(data, target)
    for name, entry in result['comparison']['files'].items():
        require_file(target / 'src' / name, entry['candidate']['sha256'])
    result['raw_acceptance'] = copy.deepcopy(result['acceptance'])
    result['raw_result_sha256'] = raw_sha
    result['correction_audit'] = report
    result['correction_audit_execution'] = metrics
    result['acceptance'] = {**result['acceptance'], 'status': 'PASS_REVIEWED_CORRECTIONS',
                            'requested_profile': 'reviewed-corrections', 'native_derived_correction_audit_passed': True,
                            'raw_comparison_preserved': True, 'production_eligible': False}


def verify_audit_review(capsule):
    unsigned = {key: value for key, value in capsule.items() if key != 'capsule_sha256'}
    if capsule.get('capsule_sha256') != digest(unsigned) or capsule.get('artifact_type') != 'ncimeta-mth-audit-review' or capsule.get('schema_version') != 1:
        raise ValueError('Invalid audit review capsule')
    for key in ('parent_run_id', 'review_id'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', capsule[key]):
            raise ValueError('Invalid audit review identity')
    if capsule['parent_run_id'] == capsule['review_id'] or not re.fullmatch(r'[0-9a-f]{40}', capsule['apparatus_ref']):
        raise ValueError('A new review identity and pinned apparatus are required')


def audit_parent(parent_id):
    parent = CONTROL / parent_id
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError('Expected a regular parent control directory')
    names = ('case.lock.json', 'raw-result.json', 'status.json')
    if any((parent / name).is_symlink() or not (parent / name).is_file() for name in names):
        raise RuntimeError('Parent lock, completed raw result and failed status are required')
    lock, raw, state = (json.loads((parent / name).read_text()) for name in names)
    target = verify_lock(lock)
    if lock['run_id'] != parent_id or not correction_profile(lock):
        raise RuntimeError('Parent is not the reviewed MTH correction case')
    if state.get('status') != 'failed' or 'correction-audit' not in state.get('error', ''):
        raise RuntimeError('Only a failed correction audit can be retried by this operation')
    if not raw['comparison']['validation']['passed'] or not raw['comparison']['validation']['identity_state']['passed']:
        raise RuntimeError('Completed clean core/identity validation is required before audit retry')
    expected = {key: lock['request'][key] for key in ('source', 'version', 'engine_ref')}
    expected['run_id'] = parent_id
    if any(raw.get(key) != value for key, value in expected.items()) or raw.get('acceptance', {}).get('status') != 'DIFFERENCES_REQUIRE_REVIEW':
        raise RuntimeError('Parent raw result identity or verdict differs from its correction case')
    output_names = {item['output_name'] for item in lock['case']['legacy_case']['reference_files']}
    if len(output_names) != 23 or set(raw['comparison']['files']) != output_names or raw.get('input_engine_runtime_and_output_hashes_verified_after_run') is not True:
        raise RuntimeError('Completed verification of all 23 parent outputs is required')
    return lock, raw, target, {name: sha(parent / name) for name in names}


def install_apparatus(run, capsule):
    apparatus = run / 'apparatus';apparatus.mkdir()
    hashes = {Path(item['repository_path']).name: item['sha256'] for item in capsule['provenance'] if item['repository_path'].startswith('tools/')}
    for name, encoded in capsule['modules_b64'].items():
        if Path(name).name != name or not name.endswith('.py'):
            raise ValueError('Invalid apparatus name')
        raw = base64.b64decode(encoded, validate=True)
        if hashlib.sha256(raw).hexdigest() != hashes.get(name):
            raise ValueError('Apparatus differs from frozen provenance')
        (apparatus / name).write_bytes(raw);(apparatus / name).chmod(0o444)
    return apparatus


def launch_audit_review(capsule):
    """Retry only the audit in a new control directory; never change the failed run."""
    guard();verify_audit_review(capsule)
    run = CONTROL / capsule['review_id']
    if run.exists() or run.is_symlink():
        raise FileExistsError('Review identity already exists')
    with runtime_lock(ROOT) as held:
        idle()
        lock, raw, target, snapshot = audit_parent(capsule['parent_run_id'])
        runtime(lock)
        if available_memory() < 24 * 1024 ** 3 or shutil.disk_usage(ROOT).free < 50 * 1024 ** 3:
            raise RuntimeError('Dev capacity reserve is unavailable')
        run.mkdir()
        apparatus = install_apparatus(run, capsule)
        request = run / 'review-request.json';save(request, capsule);request.chmod(0o444)
        save(run / 'parent-records.json', snapshot);(run / 'parent-records.json').chmod(0o444)
        entry = run / 'worker.py'
        entry.write_text('import os,sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,' + repr(str(apparatus)) + ')\n'
                         'from inversion_worker import audit_review_worker\nwith os.fdopen(' + str(held.fileno()) + ", 'a') as held:\n audit_review_worker(" + repr(str(request)) + ',inherited_lock=held)\n')
        entry.chmod(0o444)
        save(run / 'status.json', {'status': 'launching', 'source': 'MTH', 'run_id': capsule['review_id'], 'parent_run_id': capsule['parent_run_id'], 'mode': 'correction-audit-only'})
        with (run / 'worker.log').open('xb') as out:
            process = subprocess.Popen([sys.executable, '-B', '-u', str(entry)], stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
                                       close_fds=True, pass_fds=(held.fileno(),))
        result = {'run_id': capsule['review_id'], 'parent_run_id': capsule['parent_run_id'], 'worker_pid': process.pid,
                  'run_directory': str(run), 'launched_at': now(), 'capsule_sha256': capsule['capsule_sha256'], 'mode': 'correction-audit-only'}
        save(run / 'launch.json', result)
        return result


def audit_review_worker(request_path, inherited_lock=None):
    guard()
    capsule = json.loads(Path(request_path).read_text());verify_audit_review(capsule)
    run = Path(request_path).parent
    state = {'source': 'MTH', 'version': 'MTH_2026AA', 'run_id': capsule['review_id'], 'parent_run_id': capsule['parent_run_id'],
             'started_at': now(), 'status': 'auditing', 'mode': 'correction-audit-only', 'audit_apparatus_ref': capsule['apparatus_ref']}
    save(run / 'status.json', state)
    try:
        with runtime_lock(ROOT, inherited_lock):
            idle()
            lock, raw, target, snapshot = audit_parent(capsule['parent_run_id'])
            if snapshot != json.loads((run / 'parent-records.json').read_text()):
                raise RuntimeError('Parent records changed after review launch')
            import replay_mth_core
            replay_mth_core.verify_inputs(package(lock), target)
            verify_after(lock, target, copy.deepcopy(raw))
            result = copy.deepcopy(raw)
            review_corrections(lock, target, run, result)
            if result['raw_result_sha256'] != snapshot['raw-result.json'] or audit_parent(capsule['parent_run_id'])[3] != snapshot:
                raise RuntimeError('Original parent result or failure changed during review')
            result.update(review_id=capsule['review_id'], parent_run_id=capsule['parent_run_id'],
                          parent_result_completed_at=raw['completed_at'], completed_at=now(),
                          conversion_apparatus_ref=lock['apparatus_ref'], audit_apparatus_ref=capsule['apparatus_ref'],
                          audit_apparatus_provenance=capsule['provenance'], original_common_run_status='failed',
                          common_request=lock['request'], lock_sha256=lock['lock_sha256'],
                          mode='correction-audit-only', insertion_executed=False, production_eligible=False)
            save(run / 'result.json', result)
            state.update(status='complete', acceptance=result['acceptance'], completed_at=now())
            save(run / 'status.json', state)
    except BaseException as error:
        state.update(status='failed', error=str(error), completed_at=now());save(run / 'status.json', state)
        traceback.print_exc();raise


def worker(lock_path, receipt_path=None, inherited_lock=None):
    guard()
    lock = json.loads(Path(lock_path).read_text())
    target = verify_lock(lock)
    if not lock['execution_enabled']:
        raise RuntimeError('Case execution is gated pending its comparison/validation review')
    run = Path(lock_path).parent
    receipt = json.loads(Path(receipt_path).read_text()) if receipt_path else None
    state = {'source': lock['request']['source'], 'version': target.name, 'run_id': lock['run_id'],
             'engine_ref': lock['request']['engine_ref'], 'lock_sha256': lock['lock_sha256'], 'started_at': now(), 'status': 'preflight'}
    save(run / 'status.json', state)
    try:
        with runtime_lock(ROOT, inherited_lock) as held:
            idle()
            runtime(lock)
            capacity(lock)
            if target.is_symlink():
                raise RuntimeError('Source directory must not be a symlink')
            acquire_inputs(lock, run)
            preserved = preserve(target, lock['run_id'], receipt, before_publish=idle)
            state.update(status='preparing', preserved_source=str(preserved) if preserved else None)
            save(run / 'status.json', state)
            try:
                preparation = prepare(lock, target)
                if lock['request']['source'] == 'NCI' and not preparation['preparation_matches_reference']:
                    raise RuntimeError('Regenerated NCIt preparation differs from the reviewed case')
            except BaseException:
                # Partial candidates are evidence. Restore the previous canonical
                # folder only when no candidate was published at that path.
                if preserved and not target.exists():
                    restore(preserved, target, receipt)
                    state['previous_source_restored'] = True
                raise
            save(run / 'preparation.json', preparation)
            state.update(status='converting')
            save(run / 'status.json', state)
            result = convert(lock, target, run, held)
            verify_after(lock, target, result)
            if correction_profile(lock):
                state.update(status='auditing')
                save(run / 'status.json', state)
                review_corrections(lock, target, run, result)
            result.update(common_request=lock['request'], lock_sha256=lock['lock_sha256'],
                          complete_ID_range_verified=True, apparatus_ref=lock['apparatus_ref'],
                          insertion_executed=False, production_eligible=False)
            result['ID_range_verification_scope']={'bound_kind':lock['configuration']['source_atom_ids'].get('bound_kind','reserved-historical-range'),
                                                   'new_production_allocation_performed':False}
            save(run / 'result.json', result)
            state.update(status='complete', acceptance=result['acceptance'], completed_at=now())
            save(run / 'status.json', state)
    except BaseException as error:
        state.update(status='failed', error=str(error), completed_at=now())
        save(run / 'status.json', state)
        traceback.print_exc()
        raise


def launch(lock, previous_receipt=None):
    """Publish immutable control evidence, then detach one guarded dev worker."""
    guard()
    target = verify_lock(lock)
    if (CONTROL / lock['run_id']).exists() or (CONTROL / lock['run_id']).is_symlink():
        raise FileExistsError('Run identity already exists; no overwrite is permitted')
    if not lock['execution_enabled']:
        raise RuntimeError('Case is gated pending validation/comparison review')
    with runtime_lock(ROOT) as held:
        idle()
        runtime(lock)
        if target.exists() and previous_receipt is None:
            raise RuntimeError('Existing source requires an inspect-current receipt')
        capacity(lock)
        CONTROL.mkdir(parents=True, exist_ok=True)
        run = CONTROL / lock['run_id']
        run.mkdir()  # no reuse or overwrite, including failed attempts
        apparatus = run / 'apparatus'
        apparatus.mkdir()
        hashes = {Path(item['repository_path']).name: item['sha256'] for item in lock['provenance']
                  if item['repository_path'].startswith('tools/')}
        for name, encoded in lock['modules_b64'].items():
            if Path(name).name != name or not name.endswith('.py'):
                raise ValueError('Invalid apparatus name')
            raw = base64.b64decode(encoded, validate=True)
            if hashlib.sha256(raw).hexdigest() != hashes.get(name):
                raise ValueError('Apparatus differs from frozen provenance')
            (apparatus / name).write_bytes(raw)
            (apparatus / name).chmod(0o444)
        lock_path = run / 'case.lock.json'
        save(lock_path, lock)
        lock_path.chmod(0o444)
        receipt_path = run / 'previous-source-receipt.json' if previous_receipt is not None else None
        if receipt_path:
            save(receipt_path, previous_receipt)
            receipt_path.chmod(0o444)
        entry = run / 'worker.py'
        entry.write_text('import os,sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,' + repr(str(apparatus)) + ')\n'
                         'from inversion_worker import worker\nwith os.fdopen(' + str(held.fileno()) + ", 'a') as held:\n worker(" +
                         repr(str(lock_path)) + ',' + repr(str(receipt_path) if receipt_path else None) + ',inherited_lock=held)\n')
        entry.chmod(0o444)
        save(run / 'status.json', {'status': 'launching', 'run_id': lock['run_id'], 'lock_sha256': lock['lock_sha256']})
        with (run / 'worker.log').open('xb') as out:
            process = subprocess.Popen([sys.executable, '-B', '-u', str(entry)], stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=subprocess.STDOUT, start_new_session=True,
                                       close_fds=True, pass_fds=(held.fileno(),))
        result = {'run_id': lock['run_id'], 'worker_pid': process.pid, 'run_directory': str(run),
                  'launched_at': now(), 'lock_sha256': lock['lock_sha256']}
        save(run / 'launch.json', result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lock')
    parser.add_argument('--previous-receipt')
    args = parser.parse_args()
    worker(args.lock, args.previous_receipt)
