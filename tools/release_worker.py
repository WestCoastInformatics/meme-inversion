#!/usr/bin/env python3
"""Dev native release execution from a locked manifest; never executes insertion."""
import argparse
import base64
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import traceback
from urllib.parse import urlsplit
import zipfile

import inversion_worker as legacy
import release_manifest as manifests
from release_execution import HANDLERS, relative, verify_locations, verify_plan, verify_profile
from replay_process import available_memory, execute, runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
CONTROL = ROOT / 'qa/replay-requests'


def verify_lock(lock):
    if lock.get('lock_sha256') != manifests.digest({k: v for k, v in lock.items() if k != 'lock_sha256'}):
        raise ValueError('Native release lock content changed')
    if lock.get('artifact_type') != 'ncimeta-native-release-lock' or lock.get('schema_version') != 1:
        raise ValueError('Unsupported native execution lock')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', lock['run_id']):raise ValueError('Invalid run identity')
    manifest, config = lock['manifest'], lock['configuration']
    if manifest['configuration'] != config or lock['manifest_sha256'] != manifests.digest(manifest):
        raise ValueError('Frozen manifest/configuration differs')
    source, version = config['source'], config['version']
    if source not in ('NCI', 'SNOMEDCT_US', 'MTH') or not re.fullmatch(re.escape(source) + r'_[A-Za-z0-9_]+', version):
        raise ValueError('Invalid registered source/version')
    if (lock['request']['source'], lock['request']['version']) != (source, version):raise ValueError('Request identity differs')
    if not re.fullmatch(r'[0-9a-f]{40}', config['engine_ref']) or lock['request']['engine_ref'] != config['engine_ref']:
        raise ValueError('Native source origin requires one immutable matching engine commit')
    if lock['source_profile'] != manifest['profile']:raise ValueError('Source profile identity differs')
    verify_locations(manifest, ROOT / 'sources' / version)
    if lock['production_eligible'] is not False or lock['insertion_executed'] is not False or lock['execution_enabled'] is not True:
        raise ValueError('Native lock cannot authorize insertion or production')
    if config['output_stage']!='inversion-src':raise ValueError('Unsupported native execution stage')
    if manifest['purpose']=='shadow':
        from shadow_execution import budget
        budget(manifest)
    elif (manifest['purpose']!='historical-replay' or config.get('replay',{}).get('reference_stage')!='inversion-src'
          or config.get('replay',{}).get('comparison_profile')!='exact'):
        raise ValueError('Unsupported native execution/acceptance stage')
    if lock['profile_sha256'] != manifests.digest(lock['profile']) or lock['plan_sha256'] != manifests.digest(lock['plan']):
        raise ValueError('Source profile/plan content differs')
    verify_profile(lock['profile'])
    if HANDLERS.get(manifest['profile']) != lock['profile']['handler']:
        raise ValueError('Native source dispatch is unreviewed')
    if lock['plan']['engine_package'] != lock['profile']['engine_package']:raise ValueError('Native code package identity differs')
    bounds = config['source_atom_ids']
    if not bounds or any(type(bounds.get(k)) is not int or bounds[k] <= 0 for k in ('start', 'end')) or bounds['start'] > bounds['end']:
        raise ValueError('Native allocation requires exact positive inclusive integer bounds')
    allocation = manifest['artifacts'][bounds['provenance_ref']]
    if ((allocation['artifact_type'], allocation['source'], allocation['version']) != ('id-allocation', source, version)
            or any(type(allocation['data'].get(k)) is not int for k in ('start', 'end'))
            or any(allocation['data'].get(k) != bounds[k] for k in ('start', 'end', 'bound_kind'))):
        raise ValueError('Native allocation differs from its typed evidence')
    verify_plan(lock['plan'], manifest, lock['code_files'])
    adapter = importlib.import_module(lock['profile']['handler'])
    builder = getattr(adapter, 'rebuild_plan', adapter.build_plan)
    if builder(config, manifest['artifacts'], lock['code_files']) != lock['plan']:
        raise ValueError('Frozen native plan differs from the source-owned deterministic planner')
    artifacts = manifest['artifacts']
    if any(v['provenance']['evidence_kind'] == 'synthetic-fixture' for v in artifacts.values()):
        raise ValueError('Synthetic inputs cannot authorize native execution')
    if manifest['purpose']=='historical-replay':
        reference = artifacts[config['replay']['reference_ref']]
        if (reference['artifact_type'], reference['source'], reference['version'], reference['data'].get('reference_stage')) != ('reference-inversion', source, version, 'inversion-src'):
            raise ValueError('Official oracle is not current-release inversion output')
        if (len(reference['files']) != len(lock['plan']['output_files'])
                or {f['role'] for f in reference['files']} != set(lock['plan']['output_files'])):raise ValueError('Official reference coverage differs')
    hashes = {v['repository_path']: v['sha256'] for v in lock['provenance']}
    registry_raw = base64.b64decode(lock['profiles_registry_b64'], validate=True)
    if (manifests.hashlib.sha256(registry_raw).hexdigest() != hashes.get('docs/inversion-review/native-execution-profiles.json')
            or json.loads(registry_raw)['profiles'].get(manifest['profile']) != lock['profile']):
        raise ValueError('Selected native profile differs from its committed registry payload')
    for name, encoded in lock['modules_b64'].items():
        if Path(name).name != name or not name.endswith('.py'):raise ValueError('Unsafe apparatus name')
        if manifests.hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest() != hashes.get('tools/' + name):
            raise ValueError('Frozen module payload differs')
    for group in ('code_files', 'runtime_files'):
        names = set()
        for item in lock[group]:
            relative(item['relative_path'])
            if item['relative_path'] in names:raise ValueError('Duplicate code/runtime file')
            names.add(item['relative_path'])
            if item['kind'] == 'file':
                raw = base64.b64decode(item['data_b64'], validate=True)
                if len(raw) != item['bytes'] or manifests.hashlib.sha256(raw).hexdigest() != item['sha256']:
                    raise ValueError('Frozen Git code payload differs')
    identity = [{k: v for k, v in row.items() if k != 'data_b64'} for row in lock['code_files']]
    if manifests.digest(identity) not in lock['profile']['reviewed_package_sha256']:
        raise ValueError('Native package does not match reviewed capability')
    if len(lock['runtime_files']) != 169 or lock['runtime_ref'] != lock['profile']['runtime_ref']:
        raise ValueError('Complete pinned runtime is required')
    runtime_identity = [{k: v for k, v in row.items() if k != 'data_b64'} for row in lock['runtime_files']]
    if any(row['kind'] != 'file' or row['repository_path'] != row['relative_path']
           or not row['repository_path'].startswith(('INV/', 'ENV/')) for row in lock['runtime_files']):
        raise ValueError('Runtime entries must remain inside the reviewed INV/ENV package')
    if manifests.digest(runtime_identity) != lock['profile']['runtime_inventory_sha256']:
        raise ValueError('Runtime inventory differs from the reviewed native profile')
    return ROOT / 'sources' / version


def activate_runtime(lock):
    verify_lock(lock)
    return legacy.activate_verified_runtime(lock)


def inspect_current(lock):
    legacy.guard();target = verify_lock(lock)
    with runtime_lock(ROOT):
        legacy.idle()
        if target.is_symlink():raise ValueError('Canonical source path is linked')
        receipt = {'source': lock['request']['source'], 'version': target.name,
                   'exists': target.exists(), 'inspected_at': legacy.now()}
        if target.exists():receipt.update(root_mode=oct(stat.S_IMODE(target.stat().st_mode)), manifest=legacy.manifest(target))
        else:receipt.update(root_mode=None, manifest=[])
        receipt['receipt_sha256'] = manifests.digest(receipt)
        return receipt


def retention_status(lock):
    legacy.guard();target = verify_lock(lock)
    import replay_retention
    with runtime_lock(ROOT):return replay_retention.inventory(ROOT, target.name, source=lock['request']['source'])


def verify_previous(lock, target, receipt):
    if receipt is None:
        if target.exists() or target.is_symlink():raise ValueError('Existing canonical source requires an inspection receipt')
        return
    if (receipt.get('receipt_sha256') != manifests.digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'})
            or (receipt.get('source'), receipt.get('version')) != (lock['request']['source'], target.name)
            or receipt.get('exists') is not target.exists() or target.is_symlink()):
        raise ValueError('Canonical source state differs from the inspection receipt')
    if target.exists() and (receipt.get('root_mode') != oct(stat.S_IMODE(target.stat().st_mode)) or receipt.get('manifest') != legacy.manifest(target)):
        raise ValueError('Canonical source contents changed after inspection')


def capacity(lock):
    if lock['manifest']['purpose']=='shadow':
        from shadow_execution import budget
        resources=budget(lock['manifest']);output_bytes=resources['output_bytes'];scratch_bytes=resources['scratch_bytes']
    else:
        output_bytes = sum(f['bytes'] for f in lock['manifest']['artifacts'][lock['configuration']['replay']['reference_ref']]['files'])
        scratch_bytes=output_bytes
    target = ROOT / 'sources' / lock['request']['version']
    missing = {}
    for artifact in lock['manifest']['artifacts'].values():
        for file in artifact['files']:
            path = _local(file)
            if not path.exists():
                size = file.get('archive_bytes', file['bytes'])
                if str(path) in missing and missing[str(path)] != size:raise ValueError('Conflicting cache acquisition sizes')
                missing[str(path)] = size
    materialized_bytes = 0
    for item in lock['plan']['input_files']:
        file = _descriptor(lock, item);destination = _input_path(item, target)
        if item.get('scope', 'candidate') == 'candidate' or (not destination.exists() and destination != _local(file)):
            materialized_bytes += file['bytes']
    download_bytes = sum(missing.values())
    needed = download_bytes + max(lock['profile']['minimum_free_disk_gib'] * 1024 ** 3,
                                  12 * 1024 ** 3 + output_bytes + scratch_bytes + materialized_bytes)
    free = shutil.disk_usage(ROOT).free
    if free < needed or available_memory() < 24 * 1024 ** 3:
        raise RuntimeError('Native release capacity reserve unavailable: need ' + str(needed) + ' free bytes')
    return {'required_free_bytes': needed, 'observed_free_bytes': free, 'missing_download_bytes': download_bytes,
            'additional_materialization_bytes': materialized_bytes, 'per_stage_reserve_gib': 12}


def _descriptor(lock, item):
    return next(f for f in lock['manifest']['artifacts'][item['artifact']]['files'] if f['role'] == item['role'])


def _local(file):
    path = manifests.location(file, False)
    if path is None:raise ValueError('Remote descriptor must be acquired and bound to its standard local cache before native resolution')
    if not path.is_relative_to(ROOT.parent):raise ValueError('Native input is outside mirrored MEME storage')
    return path


def acquire_preserved_object(artifact, file, path, run):
    """Download one explicitly pinned prepared RRF at its original standard path."""
    if artifact['artifact_type'] not in ('prepared-bundle', 'publisher-history') or artifact['source'] != 'MTH':
        raise ValueError('Individual object acquisition is limited to declared preserved MTH inputs')
    if not re.fullmatch(r'MTH_[0-9]{4}[A-Z]{2}', artifact['version']):raise ValueError('Invalid prepared UMLS release identity')
    prefix = ROOT.parent / 'mr/umls' / artifact['version'].removeprefix('MTH_')
    relative_path = path.relative_to(prefix)
    if (len(relative_path.parts) != 3 or not re.fullmatch(r'subset[1-9][0-9]*', relative_path.parts[0])
            or relative_path.parts[1] != 'METASUBSET' or relative_path.name != file['role']
            or not re.fullmatch(r'MR[A-Z]+\.RRF', file['role'])):
        raise ValueError('Prepared object must retain its standard subset/METASUBSET role path')
    selection = artifact['data'].get('acquisition', {})
    record = selection.get('objects', {}).get(file['role'])
    key = str(path.relative_to(ROOT.parent))
    if selection.get('bucket') != 'nci-evs-meme' or not record or record.get('key') != key:
        raise ValueError('Missing exact prepared-object S3 selection: ' + file['role'])
    identity = record.get('object_identity', {})
    fields = ('ContentLength', 'ETag', 'LastModified', 'VersionId')
    if (set(identity) != set(fields) or type(identity['ContentLength']) is not int
            or identity['ContentLength'] != file['bytes'] or not identity['ETag']):
        raise ValueError('Prepared object requires complete pinned size/ETag/time/version identity')
    _safe_parent(path)
    if path.exists() or path.is_symlink():raise FileExistsError('Prepared object appeared before acquisition')
    if list(path.parent.glob('.' + path.name + '.download-*')):
        raise RuntimeError('A prepared-input partial already exists; inspect/reconcile it before another download')
    if shutil.disk_usage(path.parent).free < file['bytes'] + 12 * 1024 ** 3:
        raise RuntimeError('Insufficient prepared-object acquisition reserve')
    environment = dict(os.environ, AWS_PROFILE='meme', AWS_PAGER='', AWS_CLI_AUTO_PROMPT='off')
    def aws(arguments):
        result = subprocess.run(['/usr/bin/aws', 's3api', *arguments], capture_output=True, text=True, env=environment, timeout=1800)
        if result.returncode:raise RuntimeError('Read-only prepared-object acquisition failed: ' + result.stderr[-2000:])
        return json.loads(result.stdout)
    head = ['head-object', '--bucket', 'nci-evs-meme', '--key', key]
    if identity['VersionId'] is not None:head += ['--version-id', identity['VersionId']]
    observed = aws(head + ['--output', 'json'])
    if {name: observed.get(name) for name in fields} != identity:raise RuntimeError('Prepared object changed before acquisition')
    legacy.save(run / 'progress.json', {'stage': 'acquiring-prepared-input', 'role': file['role'], 'key': key})
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.download-', dir=str(path.parent))
    os.close(descriptor);partial = Path(temporary)
    receipt_path = run / ('acquisition-' + artifact['version'] + '-' + file['role'] + '.json')
    legacy.save(receipt_path, {'status': 'downloading', 'key': key, 'partial': str(partial), 'target': str(path)})
    get = ['get-object', '--bucket', 'nci-evs-meme', '--key', key, '--if-match', identity['ETag']]
    if identity['VersionId'] is not None:get += ['--version-id', identity['VersionId']]
    aws(get + [str(partial)])
    observed_after = aws(head + ['--output', 'json'])
    if {name: observed_after.get(name) for name in fields} != identity:
        raise RuntimeError('Prepared object changed during acquisition; partial retained')
    legacy.require_file(partial, file['sha256'])
    if partial.stat().st_size != file['bytes']:raise RuntimeError('Prepared object size differs; partial retained')
    partial.chmod(0o444)
    from prepare_snomed_candidate import publish
    publish(partial, path)
    receipt = {'status': 'frozen', 'key': key, 'path': str(path), 'object_identity': identity,
               'sha256': file['sha256'], 'bytes': file['bytes'], 'aws_profile': 'meme', 'new_archive_created': False}
    legacy.save(receipt_path, receipt)
    return receipt


def acquire_and_verify(lock, run):
    """Acquire missing official caches only; never restore completed source trees."""
    artifacts = lock['manifest']['artifacts'];downloads = []
    for artifact in artifacts.values():
        for file in artifact['files']:
            path = _local(file)
            if path.exists():continue
            if artifact['artifact_type'] in ('prepared-bundle', 'publisher-history') and artifact['source'] == 'MTH' and 'archive_member' not in file:
                downloads.append(acquire_preserved_object(artifact, file, path, run));continue
            # Only the existing standard archive helper can perform acquisition.
            if path.parent != ROOT / 'sources' or path.suffix != '.tgz' or 'archive_member' not in file:
                raise RuntimeError('Required preserved input missing: ' + str(path))
            version = path.name.removesuffix('.tgz')
            source = next((v for v in ('NCI', 'SNOMEDCT_US', 'MTH', 'MDR', 'RADLEX') if version.startswith(v + '_')), None)
            if source is None:raise ValueError('Unregistered archive namespace')
            import acquire_inversion_reference
            legacy.save(run / 'progress.json', {'stage': 'acquiring-official-archive', 'version': version})
            receipt = acquire_inversion_reference.acquire({'source': source, 'version': version,
                'engine_ref': lock['request']['engine_ref'], 'expected_code': [],
                'pull_helper_sha256': lock['profile']['pull_helper_sha256']})
            downloads.append(receipt)
    issues = [];rows = manifests.verify_files(artifacts, True, issues)
    if issues or any(row['status'] != 'VERIFIED' for row in rows):
        legacy.save(run / 'input-verification-failed.json', {'files': rows, 'issues': issues})
        raise RuntimeError('Declared native inputs or official references failed byte verification')
    receipt = {'files': rows, 'downloads': downloads, 'source_folder_restored': False, 'official_outputs_seeded': False}
    legacy.save(run / 'acquisition.json', receipt)
    return rows


def _safe_parent(path):
    if path.parent.resolve() != path.parent:raise ValueError('Linked input destination ancestor')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve() != path.parent:raise ValueError('Linked input destination ancestor')


def _input_path(item, candidate):
    root = {'candidate': candidate, 'inv': ROOT, 'meme': ROOT.parent}[item.get('scope', 'candidate')]
    return root / relative(item['destination'])


def materialize(lock, candidate):
    """Stream only declared input members; no official output or executable copying."""
    groups = {};result = []
    for item in lock['plan']['input_files']:
        file = _descriptor(lock, item);destination = _input_path(item, candidate)
        if destination.is_symlink():raise ValueError('Input destination is linked')
        _safe_parent(destination)
        if destination.exists():
            legacy.require_file(destination, file['sha256'])
            if destination.stat().st_size != file['bytes']:raise ValueError('Existing native input size differs')
            result.append({'destination': str(destination), 'reused': True, 'sha256': file['sha256']});continue
        key = (str(_local(file)), file.get('archive_format'))
        groups.setdefault(key, []).append((file, destination))
    for (source, archive_format), selections in groups.items():
        def copy_stream(incoming, file, destination):
            with destination.open('xb') as outgoing:
                for block in iter(lambda: incoming.read(4 * 1024 ** 2), b''):
                    if shutil.disk_usage(destination.parent).free < 12 * 1024 ** 3 + len(block):
                        raise RuntimeError('Native input materialization stopped at the 12 GiB disk reserve')
                    outgoing.write(block)
            legacy.require_file(destination, file['sha256'])
            if destination.stat().st_size != file['bytes']:raise ValueError('Materialized native input size differs')
            destination.chmod(0o444)
            result.append({'destination': str(destination), 'reused': False, 'sha256': file['sha256']})
        if archive_format is None:
            for file, destination in selections:
                with manifests._open(Path(source)) as incoming:copy_stream(incoming, file, destination)
        elif archive_format == 'tar.gz':
            wanted = {}
            for file, destination in selections:wanted.setdefault(file['archive_member'], []).append((file, destination))
            with tarfile.open(source, 'r|gz') as archive:
                for member in archive:
                    name = member.name.removeprefix('./').rstrip('/')
                    selections = wanted.pop(name, [])
                    first = None
                    for file, destination in selections:
                        if not member.isfile():raise ValueError('Selected native input is not regular')
                        if first is None:
                            with archive.extractfile(member) as incoming:copy_stream(incoming, file, destination)
                            first = destination
                        else:
                            with manifests._open(first) as incoming:copy_stream(incoming, file, destination)
            if wanted:raise ValueError('Native input members disappeared')
        elif archive_format == 'zip':
            with zipfile.ZipFile(source) as archive:
                for file, destination in selections:
                    with archive.open(file['archive_member']) as incoming:copy_stream(incoming, file, destination)
        else:raise ValueError('Unsupported native container')
    return result


def _write_records(records, candidate):
    for item in records:
        destination = candidate / relative(item['relative_path'])
        _safe_parent(destination)
        if item.get('kind') == 'symlink':continue
        raw = base64.b64decode(item['data_b64'], validate=True)
        with destination.open('xb') as out:out.write(raw)
        destination.chmod(int(item['mode'], 8) & ~0o222)


def _links(records, candidate):
    for item in records:
        path = candidate / relative(item['relative_path']);_safe_parent(path)
        resolved = (path.parent / item['target']).resolve()
        if not resolved.is_relative_to(ROOT.parent):raise ValueError('Source link escapes mirrored MEME storage')
        path.symlink_to(item['target'])


def prepare(lock, target, run):
    stage = Path(tempfile.mkdtemp(prefix='.' + target.name + '.native-', dir=str(target.parent)))
    # Keep failed staging evidence under the run; do not recursively discard it.
    legacy.save(run / 'staging.json', {'path': str(stage)})
    code = [v for v in lock['code_files'] if v['relative_path'] not in lock['plan'].get('code_excludes', [])]
    _write_records(code, stage)
    materialized = materialize(lock, stage)
    _write_records(lock['plan']['generated_files'], stage)
    _links([v for v in code if v.get('kind') == 'symlink'] + lock['plan']['symlinks'], stage)
    for name in ('orig', 'src', 'tmp', 'etc', 'bin', 'etc/qa'):
        (stage / name).mkdir(parents=True, exist_ok=True)
    adapter = importlib.import_module(lock['profile']['handler'])
    checked = adapter.validate_inputs(lock['plan'], stage)
    legacy.save(run / 'physical-input-validation.json', checked)
    if not checked['passed']:raise RuntimeError('Physical native input validation failed')
    if target.exists() or target.is_symlink():raise FileExistsError('Canonical candidate destination is occupied')
    from prepare_snomed_candidate import publish
    publish(stage, target)
    return {'published': str(target), 'materialized': materialized, 'physical_validation': checked,
            'code_from_git': True, 'completed_outputs_restored': False}


def verify_candidate_inputs(lock, target):
    for item in lock['plan']['input_files']:
        file = _descriptor(lock, item);legacy.require_file(_input_path(item, target), file['sha256'])
    for item in lock['plan']['generated_files']:
        legacy.require_file(target / item['relative_path'], item['sha256'])
    for item in lock['code_files']:
        if item['relative_path'] in lock['plan'].get('code_excludes', []):continue
        path = target / item['relative_path']
        if item['kind'] == 'file':legacy.require_file(path, item['sha256'])
        elif not path.is_symlink() or os.readlink(path) != item['target']:raise RuntimeError('Git code link changed')
    for item in lock['plan']['symlinks']:
        path=target/relative(item['relative_path'])
        if not path.is_symlink() or os.readlink(path)!=item['target']:raise RuntimeError('Frozen native plan link changed')


def convert(lock, target, run):
    metrics = []
    substitutions = {'{python}': sys.executable, '{target}': str(target), '{run}': str(run)}
    environment = dict(os.environ, LANG='C', LC_ALL='C', LC_COLLATE='C', _POSIX2_VERSION='1', PATH_TO_PERL='/usr/bin/perl')
    for stage in lock['plan']['stages']:
        argv = [substitutions.get(word, word) for word in stage['argv']]
        # Also support tokens embedded in one path, never shell interpolation.
        for key, value in substitutions.items():argv = [word.replace(key, value) for word in argv]
        legacy.save(run / 'progress.json', {'stage': stage['name']})
        stdout = target / stage['stdout'] if 'stdout' in stage else run / (stage['name'] + '.stdout.log')
        stdout.parent.mkdir(parents=True, exist_ok=True)
        value = execute(argv, cwd=target / stage['cwd'], stdout=stdout,
            stderr=run / (stage['name'] + '.stderr.log'), env=environment, namespace_user='current',
            progress=lambda values: legacy.save(run / 'progress.json', {'stage': stage['name'], **values}))
        metrics.append({'stage': stage['name'], **value})
    return metrics


def compare(lock, target):
    if lock['manifest']['purpose']=='shadow':
        from shadow_execution import assess
        return assess(lock,target)
    reference = lock['manifest']['artifacts'][lock['configuration']['replay']['reference_ref']]
    files = {}
    for item in reference['files']:
        path = target / relative(item['role'])
        if not path.is_file() or path.is_symlink():raise RuntimeError('Missing native output: ' + str(path))
        actual = {'sha256': legacy.sha(path), 'bytes': path.stat().st_size}
        expected = {key: item[key] for key in ('sha256', 'bytes')}
        files[item['role']] = {'candidate': actual, 'reference': expected, 'exact_match': actual == expected}
    validation = importlib.import_module(lock['profile']['handler']).validate_outputs(lock['plan'], target)
    passed = validation['passed'] and all(v['exact_match'] for v in files.values())
    return {'files': files, 'validation': validation,
            'acceptance': {'status': 'PASS_EXACT' if passed else 'DIFFERENCES_REQUIRE_REVIEW',
                           'production_eligible': False, 'historical_correction_waivers_applied': False}}


def verify_retained(lock):
    """Read-only fresh-process scan, independent of the original result flags."""
    legacy.guard();target = verify_lock(lock)
    with runtime_lock(ROOT):
        legacy.idle();legacy.runtime(lock);verify_candidate_inputs(lock, target)
        run = CONTROL / lock['run_id']
        state = manifests.load(run / 'status.json');original = manifests.load(run / 'result.json')
        if state['status'] != 'complete' or original['lock_sha256'] != lock['lock_sha256']:
            raise ValueError('Original native execution did not finish under this lock')
        issues = [];rows = manifests.verify_files(lock['manifest']['artifacts'], True, issues)
        current = json.loads(json.dumps(compare(lock, target), allow_nan=False))
        shadow=lock['manifest']['purpose']=='shadow'
        expected_status='SHADOW_VALIDATED_COMPARISON_PENDING' if shadow else 'PASS_EXACT'
        if (issues or any(row['status'] != 'VERIFIED' for row in rows)
                or original['comparison'] != {k: v for k, v in current.items() if k != 'acceptance'}
                or original['acceptance'] != current['acceptance'] or current['acceptance']['status'] != expected_status):
            raise ValueError('Independent native retained-file verification failed')
        return {'status': 'PASS_SHADOW_RETAINED_VERIFICATION' if shadow else 'PASS_NATIVE_RELEASE_VERIFICATION', 'run_id': lock['run_id'],
                'source': lock['request']['source'], 'version': target.name, 'lock_sha256': lock['lock_sha256'],
                'acceptance': expected_status, 'comparison_complete':not shadow, 'result_sha256': legacy.sha(run / 'result.json'),
                'files': {name: row['candidate'] for name, row in current['files'].items()},
                'inputs_verified': len(rows), 'runtime_files_verified': 169,
                'physical_output_validation': current['validation'],
                'native_inversion_repeated': False, 'source_data_changed': False, 'production_eligible': False}


def worker(lock_path, receipt_path=None, inherited_lock=None):
    legacy.guard();lock = manifests.load(lock_path);target = verify_lock(lock);run = Path(lock_path).parent
    receipt = manifests.load(receipt_path) if receipt_path else None
    state = {'status': 'preflight', 'source': lock['request']['source'], 'version': target.name,'purpose':lock['manifest']['purpose'],
             'run_id': lock['run_id'], 'lock_sha256': lock['lock_sha256'], 'started_at': legacy.now()}
    legacy.save(run / 'status.json', state)
    try:
        with runtime_lock(ROOT, inherited_lock):
            legacy.idle();legacy.runtime(lock);capacity(lock)
            import replay_retention
            state['retention_policy'] = replay_retention.inventory(ROOT, target.name, source=lock['request']['source'])
            if target.exists() and not state['retention_policy']['admission_available']:raise RuntimeError('Existing managed rollback requires review before replacement')
            rows = acquire_and_verify(lock, run)
            capacity(lock)
            # A nonexistent current folder has an explicit inspect receipt, but preserve expects None.
            verify_previous(lock, target, receipt)
            previous = receipt if target.exists() else None
            preserved = legacy.preserve(target, lock['run_id'], previous, before_publish=legacy.idle)
            state.update(status='preparing', preserved_source=str(preserved) if preserved else None)
            legacy.save(run / 'status.json', state)
            try:prepared = prepare(lock, target, run)
            except BaseException:
                if preserved and not target.exists():legacy.restore(preserved, target, receipt);state['previous_source_restored'] = True
                raise
            legacy.save(run / 'preparation.json', prepared)
            legacy.save(run / 'native-plan.json', lock['plan'])
            state['status'] = 'converting';legacy.save(run / 'status.json', state)
            stages = convert(lock, target, run)
            comparison = compare(lock, target)
            result = {'comparison': {k: v for k, v in comparison.items() if k != 'acceptance'},
                      'acceptance': comparison['acceptance']}
            verify_candidate_inputs(lock, target);legacy.runtime(lock)
            # Pin source archives/files again by inode/change-time; no second full archive scan.
            for row in rows:
                if list(manifests._stamp(Path(row['local_path']).lstat())) != row['snapshot']:
                    raise RuntimeError('Input/reference changed during native execution')
            result.update(source=lock['request']['source'], version=target.name, run_id=lock['run_id'],
                lock_sha256=lock['lock_sha256'], apparatus_ref=lock['apparatus_ref'], stages=stages,
                insertion_executed=False, production_eligible=False, declared_inputs_unchanged=True)
            legacy.save(run / 'result.json', result)
            state.update(status='complete', acceptance=result['acceptance'], completed_at=legacy.now())
            legacy.save(run / 'status.json', state)
    except BaseException as error:
        state.update(status='failed', error=str(error), completed_at=legacy.now());legacy.save(run / 'status.json', state)
        traceback.print_exc();raise


def launch(lock, previous_receipt=None):
    legacy.guard();target = verify_lock(lock)
    with runtime_lock(ROOT) as held:
        legacy.idle();legacy.runtime(lock);capacity(lock)
        verify_previous(lock, target, previous_receipt)
        import replay_retention
        budget = replay_retention.inventory(ROOT, target.name, source=lock['request']['source'])
        if target.exists() and not budget['admission_available']:raise ValueError('Retention admission is unavailable')
        CONTROL.mkdir(parents=True, exist_ok=True);run = CONTROL / lock['run_id'];run.mkdir()
        apparatus = run / 'apparatus';apparatus.mkdir()
        for name, encoded in lock['modules_b64'].items():
            path = apparatus / name;path.write_bytes(base64.b64decode(encoded, validate=True));path.chmod(0o444)
        lock_path = run / 'case.lock.json';legacy.save(lock_path, lock);lock_path.chmod(0o444)
        receipt_path = run / 'previous-source-receipt.json' if previous_receipt is not None else None
        if receipt_path:legacy.save(receipt_path, previous_receipt);receipt_path.chmod(0o444)
        entry = run / 'worker.py'
        entry.write_text('import os,sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,' + repr(str(apparatus)) + ')\nfrom release_worker import worker\nwith os.fdopen(' + str(held.fileno()) + ", 'a') as held:\n worker(" + repr(str(lock_path)) + ',' + repr(str(receipt_path) if receipt_path else None) + ',inherited_lock=held)\n')
        entry.chmod(0o444)
        legacy.save(run / 'status.json', {'status': 'launching', 'run_id': lock['run_id'], 'version': target.name})
        with (run / 'worker.log').open('xb') as outgoing:
            process = subprocess.Popen([sys.executable, '-B', '-u', str(entry)], stdin=subprocess.DEVNULL,
                stdout=outgoing, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True, pass_fds=(held.fileno(),))
        result = {'run_id': lock['run_id'], 'worker_pid': process.pid, 'run_directory': str(run),
                  'lock_sha256': lock['lock_sha256'], 'launched_at': legacy.now()}
        legacy.save(run / 'launch.json', result);return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('lock');parser.add_argument('--previous-receipt')
    args = parser.parse_args();worker(args.lock, args.previous_receipt)
