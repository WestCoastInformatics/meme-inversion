#!/usr/bin/env python3
"""Selectively freeze one archived prior MTH CUI/SAID map on dev.

The full conditional S3 response is consumed/hashed, never cached as a tgz.
Only src/cui_said_map plus a sealed receipt are published. This is not a full
prior release restoration, an NCImeta capture or a complete database snapshot.
"""
import argparse
from contextlib import contextmanager
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import socket
import stat
import subprocess
import tempfile
import zlib
import tarfile

from acquire_mth_subset import publish

ROOT = Path('/local/content/MEME/MEME5/inv/sources')
RECEIPT = 'prior-identity-map-reference.json'
RESERVE = 8 * 1024 ** 3
IDENTITY_FIELDS = ('ContentLength', 'ETag', 'LastModified', 'VersionId')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    def unique(rows):
        result = {}
        for key, value in rows:
            if key in result:raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))


def _safe_dir(path):
    if path.resolve() != path or not path.is_dir():
        raise ValueError('Expected an unlinked existing standard directory: ' + str(path))


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Selective prior-map capture requires tomcata on ncias-d3777-c')
    _safe_dir(ROOT)


def _sync_dir(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def _write_new(path, value, mode=0o444):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as out:
        out.write(json.dumps(value, indent=2, allow_nan=False).encode() + b'\n')
        os.fchmod(out.fileno(), mode);out.flush();os.fsync(out.fileno())


def select(request):
    required = {'source', 'version', 'bucket', 'key', 'object_identity', 'capture_id'}
    if not isinstance(request, dict) or not required <= set(request) or set(request) - required - {'archive_sha256'}:
        raise ValueError('Incomplete or unknown selective capture request fields')
    if request['source'] != 'MTH' or not isinstance(request['version'], str) or not re.fullmatch(r'MTH_[0-9]{4}(AA|AB)', request['version']):
        raise ValueError('An exact MTH_YYYYAA/AB prior release is required')
    if request['bucket'] != 'nci-evs-meme' or request['key'] != 'inv/sources/' + request['version'] + '.tgz':
        raise ValueError('Only the exact standard prior source archive is permitted')
    identity = request['object_identity']
    if not isinstance(identity, dict) or set(identity) != set(IDENTITY_FIELDS) or type(identity['ContentLength']) is not int or identity['ContentLength'] <= 0:
        raise ValueError('An independently frozen complete S3 HEAD identity is required')
    if any(not isinstance(identity[key], str) or not identity[key].strip() or any(c in identity[key] for c in '\r\n\x00') for key in ('ETag', 'LastModified')) or identity['ETag'].startswith('-'):
        raise ValueError('Pinned ETag and LastModified must be literal nonempty strings')
    if identity['VersionId'] is not None and (not isinstance(identity['VersionId'], str) or not identity['VersionId'] or '\x00' in identity['VersionId']):
        raise ValueError('VersionId must be explicit null or a literal version identity')
    if not isinstance(request['capture_id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', request['capture_id']):
        raise ValueError('A bounded capture identity is required')
    if 'archive_sha256' in request and not re.fullmatch(r'[0-9a-f]{64}', request['archive_sha256']):
        raise ValueError('Expected archive SHA-256 is malformed')
    return request['version'] + '/src/cui_said_map'


class _Download:
    def __init__(self, stream, process):
        self.stream, self.process = stream, process

    def finish(self):
        out, err = self.process.communicate(timeout=60)
        if self.process.returncode:
            raise RuntimeError('Conditional S3 GetObject failed: ' + err.decode(errors='replace')[-2000:])
        result = json.loads(out)
        return {key: result.get(key) for key in IDENTITY_FIELDS}


class AwsCliClient:
    """Injectable client boundary; production always defaults to /usr/bin/aws."""
    def __init__(self, program=None):
        self.program = ['/usr/bin/aws'] if program is None else list(program)
        self.env = dict(os.environ, AWS_PROFILE='meme', AWS_PAGER='', AWS_CLI_AUTO_PROMPT='off')

    def head(self, request):
        value = subprocess.run(self.program + ['s3api', 'head-object', '--bucket', request['bucket'], '--key', request['key'], '--output', 'json'],
                               capture_output=True, env=self.env, timeout=60, check=True)
        result = json.loads(value.stdout)
        return {key: result.get(key) for key in IDENTITY_FIELDS}

    @contextmanager
    def open(self, request):
        read_fd, write_fd = os.pipe();process = None;stream = None
        try:
            command = self.program + ['s3api', 'get-object', '--bucket', request['bucket'], '--key', request['key'],
                '--if-match', request['object_identity']['ETag'], '--cli-connect-timeout', '30', '--cli-read-timeout', '60', '--output', 'json']
            if request['object_identity']['VersionId'] is not None:
                command += ['--version-id', request['object_identity']['VersionId']]
            command.append('/dev/fd/' + str(write_fd))
            process = subprocess.Popen(command, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, pass_fds=(write_fd,))
            os.close(write_fd);write_fd = None
            stream = os.fdopen(read_fd, 'rb', buffering=0);read_fd = None
            yield _Download(stream, process)
        finally:
            if write_fd is not None:os.close(write_fd)
            if read_fd is not None:os.close(read_fd)
            if stream is not None:stream.close()
            if process is not None:
                if process.poll() is None:process.terminate()
                try:process.communicate(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=5)


class _HashReader:
    """Hash every compressed byte and independently verify gzip CRC/end marker.

    tarfile's streaming gzip reader can stop before the trailer. The small-output
    zlib pass ensures a selected early member cannot hide a truncated/invalid
    container; no decompressed archive payload is retained by this checker.
    """
    def __init__(self, stream):
        self.stream = stream;self.hash = hashlib.sha256();self.bytes = 0
        self.gzip = zlib.decompressobj(16 + zlib.MAX_WBITS);self.finished = False

    def read(self, count=-1):
        raw = self.stream.read(count)
        if not raw:return raw
        self.hash.update(raw);self.bytes += len(raw)
        if self.finished:
            if raw.strip(b'\0'):raise ValueError('Unexpected bytes after the single gzip member')
            return raw
        pending = raw
        while True:
            result = self.gzip.decompress(pending, 1024 * 1024)
            pending = self.gzip.unconsumed_tail
            if self.gzip.eof:
                if self.gzip.unused_data.strip(b'\0'):raise ValueError('Unsupported trailing/concatenated gzip content')
                self.finished = True;break
            if not pending and len(result) < 1024 * 1024:break
        return raw

    def finish(self):
        while self.read(4 * 1024 * 1024):pass
        if not self.finished:raise ValueError('Compressed archive is truncated before its gzip trailer')
        return {'sha256': self.hash.hexdigest(), 'bytes': self.bytes}


def _map(incoming, outgoing=None, expected_size=None):
    seen = set();value = hashlib.sha256();size = rows = 0;low = high = None
    while True:
        raw = incoming.readline(256)
        if not raw:break
        fields = raw.removesuffix(b'\n').split(b'|')
        if fields and fields[-1] == b'':fields.pop()
        if not raw.endswith(b'\n') or b'\r' in raw or len(fields) != 2 or not re.fullmatch(rb'C[0-9]{7,}', fields[0]) or not re.fullmatch(rb'[1-9][0-9]*', fields[1]):
            raise ValueError('Prior map requires CUI|positive-SAID rows with final newline')
        if fields[0] in seen:raise ValueError('Duplicate CUI in preserved prior map')
        seen.add(fields[0]);identifier = int(fields[1]);rows += 1;size += len(raw);value.update(raw)
        low = identifier if low is None else min(low, identifier);high = identifier if high is None else max(high, identifier)
        if outgoing is not None:
            if rows == 1 or size // (4 * 1024 * 1024) != (size - len(raw)) // (4 * 1024 * 1024):
                if shutil.disk_usage(ROOT).free < RESERVE:raise RuntimeError('Prior-map capture reached the fixed 8 GiB disk reserve')
            outgoing.write(raw)
    if not rows or (expected_size is not None and size != expected_size):raise ValueError('Prior map is empty or truncated')
    return {'sha256': value.hexdigest(), 'bytes': size, 'rows': rows, 'unique_cuis': len(seen), 'minimum_said': low, 'maximum_said': high}


def _reuse(target, request):
    _safe_dir(target);_safe_dir(target / 'src')
    receipt_path = target / RECEIPT;map_path = target / 'src/cui_said_map'
    if receipt_path.is_symlink() or map_path.is_symlink() or not receipt_path.is_file() or not map_path.is_file():
        raise ValueError('Existing prior folder has no matching sealed selective-capture receipt')
    if any(path.stat().st_mode & 0o222 for path in (receipt_path, map_path)):
        raise ValueError('Previously frozen prior map/receipt became writable')
    receipt = load(receipt_path)
    if receipt.get('receipt_sha256') != digest({k: v for k, v in receipt.items() if k != 'receipt_sha256'}) or receipt.get('request') != request or receipt.get('status') != 'CAPTURED_PRIOR_CUI_SAID_MAP':
        raise ValueError('Existing prior-map selection/receipt differs')
    if {p.name for p in target.iterdir()} != {'src', RECEIPT} or {p.name for p in (target / 'src').iterdir()} != {'cui_said_map'}:
        raise ValueError('Existing prior folder has unreviewed extra data')
    with map_path.open('rb') as incoming:
        if _map(incoming) != receipt['map_identity']:raise ValueError('Previously frozen prior map changed')
    return receipt


def capture(request, client=None):
    guard();selected = select(request);request = copy.deepcopy(request)
    client = AwsCliClient() if client is None else client
    target = ROOT / request['version']
    lock_fd = os.open(ROOT / ('.' + request['version'] + '.prior-map.lock'), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'a') as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if target.exists() or target.is_symlink():return _reuse(target, request)
        if client.head(request) != request['object_identity']:raise ValueError('S3 HEAD differs from independently frozen prior identity')
        staging = Path(tempfile.mkdtemp(prefix='.' + request['version'] + '.prior-map-', dir=str(ROOT)))
        (staging / 'src').mkdir(mode=0o700)
        try:
            found = False;seen = set();map_identity = None
            with client.open(request) as download:
                hashed = _HashReader(download.stream)
                with tarfile.open(fileobj=hashed, mode='r|gz') as archive:
                    for member in archive:
                        name = member.name.removeprefix('./').rstrip('/');path = PurePosixPath(name)
                        if not name or path.is_absolute() or '..' in path.parts or str(path) != name or path.parts[0] != request['version'] or name in seen:
                            raise ValueError('Unsafe or duplicate archive member')
                        seen.add(name)
                        if name != selected:continue
                        if found or not member.isfile() or member.size <= 0:raise ValueError('Selected prior map must be one nonempty regular member')
                        if shutil.disk_usage(ROOT).free < member.size + RESERVE:raise RuntimeError('Insufficient free disk for selected map plus fixed reserve')
                        found = True
                        with (staging / 'src/cui_said_map').open('xb') as outgoing, archive.extractfile(member) as incoming:
                            map_identity = _map(incoming, outgoing, member.size)
                            outgoing.flush();os.fchmod(outgoing.fileno(), 0o444);os.fsync(outgoing.fileno())
                container = hashed.finish();get_identity = download.finish()
            if not found:raise ValueError('The exact prior src/cui_said_map member is absent')
            if container['bytes'] != request['object_identity']['ContentLength'] or get_identity != request['object_identity'] or client.head(request) != request['object_identity']:
                raise ValueError('Container size, GetObject metadata or after-HEAD identity changed')
            if 'archive_sha256' in request and container['sha256'] != request['archive_sha256']:raise ValueError('Complete compressed archive SHA-256 differs')
            receipt = {'schema_version': 1, 'artifact_type': 'ncimeta-preserved-prior-identity-map', 'status': 'CAPTURED_PRIOR_CUI_SAID_MAP',
                       'request': request, 'source': 'MTH', 'version': request['version'], 'selected_member': selected,
                       'map_identity': map_identity, 'archive_sha256': container['sha256'], 'archive_bytes': container['bytes'],
                       'get_object_identity': get_identity, 'target': str(target), 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       'archive_cached': False, 'archived_code_executed': False, 'production_eligible': False,
                       'scope': 'One preserved prior CUI/SAID map only; not a full source restoration or complete database snapshot'}
            receipt['receipt_sha256'] = digest(receipt)
            _write_new(staging / RECEIPT, receipt)
            (staging / 'src').chmod(0o755);staging.chmod(0o755)
            _sync_dir(staging / 'src');_sync_dir(staging);_sync_dir(ROOT)
            publish(staging, target);_sync_dir(ROOT)
            return receipt
        except BaseException as error:
            if staging.exists():
                _write_new(staging / 'capture-failed.json', {'status': 'FAILED_NOT_PUBLISHED', 'request_sha256': digest(request),
                    'error': str(error), 'archive_cached': False, 'staging': str(staging)})
                _sync_dir(staging)
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('request')
    args = parser.parse_args();print(json.dumps(capture(load(args.request)), indent=2))
