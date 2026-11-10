#!/usr/bin/env python3
"""Independently rehash the completed NCIt source-plan run and preserved data."""
import base64
import copy
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import sys

ROOT = Path('/local/content/MEME/MEME5/inv')
RUN_ID = 'common-nci-source-plan-v2-20261110'
LOCK_SHA256 = '6fba98b73f86e429890fe7f12a8e91bc4475e7913b41edabf09782902c4d8026'
ORIGINAL_LOCK_SHA256 = '0d7090f53d9c67ec241b379948516f496aae27ca74dce55b60e47c0a7df18eaf'
SOURCE_ENGINE = 'b6c60b46602cb77e9ae8c5cc27d8a659362ecd78'
APPARATUS = '0df06fa39ad36733a0f786db4ac4139b81f8aea4'
CONTROL = ROOT / 'qa/replay-requests' / RUN_ID
CONTROLLER = CONTROL.with_name(RUN_ID + '.controller')
TARGET = ROOT / 'sources/NCI_2026_10D'


def load(path):
    assert not path.is_symlink(), str(path)
    return json.loads(path.read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def info(path):
    assert not path.is_symlink() and path.is_file(), str(path)
    value = hashlib.sha256();size = count = 0
    with path.open('rb') as handle:
        for raw in iter(lambda: handle.read(4194304), b''):
            value.update(raw);size += len(raw);count += raw.count(b'\n')
    return {'bytes': size, 'sha256': value.hexdigest(), 'newline_count': count}


def require(path, expected):
    actual = info(path)
    assert actual['sha256'] == expected, str(path)
    return actual


assert socket.gethostname().split('.')[0] == 'ncias-d3777-c'
assert pwd.getpwuid(os.getuid()).pw_name == 'tomcata'
with (ROOT / '.replay-runtime.lock').open('r') as held:
    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = load(CONTROL / 'status.json');controller = load(CONTROLLER / 'status.json')
    lock = load(CONTROL / 'case.lock.json');original = load(CONTROLLER / 'original-runtime.lock.json')
    result = load(CONTROL / 'result.json');preparation = load(CONTROL / 'preparation.json')
    assert state['status'] == controller['status'] == 'complete'
    assert controller['restored_original_runtime_files_verified'] == 169
    assert result['acceptance']['status'] == 'PASS_EQUIVALENT'
    assert not result['production_eligible'] and not result['insertion_executed']
    assert lock['lock_sha256'] == result['lock_sha256'] == state['lock_sha256'] == LOCK_SHA256
    assert lock['request']['engine_ref'] == SOURCE_ENGINE and lock['apparatus_ref'] == APPARATUS
    assert digest({k: v for k, v in lock.items() if k != 'lock_sha256'}) == LOCK_SHA256
    assert original['lock_sha256'] == ORIGINAL_LOCK_SHA256
    assert digest({k: v for k, v in original.items() if k != 'lock_sha256'}) == ORIGINAL_LOCK_SHA256
    expected_modules = {Path(x['repository_path']).name: x['sha256'] for x in lock['provenance'] if x['repository_path'].startswith('tools/')}
    for name, encoded in lock['modules_b64'].items():
        assert hashlib.sha256(base64.b64decode(encoded)).hexdigest() == expected_modules[name]
        require(CONTROL / 'apparatus' / name, expected_modules[name])
        require(CONTROLLER / 'apparatus' / name, expected_modules[name])
    sys.dont_write_bytecode = True;sys.path.insert(0, str(CONTROL / 'apparatus'))
    import inversion_worker, nci_configuration
    inversion_worker.verify_lock(lock)
    recipe = nci_configuration.from_lock(lock)
    assert recipe['profile'] == 'nci-source-plan-v1' and len(recipe['files']) == 5
    assert recipe['bindings']['metadata_inputs'] == []
    assert result['configuration_generation'] == nci_configuration.receipt(recipe)
    generated = {}
    for item in recipe['files']:
        path = TARGET / item['relative_path']
        generated[item['relative_path']] = require(path, item['sha256'])
        assert path.stat().st_mode & 0o222 == 0, str(path)
    nci_configuration.verify_metadata(recipe, TARGET)
    assert {(x['kind'], x['identifier']) for x in result['source_plan_preflight']['historical_findings']} == {
        ('unmapped-publisher-source', 'CTCAE 6.0'), ('unverified-termgroup-ranking', 'CELLOSAURUS_2026_10D/SY')}
    assert result['source_plan_preflight'] == preparation['source_plan_preflight']
    assert result['source_plan_preflight']['status'] == 'PASS_HISTORICAL_WITH_DECLARED_FINDINGS'
    assert len(preparation['inputs']) == 5 and all(x['relative_path'].startswith('orig/fromprovider/') for x in preparation['inputs'])
    assert preparation['preparation_matches_reference'] and len(preparation['preparation_comparison']) == 3
    assert all(x['exact_match'] for x in preparation['preparation_comparison'])
    data = lock['case']['legacy_case']
    for item in data['native_inputs'] + data['preparation_reference_files'] + data['archived_metadata_inputs']:
        require(ROOT / 'sources' / item['path'], item['sha256'])
    require(Path(data['reference']['archive_path']), data['reference']['archive_sha256'])
    assert len(lock['code_files']) == 4
    for item in lock['code_files']:
        path = TARGET / item['relative_path'];require(path, item['sha256'])
        assert path.stat().st_mode & 0o777 == int(item['mode'], 8)
    previous = load(CONTROL / 'previous-source-receipt.json')
    assert digest({k: v for k, v in previous.items() if k != 'receipt_sha256'}) == previous['receipt_sha256']
    preserved = TARGET.with_name(TARGET.name + '.before-' + RUN_ID)
    paths = set()
    for base, dirs, files in os.walk(preserved, followlinks=False):
        paths.update(str((Path(base) / name).relative_to(preserved)) for name in dirs + files)
    assert paths == {x['path'] for x in previous['manifest']}
    for item in previous['manifest']:
        path = preserved / item['path']
        if item['kind'] == 'symlink':
            assert path.is_symlink() and os.readlink(path) == item['target']
            assert path.lstat().st_mode & 0o777 == int(item['mode'], 8)
        else:
            assert not path.is_symlink() and path.stat().st_mode & 0o777 == int(item['mode'], 8) & ~0o222
            if item['kind'] == 'file':
                require(path, item['sha256'])
            else:
                assert path.is_dir()
    assert preserved.stat().st_mode & 0o777 == int(previous['root_mode'], 8) & ~0o222
    accepted = load(ROOT / 'qa/replay-requests/common-nci-generated-20261109/result.json')
    files = {}
    for name, expected in result['comparison']['files'].items():
        actual = require(TARGET / 'src' / name, expected['candidate']['sha256'])
        assert actual == accepted['comparison']['files'][name]['candidate']
        require(preserved / 'src' / name, actual['sha256']);files[name] = actual
    assert len(files) == 5
    assert original['runtime_ref'] == '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
    for item in original['runtime_files']:
        require(ROOT / item['repository_path'], item['sha256'])
    runtime_receipt = load(ROOT / 'candidate-runtime.json')
    assert runtime_receipt['runtime_ref'] == original['runtime_ref']
    answer = {'status': 'PASS_SOURCE_PLAN_FINAL_VERIFICATION', 'verified_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'run_id': RUN_ID, 'lock_sha256': LOCK_SHA256, 'source_engine_ref': SOURCE_ENGINE, 'apparatus_ref': APPARATUS,
        'candidate_seeded_with_only_five_publisher_files': True, 'generated_metadata_matches_independent_archive_hashes': True,
        'generated_read_only_files': generated, 'all_three_TREF_references_exact': True,
        'all_five_outputs_byte_exact_to_previous_accepted_candidate': True, 'files': files,
        'canonical_Git_code_files_verified': 4, 'frozen_apparatus_modules_verified': len(lock['modules_b64']),
        'entire_previous_tree_verified': True, 'preserved_manifest_entries': len(previous['manifest']),
        'preserved_previous_source': str(preserved), 'restored_runtime_ref': original['runtime_ref'],
        'restored_runtime_files_verified': len(original['runtime_files']),
        'historical_findings': result['source_plan_preflight']['historical_findings'],
        'insertion_executed': False, 'production_eligible': False,
        'scope': 'Reviewed metadata and optional additions, full historical core replay and preservation at normal dev paths; no fresh database/root inventory, production reservation, semantic correction to historical findings, insertion or deployment.'}
print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(answer));print('END_COMMON_REPLAY_RESULT', flush=True)
