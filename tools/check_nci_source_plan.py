#!/usr/bin/env python3
"""Golden metadata, actual Perl producers, novelty and negative release-plan checks."""
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_nci_configuration as previous
import nci_configuration as configuration
import nci_source_plan as plans

ROOT = Path(__file__).resolve().parents[1]


def fixture(plan=None):
    config, artifacts, template, legacy, put = previous.fixture()
    model_raw = (ROOT / 'engines/nci/metadata-policy.json').read_bytes()
    model = {'repository_path': 'engines/nci/metadata-policy.json', 'sha256': plans.sha(model_raw),
             'data_b64': base64.b64encode(model_raw).decode()}
    config['policy_ref'] = put('nci-representation-policy', {'profile': plans.PROFILE,
        'engine_ref': config['engine_ref'], 'template_repository_path': template['repository_path'],
        'template_sha256': template['sha256']})
    config['inputs']['reference_ncimeta'] = put('reviewed-nci-metadata-model',
        {key: model[key] for key in ('repository_path', 'sha256')})
    plan = copy.deepcopy(plan) if plan is not None else json.loads((ROOT / 'docs/inversion-review/configuration-examples/nci-source-plan-october-2026.json').read_text())
    config['inputs']['source_plan'] = put('reviewed-nci-source-plan', plan)
    return config, artifacts, template, model, plan


def recipe(plan=None):
    c, a, t, m, _ = fixture(plan)
    return configuration.generate(c, a, t, m)


def execute(root, generated, rows, script=None):
    for name in ('bin', 'etc/qa', 'src', 'orig', 'tmp'):
        (root / name).mkdir(parents=True, exist_ok=True)
    for item in generated['files']:
        (root / item['relative_path']).write_bytes(base64.b64decode(item['data_b64']))
    (root / 'orig/MRCONSO.TREF').write_text('|Parent|C1||NCIPT||\n|Child|C2||NCIPT||\n' + rows)
    (root / 'orig/MRSAT.TREF').write_text('')
    (root / 'orig/MRREL.TREF').write_text('|C1|CUI||PAR|isa|C2|CUI|\n')
    source = script or ROOT / 'engines/nci/bin/invert_NCI.pl'
    result = subprocess.run(['/usr/bin/perl', str(source)], cwd=root / 'bin', capture_output=True,
                            env=dict(os.environ, INV_HOME=str(ROOT / 'INV'), LC_ALL='C', PERL_HASH_SEED='1', PERL_PERTURB_KEYS='2'), timeout=40)
    if result.returncode:
        raise AssertionError(result.stderr.decode() + result.stdout.decode()[-1500:])
    return {name: (root / 'src' / name).read_bytes() for name in ('classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src')}


def native_fixture(root, generated, content):
    value = copy.deepcopy(generated)
    used = {line.split('|')[1] for line in content.splitlines()}
    labels = value['source_plan']['publisher_labels']
    native = {'classDeclaration': content,
              'annotationDeclaration': ''.join(key + '|rdfs:label|' + labels[key] + '\n' for key in used if key in labels),
              'objectDeclaration': '', 'relations': '', 'hierarchy': ''}
    for role, item in value['bindings']['native_inputs'].items():
        path = root / item['relative_path'];path.parent.mkdir(parents=True, exist_ok=True)
        raw = native[role].encode();path.write_bytes(raw);item['sha256'] = plans.sha(raw)
    return value


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def reject(action, label):
        try:
            action()
        except (ValueError, KeyError):
            checks.append(label)
        else:
            raise AssertionError(label)
    generated = recipe()
    reference = json.loads((ROOT / 'docs/inversion-review/case-catalog/nci-generated-configuration.json').read_text())
    expected = {Path(x['path']).name: x['sha256'] for x in reference['legacy_case']['archived_metadata_inputs']}
    for item in generated['files']:
        if item['relative_path'].startswith('src/'):
            good(item['sha256'] == expected[Path(item['relative_path']).name], 'All generated metadata bytes match the independent October oracle: ' + item['relative_path'])
    old = configuration.properties(subprocess.check_output(['git', 'show', 'bfda2ce:sources/NCI_2026_10D/etc/nci.cfg'], cwd=ROOT))
    props = configuration.properties(base64.b64decode(generated['files'][0]['data_b64']))
    good(all(props[key] == value for key, value in old.items()), 'All 290 legacy properties retain their exact effective values')
    c, a, t, m, _ = fixture();m = copy.deepcopy(m);m['data_b64'] = base64.b64encode(b'{}').decode()
    reject(lambda: configuration.generate(c, a, t, m), 'Substituted metadata model bytes are rejected')
    _, _, _, _, october = fixture()
    empty = copy.deepcopy(october);empty['new_subsources'] = [];empty['new_termgroups'] = [];empty['historical_exceptions'] = []
    none = recipe(empty)
    good(all(not base64.b64decode(x['data_b64']) for x in none['files'] if x['relative_path'] in (plans.ROOTS, plans.TOKENS)), 'Explicit empty arrays generate empty root/token files')
    for label, change in [
        ('unknown plan field', lambda p: p.update(previous_version='August')),
        ('missing no-additions decision', lambda p: p.pop('new_subsources')),
        ('duplicate source', lambda p: p['new_subsources'].append(copy.deepcopy(p['new_subsources'][0]))),
        ('duplicate termgroup', lambda p: p['new_termgroups'].append(copy.deepcopy(p['new_termgroups'][0]))),
        ('unknown insertion anchor', lambda p: p['new_subsources'][0].update(after_source='UNKNOWN')),
        ('unknown low source', lambda p: p['new_subsources'][0]['metadata'].update(low_source='UNKNOWN')),
        ('cyclic source rank', lambda p: p['new_subsources'][0]['metadata'].update(low_source='BLOODPAC_{{release}}')),
        ('cyclic termgroup rank', lambda p: p['new_termgroups'][0]['metadata'].update(low_termgroup='BLOODPAC_{{release}}/PT')),
        ('invalid flags', lambda p: p['new_termgroups'][0]['metadata'].update(suppressible_flag='maybe')),
        ('inconsistent termgroup type', lambda p: p['new_termgroups'][0]['metadata'].update(tty='AB')),
        ('injected field delimiter', lambda p: p['new_subsources'][0]['root'].update(short_name='bad|name')),
        ('unresolved template value', lambda p: p['new_subsources'][0]['metadata'].update(low_source='{{unknown}}')),
        ('missing root name', lambda p: p['new_subsources'][0]['root'].update(short_name='')),
        ('new source without termgroups', lambda p: p.update(new_termgroups=[])),
        ('unmapped new input type', lambda p: p['new_termgroups'][0].update(input_ttys=['NEWTYPE'])),
        ('changed existing representation', lambda p: p['property_updates'].update({'in2tty.AB': 'SY'})),
        ('unreviewed property update', lambda p: p['property_updates'].update({'MakeRoot': '1'})),
        ('wrong replacement baseline', lambda p: p['replacement_baseline'].update(version='NCI_2026_09D')),
    ]:
        plan = copy.deepcopy(october);change(plan)
        reject(lambda: recipe(plan), 'Reject ' + label)
    c, a, t, m, plan = fixture();c['version'] = 'NCI_2027_02B';c['replacement_baseline']['version'] = 'NCI_2026_12C'
    plan.update(version=c['version'], replacement_baseline=c['replacement_baseline'], historical_exceptions=[])
    plan['new_termgroups'][1]['metadata']['low_termgroup'] = 'CELLOSAURUS_{{release}}/PT'
    # Use the same metadata renderer with a new explicit common transition.
    future = plans.generate(c, plan, plans.load(base64.b64decode(m['data_b64'])), {key: value.replace('2026_10D', '2027_02B') for key, value in props.items() if not key.startswith('NCI.SourcePlan.')})
    good(b'NCI_2027_02B|NCI_2026_12C|' in base64.b64decode(future['files'][0]['data_b64']), 'Skipped-month metadata follows the declared replacement, not calendar arithmetic')
    new_type = copy.deepcopy(empty)
    new_type['new_termgroups'] = [{'metadata': {'termgroup_name': 'NCI_{{release}}/NEWTYPE', 'low_termgroup': 'NCI_{{release}}/SY', 'suppressible_flag': 'N', 'exclude_flag': 'N', 'norm_exclude_flag': 'N', 'tty': 'NEWTYPE'}, 'after_termgroup': 'NCI_{{release}}/SY', 'input_ttys': ['NEWTYPE']}]
    new_type['property_updates'] = {'in2tty.NEWTYPE': 'NEWTYPE'}
    long_source = copy.deepcopy(october);long_source['historical_exceptions'] = []
    addition = long_source['new_subsources'][0]
    addition['metadata'] = {key: value.replace('BLOODPAC', 'LONG_NEW_SOURCE') for key, value in addition['metadata'].items()}
    addition['publisher_names'] = ['LONG_NEW_SOURCE']
    for addition in long_source['new_termgroups']:
        addition['metadata'] = {key: value.replace('BLOODPAC', 'LONG_NEW_SOURCE') for key, value in addition['metadata'].items()}
        addition['after_termgroup'] = addition['after_termgroup'].replace('BLOODPAC', 'LONG_NEW_SOURCE')
    long_source['new_termgroups'][1]['metadata']['low_termgroup'] = 'CELLOSAURUS_{{release}}/PT'
    multiple = copy.deepcopy(october)
    multiple['new_subsources'].append(copy.deepcopy(long_source['new_subsources'][0]))
    multiple['new_subsources'][1]['after_source'] = 'BLOODPAC'
    multiple['new_termgroups'] += copy.deepcopy(long_source['new_termgroups'])
    multiple['new_termgroups'][2]['after_termgroup'] = 'BLOODPAC_{{release}}/SY'
    with tempfile.TemporaryDirectory(prefix='nci-source-plan-check-') as temporary:
        root = Path(temporary)
        baseline = root / 'captured.pl';baseline.write_bytes(subprocess.check_output(['git', 'show', 'bfda2ce:sources/NCI_2026_10D/bin/invert_NCI.pl'], cwd=ROOT))
        old_output = execute(root / 'old', generated, '|FDA preferred|C1||FDAPT|FIRST|\n', baseline)
        new_output = execute(root / 'new', generated, '|FDA preferred|C1||FDAPT|FIRST|\n')
        good(old_output == new_output, 'Actual new and captured Perl producers preserve every byte and ID in all five synthetic October outputs')
        output = execute(root / 'none', none, '')
        good(b'|SRC/RPT|' not in output['classes_atoms.src'] and b'|V-BLOODPAC|' not in output['classes_atoms.src'], 'Actual Perl no-additions run emits no leftover root atoms')
        good(b'|BLOODPAC_2026_10D|' in output['classes_atoms.src'], 'An established subsource remains in versioned metadata without repeating its root records')
        output = execute(root / 'long', recipe(long_source), '|Long source term|C1||LONG_NEW_SOURCEPT|EXT1|\n')
        good(b'|LONG_NEW_SOURCE_2026_10D/PT|' in output['classes_atoms.src'] and b'|V-LONG_NEW_SOURCE|' in output['classes_atoms.src'], 'Actual Perl handles a new source longer than legacy parser limits and emits its planned root')
        output = execute(root / 'multiple', recipe(multiple), '')
        roots = [line.split(b'|') for line in output['classes_atoms.src'].splitlines() if line.split(b'|')[2] in (b'SRC/RPT', b'SRC/RAB', b'SRC/SSN')]
        good([x[3] for x in roots] == [b'V-BLOODPAC'] * 3 + [b'V-LONG_NEW_SOURCE'] * 3 and all(int(y[0]) == int(x[0]) + 1 for x, y in zip(roots, roots[1:])), 'Multiple additions preserve the declared root order and consecutive SRC identities')
        output = execute(root / 'newtype', recipe(new_type), '|New term type|C1||NCINEWTYPE||\n')
        good(b'|NCI_2026_10D/NEWTYPE|' in output['classes_atoms.src'], 'Actual Perl emits a newly planned term type on an existing source')
        native = root / 'native';native.mkdir()
        text = 'C1|P108|Alpha\nC1|P90|Alpha|P383|PT|P384|FDA\n'
        discovery_recipe = copy.deepcopy(generated);discovery_recipe['source_plan']['historical_exceptions'] = []
        probe = native_fixture(native, discovery_recipe, text)
        good(plans.discover(probe, native)['status'] == 'PASS', 'Native discovery accepts reviewed publisher termgroups')
        bounded = native_fixture(native, generated, text)
        reject(lambda: plans.discover(bounded, native), 'Historical exceptions cannot transfer to a different native bundle')
        for label, data in [('unknown subsource', text.replace('|FDA', '|UNKNOWN')), ('unknown term type', text.replace('|PT|', '|NOVEL|')), ('new property', text + 'C1|P999999|new\n'), ('unknown Maps_To', text + 'C1|P375|value|P393|Novel Mapping\n'), ('unmapped historical source with different inputs', text.replace('|FDA', '|CTCAE 6.0'))]:
            value = native_fixture(native, discovery_recipe, data)
            reject(lambda: plans.discover(value, native), 'Native preflight rejects ' + label)
        value = native_fixture(native, discovery_recipe, text)
        path = native / value['bindings']['native_inputs']['classDeclaration']['relative_path'];path.write_text(text + 'C9|P108|changed\n')
        reject(lambda: plans.discover(value, native), 'Native preflight rejects input changed after freezing')
        saved = root / 'saved'
        for item in generated['files']:
            path = saved / item['relative_path'];path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(item['data_b64']));path.chmod(0o444)
        configuration.verify_files(generated, saved);configuration.verify_metadata(generated, saved)
        good(True, 'All five generated settings/metadata/plan files verify read-only')
        path = saved / 'src/sources.src';path.chmod(0o644)
        reject(lambda: configuration.verify_files(generated, saved), 'Writable generated metadata rejects execution')
        path.write_bytes(path.read_bytes() + b'changed\n');path.chmod(0o444)
        reject(lambda: configuration.verify_metadata(generated, saved), 'Changed generated metadata rejects execution')
    return checks


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'NCIt source-plan checks passed')
