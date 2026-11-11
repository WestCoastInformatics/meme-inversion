#!/usr/bin/env python3
"""Confined synthetic-file tests for the read-only exact-duplicate planner."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from unittest import mock

import plan_extent_dedup as planner


def environment(root):
    return {'hostname': 'ncias-d3777-c.fixture.invalid', 'account': 'tomcata', 'uid': os.getuid(),
            'kernel': 'SYNTHETIC-FIXTURE', 'machine': 'x86_64', 'filesystem': 'xfs',
            'device': root.stat().st_dev, 'block_bytes': planner.BLOCK, 'mountinfo_sha256': '0' * 64}


def passed_probe(root, evidence, probe_id='scratch-fixture'):
    scratch = planner.scratch
    initial = bytes((index * 73 + 19) % 256 for index in range(scratch.PREFIX)) + scratch.TAIL
    different = bytearray(initial); different[2 * planner.BLOCK] ^= 1
    cow = bytearray(initial); cow[0] ^= 1
    hashes = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'tail_hex': scratch.TAIL.hex()}
              for name, raw in zip(scratch.FILES, (initial, initial, different))}
    metadata = {name: {'dev': evidence['device'], 'ino': number + 100, 'nlink': 1, 'uid': os.getuid(), 'gid': os.getgid(),
                       'mode': oct(scratch.MODES[name]), 'size': len(initial), 'mtime_ns': 1, 'ctime_ns': 2, 'atime_ns': 3}
                for number, name in enumerate(scratch.FILES)}
    mapping = [{'logical': 0, 'physical': 1000000, 'length': scratch.PREFIX, 'flags': scratch.FIEMAP_EXTENT_SHARED}]
    value = {'schema_version': 1, 'scope': 'SYNTHETIC_SCRATCH_ONLY', 'status': 'PASS_SYNTHETIC_SCRATCH_PROBE',
             'probe_id': probe_id, 'directory': str(root / 'qa/replay-storage-probes' / probe_id),
             'real_source_data_operated_on': False, 'automatic_real_data_execution_enabled': False,
             'metadata_before': metadata, 'metadata_after_dedupe': copy.deepcopy(metadata),
             'hashes_before': hashes, 'hashes_after_dedupe': copy.deepcopy(hashes),
             'dedupe_metadata_preserved_fields': list(scratch.META_FIELDS), 'environment': evidence,
             'prefix_physical_sharing_verified_bytes': scratch.PREFIX,
             'readonly_descriptors': {name: {'access': 'O_RDONLY', 'no_follow': True, 'no_atime': True} for name in scratch.FILES},
             'fiemap_after_equal': {'source.bin': mapping, 'equal.bin': copy.deepcopy(mapping)},
             'events': [{'step': 'equal-prefix-dedupe', 'status': 0, 'bytes_deduped': scratch.PREFIX,
                         'state': 'returned', 'requested_bytes': scratch.PREFIX, 'destinations': 1, 'source_offset': 0, 'destination_offset': 0},
                        {'step': 'different-prefix-dedupe', 'status': 1, 'bytes_deduped': 0,
                         'state': 'returned', 'requested_bytes': scratch.PREFIX, 'destinations': 1, 'source_offset': 0, 'destination_offset': 0}],
             'cow': {'source_hash_unchanged': True, 'only_requested_destination_byte_changed': True, 'tails_intact': True,
                     'written_block_physically_independent': True, 'source': hashes['source.bin'],
                     'destination': {'sha256': hashlib.sha256(cow).hexdigest(), 'bytes': len(cow), 'tail_hex': scratch.TAIL.hex()},
                     'destination_mode_restored': '0o444'}}
    path = root / 'qa/replay-storage-probes' / probe_id / 'report.json'; path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value)); path.chmod(0o400)
    return path, value


def data_file(path, raw, mode=0o440):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(mode)
    # Keep read access from changing atime in local platforms lacking Linux
    # O_NOATIME. Real planner execution requires that flag without a fallback.
    stamp = path.stat(); os.utime(path, ns=(max(stamp.st_ctime_ns, stamp.st_mtime_ns) + 10 ** 12, stamp.st_mtime_ns))
    return path


def check():
    passed = []
    def good(value, label):
        assert value, label; passed.append(label)
    def reject(action, label):
        try: action()
        except (ValueError, OSError, KeyError, TypeError, SystemExit): passed.append(label)
        else: raise AssertionError(label)
    for source, version in [('NCI', 'NCI_2026_10D'), ('MTH', 'MTH_2026'), ('MTH', 'MTH_2026AC'), ('MTH', '../MTH_2026AA')]:
        reject(lambda: planner._selection(source, version, 'probe', 'plan'), 'Only the bounded MTH source/version grammar is admitted: ' + version)
    good(planner._selection('MTH', 'MTH_2025AB', 'probe', 'plan')[1] == 'MTH_2025AB' and
         planner._selection('MTH', 'MTH_2028AA', 'probe', 'plan')[1] == 'MTH_2028AA',
         'Distinct AA/AB publications use the same source/version interface without calendar constants')
    for arguments in (['--apply'], ['--root', '/tmp'], ['--target', 'old-data']):
        with contextlib.redirect_stderr(io.StringIO()):
            reject(lambda: planner.main(arguments), 'The planner has no apply, root or existing-file override: ' + repr(arguments))
    for value in ('src/qa/big.src', 'src/replay-output/big.src', 'src/worker.log', 'src/ERROR_LOG', 'src/qa_report', 'src/logs/big', 'src/report.json'):
        good(planner._excluded(value), 'QA/log/replay record is excluded before traversal/hash: ' + value)
    good(not planner._excluded('src/raw3/newsources.raw3'), 'Ordinary large native/intermediate src data is eligible for read-only hashing')
    # Tests use actual new local temporary files. No real XFS environment is
    # asserted and no ioctl is permitted. The deployed no-atime flag is mocked
    # away solely because Darwin does not implement that Linux open flag.
    with tempfile.TemporaryDirectory(prefix='extent-plan-readonly-') as directory:
        root = Path(directory).resolve(); evidence = environment(root)
        with mock.patch.object(planner, 'ROOT', root), mock.patch.object(planner.scratch, 'ROOT', root), \
             mock.patch.object(planner.scratch.os, 'O_NOATIME', 0, create=True), \
             mock.patch.object(planner.scratch, '_environment', return_value=evidence), \
             mock.patch.object(planner.scratch.fcntl, 'ioctl', side_effect=AssertionError('Planner must never issue an ioctl')):
            probe_path, original_probe = passed_probe(root, evidence)
            original = b'X' * planner.MIN_BYTES + b'tail13bytes!!'
            other = b'Y' * planner.MIN_BYTES + b'tail13bytes!!'
            current = root / 'sources/MTH_2026AA'; a = root / 'sources/MTH_2026AA.before-a'; b = root / 'sources/MTH_2026AA.before-b'
            paths = [data_file(current / 'src/current.data', original), data_file(a / 'src/renamed.data', original),
                     data_file(b / 'src/same.data', original), data_file(a / 'src/only-retained.data', other),
                     data_file(b / 'src/other-retained.data', other), data_file(current / 'src/unique.data', b'U' * planner.MIN_BYTES)]
            data_file(a / 'src/writable.data', original, 0o640)
            data_file(a / 'src/qa/large.data', original)
            data_file(a / 'src/worker.log', original)
            data_file(a / 'src/tiny.data', b'tiny')
            data_file(root / 'sources/MTH_2025AB/src/prior.data', original)
            data_file(root / 'sources/MTH_2026AB/src/other-version.data', original)
            held = root / 'sources/MTH_2026AA.before-held'; data_file(held / 'src/held.data', original)
            hold = root / 'qa/replay-retention/holds' / (held.name + '.json'); hold.parent.mkdir(parents=True); hold.write_text('{}')
            dangling = root / 'sources/MTH_2026AA.before-dangling-hold'; data_file(dangling / 'src/held.data', original)
            (hold.parent / (dangling.name + '.json')).symlink_to('missing-hold-record')
            linked = data_file(a / 'src/hardlink-source.data', original); os.link(linked, a / 'src/hardlink-target.data')
            (a / 'src/symlink.data').symlink_to(current / 'src/current.data')
            (a / 'src/linked-directory').symlink_to(current / 'src', target_is_directory=True)
            baseline = {str(path): {'metadata': planner._metadata(path.stat()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in paths}
            roots, files, skipped, names = planner._inventory('MTH_2026AA', evidence)
            good(len(files) == 6 and {item['root'] for item in files} == {current.name, a.name, b.name},
                 'Only eligible current/matching retained src files are enumerated; other publications and held trees are absent')
            reasons = {item['reason'] for item in skipped}
            good({'retention-hold', 'writable-file', 'below-one-MiB', 'qa-log-replay-record',
                  'unowned-linked-or-cross-filesystem-file', 'symlink-or-nonregular'}.issubset(reasons),
                 'Held, writable, small, QA/log, symlink/linked-ancestor and hardlinked files are excluded')
            planner._hash_files(files, roots, evidence)
            groups, pairs = planner._groups(files)
            good(len(pairs) == 3 and all(item['target_role'] == 'retained' for item in pairs) and
                 not any(item['target'].startswith(str(current) + '/') for item in pairs),
                 'Every planned target is retained; current accepted files can only be donors')
            good(sum(item['donor_role'] == 'current' for item in pairs) == 2 and
                 next(item for item in pairs if item['donor_role'] == 'retained')['donor'] == str(a / 'src/only-retained.data'),
                 'Deterministic donors prefer current files, then the first retained path')
            good(len(groups) == 2 and len({item['sha256'] for item in groups}) == 2,
                 'Same-length files with unequal full hashes are never combined into one duplicate group')
            good(sum(item['reason'] == 'retention-hold' for item in skipped) == 2,
                 'A dangling hold-marker symlink still excludes its retained folder')
            good(planner._groups(list(reversed(files))) == (groups, pairs), 'Full-SHA grouping and pair order are independent of discovery order')
            good(all(item['aligned_prefix_bytes'] == planner.MIN_BYTES and item['untouched_eof_tail_bytes'] == 13 for item in pairs),
                 'Pairs cover aligned whole-block prefixes and explicitly leave partial EOF tails untouched')
            planner._finish_inventory('MTH_2026AA', roots, files, names, evidence)
            good(all(item['metadata_before'] == item['metadata_after'] == item['metadata_final'] for item in files),
                 'All ten actual metadata fields stay identical during and after each complete hash')
            good(all(item['sha256'] == baseline[item['path']]['sha256'] for item in files),
                 'Recorded full-file hashes come from actual candidate bytes, not old receipts')
            report, receipt = planner.plan('MTH', 'MTH_2026AA', 'scratch-fixture', 'plan-one')
            good(report['status'] == 'PLAN_ONLY' and report['execute_authorized'] is False and report['ioctls_performed'] is False and
                 report['existing_file_writes_performed'] is False and report['summary']['current_targets'] == 0,
                 'A complete confined plan emits no source writes, ioctls or execution authority')
            good(report['summary']['potential_byte_upper_bound'] == 3 * planner.MIN_BYTES and
                 report['summary']['physical_bytes_reclaimed'] is None,
                 'Duplicate-byte total is an upper bound, never an actual reclaimed-space claim')
            plan_path = Path(receipt['plan_path'])
            good(hashlib.sha256(plan_path.read_bytes()).hexdigest() == receipt['plan_sha256'] and
                 stat.S_IMODE(plan_path.stat().st_mode) == 0o400 and
                 report['probe']['sha256'] == hashlib.sha256(probe_path.read_bytes()).hexdigest(),
                 'New read-only plan and passed scratch evidence are pinned by their complete serialized SHA256 values')
            good(all(planner._metadata(path.stat()) == baseline[str(path)]['metadata'] and
                     hashlib.sha256(path.read_bytes()).hexdigest() == baseline[str(path)]['sha256'] for path in paths),
                 'All eligible source-version bytes and ten metadata fields remain unchanged after planning')
            reject(lambda: planner.plan('MTH', 'MTH_2026AA', 'scratch-fixture', 'plan-one'), 'A plan identifier cannot overwrite any earlier plan/report')
            for label, change in [
                ('nonpassing status', lambda p: p.update(status='FAILED')),
                ('different kernel', lambda p: p['environment'].update(kernel='other-kernel')),
                ('changed preserved metadata', lambda p: p['metadata_after_dedupe']['source.bin'].update(size=0)),
                ('missing readonly descriptor', lambda p: p['readonly_descriptors']['equal.bin'].update(no_atime=False)),
                ('changed synthetic source hash', lambda p: p['hashes_before']['source.bin'].update(sha256='0' * 64)),
                ('unshared physical prefix', lambda p: p['fiemap_after_equal']['equal.bin'][0].update(physical=2000000)),
                ('failed independent COW', lambda p: p['cow'].update(source_hash_unchanged=False)),
            ]:
                changed = copy.deepcopy(original_probe); change(changed)
                probe_path.chmod(0o600); probe_path.write_text(json.dumps(changed)); probe_path.chmod(0o400)
                reject(lambda: planner._probe('scratch-fixture', evidence), 'Probe admission rejects ' + label)
            probe_path.chmod(0o600); probe_path.write_text(json.dumps(original_probe)); probe_path.chmod(0o400)
            roots, files, skipped, names = planner._inventory('MTH_2026AA', evidence)
            changed = Path(files[0]['path']); original_mode = stat.S_IMODE(changed.stat().st_mode)
            changed.chmod(0o600); changed.write_bytes(b'Z' * len(original)); changed.chmod(original_mode)
            reject(lambda: planner._hash_files(files, roots, evidence), 'A same-length body/ctime change after inventory fails the plan closed')
            roots, files, skipped, names = planner._inventory('MTH_2026AA', evidence)
            changed = Path(files[0]['path']); real_read = os.read; performed = []
            def change_during_hash(fd, length):
                block = real_read(fd, length)
                if block and not performed:
                    performed.append(True); mode = stat.S_IMODE(changed.stat().st_mode); changed.chmod(0o600)
                    writer = os.open(changed, os.O_WRONLY)
                    try: os.pwrite(writer, b'Q', 0)
                    finally: os.close(writer); changed.chmod(mode)
                return block
            with mock.patch.object(planner.os, 'read', side_effect=change_during_hash):
                reject(lambda: planner._hash_files(files, roots, evidence), 'A same-size body/ctime change during streaming hash fails the plan closed')
            roots, files, skipped, names = planner._inventory('MTH_2026AA', evidence)
            planner._hash_files(files, roots, evidence)
            later_hold = root / 'qa/replay-retention/holds' / (a.name + '.json'); later_hold.write_text('{}')
            reject(lambda: planner._finish_inventory('MTH_2026AA', roots, files, names, evidence), 'A retention hold appearing during planning invalidates all proposed pairs')
            later_hold.unlink()
            with mock.patch.object(planner, 'MAX_FILES', 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Eligible file-count bound is enforced before full hashing')
            with mock.patch.object(planner, 'MAX_TOTAL_BYTES', 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Total hash-byte bound is enforced before full hashing')
            with mock.patch.object(planner, 'MAX_FILE_BYTES', planner.MIN_BYTES - 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Per-file length bound fails closed')
            with mock.patch.object(planner, 'MAX_ROOTS', 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Matching-root count is bounded before any full file hash')
            with mock.patch.object(planner, 'MAX_SOURCE_ENTRIES', 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Source-directory enumeration is bounded while streaming names')
            with mock.patch.object(planner, 'MAX_ENTRIES', 1):
                reject(lambda: planner._inventory('MTH_2026AA', evidence), 'Nested source enumeration is bounded before allocating an unbounded name list')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values: print('PASS', value)
    print(len(values), 'confined read-only extent-plan checks passed; no native filesystem-sharing ioctl executed')
