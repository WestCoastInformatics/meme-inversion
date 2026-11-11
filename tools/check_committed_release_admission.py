#!/usr/bin/env python3
"""Check committed native capsules and historical compatibility; no dev contact.

All native declaration inputs/oracles here are SYNTHETIC. The confined fixture
uses the preserved-declaration enum solely to reach the serialization branch;
that enum does not authenticate origin. It rebinds URIs to nonexistent standard
test cache paths. No bytes are acquired, no server job is submitted, no native
acceptance is claimed, and no capsule is retained outside the temporary test.
Honest checked-in synthetic manifests must still be rejected by the public CLI.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

import check_execute_release_nci as nci
import check_execute_release_snomed as snomed
import check_execute_release_mth as mth
import check_release_mth
import inversion_request as historical
import inversion_worker as legacy
import release_execution as admission
import release_manifest as manifests
import release_worker as native


def check():
    root = historical.ROOT;head = historical.commit('HEAD');results = []
    with tempfile.TemporaryDirectory(prefix='committed-native-admission-') as directory:
        temporary = Path(directory).resolve();mth_root = temporary / 'mth-fixture';mth_root.mkdir()
        fixtures = [('NCI', nci.fixture()[0]), ('SNOMEDCT_US', snomed.fixture()),
                    ('MTH', mth.fixture(mth_root)[0])]
        for source, original in fixtures:
            manifest = copy.deepcopy(original);config = manifest['configuration'];artifacts = manifest['artifacts']
            config['engine_ref'] = head;manifest['purpose'] = 'historical-replay'
            for name, artifact in artifacts.items():
                artifact['provenance'].update(producer='SYNTHETIC DECLARATION SERIALIZATION TEST ONLY',
                    evidence_kind='preserved')
                for file in artifact['files']:
                    file['uri'] = 'file:///local/content/MEME/MEME5/inv/qa/nonexistent-unit-declarations/' + source + '/' + name + '/' + urlsplit(file['uri']).path.lstrip('/')
            if source == 'SNOMEDCT_US':artifacts[config['policy_ref']]['data']['engine_ref'] = head
            if source == 'MTH':check_release_mth.bind_producer_inputs(manifest)
            profile = manifests.load(admission.PROFILES)['profiles'][manifest['profile']]
            code = admission._tree(head, profile['engine_package'])
            plan = admission.importlib.import_module(profile['handler']).build_plan(config, artifacts, code)
            oracle = {'schema_version': 1, 'artifact_type': 'reference-inversion', 'source': source, 'version': config['version'],
                'provenance': {'producer': 'SYNTHETIC SERIALIZATION TEST ORACLE; NO REAL RELEASE', 'producer_version': 'unit',
                               'capture_id': 'unit-oracle-' + source, 'evidence_kind': 'preserved'},
                'files': [], 'data': {'reference_stage': 'inversion-src'}}
            for name in plan['output_files']:
                raw = ('synthetic serialization oracle only: ' + name + '\n').encode()
                oracle['files'].append({'role': name, 'uri': 'file:///local/content/MEME/MEME5/inv/qa/nonexistent-unit-oracles/' + source + '/' + name,
                                       'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
            artifacts['unit-oracle'] = oracle
            config['replay'] = {'reference_ref': 'unit-oracle', 'reference_stage': 'inversion-src', 'comparison_profile': 'exact'}
            preview = manifests.preflight(manifest)
            assert preview['manifest_valid'] and preview['declarations_valid'], (source, preview['issues'])
            lock = admission.resolve(manifest, 'unit-serialization-only-' + source.lower().replace('_', '-'))
            assert lock['apparatus_ref'] == head and lock['request']['engine_ref'] == head
            assert native.verify_lock(lock).name == config['version']
            capsule = temporary / source;capsule.mkdir()
            for name, encoded in lock['modules_b64'].items():(capsule / name).write_bytes(base64.b64decode(encoded, validate=True))
            lock_path = capsule / 'unit.lock.json';lock_path.write_text(json.dumps(lock))
            names = [Path(name).stem for name in lock['modules_b64']]
            program = ('import importlib,json,sys;sys.path.insert(0,sys.argv[1]);'
                       '[importlib.import_module(name) for name in sys.argv[3:]];'
                       'import release_worker;lock=json.load(open(sys.argv[2]));'
                       'assert release_worker.verify_lock(lock).name==lock["request"]["version"]')
            child = subprocess.run([sys.executable, '-I', '-B', '-S', '-c', program, str(capsule), str(lock_path)] + names,
                                   capture_output=True, text=True, timeout=90)
            assert child.returncode == 0, child.stderr
            shown = subprocess.run([sys.executable, '-B', str(root / 'tools/inversion_request.py'), 'show', str(lock_path)], capture_output=True, text=True)
            assert shown.returncode == 0 and json.loads(shown.stdout)['configuration'] == config, shown.stderr
            assert 'modules_b64' not in shown.stdout
            results.append({'source': source, 'scope': 'synthetic declaration serialization only',
                            'committed_resolver': 'PASS', 'isolated_stdlib_capsule_verification': 'PASS',
                            'show': 'PASS', 'module_count': len(names), 'runtime_files': len(lock['runtime_files']),
                            'server_submitted': False, 'native_conversion': False, 'operational_evidence': False})
        rejected_examples = []
        for source in ('nci', 'snomed', 'mth'):
            output = temporary / (source + '.must-not-exist.lock.json')
            process = subprocess.run([sys.executable, '-B', str(root / 'tools/inversion_request.py'), 'resolve-release',
                str(historical.DOCS / 'release-manifest-examples' / (source + '.json')),
                '--run-id', 'reject-synthetic-' + source, '--output', str(output)], capture_output=True, text=True)
            assert process.returncode == 2 and not output.exists(), process.stdout + process.stderr
            rejected_examples.append(source)
    cases = []
    for number, entry in enumerate(historical.load(historical.DOCS / 'case-catalog/index.json')['cases']):
        case = historical.load(historical.DOCS / 'case-catalog' / entry['path'])
        request = {key: case[key] for key in ('source', 'version', 'case_variant', 'reference_stage', 'comparison_profile')}
        request.update(schema_version=1, engine_ref=case['reviewed_engine_refs'][0])
        lock = historical.resolve(request, 'native-compat-' + str(number))
        assert legacy.verify_lock(lock).name == request['version'] and lock['apparatus_ref'] == head
        cases.append({key: request[key] for key in ('source', 'version', 'case_variant')})
    return {'status': 'PASS_COMMITTED_DECLARATION_CAPSULE_AND_HISTORICAL_COMPATIBILITY', 'apparatus_ref': head,
            'native_unit_probes': results, 'public_synthetic_examples_rejected': rejected_examples,
            'historical_cases_verified': cases, 'historical_locks_retained': 0,
            'server_contacted': False, 'native_real_release_tested': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
