#!/usr/bin/env python3
"""Independent captured-config and negative dependency fixtures for SNOMED preview."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import snomed_configuration as sct

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    case = json.loads((ROOT / 'docs/inversion-review/case-catalog/snomedct_us-as-produced.json').read_text())
    config, artifacts = copy.deepcopy(case['configuration']), copy.deepcopy(case['artifacts'])
    raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', sct.CAPTURED_ENGINE + ':' + sct.TEMPLATE_PATH])
    template = {'repository_path': sct.TEMPLATE_PATH, 'sha256': sct.sha(raw),
                'data_b64': base64.b64encode(raw).decode()}

    def put(role, value):
        ref = 'sha256:' + sct.digest(value)
        artifacts[ref] = {'role': role, 'value': value}
        return ref

    return case, config, artifacts, template, put


def fixture_lock():
    case, config, artifacts, template, _ = fixture()
    case['configuration'] = config
    case['artifacts'] = artifacts
    code = []
    for item in case['source_files']:
        path = 'sources/' + sct.CAPTURED_VERSION + '/' + item['relative_path']
        raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', sct.CAPTURED_ENGINE + ':' + path])
        code.append({**item, 'repository_path': path, 'data_b64': base64.b64encode(raw).decode()})
    lock = {'schema_version': 1, 'artifact_type': 'ncimeta-dev-replay-lock',
            'request': {key: config[key] for key in ('source', 'version', 'engine_ref')},
            'configuration': config, 'case': case, 'case_sha256': sct.digest(case),
            'code_files': code}
    lock['lock_sha256'] = sct.digest(lock)
    return lock


def resign(lock):
    lock['case_sha256'] = sct.digest(lock['case'])
    lock['lock_sha256'] = sct.digest({k: v for k, v in lock.items() if k != 'lock_sha256'})


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def reject(action, label):
        try:
            action()
        except (ValueError, KeyError):
            passed.append(label)
        else:
            raise AssertionError(label)

    case, config, artifacts, template, _ = fixture()
    before = json.dumps([config, artifacts, template], sort_keys=True)
    recipe = sct.generate(config, artifacts, template)
    generated = base64.b64decode(recipe['files'][0]['data_b64'])
    golden = subprocess.check_output(['git', '-C', str(ROOT), 'show', sct.CAPTURED_ENGINE + ':' + sct.TEMPLATE_PATH])
    good(generated == golden, 'Generated September configuration is byte-exact to the independent production Git capture')
    good(sct.properties(generated, True) == sct.properties(golden, True),
         'Every effective property and multiline relationship mapping agrees with captured policy')
    good(sct.sha(generated) == sct.TEMPLATE_SHA256, 'Captured golden configuration hash is retained')
    good(recipe['files'][0]['mode'] == '0o444' and len(recipe['files']) == 1 and recipe['files'][0]['relative_path'] == 'etc/sct.cfg',
         'Preview generates only a read-only compatibility configuration, with no executable copy')
    good(recipe['execution_enabled'] is False and recipe['production_eligible'] is False,
         'Configuration equivalence does not confer native execution or production eligibility')
    good(len(recipe['bindings']['native_inputs']) == 14 and len(recipe['bindings']['metadata_inputs']) == 4,
         'Fourteen native RF2 members and four metadata/ICD inputs remain distinct')
    good(recipe['bindings']['identity_state'] is None and recipe['bindings']['publisher_history'] == [],
         'The characterized core does not invent prior identity-map or publisher-history requirements')
    good(sct.properties(generated, True)['Merge.SB.sgQual2'] == 'SNOMEDCT_US_2026_03_01',
         'VSABOLD preserves the explicitly selected replacement merge qualifier')
    good(before == json.dumps([config, artifacts, template], sort_keys=True), 'Generation leaves caller configuration and artifacts unchanged')
    lock = fixture_lock()
    good(sct.preview_from_lock(lock) == recipe, 'Frozen common lock reproduces the deterministic standalone recipe')
    good(sct.preview_from_lock(json.loads(json.dumps(lock))) == recipe,
         'Saved JSON lock round trip preserves the entire recipe')
    for label, mutate in [
        ('Full RF2 view', lambda c: c['source_options'].update(rf2_view='Full')),
        ('another source option', lambda c: c['source_options'].update(language='ENG')),
        ('another source', lambda c: c.update(source='MTH')),
        ('prepared-input stage', lambda c: c['inputs'].update(source_data_stage='prepared')),
        ('wrong output stage', lambda c: c.update(output_stage='insertion')),
        ('implicit replacement', lambda c: c.update(replacement_baseline=None)),
        ('same-version replacement', lambda c: c['replacement_baseline'].update(version=c['version'])),
        ('future replacement', lambda c: c['replacement_baseline'].update(version='SNOMEDCT_US_2027_03_01')),
        ('cross-source replacement', lambda c: c['replacement_baseline'].update(source='NCI')),
        ('invalid release date', lambda c: c.update(version='SNOMEDCT_US_2026_02_30')),
        ('unreviewed engine', lambda c: c.update(engine_ref='a' * 40)),
        ('new comparison stage', lambda c: c.update(comparison_baseline=c['replacement_baseline'])),
        ('undeclared history', lambda c: c['publisher_history'].append('unexpected')),
        ('undeclared identity map', lambda c: c['inputs'].update(identity_state='unexpected')),
        ('multiple source bundles', lambda c: c['inputs']['source_data'].append(c['inputs']['source_data'][0])),
        ('boolean ID', lambda c: c['source_atom_ids'].update(start=True)),
        ('reversed ID range', lambda c: c['source_atom_ids'].update(end=1)),
        ('changed ID limit', lambda c: c['source_atom_ids'].update(end=c['source_atom_ids']['end'] + 1)),
        ('unproved emitted-range label', lambda c: c['source_atom_ids'].update(bound_kind='historical-emitted-range')),
    ]:
        c = copy.deepcopy(config)
        mutate(c)
        reject(lambda: sct.generate(c, artifacts, template), 'Reject ' + label)
    for label, mutation in [
        ('template path substitution', lambda t: t.update(repository_path='sources/old/etc/sct.cfg')),
        ('template byte mutation', lambda t: t.update(data_b64=base64.b64encode(b'Release = Full\n').decode())),
        ('self-rehashed template mutation', lambda t: t.update(data_b64=base64.b64encode(b'Release = Full\n').decode(), sha256=sct.sha(b'Release = Full\n'))),
    ]:
        t = copy.deepcopy(template)
        mutation(t)
        reject(lambda: sct.generate(config, artifacts, t), 'Reject ' + label)
    for label, role, field, mutation in [
        ('missing required RF2 member', 'source-data', 'source_data', lambda x: x.pop()),
        ('duplicate native member', 'source-data', 'source_data', lambda x: x.__setitem__(0, copy.deepcopy(x[1]))),
        ('wrong RF2 filename date', 'source-data', 'source_data', lambda x: x[0].update(path=x[0]['path'].replace('20260901.txt', '20260301.txt'))),
        ('unsafe RF2 path', 'source-data', 'source_data', lambda x: x[0].update(path='../' + x[0]['path'])),
        ('required native flag removed', 'source-data', 'source_data', lambda x: x[0].update(required=False)),
        ('wrong native role', 'source-data', 'source_data', lambda x: x[0].update(legacy_key='File.INP.EXTENDEDMAPS')),
        ('native hash absent', 'source-data', 'source_data', lambda x: x[0].update(sha256='bad')),
        ('boolean native size', 'source-data', 'source_data', lambda x: x[0].update(size=True)),
        ('missing ICD target inventory', 'preserved-reference-metadata', 'reference_ncimeta', lambda x: x.pop()),
        ('metadata/core-output substitution', 'preserved-reference-metadata', 'reference_ncimeta', lambda x: x[0].update(path=config['version'] + '/src/classes_atoms.src')),
        ('wrong ICD role', 'preserved-reference-metadata', 'reference_ncimeta', lambda x: x[-1].update(role='source-data')),
    ]:
        _, c, a, t, put = fixture()
        ref = c['inputs'][field][0] if field == 'source_data' else c['inputs'][field]
        values = copy.deepcopy(a[ref]['value'])
        mutation(values)
        bound = put(role, values)
        c['inputs'][field] = [bound] if field == 'source_data' else bound
        reject(lambda: sct.generate(c, a, t), 'Reject ' + label)
    for label, role, mutation in [
        ('changed historical replacement decision', 'reviewed-historical-transition', lambda x: x['replacement_baseline'].update(version='SNOMEDCT_US_2025_09_01')),
        ('production allocation relabeling', 'isolated-historical-ID-range', lambda x: x.update(production_reservation=True)),
        ('unreviewed range proof', 'isolated-historical-ID-range', lambda x: x.update(end=779143592)),
    ]:
        _, c, a, t, put = fixture()
        field = c['inputs']['source_plan'] if role == 'reviewed-historical-transition' else c['source_atom_ids']['provenance_ref']
        value = copy.deepcopy(a[field]['value'])
        mutation(value)
        ref = put(role, value)
        if role == 'reviewed-historical-transition':
            c['inputs']['source_plan'] = ref
        else:
            c['source_atom_ids']['provenance_ref'] = ref
        reject(lambda: sct.generate(c, a, t), 'Reject ' + label)
    tampered = copy.deepcopy(artifacts)
    tampered[config['inputs']['source_data'][0]]['value'][0]['sha256'] = 'a' * 64
    reject(lambda: sct.generate(config, tampered, template), 'Reject artifact content changed without changing its reference')
    for label, mutation, should_resign in [
        ('changed saved lock', lambda x: x['configuration'].update(version='SNOMEDCT_US_2027_03_01'), False),
        ('changed pinned cfg bytes', lambda x: x['code_files'][-1].update(data_b64=base64.b64encode(b'changed').decode()), True),
        ('duplicate code payload', lambda x: x['code_files'].append(copy.deepcopy(x['code_files'][0])), True),
        ('missing code payload', lambda x: x['code_files'].pop(), True),
        ('changed legacy native manifest', lambda x: x['case']['legacy_case']['contract']['conversion_inputs'][0].update(sha256='0' * 64), True),
        ('changed legacy replacement', lambda x: x['case']['legacy_case']['contract'].update(replacement_baseline={'source':'SNOMEDCT_US','version':'SNOMEDCT_US_2025_09_01'}), True),
    ]:
        bad = copy.deepcopy(lock)
        mutation(bad)
        if should_resign:
            resign(bad)
        reject(lambda: sct.preview_from_lock(bad), 'Reject ' + label)
    # A synthetic transition checks that replacement is an explicit choice,
    # while native filename dates still agree with the current publisher release.
    _, c, a, t, put = fixture()
    c['version'] = 'SNOMEDCT_US_2027_09_01'
    c['replacement_baseline'] = {'source': 'SNOMEDCT_US', 'version': 'SNOMEDCT_US_2026_03_01'}
    native = copy.deepcopy(a[c['inputs']['source_data'][0]]['value'])
    for item in native:
        item['path'] = item['path'].replace('SNOMEDCT_US_2026_09_01', c['version']).replace('20260901', '20270901')
    c['inputs']['source_data'] = [put('source-data', native)]
    metadata = copy.deepcopy(a[c['inputs']['reference_ncimeta']]['value'])
    for item in metadata:
        item['path'] = item['path'].replace('SNOMEDCT_US_2026_09_01', c['version'])
    c['inputs']['reference_ncimeta'] = put('preserved-reference-metadata', metadata)
    future = sct.generate(c, a, t)
    props = sct.properties(base64.b64decode(future['files'][0]['data_b64']), True)
    good(props['VSAB'] == c['version'] and props['VSABOLD'] == 'SNOMEDCT_US_2026_03_01' and props['EngNumOld'] == '20260301',
         'Synthetic skipped releases retain the explicit replacement rather than calculating a previous release')
    good(props[c['version'] + '.VSY.0'] == 'SNOMED Clinical Terms US Edition, September 1, 2027' and props['EngNum'] == '20270901',
         'Synthetic release naming preserves the explicitly bounded ManagedService package convention')
    return passed


if __name__ == '__main__':
    results = check()
    for item in results:
        print('PASS', item)
    print(len(results), 'SNOMED configuration-preview checks passed')
