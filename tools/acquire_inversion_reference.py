#!/usr/bin/env python3
"""Freeze a declared source/version archive with the existing pull helper.

Download only; never extract a completed inversion into the candidate. This
read-only S3 operation is shared by NCIt/SNOMED/MTH reference preparation.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import tempfile

from inspect_inversion_archive import inspect

ROOT = Path('/local/content/MEME/MEME5/inv/sources')
PULL = Path('/local/content/MEME/MEME5/ncim/bin/pull_s3.csh')


def save(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def acquire(request, progress=print):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Reference preparation is scoped to tomcata on dev')
    source, version = request['source'], request['version']
    if source not in {'NCI', 'SNOMEDCT_US', 'MTH'} or not re.fullmatch(re.escape(source) + r'_[A-Za-z0-9_]+', version):
        raise RuntimeError('Invalid source/version')
    if ROOT.is_symlink() or not ROOT.is_dir() or PULL.is_symlink():
        raise RuntimeError('Unexpected standard path')
    if hashlib.sha256(PULL.read_bytes()).hexdigest() != request['pull_helper_sha256']:
        raise RuntimeError('The installed pull helper differs from the reviewed version')
    archive = ROOT / (version + '.tgz')
    reference = ROOT / (version + '.tgz.reference.json')
    inventory_path = ROOT / (version + '.tgz.inventory.json')
    lock = ROOT / ('.' + version + '.reference.lock')
    with lock.open('x') as handle:
        handle.write(str(os.getpid()))
    try:
        env = dict(os.environ, AWS_PROFILE='meme', AWS_BIN='/usr/bin/aws', AWS_PAGER='', AWS_CLI_AUTO_PROMPT='off')
        key = 'inv/sources/' + version + '.tgz'

        def head():
            process = subprocess.run(['/usr/bin/aws', 's3api', 'head-object', '--bucket', 'nci-evs-meme',
                                      '--key', key, '--output', 'json'], capture_output=True, text=True, env=env, timeout=30)
            if process.returncode:
                raise RuntimeError('Archive metadata read failed: ' + process.stderr)
            metadata = json.loads(process.stdout)
            return {name: metadata.get(name) for name in ['ContentLength', 'ETag', 'LastModified', 'VersionId']}

        prior = json.loads(reference.read_text()) if reference.is_file() else None
        if archive.exists():
            if archive.is_symlink() or prior is None or prior['source'] != source or prior['version'] != version:
                raise RuntimeError('Existing archives require a matching frozen-reference receipt; nothing was overwritten')
            identity = prior['object_identity']
            downloaded = False
        else:
            if prior is not None:
                raise RuntimeError('A frozen reference file is missing; do not substitute a newer object silently')
            identity = head()
            free = os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize
            if identity['ContentLength'] + 1024 ** 3 > free:
                raise RuntimeError('Insufficient free disk for archive retention')
            progress('PHASE: downloading ' + version + ' without extraction', flush=True)
            process = subprocess.run(['tcsh', '-f', str(PULL), 'inv', version, '--download-only'],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=900)
            if process.returncode:
                raise RuntimeError('Download failed; partial files retained for inspection: ' + process.stdout.decode(errors='replace'))
            if archive.stat().st_size != identity['ContentLength'] or head() != identity:
                raise RuntimeError('Downloaded object identity/size changed; file retained for review')
            archive.chmod(0o444)
            downloaded = True
        progress('PHASE: hashing/inventorying ' + version + '; no source folder restored', flush=True)
        audit = inspect(archive, version, progress=lambda count, name: progress('AUDIT: ' + str(count) + ' members', flush=True) if count % 50 == 0 else None)
        if prior and audit['archive_sha256'] != prior['archive_sha256']:
            raise RuntimeError('Frozen reference bytes changed')
        expected = {item['path']: item['sha256'] for item in request['expected_code']}
        observed = {item['path']: item['sha256'] for item in audit['entries'] if item['kind'] == 'file' and item['path'] in expected}
        comparisons = [{'path': path, 'expected_sha256': sha, 'archive_sha256': observed.get(path),
                        'matches_snapshot': observed.get(path) == sha} for path, sha in expected.items()]
        result = {'source': source, 'version': version, 'engine_ref': request['engine_ref'], 'bucket': 'nci-evs-meme',
                  'key': key, 'aws_profile': 'meme', 'archive_path': str(archive), 'object_identity': identity,
                  'archive_sha256': audit['archive_sha256'], 'archive_bytes': audit['archive_bytes'],
                  'downloaded_this_run': downloaded, 'archive_read_only': not bool(archive.stat().st_mode & 0o222),
                  'member_count': audit['member_count'], 'regular_file_bytes': audit['regular_file_bytes'],
                  'code_comparison': comparisons, 'code_comparison_performed': bool(comparisons),
                  'code_matches_snapshot': all(item['matches_snapshot'] for item in comparisons) if comparisons else None,
                  'stages': audit['stages'], 'metadata_summary': audit['metadata_summary'],
                  'inventory_path': str(inventory_path), 'receipt_path': str(reference),
                  'source_directory_exists': (ROOT / version).exists(), 'extracted': False, 'candidate_executed': False,
                  'pull_helper_sha256': request['pull_helper_sha256'], 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        save(inventory_path, audit)
        save(reference, result)
        return result
    finally:
        lock.unlink()
