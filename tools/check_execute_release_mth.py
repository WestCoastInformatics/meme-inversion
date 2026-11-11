#!/usr/bin/env python3
"""Tiny canonical MTH native fixtures with independent identity/history goldens."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

import check_release_mth
import execute_release_mth as execution

ROOT = Path(__file__).resolve().parents[1]


def _rrf(fields):
    return '|'.join(fields) + '|\n'


def fixture(directory, skipped=True, preserved_decisions=False):
    manifest = check_release_mth.example() if skipped else check_release_mth.direct_example()
    config, artifacts = manifest['configuration'], manifest['artifacts']
    current = config['version']
    previous = artifacts['mth-plan']['data']['publisher_previous']['version']
    baseline = config['replacement_baseline']['version']
    origin = directory / 'origin'
    origin.mkdir()

    def conso(cui, aui, source, code, name):
        return _rrf([cui, 'ENG', 'P', 'L' + aui[1:], 'PF', 'S' + aui[1:], 'Y', aui,
                     '', '', '', source, 'PT', code, name, '0', 'N', ''])

    def sab(source, version):
        fields = [''] * 25
        fields[:7] = ['VC' + source, 'RC' + source, version, source, 'Synthetic ' + source, source, version]
        fields[21:23] = ['Y', 'Y']
        return _rrf(fields)

    texts = {
        'MRCONSO.RRF': conso('C1', 'A1', current, 'M1', 'Alpha') + conso('C2', 'A2', 'NEWSOURCE_1', 'N1', 'Beta') +
                         conso('C3', 'A3', 'TEST_2026', 'T3', 'Previously installed CUI') +
                         conso('C4', 'A4', 'TEST_2026', 'T4', 'New split-only CUI') +
                         conso('C1', 'A5', 'TEST_2026', 'T5', 'Moved into current CUI'),
        'MRREL.RRF': _rrf(['C1', 'A1', 'AUI', 'RO', 'C2', 'A2', 'AUI', '', 'R1', '', current, current, '', 'Y', 'N', '']),
        'MRSAT.RRF': _rrf(['C1', '', '', 'A1', 'AUI', 'M1', 'AT1', '', 'SYNTHETIC', current, 'fixture', 'N', '']),
        'MRSTY.RRF': _rrf(['C4', 'T047', 'B2', 'Disease or Syndrome', 'AT2', '']),
        'MRDEF.RRF': _rrf(['C2', 'A2', 'AT3', '', 'NEWSOURCE_1', 'Synthetic definition', 'N', '']),
        'MRCUI.RRF': _rrf(['COLD', baseline[4:], 'SY', '', '', 'C1', 'Y']) +
                      _rrf(['COLD2', previous[4:], 'RB', '', '', 'C2', 'Y']) * 2 +
                      (_rrf(['COLD3', baseline[4:], 'RN', '', '', 'C1', 'Y']) if skipped else ''),
        'MRCXT.RRF': '',
        'MRSAB.RRF': sab('MTH', current) + sab('TEST', 'TEST_2026') + sab('NEWSOURCE', 'NEWSOURCE_1'),
        'MRRANK.RRF': _rrf(['1000', current, 'PT', 'N']) + _rrf(['900', 'NEWSOURCE_1', 'PT', 'N']) +
                       _rrf(['800', 'TEST_2026', 'PT', 'N']),
        'MRAUI.RRF': ''.join(_rrf([aui, 'L' + aui[1:], (baseline if skipped and aui == 'A4' else previous)[4:], 'SY', '', '', aui, cui, 'Y'])
                             for aui, cui in [('A3', 'C3'), ('A4', 'C4'), ('A5', 'C1')]),
        'MRDOC.RRF': _rrf(['REL', 'RO', 'expanded_form', 'has other relationship'])}
    source_fields = [current, baseline, '0', current, 'MTH', current[4:], 'MTH', 'Synthetic UMLS',
                     '', '', '', '', '', '', '', 'ENG', '', '', 'UTF-8', 'N']
    metadata = {'src/sources.src': _rrf(source_fields),
                'src/termgroups.src': _rrf([current + '/PT', baseline + '/PT', 'N', 'N', 'N', 'PT']),
                'src/vsab.updates': baseline + '|' + current + '\nNew|NEWSOURCE_1\n|TEST_2026\n',
                'src/sabs_updated_umls': current + '\nNEWSOURCE_1\n',
                'src/rsabs-updated.umls': 'MTH\nNEWSOURCE\n',
                'src/vcodes_updated': 'V-MTH\nV-NEWSOURCE\n',
                'ncimid.sources': ' SAB| VSAB\nMTH|' + baseline + '\nTEST|TEST_2026\n',
                'ncimid.termgroups': 'MTH/PT|1\nTEST/PT|2\n'}

    def descriptors(values, subdir):
        result = []
        for role, text in values.items():
            path = origin / subdir / role
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            raw = path.read_bytes()
            result.append({'role': role, 'uri': path.as_uri(), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        return result

    artifacts['mth-prepared']['files'] = descriptors(texts, 'prepared')
    artifacts['mth-prepared']['data']['selected_sources'] = ['MTH', 'TEST', 'NEWSOURCE']
    artifacts['mth-state']['files'] = descriptors(metadata, 'state')
    artifacts['mth-identity']['files'] = descriptors({'cui_said_map': 'C3|777\nCOLD|778\n'}, 'identity')
    if preserved_decisions:
        data = artifacts['mth-plan']['data']
        raw_decisions = '\n'.join('|'.join((item['source'], item['version'], item['disposition'],
            'exclude termgroups: ' + ','.join(item['excluded_termgroups']) if item['excluded_termgroups'] else ''))
            for item in data['dispositions']) + '\n'
        raw_map = ' RSAB | UMLS VSAB | NCI VSAB\n' + '\n'.join('|'.join((item['source'], item['publisher_version'], item['version']))
                                                            for item in data['vsab_mappings']) + '\n'
        root = data['src_root']
        raw_root = '|'.join((current, root['status'], root['term_type'], root['name'])) + '\n'
        artifacts['mth-plan']['files'] = descriptors({'ncisources.spec': raw_decisions,
                                                       'sab.vsab.map': raw_map, 'src_data': raw_root}, 'source-plan')
        projected = execution.manifest_decisions_from_preserved(raw_decisions.encode(), raw_map.encode(), raw_root.encode(),
                        metadata['ncimid.sources'].encode(), texts['MRSAB.RRF'].encode(), current, review_id=data['review_id'])
        data['preserved_decision_sha256'] = projected['preserved_decision_sha256']
        check_release_mth.bind_producer_inputs(manifest)
    code = []
    for path in sorted((ROOT / execution.PACKAGE).rglob('*')):
        if path.is_file():
            raw = path.read_bytes()
            code.append({'repository_path': path.relative_to(ROOT).as_posix(),
                         'sha256': hashlib.sha256(raw).hexdigest(), 'data_b64': base64.b64encode(raw).decode(),
                         'mode': oct(path.stat().st_mode & 0o777)})
    plan = execution.build_plan(config, artifacts, code_files=code)
    meme = directory / 'MEME5'
    target = meme / 'inv/sources' / current
    target.mkdir(parents=True)
    for item in code:
        path = target / item['repository_path'].removeprefix(execution.PACKAGE + '/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(item['data_b64']))
        path.chmod(int(item['mode'], 8))
    for item in plan['input_files']:
        descriptor = next(value for value in artifacts[item['artifact']]['files'] if value['role'] == item['role'])
        destination = execution.input_path(item, target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(Path(descriptor['uri'].removeprefix('file://')).read_bytes())
        destination.chmod(0o444)
    for item in plan['generated_files']:
        path = target / item['relative_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(item['data_b64']))
        path.chmod(0o444)
    for item in plan['symlinks']:
        path = target / item['relative_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(item['target'])
    run = directory / 'run'
    (run / 'apparatus').mkdir(parents=True)
    for name in ['execute_release_mth.py', 'release_mth.py', 'compare_mth_core.py', 'acquire_mth_subset.py', 'compare_nci_core.py']:
        (run / 'apparatus' / name).write_bytes((ROOT / 'tools' / name).read_bytes())
    (run / 'native-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    return manifest, plan, target, run, code


def run_tiny(plan, target, run):
    env = dict(os.environ, LANG='C', LC_ALL='C', LC_COLLATE='C', _POSIX2_VERSION='1', PATH_TO_PERL='/usr/bin/perl')
    for item in plan['stages']:
        argv = [value.replace('{python}', sys.executable).replace('{target}', str(target)).replace('{run}', str(run)) for value in item['argv']]
        result = subprocess.run(argv, cwd=target / item['cwd'], env=env, capture_output=True, timeout=30)
        (run / (item['name'] + '.stdout')).write_bytes(result.stdout)
        (run / (item['name'] + '.stderr')).write_bytes(result.stderr)
        assert result.returncode == 0, (item['name'], result.stderr.decode(errors='replace')[-1200:])


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def rejects(action, label):
        try:
            action()
        except (ValueError, RuntimeError):
            passed.append(label)
        else:
            raise AssertionError(label)

    authoritative = 'b2611abcf929981628bb2e5051afb450b8525b70'
    source_paths = {'SRCbuilder.pl': 'INV/bin/SRCbuilder.pl',
                    'print.raw3.to.attributes.pl': 'INV/bin/print.raw3.to.attributes.pl'}
    for path in sorted((ROOT / execution.PACKAGE / 'bin').iterdir()):
        original_path = source_paths.get(path.name, 'sources/MTH_2026AA/' + path.name)
        original = subprocess.check_output(['git', '-C', str(ROOT), 'show', authoritative + ':' + original_path])
        expected = original.replace(b'/bin/sort', b'/usr/bin/sort').replace(b'/bin/awk', b'/usr/bin/awk') if path.name == 'raw_to_contexts.csh' else original
        good(path.read_bytes() == expected, 'Canonical consumer matches corrected authoritative bytes with only declared utility-path adaptation: ' + path.name)
    for name in ['inv1.spec', 'inv2.spec', 'inv3.spec']:
        original = subprocess.check_output(['git', '-C', str(ROOT), 'show', authoritative + ':sources/MTH_2026AA/' + name]).decode()
        expected = original.replace('SourceDir|/local/content/MEME/MEME5/inv/sources/MTHrelease', 'SourceDir|.')
        expected = expected.replace('DefineConst|MTHSAB|MTHrelease', 'DefineConst|MTHSAB|{{version}}')
        if name == 'inv3.spec':
            expected = expected.replace('MRCUI*', 'bequeathal_history.RRF').replace("(<VER> eq 'prevrel1')", '{{bequeathal_predicate}}')
        good((ROOT / execution.PACKAGE / 'templates' / (name + '.in')).read_text() == expected,
             'Canonical spec preserves all corrected rule bytes beyond explicit source/history parameters: ' + name)

    for skipped in (False, True):
        with tempfile.TemporaryDirectory(prefix='canonical-mth-native-') as temporary:
            manifest, plan, target, run, code = fixture(Path(temporary), skipped)
            label = plan['version']
            before = copy.deepcopy(manifest)
            good(plan == execution.build_plan(manifest['configuration'], manifest['artifacts'], code),
                 'Frozen canonical template renderer is deterministic without effective target spec oracles: ' + label)
            with patch.object(execution, 'ROOT', Path('/unavailable-local-checkout')):
                good(plan == execution.build_plan(manifest['configuration'], manifest['artifacts'], code),
                     'Supplied frozen code completely removes local filesystem template dependency: ' + label)
            good(all(not item['repository_path'].startswith('sources/') for item in code),
                 'Only canonical Git package files supply execution code/templates: ' + label)
            good(execution.validate_inputs(plan, target)['passed'], 'Physical prepared RRF/metadata/identity closure passes: ' + label)
            if not skipped:
                def damaged(role, transform, code, rebind=True):
                    item = next(item for item in plan['validation']['input_identities'] if item['role'] == role)
                    path = execution.input_path(item, target)
                    original = path.read_bytes()
                    path.chmod(0o644);path.write_bytes(transform(original));path.chmod(0o444)
                    changed = copy.deepcopy(plan)
                    if rebind:
                        record = next(value for value in changed['validation']['input_identities'] if value['role'] == role)
                        record.update(execution.identity(path))
                    checked = execution.validate_inputs(changed, target)
                    good(not checked['passed'] and any(value['code'] == code for value in checked['issues']),
                         'Physical input validation rejects ' + code + ' despite declared hash rebinding=' + str(rebind))
                    path.chmod(0o644);path.write_bytes(original);path.chmod(0o444)
                damaged('MRCONSO.RRF', lambda raw: raw.replace(b'Alpha', b'Changed'), 'MTH_INPUT_CHANGED', False)
                damaged('MRCONSO.RRF', lambda raw: b'C1|missing fields|\n', 'MTH_INPUT_DIALECT')
                damaged('MRSAB.RRF', lambda raw: raw.replace(label.encode(), b'MTH_2099AA'), 'MTH_PREPARED_NATIVE_RELEASE')
                damaged('src/sources.src', lambda raw: raw.replace(b'|MTH_2026AA|', b'|MTH_2025AB|'), 'MTH_SOURCE_BASELINE')
                damaged('src/termgroups.src', lambda raw: b'invalid|metadata|\n', 'MTH_INPUT_DIALECT')
                damaged('ncimid.sources', lambda raw: raw.replace(b'TEST_2026', b'TEST_2025'), 'MTH_INSTALLED_SNAPSHOT')
                damaged('src/vsab.updates', lambda raw: raw.replace(b'|TEST_2026', b'WRONG|TEST_2026'), 'MTH_VSAB_UPDATE_DECISION')
                damaged('src/sabs_updated_umls', lambda raw: raw.replace(b'NEWSOURCE_1\n', b''), 'MTH_UPDATED_VSABS')
                damaged('src/rsabs-updated.umls', lambda raw: raw.replace(b'NEWSOURCE\n', b''), 'MTH_UPDATED_RSABS')
                damaged('src/vcodes_updated', lambda raw: raw.replace(b'V-NEWSOURCE\n', b''), 'MTH_UPDATED_ROOT_CODES')
                damaged('cui_said_map', lambda raw: raw + b'C3|999\n', 'MTH_INPUT_DIALECT')
                settings = target / 'range3.spec';settings.chmod(0o644)
                good(not execution.validate_inputs(plan, target)['passed'], 'Writable generated settings block native stages')
                settings.chmod(0o444)
            good((target / 'old/src/cui_said_map').resolve() == (target.parent / 'MTH_2026AA/src/cui_said_map').resolve() and
                 (target / 'src/Meta/MRCONSO.RRF').resolve() == (target.parents[2] / ('mr/umls/' + label[4:] + '/subset3/METASUBSET/MRCONSO.RRF')).resolve(),
                 'Prior CUI and prepared native files retain standard mirrored dependency paths: ' + label)
            source_metadata = target / 'src/sources.src'
            original_metadata = source_metadata.read_bytes()
            run_tiny(plan, target, run)
            good(execution.validate_inputs(plan, target)['passed'] and source_metadata.read_bytes() == original_metadata and
                 source_metadata.stat().st_mode & 0o777 == 0o444,
                 'All declared inputs/settings remain intact after actual tiny native stages: ' + label)
            validated = execution.validate_outputs(plan, target)
            good(validated['passed'], 'Generic core and complete retained-identity validation passes actual tiny native output: ' + label + ' ' + str(validated['issues']))
            expected = {'aui_said_map': b'A1|C1|1003\nA2|C2|1004\n',
                        'moved_aui_said_map': b'A3|C3|1005\nA4|C4|1006\nA5|C1|1007\n',
                        'cui_said_map': b'C1|1003\nC2|1004\nC4|1006\n',
                        'rel_cui_said_map': b'C1|1003\nC2|1004\nC4|1006\n',
                        'cui_splitonly_said_map': b'C4|1006\n', 'cui.splitonly.new': b'C4\n'}
            for name, raw in expected.items():
                good((target / 'src' / name).read_bytes() == raw,
                     'Independent native moved/current/split identity golden: ' + label + '/' + name)
            bequeathals = [(row.split('|')[2], row.split('|')[5], row.split('|')[12], row.split('|')[14])
                           for row in (target / 'src/bequeathal.relationships.src').read_text().splitlines()]
            expected_bequeathals = [('C2', 'COLD2', 'CUI_CURRENT', 'CUI_PREVIOUS')] * 2
            if skipped:
                expected_bequeathals += [('C1', 'COLD3', 'CUI_CURRENT', 'CUI_PREVIOUS')]
            good(bequeathals == expected_bequeathals,
                 'Explicit publisher history preserves duplicate bequeathal rows and current/previous CUI roles: ' + label)
            good((target / 'src/auis_nonupdatedSAB_moved').read_bytes() == b'A3|C3\nA4|C4\nA5|C1\n',
                 'Portable join projection preserves the captured source/AUI/CUI fields exactly: ' + label)
            good((target / 'src/cui_merges').read_bytes() == b'COLD|C1\n' and manifest == before,
                 'Inserted baseline history selection remains distinct from publisher-previous version: ' + label)
            reference = Path(temporary) / 'synthetic-expected'
            for name in plan['output_files']:
                path = reference / name;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes((target / name).read_bytes())
            compared_plan = copy.deepcopy(plan)
            compared_plan['validation'].update(reference_version=label, reference_stage='inversion-src', reference_files=[
                {'role': name, **execution.identity(reference / name)} for name in plan['output_files']])
            good(execution.compare_outputs(compared_plan, target, reference)['acceptance']['status'] == 'PASS_EXACT',
                 'Release-aware comparator accepts exact synthetic references after independent validation: ' + label)
            changed = target / 'src/aui_said_map'
            original_map = changed.read_bytes()
            changed.write_bytes(original_map.splitlines(keepends=True)[0])
            good(not execution.validate_outputs(plan, target)['passed'] and
                 any(item['code'] == 'MTH_IDENTITY_COVERAGE' for item in execution.validate_outputs(plan, target)['issues']),
                 'Omitting an otherwise valid retained AUI mapping is independently rejected: ' + label)
            changed.write_bytes(original_map)
            extra = target / 'src/bequeathal.relationships.src'
            original_bequeathals = extra.read_bytes()
            extra.write_bytes(original_bequeathals.splitlines(keepends=True)[0])
            good(execution.compare_outputs(compared_plan, target, reference)['acceptance']['status'] == 'DIFFERENCES_REQUIRE_REVIEW',
                 'Native output mismatch never inherits historical 2026AA correction waiver: ' + label)
            extra.write_bytes(original_bequeathals)
            wrong = copy.deepcopy(compared_plan);wrong['validation']['reference_version'] = 'MTH_2025AB'
            rejects(lambda: execution.compare_outputs(wrong, target, reference),
                    'Older change-detection baseline cannot masquerade as current-release expected output: ' + label)
            rejects(lambda: execution.compare_outputs(plan, target, reference),
                    'Comparison cannot claim current-release equivalence without declared current oracle: ' + label)
    with tempfile.TemporaryDirectory(prefix='mth-preserved-decision-proof-') as temporary:
        manifest, plan, target, run, code = fixture(Path(temporary), True, preserved_decisions=True)
        good(execution.validate_inputs(plan, target)['passed'],
             'Typed curation is physically reconciled with all three authoritative preserved decision files')
        original = target / 'orig/source-plan'
        args = tuple((original / name).read_bytes() for name in ('ncisources.spec', 'sab.vsab.map', 'src_data'))
        args += ((target / 'ncimid.sources').read_bytes(), (target / 'src/Meta/MRSAB.RRF').read_bytes(), plan['version'])
        projected = execution.manifest_decisions_from_preserved(*args)
        good(projected['review_status'] == 'proposed' and all(item['review_status'] == 'proposed' for item in projected['dispositions']),
             'Pure archive parser never approves staff decisions without an externally supplied review identity')
        reviewed = execution.manifest_decisions_from_preserved(*args, review_id='EXTERNAL-SYNTHETIC-CURATION')
        good(reviewed['review_status'] == 'reviewed' and reviewed['src_root']['version'] == plan['version'] and
             reviewed['dispositions'][0]['prior_version'] == 'MTH_2026AA',
             'External curation identity preserves parsed decisions and binds their installed predecessor')
        for disposition in ('EXCLUDE', 'REMOVE', 'SPECIAL'):
            alternate = (args[0].replace(b'TEST_2026|KEEP|', b'TEST_2026|' + disposition.encode() + b'|'),) + args[1:]
            projected = execution.manifest_decisions_from_preserved(*alternate)
            good(projected['dispositions'][1]['disposition'] == disposition and projected['review_status'] == 'proposed',
                 'Pure parser preserves the original non-update disposition without approving its native handling: ' + disposition)
        no_explicit_test_mapping = (args[0], b'\n'.join(row for row in args[1].splitlines() if not row.startswith(b'TEST|')) + b'\n') + args[2:]
        projected = execution.manifest_decisions_from_preserved(*no_explicit_test_mapping)
        good(projected['dispositions'][1]['publisher_version'] == 'TEST_2026',
             'Missing explicit map uses only the unchanged identity evidenced in prepared native source/version data')
        unproved = no_explicit_test_mapping[:4] + (args[4].replace(b'TEST_2026', b'TEST_2099'),) + no_explicit_test_mapping[5:]
        rejects(lambda: execution.manifest_decisions_from_preserved(*unproved),
                'No active publisher mapping is guessed when both saved mapping and native identity proof are absent')
        broken = (args[0].replace(b'UPDATE', b'--NEW?--'),) + args[1:]
        rejects(lambda: execution.manifest_decisions_from_preserved(*broken, review_id='EXTERNAL-SYNTHETIC-CURATION'),
                'Externally supplied review identity cannot invent an unresolved archived disposition')
        modified = copy.deepcopy(plan)
        modified['validation']['source_plan']['dispositions'][1]['excluded_termgroups'] = ['XM']
        good(any(item['code'] == 'MTH_PRESERVED_DECISION_MISMATCH' for item in execution.validate_inputs(modified, target)['issues']),
             'A typed source decision change cannot hide behind unchanged preserved original bytes')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'canonical MTH native checks passed')
