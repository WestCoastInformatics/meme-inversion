#!/usr/bin/env python3
"""Confined mutation/recovery checks for the independent post-cleanup reader."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import tempfile

import archive_retained_source as storage

spec = importlib.util.spec_from_file_location('retention_postcheck', Path(__file__).parent / 'evidence/verify_retention_compaction_20261111.py')
verifier = importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary).resolve()
        (root / 'kept').mkdir();(root / 'empty').mkdir()
        (root / 'kept/data').write_bytes(b'keep this unique result\n')
        (root / 'duplicate').write_bytes(b'archive-backed duplicate\n')
        (root / 'prior-link').symlink_to('../required-prior-data')
        manifest, capture = storage._tree(root)
        plan = {'manifest': manifest, 'source_capture': capture, 'remove': {'duplicate': 'VERSION/duplicate'},
                'retained_unique_bytes': (root / 'kept/data').stat().st_size}
        (root / 'duplicate').unlink()
        _, remaining = storage._tree(root)
        yield root, plan, {'remaining_capture': remaining}


def check():
    passed = []
    def rejected(action, label):
        try:action()
        except (RuntimeError, ValueError, FileNotFoundError):passed.append(label)
        else:raise AssertionError(label)
    with fixture() as (root, plan, complete):
        report = verifier.retained_tree(root, plan, complete)
        assert report['regular_files_verified'] == 1 and report['entries_verified'] == 4
        passed.append('Independent reader accepts exactly the planned omission, unique data, directories and external link')
    changes = [
        ('changed file contents', lambda root, plan, complete: (root / 'kept/data').write_bytes(b'changed content')),
        ('unplanned missing file', lambda root, plan, complete: (root / 'kept/data').unlink()),
        ('unplanned added file', lambda root, plan, complete: (root / 'extra').write_bytes(b'extra')),
        ('planned duplicate still present', lambda root, plan, complete: (root / 'duplicate').write_bytes(b'archive-backed duplicate\n')),
        ('changed file permissions', lambda root, plan, complete: (root / 'kept/data').chmod(0o400)),
        ('changed file timestamp', lambda root, plan, complete: os.utime(root / 'kept/data', ns=(1, 1))),
        ('changed directory permissions', lambda root, plan, complete: (root / 'kept').chmod(0o500)),
        ('changed completion capture', lambda root, plan, complete: complete['remaining_capture'].pop('kept/data')),
        ('incorrect retained byte total', lambda root, plan, complete: plan.update(retained_unique_bytes=0)),
    ]
    for label, change in changes:
        with fixture() as (root, plan, complete):
            try:
                change(root, plan, complete)
                rejected(lambda: verifier.retained_tree(root, plan, complete), 'Independent reader rejects ' + label)
            finally:
                (root / 'kept').chmod(0o700)
    with fixture() as (root, plan, complete):
        (root / 'prior-link').unlink();(root / 'prior-link').symlink_to('../different-prior')
        rejected(lambda: verifier.retained_tree(root, plan, complete), 'Independent reader rejects changed prior link target')
    with fixture() as (root, plan, complete):
        (root / 'linked-file').symlink_to(root / 'kept/data')
        rejected(lambda: verifier.checksum(root / 'linked-file'), 'Hash reader refuses a linked file')
        (root / 'linked-directory').symlink_to(root / 'kept')
        rejected(lambda: verifier.checksum(root / 'linked-directory/data'), 'Hash reader refuses a linked ancestor')
    return passed


if __name__ == '__main__':
    checks = check()
    for label in checks:print('PASS', label)
    print(len(checks), 'independent retention postcheck checks passed')
