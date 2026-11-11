#!/usr/bin/env python3
"""Offline synthetic checks for manifest-only NCIt declaration preflight."""
import copy
import hashlib
import json
from pathlib import Path

import nci_source_plan
import release_nci


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = 'tools/fixtures/release-manifests/nci/'
ENGINE = 'c9efd6cdd32088670ba1b8a10fe28c5249bc68ea'


def source_row(source):
    value = dict.fromkeys(nci_source_plan.SOURCE_FIELDS, '')
    value.update(source_name=source + '_{{release}}', low_source=source + '_{{replacement_release}}',
                 restriction_level='0', normalized_source=source + '_{{release}}',
                 stripped_source=source, version='{{release}}', source_family='NCI',
                 official_name='SYNTHETIC ' + source + ' fixture', language='ENG', character_set='UTF-8')
    return value


def group_row(source):
    return {'termgroup_name': source + '_{{release}}/PT',
            'low_termgroup': source + '_{{replacement_release}}/PT',
            'suppressible_flag': 'N', 'exclude_flag': 'N', 'norm_exclude_flag': 'N', 'tty': 'PT'}


def fixture(version='NCI_2026_10D', prior='NCI_2026_08E', additions=True):
    """Entirely synthetic declarations; the tiny native files are NOT real exports."""
    baseline = {'source': 'NCI', 'version': prior}
    provenance = {'producer': 'check_release_nci.py synthetic fixture', 'producer_version': ENGINE,
                  'capture_id': 'synthetic-' + version, 'evidence_kind': 'synthetic-fixture'}
    def artifact(kind, data, files=None, selected_version=None):
        return {'schema_version': 1, 'artifact_type': kind, 'source': 'NCI',
                'version': selected_version or version, 'provenance': copy.deepcopy(provenance),
                'files': files or [], 'data': data}
    config = {'schema_version': 2, 'source': 'NCI', 'version': version, 'engine_ref': ENGINE,
              'policy_ref': 'representation-policy', 'environment_profile': 'dev-environment',
              'replacement_baseline': baseline, 'comparison_baseline': None, 'publisher_history': [],
              'inputs': {'source_data': ['publisher'], 'source_data_stage': 'publisher',
                         'reference_ncimeta': None, 'identity_state': 'saved-root', 'source_plan': 'release-plan'},
              'source_atom_ids': {'start': 10000, 'end': 19999, 'bound_kind': 'dev-reservation', 'provenance_ref': 'allocation'},
              'validation_profile': 'validation', 'output_stage': 'inversion-src', 'source_options': {}}
    model = {'schema_version': 1, 'source': 'NCI', 'provenance': {'origin': 'SYNTHETIC minimal catalog; never installed state'},
             'sources': [source_row('NCI')], 'termgroups': [group_row('NCI')],
             'publisher_termgroups': [['NCI', 'PT']], 'publisher_properties': [], 'publisher_labels': {}, 'relationship_roles': []}
    properties = {'VSAB': version, 'RSAB': 'NCI', 'CFG2RSAB': "'NCI'",
                  'HC.RootNodeCode': 'SYNTHETIC_ROOT', 'HC.RootNodeName': 'Synthetic saved hierarchy root'}
    plan = {'schema_version': 1, 'source': 'NCI', 'version': version, 'replacement_baseline': copy.deepcopy(baseline),
            'comparison_baseline': None, 'publisher_history': [], 'new_subsources': [], 'new_termgroups': [],
            'property_updates': {}, 'historical_exceptions': []}
    if additions:
        source = source_row('TESTPUB');source['low_source'] = 'NCI_{{release}}'
        group = group_row('TESTPUB');group['low_termgroup'] = 'NCI_{{release}}/PT'
        plan['new_subsources'] = [{'metadata': source, 'after_source': 'NCI', 'publisher_names': ['Synthetic publisher'],
                                  'root': {'preferred_term': 'SYNTHETIC fixture publisher root', 'short_name': 'TESTPUB'}}]
        plan['new_termgroups'] = [{'metadata': group, 'after_termgroup': 'NCI_{{release}}/PT', 'input_ttys': ['PT']}]
    files = []
    for role in release_nci.ROLES:
        name = role + '-20261001.txt'
        raw = (ROOT / FIXTURES / name).read_bytes()
        files.append({'role': role, 'uri': 'repo:' + FIXTURES + name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    artifacts = {
        'publisher': artifact('publisher-bundle', {'profile': release_nci.PROFILE}, files),
        'release-plan': artifact('source-plan', plan),
        'representation-policy': artifact('policy', {'profile': nci_source_plan.PROFILE, 'metadata_model': model, 'properties': properties}),
        'saved-root': artifact('identity-state', {'profile': 'saved-hierarchy-root-v1', 'root_atom_id': 321,
                                                'root_code': 'SYNTHETIC_ROOT', 'root_name': 'Synthetic saved hierarchy root',
                                                'replacement_baseline': copy.deepcopy(baseline)}, selected_version=prior),
        'allocation': artifact('id-allocation', {'start': 10000, 'end': 19999, 'bound_kind': 'dev-reservation'}),
        'dev-environment': artifact('environment-profile', {'profile_id': 'meme-dev-v1'}),
        'validation': artifact('validation-profile', {'profile_id': 'nci-release-core-v1'})}
    return {'schema_version': 1, 'artifact_type': 'ncimeta-release-manifest', 'profile': release_nci.PROFILE,
            'purpose': 'shadow', 'configuration': config, 'artifacts': artifacts}


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def result(manifest):
        return release_nci.analyze(manifest['configuration'], manifest['artifacts'])
    def codes(report, severity=None):
        return {row['code'] for row in report['issues'] if severity is None or row['severity'] == severity}
    def negative(label, mutate, expected, base=None):
        manifest = copy.deepcopy(base if base is not None else fixture())
        mutate(manifest)
        good(expected in codes(result(manifest)), label)

    manifest = fixture();before = copy.deepcopy(manifest)
    report = result(manifest)
    good(not codes(report, 'error'), 'October/August synthetic declarations validate without a case-catalog entry')
    good(manifest == before, 'All configuration, plan, policy and artifact input values remain unchanged')
    good(result(manifest) == report, 'Repeated frozen declarations produce identical reports')
    good(report['facts']['replacement_baseline']['version'] == 'NCI_2026_08E', 'An explicit August predecessor requires no September input')
    second = fixture('NCI_2027_02B', 'NCI_2026_12C', False)
    later = result(second)
    good(not codes(later, 'error') and later['facts']['optional_decisions'] == {'new_subsources': 0, 'new_termgroups': 0},
         'The same analyzer accepts February/December with skipped January and explicit empty addition arrays')
    good(report['facts']['new_subsources'] == ['TESTPUB'] and report['facts']['new_termgroups'] == 1,
         'Optional subsource and termgroup decisions reuse the existing typed source-plan generator')
    good(report['planned_outputs'] == later['planned_outputs'] == list(release_nci.PLANNED_OUTPUTS), 'Output path planning is independent of release versions')
    good(not report['facts']['production_eligible'] and not report['facts']['execution_authorized'], 'A structurally valid declaration cannot authorize execution or production')
    good(set(release_nci.CAPTURE_BLOCKERS) <= codes(report, 'blocker'), 'All six unverified deployed-state capture assurances remain blockers')
    good('NCI_INSTALLED_STATE_REQUIRED' in codes(report) and not report['facts']['representation_catalog_proves_installation'], 'Catalog membership never supplies missing installed root or ranking evidence')
    good('NCI_PUBLISHER_DISCOVERY_REQUIRED' in codes(report), 'A five-role declaration is not actual publisher-content discovery')
    good('NCI_SYNTHETIC_EVIDENCE' in codes(report), 'Synthetic provenance stays explicit and cannot establish operational evidence')

    negative('A same-release predecessor is rejected', lambda m: m['configuration'].update(replacement_baseline={'source': 'NCI', 'version': m['configuration']['version']}), 'NCI_TRANSITION_INVALID')
    negative('A future predecessor is rejected', lambda m: m['configuration'].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2027_01A'}), 'NCI_TRANSITION_INVALID')
    negative('A missing explicit predecessor is rejected', lambda m: m['configuration'].update(replacement_baseline=None), 'NCI_TRANSITION_INVALID')
    negative('A plan cannot silently select a different predecessor', lambda m: m['artifacts']['release-plan']['data'].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2026_09A'}), 'NCI_SOURCE_PLAN_INVALID')
    negative('Prepared NCIt inputs cannot masquerade as the publisher profile', lambda m: m['configuration']['inputs'].update(source_data_stage='prepared'), 'NCI_TRANSITION_INVALID')
    negative('A comparison baseline cannot introduce an unimplemented preparation stage', lambda m: m['configuration'].update(comparison_baseline={'source': 'NCI', 'version': 'NCI_2026_08E'}), 'NCI_TRANSITION_INVALID')
    negative('Undeclared source-specific options are rejected', lambda m: m['configuration'].update(source_options={'guess_previous_month': True}), 'NCI_TRANSITION_INVALID')
    negative('A publisher bundle must identify all five roles', lambda m: m['artifacts']['publisher']['files'].pop(), 'NCI_PUBLISHER_BUNDLE_INVALID')
    negative('Duplicate native roles cannot hide an omitted role', lambda m: m['artifacts']['publisher']['files'][1].update(role='annotationDeclaration'), 'NCI_PUBLISHER_BUNDLE_INVALID')
    negative('A role must agree with its native filename', lambda m: m['artifacts']['publisher']['files'][0].update(uri='repo:tools/fixtures/release-manifests/nci/wrong.txt'), 'NCI_PUBLISHER_BUNDLE_INVALID')
    negative('An unknown publisher data flag cannot broaden the profile', lambda m: m['artifacts']['publisher']['data'].update(discovery_passed=True), 'NCI_PUBLISHER_BUNDLE_INVALID')
    negative('A publisher artifact cannot silently belong to another release', lambda m: m['artifacts']['publisher'].update(version='NCI_2026_09A'), 'NCI_PUBLISHER_BUNDLE_INVALID')
    negative('A source plan must use the correct typed artifact', lambda m: m['artifacts']['release-plan'].update(artifact_type='ncimeta-state'), 'NCI_SOURCE_PLAN_INVALID')
    negative('Optional arrays must be explicit rather than omitted', lambda m: m['artifacts']['release-plan']['data'].pop('new_termgroups'), 'NCI_SOURCE_PLAN_INVALID')
    negative('A new root requires its termgroup decision', lambda m: m['artifacts']['release-plan']['data'].update(new_termgroups=[]), 'NCI_SOURCE_PLAN_SEMANTICS_INVALID')
    negative('Duplicate new-root decisions are rejected', lambda m: m['artifacts']['release-plan']['data']['new_subsources'].append(copy.deepcopy(m['artifacts']['release-plan']['data']['new_subsources'][0])), 'NCI_SOURCE_PLAN_SEMANTICS_INVALID')
    negative('A new source cannot guess an absent ranking anchor', lambda m: m['artifacts']['release-plan']['data']['new_subsources'][0].update(after_source='UNKNOWN'), 'NCI_SOURCE_PLAN_SEMANTICS_INVALID')
    negative('A saved hierarchy root must match the selected predecessor', lambda m: m['artifacts']['saved-root']['data'].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2026_09A'}), 'NCI_IDENTITY_STATE_INVALID')
    negative('A boolean is not a saved hierarchy SAID', lambda m: m['artifacts']['saved-root']['data'].update(root_atom_id=True), 'NCI_IDENTITY_STATE_INVALID')
    negative('A hierarchy anchor cannot be substituted for another declared root', lambda m: m['artifacts']['representation-policy']['data']['properties'].update({'HC.RootNodeCode': 'OTHER'}), 'NCI_IDENTITY_STATE_INVALID')
    negative('Legacy property values cannot inject another configuration line', lambda m: m['artifacts']['representation-policy']['data']['properties'].update({'VSAB': m['configuration']['version'] + '\nSAID=1'}), 'NCI_POLICY_INVALID')
    negative('A representation catalog cannot add an installation assurance flag', lambda m: m['artifacts']['representation-policy']['data']['metadata_model'].update(installed=True), 'NCI_POLICY_INVALID')
    negative('Missing allocation remains a blocker without inventing a range', lambda m: m['configuration'].update(source_atom_ids=None), 'NCI_ALLOCATION_REQUIRED')
    negative('Missing allocation defers full metadata generation validation explicitly', lambda m: m['configuration'].update(source_atom_ids=None), 'NCI_SOURCE_PLAN_SEMANTICS_NOT_EVALUATED')
    negative('A boolean is not an allocation bound', lambda m: m['configuration']['source_atom_ids'].update(start=True), 'NCI_ALLOCATION_INVALID')
    negative('Allocation evidence must match configured inclusive bounds', lambda m: m['artifacts']['allocation']['data'].update(end=20000), 'NCI_ALLOCATION_INVALID')
    negative('Allocation evidence rejects float bounds even when numerically equal', lambda m: m['artifacts']['allocation']['data'].update(start=10000.0), 'NCI_ALLOCATION_INVALID')
    negative('An allocation must fit even the declared SRC root records', lambda m: (m['configuration']['source_atom_ids'].update(end=10001), m['artifacts']['allocation']['data'].update(end=10001)), 'NCI_SOURCE_PLAN_SEMANTICS_INVALID')
    negative('Historical emitted bounds are not a new reservation', lambda m: (m['configuration']['source_atom_ids'].update(bound_kind='historical-emitted-range'), m['artifacts']['allocation']['data'].update(bound_kind='historical-emitted-range')), 'NCI_HISTORICAL_ALLOCATION_ONLY')

    historical = fixture()
    historic_data = historical['artifacts']['release-plan']['data']
    historic_data['historical_exceptions'] = [{'kind': 'unmapped-publisher-source', 'identifier': 'CTCAE 6.0',
        'reason': 'SYNTHETIC retained finding, never an approved correction', 'version': historical['configuration']['version'],
        'native_sha256': {Path(item['uri']).name: item['sha256'] for item in historical['artifacts']['publisher']['files']}}]
    good('NCI_HISTORICAL_FINDING_REQUIRES_REVIEW' in codes(result(historical)), 'A retained historical finding blocks readiness even with native hashes bound')
    ranking_finding = copy.deepcopy(historic_data['historical_exceptions'][0])
    ranking_finding.update(kind='unverified-termgroup-ranking', identifier='CELLOSAURUS_2026_10D/SY')
    historic_data['historical_exceptions'].append(ranking_finding)
    good(sum(row['code'] == 'NCI_HISTORICAL_FINDING_REQUIRES_REVIEW' for row in result(historical)['issues']) == 2,
         'CTCAE and CELLOSAURUS historical findings are independently retained without semantic corrections')
    negative('Historical findings cannot borrow another release native manifest', lambda m: m['artifacts']['release-plan']['data']['historical_exceptions'][0]['native_sha256'].update({'hierarchy-20261001.txt': '0' * 64}), 'NCI_SOURCE_PLAN_INVALID', historical)

    # Existing primary synthetic v2 fixture supplies declaration shape only.
    # This adapter does NOT read its raw bytes or claim a verified backend run.
    import check_nci_backend_preflight
    state = check_nci_backend_preflight.fixture()[4]
    supplied = fixture()
    supplied['configuration']['inputs']['reference_ncimeta'] = 'state'
    supplied['artifacts']['state'] = copy.deepcopy(supplied['artifacts']['publisher'])
    supplied['artifacts']['state'].update(artifact_type='ncimeta-state', files=[], data=copy.deepcopy(state))
    declared = result(supplied)
    good(not codes(declared, 'error'), 'An existing synthetic v2 declaration can be supplied without an invented snapshot format')
    good('NCI_BACKEND_PREFLIGHT_REQUIRED' in codes(declared) and set(release_nci.CAPTURE_BLOCKERS) <= codes(declared), 'Supplying every v2 declaration does not bypass raw/export/deployment assurances')
    good('NCI_INSTALLED_STATE_REQUIRED' not in codes(declared), 'Supplied state and absent state remain distinguishable')
    negative('A stale state identity is rejected independently of wall-clock age', lambda m: m['artifacts']['state']['data']['scope'].update(version='NCI_2026_09A'), 'NCI_INSTALLED_STATE_INVALID', supplied)
    negative('An unknown state assurance flag cannot approve itself', lambda m: m['artifacts']['state']['data'].update(reviewed=True), 'NCI_INSTALLED_STATE_INVALID', supplied)
    negative('SAIDs stay bound to the explicit project alternate-ID key', lambda m: m['artifacts']['state']['data']['project'].update(source_atom_id_key='OTHER-SRC'), 'NCI_INSTALLED_STATE_INVALID', supplied)
    negative('Backend atom IDs cannot accept booleans', lambda m: m['artifacts']['state']['data']['source_roots'][0].update(backend_atom_id=True), 'NCI_INSTALLED_STATE_INVALID', supplied)
    negative('A catalogued source can still lack an installed root', lambda m: m['artifacts']['state']['data'].update(source_roots=[r for r in m['artifacts']['state']['data']['source_roots'] if r['source'] != 'NCI']), 'NCI_ESTABLISHED_ROOT_MISSING', supplied)
    def new_root_already(m):
        row = copy.deepcopy(m['artifacts']['state']['data']['source_roots'][0])
        row.update(source='TESTPUB', source_atom_id=9876543, backend_atom_id=9876544, code_id='V-TESTPUB')
        m['artifacts']['state']['data']['source_roots'].append(row)
    negative('An explicit new-root decision conflicts with a declared installed root', new_root_already, 'NCI_NEW_ROOT_ALREADY_PRESENT', supplied)
    negative('Explicit aliases cannot be replaced by parsing NCIt suffixes', lambda m: m['artifacts']['state']['data'].update(version_aliases=[r for r in m['artifacts']['state']['data']['version_aliases'] if r['versioned_source'] != m['configuration']['replacement_baseline']['version']]), 'NCI_REPLACEMENT_STATE_MISMATCH', supplied)
    negative('Declared established source family cannot be inferred from its abbreviation', lambda m: m['artifacts']['state']['data'].update(families=[r for r in m['artifacts']['state']['data']['families'] if r['source'] != 'NCI']), 'NCI_ESTABLISHED_FAMILY_MISMATCH', supplied)
    negative('SRC/RPT selection cannot substitute another root code', lambda m: m['artifacts']['state']['data']['source_roots'][0].update(code_id='R-NCI'), 'NCI_INSTALLED_STATE_INVALID', supplied)
    explicit_alias = copy.deepcopy(supplied)
    for role in ('version_aliases', 'replacement_sources', 'source_versions'):
        for row in explicit_alias['artifacts']['state']['data'][role]:
            if row['source'] == 'NCI':
                row['backend_version'] = 'explicit-backend-august'
    good('NCI_REPLACEMENT_STATE_MISMATCH' not in codes(result(explicit_alias)), 'An explicit backend version alias can differ from the common NCIt release suffix')
    def missing_project_pair(m):
        entries = m['artifacts']['state']['data']['precedence_lists']['project']['entries']
        entries[:] = [r for r in entries if r != {'source': 'NCI', 'tty': 'PT'}]
    negative('Default ranking membership cannot replace a missing project anchor', missing_project_pair, 'NCI_NEW_RANK_ANCHOR_MISSING', supplied)
    negative('An absent established project rank needs a reconciliation decision', missing_project_pair, 'NCI_ESTABLISHED_RANK_MISSING', supplied)
    good(supplied['artifacts']['state']['data'] == state, 'State comparisons do not mutate supplied v2 evidence')
    return checks


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'scope': 'synthetic declaration preflight only'}))
