#!/usr/bin/env python3
"""Confined guard/ABI/extent tests; never issue a real dedupe/FIEMAP ioctl."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from unittest import mock

import probe_extent_dedup as probe


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def reject(action, label):
        try: action()
        except (ValueError, OSError, SystemExit): passed.append(label)
        else: raise AssertionError(label)
    good((probe.DEDUPE_HEADER.size, probe.DEDUPE_INFO.size, probe.FIEMAP_HEADER.size, probe.FIEMAP_EXTENT.size) == (24, 32, 32, 56),
         'Reviewed Linux ABI uses explicit24/32/32/56byte layouts')
    good(probe.FIDEDUPERANGE == 0xc0189436 and probe.FS_IOC_FIEMAP == 0xc020660b,
         'Reviewed ioctl encodings use fixed Linux x86_64 structure sizes')
    good(probe.PREFIX == 65536 and len(probe.TAIL) == 13 and len(probe.FILES) == 3,
         'Synthetic payload is bounded to three64KiB-prefix-plus13byte-tail files')
    for value in ('../old', '/tmp/source', 'a/b', '..', '.', '', 'x' * 65, 'has space', 'x\nfile'):
        reject(lambda: probe.identifier(value), 'Path/noncanonical probe identifier is rejected: ' + repr(value))
    good(probe.identifier('scratch-only-20261111') == 'scratch-only-20261111', 'One bounded new probe identifier is accepted')
    with mock.patch.object(probe.platform, 'system', return_value='Darwin'):
        reject(probe._environment, 'Non-Linux environment is rejected before opening the fixed root')
    with mock.patch.object(probe.platform, 'system', return_value='Linux'), mock.patch.object(probe.platform, 'machine', return_value='x86_64'), mock.patch.object(probe.socket, 'gethostname', return_value='production-host'):
        reject(probe._environment, 'Any hostname other than the named dev server is rejected')
    with mock.patch.object(probe, '_environment', side_effect=ValueError('blocked test environment')), mock.patch.object(probe, '_probe_directory') as created:
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = probe.main(['confined-test'])
        good(result == 1 and json.loads(output.getvalue())['status'] == 'BLOCKED' and not created.called,
             'Failed environment guard cannot create any probe directory')
    for arguments in (['--source', 'old-file'], ['--root', '/tmp'], ['one', 'existing-file']):
        with contextlib.redirect_stderr(io.StringIO()):
            reject(lambda: probe.main(arguments), 'CLI has no existing-file, path or directory override: ' + repr(arguments))
    with mock.patch.object(probe.os, 'O_NOATIME', 0x40000, create=True):
        flags = probe._read_flags()
        good(flags & os.O_ACCMODE == os.O_RDONLY and flags & os.O_NOFOLLOW and flags & 0x40000,
             'All probe input descriptors request read-only/no-follow/no-atime access')
    base = {key: index for index, key in enumerate(probe.META_FIELDS)}
    good(probe._stable({'source.bin': base}, {'source.bin': copy.deepcopy(base)}) is None,
         'The metadata guard accepts an exact full identity/timestamp match')
    for field in probe.META_FIELDS:
        changed = copy.deepcopy(base); changed[field] += 1
        reject(lambda: probe._stable({'source.bin': base}, {'source.bin': changed}), 'Dedupe metadata guard rejects changed ' + field)
    def extent(logical=0, physical=1000000, length=probe.PREFIX, flags=probe.FIEMAP_EXTENT_SHARED):
        return {'logical': logical, 'physical': physical, 'length': length, 'flags': flags}
    source = [extent()]
    split = [extent(length=probe.BLOCK), extent(probe.BLOCK, 1000000 + probe.BLOCK, probe.PREFIX - probe.BLOCK)]
    good(probe._shared_prefix(source, split) == probe.PREFIX, 'Physical prefix equality handles independently split extent boundaries')
    for label, changed in [
        ('different physical data', [extent(physical=2000000)]),
        ('missing SHARED flag', [extent(flags=0)]),
        ('a hole', [extent(logical=probe.BLOCK, length=probe.PREFIX - probe.BLOCK)]),
        ('incomplete mapped prefix', [extent(length=probe.PREFIX - 1)]),
    ]:
        reject(lambda: probe._shared_prefix(source, changed), 'Full-prefix mapping verification rejects ' + label)
    calls = []
    def dedupe_reply(source_fd, operation, request, mutate):
        calls.append((source_fd, operation, mutate))
        assert probe.DEDUPE_HEADER.unpack_from(request) == (0, probe.PREFIX, 1, 0, 0)
        assert probe.DEDUPE_INFO.unpack_from(request, 24) == (9, 0, 0, 0, 0)
        probe.DEDUPE_INFO.pack_into(request, 24, 9, 0, probe.PREFIX, 0, 0)
    with mock.patch.object(probe.fcntl, 'ioctl', side_effect=dedupe_reply):
        result = probe._dedupe(8, 9)
    good(calls == [(8, probe.FIDEDUPERANGE, True)] and result['status'] == 0 and
         result['bytes_deduped'] == probe.PREFIX and not result['physical_bytes_reclaimed_claimed'],
         'One fixed equal-prefix request has one destination and makes no physical-reclaim claim')
    def malformed_reply(source_fd, operation, request, mutate):
        probe.DEDUPE_INFO.pack_into(request, 24, 123, 0, probe.PREFIX, 0, 0)
    with mock.patch.object(probe.fcntl, 'ioctl', side_effect=malformed_reply):
        reject(lambda: probe._dedupe(8, 9), 'Changed kernel-response destination identity is rejected')
    def fiemap_reply(fd, operation, request, mutate):
        assert operation == probe.FS_IOC_FIEMAP
        assert probe.FIEMAP_HEADER.unpack_from(request) == (0, probe.PREFIX, probe.FIEMAP_FLAG_SYNC, 0, probe.EXTENT_CAPACITY, 0)
        probe.FIEMAP_HEADER.pack_into(request, 0, 0, probe.PREFIX, probe.FIEMAP_FLAG_SYNC, 1, probe.EXTENT_CAPACITY, 0)
        probe.FIEMAP_EXTENT.pack_into(request, 32, 0, 1000000, probe.PREFIX, 0, 0, probe.FIEMAP_EXTENT_SHARED, 0, 0, 0)
    with mock.patch.object(probe.fcntl, 'ioctl', side_effect=fiemap_reply):
        good(probe._fiemap(8) == source, 'Bounded FIEMAP parser validates the entire synthetic prefix')
    for unsafe in (0x2, 0x4, 0x8, 0x80, 0x100, 0x200, 0x400, 0x800):
        def bad_fiemap(fd, operation, request, mutate):
            fiemap_reply(fd, operation, request, mutate)
            probe.FIEMAP_EXTENT.pack_into(request, 32, 0, 1000000, probe.PREFIX, 0, 0, unsafe, 0, 0, 0)
        with mock.patch.object(probe.fcntl, 'ioctl', side_effect=bad_fiemap):
            reject(lambda: probe._fiemap(8), 'Unsafe/unknown FIEMAP data representation is rejected: ' + hex(unsafe))
    with tempfile.TemporaryDirectory(prefix='extent-probe-guards-') as directory:
        root = Path(directory).resolve()
        with mock.patch.object(probe, 'ROOT', root):
            environment = {'device': root.stat().st_dev}
            fd, path = probe._probe_directory('new-synthetic-only', environment)
            try:
                good(path == root / 'qa/replay-storage-probes/new-synthetic-only' and not list(path.iterdir()),
                     'Only a new child of the fixed confined QA namespace is created')
                reject(lambda: probe._probe_directory('new-synthetic-only', environment), 'An existing probe directory can never be reused')
                raw = b'X' * probe.PREFIX + probe.TAIL
                probe._create(fd, 'source.bin', raw, 0o440)
                good((path / 'source.bin').read_bytes() == raw and stat.S_IMODE((path / 'source.bin').stat().st_mode) == 0o440,
                     'A new bounded synthetic inode is written once then made read-only')
                reject(lambda: probe._create(fd, 'source.bin', b'Y' * len(raw), 0o440), 'Existing probe-file content cannot be overwritten during creation')
                good((path / 'source.bin').read_bytes() == raw, 'Rejected reuse leaves existing scratch bytes untouched')
                reject(lambda: probe._create(fd, 'real-file', raw, 0o440), 'Creation rejects every filename outside the three literal scratch names')
                reject(lambda: probe._create(fd, 'equal.bin', raw + b'X', 0o444), 'Creation rejects a payload beyond the fixed synthetic size')
                (path / 'equal.bin').symlink_to('source.bin')
                # Local platforms may lack Linux O_NOATIME. This check tests
                # path/descriptor safety only; no deployed timestamp claim.
                with mock.patch.object(probe.os, 'O_NOATIME', 0, create=True):
                    reject(lambda: probe._open_readonly(fd, 'equal.bin'), 'A symlink cannot redirect a scratch descriptor to another inode')
                probe._write_report(fd, {'scope': 'CONFINED_TEST_ONLY', 'no_kernel_ioctls_executed': True})
                good(stat.S_IMODE((path / 'report.json').stat().st_mode) == 0o400 and
                     json.loads((path / 'report.json').read_text())['no_kernel_ioctls_executed'],
                     'Probe reports are retained as new read-only artifacts')
                reject(lambda: probe._write_report(fd, {}), 'An existing probe report can never be overwritten')
            finally:
                os.close(fd)
    with tempfile.TemporaryDirectory(prefix='extent-probe-cow-code-') as directory:
        root = Path(directory).resolve(); fd = os.open(root, probe._directory_flags()); descriptors = {}
        try:
            raw = bytes((index * 73 + 19) % 256 for index in range(probe.PREFIX)) + probe.TAIL
            for name in probe.FILES: probe._create(fd, name, raw, probe.MODES[name])
            with mock.patch.object(probe.os, 'O_NOATIME', 0, create=True):
                for name in probe.FILES: descriptors[name] = probe._open_readonly(fd, name)
                # This tests the confined write/hash/tail/permission protocol.
                # Synthetic map replies are not evidence of actual kernel COW.
                maps = [[extent()], [extent(physical=2000000)]]
                events = []
                with mock.patch.object(probe, '_fiemap', side_effect=maps):
                    result = probe._cow(fd, descriptors['equal.bin'], raw, descriptors['source.bin'], events)
            good(result['source_hash_unchanged'] and (root / 'source.bin').read_bytes() == raw and
                 (root / 'different.bin').read_bytes() == raw,
                 'Confined COW-write code leaves both source and independent control bytes untouched')
            expected = bytearray(raw); expected[0] ^= 1
            good((root / 'equal.bin').read_bytes() == expected and result['tails_intact'],
                 'Confined COW-write code changes exactly its requested destination byte and preserves EOF tails')
            good(stat.S_IMODE((root / 'equal.bin').stat().st_mode) == 0o444 and events[0]['destination'] == 'equal.bin',
                 'Only the fixed scratch destination receives a temporary permission change, then returns to0444')
        finally:
            for value in descriptors.values(): os.close(value)
            os.close(fd)
    with tempfile.TemporaryDirectory(prefix='extent-probe-symlink-') as directory:
        root = Path(directory).resolve(); other = root / 'other'; other.mkdir()
        (root / 'qa').symlink_to(other, target_is_directory=True)
        with mock.patch.object(probe, 'ROOT', root):
            reject(lambda: probe._probe_directory('new', {'device': root.stat().st_dev}), 'A symlinked QA ancestor cannot redirect probe creation')
        good(not list(other.iterdir()), 'Rejected QA symlink creates nothing in its target')
    with tempfile.TemporaryDirectory(prefix='extent-probe-parent-') as directory:
        root = Path(directory).resolve(); parent = root / 'qa/replay-storage-probes'; parent.mkdir(parents=True); parent.chmod(0o777)
        with mock.patch.object(probe, 'ROOT', root):
            reject(lambda: probe._probe_directory('new', {'device': root.stat().st_dev}), 'A probe parent writable by other accounts is rejected')
        good(not list(parent.iterdir()), 'Rejected shared-writable parent contains no new probe directory')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values: print('PASS', value)
    print(len(values), 'confined extent-probe checks passed; no kernel dedupe/FIEMAP ioctl executed')
