#!/usr/bin/env python3
"""Check version-independent MTH manifest semantics with honest tiny fixtures."""
import copy
import hashlib
import json
from pathlib import Path

import release_mth as mth

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'docs/inversion-review/release-manifest-examples/mth.json'


def example():
    return json.loads(EXAMPLE.read_text())


def bind_producer_inputs(manifest):
    artifacts, config = manifest['artifacts'], manifest['configuration']
    inputs = config['inputs']
    plan_sha = mth.artifact_sha256(artifacts[inputs['source_plan']])
    artifacts[inputs['source_data'][0]]['data']['source_plan_sha256'] = plan_sha
    artifacts[inputs['reference_ncimeta']]['data']['source_plan_sha256'] = plan_sha
    artifacts[inputs['source_data'][0]]['data']['policy_sha256'] = mth.artifact_sha256(artifacts[config['policy_ref']])


def direct_example():
    manifest = example()
    config, artifacts = manifest['configuration'], manifest['artifacts']
    previous, current = 'MTH_2026AA', 'MTH_2026AB'
    config['version'] = current
    for value in artifacts.values():
        if value['artifact_type'] != 'identity-state':
            value['version'] = current
        value['provenance']['capture_id'] = 'SYNTHETIC-' + value['artifact_type'] + '-' + value['version']
        for item in value['files']:
            item['uri'] = item['uri'].replace('/skipped/', '/direct/')
            raw = (ROOT / item['uri'].removeprefix('repo:')).read_bytes()
            item.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    plan = artifacts['mth-plan']['data']
    chain = [previous, current]
    plan.update(publisher_previous={'source': 'MTH', 'version': previous}, publisher_release_chain=chain)
    plan['history_selection'] = {'review_status': 'reviewed', 'moved_aui_releases': chain,
                                 'cui_merge_releases': [previous], 'bequeathal_releases': [previous]}
    plan['dispositions'][0]['version'] = current
    plan['vsab_mappings'][0]['version'] = current
    plan['src_root']['version'] = current
    artifacts['mth-prepared']['data'].update(publisher_release=current[4:], history_coverage={
        key: value for key, value in plan['history_selection'].items() if key != 'review_status'})
    bind_producer_inputs(manifest)
    return manifest


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def analyze(manifest):
        return mth.analyze(manifest['configuration'], manifest['artifacts'])

    def invalid(label, mutation, expected_code, rebind=True):
        manifest = example()
        mutation(manifest)
        if rebind:
            bind_producer_inputs(manifest)
        result = analyze(manifest)
        good(any(item['code'] == expected_code and item['severity'] in {'error', 'blocker'} for item in result['issues']), label)
        good(not result['facts']['declared_prepared_inputs_consistent'], label + ': no declared-input consistency claim')

    original = example()
    before = copy.deepcopy(original)
    result = analyze(original)
    good(result['issues'] == [] and result['facts']['declared_prepared_inputs_consistent'],
         'One version-independent analyzer accepts the explicit synthetic skipped-insertion transition')
    direct = direct_example()
    direct_result = analyze(direct)
    good(direct_result['issues'] == [] and direct_result['facts']['version'] == 'MTH_2026AB',
         'Same analyzer accepts a second release with publisher predecessor equal to inserted baseline')
    good(result['facts']['replacement_baseline']['version'] == 'MTH_2026AA' and
         result['facts']['publisher_previous']['version'] == 'MTH_2026AB' and
         result['facts']['publisher_history_artifacts'] == 0,
         'Uninserted publisher predecessor stays distinct without requiring redundant publisher packages')
    good(direct_result['facts']['publisher_previous']['version'] == 'MTH_2026AA',
         'Direct transition retains its independently declared publisher-previous role')
    good(original == before and json.loads(json.dumps(result)) == result and analyze(original) == result,
         'Analysis is deterministic, JSON-compatible and leaves all manifest inputs unchanged')
    good(result['facts']['prepared_RRF_roles'] == 11 and result['facts']['preserved_metadata_roles'] == 8 and
         result['facts']['MetamorphoSys_required'] is False and
         result['facts']['historical_database_reconstruction_required'] is False,
         'Complete preserved prepared inputs do not require MetamorphoSys or historical DB reconstruction')
    good(result['planned_outputs'] == mth.PLANNED_OUTPUTS and
         result['facts']['execution_implemented'] is False and result['facts']['production_eligible'] is False,
         'Planned legacy paths confer neither native execution nor operational eligibility')
    good(result['facts']['legacy_allocation'] == {'SRCbuilder_start': 1000, 'SourceAtomIdBase': 1002,
                                                  'first_ordinary_atom': 1003, 'SourceAtomIdLimit': 1099},
         'Common complete bounds retain the real MTH two-position offset and preincrement behavior')
    for manifest in (original, direct):
        for name, artifact in manifest['artifacts'].items():
            good(artifact['provenance']['evidence_kind'] == 'synthetic-fixture',
                 'Example evidence is explicitly synthetic: ' + manifest['configuration']['version'] + '/' + name)
            for item in artifact['files']:
                good(item['uri'].startswith('repo:tools/fixtures/release-manifests/mth/') and
                     (lambda raw: hashlib.sha256(raw).hexdigest() == item['sha256'] and len(raw) == item['bytes'])(
                         (ROOT / item['uri'].removeprefix('repo:')).read_bytes()),
                     'Actual tiny fixture identity matches role: ' + manifest['configuration']['version'] + '/' + item['role'])
    invalid('Reject publisher mode in prepared-input profile',
            lambda m: m['configuration']['inputs'].update(source_data_stage='publisher'), 'MTH_PREPARED_STAGE_ONLY')
    invalid('Reject MetamorphoSys/runtime overrides in prepared options',
            lambda m: m['configuration']['source_options'].update(metamorphosys_profile='unknown'), 'MTH_PREPARED_OPTIONS')
    invalid('Reject missing prepared RRF role', lambda m: m['artifacts']['mth-prepared']['files'].pop(), 'MTH_INPUT_ROLES')
    invalid('Reject duplicate prepared RRF role',
            lambda m: m['artifacts']['mth-prepared']['files'].append(copy.deepcopy(m['artifacts']['mth-prepared']['files'][0])),
            'MTH_INPUT_ROLES')
    invalid('Reject missing saved precedence/metadata role', lambda m: m['artifacts']['mth-state']['files'].pop(), 'MTH_INPUT_ROLES')
    invalid('Reject prepared producer release mismatch',
            lambda m: m['artifacts']['mth-prepared']['data'].update(publisher_release='2026AB'), 'MTH_PREPARED_RELEASE')
    invalid('Reject subset/policy mismatch', lambda m: m['artifacts']['mth-prepared']['data'].update(subset_profile='different'),
            'MTH_SUBSET_POLICY')
    invalid('Reject source plan logical-reference mismatch',
            lambda m: m['artifacts']['mth-prepared']['data'].update(source_plan_ref='different'), 'MTH_PLAN_BINDING')
    invalid('Missing producer plan digest blocks preparation',
            lambda m: m['artifacts']['mth-prepared']['data'].pop('source_plan_sha256'), 'MTH_PLAN_PRODUCER_BINDING', False)
    invalid('Missing state producer plan digest blocks preparation',
            lambda m: m['artifacts']['mth-state']['data'].pop('source_plan_sha256'), 'MTH_PLAN_PRODUCER_BINDING', False)
    invalid('Missing producer policy digest blocks preparation',
            lambda m: m['artifacts']['mth-prepared']['data'].pop('policy_sha256'), 'MTH_POLICY_PRODUCER_BINDING', False)
    invalid('Logical plan name cannot hide a post-preparation review change',
            lambda m: m['artifacts']['mth-plan']['data'].update(review_id='CHANGED-AFTER-PREPARATION'), 'MTH_PLAN_PRODUCER_BINDING', False)
    invalid('Policy content change invalidates recorded producer binding',
            lambda m: m['artifacts']['mth-policy']['data'].update(notes='changed'), 'MTH_POLICY_PRODUCER_BINDING', False)
    invalid('Whole artifact provenance participates in producer binding',
            lambda m: m['artifacts']['mth-plan']['provenance'].update(capture_id='changed'), 'MTH_PLAN_PRODUCER_BINDING', False)
    invalid('Reject absent identity map', lambda m: m['artifacts']['mth-identity'].update(files=[]), 'MTH_INPUT_ROLES')
    invalid('Reject publisher-previous map substituted for last-inserted identity',
            lambda m: m['artifacts']['mth-identity'].update(version='MTH_2026AB'), 'MTH_ARTIFACT_RELEASE')
    invalid('Reject identity-role ambiguity', lambda m: m['artifacts']['mth-identity']['data'].update(identity_role='publisher-previous-map'),
            'MTH_CUI_BASELINE_ROLE')
    invalid('Reject mismatched installed MTH baseline',
            lambda m: m['artifacts']['mth-state']['data']['installed_sources'][0].update(version='MTH_2026AB'), 'MTH_INSERTED_VERSION')
    invalid('Reject missing inserted predecessor in explicit chain',
            lambda m: m['artifacts']['mth-plan']['data']['publisher_release_chain'].pop(0), 'MTH_RELEASE_CHAIN')
    invalid('Reject generic previous-version substitution',
            lambda m: m['artifacts']['mth-plan']['data']['publisher_previous'].update(version='MTH_2026AA'), 'MTH_PUBLISHER_PREVIOUS')
    invalid('Reject guessed empty history selection across skipped insertion',
            lambda m: m['artifacts']['mth-plan']['data']['history_selection'].update(cui_merge_releases=[]), 'MTH_HISTORY_SELECTION')
    invalid('Reject prepared history missing the inserted predecessor',
            lambda m: m['artifacts']['mth-prepared']['data']['history_coverage']['cui_merge_releases'].remove('MTH_2026AA'),
            'MTH_HISTORY_GAP')
    invalid('Reject duplicate producer history identity',
            lambda m: m['artifacts']['mth-prepared']['data']['history_coverage']['moved_aui_releases'].append('MTH_2026AA'),
            'MTH_HISTORY_COVERAGE')
    invalid('Approval flag cannot approve a proposed source plan',
            lambda m: m['artifacts']['mth-plan']['data'].update(review_status='proposed', approved=True), 'MTH_REVIEW_REQUIRED')
    invalid('Reviewed label cannot silently promote a proposal row',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(proposed=True), 'MTH_REVIEW_REQUIRED')
    invalid('Disposition approval boolean cannot replace explicit review',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(review_status='proposed', approved=True),
            'MTH_REVIEW_REQUIRED')
    invalid('Reject undecided legacy --NEW?-- disposition',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(disposition='--NEW?--'), 'MTH_DISPOSITION_VALUE')
    invalid('Reject object masquerading as a typed disposition',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(disposition={}), 'MTH_DISPOSITION_VALUE')
    invalid('Numeric proposal flag cannot bypass review',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(proposed=1), 'MTH_REVIEW_REQUIRED')
    invalid('Reject duplicate source/version decisions',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'].append(copy.deepcopy(m['artifacts']['mth-plan']['data']['dispositions'][0])),
            'MTH_DISPOSITION_DUPLICATE')
    invalid('Reject conflicting installed KEEP decision',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(prior_version='TEST_2025'), 'MTH_PRIOR_SOURCE_VERSION')
    invalid('Reject new version disguised as KEEP',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(version='TEST_2027'), 'MTH_KEEP_VERSION')
    invalid('Reject missing explicit null prior version for NEW',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][2].pop('prior_version'), 'MTH_PRIOR_SOURCE_VERSION')
    invalid('Reject installed source mislabeled NEW',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(disposition='NEW', prior_version=None),
            'MTH_NEW_ALREADY_INSTALLED')
    invalid('Reject missing publisher/NCImeta mapping', lambda m: m['artifacts']['mth-plan']['data']['vsab_mappings'].pop(),
            'MTH_VSAB_BINDING')
    invalid('Reject ambiguous publisher mapping',
            lambda m: m['artifacts']['mth-plan']['data']['vsab_mappings'].append(copy.deepcopy(m['artifacts']['mth-plan']['data']['vsab_mappings'][0])),
            'MTH_VSAB_MAPPING')
    invalid('Reject unknown SPECIAL handling',
            lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].update(disposition='SPECIAL'), 'MTH_SPECIAL_RULE')
    invalid('Reject undeclared exclusion list', lambda m: m['artifacts']['mth-plan']['data']['dispositions'][1].pop('excluded_termgroups'),
            'MTH_EXCLUDED_TERMGROUPS')
    invalid('Reject root declaration release mismatch',
            lambda m: m['artifacts']['mth-plan']['data']['src_root'].update(version='MTH_2026AA'), 'MTH_SRC_ROOT')
    invalid('No final ID range blocks a shadow inversion', lambda m: m['configuration'].update(source_atom_ids=None),
            'MTH_FINAL_RANGE_REQUIRED')
    invalid('Preliminary estimate cannot become a final allocation',
            lambda m: m['artifacts']['mth-allocation']['data'].update(stage='estimate'), 'MTH_FINAL_ALLOCATION')
    invalid('Final allocation must include two SRC positions',
            lambda m: m['artifacts']['mth-allocation']['data'].update(reserved_SRC_atoms=0), 'MTH_FINAL_ALLOCATION')
    invalid('Changed range invalidates allocation binding', lambda m: m['configuration']['source_atom_ids'].update(end=1200),
            'MTH_ALLOCATION_BINDING')
    invalid('Boolean is not a final MTH identifier', lambda m: m['configuration']['source_atom_ids'].update(start=True),
            'MTH_RANGE_VALUES')
    for disposition in ('EXCLUDE', 'REMOVE', 'SPECIAL'):
        manifest = example()
        row = manifest['artifacts']['mth-plan']['data']['dispositions'][1]
        row['disposition'] = disposition
        if disposition == 'SPECIAL':
            row['special_handling'] = 'synthetic-special-v1'
            manifest['artifacts']['mth-policy']['data']['special_disposition_rules'] = ['synthetic-special-v1']
        bind_producer_inputs(manifest)
        good(analyze(manifest)['issues'] == [], 'Typed reviewed disposition is recognized without invented native work: ' + disposition)
    manifest = example()
    prepared = manifest['artifacts']['mth-prepared']
    prepared['data']['history_coverage']['cui_merge_releases'].remove('MTH_2026AA')
    extra = copy.deepcopy(prepared)
    extra.update(artifact_type='publisher-history', files=[item for item in prepared['files']
                                                         if item['role'] in {'MRAUI.RRF', 'MRCUI.RRF'}])
    extra['data'] = {'history_coverage': {'moved_aui_releases': [], 'cui_merge_releases': ['MTH_2026AA'],
                                        'bequeathal_releases': []}}
    manifest['artifacts']['declared-history'] = extra
    manifest['configuration']['publisher_history'] = ['declared-history']
    good(analyze(manifest)['issues'] == [],
         'An explicitly selected two-file history artifact can close a declared prepared-input history gap')
    extra['files'].pop()
    good(any(item['code'] == 'MTH_INPUT_ROLES' for item in analyze(manifest)['issues']),
         'Additional history cannot claim coverage without the two declared RRF input roles')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH release-manifest preflight checks passed')
