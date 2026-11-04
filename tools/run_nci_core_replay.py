#!/usr/bin/env python3
"""Run the pinned October NCIt core on dev and compare its five src outputs.

This is a bounded characterization case, not the proposed general replay runner.
It deliberately excludes metadata acquisition, legacy QA and insertion.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import socket
import subprocess
import tempfile
import time

ROOT = Path('/local/content/MEME/MEME5/inv')
VERSION = 'NCI_2026_10D'


def info(path):
    digest = hashlib.sha256()
    lines = 0
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
            lines += block.count(b'\n')
    return {'path': str(path), 'bytes': path.stat().st_size,
            'sha256': digest.hexdigest(), 'newline_count': lines}


def save(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(contract, expected_code, expected_runtime, progress=print, timeout_seconds=7200):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('This characterization is scoped to tomcata on dev')
    if contract['version'] != VERSION or contract['reference_stage'] != 'inversion-src':
        raise RuntimeError('Unexpected characterization case')
    target = ROOT / 'sources' / VERSION
    receipt = target / 'etc/replay-core.json'
    if receipt.exists() or receipt.is_symlink():
        raise RuntimeError('A core replay receipt already exists; existing runs are preserved')
    if target.is_symlink() or (target / 'src').is_symlink():
        raise RuntimeError('Candidate directories must not be symlinks')
    case = json.loads((target / 'etc/replay-case.json').read_text())
    preparation_ref = contract.get('preparation_engine_ref', contract['engine_ref'])
    if case['engine_ref'] != preparation_ref or not case['preparation_matches_reference']:
        raise RuntimeError('Candidate preparation is not the verified pinned case')
    expected_environment = {'INV_HOME': str(ROOT / 'INV'), 'SRC_ROOT': str(ROOT / 'sources'),
                            'LC_COLLATE': 'C', 'TMP_DIR': '/tmp'}
    if any(os.environ.get(key) != value for key, value in expected_environment.items()):
        raise RuntimeError('Unexpected inversion environment')
    if {path.name for path in (target / 'src').iterdir()} != {'sources.src', 'termgroups.src'}:
        raise RuntimeError('The candidate must not contain generated src outputs before execution')
    checks = []
    for item in contract['native_inputs'] + contract['archived_metadata_inputs'] + contract['preparation_reference_files']:
        path = ROOT / 'sources' / item['path']
        checks.append((path, item['sha256']))
    for item in expected_code:
        checks.append((target / item['relative_path'], item['sha256']))
    for item in expected_runtime:
        path = Path(item['path'])
        if not path.is_relative_to(ROOT) or path.is_symlink():
            raise RuntimeError('Unexpected installed runtime path')
        checks.append((path, item['sha256']))
    for path, expected in checks:
        if path.is_symlink() or info(path)['sha256'] != expected:
            raise RuntimeError('Pinned input or code changed: ' + str(path))
    archive = Path(contract['reference']['archive_path'])
    if archive != ROOT / 'sources' / (VERSION + '.tgz') or info(archive)['sha256'] != contract['reference']['archive_sha256']:
        raise RuntimeError('Frozen reference archive changed')
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = {'source': 'NCI', 'version': VERSION, 'engine_ref': contract['engine_ref'],
              'preparation_engine_ref': preparation_ref, 'run_id': contract.get('run_id'),
              'case_variant': contract['case_variant'], 'reference_stage': 'inversion-src',
              'host': socket.gethostname(), 'candidate_path': str(target), 'started_at': started,
              'archive_sha256': contract['reference']['archive_sha256'],
              'network': 'disabled', 'metadata_inputs': ['sources.src', 'termgroups.src'],
              'core_inverter_executed': False, 'insertion_preparation_executed': False,
              'verified_input_and_code_files': len(checks), 'comparison': [],
              'coverage': 'Five core src outputs from regenerated TREF and archived source metadata',
              'independent_semantic_validation': 'pending', 'status': 'running',
              'timeout_seconds': timeout_seconds}
    with receipt.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    log = target / 'etc/qa/replay-core-inversion.log'
    command = ['unshare', '--user', '--map-root-user', '--net', '/usr/bin/perl', 'invert_NCI.pl']
    result.update(command=command, log=str(log), core_inverter_executed=True)
    progress('PHASE: running pinned NCIt inverter with network disabled', flush=True)
    try:
        with log.open('xb') as handle:
            process = subprocess.Popen(command, cwd=target / 'bin', stdout=handle, stderr=subprocess.STDOUT,
                                       env=os.environ.copy())
            result['core_pid'] = process.pid
            save(receipt, result)
            deadline = time.monotonic() + timeout_seconds
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    process.kill()
                    process.wait()
                    raise subprocess.TimeoutExpired(command, timeout_seconds)
                try:
                    process.wait(timeout=min(30, remaining))
                    break
                except subprocess.TimeoutExpired:
                    sizes = {p.name: p.stat().st_size for p in (target / 'src').glob('*.src')}
                    progress('PROGRESS: ' + json.dumps(sizes), flush=True)
        result['exit_status'] = process.returncode
    except subprocess.TimeoutExpired:
        result.update(exit_status=None, error='Core inversion exceeded the configured time limit')
    result['inverter_completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(receipt, result)
    progress('PHASE: comparing fresh core src files with frozen October src hashes', flush=True)
    for item in contract['core_outputs_to_regenerate']:
        path = target / str(PurePosixPath(item['path']).relative_to(VERSION))
        observed = info(path) if path.is_file() and not path.is_symlink() else {'path': str(path), 'missing': True}
        observed.update(expected_sha256=item['sha256'], expected_newline_count=item['newline_count'],
                        exact_match=observed.get('sha256') == item['sha256'])
        result['comparison'].append(observed)
    result['metadata_unchanged'] = all(info(ROOT / 'sources' / item['path'])['sha256'] == item['sha256']
                                       for item in contract['archived_metadata_inputs'])
    result['all_five_exact_match'] = len(result['comparison']) == 5 and all(item['exact_match'] for item in result['comparison'])
    result['status'] = ('core-src-exact-match' if result['exit_status'] == 0 and result['all_five_exact_match']
                        and result['metadata_unchanged'] else 'core-src-differences-require-review')
    result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['log_info'] = info(log)
    save(receipt, result)
    return result
