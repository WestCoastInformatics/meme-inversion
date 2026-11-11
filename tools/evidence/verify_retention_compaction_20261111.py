#!/usr/bin/env python3
"""Read-only, independent check of the two user-approved retention operations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import stat

from replay_process import runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
APPROVED = {'snomed': ('SNOMEDCT_US_2026_09_01', 'common-snomed-generated-20261110', 27),
            'mth': ('MTH_2026AA', 'common-mth-generated-20261110', 56)}


def stamp(info):
    return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size, stat.S_IMODE(info.st_mode)]


def checksum(path):
    path = Path(path)
    if path.resolve() != path:
        raise ValueError('Unexpected linked file or ancestor: ' + str(path))
    value = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Expected a regular file')
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            value.update(block)
        if stamp(os.fstat(handle.fileno())) != stamp(before) or stamp(path.lstat()) != stamp(before):
            raise RuntimeError('File changed while checking: ' + str(path))
    return value.hexdigest()


def record(path, expected):
    if checksum(path) != expected:
        raise RuntimeError('Pinned record changed: ' + str(path))
    result = json.loads(Path(path).read_text())
    if checksum(path) != expected:
        raise RuntimeError('Record changed while reading')
    return result


def metadata(root):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(base) / name
            info = path.lstat()
            result[str(path.relative_to(root))] = {
                'device': info.st_dev, 'inode': info.st_ino, 'mode': info.st_mode,
                'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
                'target': os.readlink(path) if path.is_symlink() else None}
    return result


def retained_tree(source, plan, complete):
    """Rehash every retained regular file; accept exactly the approved omissions."""
    if source.resolve() != source or not source.is_dir():
        raise ValueError('Unexpected retained root')
    expected = {item['path']: item for item in plan['manifest']['entries']}
    actual = metadata(source)
    if set(actual) != set(expected) - set(plan['remove']):
        raise RuntimeError('Unexpected added/missing retained entries')
    capture = {'.': stamp(source.lstat())}
    regular_files = regular_bytes = 0
    for name, info in actual.items():
        item = expected[name]
        mode = stat.S_IMODE(info['mode'])
        if mode != item['mode']:
            raise RuntimeError('Retained permissions changed: ' + name)
        path = source / name
        if item['type'] == 'file':
            if not stat.S_ISREG(info['mode']) or checksum(path) != item['sha256'] or info['size'] != item['bytes']:
                raise RuntimeError('Retained file bytes changed: ' + name)
            regular_files += 1;regular_bytes += item['bytes']
        elif item['type'] == 'symlink':
            if not stat.S_ISLNK(info['mode']) or info['target'] != item['target']:
                raise RuntimeError('Retained link changed: ' + name)
        elif item['type'] != 'directory' or not stat.S_ISDIR(info['mode']):
            raise RuntimeError('Retained entry type changed: ' + name)
        capture[name] = stamp(path.lstat())
        if item['type'] == 'directory' and capture[name][:2] != plan['source_capture'][name][:2]:
            raise RuntimeError('Retained directory identity changed: ' + name)
        if item['type'] != 'directory' and capture[name] != plan['source_capture'][name]:
            raise RuntimeError('Retained identity/timestamp changed: ' + name)
    if (capture != complete['remaining_capture'] or capture['.'][4] != plan['manifest']['root_mode']
            or capture['.'][:2] != plan['source_capture']['.'][:2]):
        raise RuntimeError('Completed retained tree metadata changed')
    if regular_bytes != plan['retained_unique_bytes']:
        raise RuntimeError('Retained byte total differs')
    return {'regular_files_verified': regular_files, 'regular_bytes_verified': regular_bytes,
            'entries_verified': len(actual), 'retained_file_and_link_modes_identities_and_timestamps_unchanged': True,
            'directory_modes_and_identities_unchanged': True}


def verify(request):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Verification requires tomcata on dev')
    if set(request['plans']) != set(APPROVED):
        raise ValueError('Only the two approved plans may be verified')
    reports, runtimes = {}, {}
    with runtime_lock(ROOT):
        for name, spec in request['plans'].items():
            version, run_id, count = APPROVED[name]
            plan = record(spec['plan'], spec['plan_sha256'])
            complete = record(spec['complete'], spec['complete_sha256'])
            source = ROOT / 'sources' / (version + '.before-' + run_id)
            namespace = ROOT / 'qa/replay-retention' / source.name
            if (Path(spec['plan']) != namespace / 'plan.json' or Path(spec['complete']) != namespace / 'complete.json'
                    or plan['source'] != str(source) or complete['source'] != str(source)
                    or complete['status'] != 'COMPACTED' or complete['plan_sha256'] != spec['plan_sha256']
                    or len(plan['remove']) != count or complete['duplicate_files_removed'] != count
                    or complete['duplicate_bytes_removed'] != plan['duplicate_bytes']
                    or complete['new_archive_created'] is not False):
                raise RuntimeError('Completion does not match the approved operation')
            archive = Path(plan['archive']['archive_path'])
            if archive != ROOT / 'sources' / (version + '.tgz') or checksum(archive) != plan['archive']['archive_sha256']:
                raise RuntimeError('Official recovery archive changed')
            for relative, member in plan['remove'].items():
                if member.removeprefix('./') != version + '/' + relative:
                    raise RuntimeError('Unexpected archive recovery mapping')
            for pin in plan['evidence']:
                if checksum(Path(pin['path'])) != pin['sha256']:
                    raise RuntimeError('Original source/acceptance/failure evidence changed')
            current = ROOT / 'sources' / version
            if metadata(current) != request['preflight']['plans'][name]['current_tree_metadata']:
                raise RuntimeError('Current inversion tree changed')
            verification = record(plan['verification']['path'], plan['verification']['sha256'])
            rows = [row for row in verification['runs'] if row['run_id'] == run_id]
            if len(rows) != 1 or len(rows[0]['outputs_verified']) != (23 if name == 'mth' else 5):
                raise RuntimeError('Incomplete current output inventory')
            for output, expected in rows[0]['outputs_verified'].items():
                if Path(output).name != output or checksum(current / 'src' / output) != expected:
                    raise RuntimeError('Current inversion output changed: ' + output)
            lock_path = ROOT / 'qa/replay-requests' / run_id / 'case.lock.json'
            lock = json.loads(lock_path.read_text())  # Its exact bytes were checked above.
            for item in lock['runtime_files']:
                previous = runtimes.setdefault(item['repository_path'], item['sha256'])
                if previous != item['sha256']:
                    raise RuntimeError('Conflicting original runtime expectations')
            if name == 'mth':
                prior = ROOT / 'sources/MTH_2025AB/src/cui_said_map'
                if checksum(prior) != lock['case']['legacy_case']['prior_map']['sha256']:
                    raise RuntimeError('Required prior MTH identity data changed')
            reports[name] = {**retained_tree(source, plan, complete),
                             'duplicate_files_removed': count, 'duplicate_bytes_removed': plan['duplicate_bytes'],
                             'archive_sha256': plan['archive']['archive_sha256'],
                             'plan_sha256': spec['plan_sha256'], 'complete_sha256': spec['complete_sha256'],
                             'current_outputs_rehashed': len(rows[0]['outputs_verified']),
                             'current_entire_tree_metadata_unchanged': True, 'original_evidence_unchanged': True}
        if len(runtimes) != 169:
            raise RuntimeError('Incomplete original shared runtime inventory')
        for name, expected in runtimes.items():
            if checksum(ROOT / name) != expected:
                raise RuntimeError('Shared runtime changed')
        for name, (version, _, _) in APPROVED.items():
            if metadata(ROOT / 'sources' / version) != request['preflight']['plans'][name]['current_tree_metadata']:
                raise RuntimeError('Current tree changed during postcheck')
        free = shutil.disk_usage(ROOT).free
    return {'status': 'PASS_APPROVED_RETENTION_POSTCHECK', 'sources': reports,
            'current_output_files_rehashed': 28, 'original_shared_runtime_files_rehashed': 169,
            'required_prior_MTH_identity_input_unchanged': True,
            'free_bytes_before': request['preflight']['free_bytes'], 'free_bytes_after': free,
            'free_bytes_increase': free - request['preflight']['free_bytes'],
            'recovery_proof': 'Pinned original per-member plan proofs and unchanged full official archive hashes; retained files independently rehashed. No full restoration copy created.',
            'new_archive_created': False, 'verifier_sha256': checksum(Path(__file__).resolve())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request')
    args = parser.parse_args()
    print(json.dumps(verify(json.loads(Path(args.request).read_text())), indent=2))
