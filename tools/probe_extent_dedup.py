#!/usr/bin/env python3
"""Probe FIDEDUPERANGE only on new, tiny, synthetic dev-server QA files.

There are no source-file, target-file, directory, size or environment overrides.
This is a filesystem mutation probe, not a real-data maintenance command.

ABI authority (Linux v6.1, x86_64 little endian):
  include/uapi/linux/fs.h: file_dedupe_range/info and FIDEDUPERANGE
  include/uapi/linux/fiemap.h: fiemap/fiemap_extent and SHARED flags
  include/uapi/asm-generic/ioctl.h: _IOC encoding
  fs/remap_range.c: owner-held read-only dedupe, comparison and result handling
  fs/xfs/xfs_file.c, fs/xfs/xfs_reflink.c: range remapping and COW
https://github.com/torvalds/linux/tree/v6.1/include/uapi/linux
https://github.com/torvalds/linux/blob/v6.1/fs/remap_range.c

Legacy bytes_deduped is not a physical-space measurement and can overreport
actual remapping.  This probe independently checks the mapped entire prefix.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import pwd
import re
import socket
import stat
import struct
import sys
import time


ROOT = Path('/local/content/MEME/MEME5/inv')
PARENT_PARTS = ('qa', 'replay-storage-probes')
HOST = 'ncias-d3777-c'
USER = 'tomcata'
BLOCK = 4096
PREFIX = 64 * 1024
TAIL = b'EOF-TAIL-0013'
FILES = ('source.bin', 'equal.bin', 'different.bin')
MODES = dict(zip(FILES, (0o440, 0o444, 0o440)))
META_FIELDS = ('dev', 'ino', 'nlink', 'uid', 'gid', 'mode', 'size', 'mtime_ns', 'ctime_ns', 'atime_ns')

# All formats have explicit widths/byte order; no native struct padding.
DEDUPE_HEADER = struct.Struct('<QQHHI')
DEDUPE_INFO = struct.Struct('<qQQiI')
FIEMAP_HEADER = struct.Struct('<QQIIII')
FIEMAP_EXTENT = struct.Struct('<QQQQQIIII')
FIDEDUPERANGE = (3 << 30) | (DEDUPE_HEADER.size << 16) | (0x94 << 8) | 54
FS_IOC_FIEMAP = (3 << 30) | (FIEMAP_HEADER.size << 16) | (ord('f') << 8) | 11
FIEMAP_FLAG_SYNC = 0x1
FIEMAP_EXTENT_LAST = 0x1
FIEMAP_EXTENT_SHARED = 0x2000
UNSAFE_EXTENTS = 0x2 | 0x4 | 0x8 | 0x80 | 0x100 | 0x200 | 0x400 | 0x800
EXTENT_CAPACITY = 64


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', value):
        raise ValueError('Expected one new probe identifier, not a path')
    return value


def _directory_flags():
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _read_flags():
    # No permissive fallback: the deployed probe must preserve access times.
    return os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC


def _unescape_mount(value):
    return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)


def _environment():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or sys.byteorder != 'little':
        raise ValueError('This probe requires the reviewed Linux x86_64 little-endian ABI')
    if socket.gethostname().split('.')[0] != HOST:
        raise ValueError('This probe is limited to the named dev server')
    if os.geteuid() != os.getuid() or pwd.getpwuid(os.getuid()).pw_name != USER:
        raise ValueError('This probe requires the ordinary tomcata dev account')
    _read_flags()
    for path in (ROOT, *ROOT.parents):
        observed = path.lstat()
        if not stat.S_ISDIR(observed.st_mode) or path.resolve() != path:
            raise ValueError('The fixed inversion root must have real directory ancestors')
    root_stat = ROOT.stat()
    device = str(os.major(root_stat.st_dev)) + ':' + str(os.minor(root_stat.st_dev))
    mountinfo = Path('/proc/self/mountinfo').read_text()
    matches = []
    for line in mountinfo.splitlines():
        before, separator, after = line.partition(' - ')
        fields, filesystem = before.split(), after.split()
        if not separator or len(fields) < 6 or len(filesystem) < 3:
            raise ValueError('Malformed mounted-filesystem evidence')
        mount = Path(_unescape_mount(fields[4]))
        if fields[2] == device and (ROOT == mount or mount in ROOT.parents):
            matches.append((len(mount.parts), filesystem[0], fields[5]))
    if not matches or sorted(matches)[-1][1] != 'xfs' or 'rw' not in sorted(matches)[-1][2].split(','):
        raise ValueError('The fixed inversion root must be on a writable XFS mount')
    geometry = os.statvfs(ROOT)
    if geometry.f_bsize != BLOCK or geometry.f_frsize != BLOCK:
        raise ValueError('The reviewed probe requires 4096-byte filesystem blocks')
    return {'hostname': socket.gethostname(), 'account': USER, 'uid': os.getuid(),
            'kernel': platform.release(), 'machine': platform.machine(), 'filesystem': 'xfs',
            'device': root_stat.st_dev, 'block_bytes': BLOCK,
            'mountinfo_sha256': hashlib.sha256(mountinfo.encode()).hexdigest()}


def _probe_directory(value, environment):
    """Create a new child of the one fixed QA namespace; never reopen a run."""
    value = identifier(value)
    opened = []
    try:
        fd = os.open(ROOT, _directory_flags()); opened.append(fd)
        if os.fstat(fd).st_dev != environment['device']:
            raise ValueError('Fixed-root device changed')
        for component in PARENT_PARTS:
            try:
                os.mkdir(component, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(component, _directory_flags(), dir_fd=fd); opened.append(child)
            observed = os.fstat(child)
            if observed.st_dev != environment['device']:
                raise ValueError('QA probe directory crosses a filesystem boundary')
            if component == PARENT_PARTS[-1] and (observed.st_uid != os.getuid() or stat.S_IMODE(observed.st_mode) & 0o022):
                raise ValueError('Existing probe parent must be owned by tomcata and not writable by others')
            fd = child
        os.mkdir(value, 0o700, dir_fd=fd)  # EEXIST is a hard failure, including a symlink.
        child = os.open(value, _directory_flags(), dir_fd=fd)
        observed = os.fstat(child)
        if observed.st_uid != os.getuid() or observed.st_dev != environment['device'] or stat.S_IMODE(observed.st_mode) != 0o700:
            os.close(child)
            raise ValueError('New probe directory ownership/device/mode differs')
        return child, ROOT.joinpath(*PARENT_PARTS, value)
    finally:
        for fd in reversed(opened): os.close(fd)


def _metadata(fd):
    value = os.fstat(fd)
    if not stat.S_ISREG(value.st_mode) or value.st_uid != os.getuid() or value.st_nlink != 1:
        raise ValueError('Probe files must be ordinary owner-controlled single-link inodes')
    return {'dev': value.st_dev, 'ino': value.st_ino, 'nlink': value.st_nlink,
            'uid': value.st_uid, 'gid': value.st_gid, 'mode': oct(stat.S_IMODE(value.st_mode)),
            'size': value.st_size, 'mtime_ns': value.st_mtime_ns, 'ctime_ns': value.st_ctime_ns,
            'atime_ns': value.st_atime_ns}


def _create(fd, name, raw, mode):
    if name not in FILES or len(raw) != PREFIX + len(TAIL) or mode != MODES[name]:
        raise ValueError('Only the three fixed small synthetic files can be created')
    target = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(target, view)
            if written <= 0: raise OSError('Short synthetic-file write')
            view = view[written:]
        os.fsync(target); os.fchmod(target, mode); os.fsync(target)
        observed = _metadata(target)
        if observed['size'] != len(raw) or observed['mode'] != oct(mode):
            raise ValueError('Created synthetic-file size/mode differs')
    finally:
        os.close(target)


def _open_readonly(fd, name):
    if name not in FILES: raise ValueError('Only fixed synthetic names may be opened')
    result = os.open(name, _read_flags(), dir_fd=fd)
    try:
        observed = _metadata(result)
        if observed['size'] != PREFIX + len(TAIL) or observed['mode'] != oct(MODES[name]):
            raise ValueError('The new synthetic file has changed')
        return result
    except BaseException:
        os.close(result)
        raise


def _readonly_descriptor(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    if flags & os.O_ACCMODE != os.O_RDONLY or not flags & os.O_NOFOLLOW or not flags & os.O_NOATIME:
        raise ValueError('Synthetic descriptor is not read-only/no-follow/no-atime')
    return {'flags': flags, 'access': 'O_RDONLY', 'no_follow': True, 'no_atime': True}


def _body(fd):
    raw = os.pread(fd, PREFIX + len(TAIL) + 1, 0)
    if len(raw) != PREFIX + len(TAIL): raise ValueError('Synthetic file size changed')
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'tail_hex': raw[PREFIX:].hex()}


def _dedupe(source, destination):
    request = bytearray(DEDUPE_HEADER.pack(0, PREFIX, 1, 0, 0) + DEDUPE_INFO.pack(destination, 0, 0, 0, 0))
    fcntl.ioctl(source, FIDEDUPERANGE, request, True)
    header = DEDUPE_HEADER.unpack_from(request)
    fd, offset, progress, status_code, reserved = DEDUPE_INFO.unpack_from(request, DEDUPE_HEADER.size)
    if header != (0, PREFIX, 1, 0, 0) or fd != destination or offset != 0 or reserved != 0:
        raise ValueError('Kernel dedupe response changed request identities/reserved fields')
    return {'status': status_code, 'bytes_deduped': progress, 'requested_bytes': PREFIX,
            'destinations': 1, 'source_offset': 0, 'destination_offset': 0,
            'physical_bytes_reclaimed_claimed': False}


def _fiemap(fd):
    request = bytearray(FIEMAP_HEADER.pack(0, PREFIX, FIEMAP_FLAG_SYNC, 0, EXTENT_CAPACITY, 0) +
                        b'\0' * (EXTENT_CAPACITY * FIEMAP_EXTENT.size))
    fcntl.ioctl(fd, FS_IOC_FIEMAP, request, True)
    start, length, flags, count, capacity, reserved = FIEMAP_HEADER.unpack_from(request)
    if (start, length, flags, capacity, reserved) != (0, PREFIX, FIEMAP_FLAG_SYNC, EXTENT_CAPACITY, 0) or count > EXTENT_CAPACITY:
        raise ValueError('Invalid FIEMAP response bounds')
    result = []
    previous_end = 0
    for index in range(count):
        values = FIEMAP_EXTENT.unpack_from(request, FIEMAP_HEADER.size + index * FIEMAP_EXTENT.size)
        logical, physical, size, r0, r1, extent_flags, r2, r3, r4 = values
        if not size or logical < previous_end or any((r0, r1, r2, r3, r4)) or extent_flags & UNSAFE_EXTENTS:
            raise ValueError('Unreviewed, overlapping or unsafe FIEMAP extent')
        previous_end = logical + size
        result.append({'logical': logical, 'physical': physical, 'length': size, 'flags': extent_flags})
    # The prefix can end inside the last returned extent, so LAST is optional.
    _cover(result)
    return result


def _cover(extents):
    cursor = 0
    for item in extents:
        left, right = item['logical'], item['logical'] + item['length']
        if right <= cursor: continue
        if left > cursor: raise ValueError('The synthetic prefix has a FIEMAP hole')
        cursor = min(PREFIX, right)
        if cursor == PREFIX: return
    raise ValueError('FIEMAP did not cover the complete fixed prefix')


def _physical(extents, offset):
    for item in extents:
        if item['logical'] <= offset < item['logical'] + item['length']:
            return item['physical'] + offset - item['logical'], item
    raise ValueError('No physical mapping covers a synthetic prefix byte')


def _shared_prefix(left, right):
    _cover(left); _cover(right)
    cursor = 0
    while cursor < PREFIX:
        physical_left, a = _physical(left, cursor); physical_right, b = _physical(right, cursor)
        if physical_left != physical_right or not (a['flags'] & b['flags'] & FIEMAP_EXTENT_SHARED):
            raise ValueError('The complete prefix is not physically shared with SHARED flags in both files')
        cursor = min(PREFIX, a['logical'] + a['length'], b['logical'] + b['length'])
    return PREFIX


def _space(fd):
    value = os.fstatvfs(fd)
    return {'block_bytes': value.f_frsize, 'free_blocks': value.f_bfree, 'available_blocks': value.f_bavail,
            'interpretation': 'Context only: concurrent allocation and metadata costs prevent a reclaimed-space claim'}


def _stable(before, after):
    if before != after:
        changes = {name: {key: {'before': before[name][key], 'after': after[name][key]}
                          for key in META_FIELDS if before[name][key] != after[name][key]}
                   for name in before if before[name] != after[name]}
        raise ValueError('Dedupe changed logical file metadata: ' + json.dumps(changes, sort_keys=True))


def _cow(fd, destination, initial, source, events):
    """The only ordinary file write after creation targets this new scratch file."""
    expected = bytearray(initial); expected[0] ^= 1
    identity = _metadata(destination)
    events.append({'step': 'scratch-cow-write', 'destination': 'equal.bin', 'offset': 0, 'bytes': 1,
                   'temporary_permission_change': '0444 ->0600 ->0444',
                   'mtime_ctime_changes_expected_for_this_explicit_write': True})
    os.fchmod(destination, 0o600)
    writer = None
    try:
        writer = os.open('equal.bin', os.O_WRONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_CLOEXEC, dir_fd=fd)
        current = _metadata(writer)
        if any(current[key] != identity[key] for key in ('dev', 'ino', 'nlink', 'uid', 'gid', 'size')):
            raise ValueError('Scratch COW writer is not the independently verified destination inode')
        if os.pwrite(writer, bytes(expected[:1]), 0) != 1: raise OSError('Short scratch COW write')
        os.fsync(writer)
    finally:
        if writer is not None: os.close(writer)
        os.fchmod(destination, 0o444)
    source_body, destination_body = _body(source), _body(destination)
    if (source_body['sha256'] != hashlib.sha256(initial).hexdigest() or
            destination_body['sha256'] != hashlib.sha256(expected).hexdigest() or
            source_body['tail_hex'] != TAIL.hex() or destination_body['tail_hex'] != TAIL.hex()):
        raise ValueError('The scratch COW write changed another file, more than one byte, or the preserved EOF tail')
    source_map, destination_map = _fiemap(source), _fiemap(destination)
    if _physical(source_map, 0)[0] == _physical(destination_map, 0)[0]:
        raise ValueError('Scratch COW write did not separate the written block')
    return {'source': source_body, 'destination': destination_body, 'source_fiemap': source_map,
            'destination_fiemap': destination_map, 'source_hash_unchanged': True,
            'only_requested_destination_byte_changed': True, 'tails_intact': True,
            'written_block_physically_independent': True, 'destination_mode_restored': oct(stat.S_IMODE(os.fstat(destination).st_mode))}


def _exercise(fd, report):
    initial = bytes((index * 73 + 19) % 256 for index in range(PREFIX)) + TAIL
    assert len(TAIL) == 13 and PREFIX % BLOCK == 0
    different = bytearray(initial); different[2 * BLOCK] ^= 1
    report['events'].append({'step': 'create-synthetic-files', 'files': list(FILES), 'bytes_each': len(initial),
                             'aligned_prefix_bytes': PREFIX, 'untouched_eof_tail_bytes': len(TAIL)})
    for name, raw in zip(FILES, (initial, initial, different)): _create(fd, name, raw, MODES[name])
    descriptors = {}
    try:
        for name in FILES: descriptors[name] = _open_readonly(fd, name)
        report['metadata_before'] = {name: _metadata(value) for name, value in descriptors.items()}
        report['readonly_descriptors'] = {name: _readonly_descriptor(value) for name, value in descriptors.items()}
        if len({item['ino'] for item in report['metadata_before'].values()}) != len(FILES):
            raise ValueError('Synthetic files are not independent inodes')
        report['hashes_before'] = {name: _body(value) for name, value in descriptors.items()}
        report['fiemap_before'] = {name: _fiemap(value) for name, value in descriptors.items()}
        report['space_before_dedupe'] = _space(fd)
        source, destination, unequal = (descriptors[name] for name in FILES)
        if _physical(report['fiemap_before']['source.bin'], 0)[0] == _physical(report['fiemap_before']['equal.bin'], 0)[0]:
            raise ValueError('New synthetic copies unexpectedly already share their first block')
        report['events'].append({'step': 'equal-prefix-dedupe', 'state': 'attempted'})
        result = _dedupe(source, destination)
        report['events'][-1].update(state='returned', **result)
        if result['status'] != 0 or result['bytes_deduped'] != PREFIX:
            raise ValueError('Equal synthetic prefix did not report the expected success')
        after_equal = {name: _fiemap(value) for name, value in descriptors.items()}
        report['fiemap_after_equal'] = after_equal
        report['prefix_physical_sharing_verified_bytes'] = _shared_prefix(after_equal['source.bin'], after_equal['equal.bin'])
        report['events'].append({'step': 'different-prefix-dedupe', 'state': 'attempted'})
        result = _dedupe(source, unequal)
        report['events'][-1].update(state='returned', **result)
        if result['status'] != 1 or result['bytes_deduped'] != 0:
            raise ValueError('Different synthetic data was not rejected with FILE_DEDUPE_RANGE_DIFFERS')
        report['fiemap_after_dedupe'] = {name: _fiemap(value) for name, value in descriptors.items()}
        if report['fiemap_after_dedupe']['different.bin'] != report['fiemap_before']['different.bin']:
            raise ValueError('Rejected different-file request changed its physical mapping')
        report['hashes_after_dedupe'] = {name: _body(value) for name, value in descriptors.items()}
        report['metadata_after_dedupe'] = {name: _metadata(value) for name, value in descriptors.items()}
        if report['hashes_before'] != report['hashes_after_dedupe']:
            raise ValueError('Dedupe changed synthetic file bytes or EOF tails')
        _stable(report['metadata_before'], report['metadata_after_dedupe'])
        report['dedupe_metadata_preserved_fields'] = list(META_FIELDS)
        report['space_after_dedupe'] = _space(fd)
        report['cow'] = _cow(fd, destination, initial, source, report['events'])
        if _body(unequal) != report['hashes_before']['different.bin']:
            raise ValueError('The independent different-file control changed during COW')
        _stable({'source.bin': report['metadata_before']['source.bin'], 'different.bin': report['metadata_before']['different.bin']},
                {name: _metadata(descriptors[name]) for name in ('source.bin', 'different.bin')})
        report['metadata_after_cow'] = {name: _metadata(value) for name, value in descriptors.items()}
        report['space_after_cow'] = _space(fd)
        report['status'] = 'PASS_SYNTHETIC_SCRATCH_PROBE'
    finally:
        for value in descriptors.values(): os.close(value)


def _write_report(fd, report):
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    if len(raw) > 128 * 1024: raise ValueError('Bounded scratch report exceeded its fixed size limit')
    output = os.open('report.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=fd)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(output, view)
            if written <= 0: raise OSError('Short scratch report write')
            view = view[written:]
        os.fchmod(output, 0o400); os.fsync(output)
    finally:
        os.close(output)
    os.fsync(fd)


def run_probe(value):
    value = identifier(value)
    environment = _environment()
    fd, path = _probe_directory(value, environment)
    report = {'schema_version': 1, 'scope': 'SYNTHETIC_SCRATCH_ONLY', 'status': 'FAILED', 'probe_id': value,
              'directory': str(path), 'environment': environment, 'started_ns': time.time_ns(), 'events': [],
              'synthetic_file_bytes_total': len(FILES) * (PREFIX + len(TAIL)),
              'logical_sharing_upper_bound_bytes': PREFIX, 'physical_bytes_reclaimed_claimed': False,
              'real_source_data_operated_on': False, 'existing_files_removed': False,
              'all_probe_artifacts_retained': True, 'automatic_real_data_execution_enabled': False,
              'abi': {'FIDEDUPERANGE': hex(FIDEDUPERANGE), 'dedupe_header_bytes': DEDUPE_HEADER.size,
                      'dedupe_destination_bytes': DEDUPE_INFO.size, 'FS_IOC_FIEMAP': hex(FS_IOC_FIEMAP),
                      'fiemap_header_bytes': FIEMAP_HEADER.size, 'fiemap_extent_bytes': FIEMAP_EXTENT.size}}
    try:
        try:
            _exercise(fd, report)
        except BaseException as error:
            report['error'] = {'type': type(error).__name__, 'message': str(error)}
        report['finished_ns'] = time.time_ns()
        _write_report(fd, report)
    finally:
        os.close(fd)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe_id', help='New directory name under the fixed dev QA probe namespace')
    args = parser.parse_args(argv)
    try:
        report = run_probe(args.probe_id)
    except Exception as error:
        print(json.dumps({'status': 'BLOCKED', 'scope': 'SYNTHETIC_SCRATCH_ONLY', 'error': str(error)}))
        return 1
    print(json.dumps({'status': report['status'], 'directory': report['directory'],
                      'report': report['directory'] + '/report.json',
                      'real_source_data_operated_on': False, 'physical_bytes_reclaimed_claimed': False}))
    return 0 if report['status'] == 'PASS_SYNTHETIC_SCRATCH_PROBE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
