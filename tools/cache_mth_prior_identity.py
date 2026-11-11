#!/usr/bin/env python3
"""Publish one captured prior MTH identity map outside replaceable source trees.

Only an independently copied cui_said_map and sealed receipt are cached beneath
inv/qa/prior-identity-cache/<version>/<full-map-SHA256>/. Original source folders,
receipts, manifests and execution locks remain unchanged. The converter retains
its candidate-local orig/identity snapshot and usual old/src access.

First publication requires the original sealed selective-capture receipt and
its exact readonly canonical map/receipt. Reuse requires only the supplied valid
capture receipt plus the sealed independent cache: the old canonical directory
may since have been renamed, deleted or replaced by a different inversion.
No S3, database, native conversion, insertion, cleanup or full archive copy runs.
"""
import argparse
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import stat

import capture_mth_prior as original
from capture_mth_prepared import publish

MEME_ROOT = Path('/local/content/MEME/MEME5')
RESERVE = 12 * 1024 ** 3
RECEIPT = 'receipt.json'
MAP = 'cui_said_map'


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.geteuid()).pw_name != 'tomcata':
        raise RuntimeError('Prior identity caching requires tomcata on ncias-d3777-c')
    required = (MEME_ROOT, MEME_ROOT / 'inv/sources', MEME_ROOT / 'inv/qa')
    if any(path.resolve() != path or not path.is_dir() for path in required):
        raise RuntimeError('Expected unlinked existing standard MEME source and QA roots')


def _regular(path, readonly=True):
    if path.parent.resolve() != path.parent:
        raise ValueError('Prior identity file ancestor is linked')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1 or
            (readonly and stat.S_IMODE(info.st_mode) != 0o444)):
        raise ValueError('Expected an owned unlinked readonly regular identity file: ' + str(path))
    return info


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, stat.S_IMODE(info.st_mode))


def _open(path):
    before = _regular(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    handle = os.fdopen(descriptor, 'rb')
    if _stamp(os.fstat(handle.fileno())) != _stamp(before):
        handle.close()
        raise ValueError('Identity file changed before opening')
    return handle, _stamp(before)


def _unchanged(path, handle, expected):
    if _stamp(os.fstat(handle.fileno())) != expected or _stamp(_regular(path)) != expected:
        raise ValueError('Original identity map changed during verified copying')


def _directory(path, create=False):
    if not path.is_relative_to(MEME_ROOT):
        raise ValueError('Cache path is outside the standard MEME tree')
    current = MEME_ROOT
    cache_root = MEME_ROOT / 'inv/qa/prior-identity-cache'
    for part in path.relative_to(MEME_ROOT).parts:
        current = current / part
        if create and not current.exists() and not current.is_symlink():current.mkdir(mode=0o755)
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or current.resolve() != current:
            raise ValueError('Expected an unlinked standard directory: ' + str(current))
        if current.is_relative_to(cache_root) and (info.st_uid != os.geteuid() or info.st_mode & 0o022):
            raise ValueError('Cache directories must be owned and not shared-writable: ' + str(current))


def select(captured):
    """Validate captured provenance and derive the sole permitted source/cache."""
    value = copy.deepcopy(captured)
    if (not isinstance(value, dict) or value.get('schema_version') != 1 or
            value.get('artifact_type') != 'ncimeta-preserved-prior-identity-map' or
            value.get('status') != 'CAPTURED_PRIOR_CUI_SAID_MAP' or value.get('source') != 'MTH' or
            not isinstance(value.get('version'), str) or not re.fullmatch(r'MTH_[0-9]{4}(?:AA|AB)', value['version']) or
            value.get('receipt_sha256') != original.digest({key: item for key, item in value.items() if key != 'receipt_sha256'})):
        raise ValueError('A complete sealed original selective prior-map capture receipt is required')
    member = original.select(value['request'])
    version = value['version']
    source = MEME_ROOT / 'inv/sources' / version / 'src/cui_said_map'
    if (value['request']['version'] != version or value.get('selected_member') != member or
            value.get('target') != str(source.parent.parent) or value.get('get_object_identity') != value['request']['object_identity'] or
            value.get('archive_bytes') != value['request']['object_identity']['ContentLength'] or
            not isinstance(value.get('archive_sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', value['archive_sha256']) or
            ('archive_sha256' in value['request'] and value['archive_sha256'] != value['request']['archive_sha256']) or
            value.get('archive_cached') is not False or value.get('archived_code_executed') is not False or
            value.get('production_eligible') is not False):
        raise ValueError('Original capture release, S3/container identity, source path or scope differs')
    identity = value.get('map_identity', {})
    if (not isinstance(identity, dict) or set(identity) != {'sha256', 'bytes', 'rows', 'unique_cuis', 'minimum_said', 'maximum_said'} or
            not isinstance(identity.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', identity['sha256']) or
            any(type(identity.get(key)) is not int or identity[key] <= 0 for key in ('bytes', 'rows', 'unique_cuis', 'minimum_said', 'maximum_said')) or
            identity['rows'] != identity['unique_cuis'] or identity['minimum_said'] > identity['maximum_said']):
        raise ValueError('Original map requires complete positive size/row/unique-CUI/SAID facts')
    target = MEME_ROOT / 'inv/qa/prior-identity-cache' / version / identity['sha256']
    return value, source, target


def _write_new(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as outgoing:
        outgoing.write(json.dumps(value, indent=2, allow_nan=False).encode() + b'\n')
        outgoing.flush();os.fchmod(outgoing.fileno(), 0o444);os.fsync(outgoing.fileno())


def _reuse(directory, captured, target):
    """Validate cache only, deliberately independent of canonical prior paths."""
    _directory(directory)
    if stat.S_IMODE(directory.stat().st_mode) != 0o555 or {p.name for p in directory.iterdir()} != {MAP, RECEIPT}:
        raise ValueError('Existing identity cache inventory or readonly directory mode differs')
    receipt_path = directory / RECEIPT;map_path = directory / MAP
    _regular(receipt_path);_regular(map_path)
    receipt = original.load(receipt_path)
    if (receipt.get('receipt_sha256') != original.digest({key: value for key, value in receipt.items() if key != 'receipt_sha256'}) or
            receipt.get('artifact_type') != 'ncimeta-prior-identity-cache-receipt' or
            receipt.get('schema_version') != 1 or receipt.get('status') != 'PUBLISHED_PRIOR_IDENTITY_CACHE' or
            receipt.get('source') != 'MTH' or receipt.get('version') != captured['version'] or
            receipt.get('original_capture_receipt') != captured or
            receipt.get('original_capture_receipt_sha256') != captured['receipt_sha256'] or
            receipt.get('cache_directory') != str(target) or receipt.get('cache_file') != {
                'role': MAP, 'uri': (target / MAP).as_uri(),
                'sha256': captured['map_identity']['sha256'], 'bytes': captured['map_identity']['bytes']} or
            receipt.get('map_identity') != captured['map_identity'] or
            receipt.get('independent_copy') is not True or receipt.get('hardlink_used') is not False or
            receipt.get('symlink_used') is not False or receipt.get('production_eligible') is not False):
        raise ValueError('Existing identity cache seal, captured provenance, map identity or scope differs')
    incoming, before = _open(map_path)
    with incoming:
        if original._map(incoming, expected_size=captured['map_identity']['bytes']) != captured['map_identity']:
            raise ValueError('Existing identity cache data or row facts differ')
        _unchanged(map_path, incoming, before)
    return receipt


def publish_cache(capture_receipt):
    """Make/reuse an independently copied immutable prior DATA cache only."""
    guard();captured, source, target = select(capture_receipt)
    _directory(target.parent, create=True)
    lock_path = target.parent / '.publish.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as held:
        _regular(lock_path, readonly=False)
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if target.exists() or target.is_symlink():return _reuse(target, captured, target)
        staging = target.parent / ('.' + target.name + '.publishing')
        if staging.exists() or staging.is_symlink():
            # A complete seal is enough to retry only the final publication.
            # A partial/failed stage is retained for review, never duplicated.
            receipt = _reuse(staging, captured, target)
            publish(staging, target);original._sync_dir(target.parent)
            return receipt
        source_receipt_path = source.parent.parent / original.RECEIPT
        _regular(source_receipt_path)
        if original.load(source_receipt_path) != captured:
            raise ValueError('Canonical source capture receipt differs from the supplied original seal')
        incoming, signature = _open(source)
        with incoming:
            if original._map(incoming, expected_size=captured['map_identity']['bytes']) != captured['map_identity']:
                raise ValueError('Canonical original CUI map differs from its captured identity/row facts')
            _unchanged(source, incoming, signature)
            if shutil.disk_usage(target.parent).free < captured['map_identity']['bytes'] + RESERVE:
                raise RuntimeError('Independent prior-map copy requires payload plus the fixed 12GiB reserve')
            staging.mkdir(mode=0o700)
            try:
                incoming.seek(0);checksum = hashlib.sha256();size = 0
                descriptor = os.open(staging / MAP, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, 'wb') as outgoing:
                    for raw in iter(lambda: incoming.read(4 * 1024 ** 2), b''):
                        if shutil.disk_usage(target.parent).free < RESERVE + len(raw):
                            raise RuntimeError('Independent prior-map copy reached the fixed 12GiB reserve')
                        outgoing.write(raw);checksum.update(raw);size += len(raw)
                    outgoing.flush();os.fchmod(outgoing.fileno(), 0o444);os.fsync(outgoing.fileno())
                _unchanged(source, incoming, signature)
                if (checksum.hexdigest(), size) != (captured['map_identity']['sha256'], captured['map_identity']['bytes']):
                    raise ValueError('Independent copy differs from the captured prior map')
                copied = _regular(staging / MAP)
                if (copied.st_dev, copied.st_ino) == signature[:2]:
                    raise ValueError('Prior identity cache must be an independent copy, never a hardlink')
                receipt = {'schema_version': 1, 'artifact_type': 'ncimeta-prior-identity-cache-receipt',
                    'status': 'PUBLISHED_PRIOR_IDENTITY_CACHE', 'source': 'MTH', 'version': captured['version'],
                    'original_capture_receipt_sha256': captured['receipt_sha256'],
                    'original_capture_receipt': captured, 'map_identity': captured['map_identity'],
                    'cache_directory': str(target), 'cache_file': {'role': MAP, 'uri': (target / MAP).as_uri(),
                        'sha256': checksum.hexdigest(), 'bytes': size},
                    'original_locator': source.as_uri(), 'original_signature_at_copy': list(signature),
                    'independent_copy': True, 'hardlink_used': False, 'symlink_used': False,
                    'copy_reserve_bytes': RESERVE,
                    'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'apparatus_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'native_execution_performed': False, 'production_eligible': False,
                    'scope': 'One immutable prior identity DATA copy plus provenance receipt; original canonical stub and all earlier records remain unchanged'}
                receipt['receipt_sha256'] = original.digest(receipt)
                _write_new(staging / RECEIPT, receipt)
                staging.chmod(0o555);original._sync_dir(staging)
                publish(staging, target);original._sync_dir(target.parent)
                return receipt
            except BaseException as error:
                if staging.exists() and stat.S_IMODE(staging.stat().st_mode) != 0o555:
                    _write_new(staging / 'publication-failed.json', {'status': 'FAILED_NOT_PUBLISHED',
                        'original_capture_receipt_sha256': captured['receipt_sha256'], 'error': str(error),
                        'scope': 'Retained request-owned partial evidence; original prior data is untouched'})
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('capture_receipt', help='Original complete selective prior-map receipt JSON')
    arguments = parser.parse_args()
    print(json.dumps(publish_cache(original.load(arguments.capture_receipt)), indent=2))


if __name__ == '__main__':main()
