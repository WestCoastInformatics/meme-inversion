#!/usr/bin/env python3
"""Physical synthetic NCIt execution-plan checks; no native full inversion."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import check_release_nci
import execute_release_nci as execute
import nci_source_plan
import release_nci

ROOT = Path(__file__).resolve().parents[1]


def fixture(version='NCI_2026_10D', prior='NCI_2026_08E', additions=False):
    manifest = check_release_nci.fixture(version, prior, additions)
    config, artifacts = manifest['configuration'], manifest['artifacts']
    template = (ROOT / 'engines/nci/nci.cfg.in').read_bytes()
    code = [{'relative_path': 'nci.cfg.in', 'sha256': execute._sha(template), 'data_b64': base64.b64encode(template).decode(), 'mode': '0o444'}]
    root = artifacts['saved-root']['data']
    root.update(root_code='V-NCI', root_name='National Cancer Institute Thesaurus')
    cfg = template.decode().replace('{{release}}', version[4:]).replace('{{source_atom_ids.start}}', str(config['source_atom_ids']['start'])).replace('{{identity_state.root_atom_id}}', str(root['root_atom_id'])).encode()
    properties = execute._properties(cfg)
    plan = artifacts['release-plan']['data']
    if additions:
        for addition in plan['new_subsources']:
            source = addition['metadata']['stripped_source']
            for alias in addition['publisher_names']:
                properties['vsab.' + alias] = source + '_' + version[4:]
                properties['rsab.' + alias] = source
        cfg = ''.join(key + ' = ' + value + '\n' for key, value in properties.items()).encode()
    model = artifacts['representation-policy']['data']['metadata_model']
    model.update(publisher_termgroups=[['NCI', 'PT'], ['NCI', 'SY']], publisher_properties=['P108', 'P90'],
                 publisher_labels={'P108': 'Preferred_Name', 'R1': 'related_to'}, relationship_roles=['R1'])
    variables = {'release': version[4:], 'replacement_release': prior[4:]}
    sources = [nci_source_plan.row(model['sources'][0], nci_source_plan.SOURCE_FIELDS, variables)]
    groups = [nci_source_plan.row(model['termgroups'][0], nci_source_plan.TERMGROUP_FIELDS, variables)]
    for addition in plan['new_subsources']:
        sources.append(nci_source_plan.row(addition['metadata'], nci_source_plan.SOURCE_FIELDS, variables))
    for addition in plan['new_termgroups']:
        groups.append(nci_source_plan.row(addition['metadata'], nci_source_plan.TERMGROUP_FIELDS, variables))
    serialize = lambda rows, fields: ''.join('|'.join(row[key] for key in fields) + '|\n' for row in rows).encode()
    raw = {'annotationDeclaration': b'P108|label|Preferred_Name\n', 'objectDeclaration': b'R1|label|related_to\n',
           'classDeclaration': b'C1|P108|Alpha\nC2|P108|Beta\n', 'relations': b'C1||R1|C2\n', 'hierarchy': b'C2|C1\n',
           'sources-src': serialize(sources, nci_source_plan.SOURCE_FIELDS),
           'termgroups-src': serialize(groups, nci_source_plan.TERMGROUP_FIELDS), 'nci-configuration': cfg}
    if additions:
        raw['classDeclaration'] += b'C1|P90|Alpha external|P383|PT|P384|Synthetic publisher\n'
    for item in artifacts['publisher']['files']:
        value = raw[item['role']]
        item.update(sha256=execute._sha(value), bytes=len(value))
    state = copy.deepcopy(artifacts['publisher'])
    state.update(artifact_type='ncimeta-state', data={'profile': execute.PROFILE, 'replacement_baseline': copy.deepcopy(config['replacement_baseline']), 'properties': properties}, files=[])
    for role in execute.STATE_ROLES:
        value = raw[role]
        state['files'].append({'role': role, 'uri': 'file:///SYNTHETIC/' + role, 'sha256': execute._sha(value), 'bytes': len(value)})
    artifacts['state'] = state;config['inputs']['reference_ncimeta'] = 'state'
    return manifest, code, raw


def stage(plan, raw, target):
    for item in plan['input_files']:
        path = target / item['destination'];path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw[item['role']])
    for item in plan['generated_files']:
        path = target / item['relative_path'];path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(item['data_b64']));path.chmod(int(item['mode'], 8))


def outputs(plan, target):
    version = plan['version']
    def row(name, values):
        (target / 'src' / name).write_text('|'.join(values) + '\n')
    row('classes_atoms.src', ['10000', version, version + '/PT', 'C1', 'R', 'Y', 'N', 'Alpha', 'N', '', 'C1', '', 'ENG', '1000', ''])
    value = 'Definition'
    row('attributes.src', ['1', '10000', 'C', 'DEFINITION', value, version, 'R', 'Y', 'N', 'N', 'SRC_ATOM_ID', '', '', hashlib.md5(value.encode()).hexdigest(), ''])
    row('relationships.src', ['1', 'C', '10000', 'RT', '', '10000', version, version, 'R', 'Y', 'N', 'N', 'SRC_ATOM_ID', '', 'SRC_ATOM_ID', '', '', '', ''])
    row('mergefacts.src', ['10000', 'SY', '10000', version, '', 'Y', 'N', 'NCI-SY', 'SRC_ATOM_ID', '', 'SRC_ATOM_ID', '', ''])
    row('contexts.src', ['10000', 'PAR', 'isa', '321', version, version, '', '321', '00', '', '', '10000', 'SRC_ATOM_ID', '', '321', 'SRC_ATOM_ID', '', ''])


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def build(args):
        return execute.build_plan(args[0]['configuration'], args[0]['artifacts'], args[1])
    def reject(label, mutate):
        args = fixture();mutate(args)
        try:
            build(args)
        except (ValueError, KeyError):
            checks.append(label)
        else:
            raise AssertionError(label)
    def physical_reject(label, role, alter):
        args = fixture()
        args[2][role] = alter(args[2][role])
        for artifact in args[0]['artifacts'].values():
            for descriptor in artifact['files']:
                if descriptor['role'] == role:
                    descriptor.update(sha256=execute._sha(args[2][role]), bytes=len(args[2][role]))
        plan = build(args)
        with tempfile.TemporaryDirectory(prefix='check-nci-physical-reject-') as directory:
            target = Path(directory).resolve();stage(plan, args[2], target)
            good(not execute.validate_inputs(plan, target)['passed'], label)
    args = fixture();before = copy.deepcopy(args)
    plan = build(args)
    good(execute.rebuild_plan(args[0]['configuration'], args[0]['artifacts'], args[1]) == plan, 'Runtime rebuild uses the same source planner and exactly reproduces its admitted recipe')
    forged = copy.deepcopy(plan);forged['stages'][0]['argv'] = ['/usr/bin/true']
    good(execute.rebuild_plan(args[0]['configuration'], args[0]['artifacts'], args[1]) != forged, 'Resealing an altered native command cannot change the source-fixed rebuilt recipe')
    good(args == before, 'Planning preserves every configuration/artifact/code value')
    good(plan == build(args), 'Frozen archived inputs produce the same deterministic recipe')
    good(plan['version'] == 'NCI_2026_10D' and plan['validation']['replacement_baseline']['version'] == 'NCI_2026_08E', 'Explicit August predecessor supports skipped September')
    second = fixture('NCI_2027_02B', 'NCI_2026_12C', True)
    second_plan = build(second)
    good(len(plan['stages']) == len(second_plan['stages']) == 6 and plan['output_files'] == second_plan['output_files'], 'The identical planner supports another release with skipped January and optional additions')
    good(all('2026_10D' not in str(stage) for stage in second_plan['stages']), 'Native stage names and commands contain no characterized-version constants')
    good(len(plan['input_files']) == 8 and len(plan['generated_files']) == 3, 'Only five native files and three preserved data files are seeded; three settings/plan files are generated')
    good(not any(item['destination'] in execute.OUTPUTS for item in plan['input_files']), 'Completed official outputs can never be seed inputs')
    good(all(not any(term in str(stage['argv']) for term in ('ssh', 'sql', 'curl', 's3')) for stage in plan['stages']), 'Native stages use fixed local code and contain no acquisition/database commands')
    declaration = release_nci.analyze(args[0]['configuration'], args[0]['artifacts'])
    codes = {row['code'] for row in declaration['issues']}
    good(not any(row['severity'] == 'error' for row in declaration['issues']), 'Preserved-preparation profile is recognized by declaration preflight')
    good('NCI_PHYSICAL_INPUT_VALIDATION_REQUIRED' in codes and not set(release_nci.CAPTURE_BLOCKERS) & codes, 'Preserved input closure requires physical checks rather than authenticating a newly invented exporter')
    good(not declaration['facts']['execution_authorized'] and not declaration['facts']['production_eligible'], 'Declaration preview remains unable to authorize execution')
    with tempfile.TemporaryDirectory(prefix='check-execute-release-nci-') as directory:
        target = Path(directory).resolve()
        stage(plan, args[2], target)
        checked = execute.validate_inputs(plan, target)
        good(checked['passed'] and checked['facts']['native_rows']['classDeclaration'] == 2, 'Actual native row scan and preserved metadata/configuration validate')
        good(checked['facts']['discovery']['status'] == 'PASS', 'Existing physical discovery runs against preserved metadata instead of a representation-catalog membership claim')
        frozen = target / 'plan.json';frozen.write_text(json.dumps(plan))
        runtime = subprocess.run([sys.executable, '-S', '-c',
            'import json,sys;sys.path.insert(0,sys.argv[1]);import execute_release_nci as e;'
            'r=e.validate_inputs(json.load(open(sys.argv[2])),sys.argv[3]);'
            'print(json.dumps(r));sys.exit(0 if r["passed"] else 1)', str(ROOT / 'tools'), str(frozen), str(target)], capture_output=True, text=True)
        good(runtime.returncode == 0, 'Physical runtime validation works with Python -S and no third-party packages')
        capsule = target / 'rebuild.json';capsule.write_text(json.dumps({'manifest': args[0], 'code_files': args[1]}))
        rebuilt = subprocess.run([sys.executable, '-S', '-c',
            'import json,sys;sys.path.insert(0,sys.argv[1]);import execute_release_nci as e;'
            'v=json.load(open(sys.argv[2]));m=v["manifest"];'
            'p=e.rebuild_plan(m["configuration"],m["artifacts"],v["code_files"]);'
            'sys.exit(0 if p==json.load(open(sys.argv[3])) else 1)', str(ROOT / 'tools'), str(capsule), str(frozen)], capture_output=True, text=True)
        good(rebuilt.returncode == 0, 'Worker rebuild works with Python -S without schema files or third-party dependencies')
        (target / 'bin').mkdir();(target / 'tmp').mkdir()
        for name in ('create_rolegroups.pl', 'create_tref.pl', 'delete_dup_tref_lines.pl'):
            (target / 'bin' / name).write_bytes((ROOT / 'engines/nci/bin' / name).read_bytes())
        for native_stage in plan['stages'][:-1]:
            output = target / native_stage['stdout'] if 'stdout' in native_stage else None
            if output:
                with output.open('wb') as handle:
                    subprocess.run(native_stage['argv'], cwd=target / native_stage['cwd'], stdout=handle, stderr=subprocess.PIPE, check=True, timeout=30)
            else:
                subprocess.run(native_stage['argv'], cwd=target / native_stage['cwd'], capture_output=True, check=True, timeout=30)
        good((target / 'orig/MRCONSO.TREF').read_bytes().count(b'\n') == 2 and (target / 'orig/MRREL.TREF').is_file() and (target / 'orig/MRSAT.TREF').is_file(),
             'Actual Git-owned Perl preparation scripts consume the planned roles and regenerate all three TREF files locally')
        outputs(plan, target)
        validated = execute.validate_outputs(plan, target)
        good(validated['passed'], 'Valid physical src structures/digests/typed references and declared ID range pass independently')
        (target / 'src/attributes.src').write_text((target / 'src/attributes.src').read_text().replace('Definition', 'Tampered'))
        good(not execute.validate_outputs(plan, target)['passed'], 'A changed attribute value with stale digest fails output validation')
        outputs(plan, target)
        attributes = target / 'src/attributes.src';attributes.write_bytes(attributes.read_bytes() * 2)
        good(not execute.validate_outputs(plan, target)['passed'], 'Duplicate generated attribute IDs fail output validation')
        outputs(plan, target)
        path = target / 'src/classes_atoms.src';path.write_text(path.read_text().replace('10000', '9999', 1))
        good(not execute.validate_outputs(plan, target)['passed'], 'An out-of-range emitted SAID fails independent validation')
        native = target / plan['validation']['native_inputs']['classDeclaration']['relative_path']
        native.write_bytes(native.read_bytes() + b'C3|P108|Unexpected\n')
        good(not execute.validate_inputs(plan, target)['passed'], 'Mutation of an actual publisher file fails frozen hash checks')
    with tempfile.TemporaryDirectory(prefix='check-execute-release-nci-additions-') as directory:
        target = Path(directory).resolve()
        stage(second_plan, second[2], target)
        good(execute.validate_inputs(second_plan, target)['passed'], 'Optional root and termgroup decisions agree with real staged metadata and publisher records')
        path = target / 'etc/preserved-nci.cfg';path.write_bytes(path.read_bytes() + b'Unexpected = true\n')
        good(not execute.validate_inputs(second_plan, target)['passed'], 'Actual archived configuration cannot disagree with its frozen declared properties')
    reject('The same or a later baseline is not accepted', lambda a: a[0]['configuration'].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2026_10D'}))
    reject('Allocation seed must match preserved native configuration', lambda a: (a[0]['configuration']['source_atom_ids'].update(start=10001), a[0]['artifacts']['allocation']['data'].update(start=10001)))
    reject('An allocation evidence float cannot pose as an integer', lambda a: a[0]['artifacts']['allocation']['data'].update(start=10000.0))
    reject('A source plan cannot silently change its predecessor', lambda a: a[0]['artifacts']['release-plan']['data'].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2026_09A'}))
    reject('Frozen preserved profile requires all three exact metadata/config roles', lambda a: a[0]['artifacts']['state']['files'].pop())
    reject('Fresh v2 state cannot masquerade as preserved conversion inputs', lambda a: a[0]['artifacts']['state']['data'].update(profile='ncimeta-installed-state-v2'))
    reject('Native paths cannot redirect output outside the candidate', lambda a: a[0]['artifacts']['state']['data']['properties'].update(SRCDIR='/tmp/other'))
    reject('An unknown native command/configuration meaning is rejected', lambda a: a[0]['artifacts']['state']['data']['properties'].update(ExecuteCommand='unsafe'))
    reject('Pinned Git template bytes cannot be substituted', lambda a: a[1][0].update(sha256='0' * 64))
    reject('Publisher filenames must retain their five distinct roles', lambda a: a[0]['artifacts']['publisher']['files'][0].update(uri='file:///other.txt'))
    reject('Saved hierarchy identity must belong to explicit prior', lambda a: a[0]['artifacts']['saved-root'].update(version='NCI_2026_09A'))
    physical_reject('Actual unknown source/term type is rejected even when newly hashed declarations conceal it', 'classDeclaration', lambda raw: raw + b'C1|P90|Unreviewed|P383|SY|P384|UNKNOWN\n')
    physical_reject('Actual label changes require review rather than trusting recorded label summaries', 'annotationDeclaration', lambda raw: raw.replace(b'Preferred_Name', b'Changed_Label'))
    physical_reject('Malformed actual hierarchy rows fail despite a matching file hash', 'hierarchy', lambda raw: raw + b'C3\n')
    physical_reject('Physical metadata cannot silently select a different predecessor even with its new hash supplied', 'sources-src', lambda raw: raw.replace(b'NCI_2026_08E', b'NCI_2026_09A'))
    return checks


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'scope': 'synthetic physical input/output validation; no native full inversion'}))
