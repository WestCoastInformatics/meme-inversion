#!/usr/bin/env python3
"""Bound dev rollback retention and compact only archive-recoverable duplicates."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

import archive_retained_source as storage
from replay_process import runtime_lock

ROOT = storage.ROOT
POLICY = 'dev-replay-retention-v1'
MAX_EXPANDED_ROLLBACKS = 1
VERSIONS = {'NCI': 'NCI_2026_10D', 'SNOMEDCT_US': 'SNOMEDCT_US_2026_09_01',
            'MTH': 'MTH_2026AA', 'MDR': 'MDR_29_1', 'RADLEX': 'RADLEX_4_3'}
VERDICTS = {'PASS_EXACT', 'PASS_EQUIVALENT', 'PASS_REVIEWED_CORRECTIONS'}
VERIFICATIONS = {'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION',
                 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION_WITH_FINALIZATION_REVIEW',
                 'PASS_RETAINED_COMMON_MATRIX_VERIFICATION'}


def digest(value):
    return hashlib.sha256(storage.canonical(value)).hexdigest()


def _run(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', value):
        raise ValueError('Invalid common run identity')
    return value


def _record(path):
    path = Path(path)
    storage._safe_directory(path.parent)
    value = storage._load(path)
    pin = {'path': str(path), 'sha256': storage._file_sha(path)}
    if storage._load(path) != value:
        raise RuntimeError('Evidence changed while reading: ' + str(path))
    return value, pin


def _namespace(source, create=False):
    parent = ROOT / 'qa/replay-retention'
    if create:
        parent.mkdir(exist_ok=True)
        storage._sync_dir(parent.parent)
    storage._safe_directory(parent)
    namespace = parent / source.name
    if create:
        namespace.mkdir(exist_ok=True)
        storage._sync_dir(parent)
    storage._safe_directory(namespace)
    return namespace


def _held(source):
    hold = ROOT / 'qa/replay-retention/holds' / (source.name + '.json')
    if hold.exists() or hold.is_symlink():
        raise RuntimeError('Retention hold requires investigation: ' + str(hold))


def _shape(source):
    """Fast metadata inventory for admission, never authority for deletion."""
    result = {}
    for base, directories, files in os.walk(source, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            result[str(path.relative_to(source))] = storage._stamp(path.lstat())
    result['.'] = storage._stamp(source.lstat())
    return result


def inventory(root, version):
    if version not in VERSIONS.values():
        raise ValueError('Unreviewed source/version retention policy')
    expanded, compacted = [], []
    for source in sorted((root / 'sources').glob(version + '.before-*')):
        if source.is_symlink() or not source.is_dir():
            raise RuntimeError('Unexpected rollback path: ' + str(source))
        namespace = root / 'qa/replay-retention' / source.name
        complete = namespace / 'complete.json'
        hold = root / 'qa/replay-retention/holds' / (source.name + '.json')
        try:
            storage._safe_directory(namespace)
            state = storage._load(complete)
            plan_path = namespace / 'plan.json'
            valid = (state['status'] == 'COMPACTED' and state['policy'] == POLICY
                     and state['source'] == str(source)
                     and storage._file_sha(plan_path) == state['plan_sha256']
                     and state['remaining_capture'] == _shape(source)
                     and not (hold.exists() or hold.is_symlink()))
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        (compacted if valid else expanded).append(str(source))
    return {'policy': POLICY, 'maximum_expanded_rollbacks': MAX_EXPANDED_ROLLBACKS,
            'expanded_rollbacks': expanded, 'compacted_runs': compacted,
            'admission_available': len(expanded) < MAX_EXPANDED_ROLLBACKS}


def check_budget(root, version):
    result = inventory(root, version)
    if not result['admission_available']:
        raise RuntimeError('Retention limit: compact/review the existing rollback before another replay; '
                           'no automatic archive or deletion: ' + ', '.join(result['expanded_rollbacks']))
    return result


def status(version):
    storage.guard()
    with runtime_lock(ROOT):
        return inventory(ROOT, version)


def _no_live_dependencies(source, lock):
    def visit(value):
        if isinstance(value, dict):
            for item in value.values():visit(item)
        elif isinstance(value, list):
            for item in value:visit(item)
        elif isinstance(value, str) and (value == str(source) or value.startswith(str(source) + '/')):
            raise RuntimeError('Preserved tree is still a declared execution dependency')
    visit(lock['case'])
    for release in (ROOT / 'sources').iterdir():
        if release == source:
            continue
        if release.is_symlink():
            links = [release]
        elif release.is_dir():
            links = [Path(base) / name for base, dirs, files in os.walk(release, followlinks=False)
                     for name in dirs + files if (Path(base) / name).is_symlink()]
        else:
            continue
        for link in links:
            if link.resolve().is_relative_to(source):
                raise RuntimeError('A source dependency links into the preserved tree: ' + str(link))


def _preservation_context(run_id):
    """Storage preservation is independent of semantic acceptance of a test."""
    _run(run_id)
    control = ROOT / 'qa/replay-requests' / run_id
    lock, lock_pin = _record(control / 'case.lock.json')
    if (lock.get('artifact_type') != 'ncimeta-dev-replay-lock' or lock.get('run_id') != run_id
            or lock.get('lock_sha256') != digest({k: v for k, v in lock.items() if k != 'lock_sha256'})):
        raise ValueError('Common run lock changed')
    source_id, version = lock['request']['source'], lock['request']['version']
    if VERSIONS.get(source_id) != version:
        raise ValueError('Unreviewed source/version')
    source = storage._source(ROOT / 'sources' / (version + '.before-' + run_id))
    _held(source)
    _no_live_dependencies(source, lock)
    state, state_pin = _record(control / 'status.json')
    if state.get('status') not in ('complete', 'failed'):
        raise ValueError('An active/unresolved operation cannot authorize cleanup')
    previous, previous_pin = _record(control / 'previous-source-receipt.json')
    if (previous.get('version') != version or previous.get('source') != source_id
            or previous.get('receipt_sha256') != digest({k: v for k, v in previous.items() if k != 'receipt_sha256'})
            or state.get('preserved_source') != str(source)):
        raise ValueError('Preserved tree is not the declared predecessor')
    archive_path = ROOT / 'sources' / (version + '.tgz')
    archives = [item for item in lock['case']['acquisition']['archives'] if item['archive_path'] == str(archive_path)]
    if len(archives) != 1:
        raise ValueError('No unique pinned current-version official archive')
    for active in (source / 'replay-active-run.json', source / 'etc/replay-active-run.json'):
        if active.exists() and storage._load(active).get('status') not in ('complete', 'failed'):
            raise RuntimeError('Preserved attempt is still active')
    return source, previous, archives[0], [lock_pin, state_pin, previous_pin], lock, state, control


def _verified_context(run_id, verification, verification_sha256):
    """Optionally bind acceptance too, without relabeling failed attempts."""
    source, previous, archive, pins, lock, state, control = _preservation_context(run_id)
    source_id, version = lock['request']['source'], lock['request']['version']
    scan, scan_pin = _record(verification)
    if scan_pin['sha256'] != verification_sha256 or scan.get('status') not in VERIFICATIONS:
        raise ValueError('Pinned independent verification is absent or unsuccessful')
    rows = scan.get('runs', scan.get('cases', [scan]))
    matches = [row for row in rows if row.get('run_id') == run_id]
    if len(matches) != 1:
        raise ValueError('Independent verification does not identify one accepted run')
    row = matches[0]
    if row.get('lock_sha256') != lock['lock_sha256']:
        raise ValueError('Independent verification belongs to another lock')
    result_control = control
    if state.get('status') != 'complete':
        # Explicitly support the recorded generated-MTH finalization review.
        review_id = _run(row.get('finalization_review_id'))
        if (source_id != 'MTH' or state.get('status') != 'failed'
                or row.get('original_common_run_status') != 'failed'
                or scan['status'] != 'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION_WITH_FINALIZATION_REVIEW'):
            raise ValueError('Failed/unresolved runs cannot authorize retention cleanup')
        result_control = ROOT / 'qa/replay-requests' / review_id
    result, result_pin = _record(result_control / 'result.json')
    if 'result_sha256' in row and row['result_sha256'] != result_pin['sha256']:
        raise ValueError('Independent verification belongs to another result')
    acceptance = result.get('acceptance', {})
    verdict = acceptance.get('status')
    scan_verdict = row.get('acceptance') if row is scan else row.get('acceptance', row.get('status'))
    if (result.get('run_id') != run_id or result.get('lock_sha256') != lock['lock_sha256']
            or verdict not in VERDICTS or scan_verdict not in (None, verdict)):
        raise ValueError('Run has no matching accepted comparison result')
    if result_control != control:
        review_state, review_pin = _record(result_control / 'status.json')
        if (review_state.get('status') != 'complete' or result.get('review_id') != result_control.name
                or result.get('parent_run_id') != run_id or result.get('native_conversion_repeated') is not False):
            raise ValueError('Separate finalization review is incomplete or mismatched')
    else:
        review_pin = None
    files = result['comparison']['files']
    expected = row.get('outputs_verified', row.get('files'))
    if len(files) != (23 if source_id == 'MTH' else 5) or set(files) != set(expected):
        raise ValueError('Independent output inventory differs')
    for name, record in files.items():
        storage._relative(name)
        if Path(name).name != name:
            raise ValueError('Unexpected output name')
        checksum = record['candidate']['sha256']
        independently_verified = expected[name] if isinstance(expected[name], str) else expected[name]['sha256']
        if checksum != independently_verified or storage._file_sha(ROOT / 'sources' / version / 'src' / name) != checksum:
            raise RuntimeError('Accepted output changed since independent verification: ' + name)
    if verdict == 'PASS_REVIEWED_CORRECTIONS':
        if (acceptance.get('native_derived_correction_audit_passed') is not True
                or acceptance.get('raw_comparison_preserved') is not True):
            raise ValueError('Mandatory correction audit is absent')
        raw, raw_pin = _record(result_control / 'raw-result.json')
        audit, audit_pin = _record(result_control / 'correction-audit.json')
        if (raw_pin['sha256'] != result['raw_result_sha256'] or audit != result['correction_audit']
                or raw['comparison'] != result['comparison']):
            raise ValueError('Correction acceptance lost its raw/audit binding')
    else:
        raw_pin = audit_pin = None
    pins += [scan_pin, result_pin, review_pin, raw_pin, audit_pin]
    return source, previous, archive, [item for item in pins if item]


def _context(run_id, verification=None, verification_sha256=None):
    if (verification is None) != (verification_sha256 is None):
        raise ValueError('Independent verification path and SHA-256 must be supplied together')
    if verification is not None:
        return _verified_context(run_id, verification, verification_sha256)
    return _preservation_context(run_id)[:4]


def _matches_previous(manifest, previous):
    expected = {item['path']: item for item in previous['manifest']}
    if set(expected) != {item['path'] for item in manifest['entries']}:
        raise RuntimeError('Preserved tree topology changed')
    if manifest['root_mode'] != int(previous['root_mode'], 8) & ~0o222:
        raise RuntimeError('Preserved root permissions changed')
    for item in manifest['entries']:
        old = expected[item['path']]
        mode = int(old['mode'], 8) & (~0o222 if old['kind'] != 'symlink' else 0o7777)
        if item['type'] != old['kind'] or item['mode'] != mode:
            raise RuntimeError('Preserved tree type/permissions changed: ' + item['path'])
        if item['type'] == 'file' and (item['sha256'], item['bytes']) != (old['sha256'], old['bytes']):
            raise RuntimeError('Preserved file changed: ' + item['path'])
        if item['type'] == 'symlink' and item['target'] != old['target']:
            raise RuntimeError('Preserved link changed: ' + item['path'])


def _archive_matches(archive, manifest):
    path = Path(archive['archive_path'])
    storage._safe_directory(path.parent)
    if storage._file_sha(path) != archive['archive_sha256']:
        raise RuntimeError('Pinned official archive changed')
    wanted = {manifest['source_name'].split('.before-', 1)[0] + '/' + item['path']: item
              for item in manifest['entries'] if item['type'] == 'file'
              and not any(part in ('qa', 'logs') for part in PurePosixPath(item['path']).parts)
              and not Path(item['path']).name.startswith('replay-')
              and not item['path'].endswith(('.log', '.out', '.err'))}
    matched, seen = {}, set()
    with storage._open_file(path) as raw, tarfile.open(fileobj=raw, mode='r|gz') as contents:
        for member in contents:
            name = member.name.removeprefix('./').rstrip('/')
            storage._relative(name)
            if name in seen:
                raise ValueError('Duplicate official archive member: ' + name)
            seen.add(name)
            item = wanted.get(name)
            if item and member.isfile() and member.size == item['bytes']:
                with contents.extractfile(member) as handle:
                    if storage._hash_stream(handle) == item['sha256']:
                        matched[item['path']] = member.name
    if storage._file_sha(path) != archive['archive_sha256']:
        raise RuntimeError('Official archive changed during verification')
    return matched


def plan(run_id, verification=None, verification_sha256=None):
    storage.guard()
    with runtime_lock(ROOT):
        _idle()
        source, previous, archive, pins = _context(run_id, verification, verification_sha256)
        manifest, capture = storage._tree(source)
        _matches_previous(manifest, previous)
        matches = _archive_matches(archive, manifest)
        if storage._tree(source) != (manifest, capture):
            raise RuntimeError('Preserved tree changed during retention planning')
        result = {'policy': POLICY, 'status': 'PLANNED', 'source': str(source), 'run_id': run_id,
                  'manifest': manifest, 'source_capture': capture, 'archive': archive,
                  'remove': matches, 'evidence': pins, 'new_archive_created': False,
                  'verification': None if verification is None else {'path': verification, 'sha256': verification_sha256},
                  'verification_scope': 'PRESERVATION_ONLY_NO_RUN_ACCEPTANCE' if verification is None else 'PRESERVATION_AND_EXISTING_INDEPENDENT_ACCEPTANCE',
                  'tool_sha256': storage._file_sha(Path(__file__).resolve()),
                  'storage_helper_sha256': storage._file_sha(Path(storage.__file__).resolve()),
                  'duplicate_bytes': sum(item['bytes'] for item in manifest['entries'] if item['path'] in matches),
                  'retained_unique_bytes': sum(item['bytes'] for item in manifest['entries'] if item['type'] == 'file' and item['path'] not in matches)}
        namespace = _namespace(source, create=True)
        checksum = storage._save(namespace / 'plan.json', result)
        return {'status': 'PLANNED', 'plan': str(namespace / 'plan.json'), 'plan_sha256': checksum,
                'duplicate_files': len(matches), 'duplicate_bytes': result['duplicate_bytes'],
                'retained_unique_bytes': result['retained_unique_bytes'], 'new_archive_created': False}


def _idle():
    # Same activity check as the worker; import kept local to avoid a module cycle.
    import replay_mth_core
    replay_mth_core.idle()


def _load_plan(plan_path, plan_sha256, allow_hold=False):
    plan_path = Path(plan_path)
    record, pin = _record(plan_path)
    if pin['sha256'] != plan_sha256 or record.get('policy') != POLICY or record.get('status') != 'PLANNED':
        raise ValueError('Pinned retention plan differs')
    source = storage._source(record['source'])
    if plan_path != _namespace(source) / 'plan.json':
        raise ValueError('Retention plan belongs to another namespace')
    storage._manifest(record['manifest'])
    if not allow_hold:
        _held(source)
    return source, record, plan_path.parent


def _check_remaining(source, record, allow_incomplete_modes=False):
    actual, capture = storage._tree(source)
    expected = {item['path']: item for item in record['manifest']['entries']}
    remaining = {item['path']: item for item in actual['entries']}
    absent = set(expected) - set(remaining)
    writable_parents = {str(PurePosixPath(name).parent) for name in record['remove']}
    if not absent <= set(record['remove']) or set(remaining) - set(expected):
        raise RuntimeError('Unplanned tree changes during compaction')
    for name, item in remaining.items():
        if item['type'] == 'directory':
            allowed_modes = {expected[name]['mode']}
            if allow_incomplete_modes and name in writable_parents:
                allowed_modes.add(expected[name]['mode'] | 0o700)
            if expected[name]['type'] != 'directory' or item['mode'] not in allowed_modes:
                raise RuntimeError('Retained directory changed: ' + name)
        elif item != expected[name]:
            raise RuntimeError('Retained entry changed: ' + name)
        if item['type'] != 'directory' and capture[name] != record['source_capture'][name]:
            raise RuntimeError('Retained file/link identity changed: ' + name)
        if item['type'] == 'directory' and capture[name][:2] != record['source_capture'][name][:2]:
            raise RuntimeError('Retained directory identity changed: ' + name)
    root_modes = {record['manifest']['root_mode']}
    if allow_incomplete_modes and '.' in writable_parents:
        root_modes.add(record['manifest']['root_mode'] | 0o700)
    if capture['.'][:2] != record['source_capture']['.'][:2] or actual['root_mode'] not in root_modes:
        raise RuntimeError('Preserved root changed')
    return actual, capture


def compact(plan_path, plan_sha256):
    storage.guard()
    with runtime_lock(ROOT):
        _idle()
        source, record, namespace = _load_plan(plan_path, plan_sha256)
        if (namespace / 'complete.json').exists():
            raise FileExistsError('Compaction already completed')
        for pin in record['evidence']:
            if storage._file_sha(Path(pin['path'])) != pin['sha256']:
                raise RuntimeError('Acceptance/verification evidence changed')
        # Re-run acceptance and output checks; a plan is not permission to delete changed data.
        scan_pin = record['verification']
        _context(record['run_id'], scan_pin['path'] if scan_pin else None, scan_pin['sha256'] if scan_pin else None)
        if _archive_matches(record['archive'], record['manifest']) != record['remove']:
            raise RuntimeError('Official recovery members differ')
        started = namespace / 'started.json'
        if started.exists() and storage._load(started).get('plan_sha256') != plan_sha256:
            raise RuntimeError('Another compaction attempt owns this namespace')
        if not started.exists() and storage._tree(source) != (record['manifest'], record['source_capture']):
            raise RuntimeError('Preserved tree changed before first compaction')
        _check_remaining(source, record, allow_incomplete_modes=started.exists())
        # Durable plan and provider precede the first unlink. No copy/archive is made.
        for path in (Path(plan_path), Path(record['archive']['archive_path'])):
            with storage._open_file(path) as handle:
                os.fsync(handle.fileno())
        storage._sync_dir(namespace)
        if not started.exists():
            storage._save(started, {'plan_sha256': plan_sha256, 'status': 'COMPACTING'})
        rootfd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name in record['remove']:
                relative = PurePosixPath(name)
                with storage._directory_fd(rootfd, str(relative.parent)) as parent:
                    info = os.fstat(parent)
                    expected_parent = record['source_capture'][str(relative.parent)]
                    if [info.st_dev, info.st_ino] != expected_parent[:2]:
                        raise RuntimeError('Compaction directory was replaced')
                    os.fchmod(parent, stat.S_IMODE(info.st_mode) | 0o700)
                    try:
                        try:
                            file_info = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
                        except FileNotFoundError:
                            continue  # A resumed operation may have removed this planned duplicate.
                        if storage._stamp(file_info) != record['source_capture'][name]:
                            raise RuntimeError('Duplicate changed before deletion: ' + name)
                        os.unlink(relative.name, dir_fd=parent)
                        os.fsync(parent)
                    finally:
                        os.fchmod(parent, expected_parent[4])
        finally:
            os.close(rootfd)
        actual, capture = _check_remaining(source, record)
        if set(record['remove']) & {item['path'] for item in actual['entries']}:
            raise RuntimeError('Compaction incomplete')
        result = {'policy': POLICY, 'status': 'COMPACTED', 'source': str(source),
                  'plan_sha256': plan_sha256, 'remaining_capture': capture,
                  'duplicate_files_removed': len(record['remove']), 'duplicate_bytes_removed': record['duplicate_bytes'],
                  'retained_unique_bytes': record['retained_unique_bytes'], 'new_archive_created': False}
        result['verification_scope'] = record['verification_scope']
        storage._save(namespace / 'complete.json', result)
        return result


def restore(plan_path, plan_sha256, destination):
    """Reconstruct into a fresh rollback name; never overwrite a current tree."""
    storage.guard()
    with runtime_lock(ROOT):
        _idle()
        source, record, namespace = _load_plan(plan_path, plan_sha256, allow_hold=True)
        started = namespace / 'started.json'
        if started.exists() and storage._load(started).get('plan_sha256') != plan_sha256:
            raise RuntimeError('Another compaction attempt owns this namespace')
        _check_remaining(source, record, allow_incomplete_modes=started.exists())
        if _archive_matches(record['archive'], record['manifest']) != record['remove']:
            raise RuntimeError('Official recovery archive differs')
        destination = storage._source(destination, exists=False)
        if destination.name.split('.before-', 1)[0] != source.name.split('.before-', 1)[0]:
            raise ValueError('Restore release differs')
        manifest = record['manifest']
        directories = [item for item in manifest['entries'] if item['type'] == 'directory']
        destination.mkdir(mode=0o700)
        for item in sorted(directories, key=lambda row: row['path'].count('/')):
            (destination / item['path']).mkdir(mode=0o700)
        by_member = {member: name for name, member in record['remove'].items()}
        with storage._open_file(Path(record['archive']['archive_path'])) as raw, tarfile.open(fileobj=raw, mode='r|gz') as archive:
            for member in archive:
                name = by_member.get(member.name)
                if name:
                    with archive.extractfile(member) as incoming, (destination / name).open('xb') as outgoing:
                        _copy(incoming, outgoing)
        for item in manifest['entries']:
            path = destination / item['path']
            if item['type'] == 'file':
                if item['path'] not in record['remove']:
                    with storage._open_file(source / item['path']) as incoming, path.open('xb') as outgoing:
                        _copy(incoming, outgoing)
                path.chmod(item['mode'])
                os.utime(path, ns=(item['mtime_ns'], item['mtime_ns']))
            elif item['type'] == 'symlink':
                path.symlink_to(item['target'])
                os.utime(path, ns=(item['mtime_ns'], item['mtime_ns']), follow_symlinks=False)
        for item in sorted(directories, key=lambda row: row['path'].count('/'), reverse=True):
            path = destination / item['path'];path.chmod(item['mode'])
            os.utime(path, ns=(item['mtime_ns'], item['mtime_ns']))
        destination.chmod(manifest['root_mode'])
        os.utime(destination, ns=(manifest['root_mtime_ns'], manifest['root_mtime_ns']))
        actual, _ = storage._tree(destination)
        if actual != dict(manifest, source_name=destination.name):
            raise RuntimeError('Restored tree differs; partial destination retained')
        return {'status': 'PASS_RESTORED_TREE_VERIFICATION', 'destination': str(destination), 'plan_sha256': plan_sha256}


def _copy(incoming, outgoing):
    for block in iter(lambda: incoming.read(4 * 1024 * 1024), b''):
        outgoing.write(block)
    outgoing.flush();os.fsync(outgoing.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    status_parser = commands.add_parser('status')
    status_parser.add_argument('--version', required=True, choices=tuple(VERSIONS.values()))
    planner = commands.add_parser('plan')
    planner.add_argument('--run-id', required=True)
    planner.add_argument('--verification')
    planner.add_argument('--verification-sha256')
    for name in ('compact', 'restore'):
        child = commands.add_parser(name)
        child.add_argument('--plan-path', required=True)
        child.add_argument('--plan-sha256', required=True)
        if name == 'restore':child.add_argument('--destination', required=True)
    args = vars(parser.parse_args());command = args.pop('command')
    if command == 'status':
        result = status(args['version'])
    else:
        result = globals()[command](**args)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
