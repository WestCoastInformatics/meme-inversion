#!/usr/bin/env python3
"""Confined source-preflight checks against two honestly synthetic RF2 bundles."""
import copy
import hashlib
import json
from pathlib import Path

import release_snomed as snomed

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'docs/inversion-review/release-manifest-examples/snomed.json'
SECOND = ROOT / 'tools/fixtures/release-manifests/snomed/second-release.json'
FIXTURE_ROOT = ROOT / 'tools/fixtures/release-manifests/snomed/publication-one'


def load(path=EXAMPLE):
    return json.loads(path.read_text())


def report(manifest):
    return snomed.analyze(manifest['configuration'], manifest['artifacts'])


def descriptor(role, path):
    raw = path.read_bytes()
    return {'role': role, 'uri': 'repo:' + path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def rejects(mutate, code, label):
        manifest = load()
        mutate(manifest['configuration'], manifest['artifacts'])
        result = report(manifest)
        good(any(issue['code'] == code for issue in result['issues']), label)

    first, second = load(), load(SECOND)
    before = json.dumps(first, sort_keys=True)
    one, two = report(first), report(second)
    good(not one['issues'] and not two['issues'], 'Two distinct publication/package/predecessor bundles pass the same source preflight')
    good(one['facts']['version'] == 'SNOMEDCT_US_2027_03_01' and two['facts']['version'] == 'SNOMEDCT_US_2028_11_15',
         'New version dates need no source constant edits or historical case registration')
    good(one['facts']['package_name'] != two['facts']['package_name'] and 'T120000Z' not in one['facts']['package_name'],
         'Explicit package naming and timestamps are independent of the captured September convention')
    good(one['facts']['replacement_baseline']['version'] == 'SNOMEDCT_US_2026_03_01',
         'A nonadjacent inserted predecessor is retained without calendar inference')
    good(one['facts']['older_snapshot_effective_dates_accepted'], 'Older Snapshot row effective dates are valid')
    good(one['facts']['execution_enabled'] is False and two['facts']['execution_enabled'] is False,
         'Source preflight never enables execution')
    good(before == json.dumps(first, sort_keys=True), 'Source analysis leaves configuration and artifact dictionaries unchanged')
    good(one['planned_outputs'] == ['etc/sct.cfg', 'src/sources.src', 'src/termgroups.src', 'etc/icd10.inmeta', 'etc/icd10cm.inmeta'],
         'Legacy staging/rendering paths retain the established filesystem layout')
    good(all(artifact['provenance']['evidence_kind'] == 'synthetic-fixture' for example in (first, second)
             for artifact in example['artifacts'].values()), 'Every example artifact is explicitly synthetic')
    for example in (first, second):
        for artifact in example['artifacts'].values():
            for entry in artifact['files']:
                path = ROOT / entry['uri'].removeprefix('repo:')
                raw = path.read_bytes()
                assert len(raw) == entry['bytes'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
        native = example['artifacts']['native-release']
        for entry in native['files']:
            actual = (ROOT / entry['uri'].removeprefix('repo:')).read_text().splitlines()[0].split('\t')
            assert actual == native['data']['headers'][entry['role']]
        meta = example['artifacts']['ncimeta-snapshot']
        for role, key in [('sources-src', 'sources_rows'), ('termgroups-src', 'termgroups_rows')]:
            entry = next(x for x in meta['files'] if x['role'] == role)
            actual = [row.split('|') for row in (ROOT / entry['uri'].removeprefix('repo:')).read_text().splitlines()]
            assert actual == meta['data'][key]
    passed.append('Every checked-in fixture file has real matching hashes/bytes, declared headers and metadata rows')
    for label, mutate, code in [
        ('Full input blocked', lambda c, a: c['source_options'].update(rf2_view='Full'), 'SNOMED_RF2_VIEW'),
        ('Delta input blocked', lambda c, a: c['source_options'].update(rf2_view='Delta'), 'SNOMED_RF2_VIEW'),
        ('Unsupported extra option rejected', lambda c, a: c['source_options'].update(language='ENG'), 'SNOMED_RF2_VIEW'),
        ('Prepared source stage rejected', lambda c, a: c['inputs'].update(source_data_stage='prepared'), 'SNOMED_INPUT_STAGE'),
        ('Inapplicable output stage blocked', lambda c, a: c.update(output_stage='insertion-package'), 'SNOMED_OUTPUT_STAGE'),
        ('Missing predecessor rejected', lambda c, a: c.update(replacement_baseline=None), 'SNOMED_REPLACEMENT'),
        ('Same-version predecessor rejected', lambda c, a: c['replacement_baseline'].update(version=c['version']), 'SNOMED_REPLACEMENT'),
        ('Future predecessor rejected', lambda c, a: c['replacement_baseline'].update(version='SNOMEDCT_US_2030_01_01'), 'SNOMED_REPLACEMENT'),
        ('Cross-source predecessor rejected', lambda c, a: c['replacement_baseline'].update(source='NCI'), 'SNOMED_REPLACEMENT'),
        ('Undeclared history consumer blocked', lambda c, a: c['publisher_history'].append('unexpected'), 'SNOMED_HISTORY_STAGE'),
        ('Undeclared prior identity map blocked', lambda c, a: c['inputs'].update(identity_state='unexpected'), 'SNOMED_IDENTITY_STAGE'),
        ('Multiple native bundles rejected', lambda c, a: c['inputs']['source_data'].append('native-release'), 'SNOMED_NATIVE_BUNDLE'),
        ('Wrong artifact role rejected', lambda c, a: a['native-release'].update(artifact_type='prepared-bundle'), 'SNOMED_ARTIFACT_ROLE'),
        ('Publisher source version mismatch rejected', lambda c, a: a['native-release'].update(version='SNOMEDCT_US_2026_09_01'), 'SNOMED_ARTIFACT_RELEASE'),
        ('Policy bound to another engine rejected', lambda c, a: a['representation-policy']['data'].update(engine_ref='a'*40), 'SNOMED_POLICY_ENGINE'),
        ('Publisher Full package blocked', lambda c, a: a['native-release']['data'].update(rf2_view='Full'), 'SNOMED_PACKAGE_VIEW'),
        ('Publisher package date mismatch rejected', lambda c, a: a['native-release']['data'].update(publisher_release_date='2027-04-01'), 'SNOMED_PUBLISHER_DATE'),
        ('Missing required RF2 member rejected', lambda c, a: a['native-release']['files'].pop(), 'SNOMED_MISSING_RF2_ROLES'),
        ('Duplicate RF2 role rejected', lambda c, a: a['native-release']['files'].append(copy.deepcopy(a['native-release']['files'][0])), 'SNOMED_DUPLICATE_FILE_ROLE'),
        ('Unreviewed native role blocked', lambda c, a: a['native-release']['files'].append({**a['native-release']['files'][0], 'role':'rf2-unknown'}), 'SNOMED_UNSUPPORTED_RF2_ROLES'),
        ('Wrong member filename role rejected', lambda c, a: a['native-release']['files'][0].update(uri=a['native-release']['files'][1]['uri']), 'SNOMED_RF2_MEMBER_IDENTITY'),
        ('Wrong declared RF2 header rejected', lambda c, a: a['native-release']['data']['headers']['rf2-concepts'].append('wrong'), 'SNOMED_RF2_HEADER'),
        ('Future Snapshot effective date rejected', lambda c, a: a['native-release']['data']['effective_time_bounds'].update(maximum='20270302'), 'SNOMED_EFFECTIVE_TIME'),
        ('Unreviewed module dependency rejected', lambda c, a: a['native-release']['data']['module_dependencies'][0].update(target_module_id='999'), 'SNOMED_MODULE_COMPATIBILITY'),
        ('Future module target rejected', lambda c, a: a['native-release']['data']['module_dependencies'][0].update(target_effective_time='20270302'), 'SNOMED_MODULE_COMPATIBILITY'),
        ('Missing ICD inventory rejected', lambda c, a: a['ncimeta-snapshot']['files'].pop(), 'SNOMED_METADATA_DEPENDENCY'),
        ('Mixed capture boundary rejected', lambda c, a: a['ncimeta-snapshot']['data'].update(snapshot_id='different-capture'), 'SNOMED_METADATA_SNAPSHOT'),
        ('Source metadata predecessor mismatch rejected', lambda c, a: a['ncimeta-snapshot']['data']['sources_rows'][0].__setitem__(1,'SNOMEDCT_US_2026_09_01'), 'SNOMED_SOURCE_METADATA'),
        ('Wrong source-family metadata rejected', lambda c, a: a['ncimeta-snapshot']['data']['sources_rows'][0].__setitem__(6,'SNOMEDCT'), 'SNOMED_SOURCE_METADATA'),
        ('Termgroup qualifier mismatch rejected', lambda c, a: a['ncimeta-snapshot']['data']['termgroups_rows'][0].__setitem__(0,'SNOMEDCT_US_2026_09_01/FN'), 'SNOMED_TERMGROUP_METADATA'),
        ('Changed transition plan rejected', lambda c, a: a['source-plan']['data'].update(comparison_baseline={'source':'SNOMEDCT_US','version':'SNOMEDCT_US_2026_09_01'}), 'SNOMED_TRANSITION_PLAN'),
        ('Nonboolean MRDOC selection rejected', lambda c, a: a['source-plan']['data'].update(mrdoc_required='yes'), 'SNOMED_MRDOC_SELECTION'),
        ('Selected MRDOC blocks on missing frozen tables', lambda c, a: a['source-plan']['data'].update(mrdoc_required=True), 'SNOMED_MRDOC_DEPENDENCY'),
        ('Unknown relationship identifier blocked', lambda c, a: a['native-release']['data']['discovery']['relationship_types'].append('999'), 'SNOMED_UNRESOLVED_NATIVE_VALUE'),
        ('Missing observed identifier label rejected', lambda c, a: a['native-release']['data']['discovery']['labels'].clear(), 'SNOMED_DISCOVERY_LABELS'),
        ('Unreviewed changed label blocked', lambda c, a: a['native-release']['data']['discovery']['labels'].update({'116680003':'A changed publisher label'}), 'SNOMED_CHANGED_LABEL'),
        ('Changed established policy blocked', lambda c, a: a['source-plan']['data']['mapping_decisions']['relationship_types'].update({'116680003':{'decision':'exclude','reason':'arbitrary'}}), 'SNOMED_EXISTING_POLICY_CHANGE'),
        ('Unknown mapping category rejected', lambda c, a: a['source-plan']['data']['mapping_decisions'].update(unrecognized={}), 'SNOMED_MAPPING_CATEGORIES'),
        ('Missing mapping representation fields rejected', lambda c, a: a['representation-policy']['data']['mappings']['relationship_types']['116680003'].pop('inverse_rela'), 'SNOMED_MAPPING_FIELDS'),
        ('Description TTY lacks metadata rejected', lambda c, a: a['representation-policy']['data']['mappings']['description_types']['900000000000003001'].update(tty='NEW'), 'SNOMED_TTY_METADATA'),
        ('Pending final ID allocation blocked', lambda c, a: c.update(source_atom_ids=None), 'SNOMED_ID_ALLOCATION_PENDING'),
        ('ID bounds differ from evidence rejected', lambda c, a: c['source_atom_ids'].update(end=1000000100), 'SNOMED_ID_ALLOCATION_BINDING'),
        ('Boolean ID bound rejected', lambda c, a: c['source_atom_ids'].update(start=True), 'SNOMED_ID_BOUNDS'),
    ]:
        rejects(mutate, code, label)
    changed = load()
    changed['artifacts']['native-release']['data']['discovery']['labels']['116680003'] = 'A changed publisher label'
    changed['artifacts']['source-plan']['data']['label_decisions']['116680003'] = {
        'previous_label':'Is a (attribute)', 'current_label':'A changed publisher label', 'reason':'Synthetic reviewed identity-preserving label change'}
    good(not report(changed)['issues'], 'Explicit identifier-bound label decision resolves a declared label change')
    new = load()
    new['artifacts']['native-release']['data']['discovery']['relationship_types'].append('999')
    new['artifacts']['native-release']['data']['discovery']['labels']['999'] = 'Synthetic new relation'
    new['artifacts']['source-plan']['data']['mapping_decisions']['relationship_types']['999'] = {
        'decision':'represent', 'rel':'RO', 'rela':'synthetic_relation', 'inverse_rela':'inverse_synthetic_relation'}
    good(not report(new)['issues'], 'A new identifier requires and accepts an explicit reviewed mapping decision')
    new['artifacts']['source-plan']['data']['mapping_decisions']['relationship_types']['999'] = {'decision':'exclude'}
    good(any(x['code']=='SNOMED_EXCLUSION_REASON' for x in report(new)['issues']), 'Intentional exclusion requires a rationale')
    optional = load()
    optional['artifacts']['native-release']['files'].append(descriptor('rf2-complex-map', FIXTURE_ROOT/'ClinicUS_R7_20270301T230000Z/der2_iissscRefset_ComplexMapSnapshot_US1000124_20270301.txt'))
    optional['artifacts']['native-release']['data']['headers']['rf2-complex-map'] = snomed.OPTIONAL_HEADERS['rf2-complex-map']
    good(not report(optional)['issues'], 'Optional ComplexMap presence is an explicit declared input rather than silently ignored')
    mrdoc = load()
    mrdoc['artifacts']['source-plan']['data']['mrdoc_required'] = True
    for role, name in [('rela-inverse','rela-inverse.txt'),('expanded-form','expanded-form.txt'),('tty-class','tty-class.txt')]:
        mrdoc['artifacts']['ncimeta-snapshot']['files'].append(descriptor(role,FIXTURE_ROOT/'metadata'/name))
    result = report(mrdoc)
    good(not result['issues'] and 'src/MRDOC.RRF' in result['planned_outputs'],
         'Selected MRDOC planning accepts all three frozen metadata tables without live API access')
    saved = load()
    saved['artifacts']['ncimeta-snapshot']['provenance']['evidence_kind'] = 'preserved'
    good(report(saved)['facts']['metadata_inputs_preserved'],
         'Preserved metadata provenance does not require recreating its original database queries')
    return passed


if __name__ == '__main__':
    values = check()
    for name in values:
        print('PASS', name)
    print(len(values), 'SNOMED parameterized release-preflight checks passed')
