#!/usr/bin/env python3
"""Contract, provenance, lifecycle and dispatch checks for the common interface."""
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import sys
from contextlib import nullcontext
from unittest.mock import patch

import inversion_request as request
import inversion_remote as remote
import inversion_worker as worker
from replay_process import runtime_lock


def check():
    passed = []
    def require(value, label):
        assert value, label
        passed.append(label)
    def rejected(action, label, exceptions=(ValueError, RuntimeError, FileExistsError, BlockingIOError)):
        try:
            action()
        except exceptions:
            passed.append(label)
        else:
            raise AssertionError(label)
    cases = [request.load(request.DOCS / 'case-catalog' / entry['path'])
             for entry in request.load(request.DOCS / 'case-catalog/index.json')['cases']]
    requests = []
    for case in cases:
        value = {key: case[key] for key in ('source', 'version', 'case_variant', 'reference_stage', 'comparison_profile')}
        value.update(schema_version=1, engine_ref=case['reviewed_engine_refs'][0])
        selected, config, _ = request.select_case(value)
        require(selected == case and config == case['configuration'], 'Common schema resolves ' + value['source'] + '/' + value['case_variant'])
        requests.append(value)
    for key, value in [('source', 'UNKNOWN'), ('source', 'MDR'), ('source', 'RADLEX'),
                       ('version', 'NCI_2026_09D'), ('case_variant', 'latest'),
                       ('reference_stage', 'insertion-package'), ('comparison_profile', 'exact'),
                       ('engine_ref', '<candidate-commit-sha>'), ('engine_ref', 'HEAD; echo bad')]:
        bad = {**requests[0], key: value}
        rejected(lambda: request.select_case(bad), 'Unsupported request rejected: ' + key + '=' + value)
    rejected(lambda: request.select_case({**requests[0], 'previous_version': 'August'}), 'Unknown parameter synonym rejected')
    config = copy.deepcopy(cases[1]['configuration'])
    config['source_options']['metamorphosys_profile_ref'] = 'unexpected'
    rejected(lambda: request.validate(config, 'configuration.schema.json'), 'Options from another source rejected')
    config = copy.deepcopy(cases[2]['configuration'])
    request.validate(config, 'configuration.schema.json')
    passed.append('MTH prepared bundle does not require its historical generator')
    config['inputs']['source_data_stage'] = 'publisher'
    rejected(lambda: request.validate(config, 'configuration.schema.json'), 'MTH publisher preparation requires its MetamorphoSys profile')
    original_blob = request.blob
    apparatus_ref = request.commit('HEAD')
    def fixture_blob(ref, name):
        # Freeze the in-progress apparatus only inside this fixture. Public
        # resolve uses committed Git blobs and rejects uncommitted differences.
        path = request.ROOT / name
        if ref == apparatus_ref and (name.startswith('tools/') or name.startswith('docs/') or name == 'baseline/manifest.json'):
            return path.read_bytes()
        return original_blob(ref, name)
    with patch.object(request, 'blob', side_effect=fixture_blob):
        locks = [request.resolve(value, 'fixture-' + str(number)) for number, value in enumerate(requests)]
    for lock in locks:
        target = worker.verify_lock(lock)
        require(target.name == lock['request']['version'], 'Frozen lock round trip: ' + lock['request']['source'] + '/' + lock['request']['case_variant'])
        package = worker.package(lock)
        source = lock['request']['source']
        engine = package.get('contract', package)['engine_ref']
        require(engine == lock['request']['engine_ref'], 'Adapter retains selected engine: ' + source + '/' + lock['request']['case_variant'])
    require(locks[2]['runtime_ref'] != locks[3]['request']['engine_ref'] and locks[3]['runtime_ref'] == locks[2]['runtime_ref'], 'MTH candidate source and unchanged shared runtime identities remain separate')
    for part in ('configuration', 'code_files', 'runtime_files', 'case'):
        bad = copy.deepcopy(locks[0])
        bad[part] = None
        rejected(lambda: worker.verify_lock(bad), 'Modified frozen payload rejected: ' + part)
    bad = copy.deepcopy(locks[0]);bad['request']['comparison_profile'] = 'exact'
    bad['lock_sha256'] = request.digest({k: v for k, v in bad.items() if k != 'lock_sha256'})
    rejected(lambda: worker.verify_lock(bad), 'Rehashed lock cannot override the case comparison profile')
    require(worker.correction_profile(locks[3]), 'Corrected MTH case selects its mandatory independent acceptance audit')
    require(worker.package(locks[3])['apparatus_ref'] == locks[3]['apparatus_ref'], 'MTH audit records the actual common execution apparatus')
    rejected(lambda: request.select_case({**requests[3], 'comparison_profile': 'exact'}), 'Corrected MTH case cannot be mislabeled as exact reproduction')
    gated = copy.deepcopy(locks[3])
    gated['execution_enabled'] = gated['case']['execution_enabled'] = False
    gated['case_sha256'] = request.digest(gated['case'])
    gated['lock_sha256'] = request.digest({k: v for k, v in gated.items() if k != 'lock_sha256'})
    with patch.object(worker, 'guard'):
        rejected(lambda: worker.launch(gated), 'An explicitly gated case remains blocked after audit integration')
    program = remote.bootstrap(locks[0], 'submit')
    compile(program.split("\n", 1)[1].rsplit('\nNCIM_COMMON_REQUEST', 1)[0], '<bootstrap>', 'exec')
    passed.append('Submission script compiles without shell interpolation of request values')
    for source in ('NCI', 'SNOMEDCT_US', 'MTH'):
        program = remote.read_program(source, 'fixture-case', True)
        compile(program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0], '<read>', 'exec')
    passed.append('Read-only status/collection scripts compile for all three sources')
    with tempfile.TemporaryDirectory(prefix='common-inversion-') as temporary:
        root = Path(temporary)
        malformed = root / 'malformed.json'
        malformed.write_text('{"source":"NCI","source":"MTH"}')
        rejected(lambda: request.load(malformed), 'Duplicate JSON keys rejected')
        output = root / 'immutable.json'
        request.write_new(output, {'saved': True})
        rejected(lambda: request.write_new(output, {}), 'Existing run lock cannot be overwritten')
        require(output.stat().st_mode & 0o777 == 0o400, 'Local lock is owner-readable and not writable')
        with runtime_lock(root) as held:
            with runtime_lock(root, held):
                passed.append('Preparation and source worker share the same held runtime lock')
            rejected(lambda: runtime_lock(root).__enter__(), 'Another runtime owner cannot enter during the inherited-lock lifetime')
            wrong = root / 'wrong.lock';wrong.touch()
            with wrong.open('a') as handle:
                rejected(lambda: runtime_lock(root, handle).__enter__(), 'Inherited descriptor from another lock file rejected')
        with runtime_lock(root):
            passed.append('Runtime lock releases after the complete lifecycle')
        target = root / 'MTH_2026AA';target.mkdir()
        (target / 'src').mkdir();(target / 'src/atoms').write_text('original data\n')
        (target / 'old').symlink_to('../MTH_2025AB')
        receipt = {'source': 'MTH', 'version': target.name, 'root_mode': oct(target.stat().st_mode & 0o777), 'manifest': worker.manifest(target)}
        receipt['receipt_sha256'] = request.digest(receipt)
        rejected(lambda: worker.preserve(target, 'fixture', None), 'Existing release needs an explicit previous-source receipt')
        (target / 'src/atoms').write_text('changed data\n')
        rejected(lambda: worker.preserve(target, 'fixture', receipt), 'Changed predecessor cannot be preserved under an old receipt')
        (target / 'src/atoms').write_text('original data\n')
        def fixture_publish(before, after):
            if after.exists() or after.is_symlink():
                raise FileExistsError(after)
            before.rename(after)
        # Production publication uses Linux renameat2(RENAME_NOREPLACE). Mac
        # fixtures exercise the lifecycle with an injected filesystem publisher;
        # the separate Linux worker suite exercises the actual syscall.
        publisher = nullcontext() if sys.platform.startswith('linux') else patch('prepare_snomed_candidate.publish', side_effect=fixture_publish)
        with publisher:
            preserved = worker.preserve(target, 'fixture', receipt)
            require(not target.exists() and (preserved / 'src/atoms').read_text() == 'original data\n', 'Complete predecessor is retained at a version-specific path')
            require(not (preserved / 'src/atoms').stat().st_mode & 0o222 and (preserved / 'old').is_symlink(), 'Preservation masks write access and retains link topology')
            worker.restore(preserved, target, receipt)
        require(worker.manifest(target) == receipt['manifest'], 'Rollback restores original bytes, topology and access modes')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'common inversion interface checks passed')
