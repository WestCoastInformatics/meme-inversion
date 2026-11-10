#!/usr/bin/env python3
"""Local retention fixtures; no dev/production server access."""
from contextlib import contextmanager
import copy
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import tarfile

import archive_retained_source as retain
from replay_process import runtime_lock


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch).resolve() / 'inv';root.mkdir()
        (root / 'sources').mkdir();(root / 'qa').mkdir()
        external = Path(scratch) / 'external';external.mkdir()
        (external / 'unique').write_bytes(b'Never traverse or remove this external data')
        source = root / 'sources/NCI_2026_10D.before-fixture';source.mkdir()
        (source / 'empty').mkdir();(source / 'nested').mkdir()
        (source / 'nested/data').write_bytes(b'Preserve every byte\x00\xff\n')
        (source / 'data').write_bytes(b'Original retained data\n')
        (source / 'external').symlink_to(external, target_is_directory=True)
        (source / 'broken').symlink_to('../missing-target')
        (source / 'nested/data').chmod(0o440);(source / 'data').chmod(0o444)
        os.utime(source / 'data', ns=(1700000000123456789, 1700000000123456789))
        (source / 'nested').chmod(0o550);(source / 'empty').chmod(0o555);source.chmod(0o555)
        with patch.object(retain, 'ROOT', root), patch.object(retain.socket, 'gethostname', return_value='ncias-d3777-c.nci.nih.gov'), patch.object(retain.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='tomcata')):
            try:
                yield root, source, external
            finally:
                # Fixture cleanup only; production retention never recursively removes
                # an unverified tree. Restore write permission without following links.
                for parent, dirs, files in os.walk(root, followlinks=False):
                    Path(parent).chmod(0o700)


def check():
    checks = []

    def good(value, label):
        assert value, label
        checks.append(label)

    def rejects(action, label):
        try:
            action()
        except (ValueError, RuntimeError, OSError, tarfile.TarError):
            checks.append(label)
        else:
            raise AssertionError(label)

    def archive(root, source, name='fixture'):
        return retain.archive(source, root / 'qa/retained-source-archives' / name)

    def args(result):
        return {key: result[key] for key in ('archive', 'receipt')} | {'expected_receipt_sha256': result['receipt_sha256']}

    with fixture() as (root, source, external):
        expected, stamps = retain._tree(source)
        result = archive(root, source)
        good(retain._tree(source) == (expected, stamps), 'Archiving leaves the complete expanded tree unchanged')
        good(result['verification']['entries_verified'] == len(expected['entries']) + 1, 'Every manifest entry and root is verified')
        good(result['verification']['file_bytes_verified'] == sum(x.get('bytes', 0) for x in expected['entries']), 'Every regular-file byte is included in verification')
        good(not result['source_retired'] and source.exists(), 'Default archiving does not retire source data')
        good(retain.verify(**args(result)) == result['verification'], 'Independent verification reopens and verifies the whole archive')
        for name in ('manifest.json', 'archive-receipt.json', 'tree.tar.gz'):
            good(not (Path(result['receipt']).parent / name).stat().st_mode & 0o222, 'Retained artifact is read-only: ' + name)
        rejects(lambda: archive(root, source), 'Namespace collision cannot overwrite prior archive or receipt')
        rejects(lambda: retain.restore(destination=source, **args(result)), 'Restore cannot overwrite an existing tree')
        prior_bytes = {name: (Path(result['receipt']).parent / name).read_bytes() for name in ('manifest.json', 'archive-receipt.json', 'tree.tar.gz')}
        retired = retain.retire(source=source, **args(result))
        good(retired['status'] == 'RETIRED_VERIFIED_EXPANDED_COPY' and not source.exists(), 'Explicit verified retirement removes only expanded source copy')
        good((external / 'unique').read_bytes().startswith(b'Never traverse'), 'Retirement never follows an external directory symlink')
        good(all((Path(result['receipt']).parent / name).read_bytes() == raw for name, raw in prior_bytes.items()), 'Retirement preserves archive, manifest and original receipt bytes')
        restored = retain.restore(destination=source, **args(result))
        good(restored['status'] == 'PASS_RESTORED_TREE_VERIFICATION' and retain._tree(source)[0] == expected, 'Round trip restores exact bytes, modes, nanosecond mtimes, empty directories and symlink topology')
        good((source / 'data').stat().st_mtime_ns == 1700000000123456789, 'Historical file modification time is retained exactly')
        good(source.stat().st_mode & 0o7777 == expected['root_mode'], 'Root directory mode survives retirement and restore')
        good((source / 'broken').is_symlink() and not (source / 'broken').exists(), 'Dangling relative link survives without resolution')
        rejects(lambda: retain.retire(source=source, **args(result)), 'Restored new inode identity cannot silently reuse the previous retirement receipt')
    with fixture() as (root, source, external):
        for name in ('NCI_2026_10D', 'MTH_2026AA', 'NCI_2026_10D.tgz', 'OTHER_2026.before-x'):
            rejects(lambda name=name: retain.archive(root / 'sources' / name, root / 'qa/retained-source-archives/x'), 'Canonical/unreviewed source identity rejected: ' + name)
        rejects(lambda: retain.archive(source / 'nested', root / 'qa/retained-source-archives/x'), 'Nested source paths are rejected')
        linked = root / 'sources/NCI_2026_10D.before-linked';linked.symlink_to(source, target_is_directory=True)
        rejects(lambda: archive(root, linked), 'Symlink source root is rejected')
        rejects(lambda: retain.archive(source, external / 'archive'), 'Destination outside dev retention root is rejected')
        with patch.object(retain.socket, 'gethostname', return_value='ncias-q3793-c'):
            rejects(lambda: archive(root, source), 'Production host is rejected')
        with patch.object(retain.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='other')):
            rejects(lambda: archive(root, source), 'Non-tomcata execution is rejected')
        with runtime_lock(root):
            rejects(lambda: archive(root, source), 'Global runtime lock excludes active worker/retention overlap')
        good(not (root / 'qa/retained-source-archives').exists(), 'Rejected guards/lock operations create no retention artifacts')
    with fixture() as (root, source, external):
        (root / 'sources').rename(root / 'actual-sources')
        (root / 'sources').symlink_to(root / 'actual-sources', target_is_directory=True)
        rejects(lambda: archive(root, source), 'A symlink source ancestor is rejected')
    with fixture() as (root, source, external):
        result = archive(root, source)
        with patch.object(retain, '_sync_dir', side_effect=OSError('fixture durability unavailable')):
            rejects(lambda: retain.retire(source=source, **args(result)), 'Directory durability failure aborts before retirement')
        good((source / 'data').exists() and retain.verify(**args(result))['status'] == 'PASS_FULL_ARCHIVE_VERIFICATION', 'Durability failure leaves source and complete archive intact')
    with fixture() as (root, source, external):
        result = archive(root, source)
        info = (source / 'data').stat()
        os.utime(source / 'data', ns=(info.st_atime_ns + 1000000000, info.st_mtime_ns))
        good(retain.retire(source=source, **args(result))['status'] == 'RETIRED_VERIFIED_EXPANDED_COPY', 'Atime/ctime-only changes do not falsely invalidate unchanged source contents')
    with fixture() as (root, source, external):
        expected = retain._tree(source)
        with patch.object(retain.shutil, 'disk_usage', return_value=SimpleNamespace(free=retain.FREE_DISK_RESERVE)):
            rejects(lambda: archive(root, source), 'Insufficient initial free space stops compression at the fixed reserve')
        namespace = root / 'qa/retained-source-archives/fixture'
        good(retain._tree(source) == expected and not (namespace / 'archive-receipt.json').exists(), 'Initial reserve failure leaves source untouched and creates no verified receipt')
    with fixture() as (root, source, external):
        source.chmod(0o755)
        (source / 'incompressible').write_bytes(os.urandom(3 * retain.DISK_CHECK_INTERVAL))
        (source / 'incompressible').chmod(0o444);source.chmod(0o555)
        expected = retain._tree(source)
        with patch.object(retain.shutil, 'disk_usage', side_effect=[SimpleNamespace(free=100 * 1024 ** 3), SimpleNamespace(free=retain.FREE_DISK_RESERVE)]):
            rejects(lambda: archive(root, source), 'Falling free space is detected during compressed output rather than only at startup')
        namespace = root / 'qa/retained-source-archives/fixture'
        good((namespace / 'tree.tar.gz').exists() and not (namespace / 'archive-receipt.json').exists()
             and retain._tree(source) == expected, 'Mid-compression reserve failure retains partial archive and unchanged expanded source')
    for name in ('archive', 'receipt', 'manifest'):
        with fixture() as (root, source, external):
            result = archive(root, source)
            target = Path(result['archive'] if name == 'archive' else result['receipt'] if name == 'receipt' else Path(result['receipt']).parent / 'manifest.json')
            target.chmod(0o644);target.write_bytes(target.read_bytes() + b'corruption')
            rejects(lambda: retain.retire(source=source, **args(result)), 'Changed ' + name + ' cannot authorize retirement')
            good(source.exists() and (source / 'data').exists(), 'Tampered ' + name + ' leaves expanded data intact')
    with fixture() as (root, source, external):
        result = archive(root, source)
        record = Path(result['receipt']);record.chmod(0o644)
        record.write_text('{"profile":"retained-dev-source-v1","profile":"retained-dev-source-v1"}')
        tampered = args(result);tampered['expected_receipt_sha256'] = retain._file_sha(record)
        rejects(lambda: retain.verify(**tampered), 'Strict receipt JSON rejects duplicate keys even with supplied matching bytes hash')
    with fixture() as (root, source, external):
        original = retain._write_archive
        def mutate(tree, path, manifest):
            original(tree, path, manifest)
            (tree / 'data').chmod(0o644);(tree / 'data').write_bytes(b'Changed during capture\n')
        with patch.object(retain, '_write_archive', side_effect=mutate):
            rejects(lambda: archive(root, source), 'Mutation during archive creation is rejected before a valid receipt exists')
        namespace = root / 'qa/retained-source-archives/fixture'
        good((namespace / 'tree.tar.gz').exists() and not (namespace / 'archive-receipt.json').exists(), 'Failed capture retains its archive and creates no verified receipt')
        good((source / 'data').read_bytes() == b'Changed during capture\n', 'Failed capture never removes newly changed source data')
    with fixture() as (root, source, external):
        result = archive(root, source)
        (source / 'data').chmod(0o644);(source / 'data').write_bytes(b'New unique data after archive\n')
        rejects(lambda: retain.retire(source=source, **args(result)), 'Mutation after capture blocks retirement')
        good((source / 'data').read_bytes().startswith(b'New unique'), 'Rejected retirement preserves data absent from the archive')
    with fixture() as (root, source, external):
        result = archive(root, source)
        original = retain.os.unlink
        count = [0]
        def fail_late(*pos, **kw):
            count[0] += 1
            if count[0] == 2:
                raise OSError('fixture interrupted retirement')
            return original(*pos, **kw)
        with patch.object(retain.os, 'unlink', side_effect=fail_late):
            rejects(lambda: retain.retire(source=source, **args(result)), 'Interrupted partial retirement reports failure')
        good(retain.verify(**args(result))['status'] == 'PASS_FULL_ARCHIVE_VERIFICATION', 'Partial retirement leaves fully verified archive recoverable')
        good(source.stat().st_mode & 0o7777 == 0o555, 'Failed retirement restores surviving root directory mode')
        good(any(Path(result['receipt']).parent.glob('retirement-*-failed.json')), 'Partial retirement retains recovery instructions')
        recovered = root / 'sources/NCI_2026_10D.before-recovered'
        good(retain.restore(destination=recovered, **args(result))['status'] == 'PASS_RESTORED_TREE_VERIFICATION' and source.exists(), 'Partial tree is recoverable into a fresh name without overwriting partial/newer data')
    with fixture() as (root, source, external):
        source.chmod(0o755);os.link(source / 'data', source / 'hardlink')
        rejects(lambda: archive(root, source), 'Hardlink topology is rejected rather than silently duplicated')
    with fixture() as (root, source, external):
        source.chmod(0o755);os.mkfifo(source / 'pipe')
        rejects(lambda: archive(root, source), 'Special files are rejected without opening or blocking')
    with fixture() as (root, source, external):
        expected, _ = retain._tree(source)
        corrupt = root / 'qa/corrupt.tar.gz'
        with tarfile.open(corrupt, 'w:gz') as handle:
            member = tarfile.TarInfo('../escape');member.size = 1
            handle.addfile(member, io.BytesIO(b'x'))
        rejects(lambda: retain._verify_tar(corrupt, expected), 'Traversal or unexpected archive member is rejected')
        corrupt.unlink()
        data = source / 'data';data.chmod(0o644);data.write_bytes(b'X' * data.stat().st_size);data.chmod(0o444)
        retain._write_archive(source, corrupt, expected)
        rejects(lambda: retain._verify_tar(corrupt, expected), 'Full archive verification detects changed per-file bytes independent of aggregate archive identity')
        manifest = copy.deepcopy(expected)
        manifest['entries'].append({'path': 'external/danger', 'type': 'file', 'mode': 0o444, 'mtime_ns': 0, 'bytes': 0, 'sha256': retain.sha(b'')})
        rejects(lambda: retain._manifest(manifest), 'Manifest cannot put a member underneath an external symlink')
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'details': checks}, indent=2))
    return checks


if __name__ == '__main__':
    check()
