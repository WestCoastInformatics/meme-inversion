#!/usr/bin/env python3
"""Test manifest-only planning, physical scans and release-aware SRC validation."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import execute_release_snomed as execute

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [ROOT / 'docs/inversion-review/release-manifest-examples/snomed.json',
            ROOT / 'tools/fixtures/release-manifests/snomed/second-release.json']


def fixture(index=0):
    manifest = json.loads(EXAMPLES[index].read_text())
    manifest['artifacts']['representation-policy']['data']['mapping_targets'] = {
        'ICD10': 'ICD10_2016', 'ICD10CM': 'ICD10CM_2027', 'ICD9CM': 'ICD9CM_2013'}
    return manifest


def plan(manifest):
    return execute.build_plan(manifest['configuration'], manifest['artifacts'])


def materialize(manifest, target):
    recipe = plan(manifest)
    for item in recipe['input_files']:
        artifact = manifest['artifacts'][item['artifact']]
        entry = next(value for value in artifact['files'] if value['role'] == item['role'])
        destination = target / item['destination']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / entry['uri'].removeprefix('repo:'), destination)
        destination.chmod(0o444)
    for item in recipe['generated_files']:
        path = target / item['relative_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(item['data_b64'])); path.chmod(int(item['mode'], 8))
    return recipe


def output_fixture(recipe):
    version = recipe['version']; left = str(recipe['validation']['source_atom_ids']['start']); right = str(int(left) + 1)
    return {
        'classes_atoms.src': [[left, version, version + '/PT', '100001', 'R', 'Y', 'N', 'Synthetic term', 'N', '100011', '100001', '', 'ENG', '1', ''],
                              [right, version, version + '/FN', '138875005', 'R', 'Y', 'N', 'Synthetic root', 'N', '100010', '138875005', '', 'ENG', '1', '']],
        'attributes.src': [['1', '100011', 'S', 'DESCRIPTION_LENGTH', '5', version, 'R', 'n', 'N', 'N', 'SOURCE_AUI', version, '', hashlib.md5(b'5').hexdigest(), '']],
        'relationships.src': [['1', 'S', '138875005', 'CHD', 'isa', '100001', version, version, 'R', 'Y', 'N', 'N', 'SOURCE_CUI', version, 'SOURCE_CUI', version, '123', '0', '']],
        'mergefacts.src': [['100011', 'SY', '100001', version, '', 'N', 'N', 'SNOMEDCT_US-SCUI', 'SOURCE_AUI', version, 'SOURCE_CUI', version, '']],
        'contexts.src': [[left, 'PAR', 'isa', right, version, version, '', right, '00', '123', '0', '100001', 'SOURCE_CUI', version, '138875005', 'SOURCE_CUI', version, '']]}


def write_outputs(target, values):
    for name, rows in values.items():
        path = target / 'src' / name
        path.write_text(''.join('|'.join(row) + '\n' for row in rows))


def check():
    passed = []
    def good(value, label):
        assert value, label; passed.append(label)
    def reject(action, label):
        try: action()
        except (ValueError, KeyError): passed.append(label)
        else: raise AssertionError(label)
    first, second = fixture(), fixture(1)
    original = json.dumps(first, sort_keys=True)
    a, b = plan(first), plan(second)
    good(a['version'] != b['version'] and a['engine_package'] == b['engine_package'] == execute.PACKAGE,
         'The same canonical Git package plans two dates/packages/inserted predecessors without version edits')
    good(original == json.dumps(first, sort_keys=True), 'Plan generation does not mutate the manifest')
    good(a['output_files'] == ['src/' + value for value in execute.OUTPUTS] and not a['symlinks'],
         'Five core outputs retain standard source paths and no undeclared links')
    good(a['stages'][-1]['stdout'] == 'src/attributes.src' and all('sh' not in value for stage in a['stages'] for value in stage['argv']),
         'Native stages are fixed commands with the original cleanup and no manifest shell commands')
    good(all('ClinicUS_R7_20270301T230000Z' in item['destination'] for item in a['input_files'] if item['role'].startswith('rf2-')),
         'Provider paths preserve the explicitly named native package including its independent timestamp')
    for number, manifest in enumerate((first, second)):
        with tempfile.TemporaryDirectory(prefix='snomed-release-physical-') as directory:
            target = Path(directory).resolve()
            recipe = materialize(manifest, target)
            result = execute.validate_inputs(recipe, target)
            good(result['passed'] and result['facts']['actual_headers_verified'],
                 'Actual physical RF2/metadata scanning passes for synthetic publication ' + str(number + 1))
            good(result['facts']['native_rows']['rf2-concepts'] == 2 and result['facts']['physical_discovery']['relationship_types'] == ['116680003'],
                 'Discovery derives actual row counts/native IDs rather than trusting declarations ' + str(number + 1))
            for label, mutate in [
                ('Full view', lambda c, art: c['source_options'].update(rf2_view='Full')),
                ('Delta view', lambda c, art: c['source_options'].update(rf2_view='Delta')),
                ('missing explicit mapping target versions', lambda c, art: art['representation-policy']['data'].pop('mapping_targets')),
                ('reversed ID range', lambda c, art: c['source_atom_ids'].update(end=1)),
                ('MRDOC live stage', lambda c, art: art['source-plan']['data'].update(mrdoc_required=True)),
            ] if number == 0 else []:
                bad = copy.deepcopy(manifest); mutate(bad['configuration'], bad['artifacts'])
                reject(lambda: plan(bad), 'Reject ' + label + ' before native execution')
            values = output_fixture(recipe); write_outputs(target, values)
            good(execute.validate_outputs(recipe, target)['passed'],
                 'Release-aware independent output validation accepts publication ' + str(number + 1) + ' with its own range/qualifiers')
            reference = target / 'official'; reference.mkdir()
            for name in execute.OUTPUTS: shutil.copyfile(target / 'src' / name, reference / name)
            good(execute.compare_outputs(recipe, target, reference)['status'] == 'PASS_EXACT',
                 'All fields, IDs, qualifiers, grouping and duplicate multiplicity are compared for publication ' + str(number + 1))
            for label, name, row, column, value in [
                ('foreign publication qualifier', 'attributes.src', 0, 11, 'SNOMEDCT_US_2026_09_01'),
                ('out-of-range atom', 'classes_atoms.src', 0, 0, '42'),
                ('wrong atom publication', 'classes_atoms.src', 0, 1, 'SNOMEDCT_US_2026_09_01'),
                ('wrong relationship publication', 'relationships.src', 0, 6, 'SNOMEDCT_US_2026_09_01'),
                ('wrong merge publication', 'mergefacts.src', 0, 3, 'SNOMEDCT_US_2026_09_01'),
                ('wrong context publication', 'contexts.src', 0, 4, 'SNOMEDCT_US_2026_09_01'),
                ('dangling description attribute', 'attributes.src', 0, 1, '99999'),
                ('broken context identity', 'contexts.src', 0, 11, '99999'),
                ('wrong attribute digest', 'attributes.src', 0, 13, '0' * 32),
            ] if number == 0 else []:
                bad = copy.deepcopy(values); bad[name][row][column] = value; write_outputs(target, bad)
                good(not execute.validate_outputs(recipe, target)['passed'], 'Independent validator rejects ' + label)
            write_outputs(target, values)
            (target / 'src/relationships.src').write_text(''.join('|'.join(row) + '\n' for row in values['relationships.src']) * 2)
            good(execute.compare_outputs(recipe, target, reference)['status'] != 'PASS_EXACT', 'Duplicated full records cannot be ignored ' + str(number + 1))
    # Test physical content failures with freshly bound hashes, demonstrating
    # semantic/header discovery independently of the common byte verifier.
    for label, role, change in [
        ('wrong actual header', 'rf2-concepts', lambda text: text.replace('definitionStatusId', 'unexpectedColumn', 1)),
        ('future actual effective date', 'rf2-concepts', lambda text: text.replace('20200131', '20990101', 1)),
        ('unknown actual relationship type', 'rf2-relationships', lambda text: text.replace('116680003', '999999999', 1)),
        ('unknown actual description type', 'rf2-descriptions', lambda text: text.replace('900000000000003001', '999999999', 1)),
        ('duplicate actual Snapshot row', 'rf2-concepts', lambda text: text + text.splitlines()[1] + '\n'),
    ]:
        with tempfile.TemporaryDirectory(prefix='snomed-release-reject-') as directory:
            target = Path(directory).resolve(); recipe = materialize(first, target)
            destination = recipe['validation']['native_paths'][role]; path = target / destination
            path.chmod(0o644); path.write_text(change(path.read_text())); path.chmod(0o444)
            info = execute.file_info(path); recipe['validation']['input_fingerprints'][destination] = {key: info[key] for key in ('sha256', 'bytes')}
            good(not execute.validate_inputs(recipe, target)['passed'], 'Physical discovery rejects ' + label + ' even with updated file identity')
    with tempfile.TemporaryDirectory(prefix='snomed-release-settings-') as directory:
        target = Path(directory).resolve(); recipe = materialize(first, target)
        path = target / 'etc/sct.cfg'; path.chmod(0o644)
        good(not execute.validate_inputs(recipe, target)['passed'], 'Writable generated cfg is rejected')
    with tempfile.TemporaryDirectory(prefix='snomed-release-policy-') as directory:
        target = Path(directory).resolve(); changed = fixture()
        changed['artifacts']['representation-policy']['data']['mappings']['description_types']['900000000000003001']['tty'] = 'PT'
        recipe = materialize(changed, target)
        good(not execute.validate_inputs(recipe, target)['passed'], 'A typed policy declaration cannot silently change the captured TTY representation')
    with tempfile.TemporaryDirectory(prefix='snomed-release-metadata-wire-') as directory:
        target = Path(directory).resolve(); manifest = fixture()
        materialize(manifest, target)
        state = manifest['artifacts']['ncimeta-snapshot']; state['data']['metadata_format'] = {}
        for role, key, destination in [('sources-src','sources_rows','src/sources.src'),('termgroups-src','termgroups_rows','src/termgroups.src')]:
            wire = ''.join('|'.join(row)+'|\n' for row in state['data'][key]).encode()
            entry = next(item for item in state['files'] if item['role'] == role)
            entry.update(sha256=hashlib.sha256(wire).hexdigest(),bytes=len(wire))
            state['data']['metadata_format'][role] = {'terminal_delimiter':True}
            path = target / destination; path.chmod(0o644);path.write_bytes(wire);path.chmod(0o444)
        recipe = plan(manifest)
        good(execute.validate_inputs(recipe,target)['passed'], 'Explicit terminal-delimiter dialect preserves archived metadata bytes with logical20/6fields')
        state['data']['metadata_format']['sources-src']['terminal_delimiter']='yes'
        reject(lambda:plan(manifest),'Metadata wire-dialect flags must be explicit booleans')
    # Captured conversion changes are restricted to the three reviewed target
    # literal substitutions; every other byte and the cleanup script agree.
    ref = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'; source = 'sources/SNOMEDCT_US_2026_09_01/bin/'
    original_perl = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + source + 'invert_rf2.pl'])
    generic_perl = (ROOT / execute.PACKAGE / 'bin/invert_rf2.pl').read_bytes()
    reverted = generic_perl
    for new, old in [(b"my($ICDversion) = $$CfgRef->getReqEle('MappingTarget.ICD9CM.Version');", b'my($ICDversion) = "2013";'),
                     (b"$$CfgRef->getReqEle('MappingTarget.ICD10')", b'"${ICDRSAB}_2016"'),
                     (b"$$CfgRef->getReqEle('MappingTarget.ICD10CM')", b'"${ICDRSAB}_2027"')]:
        assert reverted.count(new) == 1; reverted = reverted.replace(new, old)
    good(reverted == original_perl, 'Canonical converter differs from verified production bytes only in the three explicit target bindings')
    original_cleanup = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':' + source + 'rmdanglingattrs.pl'])
    good((ROOT / execute.PACKAGE / 'bin/rmdanglingattrs.pl').read_bytes() == original_cleanup,
         'Canonical dangling-attribute cleanup is byte-identical to production')
    # Historical cfg is an independent expected result, never a renderer input.
    captured_cfg = subprocess.check_output(['git', '-C', str(ROOT), 'show', ref + ':sources/SNOMEDCT_US_2026_09_01/etc/sct.cfg'])
    historical = fixture()
    cfg = historical['configuration']; artifacts = historical['artifacts']; previous_version = cfg['version']
    cfg['version'] = 'SNOMEDCT_US_2026_09_01'; cfg['replacement_baseline']['version'] = 'SNOMEDCT_US_2026_03_01'
    cfg['source_atom_ids'].update(start=777343593, end=779143592)
    artifacts['id-allocation']['data'].update(start=777343593, end=779143592)
    artifacts['source-plan']['data']['replacement_baseline'] = copy.deepcopy(cfg['replacement_baseline'])
    case = json.loads((ROOT / 'docs/inversion-review/case-catalog/snomedct_us-as-produced.json').read_text())
    native_capture = case['artifacts'][case['configuration']['inputs']['source_data'][0]]['value']
    paths_by_role = {entry['role']: entry for entry in artifacts['native-release']['files']}
    for captured in native_capture:
        name = Path(captured['path']).name
        matches = [entry for entry in paths_by_role.values() if Path(entry['uri']).name.rsplit('_',1)[0] == name.rsplit('_',1)[0]]
        assert len(matches) == 1
        matches[0]['uri'] = 'file:///capture/' + captured['path']
    artifacts['native-release']['data'].update(publisher_release_date='2026-09-01', package_name='SnomedCT_ManagedServiceUS_PRODUCTION_US1000124_20260901T120000Z')
    meta = artifacts['ncimeta-snapshot']; meta['data']['sources_rows'][0][0:2] = [cfg['version'], cfg['replacement_baseline']['version']]
    for row in meta['data']['termgroups_rows']:
        row[0] = cfg['version'] + '/' + row[5]
    for role, key in [('sources-src','sources_rows'),('termgroups-src','termgroups_rows')]:
        raw = ''.join('|'.join(row)+'\n' for row in meta['data'][key]).encode()
        entry = next(value for value in meta['files'] if value['role'] == role)
        entry.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    rendered = execute.properties(base64.b64decode(plan(historical)['generated_files'][0]['data_b64']), True)
    expected = execute.properties(captured_cfg, True)
    extra = {'MappingTarget.ICD10','MappingTarget.ICD10CM','MappingTarget.ICD9CM.Version'}
    good({key:value for key,value in rendered.items() if key not in extra | {'File.INP.COMPLEXMAPS'}} ==
         {key:value for key,value in expected.items() if key != 'File.INP.COMPLEXMAPS'},
         'Every consumed effective historical setting matches independent production cfg, with explicit targets and absent ComplexMap tracked separately')
    expression = re.search(r'my\(\$ICDVSAB\).*?"UNKNOWN";', generic_perl.decode(), re.S)[0]
    for target in ('ICD10CM_2027', 'ICD10CM_2026'):
        probe = "{package FixtureCfg;sub getReqEle{return $_[0]->{$_[1]};}}\n" + \
                "my $cfg=bless {'MappingTarget.ICD10'=>'ICD10_2016','MappingTarget.ICD10CM'=>'" + target + "'},'FixtureCfg';my $CfgRef=\\$cfg;\n" + \
                "my($i10id,$i10cmid,$refSetId,$ICDRSAB)=('447562003','6011000124106','6011000124106','ICD10CM');\n" + expression + '\nprint $ICDVSAB;'
        actual = subprocess.check_output(['/usr/bin/perl', '-e', probe]).decode()
        good(actual == target, 'Actual canonical Perl target expression honors reviewed target ' + target + ' without a release-year assumption')
    return passed


if __name__ == '__main__':
    results = check()
    for label in results: print('PASS', label)
    print(len(results), 'generic SNOMED execution checks passed')
