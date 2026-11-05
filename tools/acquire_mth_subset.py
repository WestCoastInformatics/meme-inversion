#!/usr/bin/env python3
"""Freeze the declared prepared UMLS inputs at the standard MTH dependency path.

The existing pull helper restores the entire UMLS tree. This bounded adapter
uses its existing AWS CLI/profile/bucket for eleven explicit objects, without
modifying that helper or introducing another archive convention.
"""
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import tempfile

ROOT = Path('/local/content/MEME/MEME5/mr/umls')
RELEASE = '2026AA'
NAMES = {'MRCONSO.RRF', 'MRREL.RRF', 'MRSAT.RRF', 'MRSTY.RRF', 'MRDEF.RRF', 'MRCUI.RRF',
         'MRCXT.RRF', 'MRSAB.RRF', 'MRRANK.RRF', 'MRAUI.RRF', 'MRDOC.RRF'}


def identity(path):
    digest, lines = hashlib.sha256(), 0
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4194304), b''):
            digest.update(block)
            lines += block.count(b'\n')
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'newline_count': lines}


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Prepared UMLS restoration is scoped to tomcata on dev')
    if ROOT.is_symlink():
        raise RuntimeError('Unexpected UMLS root symlink')


def select(request):
    if request['source'] != 'MTH' or request['version'] != 'MTH_2026AA' or request['umls_release'] != RELEASE:
        raise RuntimeError('Only the declared MTH 2026AA case is supported')
    items = request['objects']
    prefix = 'mr/umls/' + RELEASE + '/subset3/METASUBSET/'
    if len(items) != len(NAMES) or {x['key'] for x in items} != {prefix + name for name in NAMES}:
        raise RuntimeError('Only the eleven explicit prepared-subset objects may be restored')
    if any(not isinstance(x['bytes'], int) or x['bytes'] <= 0 or not x.get('etag') for x in items):
        raise RuntimeError('Every object needs a pinned size and ETag')
    return items


def aws(arguments, env):
    process = subprocess.run(['/usr/bin/aws'] + arguments, env=env, capture_output=True, text=True, timeout=1800)
    if process.returncode:
        raise RuntimeError('Read-only S3 operation failed: ' + process.stderr[-2000:])
    return json.loads(process.stdout) if arguments[0] == 's3api' else None


def publish(staging, target):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    libc.renameat2.restype = ctypes.c_int
    if libc.renameat2(-100, os.fsencode(staging), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def acquire(request, progress=print):
    guard()
    selected = select(request)
    target = ROOT / RELEASE
    receipt = target / 'prepared-subset-reference.json'
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not receipt.is_file():
            raise RuntimeError('An existing UMLS release needs a matching frozen receipt; nothing overwritten')
        prior = json.loads(receipt.read_text())
        if prior['request'] != request:
            raise RuntimeError('Frozen UMLS selection changed')
        for item in prior['files']:
            path = target / item['relative_path']
            if path.is_symlink() or not path.is_file() or identity(path) != item['identity']:
                raise RuntimeError('Frozen prepared subset changed')
        return prior
    ROOT.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(ROOT).free < sum(x['bytes'] for x in selected) + 30 * 1024 ** 3:
        raise RuntimeError('Insufficient free disk for these inputs plus replay reserve')
    env = dict(os.environ, AWS_PROFILE='meme', AWS_PAGER='', AWS_CLI_AUTO_PROMPT='off')
    staging = Path(tempfile.mkdtemp(prefix='.' + RELEASE + '.inputs-', dir=str(ROOT)))
    result = {'source': 'MTH', 'version': 'MTH_2026AA', 'umls_release': RELEASE, 'request': request,
              'files': [], 'scope': 'Archived prepared subset inputs only; not a regenerated MetamorphoSys run or a complete UMLS installation',
              'aws_profile': 'meme', 'bucket': 'nci-evs-meme', 's3_operations': ['HeadObject', 'GetObject via aws s3 cp'],
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    try:
        # The retained production symlink spells DVDIMAGE/../subset3. The
        # directory must exist for that path to resolve; no JRE is invented.
        (staging / 'DVDIMAGE').mkdir()
        for item in selected:
            relative = item['key'].removeprefix('mr/umls/' + RELEASE + '/')
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            arguments = ['s3api', 'head-object', '--bucket', 'nci-evs-meme', '--key', item['key'], '--output', 'json']
            before = aws(arguments, env)
            if before['ContentLength'] != item['bytes'] or before['ETag'] != item['etag']:
                raise RuntimeError('S3 object differs from the audited selection')
            progress('INPUT: downloading ' + item['key'] + ' (' + str(item['bytes']) + ' bytes)', flush=True)
            aws(['s3', 'cp', 's3://nci-evs-meme/' + item['key'], str(destination), '--no-progress'], env)
            after = aws(arguments, env)
            keys = ['ContentLength', 'ETag', 'LastModified', 'VersionId']
            if any(before.get(k) != after.get(k) for k in keys) or not destination.is_file() or destination.stat().st_size != item['bytes']:
                raise RuntimeError('Object identity changed or download is incomplete')
            observed = identity(destination)
            destination.chmod(0o444)
            result['files'].append({'relative_path': relative, 'object_identity': {k: after.get(k) for k in keys}, 'identity': observed})
            progress('INPUT: frozen ' + str(len(result['files'])) + '/11', flush=True)
        result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        local_receipt = staging / receipt.name
        local_receipt.write_text(json.dumps(result, indent=2) + '\n')
        local_receipt.chmod(0o444)
        publish(staging, target)
        return result
    except BaseException as error:
        (staging / 'acquisition-failed.json').write_text(json.dumps({'error': str(error), 'published': False}) + '\n')
        raise
