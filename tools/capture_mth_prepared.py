#!/usr/bin/env python3
"""First capture of eleven preserved prepared MTH objects at the dev path.

This is separate from bounded historical acquisition. It reads S3, records the
first full byte SHA256 values and native record facts, and publishes a complete
read-only METASUBSET directory atomically without clobbering an existing path.
No MetamorphoSys, inversion, insertion, ID allocation or S3 write is performed.

Request: source, version (MTH_YYYYAA/AB), subset_directory
(subsetN/METASUBSET), bucket=nci-evs-meme, objects:[{role,key,head:{
ContentLength,ETag,LastModified,VersionId}}]. ``object_identity`` is accepted as
the inventory's spelling of ``head``; supplying both is rejected. Eleven roles
are accepted, and each key must equal mr/umls/<release>/<subset>/<role>.
Unknown SHA256 is intentional: these are captured from conditionally selected
authoritative object bytes, not guessed from an ETag.

Complete checkpointed prefixes survive a streaming failure and are rehashed
before ranged resumption. An AWS CLI failure whose response headers were not
obtained retains its private incoming file for review rather than trusting,
overwriting, or silently duplicating it. Completed roles are never redownloaded.
The 12GiB capture reserve is independent of the worker's 45GiB execution gate.
"""
import argparse
import base64
from collections import Counter
import ctypes
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
import subprocess
import sys
import tempfile

import execute_release_mth as execution

MEME_ROOT = Path('/local/content/MEME/MEME5')
CAPTURE_RESERVE = 12 * 1024 ** 3
CHUNK_BYTES = 64 * 1024 ** 2
RECEIPT = '.mth-prepared-capture.json'
STATE = '.capture-state.json'
HEAD_KEYS = ('ContentLength', 'ETag', 'LastModified', 'VersionId')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _time(value):
    if isinstance(value, datetime.datetime):
        value = value.isoformat()
    if not isinstance(value, str):
        raise ValueError('Pinned S3 LastModified is required')
    try:
        parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('Pinned S3 LastModified must be an ISO8601 instant') from error
    if parsed.utcoffset() is None:
        raise ValueError('Pinned S3 LastModified requires a timezone')
    return parsed.astimezone(datetime.timezone.utc).isoformat()


def _head(value):
    if (not isinstance(value, dict) or type(value.get('ContentLength')) is not int or value['ContentLength'] < 0 or
            not isinstance(value.get('ETag'), str) or not re.fullmatch(r'"[^"\r\n]+"', value['ETag']) or
            'VersionId' not in value or (value['VersionId'] is not None and
            (not isinstance(value['VersionId'], str) or not value['VersionId'] or any(ord(x) < 32 for x in value['VersionId'])))):
        raise ValueError('Every object needs pinned ContentLength, quoted ETag, LastModified and explicit VersionId/null')
    return {'ContentLength': value['ContentLength'], 'ETag': value['ETag'],
            'LastModified': _time(value['LastModified']), 'VersionId': value['VersionId']}


def select(request):
    value = json.loads(canonical(request))
    if (value.get('source') != 'MTH' or not isinstance(value.get('version'), str) or
            not re.fullmatch(r'MTH_[0-9]{4}(?:AA|AB)', value['version']) or
            not isinstance(value.get('subset_directory'), str) or
            not re.fullmatch(r'subset[1-9][0-9]*/METASUBSET', value['subset_directory']) or
            value.get('bucket') != 'nci-evs-meme'):
        raise ValueError('A canonical MTH release, preserved standard subset and archive bucket are required')
    objects = value.get('objects')
    if (not isinstance(objects, list) or len(objects) != len(execution.RRF_WIDTHS) or
            any(not isinstance(item, dict) or not isinstance(item.get('role'), str) for item in objects) or
            {item['role'] for item in objects} != set(execution.RRF_WIDTHS)):
        raise ValueError('Exactly the eleven distinct prepared RRF roles are required')
    prefix = 'mr/umls/' + value['version'][4:] + '/' + value['subset_directory'] + '/'
    for item in objects:
        if 'object_identity' in item:
            if 'head' in item:
                raise ValueError('Supply one spelling of the pinned HEAD identity')
            item['head'] = item.pop('object_identity')
        if item.get('key') != prefix + item['role']:
            raise ValueError('Prepared object key differs from the declared standard release/subset path')
        if set(item) != {'role', 'key', 'head'}:
            raise ValueError('Prepared object selectors contain unreviewed fields')
        item['head'] = _head(item['head'])
        if item['role'] in ('MRCONSO.RRF', 'MRSAB.RRF', 'MRRANK.RRF') and item['head']['ContentLength'] == 0:
            raise ValueError('Required prepared native input cannot be empty: ' + item['role'])
    value['objects'] = sorted(objects, key=lambda item: item['role'])
    return value


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.geteuid()).pw_name != 'tomcata':
        raise RuntimeError('Prepared object capture is scoped to tomcata on ncias-d3777-c')
    if MEME_ROOT.resolve() != MEME_ROOT:
        raise RuntimeError('The standard MEME root cannot traverse a symlink')


def _directories(path):
    if not path.is_relative_to(MEME_ROOT):
        raise RuntimeError('Capture path is outside the standard MEME root')
    for parent in [MEME_ROOT, *[MEME_ROOT.joinpath(*path.relative_to(MEME_ROOT).parts[:i])
                               for i in range(1, len(path.relative_to(MEME_ROOT).parts) + 1)]]:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            parent.mkdir(mode=0o755)
            info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RuntimeError('Capture path has a non-directory or linked ancestor: ' + str(parent))


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
        raise RuntimeError('A private owned regular capture file is required: ' + str(path))
    return info


def _identity(path):
    before = _regular(path)
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as handle:
        for raw in iter(lambda: handle.read(4 * 1024 ** 2), b''):
            digest.update(raw);size += len(raw)
    after = _regular(path)
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise RuntimeError('Capture file changed while hashing')
    return {'sha256': digest.hexdigest(), 'bytes': size}


def _write(path, value):
    if path.exists() or path.is_symlink():
        _regular(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.state-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(canonical(value) + b'\n');handle.flush();os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(staging, target):
    """Atomic directory rename with kernel-enforced no-replace semantics."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux'):
        function = getattr(libc, 'renameat2', None)
        if function is None:
            raise RuntimeError('Kernel-backed no-replace publication is unavailable; nothing published')
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        result = function(-100, os.fsencode(staging), -100, os.fsencode(target), 1)
    elif sys.platform == 'darwin':
        # macOS SDK sys/stdio.h: RENAME_EXCL=0x00000004. Dev uses Linux above.
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        result = function(os.fsencode(staging), os.fsencode(target), 0x00000004)
    else:
        raise RuntimeError('Kernel-backed no-replace publication is unsupported')
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def _scan(path, role, version):
    digest, size, rows, malformed = hashlib.sha256(), 0, 0, 0
    versions, relations, by_version = Counter(), Counter(), {}
    mrsab = bytearray()
    has_mth = False
    with path.open('rb') as handle:
        for raw in handle:
            digest.update(raw);size += len(raw);rows += 1
            fields = execution._fields(raw)
            malformed += len(fields) != execution.RRF_WIDTHS[role] or not raw.endswith(b'|\n') or b'\0' in raw or b'\r' in raw
            try:
                raw.decode('utf-8')
            except UnicodeDecodeError:
                malformed += 1
            if len(fields) != execution.RRF_WIDTHS[role]:
                continue
            if role in ('MRAUI.RRF', 'MRCUI.RRF'):
                index = 2 if role == 'MRAUI.RRF' else 1
                release, relation = fields[index].decode(errors='replace'), fields[index + 1].decode(errors='replace')
                versions[release] += 1;relations[relation] += 1
                nested = by_version.setdefault(release, Counter());nested[relation] += 1
            if role == 'MRCONSO.RRF':
                malformed += not fields[0] or not fields[7]
            if role == 'MRSAB.RRF':
                mrsab.extend(raw)
                if len(mrsab) > 32 * 1024 ** 2:
                    raise RuntimeError('MRSAB exceeds the bounded small-body capture limit')
                has_mth = has_mth or fields[2:4] == [version.encode(), b'MTH']
    if malformed or (role in ('MRCONSO.RRF', 'MRSAB.RRF', 'MRRANK.RRF') and rows == 0):
        raise RuntimeError('Malformed or empty required native input: ' + role + ' (' + str(malformed) + ' record issues)')
    if role == 'MRSAB.RRF' and not has_mth:
        raise RuntimeError('Prepared MRSAB does not contain the selected current MTH version')
    facts = {'sha256': digest.hexdigest(), 'bytes': size, 'rows': rows, 'malformed_rows': malformed}
    if role in ('MRAUI.RRF', 'MRCUI.RRF'):
        facts.update(versions=dict(versions), relations=dict(relations),
                     version_relations={key: dict(value) for key, value in by_version.items()})
    if role == 'MRSAB.RRF':
        facts['data_b64'] = base64.b64encode(mrsab).decode()
    return facts


def _arguments(request, item):
    result = {'Bucket': request['bucket'], 'Key': item['key']}
    if item['head']['VersionId'] is not None:
        result['VersionId'] = item['head']['VersionId']
    return result


def _head_matches(client, request, item):
    value = client.head_object(**_arguments(request, item))
    value.setdefault('VersionId', None)
    observed = _head(value)
    if observed != item['head']:
        raise RuntimeError('S3 object differs from its pinned identity: ' + item['key'])
    return observed


def _response(response, item, start, end):
    expected = item['head']
    if (response.get('ETag') != expected['ETag'] or response.get('VersionId') != expected['VersionId'] or
            response.get('ContentLength') != end - start + 1 or
            response.get('ContentRange') != 'bytes ' + str(start) + '-' + str(end) + '/' + str(expected['ContentLength'])):
        raise RuntimeError('Conditional ranged S3 response differs from its pinned request')
    if 'LastModified' in response and _time(response['LastModified']) != expected['LastModified']:
        raise RuntimeError('Ranged S3 LastModified differs from its pinned request')


def _download(client, request, item, staging, state, progress):
    role = item['role'];expected = item['head']['ContentLength'];part = staging / (role + '.part')
    prior = state['progress'].get(role, {'sha256': sha(b''), 'bytes': 0})
    if part.exists() or part.is_symlink():
        if _identity(part) != {key: prior[key] for key in ('sha256', 'bytes')}:
            raise RuntimeError('Retained private download prefix differs from its checkpoint: ' + role)
    elif prior['bytes'] != 0:
        raise RuntimeError('Retained private download prefix is missing: ' + role)
    if prior['bytes'] > expected:
        raise RuntimeError('Retained download exceeds the pinned object length')
    digest = hashlib.sha256()
    if part.exists():
        with part.open('rb') as handle:
            for raw in iter(lambda: handle.read(4 * 1024 ** 2), b''):digest.update(raw)
    else:
        with part.open('xb'):
            pass
    size = prior['bytes']
    while size < expected:
        start, end = size, min(expected - 1, size + CHUNK_BYTES - 1)
        response = client.get_object(**_arguments(request, item), IfMatch=item['head']['ETag'],
                                     Range='bytes=' + str(start) + '-' + str(end))
        body = response.get('Body')
        try:
            _response(response, item, start, end)
            with part.open('ab') as handle:
                try:
                    while True:
                        raw = body.read(min(4 * 1024 ** 2, end - size + 2))
                        if not raw:
                            break
                        if not isinstance(raw, bytes) or len(raw) > end - size + 1:
                            raise RuntimeError('S3 response exceeded the pinned byte range')
                        handle.write(raw);digest.update(raw);size += len(raw)
                finally:
                    handle.flush();os.fsync(handle.fileno())
                    state['progress'][role] = {'sha256': digest.hexdigest(), 'bytes': size}
                    _write(staging / STATE, state)
            if size != end + 1:
                raise RuntimeError('S3 response ended before the pinned byte range')
        finally:
            if body is not None:body.close()
    _head_matches(client, request, item)
    observed = _scan(part, role, request['version'])
    if (observed['sha256'], observed['bytes']) != (digest.hexdigest(), expected):
        raise RuntimeError('Downloaded native input changed while validating: ' + role)
    part.chmod(0o444)
    os.link(part, staging / role, follow_symlinks=False)
    part.unlink()
    state['completed'][role] = observed
    state['progress'].pop(role, None)
    _write(staging / STATE, state)
    progress('Captured ' + role + ': ' + str(expected) + ' bytes')


class AwsCliS3:
    """Only HeadObject/GetObject via the existing read-only meme AWS profile."""
    def __init__(self, staging):
        self.staging = Path(staging)
        self.environment = dict(os.environ, AWS_PROFILE='meme', AWS_PAGER='', AWS_CLI_AUTO_PROMPT='off')

    def _call(self, operation, arguments, output=None):
        argv = ['/usr/bin/aws', 's3api', operation]
        for key, value in arguments.items():
            argv += ['--' + re.sub(r'(?<!^)(?=[A-Z])', '-', key).lower(), str(value)]
        argv += ['--output', 'json']
        if output is not None:argv.append(str(output))
        result = subprocess.run(argv, env=self.environment, capture_output=True, text=True, timeout=1800)
        if result.returncode:
            raise RuntimeError('Read-only S3 ' + operation + ' failed; private response retained: ' + result.stderr[-1500:])
        return json.loads(result.stdout)

    def head_object(self, **arguments):
        value = self._call('head-object', arguments)
        value.setdefault('VersionId', None)
        return value

    def get_object(self, **arguments):
        suffix = sha(canonical(arguments))[:24]
        incoming = self.staging / ('.incoming-' + suffix)
        if incoming.exists() or incoming.is_symlink():
            raise RuntimeError('An unconfirmed prior CLI response requires review; not overwritten: ' + str(incoming))
        descriptor = os.open(incoming, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        value = self._call('get-object', arguments, incoming)
        value.setdefault('VersionId', None)
        handle = incoming.open('rb')
        class Body:
            def read(self, count):return handle.read(count)
            def close(self):
                handle.close()
                incoming.unlink()
        value['Body'] = Body()
        return value


def capture(request, client=None, progress=print):
    """Capture to the standard dev path, or reverify its exact sealed receipt."""
    guard()
    request = select(request)
    request_sha = sha(canonical(request))
    target = MEME_ROOT / 'mr/umls' / request['version'][4:] / request['subset_directory']
    parent = target.parent
    _directories(parent)
    lock_path = parent / '.mth-prepared-capture.lock'
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'r+') as lock:
        _regular(lock_path)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another prepared capture holds this subset lock') from error
        staging = parent / ('.METASUBSET.capture-' + request_sha[:24])
        if client is None:client = AwsCliS3(staging)
        before = {item['role']: _head_matches(client, request, item) for item in request['objects']}
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir():
                raise RuntimeError('An existing prepared target is not a regular directory; nothing overwritten')
            receipt_path = target / RECEIPT
            _regular(receipt_path)
            if (receipt_path.stat().st_mode & 0o222 or
                    set(path.name for path in target.iterdir()) != {*execution.RRF_WIDTHS, RECEIPT}):
                raise RuntimeError('Published prepared directory or read-only receipt inventory changed')
            prior = json.loads(receipt_path.read_text())
            if prior.get('request_sha256') != request_sha or prior.get('request') != request or prior.get('complete') is not True:
                raise RuntimeError('Existing prepared target lacks this exact complete request receipt; nothing overwritten')
            for item in request['objects']:
                path = target / item['role'];observed = _identity(path)
                if observed != {key: prior['facts'][item['role']][key] for key in ('sha256', 'bytes')} or path.stat().st_mode & 0o222:
                    raise RuntimeError('Published prepared input changed or became writable: ' + str(path))
            for item in request['objects']:_head_matches(client, request, item)
            return prior
        if staging.exists() or staging.is_symlink():
            if (staging.is_symlink() or not staging.is_dir() or staging.stat().st_uid != os.geteuid() or
                    staging.stat().st_mode & 0o022):
                raise RuntimeError('Retained staging is not this operator owned directory')
            state_path = staging / STATE
            if not state_path.exists() and (staging / RECEIPT).is_file():
                # Publication may have failed safely after the complete seal.
                _regular(staging / RECEIPT)
                state = json.loads((staging / RECEIPT).read_text())
                if state.get('request_sha256') != request_sha or state.get('request') != request or state.get('complete') is not True:
                    raise RuntimeError('Retained complete stage belongs to another request')
                if (set(path.name for path in staging.iterdir()) != {*execution.RRF_WIDTHS, RECEIPT} or
                        (staging / RECEIPT).stat().st_mode & 0o222):
                    raise RuntimeError('Retained complete stage inventory or read-only receipt changed')
                for item in request['objects']:
                    if (_identity(staging / item['role']) != {key: state['facts'][item['role']][key] for key in ('sha256', 'bytes')} or
                            (staging / item['role']).stat().st_mode & 0o222):
                        raise RuntimeError('Retained complete stage changed')
                for item in request['objects']:_head_matches(client, request, item)
                publish(staging, target)
                return state
            _regular(state_path)
            state = json.loads(state_path.read_text())
            if state.get('request_sha256') != request_sha or state.get('request') != request:
                raise RuntimeError('Retained stage belongs to another request')
        else:
            staging.mkdir(mode=0o700)
            state = {'schema_version': 1, 'request_sha256': request_sha, 'request': request,
                     'completed': {}, 'progress': {}, 'before_heads': before}
            _write(staging / STATE, state)
        existing_bytes = 0
        for item in request['objects']:
            role = item['role']
            if role in state['completed']:
                path = staging / role
                if _identity(path) != {key: state['completed'][role][key] for key in ('sha256', 'bytes')} or path.stat().st_mode & 0o222:
                    raise RuntimeError('Retained completed input changed: ' + role)
                existing_bytes += state['completed'][role]['bytes']
            elif role in state['progress']:
                if _identity(staging / (role + '.part')) != state['progress'][role]:
                    raise RuntimeError('Retained partial input changed: ' + role)
                existing_bytes += state['progress'][role]['bytes']
        payload = sum(item['head']['ContentLength'] for item in request['objects'])
        required = payload - existing_bytes + CAPTURE_RESERVE
        if shutil.disk_usage(parent).free < required:
            raise RuntimeError('Capture requires remaining payload plus the separate 12GiB reserve; execution still requires its independent 45GiB floor')
        try:
            for item in request['objects']:
                if item['role'] not in state['completed']:_download(client, request, item, staging, state, progress)
            after = {item['role']: _head_matches(client, request, item) for item in request['objects']}
            if set(path.name for path in staging.iterdir()) != {*execution.RRF_WIDTHS, STATE}:
                raise RuntimeError('Unexpected retained evidence in stage requires review before publication')
            result = {'schema_version': 1, 'artifact_type': 'mth-prepared-capture-receipt',
                'source': 'MTH', 'version': request['version'], 'subset_directory': request['subset_directory'],
                'request_sha256': request_sha, 'request': request, 'complete': True,
                'before_heads': before, 'after_heads': after, 'facts': state['completed'],
                'files': [{'role': item['role'], 'uri': 's3://' + request['bucket'] + '/' + item['key'],
                           **{key: state['completed'][item['role']][key] for key in ('sha256', 'bytes')}} for item in request['objects']],
                'mrsab_data_b64': state['completed']['MRSAB.RRF']['data_b64'],
                'capture_reserve_bytes': CAPTURE_RESERVE, 'native_execution_performed': False,
                'production_eligible': False, 'execution_capacity_gate_satisfied': False,
                'scope': 'Authoritative preserved prepared bytes, not upstream regeneration or native inversion proof',
                'apparatus_sha256': sha(Path(__file__).read_bytes())}
            _write(staging / RECEIPT, result)
            (staging / RECEIPT).chmod(0o444)
            (staging / STATE).unlink()
            staging.chmod(0o555)
            publish(staging, target)
            return result
        except BaseException:
            # Keep this exact request's checkpoint and partial bytes. No broad
            # deletion, second copy, changed request adoption or target overwrite.
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('request')
    arguments = parser.parse_args()
    with Path(arguments.request).open() as handle:request = json.load(handle)
    result = capture(request)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
