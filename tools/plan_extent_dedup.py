#!/usr/bin/env python3
"""Hash exact MTH duplicates and emit a read-only storage plan, never apply it.

Only --source MTH, an explicit MTH_YYYYAA/AB version, a passed scratch-probe
identifier and a new plan identifier are accepted.  Data files are opened with
O_RDONLY|O_NOFOLLOW|O_NOATIME. No ioctl, chmod, unlink, rewrite, native-run hook,
or physical-sharing operation is performed on source-version files.

The only writes create a fresh QA plan directory, plan.json and receipt.json.
Pair lengths are whole 4096-byte prefixes; partial EOF tails remain outside the
plan. Full-file SHA256 equality is a selection condition, not an authorization
or proof of physical space that could actually be reclaimed.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time

import probe_extent_dedup as scratch


ROOT = scratch.ROOT
OUTPUT_PARTS = ('qa', 'replay-storage-plans')
MIN_BYTES = 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 ** 3
MAX_TOTAL_BYTES = 128 * 1024 ** 3
MAX_FILES = 512
MAX_ROOTS = 32
MAX_SOURCE_ENTRIES = 16384
MAX_ENTRIES = 4096
MAX_DEPTH = 8
MAX_PATH_BYTES = 240
MAX_REPORT_BYTES = 8 * 1024 * 1024
BLOCK = 4096
PROFILE = 'mth-exact-whole-file-readonly-plan-v1'


def _selection(source, version, probe_id, plan_id):
    if source != 'MTH' or not isinstance(version, str) or not re.fullmatch(r'MTH_[0-9]{4}(?:AA|AB)', version):
        raise ValueError('This plan-only profile requires MTH and one exact MTH_YYYYAA/AB version')
    return source, version, scratch.identifier(probe_id), scratch.identifier(plan_id)


def _metadata(value):
    return {'dev': value.st_dev, 'ino': value.st_ino, 'nlink': value.st_nlink,
            'uid': value.st_uid, 'gid': value.st_gid, 'mode': oct(stat.S_IMODE(value.st_mode)),
            'size': value.st_size, 'mtime_ns': value.st_mtime_ns, 'ctime_ns': value.st_ctime_ns,
            'atime_ns': value.st_atime_ns}


def _directory_identity(value):
    return {key: _metadata(value)[key] for key in ('dev', 'ino', 'uid', 'gid', 'mode')}


def _dir_flags():
    return scratch._directory_flags() | os.O_NOATIME


def _open_directory_at(parent, name, device):
    observed = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(observed.st_mode) or observed.st_uid != os.getuid() or observed.st_dev != device:
        raise ValueError('Directory is linked, unowned or on another filesystem')
    fd = os.open(name, _dir_flags(), dir_fd=parent)
    try:
        current = os.fstat(fd)
        if _directory_identity(current) != _directory_identity(observed):
            raise ValueError('Directory changed while opening its no-follow descriptor')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_chain(parts, device):
    fd = os.open(ROOT, scratch._directory_flags())
    try:
        if os.fstat(fd).st_dev != device: raise ValueError('Fixed inversion-root device changed')
        for name in parts:
            child = _open_directory_at(fd, name, device)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON key in pinned evidence')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON evidence')))


def _read_file(fd, name, maximum, readonly=True):
    observed = os.stat(name, dir_fd=fd, follow_symlinks=False)
    if (not stat.S_ISREG(observed.st_mode) or observed.st_uid != os.getuid() or observed.st_nlink != 1 or
            observed.st_size > maximum or (readonly and observed.st_mode & 0o222)):
        raise ValueError('Expected bounded, ordinary, unlinked, owned evidence/code')
    incoming = os.open(name, scratch._read_flags(), dir_fd=fd)
    try:
        before = _metadata(os.fstat(incoming))
        if before != _metadata(observed): raise ValueError('Evidence identity changed while opening')
        chunks, size = [], 0
        while True:
            block = os.read(incoming, min(1024 * 1024, maximum + 1 - size))
            if not block: break
            chunks.append(block); size += len(block)
            if size > maximum: raise ValueError('Evidence exceeded its fixed byte bound')
        after = _metadata(os.fstat(incoming))
        if before != after or after != _metadata(os.stat(name, dir_fd=fd, follow_symlinks=False)) or size != before['size']:
            raise ValueError('Evidence bytes/metadata changed while reading')
        return b''.join(chunks), before
    finally:
        os.close(incoming)


def _probe(probe_id, environment):
    fd = _open_chain(('qa', 'replay-storage-probes', probe_id), environment['device'])
    try:
        raw, metadata = _read_file(fd, 'report.json', 128 * 1024)
    finally:
        os.close(fd)
    value = _json(raw)
    expected_path = ROOT / 'qa/replay-storage-probes' / probe_id
    if (value.get('schema_version') != 1 or value.get('scope') != 'SYNTHETIC_SCRATCH_ONLY' or
            value.get('status') != 'PASS_SYNTHETIC_SCRATCH_PROBE' or value.get('probe_id') != probe_id or
            value.get('directory') != str(expected_path) or value.get('real_source_data_operated_on') is not False or
            value.get('automatic_real_data_execution_enabled') is not False or
            value.get('metadata_before') != value.get('metadata_after_dedupe') or
            set(value.get('dedupe_metadata_preserved_fields', [])) != set(scratch.META_FIELDS) or
            len(value['dedupe_metadata_preserved_fields']) != len(scratch.META_FIELDS) or
            value.get('hashes_before') != value.get('hashes_after_dedupe') or
            value.get('prefix_physical_sharing_verified_bytes') != scratch.PREFIX):
        raise ValueError('The pinned scratch report does not prove the required metadata/content/extent checks')
    for key in ('hostname', 'account', 'uid', 'kernel', 'machine', 'filesystem', 'device', 'block_bytes'):
        if value['environment'].get(key) != environment.get(key):
            raise ValueError('The passed scratch probe is from a different deployed environment: ' + key)
    if set(value['metadata_before']) != set(scratch.FILES) or set(value['readonly_descriptors']) != set(scratch.FILES):
        raise ValueError('Scratch report inode/descriptor identities are incomplete')
    for name in scratch.FILES:
        item = value['metadata_before'][name]
        if (set(item) != set(scratch.META_FIELDS) or item['dev'] != environment['device'] or
                item['uid'] != environment['uid'] or item['nlink'] != 1 or item['mode'] != oct(scratch.MODES[name]) or
                item['size'] != scratch.PREFIX + len(scratch.TAIL)):
            raise ValueError('Scratch metadata does not describe the fixed independent synthetic inodes')
    if len({item['ino'] for item in value['metadata_before'].values()}) != len(scratch.FILES):
        raise ValueError('Scratch proof aliases its synthetic file inodes')
    if any(value['readonly_descriptors'][name].get(key) != expected for name in scratch.FILES
           for key, expected in (('access', 'O_RDONLY'), ('no_follow', True), ('no_atime', True))):
        raise ValueError('Scratch proof did not use readonly/no-follow/no-atime descriptors')
    scratch._shared_prefix(value['fiemap_after_equal']['source.bin'], value['fiemap_after_equal']['equal.bin'])
    controls = {item['step']: item for item in value['events']}
    if (controls['equal-prefix-dedupe']['status'] != 0 or controls['different-prefix-dedupe']['status'] != 1 or
            controls['equal-prefix-dedupe']['bytes_deduped'] != scratch.PREFIX or
            controls['different-prefix-dedupe']['bytes_deduped'] != 0 or
            any(value['cow'].get(key) is not True for key in ('source_hash_unchanged', 'only_requested_destination_byte_changed',
                    'tails_intact', 'written_block_physically_independent')) or
            value['cow']['source'] != value['hashes_before']['source.bin']):
        raise ValueError('Scratch equality/mismatch/independent-COW controls are incomplete')
    if any(controls[step].get(key) != expected for step in ('equal-prefix-dedupe', 'different-prefix-dedupe')
           for key, expected in (('state', 'returned'), ('requested_bytes', scratch.PREFIX), ('destinations', 1),
                                 ('source_offset', 0), ('destination_offset', 0))):
        raise ValueError('Scratch probe requests do not match the one-destination fixed prefix ABI')
    initial = bytes((index * 73 + 19) % 256 for index in range(scratch.PREFIX)) + scratch.TAIL
    different = bytearray(initial); different[2 * BLOCK] ^= 1
    cow = bytearray(initial); cow[0] ^= 1
    expected_hashes = dict(zip(scratch.FILES, (hashlib.sha256(initial).hexdigest(), hashlib.sha256(initial).hexdigest(), hashlib.sha256(different).hexdigest())))
    if (any(value['hashes_before'][name]['sha256'] != expected_hashes[name] or
            value['hashes_before'][name]['bytes'] != len(initial) or value['hashes_before'][name]['tail_hex'] != scratch.TAIL.hex()
            for name in scratch.FILES) or value['cow']['destination']['sha256'] != hashlib.sha256(cow).hexdigest() or
            value['cow']['destination']['tail_hex'] != scratch.TAIL.hex() or value['cow']['destination_mode_restored'] != '0o444'):
        raise ValueError('Scratch proof hashes/tails do not match the fixed synthetic equality/mismatch/COW data')
    return {'probe_id': probe_id, 'path': str(expected_path / 'report.json'),
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'metadata': metadata,
            'status': value['status'], 'kernel': value['environment']['kernel'],
            'scope': 'Passed synthetic scratch evidence only; no permission for real-file maintenance'}


def _apparatus():
    result = []
    for path in (Path(__file__).absolute(), Path(scratch.__file__).absolute()):
        for ancestor in (path.parent, *path.parents):
            if not stat.S_ISDIR(ancestor.lstat().st_mode) or ancestor.resolve() != ancestor:
                raise ValueError('Apparatus has a linked ancestor')
        fd = os.open(path.parent, scratch._directory_flags())
        try: raw, metadata = _read_file(fd, path.name, 1024 * 1024, readonly=False)
        finally: os.close(fd)
        result.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'metadata': metadata})
    return result


def _held(name, device):
    fd = os.open(ROOT, scratch._directory_flags())
    try:
        for component in ('qa', 'replay-retention', 'holds'):
            try: child = _open_directory_at(fd, component, device)
            except FileNotFoundError: return False
            os.close(fd); fd = child
        try: os.stat(name + '.json', dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError: return False
        return True  # All markers, including dangling symlinks, hold the tree.
    finally:
        os.close(fd)


def _excluded(relative):
    for part in PurePosixPath(relative).parts:
        value = part.lower()
        if ('replay' in value or 'log' in value or value in ('qa', 'test', 'tests', 'missing.tgs', 'missing.vsabs') or
                value.startswith(('qa_', 'qa.')) or 'checklist' in value or value.endswith(('.json', '.out', '.err'))):
            return True
    return False


def _entry_names(fd, maximum):
    names = []
    with os.scandir(fd) as entries:
        for entry in entries:
            names.append(entry.name)
            if len(names) > maximum: raise ValueError('Directory enumeration exceeds the fixed entry bound')
    return sorted(names)


def _names(source_fd, version):
    names = [name for name in _entry_names(source_fd, MAX_SOURCE_ENTRIES) if name == version or name.startswith(version + '.before-')]
    if len(names) > MAX_ROOTS: raise ValueError('Matching MTH roots exceed the fixed plan bound')
    if version not in names: raise ValueError('The canonical current MTH version folder is absent')
    return sorted(names, key=lambda name: (name != version, name))


def _inventory(version, environment):
    source_fd = _open_chain(('sources',), environment['device'])
    roots, files, skipped, seen_directories = [], [], [], set()
    total_entries = 0
    try:
        names = _names(source_fd, version)
        for name in names:
            if name != version and not re.fullmatch(re.escape(version) + r'\.before-[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name):
                skipped.append({'path': str(ROOT / 'sources' / name), 'reason': 'unsupported-retained-folder-name'}); continue
            if _held(name, environment['device']):
                skipped.append({'path': str(ROOT / 'sources' / name), 'reason': 'retention-hold'}); continue
            try: fd = _open_directory_at(source_fd, name, environment['device'])
            except (ValueError, OSError) as error:
                skipped.append({'path': str(ROOT / 'sources' / name), 'reason': 'unsafe-linked-or-unowned-root', 'detail': str(error)}); continue
            try:
                identity = _directory_identity(os.fstat(fd)); inode = (identity['dev'], identity['ino'])
                if inode in seen_directories:
                    skipped.append({'path': str(ROOT / 'sources' / name), 'reason': 'repeated-root-directory-inode'}); continue
                seen_directories.add(inode)
                root = {'name': name, 'path': str(ROOT / 'sources' / name), 'role': 'current' if name == version else 'retained',
                        'identity_before': identity, 'held': False}
                roots.append(root)
                try: src = _open_directory_at(fd, 'src', environment['device'])
                except (ValueError, OSError) as error:
                    skipped.append({'path': root['path'] + '/src', 'reason': 'unsafe-linked-unowned-or-missing-src', 'detail': str(error)}); continue
                def walk(directory, relative, ancestors):
                    nonlocal total_entries
                    observed_dir = _directory_identity(os.fstat(directory)); directory_inode = (observed_dir['dev'], observed_dir['ino'])
                    if directory_inode in seen_directories:
                        skipped.append({'path': root['path'] + '/' + relative, 'reason': 'repeated-directory-inode'}); return
                    seen_directories.add(directory_inode)
                    current_ancestors = ancestors + [{'relative_path': relative, 'identity': observed_dir}]
                    for child_name in _entry_names(directory, MAX_ENTRIES - total_entries):
                        total_entries += 1
                        if total_entries > MAX_ENTRIES: raise ValueError('Source traversal exceeds the fixed entry bound')
                        child_path = relative + '/' + child_name; absolute = root['path'] + '/' + child_path
                        if len(child_path.encode()) > MAX_PATH_BYTES or len(PurePosixPath(child_path).parts) > MAX_DEPTH:
                            raise ValueError('Source path/depth exceeds the fixed traversal bound')
                        if _excluded(child_path): skipped.append({'path': absolute, 'reason': 'qa-log-replay-record'}); continue
                        observed = os.stat(child_name, dir_fd=directory, follow_symlinks=False)
                        if stat.S_ISDIR(observed.st_mode):
                            try: nested = _open_directory_at(directory, child_name, environment['device'])
                            except (ValueError, OSError) as error:
                                skipped.append({'path': absolute, 'reason': 'unsafe-linked-or-unowned-directory', 'detail': str(error)}); continue
                            try: walk(nested, child_path, current_ancestors)
                            finally: os.close(nested)
                        elif not stat.S_ISREG(observed.st_mode): skipped.append({'path': absolute, 'reason': 'symlink-or-nonregular'})
                        elif observed.st_dev != environment['device'] or observed.st_uid != os.getuid() or observed.st_nlink != 1:
                            skipped.append({'path': absolute, 'reason': 'unowned-linked-or-cross-filesystem-file'})
                        elif observed.st_mode & 0o222: skipped.append({'path': absolute, 'reason': 'writable-file'})
                        elif observed.st_size < MIN_BYTES: skipped.append({'path': absolute, 'reason': 'below-one-MiB'})
                        elif observed.st_size > MAX_FILE_BYTES: raise ValueError('An eligible source file exceeds the fixed length bound')
                        else:
                            files.append({'root': name, 'root_role': root['role'], 'relative_path': child_path, 'path': absolute,
                                          'metadata_inventory': _metadata(observed), 'ancestors': current_ancestors})
                            if len(files) > MAX_FILES: raise ValueError('Eligible source files exceed the fixed count bound')
                try: walk(src, 'src', [])
                finally: os.close(src)
            finally:
                os.close(fd)
        if sum(item['metadata_inventory']['size'] for item in files) > MAX_TOTAL_BYTES:
            raise ValueError('Eligible input bytes exceed the fixed total hash bound')
        aliases = defaultdict(list)
        for item in files: aliases[(item['metadata_inventory']['dev'], item['metadata_inventory']['ino'])].append(item)
        aliased = {item['path'] for values in aliases.values() if len(values) > 1 for item in values}
        if aliased:
            skipped.extend({'path': path, 'reason': 'same-inode-visible-at-multiple-paths'} for path in sorted(aliased))
            files = [item for item in files if item['path'] not in aliased]
        return roots, files, skipped, names
    finally:
        os.close(source_fd)


def _file_descriptor(item, roots, device):
    root = next(value for value in roots if value['name'] == item['root'])
    parts = PurePosixPath(item['relative_path']).parts
    fd = _open_chain(('sources', item['root']), device)
    try:
        if _directory_identity(os.fstat(fd)) != root['identity_before']:
            raise ValueError('Selected source root identity changed')
        for part, expected in zip(parts[:-1], item['ancestors']):
            child = _open_directory_at(fd, part, device)
            os.close(fd); fd = child
            if _directory_identity(os.fstat(fd)) != expected['identity']:
                raise ValueError('Selected file has a changed or linked ancestor')
        if len(parts) - 1 != len(item['ancestors']): raise ValueError('Incomplete source ancestor binding')
        observed = os.stat(parts[-1], dir_fd=fd, follow_symlinks=False)
        if not stat.S_ISREG(observed.st_mode) or _metadata(observed) != item['metadata_inventory']:
            raise ValueError('Eligible source metadata changed before/after hashing')
        incoming = os.open(parts[-1], scratch._read_flags(), dir_fd=fd)
        if _metadata(os.fstat(incoming)) != item['metadata_inventory']:
            os.close(incoming); raise ValueError('Source descriptor identity changed while opening')
        return incoming
    finally:
        os.close(fd)


def _hash_files(files, roots, environment):
    for item in files:
        fd = _file_descriptor(item, roots, environment['device'])
        try:
            before = _metadata(os.fstat(fd)); digest = hashlib.sha256(); size = 0
            while True:
                block = os.read(fd, 4 * 1024 * 1024)
                if not block: break
                digest.update(block); size += len(block)
                if size > before['size']: raise ValueError('Source file grew while hashing')
            after = _metadata(os.fstat(fd))
            if before != after or size != before['size']:
                raise ValueError('Source body/metadata changed while hashing')
            item.update(sha256=digest.hexdigest(), bytes=size, metadata_before=before, metadata_after=after,
                        readonly_descriptor={'access': 'O_RDONLY', 'no_follow': True, 'no_atime': True})
        finally:
            os.close(fd)


def _groups(files):
    grouped = defaultdict(list)
    for item in files: grouped[(item['sha256'], item['bytes'])].append(item)
    groups, pairs = [], []
    for (digest, size), members in sorted(grouped.items()):
        ordered = sorted(members, key=lambda item: (item['root_role'] != 'current', item['root'], item['relative_path']))
        if len(ordered) < 2: continue
        donor = ordered[0]
        targets = [item for item in ordered[1:] if item['root_role'] == 'retained']
        groups.append({'sha256': digest, 'bytes': size, 'members': [item['path'] for item in ordered],
                       'donor': donor['path'], 'donor_role': donor['root_role'], 'targets': [item['path'] for item in targets]})
        for target in sorted(targets, key=lambda item: item['path']):
            if (donor['metadata_before']['dev'] != target['metadata_before']['dev'] or
                    donor['metadata_before']['ino'] == target['metadata_before']['ino']):
                raise ValueError('A planned pair is cross-filesystem or aliases one inode')
            length = size // BLOCK * BLOCK
            pairs.append({'donor': donor['path'], 'donor_role': donor['root_role'], 'target': target['path'],
                          'target_role': 'retained', 'sha256': digest, 'bytes': size,
                          'source_offset': 0, 'destination_offset': 0, 'aligned_prefix_bytes': length,
                          'untouched_eof_tail_bytes': size - length,
                          'potential_byte_upper_bound': length, 'full_file_hash_and_size_equal': True})
    return groups, pairs


def _finish_inventory(version, roots, files, names, environment):
    fd = _open_chain(('sources',), environment['device'])
    try:
        if _names(fd, version) != names: raise ValueError('Matching source-version roots changed during planning')
    finally: os.close(fd)
    for root in roots:
        if _held(root['name'], environment['device']): raise ValueError('A selected folder acquired a retention hold')
        fd = _open_chain(('sources', root['name']), environment['device'])
        try: root['identity_after'] = _directory_identity(os.fstat(fd))
        finally: os.close(fd)
        if root['identity_after'] != root['identity_before']: raise ValueError('A selected source root changed')
    for item in files:
        fd = _file_descriptor(item, roots, environment['device'])
        try: item['metadata_final'] = _metadata(os.fstat(fd))
        finally: os.close(fd)
        if item['metadata_final'] != item['metadata_before']: raise ValueError('Source metadata changed after hashing')


def _output_directory(plan_id, environment):
    fd = _open_chain(('qa',), environment['device'])
    try:
        try: os.mkdir(OUTPUT_PARTS[-1], 0o700, dir_fd=fd)
        except FileExistsError: pass
        child = _open_directory_at(fd, OUTPUT_PARTS[-1], environment['device'])
        os.close(fd); fd = child
        if stat.S_IMODE(os.fstat(fd).st_mode) & 0o022:
            raise ValueError('Plan output parent is writable by other accounts')
        os.mkdir(plan_id, 0o700, dir_fd=fd)  # No overwriting/reuse, even after failure.
        return _open_directory_at(fd, plan_id, environment['device'])
    finally: os.close(fd)


def _save(fd, name, value):
    if name not in ('plan.json', 'receipt.json'): raise ValueError('Only the fixed new QA report names may be written')
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    if len(raw) > MAX_REPORT_BYTES: raise ValueError('Plan evidence exceeds its fixed output bound')
    out = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(out, view)
            if count <= 0: raise OSError('Short plan report write')
            view = view[count:]
        os.fchmod(out, 0o400); os.fsync(out)
    finally: os.close(out)
    os.fsync(fd)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def plan(source, version, probe_id, plan_id):
    source, version, probe_id, plan_id = _selection(source, version, probe_id, plan_id)
    environment = scratch._environment()
    if environment['block_bytes'] != BLOCK: raise ValueError('Only reviewed 4096-byte aligned ranges are supported')
    probe = _probe(probe_id, environment)
    apparatus = _apparatus()
    output = ROOT.joinpath(*OUTPUT_PARTS, plan_id)
    fd = _output_directory(plan_id, environment)
    report = {'schema_version': 1, 'artifact_type': 'ncimeta-extent-dedup-plan', 'profile': PROFILE,
              'status': 'FAILED_PLAN', 'source': source, 'version': version, 'plan_id': plan_id,
              'execute_authorized': False, 'existing_file_writes_performed': False,
              'existing_files_removed': False, 'ioctls_performed': False,
              'automatic_native_run_hook': False, 'production_eligible': False,
              'old_deletion_plans_executed_or_replayed': False,
              'scope': 'PLAN_ONLY; new QA JSON evidence only; every source-version file remains unchanged',
              'future_operation_requires_separate_concrete_user_approval': True,
              'environment': environment, 'probe': probe, 'apparatus': apparatus, 'directory': str(output),
              'started_ns': time.time_ns(), 'space_before': scratch._space(fd),
              'bounds': {'minimum_file_bytes': MIN_BYTES, 'maximum_file_bytes': MAX_FILE_BYTES,
                         'maximum_total_hash_bytes': MAX_TOTAL_BYTES, 'maximum_files': MAX_FILES,
                         'maximum_roots': MAX_ROOTS, 'maximum_entries': MAX_ENTRIES, 'maximum_depth': MAX_DEPTH,
                         'maximum_source_directory_entries': MAX_SOURCE_ENTRIES,
                         'maximum_relative_path_bytes': MAX_PATH_BYTES, 'alignment_bytes': BLOCK}}
    try:
        try:
            roots, files, skipped, names = _inventory(version, environment)
            report.update(roots=roots, files=files, skipped=skipped)
            _hash_files(files, roots, environment)
            groups, pairs = _groups(files)
            _finish_inventory(version, roots, files, names, environment)
            if _probe(probe_id, environment) != probe or _apparatus() != apparatus:
                raise ValueError('Pinned scratch proof or apparatus changed during planning')
            by_root = defaultdict(lambda: {'files': 0, 'potential_byte_upper_bound': 0})
            for pair in pairs:
                name = PurePosixPath(pair['target']).parts[len(ROOT.parts) + 1]
                by_root[name]['files'] += 1; by_root[name]['potential_byte_upper_bound'] += pair['potential_byte_upper_bound']
            report.update(status='PLAN_ONLY', groups=groups, pairs=pairs,
                          summary={'files_fully_hashed': len(files), 'full_file_bytes_hashed': sum(item['bytes'] for item in files),
                                   'duplicate_groups': len(groups), 'retained_targets': len(pairs),
                                   'current_targets': 0, 'potential_byte_upper_bound': sum(item['potential_byte_upper_bound'] for item in pairs),
                                   'untouched_target_eof_tail_bytes': sum(item['untouched_eof_tail_bytes'] for item in pairs),
                                   'by_retained_root': dict(sorted(by_root.items())), 'skipped_entries': len(skipped),
                                   'physical_bytes_reclaimed': None,
                                   'limitation': 'No physical extents inspected: existing sharing, holes, metadata costs and future COW may reduce savings'})
        except BaseException as error:
            report['error'] = {'type': type(error).__name__, 'message': str(error)}
        report.update(finished_ns=time.time_ns(), space_after=scratch._space(fd))
        pin = _save(fd, 'plan.json', report)
        receipt = {'schema_version': 1, 'status': report['status'], 'plan_id': plan_id,
                   'plan_path': str(output / 'plan.json'), 'plan_sha256': pin['sha256'], 'plan_bytes': pin['bytes'],
                   'probe_sha256': probe['sha256'], 'execute_authorized': False}
        _save(fd, 'receipt.json', receipt)
        return report, receipt
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, choices=('MTH',))
    parser.add_argument('--version', required=True)
    parser.add_argument('--probe-id', required=True)
    parser.add_argument('--plan-id', required=True)
    args = parser.parse_args(argv)
    try: report, receipt = plan(**vars(args))
    except Exception as error:
        print(json.dumps({'status': 'BLOCKED_PLAN', 'execute_authorized': False, 'error': str(error)})); return 1
    print(json.dumps({**receipt, 'summary': report.get('summary'), 'error': report.get('error')}, indent=2))
    return 0 if report['status'] == 'PLAN_ONLY' else 1


if __name__ == '__main__':
    raise SystemExit(main())
