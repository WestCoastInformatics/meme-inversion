#!/usr/bin/env python3
"""Prepare a clean, standard-path NCIt candidate and characterize native preparation.

Only declared publisher/source-metadata inputs are copied from the retained
archive. Completed inversion outputs are inspected as references, never seeded.
"""
import base64
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import socket
import subprocess
import tarfile
import tempfile

ROOT = Path('/local/content/MEME/MEME5/inv/sources')
VERSION = 'NCI_2026_10D'


def file_info(path):
    h = hashlib.sha256()
    lines = 0
    with path.open('rb') as handle:
        for data in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            h.update(data)
            lines += data.count(b'\n')
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest(), 'newline_count': lines}


def save(path, data):
    fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.write-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def prepare(contract, code_files, progress=print):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('This characterization is scoped to tomcata on dev')
    target = ROOT / VERSION
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError('Unexpected standard source root')
    if target.exists() or target.is_symlink():
        raise RuntimeError('Candidate folder already exists; no existing source data was changed')
    archive = Path(contract['reference']['archive_path'])
    if archive != ROOT / (VERSION + '.tgz') or archive.is_symlink():
        raise RuntimeError('Unexpected frozen-reference location')
    if file_info(archive)['sha256'] != contract['reference']['archive_sha256']:
        raise RuntimeError('Frozen archive hash differs from the reviewed reference')
    allowed = {x['path']: x for x in contract['native_inputs'] + contract['archived_metadata_inputs']}
    metadata_names = {VERSION + '/src/sources.src', VERSION + '/src/termgroups.src'}
    native_names = {x['path'] for x in contract['native_inputs']}
    if len(allowed) != 7 or len(native_names) != 5 or set(allowed) - native_names != metadata_names or not all(x.startswith(VERSION + '/orig/fromprovider/') for x in native_names):
        raise RuntimeError('The initial candidate must contain five native and two metadata inputs only')
    if os.environ.get('INV_HOME') != '/local/content/MEME/MEME5/inv/INV' or os.environ.get('LC_COLLATE') != 'C':
        raise RuntimeError('The configured inversion environment must be active')
    baseline_sha = contract['engine_ref']
    result = {'source': 'NCI', 'version': VERSION, 'engine_ref': baseline_sha,
              'environment_profile': 'ncias-d3777-c', 'case_variant': contract['case_variant'],
              'reference_stage': 'inversion-src', 'archive_sha256': contract['reference']['archive_sha256'],
              'candidate_path': str(target), 'inputs': [], 'code': [], 'stages': [],
              'core_inverter_executed': False, 'insertion_preparation_executed': False,
              'coverage': 'Native/TREF preparation with archived source metadata; metadata acquisition, QA, insertion excluded'}
    staging = Path(tempfile.mkdtemp(prefix='.' + VERSION + '.prepare-', dir=str(ROOT)))
    atom_ids = set()
    atom_rows = 0
    atom_invalid_ids = 0
    try:
        for name in ['bin', 'etc/qa', 'orig/fromprovider', 'tmp', 'src']:
            (staging / name).mkdir(parents=True, exist_ok=True)
        progress('PHASE: staging only declared input members; completed src output is excluded', flush=True)
        with tarfile.open(archive, mode='r|gz') as tar:
            for member in tar:
                name = PurePosixPath(member.name).as_posix()
                if name == VERSION + '/src/classes_atoms.src':
                    h = hashlib.sha256()
                    for line in tar.extractfile(member):
                        h.update(line)
                        atom_rows += 1
                        try:
                            atom_ids.add(int(line.split(b'|', 1)[0]))
                        except ValueError:
                            atom_invalid_ids += 1
                    expected_atoms = next(x for x in contract['core_outputs_to_regenerate'] if x['path'] == name)
                    if h.hexdigest() != expected_atoms['sha256']:
                        raise RuntimeError('Atom-ID evidence differs from the frozen reference')
                if name not in allowed:
                    continue
                if not member.isfile():
                    raise RuntimeError('Declared input is not a regular archive member')
                relative = PurePosixPath(name).relative_to(VERSION)
                path = staging / str(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                h = hashlib.sha256()
                with path.open('xb') as handle:
                    source = tar.extractfile(member)
                    for data in iter(lambda: source.read(4 * 1024 * 1024), b''):
                        h.update(data)
                        handle.write(data)
                if h.hexdigest() != allowed[name]['sha256']:
                    raise RuntimeError('Candidate input hash differs from frozen member: ' + name)
                path.chmod(member.mode & 0o777)
                os.utime(path, (member.mtime, member.mtime))
                result['inputs'].append({'relative_path': str(relative), 'sha256': h.hexdigest(), 'bytes': member.size})
        if len(result['inputs']) != len(allowed) or atom_invalid_ids or not atom_ids:
            raise RuntimeError('Incomplete input or historical-ID evidence')
        for f in code_files:
            relative = PurePosixPath(f['path']).relative_to('sources/' + VERSION)
            path = staging / str(relative)
            if path.exists() or '..' in relative.parts or relative.parts[0] not in ('bin', 'etc'):
                raise RuntimeError('Unexpected code bundle path')
            raw = base64.b64decode(f['data_b64'], validate=True)
            if hashlib.sha256(raw).hexdigest() != f['sha256']:
                raise RuntimeError('Pinned code hash mismatch')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(int(f['mode'], 8))
            result['code'].append({'relative_path': str(relative), 'sha256': f['sha256']})
        if {x.name for x in (staging / 'src').iterdir()} != {'sources.src', 'termgroups.src'}:
            raise RuntimeError('Candidate was seeded with undeclared generated output')
        result['reference_atom_id_evidence'] = {'rows': atom_rows, 'unique_ids': len(atom_ids),
            'minimum': min(atom_ids), 'maximum': max(atom_ids), 'contiguous': len(atom_ids) == max(atom_ids) - min(atom_ids) + 1,
            'scope': 'Observed official output IDs for isolated replay; not a production allocation receipt'}
        del atom_ids
        result['candidate_prepared_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['src_seed_files'] = ['sources.src', 'termgroups.src']
        save(staging / 'etc/replay-case.json', result)
        staging.chmod(ROOT.stat().st_mode & 0o777)
        libc = ctypes.CDLL(None, use_errno=True)
        libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        libc.renameat2.restype = ctypes.c_int
        if libc.renameat2(-100, os.fsencode(staging), -100, os.fsencode(target), 1):
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number))
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    def stage(name, args, stdout_path=None):
        log = target / ('etc/qa/replay-' + name + '.log')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        progress('PHASE: ' + name, flush=True)
        with log.open('wb') as errors:
            output = stdout_path.open('wb') if stdout_path else errors
            try:
                p = subprocess.run(['unshare', '--user', '--map-root-user', '--net'] + args,
                                   cwd=target / 'bin', stdout=output, stderr=errors, timeout=300, env=os.environ.copy())
                status, error = p.returncode, None
            except subprocess.TimeoutExpired:
                status, error = None, 'Stage exceeded the 300-second limit'
            finally:
                if stdout_path:
                    output.close()
        item = {'name': name, 'args': args, 'status': status, 'started_at': started,
                'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'log': str(log), 'network': 'disabled'}
        if error:
            item['error'] = error
        result['stages'].append(item)
        result['status'] = 'native-preparation-running' if status == 0 else 'native-preparation-stage-failed'
        save(target / 'etc/replay-case.json', result)
        if status != 0:
            raise RuntimeError('Preparation stage failed: ' + name + '; see ' + str(log))

    stage('role-groups', ['/usr/bin/perl', 'create_rolegroups.pl'])
    stage('sort-role-groups', ['/usr/bin/sort', '../tmp/rolegroups.tmp', '-o', '../tmp/rolegroups.sorted.tmp'])
    stage('repeated-role-groups', ['/usr/bin/uniq', '-d', '../tmp/rolegroups.sorted.tmp'], target / 'orig/rels_needing_relgrp.txt')
    stage('create-tref', ['/usr/bin/perl', 'create_tref.pl'])
    stage('deduplicate-tref', ['/usr/bin/perl', 'delete_dup_tref_lines.pl'])
    comparisons = []
    for f in contract['preparation_reference_files']:
        path = target / str(PurePosixPath(f['path']).relative_to(VERSION))
        observed = file_info(path)
        observed.update(expected_sha256=f['sha256'], exact_match=observed['sha256'] == f['sha256'])
        comparisons.append(observed)
    result['preparation_comparison'] = comparisons
    result['preparation_matches_reference'] = all(x['exact_match'] for x in comparisons)
    result['core_outputs_present'] = [x.name for x in (target / 'src').iterdir() if x.name not in result['src_seed_files']]
    result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['status'] = 'native-preparation-matches-reference' if result['preparation_matches_reference'] else 'native-preparation-differences-require-review'
    for f in result['inputs']:
        if file_info(target / f['relative_path'])['sha256'] != f['sha256']:
            raise RuntimeError('A declared input was modified during native preparation')
    save(target / 'etc/replay-case.json', result)
    return result
