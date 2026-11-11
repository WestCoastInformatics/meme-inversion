#!/usr/bin/env python3
"""Discard obsolete test bulk, preserving small records and live dependencies.

This deliberately differs from lossless archive compaction: unneeded generated
files can be discarded even when their bytes differ from the official archive.
Only terminal common-run .before- folders and regular src files >=1 MiB qualify.
An externally pinned plan is required; current releases, inputs, QA and logs are
never deletion targets. The caller must have authorization to retire the test.
"""
from pathlib import Path, PurePosixPath
import os
import stat

import archive_retained_source as storage
import replay_retention as retention
from replay_process import runtime_lock

ROOT = storage.ROOT
POLICY = 'dev-test-bulk-retirement-v1'
MINIMUM_BYTES = 1024 ** 2


def eligible(item):
    relative = PurePosixPath(item['path'])
    if relative.is_absolute() or '..' in relative.parts or str(relative) != item['path']:
        return False
    parts = relative.parts
    if item['type'] != 'file' or item['bytes'] < MINIMUM_BYTES or len(parts) < 2 or parts[0] != 'src':
        return False
    for part in parts:
        value = part.lower()
        if ('replay' in value or 'log' in value or value in ('qa', 'test', 'tests') or
                value.startswith(('qa_', 'qa.')) or 'checklist' in value or
                value.endswith(('.json', '.out', '.err'))):
            return False
    return True


def namespace(source, create=False):
    parent = ROOT / 'qa/replay-retirement'
    if create:
        parent.mkdir(exist_ok=True)
    storage._safe_directory(parent)
    target = parent / source.name
    if create:
        target.mkdir()  # Never replace a previous plan, including failed attempts.
    storage._safe_directory(target)
    return target


def context(run_id):
    source, previous, archive, pins, lock, state, control = retention._preservation_context(run_id)
    # Other retained common locks may consume the tree too, even without links.
    for folder in (ROOT / 'qa/replay-requests').iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        path = folder / 'case.lock.json'
        if path.is_file() and not path.is_symlink():
            other = storage._load(path)
            def visit(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key not in ('modules_b64', 'code_files', 'runtime_files'):
                            visit(child)
                elif isinstance(value, list):
                    for child in value: visit(child)
                elif isinstance(value, str):
                    from urllib.parse import unquote, urlsplit
                    if value.startswith('file:'):
                        locator = os.path.normpath(unquote(urlsplit(value).path))
                    elif value.startswith('/'):
                        locator = os.path.normpath(value)
                    else:
                        return
                    if locator == str(source) or locator.startswith(str(source) + '/'):
                        raise RuntimeError('Another common lock depends on this retained tree')
            visit(other.get('case', other.get('manifest', {})))
    return source, pins


def plan(run_id):
    storage.guard()
    with runtime_lock(ROOT):
        retention._idle()
        source, pins = context(run_id)
        manifest, capture = storage._tree(source)
        remove = {item['path']: {'bytes': item['bytes'], 'sha256': item['sha256']}
                  for item in manifest['entries'] if eligible(item)}
        report = {'policy': POLICY, 'status': 'PLANNED', 'run_id': run_id,
                  'source': str(source), 'manifest': manifest, 'source_capture': capture,
                  'remove': remove, 'evidence': pins, 'minimum_bulk_bytes': MINIMUM_BYTES,
                  'bulk_bytes': sum(item['bytes'] for item in remove.values()),
                  'retained_bytes': sum(item['bytes'] for item in manifest['entries']
                                        if item['type'] == 'file' and item['path'] not in remove),
                  'disposition': 'DISCARD_OBSOLETE_TEST_BULK; NOT_LOSSLESS_COMPACTION',
                  'original_bulk_restorable': False, 'run_acceptance_changed': False,
                  'new_archive_created': False, 's3_upload': False,
                  'tool_sha256': storage._file_sha(Path(__file__))}
        target = namespace(source, create=True)
        checksum = storage._save(target / 'plan.json', report)
        return {'status': 'PLANNED', 'run_id': run_id, 'source': str(source),
                'plan_path': str(target / 'plan.json'), 'plan_sha256': checksum,
                'files_to_remove': len(remove), 'bulk_bytes': report['bulk_bytes'],
                'retained_bytes': report['retained_bytes'], 'original_bulk_restorable': False}


def _load(plan_path, plan_sha256):
    path = Path(plan_path)
    report, pin = retention._record(path)
    if pin['sha256'] != plan_sha256 or report.get('policy') != POLICY or report.get('status') != 'PLANNED':
        raise ValueError('Retirement plan identity changed')
    source, pins = context(report['run_id'])
    if report['source'] != str(source) or path != namespace(source) / 'plan.json' or pins != report['evidence']:
        raise ValueError('Retirement context changed')
    storage._manifest(report['manifest'], capability_source=source)
    if storage._file_sha(Path(__file__)) != report['tool_sha256']:
        raise ValueError('Retirement apparatus changed')
    expected = {item['path']: {'bytes': item['bytes'], 'sha256': item['sha256']}
                for item in report['manifest']['entries'] if eligible(item)}
    if report['remove'] != expected:
        raise ValueError('Plan contains an ineligible retirement target')
    return source, report, path.parent


def apply(plan_path, plan_sha256):
    storage.guard()
    with runtime_lock(ROOT):
        retention._idle()
        source, report, target = _load(plan_path, plan_sha256)
        if (target / 'complete.json').exists():
            raise FileExistsError('Retirement already completed')
        started = target / 'started.json'
        if started.exists():
            if storage._load(started).get('plan_sha256') != plan_sha256:
                raise ValueError('Another plan owns this retirement')
            retention._check_remaining(source, report, allow_incomplete_modes=True)
        elif storage._tree(source) != (report['manifest'], report['source_capture']):
            raise RuntimeError('Obsolete test tree changed since planning')
        before = os.statvfs(ROOT)
        if not started.exists():
            storage._save(started, {'status': 'RETIRING_OBSOLETE_TEST_BULK', 'plan_sha256': plan_sha256})
        rootfd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name in sorted(report['remove']):
                relative = PurePosixPath(name)
                with storage._directory_fd(rootfd, str(relative.parent)) as parent:
                    info = os.fstat(parent)
                    expected = report['source_capture'][str(relative.parent)]
                    if [info.st_dev, info.st_ino] != expected[:2]:
                        raise RuntimeError('Retirement parent was replaced')
                    os.fchmod(parent, stat.S_IMODE(info.st_mode) | 0o700)
                    try:
                        try: current = os.stat(relative.name, dir_fd=parent, follow_symlinks=False)
                        except FileNotFoundError: continue
                        if not stat.S_ISREG(current.st_mode) or storage._stamp(current) != report['source_capture'][name]:
                            raise RuntimeError('Retirement target changed')
                        os.unlink(relative.name, dir_fd=parent)
                        os.fsync(parent)
                    finally:
                        os.fchmod(parent, expected[4])
        finally:
            os.close(rootfd)
        actual, capture = retention._check_remaining(source, report)
        if set(report['remove']) & {item['path'] for item in actual['entries']}:
            raise RuntimeError('Retirement incomplete')
        after = os.statvfs(ROOT)
        result = {'status': 'RETIRED_TEST_BULK', 'policy': POLICY, 'source': str(source),
                  'run_id': report['run_id'], 'plan_path': str(Path(plan_path)), 'plan_sha256': plan_sha256,
                  'files_removed': len(report['remove']), 'logical_bytes_removed': report['bulk_bytes'],
                  'retained_bytes': report['retained_bytes'], 'remaining_capture': capture,
                  'free_bytes_before': before.f_bavail * before.f_frsize,
                  'free_bytes_after': after.f_bavail * after.f_frsize,
                  'run_acceptance_changed': False, 'original_bulk_restorable': False,
                  'new_archive_created': False, 's3_upload': False}
        storage._save(target / 'complete.json', result)
        # Distinct from the old lossless completion. Never relabel old receipts.
        old_namespace = retention._namespace(source, create=True)
        storage._save(old_namespace / 'retirement.json', result)
        return result
