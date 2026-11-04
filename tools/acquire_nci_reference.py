#!/usr/bin/env python3
"""Test/deploy the reviewed pull helper, then freeze and inspect the NCIt reference."""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import tempfile
import uuid

from check_pull_s3 import check
from inspect_inversion_archive import inspect

ROOT = Path('/local/content/MEME/MEME5/inv/sources')
PULL = Path('/local/content/MEME/MEME5/ncim/bin/pull_s3.csh')
VERSION = 'NCI_2026_10D'
KEY = 'inv/sources/' + VERSION + '.tgz'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic_write(path, raw, mode):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.write-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def acquire(pull_source, expected_previous_sha, baseline_files, source_commit, progress=print):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Reference preparation is scoped to tomcata on ncias-d3777-c')
    if PULL.is_symlink() or not PULL.is_file() or not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError('Unexpected standard tool/source path')
    proposed_sha = sha(pull_source)
    previous = PULL.read_bytes()
    if sha(previous) not in (expected_previous_sha, proposed_sha):
        raise RuntimeError('Dev pull script changed since review')
    progress('PHASE: offline pull-script fixture checks', flush=True)
    with tempfile.TemporaryDirectory(prefix='.pull-review-', dir=str(ROOT)) as temp:
        script = Path(temp) / 'pull_s3.csh'
        script.write_bytes(pull_source)
        checks = check(script)
    progress('PHASE: ' + str(checks['passed']) + ' pull-script checks passed', flush=True)
    backup = None
    if previous != pull_source:
        if PULL.read_bytes() != previous:
            raise RuntimeError('Dev pull script changed during fixture checks')
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = PULL.with_name(PULL.name + '.before-reference-' + stamp)
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(previous)
        mode = PULL.stat().st_mode & 0o777
        atomic_write(PULL, pull_source, mode)
    if sha(PULL.read_bytes()) != proposed_sha:
        raise RuntimeError('Deployed pull-script hash mismatch')
    tool_receipt = {'path': str(PULL), 'base_ref': 'production-snapshot-20261103',
                    'sha256': proposed_sha, 'previous_sha256': sha(previous),
                    'backup': str(backup) if backup else None, 'checks': checks,
                    'changes': ['Optional download-only and keep-archive modes for inversion archives',
                                'AWS_PROFILE and optional AWS_BIN supplied through the environment',
                                'Invalid arguments and failed transfers/extractions return failure',
                                'Existing local archives are not overwritten'],
                    'profile_selected_for_this_job': 'meme'}
    tool_receipt_path = PULL.with_name(PULL.name + '.reference-setup.json')
    atomic_write(tool_receipt_path, (json.dumps(tool_receipt, indent=2) + '\n').encode(), 0o644)
    archive = ROOT / (VERSION + '.tgz')
    receipt_path = ROOT / (VERSION + '.tgz.reference.json')
    inventory_path = ROOT / (VERSION + '.tgz.inventory.json')
    lock = ROOT / ('.' + VERSION + '.reference.lock')
    lock_value = (str(os.getpid()) + ':' + uuid.uuid4().hex).encode()
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(lock_value)
    try:
        env = dict(os.environ, AWS_PROFILE='meme', AWS_BIN='/usr/bin/aws', AWS_PAGER='',
                   AWS_CLI_AUTO_PROMPT='off', AWS_METADATA_SERVICE_TIMEOUT='2', AWS_METADATA_SERVICE_NUM_ATTEMPTS='1')

        def head():
            p = subprocess.run(['/usr/bin/aws', 's3api', 'head-object', '--bucket', 'nci-evs-meme', '--key', KEY, '--output', 'json'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, env=env)
            if p.returncode:
                raise RuntimeError('Archive metadata read failed: ' + p.stderr.decode(errors='replace'))
            data = json.loads(p.stdout)
            return {k: data.get(k) for k in ['ContentLength', 'ETag', 'LastModified', 'VersionId']}

        old_receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
        if archive.exists():
            if archive.is_symlink() or old_receipt is None:
                raise RuntimeError('An existing local archive requires a matching frozen-reference receipt; nothing was overwritten')
            identity = old_receipt['object_identity']
            downloaded = False
        else:
            if old_receipt is not None:
                raise RuntimeError('The frozen reference archive is missing; do not silently substitute a newer object')
            identity = head()
            free = os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize
            if identity['ContentLength'] + 1024 ** 3 > free:
                raise RuntimeError('Insufficient free disk for the retained reference download')
            progress('PHASE: downloading official archive at standard source path', flush=True)
            p = subprocess.run(['tcsh', '-f', str(PULL), 'inv', VERSION, '--download-only'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600, env=env)
            if p.returncode:
                raise RuntimeError('Archive acquisition failed: ' + p.stdout.decode(errors='replace'))
            if not archive.is_file() or archive.stat().st_size != identity['ContentLength']:
                raise RuntimeError('Downloaded archive size differs from S3 metadata')
            if head() != identity:
                raise RuntimeError('Official archive identity changed during acquisition; the downloaded file was retained for review')
            archive.chmod(0o444)
            downloaded = True
        progress('PHASE: hashing and inventorying completed archive; no extraction', flush=True)

        def audit_progress(count, path):
            if count % 25 == 0:
                progress('AUDIT: ' + str(count) + ' members', flush=True)

        audit = inspect(archive, VERSION, progress=audit_progress)
        if old_receipt and audit['archive_sha256'] != old_receipt['archive_sha256']:
            raise RuntimeError('Frozen archive content changed since its receipt')
        native = [x for x in audit['entries'] if x['role'] == 'publisher-input' and x['kind'] == 'file']
        expected = {x['repository_path']: x for x in baseline_files}
        code_comparison = []
        for item in audit['entries']:
            repository_path = 'sources/' + item['path']
            if item['kind'] == 'file' and repository_path in expected:
                baseline = expected[repository_path]
                code_comparison.append({'path': item['path'], 'archive_sha256': item['sha256'],
                                        'matches_captured_production': item['sha256'] == baseline['sha256'],
                                        'matches_committed_snapshot': item['sha256'] == baseline['imported_sha256']})
        stage_maps = {stage: {x['path'].split('/')[-1]: x for x in audit['stages'][stage]} for stage in ('src', 'insert')}
        overlap = [{'name': name, 'same_sha256': stage_maps['src'][name]['sha256'] == stage_maps['insert'][name]['sha256']}
                   for name in sorted(set(stage_maps['src']) & set(stage_maps['insert']))]
        result = {'source': 'NCI', 'version': VERSION, 'engine_ref': source_commit,
                  'environment_profile': 'ncias-d3777-c', 'bucket': 'nci-evs-meme', 'key': KEY,
                  'aws_profile': 'meme', 'archive_path': str(archive), 'object_identity': identity,
                  'archive_sha256': audit['archive_sha256'], 'archive_bytes': audit['archive_bytes'],
                  'downloaded_this_run': downloaded, 'archive_read_only': archive.stat().st_mode & 0o222 == 0,
                  'member_count': audit['member_count'], 'regular_file_bytes': audit['regular_file_bytes'],
                  'native_files': [{k: x[k] for k in ['path', 'size', 'sha256']} for x in native],
                  'stages': audit['stages'], 'stage_overlap': overlap, 'metadata_summary': audit['metadata_summary'],
                  'code_comparison': code_comparison, 'pull_tool': tool_receipt,
                  'inventory_path': str(inventory_path), 'receipt_path': str(receipt_path),
                  'source_directory_exists': (ROOT / VERSION).exists(), 'extracted': False,
                  'candidate_executed': False, 'case_status': 'reference-frozen-input-output-review-pending',
                  'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        atomic_write(inventory_path, (json.dumps(audit, indent=2) + '\n').encode(), 0o444)
        atomic_write(receipt_path, (json.dumps(result, indent=2) + '\n').encode(), 0o444)
        return result
    finally:
        if lock.exists() and lock.read_bytes() == lock_value:
            lock.unlink()
