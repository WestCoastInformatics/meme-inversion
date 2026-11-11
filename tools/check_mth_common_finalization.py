#!/usr/bin/env python3
"""Exercise common MTH finalization against real generated staging and APIs.

Only host-runtime verification is stubbed. Recipe construction, package
translation, generation, seven-file verification, source oracles, inclusive ID
bounds and every compared-output hash use the actual implementation.
"""
import ast
import copy
import hashlib
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import check_mth_generated_execution
import inversion_worker as worker
import mth_configuration
import replay_mth_core as replay

ROOT = Path(__file__).resolve().parents[1]
FAILED_APPARATUS = '79df69fe5b0b45d4f3c10550c16cb62cb9e8199e'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    lock, _ = check_mth_generated_execution.fixture()
    config, case = lock['configuration'], lock['case']
    lock.update(run_id='fixture-mth-common-finalization', runtime_ref=case['runtime_ref'],
                apparatus_ref='a' * 40, runtime_files=[], modules_b64={})
    lock['request'] = {'source': 'MTH', 'version': config['version'],
                       'engine_ref': config['engine_ref'], 'case_variant': case['case_variant'],
                       'reference_stage': 'inversion-src', 'comparison_profile': 'reviewed-corrections'}
    return lock


def atom(identifier, name='Alpha'):
    return (str(identifier) + '|TEST|TEST/PT|T1|R|Y|A|' + name + '|N||||ENG||\n').encode()


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def reject(action, label, message):
        try:
            action()
        except (RuntimeError, ValueError) as error:
            assert message in str(error), (label, error)
            passed.append(label)
        else:
            raise AssertionError(label)

    lock = fixture()
    package = worker.package(lock)
    bounds = lock['configuration']['source_atom_ids']
    originals = copy.deepcopy(lock)
    with tempfile.TemporaryDirectory(prefix='mth-common-finalization-') as temporary:
        target = Path(temporary)
        receipt = replay.stage_code_files(package, target)
        good(receipt['recipe_sha256'] == mth_configuration.digest(lock['configuration_generation']) and
             len(receipt['files']) == 7,
             'Actual worker package and replay staging materialize the seven bound generated settings')
        output_names = [item['output_name'] for item in package['reference_files']]
        good(len(output_names) == len(set(output_names)) == 23,
             'Fixture exercises all 23 characterized MTH compared outputs')
        for name in output_names:
            raw = atom(bounds['start']) + atom(bounds['end'], 'Omega') if name == 'classes_atoms.src' else (
                'fixture compared output ' + name + '\n').encode()
            (target / 'src' / name).write_bytes(raw)
        result = {'comparison': {'files': {name: {'candidate': {'sha256': sha((target / 'src' / name).read_bytes())},
                                                 'exact_match': True} for name in output_names}},
                  'acceptance': {'status': 'PASS_EXACT'}}
        with patch.object(worker, 'runtime') as host_runtime:
            accepted = copy.deepcopy(result)
            worker.verify_after(lock, target, accepted)
            good(accepted.get('compared_output_hashes_verified_after_run') is True and host_runtime.call_count == 1,
                 'Actual common finalization succeeds through real MTH verification and all output checks')
            good(replay.verify_generated(package, target) == receipt,
                 'Successful common finalization retains the exact real seven-file verification receipt')
            # Reproduce the frozen failing function with the same real modules.
            # No mth_configuration.verify_generated shim exists or is created.
            historical = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                            FAILED_APPARATUS + ':tools/inversion_worker.py']).decode()
            node = next(node for node in ast.parse(historical).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'verify_after')
            namespace = worker.__dict__.copy()
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         'frozen-failed-common-finalization', 'exec'), namespace)
            try:
                namespace['verify_after'](lock, target, copy.deepcopy(result))
            except AttributeError as error:
                good('mth_configuration' in str(error) and 'verify_generated' in str(error),
                     'Frozen failed apparatus reproduces the exact missing-method failure with real modules')
            else:
                raise AssertionError('Frozen wrong-module dispatch unexpectedly passed')
            for item in lock['configuration_generation']['files']:
                path = target / item['relative_path']
                raw = path.read_bytes()
                path.chmod(0o644)
                reject(lambda: worker.verify_after(lock, target, copy.deepcopy(result)),
                       'Common finalization rejects writable generated settings: ' + item['relative_path'],
                       'changed access bits')
                path.write_bytes(raw + b'# mutation\n')
                path.chmod(0o444)
                reject(lambda: worker.verify_after(lock, target, copy.deepcopy(result)),
                       'Common finalization rejects changed generated settings: ' + item['relative_path'],
                       'Pinned artifact differs')
                path.chmod(0o644)
                path.write_bytes(raw)
                path.chmod(0o444)
            source = target / 'invert1.s'
            raw = source.read_bytes()
            source.write_bytes(raw + b'# changed producer\n')
            reject(lambda: worker.verify_after(lock, target, copy.deepcopy(result)),
                   'Common finalization independently verifies pinned source files after generation', 'Frozen artifact differs')
            source.write_bytes(raw)
            old = target / 'old'
            old.unlink()
            old.symlink_to('../MTH_2025AA')
            reject(lambda: worker.verify_after(lock, target, copy.deepcopy(result)),
                   'Common finalization verifies the captured prior-source link topology', 'Source topology changed')
            old.unlink()
            old.symlink_to('../MTH_2025AB')
            atoms = target / 'src/classes_atoms.src'
            raw_atoms = atoms.read_bytes()
            for identifier in (bounds['start'] - 1, bounds['end'] + 1, 'invalid'):
                atoms.write_bytes(atom(identifier))
                modified = copy.deepcopy(result)
                modified['comparison']['files']['classes_atoms.src']['candidate']['sha256'] = sha(atoms.read_bytes())
                reject(lambda: worker.verify_after(lock, target, modified),
                       'Common finalization independently rejects out-of-range/non-numeric atom ID: ' + str(identifier),
                       'Atoms outside the complete declared historical ID range')
            atoms.write_bytes(raw_atoms)
            for name in output_names:
                path = target / 'src' / name
                raw = path.read_bytes()
                path.write_bytes(raw.replace(b'Alpha', b'Changed') if name == 'classes_atoms.src' else raw + b'mutation\n')
                reject(lambda: worker.verify_after(lock, target, copy.deepcopy(result)),
                       'Common finalization rehashes compared output: ' + name, 'Frozen artifact differs')
                path.write_bytes(raw)
            unsafe = copy.deepcopy(result)
            unsafe['comparison']['files']['../outside.src'] = unsafe['comparison']['files'][output_names[0]]
            reject(lambda: worker.verify_after(lock, target, unsafe),
                   'Common finalization rejects a compared-output name outside the source directory',
                   'Unexpected compared output name')
            exact = copy.deepcopy(lock)
            exact['request']['comparison_profile'] = 'exact'
            nonexact = copy.deepcopy(result)
            nonexact['comparison']['files'][output_names[0]]['exact_match'] = False
            nonexact['acceptance']['status'] = 'PASS_EQUIVALENT'
            worker.verify_after(exact, target, nonexact)
            good(nonexact['acceptance']['status'] == 'DIFFERENCES_REQUIRE_REVIEW' and
                 nonexact['acceptance']['requested_profile'] == 'exact',
                 'Common finalization preserves the exact-comparison gate after generated-file verification')
            restored = copy.deepcopy(result)
            worker.verify_after(lock, target, restored)
            good(restored.get('compared_output_hashes_verified_after_run') is True and lock == originals,
                 'Restored fixture passes complete finalization without changing the frozen lock')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH common-finalization checks passed')
