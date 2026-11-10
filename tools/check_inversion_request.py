#!/usr/bin/env python3
"""Contract, provenance, lifecycle and dispatch checks for the common interface."""
import base64
import copy
import fcntl
import json
import os
import subprocess
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
        review = request.audit_review_capsule('parent-mth-run', 'review-mth-run')
    worker.verify_audit_review(review)
    passed.append('Audit-only review freezes a separately identified committed apparatus')
    rejected(lambda: request.audit_review_capsule('parent-mth-run', 'parent-mth-run'), 'Audit review cannot overwrite its failed parent identity')
    rejected(lambda: request.audit_review_capsule('../parent', 'review-mth-run'), 'Unsafe parent run identity rejected before review')
    program = remote.bootstrap_review(review)
    compile(program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_REVIEW', 1)[0], '<review-bootstrap>', 'exec')
    passed.append('Audit-review bootstrap compiles without interpolated shell commands')
    modules = {name: base64.b64decode(raw) for name, raw in locks[0]['modules_b64'].items()}
    request.validate_module_dependencies(modules)
    passed.append('Frozen apparatus includes its repository Python import dependencies')
    incomplete = {name: raw for name, raw in modules.items() if name != 'run_nci_core_replay.py'}
    rejected(lambda: request.validate_module_dependencies(incomplete), 'Missing NCIt helper rejected before remote preparation')
    incomplete = {name: raw for name, raw in modules.items() if name != 'replay_process.py'}
    rejected(lambda: request.validate_module_dependencies(incomplete), 'Missing shared process helper rejected before remote preparation')
    with tempfile.TemporaryDirectory(prefix='frozen-apparatus-imports-') as temporary:
        capsule = Path(temporary)
        for name, raw in modules.items():(capsule / name).write_bytes(raw)
        program = 'import importlib,sys;sys.path.insert(0,sys.argv[1]);[importlib.import_module(name) for name in sys.argv[2:]];from run_nci_core_replay import info;assert callable(info)'
        process = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(capsule)] + [Path(name).stem for name in modules], capture_output=True, text=True)
        require(process.returncode == 0, 'Frozen modules import successfully without the repository or installed helper copies: ' + process.stderr)
    for lock in locks:
        target = worker.verify_lock(json.loads(json.dumps(lock)))
        require(target.name == lock['request']['version'], 'Frozen lock round trip: ' + lock['request']['source'] + '/' + lock['request']['case_variant'])
        package = worker.package(lock)
        source = lock['request']['source']
        engine = package.get('contract', package)['engine_ref']
        require(engine == lock['request']['engine_ref'], 'Adapter retains selected engine: ' + source + '/' + lock['request']['case_variant'])
    for source,variant,option in [('MDR','consistent-history-context',{'language':'JPN'}),('RADLEX','as-produced',{'language':'ENG'})]:
        selected=next(x for x in locks if x['request']['source']==source and x['request']['case_variant']==variant)
        config=copy.deepcopy(selected['configuration']);config['source_options']=option
        rejected(lambda: request.validate(config,'configuration.schema.json'),'Unreviewed '+source+' source options rejected')
    generated = next(item for item in locks if item['request']['case_variant'] == 'generated-configuration')
    require(all(item['repository_path'].startswith('engines/nci/bin/') for item in generated['code_files']), 'Generated NCIt selects canonical Git code instead of a release-folder snapshot')
    require(len(generated['code_files']) == 4 and generated['configuration_generation']['files'][0]['relative_path'] == 'etc/nci.cfg', 'Generated settings have separate provenance from the four executable files')
    for label, mutate in [
        ('missing generated recipe', lambda item: item.pop('configuration_generation')),
        ('changed generated bytes', lambda item: item['configuration_generation']['files'][0].update(data_b64='Y2hhbmdlZA==')),
        ('wrong canonical code path', lambda item: item['code_files'][0].update(repository_path='sources/old/bin/create_rolegroups.pl')),
        ('removed generation contract', lambda item: (item.pop('configuration_generation'), item['case'].pop('configuration_generation'), item['case'].pop('source_package'))),
    ]:
        bad = copy.deepcopy(generated);mutate(bad)
        bad['case_sha256'] = request.digest(bad['case'])
        bad['lock_sha256'] = request.digest({key:value for key,value in bad.items() if key != 'lock_sha256'})
        rejected(lambda: worker.verify_lock(bad), 'Rehashed NCIt lock rejects ' + label)
    planned = next(item for item in locks if item['request']['case_variant'] == 'source-plan')
    require(len(planned['configuration_generation']['files']) == 5 and planned['configuration_generation']['bindings']['metadata_inputs'] == [], 'Source-plan case generates metadata and plan files without archived metadata seeds')
    require(len(planned['configuration_generation']['source_plan']['historical_exceptions']) == 2, 'Source-plan case retains both bounded historical findings')
    for label, mutate in [
        ('substituted metadata model', lambda item: item['configuration_generation']['metadata_model'].update(data_b64='e30=')),
        ('changed metadata bytes', lambda item: item['configuration_generation']['files'][1].update(data_b64='Y2hhbmdlZA==')),
        ('hidden historical finding', lambda item: item['configuration_generation']['source_plan'].update(historical_exceptions=[])),
        ('downgraded profile', lambda item: item['case']['configuration_generation'].update(profile='nci-properties-v1')),
    ]:
        bad = copy.deepcopy(planned);mutate(bad)
        bad['case_sha256'] = request.digest(bad['case']);bad['lock_sha256'] = request.digest({key:value for key,value in bad.items() if key != 'lock_sha256'})
        rejected(lambda: worker.verify_lock(bad), 'Source-plan lock rejects ' + label)
    radlex=next(x for x in locks if x['request']['source']=='RADLEX')
    bad=copy.deepcopy(radlex);bad['configuration']['source_atom_ids']['bound_kind']='reserved-historical-range'
    bad['case']['configuration']=copy.deepcopy(bad['configuration']);bad['case_sha256']=request.digest(bad['case']);bad['lock_sha256']=request.digest({k:v for k,v in bad.items() if k!='lock_sha256'})
    rejected(lambda:worker.verify_lock(bad),'RADLEX emitted-ID evidence cannot be relabeled as a production reservation')
    mdr=next(x for x in locks if x['request']['source']=='MDR')
    require(worker.correction_profile(mdr),'MDR selects its mandatory complete-record correction audit')
    require(worker.package(mdr)['runtime_ref']!=worker.package(radlex)['runtime_ref'],'MDR correction runtime and unchanged RADLEX runtime remain independently pinned')
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
    for source in request.ADAPTERS:
        program = remote.read_program(source, 'fixture-case', True)
        compile(program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0], '<read>', 'exec')
    passed.append('Read-only status/collection scripts compile for all five sources')
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
