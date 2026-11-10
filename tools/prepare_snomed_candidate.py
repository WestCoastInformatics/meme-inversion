#!/usr/bin/env python3
"""Stage only declared SNOMED inputs and production Git code on dev."""
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
import tarfile
import tempfile

ROOT = Path('/local/content/MEME/MEME5/inv')
VERSION = 'SNOMEDCT_US_2026_09_01'
TARGET = ROOT / 'sources' / VERSION
BASELINE = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
CORE_NAMES = {'classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('This SNOMED replay requires tomcata on ncias-d3777-c')
    for path in [ROOT, ROOT / 'sources', TARGET]:
        if path.is_symlink():
            raise RuntimeError('Unexpected symlink: ' + str(path))
    if os.environ.get('INV_HOME') != str(ROOT / 'INV') or os.environ.get('LC_COLLATE') != 'C':
        raise RuntimeError('The mirrored inversion environment must be active')


def info(path):
    digest, rows = hashlib.sha256(), 0
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4194304), b''):
            digest.update(block)
            rows += block.count(b'\n')
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'newline_count': rows}


def require_hash(path, expected):
    if path.is_symlink() or not path.is_file() or info(path)['sha256'] != expected:
        raise RuntimeError('Artifact differs from its pinned hash: ' + str(path))


def save(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def selected_inputs(contract):
    if contract['version'] != VERSION or contract['engine_ref'] != BASELINE or contract['reference_stage'] != 'inversion-src':
        raise RuntimeError('Only the reviewed unchanged-engine SNOMED case is supported')
    if {x['output_name'] for x in contract['reference_file_map']} != CORE_NAMES:
        raise RuntimeError('Five explicit output reference members are required')
    attributes = next(x for x in contract['reference_file_map'] if x['output_name'] == 'attributes.src')
    if attributes['reference_path'] != VERSION + '/src/attributes.orig':
        raise RuntimeError('Inversion attributes must use the pre-enrichment reference')
    inputs = [x for x in contract['conversion_inputs'] if x['required']]
    if len(inputs) != 16 or any(not x['present'] for x in inputs):
        raise RuntimeError('The sixteen required RF2 and historical ICD inputs are required')
    inputs += contract['archived_metadata_inputs']
    paths = {x['path'] for x in inputs}
    metadata = {VERSION + '/src/sources.src', VERSION + '/src/termgroups.src'}
    if len(paths) != 18 or not metadata.issubset(paths):
        raise RuntimeError('Exactly sixteen conversion and two metadata inputs are required')
    for item in inputs:
        relative = PurePosixPath(item['path'])
        if relative.parts[0] != VERSION or '..' in relative.parts or relative.is_absolute():
            raise RuntimeError('Invalid input path')
        if '/src/' in item['path'] and item['path'] not in metadata:
            raise RuntimeError('Generated output cannot seed a candidate')
        if not (item['path'] in metadata or '/orig/fromprovider/' in item['path'] or item['path'] in
                {VERSION + '/etc/icd10.inmeta', VERSION + '/etc/icd10cm.inmeta'}):
            raise RuntimeError('Undeclared input category')
    return {x['path']: x for x in inputs}


def publish(staging, target):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    libc.renameat2.restype = ctypes.c_int
    if libc.renameat2(-100, os.fsencode(staging), -100, os.fsencode(target), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def prepare(contract, code_files, progress=print, generated_configuration=None, configuration_generation_inputs=None):
    guard()
    allowed = selected_inputs(contract)
    if generated_configuration is not None:
        import snomed_configuration
        snomed_configuration.validate_execution_recipe(generated_configuration, configuration_generation_inputs,
                                                       contract=contract, code_files=code_files)
    elif configuration_generation_inputs is not None:
        raise ValueError('Configuration-generation inputs require a generated recipe')
    if TARGET.exists() or TARGET.is_symlink():
        raise RuntimeError('Candidate already exists; no replacement is permitted')
    archive = Path(contract['reference']['archive_path'])
    if archive != ROOT / 'sources' / (VERSION + '.tgz'):
        raise RuntimeError('The frozen archive must remain at the standard path')
    require_hash(archive, contract['reference']['archive_sha256'])
    if shutil.disk_usage(ROOT).free < 50 * 1024 ** 3:
        raise RuntimeError('At least 50 GiB of free disk is required for this case')
    expected_code = {'bin/invert.s', 'bin/invert_rf2.pl', 'bin/rmdanglingattrs.pl', 'etc/README.txt', 'etc/sct.cfg'}
    if {x['relative_path'] for x in code_files} != expected_code:
        raise RuntimeError('The five production source-code/configuration files are required')
    staging = Path(tempfile.mkdtemp(prefix='.' + VERSION + '.prepare-', dir=str(ROOT / 'sources')))
    result = {'source': 'SNOMEDCT_US', 'version': VERSION, 'engine_ref': BASELINE,
              'started_at': now(), 'archive_sha256': contract['reference']['archive_sha256'],
              'generated_outputs_seeded': False, 'insertion_executed': False, 'inputs': [], 'code': []}
    try:
        for directory in ['bin', 'etc/qa', 'orig', 'tmp', 'src', 'insert']:
            (staging / directory).mkdir(parents=True, exist_ok=True)
        found = set()
        with tarfile.open(archive, 'r|gz') as tar:
            for member in tar:
                name = member.name.removeprefix('./')
                if name not in allowed:
                    continue
                if name in found or not member.isfile():
                    raise RuntimeError('Duplicate or nonregular selected archive input')
                item = allowed[name]
                if member.size != item['size']:
                    raise RuntimeError('Selected input size changed')
                path = staging / str(PurePosixPath(name).relative_to(VERSION))
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 4194304)
                observed = info(path)
                if observed['sha256'] != item['sha256'] or observed['newline_count'] != item['newline_count']:
                    raise RuntimeError('Selected input identity changed')
                path.chmod(0o444)
                result['inputs'].append({'path': name, **observed})
                found.add(name)
                progress('Prepared input ' + str(len(found)) + '/18: ' + name, flush=True)
        if found != set(allowed):
            raise RuntimeError('Not all selected inputs were found')
        for item in code_files:
            raw = base64.b64decode(item['data_b64'], validate=True)
            if hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise RuntimeError('Source code bundle hash mismatch')
            if generated_configuration is not None and item['relative_path'] == 'etc/sct.cfg':
                # The captured cfg is the immutable template/oracle, not a seed
                # file.  Only the recomputed recipe writes the operational cfg.
                result['configuration_templates'] = [{k: item[k] for k in ['relative_path', 'sha256', 'mode']}]
                continue
            path = staging / item['relative_path']
            with path.open('xb') as out:
                out.write(raw)
            path.chmod(int(item['mode'], 8))
            result['code'].append({k: item[k] for k in ['relative_path', 'sha256', 'mode']})
        if generated_configuration is not None:
            for item in generated_configuration['files']:
                path = staging / item['relative_path']
                with path.open('xb') as out:
                    out.write(base64.b64decode(item['data_b64'], validate=True))
                path.chmod(int(item['mode'], 8))
            snomed_configuration.verify_generated(generated_configuration, staging)
            result['configuration_generation'] = snomed_configuration.receipt(generated_configuration)
            result['configuration_seeded_from_code_files'] = False
        sources = (staging / 'src/sources.src').read_text().splitlines()
        if len(sources) != 1 or sources[0].split('|')[:2] != [VERSION, 'SNOMEDCT_US_2026_03_01']:
            raise RuntimeError('Historical source/replacement metadata does not agree with the selected case')
        result['replacement_baseline_verified'] = 'SNOMEDCT_US_2026_03_01'
        result['completed_at'] = now()
        save(staging / 'etc/replay-case.json', contract)
        save(staging / 'etc/replay-preparation.json', result)
        publish(staging, TARGET)
        return result
    finally:
        if staging.exists():
            shutil.rmtree(staging)
