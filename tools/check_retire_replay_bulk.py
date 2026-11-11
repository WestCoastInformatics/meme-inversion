#!/usr/bin/env python3
"""Confined destructive-operation fixtures; never contact dev or S3."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from unittest.mock import patch

import archive_retained_source as storage
from check_replay_retention import fixture, put, worker
import replay_retention as retention
import retire_replay_bulk as retirement


@contextmanager
def sample():
    with fixture('MTH') as values:
        root, source, current, control, archive, scan, args = values
        (source / 'src').chmod(0o700)
        for name in ('a-generated.raw', 'z-different-from-official.src'):
            (source / 'src' / name).write_bytes(b'generated scratch\n' * 70000)
            (source / 'src' / name).chmod(0o400)
        (source / 'src/qa').mkdir()
        (source / 'src/qa/large.bin').write_bytes(b'QA\n' * 400000)
        (source / 'src/failure.log').write_bytes(b'log\n' * 300000)
        (source / 'src/outside.link').symlink_to(current / 'src/attributes.src')
        for base, dirs, files in os.walk(source):
            for name in files:
                path = Path(base) / name
                if not path.is_symlink(): path.chmod(path.stat().st_mode & ~0o222)
        for base, dirs, files in os.walk(source, topdown=False):
            Path(base).chmod(Path(base).stat().st_mode & ~0o222)
        (source / 'src').chmod(0o500)
        previous = json.loads((control / 'previous-source-receipt.json').read_text())
        previous['manifest'] = worker.manifest(source)
        previous['receipt_sha256'] = retention.digest({k: v for k, v in previous.items() if k != 'receipt_sha256'})
        put(control / 'previous-source-receipt.json', previous)
        with patch.object(retirement, 'ROOT', root):
            yield values


def check():
    checks = []
    def require(value, label):
        assert value, label
        checks.append(label)
    def rejected(action, label):
        try: action()
        except (ValueError, RuntimeError, FileExistsError, OSError, KeyError, TypeError): checks.append(label)
        else: raise AssertionError(label)

    for name in ('src/qa/large.src', 'src/worker.log', 'src/replay-data/large.src',
                 'src/qa_report', 'src/report.json', 'native/input.raw', '../src/x', 'src/../logs/x',
                 'src/../../MTH_2026AA/src/attributes.src', '/src/a.src', 'src//a.src'):
        require(not retirement.eligible({'path': name, 'type': 'file', 'bytes': 2 ** 21}), 'Protected path excluded: ' + name)
    with sample() as (root, source, current, control, archive, scan, args):
        before = storage._tree(source); current_before = storage._tree(current)
        archive_before = storage._file_sha(archive)
        plan = retirement.plan(args[0]); raw = storage._load(Path(plan['plan_path']))
        require(set(raw['remove']) == {'src/a-generated.raw', 'src/z-different-from-official.src'}, 'Only obsolete regular src bulk is selected, including unique generated differences')
        require(storage._tree(source) == before, 'Planning leaves every source entry unchanged')
        rejected(lambda: retirement.apply(plan['plan_path'], '0' * 64), 'Changed external plan SHA blocks deletion')
        result = retirement.apply(plan['plan_path'], plan['plan_sha256'])
        require(result['status'] == 'RETIRED_TEST_BULK' and result['files_removed'] == 2, 'Actual unlink removes exactly the planned obsolete bulk')
        require(result['original_bulk_restorable'] is False and result['run_acceptance_changed'] is False, 'Discard is explicit and changes no historical acceptance')
        require(storage._tree(current) == current_before, 'Canonical current outputs, links, permissions and timestamps are unchanged')
        require(storage._file_sha(archive) == archive_before, 'Official archive cache is untouched')
        for name in ('src/qa/large.bin', 'src/failure.log', 'src/outside.link', 'manual.txt'):
            require((source / name).exists(), 'Protected record survives: ' + name)
        require((source / 'src').stat().st_mode & 0o777 == 0o500, 'Read-only source directory mode is restored')
        require(not list(root.rglob('tree.tar.gz')), 'No new data archive is created')
        require(retention.inventory(root, current.name)['retired_runs'] == [str(source)], 'Retired test has a distinct lifecycle state and frees the rollback slot')
        rejected(lambda: retirement.apply(plan['plan_path'], plan['plan_sha256']), 'Completed retirement cannot run again')
        (source / 'src').chmod(0o700); (source / 'src/new.src').write_text('unreviewed change')
        require(not retention.inventory(root, current.name)['admission_available'], 'Changed retired tree blocks admission rather than bypassing the limit')
    with sample() as (root, source, current, control, archive, scan, args):
        plan = retirement.plan(args[0]); victim = source / 'src/a-generated.raw'
        victim.chmod(0o600); victim.write_bytes(b'changed after planning')
        rejected(lambda: retirement.apply(plan['plan_path'], plan['plan_sha256']), 'Changed candidate data fails before any deletion')
        require((source / 'src/z-different-from-official.src').exists(), 'Other planned bulk remains after the preflight failure')
    with sample() as (root, source, current, control, archive, scan, args):
        plan = retirement.plan(args[0]); held = root / 'qa/replay-retention/holds'
        held.mkdir(parents=True); put(held / (source.name + '.json'), {'reason': 'active investigation'})
        rejected(lambda: retirement.apply(plan['plan_path'], plan['plan_sha256']), 'A new investigation hold blocks retirement')
    with sample() as (root, source, current, control, archive, scan, args):
        put(control / 'status.json', {'status': 'converting', 'preserved_source': str(source)})
        rejected(lambda: retirement.plan(args[0]), 'An unfinished test is not eligible')
    with sample() as (root, source, current, control, archive, scan, args):
        (current / 'still-needed').symlink_to(source / 'src/a-generated.raw')
        rejected(lambda: retirement.plan(args[0]), 'Incoming source dependency blocks retirement')
    with sample() as (root, source, current, control, archive, scan, args):
        other = root / 'qa/replay-requests/other'; other.mkdir()
        put(other / 'case.lock.json', {'manifest': {'uri': (source / 'src/a-generated.raw').as_uri()}})
        rejected(lambda: retirement.plan(args[0]), 'Another frozen input URI blocks retirement')
    with sample() as (root, source, current, control, archive, scan, args):
        other = root / 'qa/replay-requests/other'; other.mkdir()
        put(other / 'case.lock.json', {'manifest': {'uri': source.parent.as_uri() + '/alias/%2e%2e/' + source.name + '/src/a-generated.raw'}})
        rejected(lambda: retirement.plan(args[0]), 'An encoded parent alias cannot conceal a frozen input dependency')
    with sample() as (root, source, current, control, archive, scan, args):
        plan = retirement.plan(args[0]); original = os.unlink
        def interrupted(name, *a, **kw):
            if name == 'z-different-from-official.src': raise OSError('simulated interruption')
            return original(name, *a, **kw)
        with patch.object(os, 'unlink', side_effect=interrupted):
            rejected(lambda: retirement.apply(plan['plan_path'], plan['plan_sha256']), 'Interrupted deletion is recorded without false completion')
        require(not (source / 'src/a-generated.raw').exists() and (source / 'src/z-different-from-official.src').exists(), 'Partial retirement removes only planned files')
        require(retirement.apply(plan['plan_path'], plan['plan_sha256'])['status'] == 'RETIRED_TEST_BULK', 'The same pinned plan resumes safely after interruption')
    with sample() as (root, source, current, control, archive, scan, args):
        old = retention.plan(*args); retention.compact(old['plan'], old['plan_sha256'])
        old_records = {p: p.read_bytes() for p in (root / 'qa/replay-retention' / source.name).glob('*.json')}
        plan = retirement.plan(args[0]); retirement.apply(plan['plan_path'], plan['plan_sha256'])
        require(all(p.read_bytes() == raw for p, raw in old_records.items()), 'Original lossless compaction plans and receipts remain byte-for-byte unchanged')
    for label in checks: print('PASS', label)
    print(len(checks), 'confined retirement checks passed; no server or S3 access')


if __name__ == '__main__':
    check()
