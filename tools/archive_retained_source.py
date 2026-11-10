#!/usr/bin/env python3
"""Reversibly retain expanded historical dev test trees; never archives current sources."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import socket
import stat
import tarfile
import uuid

from replay_process import runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
VERSIONS = ('NCI_2026_10D', 'SNOMEDCT_US_2026_09_01', 'MTH_2026AA', 'MDR_29_1', 'RADLEX_4_3')
NAME = re.compile('(?:' + '|'.join(re.escape(x) for x in VERSIONS) + r')\.before-[A-Za-z0-9][A-Za-z0-9._-]{0,150}')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hash_stream(handle):
    result = hashlib.sha256()
    for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
        result.update(block)
    return result.hexdigest()


def _file_sha(path):
    with _open_file(path) as handle:
        return _hash_stream(handle)


@contextmanager
def _open_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('A regular file is required: ' + str(path))
        yield handle


def _load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    with _open_file(path) as handle:
        return json.load(handle, object_pairs_hook=unique,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))


def _save(path, value):
    raw = canonical(value) + b'\n'
    with path.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o444)
    with _open_file(path) as handle:
        os.fsync(handle.fileno())
    _sync_dir(path.parent)
    return sha(raw)


def _sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_directory(path):
    if not path.is_dir() or path.is_symlink() or path.resolve() != path:
        raise ValueError('Directory or ancestor is absent/linked: ' + str(path))


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Retained-tree operations require tomcata on ncias-d3777-c')
    for path in (ROOT, ROOT / 'sources', ROOT / 'qa'):
        _safe_directory(path)


def _source(source, exists=True):
    source = Path(source)
    if source.parent != ROOT / 'sources' or not NAME.fullmatch(source.name):
        raise ValueError('Only explicit reviewed source-version .before- trees are allowed')
    _safe_directory(source.parent)
    if exists:
        _safe_directory(source)
    elif source.exists() or source.is_symlink():
        raise FileExistsError('Restore destination already exists')
    return source


def _archives(create=False):
    parent = ROOT / 'qa' / 'retained-source-archives'
    if create:
        try:
            parent.mkdir(mode=0o755)
            _sync_dir(parent.parent)
        except FileExistsError:
            pass
    _safe_directory(parent)
    return parent


def _namespace(destination, create=False):
    path = Path(destination)
    if path.parent != ROOT / 'qa/retained-source-archives' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,150}', path.name):
        raise ValueError('A direct unique retained-source-archives namespace is required')
    _archives(create)
    if create:
        path.mkdir(mode=0o755)
        _sync_dir(path.parent)
    _safe_directory(path)
    return path


def _stamp(info):
    # Reading can change atime; chmod can change ctime without changing content.
    return [info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size, stat.S_IMODE(info.st_mode)]


def _relative(name):
    path = PurePosixPath(name)
    if not isinstance(name, str) or not path.parts or path.is_absolute() or '..' in path.parts or str(path) != name:
        raise ValueError('Unsafe retained-tree member path')
    return path


def _tree(source):
    """Capture through no-follow directory descriptors, never through link targets."""
    entries, stamps = [], {}
    rootfd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_stat = os.fstat(rootfd)
        if _stamp(source.lstat()) != _stamp(root_stat):
            raise RuntimeError('Source root changed before capture')
        stamps['.'] = _stamp(root_stat)

        def walk(directory_fd, prefix):
            for leaf in sorted(os.listdir(directory_fd)):
                name = (prefix / leaf).as_posix()
                _relative(name)
                info = os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)
                record = {'path': name, 'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns}
                stamps[name] = _stamp(info)
                if stat.S_ISLNK(info.st_mode):
                    record.update(type='symlink', target=os.readlink(leaf, dir_fd=directory_fd))
                elif stat.S_ISDIR(info.st_mode):
                    record.update(type='directory')
                    child = os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
                    try:
                        if _stamp(os.fstat(child)) != _stamp(info):
                            raise RuntimeError('Source directory changed before capture')
                        walk(child, PurePosixPath(name))
                        if _stamp(os.fstat(child)) != _stamp(info):
                            raise RuntimeError('Source directory changed during capture')
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    if info.st_nlink != 1:
                        raise ValueError('Hardlinked files require a separately reviewed retention contract')
                    descriptor = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
                    with os.fdopen(descriptor, 'rb') as handle:
                        if _stamp(os.fstat(handle.fileno())) != _stamp(info):
                            raise RuntimeError('Source file changed before capture')
                        checksum = _hash_stream(handle)
                        if _stamp(os.fstat(handle.fileno())) != _stamp(info):
                            raise RuntimeError('Source file changed during capture')
                    record.update(type='file', bytes=info.st_size, sha256=checksum)
                else:
                    raise ValueError('Unsupported retained-tree special file')
                entries.append(record)
                if _stamp(os.stat(leaf, dir_fd=directory_fd, follow_symlinks=False)) != stamps[name]:
                    raise RuntimeError('Source entry changed during capture')
        walk(rootfd, PurePosixPath('.'))
        if _stamp(os.fstat(rootfd)) != stamps['.'] or _stamp(source.lstat()) != stamps['.']:
            raise RuntimeError('Source root changed during capture')
        return {'schema_version': 1, 'source_name': source.name, 'root_mode': stat.S_IMODE(root_stat.st_mode),
                'root_mtime_ns': root_stat.st_mtime_ns, 'entries': sorted(entries, key=lambda item: item['path'])}, stamps
    finally:
        os.close(rootfd)


def _manifest(manifest):
    if set(manifest) != {'schema_version', 'source_name', 'root_mode', 'root_mtime_ns', 'entries'} or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or not NAME.fullmatch(manifest['source_name']):
        raise ValueError('Unrecognized retained manifest')
    if type(manifest['root_mode']) is not int or not 0 <= manifest['root_mode'] <= 0o7777 or type(manifest['root_mtime_ns']) is not int or not isinstance(manifest['entries'], list):
        raise ValueError('Invalid retained manifest root/members')
    result = {}
    for item in manifest['entries']:
        name = item['path'];_relative(name)
        fields = {'path', 'mode', 'mtime_ns', 'type'}
        if item['type'] == 'file':
            fields |= {'bytes', 'sha256'}
            if type(item['bytes']) is not int or item['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                raise ValueError('Invalid retained file identity')
        elif item['type'] == 'symlink':
            fields |= {'target'}
            if not isinstance(item['target'], str) or '\x00' in item['target']:
                raise ValueError('Invalid retained link target')
        elif item['type'] != 'directory':
            raise ValueError('Unsupported retained member type')
        if set(item) != fields or name == '.' or name in result or type(item['mode']) is not int or not 0 <= item['mode'] <= 0o7777 or type(item['mtime_ns']) is not int:
            raise ValueError('Invalid or duplicate retained member')
        result[name] = item
    for name in result:
        for ancestor in PurePosixPath(name).parents:
            if str(ancestor) != '.' and (str(ancestor) not in result or result[str(ancestor)]['type'] != 'directory'):
                raise ValueError('Retained member has a non-directory or missing ancestor')
    return result


def _verify_tar(archive_path, manifest):
    expected = _manifest(manifest)
    expected['.'] = {'path': '.', 'type': 'directory', 'mode': manifest['root_mode'], 'mtime_ns': manifest['root_mtime_ns']}
    seen, total, files = set(), 0, 0
    with _open_file(archive_path) as raw, tarfile.open(fileobj=raw, mode='r:gz') as archive:
        for member in archive:
            name = member.name
            if name not in expected or name in seen:
                raise ValueError('Unexpected or duplicate archive member: ' + name)
            item = expected[name]
            if member.mode != item['mode'] or (member.isdir(), member.isfile(), member.issym()) != tuple(item['type'] == value for value in ('directory', 'file', 'symlink')):
                raise ValueError('Archive member type/mode differs: ' + name)
            if Decimal(member.pax_headers.get('mtime', str(member.mtime))) * 10 ** 9 != item['mtime_ns']:
                raise ValueError('Archive member modification time differs: ' + name)
            if item['type'] == 'file':
                if member.size != item['bytes']:
                    raise ValueError('Archive member size differs: ' + name)
                with archive.extractfile(member) as handle:
                    if _hash_stream(handle) != item['sha256']:
                        raise ValueError('Archive member content differs: ' + name)
                total += member.size
                files += 1
            elif member.size != 0 or (item['type'] == 'symlink' and member.linkname != item['target']):
                raise ValueError('Archive directory/link metadata differs: ' + name)
            seen.add(name)
    if seen != set(expected):
        raise ValueError('Archive members are missing')
    return {'status': 'PASS_FULL_ARCHIVE_VERIFICATION', 'entries_verified': len(expected), 'regular_files_verified': files, 'file_bytes_verified': total}


def _write_archive(source, path, manifest):
    items = [{'path': '.', 'type': 'directory', 'mode': manifest['root_mode'], 'mtime_ns': manifest['root_mtime_ns']}] + manifest['entries']
    rootfd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        with path.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for item in items:
                member = tarfile.TarInfo(item['path']);member.mode = item['mode']
                member.mtime = item['mtime_ns'] // 10 ** 9
                member.pax_headers = {'mtime': format(Decimal(item['mtime_ns']) / Decimal(10 ** 9), 'f')}
                if item['type'] == 'directory':
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                elif item['type'] == 'symlink':
                    member.type = tarfile.SYMTYPE;member.linkname = item['target']
                    archive.addfile(member)
                else:
                    member.size = item['bytes']
                    relative = PurePosixPath(item['path'])
                    with _directory_fd(rootfd, str(relative.parent)) as parent:
                        descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                        with os.fdopen(descriptor, 'rb') as handle:
                            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                                raise ValueError('Archive source changed file type')
                            archive.addfile(member, handle)
    finally:
        os.close(rootfd)
    with _open_file(path) as raw:
        os.fsync(raw.fileno())
    path.chmod(0o444)
    with _open_file(path) as raw:
        os.fsync(raw.fileno())
    _sync_dir(path.parent)


def _bundle(archive, receipt, expected_receipt_sha256):
    archive, receipt = Path(archive), Path(receipt)
    _namespace(receipt.parent)
    if receipt.name != 'archive-receipt.json' or archive != receipt.parent / 'tree.tar.gz':
        raise ValueError('Archive/receipt must belong to one explicit retention namespace')
    if not isinstance(expected_receipt_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_receipt_sha256) or _file_sha(receipt) != expected_receipt_sha256:
        raise ValueError('Pinned archive receipt changed')
    record = _load(receipt)
    expected_fields = {'schema_version', 'profile', 'status', 'root', 'source', 'created_at', 'manifest_sha256',
                       'source_capture', 'archive_sha256', 'archive_bytes', 'expanded_regular_bytes',
                       'regular_files_verified', 'verification', 'tool_sha256'}
    if (not isinstance(record, dict) or set(record) != expected_fields or type(record['schema_version']) is not int
            or record['schema_version'] != 1 or record['profile'] != 'retained-dev-source-v1'
            or record['status'] != 'VERIFIED' or record['root'] != str(ROOT)):
        raise ValueError('Unsupported archive receipt')
    source = _source(record['source'], exists=False) if not Path(record['source']).exists() else _source(record['source'])
    manifest_path = receipt.parent / 'manifest.json'
    if _file_sha(manifest_path) != record['manifest_sha256'] or _file_sha(archive) != record['archive_sha256'] or archive.stat().st_size != record['archive_bytes']:
        raise ValueError('Archive or manifest differs from pinned receipt')
    manifest = _load(manifest_path)
    if manifest['source_name'] != source.name:
        raise ValueError('Archive source identity differs')
    verification = _verify_tar(archive, manifest)
    if (verification != record['verification'] or record['expanded_regular_bytes'] != verification['file_bytes_verified']
            or record['regular_files_verified'] != verification['regular_files_verified']
            or not isinstance(record['source_capture'], dict)
            or set(record['source_capture']) != {'.'} | {item['path'] for item in manifest['entries']}
            or any(not isinstance(value, list) or len(value) != 5 or any(type(x) is not int for x in value)
                   for value in record['source_capture'].values())):
        raise ValueError('Receipt capture/verification fields differ')
    return record, manifest, verification


def archive(source, destination, retire=False):
    guard()
    with runtime_lock(ROOT):
        source = _source(source)
        manifest, stamps = _tree(source)
        _manifest(manifest)
        namespace = _namespace(destination, create=True)
        tar_path = namespace / 'tree.tar.gz'
        _write_archive(source, tar_path, manifest)
        verification = _verify_tar(tar_path, manifest)
        if _tree(source) != (manifest, stamps):
            raise RuntimeError('Source changed during archiving; retained incomplete namespace must be reviewed')
        manifest_sha = _save(namespace / 'manifest.json', manifest)
        receipt = {'schema_version': 1, 'profile': 'retained-dev-source-v1', 'status': 'VERIFIED',
                   'root': str(ROOT), 'source': str(source), 'created_at': datetime.now(timezone.utc).isoformat(),
                   'manifest_sha256': manifest_sha, 'source_capture': stamps,
                   'archive_sha256': _file_sha(tar_path), 'archive_bytes': tar_path.stat().st_size,
                   'expanded_regular_bytes': verification['file_bytes_verified'], 'regular_files_verified': verification['regular_files_verified'],
                   'verification': verification, 'tool_sha256': _file_sha(Path(__file__).resolve())}
        receipt_path = namespace / 'archive-receipt.json'
        receipt_sha = _save(receipt_path, receipt)
        _sync_dir(namespace)
        _sync_dir(namespace.parent)
        result = {'status': 'ARCHIVED_AND_VERIFIED', 'source': str(source), 'archive': str(tar_path),
                  'receipt': str(receipt_path), 'receipt_sha256': receipt_sha,
                  'archive_bytes': receipt['archive_bytes'], 'expanded_regular_bytes': receipt['expanded_regular_bytes'],
                  'regular_files_verified': receipt['regular_files_verified'], 'verification': verification, 'source_retired': False}
    if retire:
        result['retirement'] = globals()['retire'](source, tar_path, receipt_path, receipt_sha)
        result['source_retired'] = True
    return result


def verify(archive, receipt, expected_receipt_sha256):
    guard()
    with runtime_lock(ROOT):
        _, _, result = _bundle(archive, receipt, expected_receipt_sha256)
        return result


@contextmanager
def _directory_fd(rootfd, path):
    descriptor = os.dup(rootfd)
    try:
        for component in PurePosixPath(path).parts:
            if component == '.':
                continue
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor);descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def retire(source, archive, receipt, expected_receipt_sha256):
    guard()
    with runtime_lock(ROOT):
        source = _source(source)
        record, manifest, verified = _bundle(archive, receipt, expected_receipt_sha256)
        if str(source) != record['source'] or _tree(source) != (manifest, record['source_capture']):
            raise RuntimeError('Expanded source changed since verified capture; retirement refused')
        if (_file_sha(archive) != record['archive_sha256'] or _file_sha(receipt) != expected_receipt_sha256
                or _file_sha(Path(receipt).parent / 'manifest.json') != record['manifest_sha256']):
            raise RuntimeError('Retention evidence changed during retirement preflight')
        namespace = Path(receipt).parent
        operation_id = uuid.uuid4().hex
        _save(namespace / ('retirement-' + operation_id + '-started.json'),
              {'status': 'RETIREMENT_STARTED', 'source': str(source), 'receipt_sha256': expected_receipt_sha256,
               'verification': verified})
        for retained in (Path(archive), Path(receipt), namespace / 'manifest.json'):
            with _open_file(retained) as handle:
                os.fsync(handle.fileno())
        _sync_dir(namespace)
        _sync_dir(namespace.parent)
        dirs = [{'path': '.', 'mode': manifest['root_mode']}] + [x for x in manifest['entries'] if x['type'] == 'directory']
        rootfd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if _stamp(os.fstat(rootfd)) != record['source_capture']['.']:
                raise RuntimeError('Source root changed before retirement')
            for item in sorted(dirs, key=lambda row: row['path'].count('/')):
                with _directory_fd(rootfd, item['path']) as descriptor:
                    info = os.fstat(descriptor)
                    if [info.st_dev, info.st_ino] != record['source_capture'][item['path']][:2]:
                        raise RuntimeError('Directory identity changed before retirement')
                    os.fchmod(descriptor, item['mode'] | 0o700)
            for item in manifest['entries']:
                if item['type'] == 'directory':
                    continue
                relative = PurePosixPath(item['path'])
                with _directory_fd(rootfd, str(relative.parent)) as descriptor:
                    info = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
                    if _stamp(info) != record['source_capture'][item['path']]:
                        raise RuntimeError('Source entry changed during retirement')
                    os.unlink(relative.name, dir_fd=descriptor)
            for item in sorted((x for x in dirs if x['path'] != '.'), key=lambda row: row['path'].count('/'), reverse=True):
                relative = PurePosixPath(item['path'])
                with _directory_fd(rootfd, str(relative.parent)) as descriptor:
                    info = os.stat(relative.name, dir_fd=descriptor, follow_symlinks=False)
                    if [info.st_dev, info.st_ino] != record['source_capture'][item['path']][:2] or not stat.S_ISDIR(info.st_mode):
                        raise RuntimeError('Source directory changed during retirement')
                    os.rmdir(relative.name, dir_fd=descriptor)
            if _stamp(source.lstat())[:2] != record['source_capture']['.'][:2] or source.is_symlink():
                raise RuntimeError('Source root changed during retirement')
            source.rmdir()
            _sync_dir(source.parent)
        except Exception as exc:
            _save(namespace / ('retirement-' + operation_id + '-failed.json'),
                  {'status': 'RETIREMENT_INCOMPLETE', 'source': str(source), 'error': str(exc),
                   'receipt_sha256': expected_receipt_sha256,
                   'recovery': 'Archive/receipt remain intact. Restore to a fresh allowed retained-tree path; never overwrite the partial tree.'})
            raise
        finally:
            for item in sorted(dirs, key=lambda row: row['path'].count('/'), reverse=True):
                try:
                    with _directory_fd(rootfd, item['path']) as descriptor:
                        os.fchmod(descriptor, item['mode'])
                except OSError:
                    pass
            os.close(rootfd)
        result = {'status': 'RETIRED_VERIFIED_EXPANDED_COPY', 'source': str(source),
                  'receipt_sha256': expected_receipt_sha256, 'verification': verified}
        _save(namespace / ('retirement-' + operation_id + '-complete.json'), result)
        return result


def restore(archive, receipt, destination, expected_receipt_sha256):
    guard()
    with runtime_lock(ROOT):
        _, manifest, verified = _bundle(archive, receipt, expected_receipt_sha256)
        destination = _source(destination, exists=False)
        if destination.name.split('.before-', 1)[0] != manifest['source_name'].split('.before-', 1)[0]:
            raise ValueError('Restore source-version identity differs')
        destination.mkdir(mode=0o700)
        directories = [x for x in manifest['entries'] if x['type'] == 'directory']
        # No links exist until every directory and regular file has been created.
        for item in sorted(directories, key=lambda row: row['path'].count('/')):
            (destination / item['path']).mkdir(mode=0o700)
        entries = {x['path']: x for x in manifest['entries']}
        with _open_file(archive) as raw, tarfile.open(fileobj=raw, mode='r:gz') as source:
            for member in source:
                item = entries.get(member.name)
                if not item or item['type'] != 'file':
                    continue
                path = destination / item['path']
                with source.extractfile(member) as incoming, path.open('xb') as outgoing:
                    for block in iter(lambda: incoming.read(4 * 1024 * 1024), b''):
                        outgoing.write(block)
                path.chmod(item['mode'])
                os.utime(path, ns=(item['mtime_ns'], item['mtime_ns']), follow_symlinks=False)
        for item in manifest['entries']:
            if item['type'] == 'symlink':
                path = destination / item['path']
                path.symlink_to(item['target'])
                if stat.S_IMODE(path.lstat().st_mode) != item['mode']:
                    raise ValueError('Platform cannot restore the recorded symlink mode')
                os.utime(path, ns=(item['mtime_ns'], item['mtime_ns']), follow_symlinks=False)
        for item in sorted(directories, key=lambda row: row['path'].count('/'), reverse=True):
            (destination / item['path']).chmod(item['mode'])
            os.utime(destination / item['path'], ns=(item['mtime_ns'], item['mtime_ns']), follow_symlinks=False)
        destination.chmod(manifest['root_mode'])
        os.utime(destination, ns=(manifest['root_mtime_ns'], manifest['root_mtime_ns']), follow_symlinks=False)
        actual, _ = _tree(destination)
        expected = dict(manifest, source_name=destination.name)
        if actual != expected:
            raise RuntimeError('Restored tree differs; partial destination retained for review')
        result = {'status': 'PASS_RESTORED_TREE_VERIFICATION', 'destination': str(destination),
                  'receipt_sha256': expected_receipt_sha256, 'verification': verified}
        _save(Path(receipt).parent / ('restore-' + uuid.uuid4().hex + '.json'), result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    archive_parser = commands.add_parser('archive')
    archive_parser.add_argument('--source', required=True)
    archive_parser.add_argument('--destination', required=True)
    for command in ('verify', 'retire', 'restore'):
        child = commands.add_parser(command)
        child.add_argument('--archive', required=True)
        child.add_argument('--receipt', required=True)
        child.add_argument('--receipt-sha256', required=True)
        if command == 'retire':
            child.add_argument('--source', required=True)
        elif command == 'restore':
            child.add_argument('--destination', required=True)
    args = vars(parser.parse_args());command = args.pop('command')
    if 'receipt_sha256' in args:
        args['expected_receipt_sha256'] = args.pop('receipt_sha256')
    print(json.dumps(globals()[command](**args), indent=2))


if __name__ == '__main__':
    main()
