#!/usr/bin/env python3
"""Source semantics for manifest-driven MTH prepared-input preflight only."""
import hashlib
import json
import re

PROFILE = 'mth-prepared-inputs-v1'
RRF_ROLES = {'MRCONSO.RRF', 'MRREL.RRF', 'MRSAT.RRF', 'MRSTY.RRF',
             'MRDEF.RRF', 'MRCUI.RRF', 'MRCXT.RRF', 'MRSAB.RRF',
             'MRRANK.RRF', 'MRAUI.RRF', 'MRDOC.RRF'}
METADATA_ROLES = {'src/sources.src', 'src/termgroups.src', 'src/vsab.updates',
                  'src/sabs_updated_umls', 'src/rsabs-updated.umls',
                  'src/vcodes_updated', 'ncimid.sources', 'ncimid.termgroups'}
DISPOSITIONS = {'KEEP', 'UPDATE', 'NEW', 'EXCLUDE', 'REMOVE', 'SPECIAL'}
ACTIVE = {'KEEP', 'UPDATE', 'NEW'}
HISTORY_KINDS = ('moved_aui_releases', 'cui_merge_releases', 'bequeathal_releases')
PLANNED_OUTPUTS = ['range3.spec', 'src/inv1.spec', 'src/inv2.spec', 'src/inv3.spec',
                   'ncisources.spec', 'sab.vsab.map', 'src_data']
TOKEN = re.compile(r'[A-Za-z0-9_.-]+')
RELEASE = re.compile(r'MTH_([0-9]{4}(?:AA|AB))')


def artifact_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def rest_selected_sources(dispositions):
    """The retained invert1.s REST choice, separate from background decisions.

    SNOMED CT US UPDATE is inverted separately. Otherwise SCTSPA is excluded.
    The SRC pseudo-source never reaches vsab.updates. No other active source
    can be omitted merely by removing it from a prepared selected_sources list.
    """
    active = [row for row in dispositions if isinstance(row, dict) and row.get('disposition') in ACTIVE]
    excluded = 'SNOMEDCT_US' if any(row.get('source') == 'SNOMEDCT_US' and
                                   row.get('disposition') == 'UPDATE' for row in active) else 'SCTSPA'
    return {row['source'] for row in active if row.get('source') != excluded and row.get('version') != 'SRC'}, excluded


def analyze(configuration, artifacts):
    """Check declared prepared inputs; never acquire, render, execute or approve.

    Common schema, URI, hash and admission checks belong to the caller. Logical
    artifact references here are frozen by that caller, including nested data.
    """
    issues = []
    artifact_paths = {}
    facts = {'profile': PROFILE, 'execution_implemented': False,
             'production_eligible': False, 'publisher_preparation_executed': False,
             'historical_database_reconstruction_required': False,
             'retained_background_choices': []}

    def issue(code, message, path, severity='error'):
        for role, logical_path in artifact_paths.items():
            prefix = '/artifacts/' + role
            if path == prefix or path.startswith(prefix + '/'):
                path = logical_path + path[len(prefix):]
                break
        issues.append({'severity': severity, 'code': code, 'message': message, 'path': path})

    def token(value):
        return isinstance(value, str) and TOKEN.fullmatch(value) is not None

    def release(value):
        return isinstance(value, str) and RELEASE.fullmatch(value) is not None

    def get(reference, kind, path, version=None):
        value = artifacts.get(reference) if isinstance(reference, str) else None
        if not isinstance(value, dict) or value.get('artifact_type') != kind:
            issue('MTH_ARTIFACT_ROLE', 'A ' + kind + ' artifact is required.', path)
            return {}, {}
        if value.get('source') != 'MTH' or (version is not None and value.get('version') != version):
            issue('MTH_ARTIFACT_RELEASE', 'Artifact source/release differs from its selected role.', path)
        data = value.get('data')
        if not isinstance(data, dict):
            issue('MTH_ARTIFACT_DATA', 'Typed artifact data is required.', path + '/data')
            data = {}
        return value, data

    def roles(value, expected, path):
        files = value.get('files', [])
        if not isinstance(files, list):
            files = []
        names = [item.get('role') for item in files if isinstance(item, dict)]
        if len(names) != len(expected) or not all(isinstance(x, str) for x in names) or set(names) != expected:
            issue('MTH_INPUT_ROLES', 'Exactly these distinct input roles are required: ' +
                  ', '.join(sorted(expected)), path + '/files')
        return len(names)

    def reviewed(value, path):
        if (value.get('review_status') != 'reviewed' or value.get('proposed', False) is not False or
                value.get('proposal', False) is not False):
            issue('MTH_REVIEW_REQUIRED', 'An explicit reviewed decision is required; proposal flags do not approve it.',
                  path, 'blocker')

    config = configuration if isinstance(configuration, dict) else {}
    inputs = config.get('inputs') if isinstance(config.get('inputs'), dict) else {}
    version = config.get('version')
    baseline = config.get('replacement_baseline')
    if config.get('source') != 'MTH' or not release(version):
        issue('MTH_RELEASE_IDENTITY', 'A canonical MTH_YYYYAA or MTH_YYYYAB identity is required.', '/configuration/version')
    if (not isinstance(baseline, dict) or baseline.get('source') != 'MTH' or
            not release(baseline.get('version')) or not release(version) or baseline['version'] >= version):
        issue('MTH_REPLACEMENT_BASELINE', 'Select the earlier last-inserted MTH baseline explicitly.',
              '/configuration/replacement_baseline')
        baseline = {}
    if inputs.get('source_data_stage') != 'prepared':
        issue('MTH_PREPARED_STAGE_ONLY', 'This profile consumes preserved prepared inputs; publisher/MetamorphoSys production is separate.',
              '/configuration/inputs/source_data_stage')
    if config.get('source_options') != {}:
        issue('MTH_PREPARED_OPTIONS', 'Prepared-input preflight has no publisher or runtime override options.',
              '/configuration/source_options')
    if config.get('output_stage') != 'inversion-src':
        issue('MTH_OUTPUT_STAGE', 'Only final inversion-src preparation is described.', '/configuration/output_stage')
    selected = inputs.get('source_data', [])
    if not isinstance(selected, list) or len(selected) != 1:
        issue('MTH_PREPARED_BUNDLE', 'Select one complete prepared MTH bundle.', '/configuration/inputs/source_data')
        selected = []
    references_by_role = {'prepared-bundle': selected[0] if selected else None,
                          'ncimeta-state': inputs.get('reference_ncimeta'),
                          'identity-state': inputs.get('identity_state'),
                          'source-plan': inputs.get('source_plan'), 'policy': config.get('policy_ref')}
    if isinstance(config.get('source_atom_ids'), dict):
        references_by_role['id-allocation'] = config['source_atom_ids'].get('provenance_ref')
    artifact_paths.update({role: '/artifacts/' + reference.replace('~', '~0').replace('/', '~1')
                           for role, reference in references_by_role.items() if isinstance(reference, str)})
    bundle, prepared = get(selected[0] if selected else None, 'prepared-bundle',
                           '/configuration/inputs/source_data', version)
    state_artifact, state = get(inputs.get('reference_ncimeta'), 'ncimeta-state',
                                '/configuration/inputs/reference_ncimeta', version)
    identity_artifact, identity = get(inputs.get('identity_state'), 'identity-state',
                                      '/configuration/inputs/identity_state', baseline.get('version'))
    _, plan = get(inputs.get('source_plan'), 'source-plan', '/configuration/inputs/source_plan', version)
    _, policy = get(config.get('policy_ref'), 'policy', '/configuration/policy_ref')
    facts['prepared_RRF_roles'] = roles(bundle, RRF_ROLES, '/artifacts/prepared-bundle')
    facts['preserved_metadata_roles'] = roles(state_artifact, METADATA_ROLES, '/artifacts/ncimeta-state')
    roles(identity_artifact, {'cui_said_map'}, '/artifacts/identity-state')
    reviewed(plan, '/artifacts/source-plan/data')
    if not isinstance(plan.get('review_id'), str) or not plan.get('review_id', '').strip():
        issue('MTH_REVIEW_ID', 'Bind the reviewed source plan to an identified review.', '/artifacts/source-plan/data/review_id', 'blocker')
    for role, data in [('source-plan', plan), ('ncimeta-state', state), ('identity-state', identity)]:
        if data.get('replacement_baseline') != baseline:
            issue('MTH_BASELINE_BINDING', 'The selected replacement baseline and saved state must agree.',
                  '/artifacts/' + role + '/data/replacement_baseline')
    for role, data in [('prepared-bundle', prepared), ('ncimeta-state', state)]:
        if data.get('source_plan_ref') != inputs.get('source_plan'):
            issue('MTH_PLAN_BINDING', 'Prepared inputs and metadata must identify the same reviewed source plan.',
                  '/artifacts/' + role + '/data/source_plan_ref')
        producer_hash = data.get('source_plan_sha256')
        selected_plan = artifacts.get(inputs.get('source_plan')) if isinstance(inputs.get('source_plan'), str) else None
        if not producer_hash:
            issue('MTH_PLAN_PRODUCER_BINDING', 'The producer must record the complete source-plan artifact hash used during preparation.',
                  '/artifacts/' + role + '/data/source_plan_sha256', 'blocker')
        elif not isinstance(selected_plan, dict) or producer_hash != artifact_sha256(selected_plan):
            issue('MTH_PLAN_PRODUCER_BINDING', 'Prepared producer source-plan hash differs from the selected complete artifact.',
                  '/artifacts/' + role + '/data/source_plan_sha256')
    if prepared.get('publisher_release') != (version[4:] if release(version) else None):
        issue('MTH_PREPARED_RELEASE', 'Prepared producer release differs from the selected MTH release.',
              '/artifacts/prepared-bundle/data/publisher_release')
    if prepared.get('policy_ref') != config.get('policy_ref'):
        issue('MTH_POLICY_BINDING', 'The prepared bundle must identify its reviewed representation policy.',
              '/artifacts/prepared-bundle/data/policy_ref')
    selected_policy = artifacts.get(config.get('policy_ref')) if isinstance(config.get('policy_ref'), str) else None
    if not prepared.get('policy_sha256'):
        issue('MTH_POLICY_PRODUCER_BINDING', 'The producer must record the complete policy artifact hash used during preparation.',
              '/artifacts/prepared-bundle/data/policy_sha256', 'blocker')
    elif not isinstance(selected_policy, dict) or prepared['policy_sha256'] != artifact_sha256(selected_policy):
        issue('MTH_POLICY_PRODUCER_BINDING', 'Prepared producer policy hash differs from the selected complete artifact.',
              '/artifacts/prepared-bundle/data/policy_sha256')
    if not token(policy.get('subset_profile')) or prepared.get('subset_profile') != policy.get('subset_profile'):
        issue('MTH_SUBSET_POLICY', 'Prepared subset identity must agree with the reviewed policy.',
              '/artifacts/prepared-bundle/data/subset_profile')
    if identity.get('identity_role') != 'last-inserted-cui-map':
        issue('MTH_CUI_BASELINE_ROLE', 'Identity state must explicitly be the last-inserted CUI map, not publisher-previous state.',
              '/artifacts/identity-state/data/identity_role')

    publisher_previous = plan.get('publisher_previous')
    chain = plan.get('publisher_release_chain')
    chain_valid = (isinstance(chain, list) and len(chain) >= 2 and all(release(x) for x in chain) and
                   len(set(chain)) == len(chain) and chain == sorted(chain) and
                   chain[0] == baseline.get('version') and chain[-1] == version)
    if not chain_valid:
        issue('MTH_RELEASE_CHAIN', 'Declare the ordered publisher release chain from last inserted baseline through current release.',
              '/artifacts/source-plan/data/publisher_release_chain')
        chain = []
    if (not isinstance(publisher_previous, dict) or publisher_previous.get('source') != 'MTH' or
            not chain or publisher_previous.get('version') != chain[-2]):
        issue('MTH_PUBLISHER_PREVIOUS', 'Publisher-previous selection must be explicit and agree with the declared chain.',
              '/artifacts/source-plan/data/publisher_previous')
        publisher_previous = {}
    selection = plan.get('history_selection')
    selection = selection if isinstance(selection, dict) else {}
    reviewed(selection, '/artifacts/source-plan/data/history_selection')
    coverage = {kind: set() for kind in HISTORY_KINDS}
    history_inputs = [(prepared, '/artifacts/prepared-bundle/data/history_coverage')]
    references = config.get('publisher_history', [])
    if not isinstance(references, list):
        references = []
    for index, reference in enumerate(references):
        extra_artifact, extra = get(reference, 'publisher-history', '/configuration/publisher_history/' + str(index))
        roles(extra_artifact, {'MRAUI.RRF', 'MRCUI.RRF'}, '/artifacts/' + str(reference))
        if not release(extra_artifact.get('version')) or extra_artifact.get('version') not in chain:
            issue('MTH_HISTORY_RELEASE', 'Additional history must identify a release in the explicitly reviewed chain.',
                  '/artifacts/' + str(reference) + '/version')
        history_inputs.append((extra, '/artifacts/' + str(reference) + '/data/history_coverage'))
    for data, path in history_inputs:
        supplied = data.get('history_coverage')
        supplied = supplied if isinstance(supplied, dict) else {}
        for kind in HISTORY_KINDS:
            values = supplied.get(kind)
            if not isinstance(values, list) or not all(release(x) for x in values) or len(set(values)) != len(values):
                issue('MTH_HISTORY_COVERAGE', 'Producer must declare distinct release identities for each history role.', path + '/' + kind)
            else:
                coverage[kind].update(values)
    for kind in HISTORY_KINDS:
        requested = selection.get(kind)
        allowed = chain if kind == 'moved_aui_releases' else chain[:-1]
        if (not isinstance(requested, list) or not all(release(x) for x in requested) or
                len(set(requested)) != len(requested) or not allowed or set(requested) != set(allowed)):
            issue('MTH_HISTORY_SELECTION', 'Reviewed history selection must cover the explicitly declared transition chain for this role.',
                  '/artifacts/source-plan/data/history_selection/' + kind)
        elif not set(requested) <= coverage[kind]:
            issue('MTH_HISTORY_GAP', 'Declared prepared/history inputs do not cover the reviewed transition selection.',
                  '/artifacts/source-plan/data/history_selection/' + kind)

    installed = {}
    installed_rows = state.get('installed_sources', [])
    if not isinstance(installed_rows, list):
        installed_rows = []
    for index, row in enumerate(installed_rows):
        if (not isinstance(row, dict) or not token(row.get('source')) or not token(row.get('version')) or
                row['source'] in installed):
            issue('MTH_INSTALLED_SOURCES', 'Saved current_sources must contain distinct typed source/version identities.',
                  '/artifacts/ncimeta-state/data/installed_sources/' + str(index))
        else:
            installed[row['source']] = row['version']
    if installed.get('MTH') != baseline.get('version'):
        issue('MTH_INSERTED_VERSION', 'Saved installed MTH state must match the selected replacement baseline.',
              '/artifacts/ncimeta-state/data/installed_sources')
    decisions, seen, active = plan.get('dispositions', []), set(), set()
    if not isinstance(decisions, list) or not decisions:
        issue('MTH_DISPOSITIONS', 'Provide typed reviewed source/version dispositions.', '/artifacts/source-plan/data/dispositions')
        decisions = []
    # A complete background staff plan also contains choices for sources that
    # the retained REST preparation deliberately does not select. A same-version
    # UPDATE is admissible only for that canonical excluded background source,
    # with a complete selected set and original data hashes that the physical
    # validator independently reparses before any conversion.
    valid_decisions = [row for row in decisions if isinstance(row, dict) and
                       token(row.get('source')) and isinstance(row.get('disposition'), str)]
    expected_selected, excluded_background = rest_selected_sources(valid_decisions)
    selected_sources = prepared.get('selected_sources')
    selection_consistent = (isinstance(selected_sources, list) and all(token(x) for x in selected_sources) and
                            len(set(selected_sources)) == len(selected_sources) and set(selected_sources) == expected_selected)
    if selected_sources is not None and not selection_consistent:
        issue('MTH_PREPARED_SELECTION', 'Prepared selected sources must match the retained canonical REST selection, not arbitrary omissions.',
              '/artifacts/prepared-bundle/data/selected_sources')
    evidence = prepared.get('selection_evidence')
    selection_bound = False
    if evidence is not None:
        def file_sha(artifact, role):
            matches = [item.get('sha256') for item in artifact.get('files', [])
                       if isinstance(item, dict) and item.get('role') == role]
            return matches[0] if len(matches) == 1 else None
        plan_artifact = artifacts.get(inputs.get('source_plan'), {})
        expected_hashes = {'ncisources_sha256': file_sha(plan_artifact, 'ncisources.spec'),
                           'vsab_updates_sha256': file_sha(state_artifact, 'src/vsab.updates'),
                           'mrsab_sha256': file_sha(bundle, 'MRSAB.RRF'),
                           'installed_sources_sha256': file_sha(state_artifact, 'ncimid.sources')}
        preserved = plan.get('preserved_decision_sha256', {})
        snapshots = plan.get('preserved_snapshot_sha256', {})
        selection_bound = (selection_consistent and isinstance(evidence, dict) and
            evidence.get('profile') == 'mth-rest-subset-selection-v1' and
            all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) and evidence.get(key) == value
                for key, value in expected_hashes.items()) and
            isinstance(preserved, dict) and preserved.get('ncisources.spec') == expected_hashes['ncisources_sha256'] and
            isinstance(snapshots, dict) and snapshots.get('MRSAB.RRF') == expected_hashes['mrsab_sha256'] and
            snapshots.get('ncimid.sources') == expected_hashes['installed_sources_sha256'] and
            len(plan_artifact.get('files', [])) == 3 and
            {item.get('role') for item in plan_artifact.get('files', []) if isinstance(item, dict)} ==
                {'ncisources.spec', 'sab.vsab.map', 'src_data'})
        if not selection_bound:
            issue('MTH_PREPARED_SELECTION_BINDING', 'REST selection evidence must bind the complete selected set and original decisions, VSAB updates, MRSAB and installed-state bytes.',
                  '/artifacts/prepared-bundle/data/selection_evidence')
    mappings = {}
    mapping_rows = plan.get('vsab_mappings', [])
    if not isinstance(mapping_rows, list):
        mapping_rows = []
    for index, row in enumerate(mapping_rows):
        path = '/artifacts/source-plan/data/vsab_mappings/' + str(index)
        if not isinstance(row, dict) or any(not token(row.get(key)) for key in ('source', 'publisher_version', 'version')):
            issue('MTH_VSAB_MAPPING', 'Each mapping needs source, publisher_version and NCImeta version.', path)
            continue
        key = (row['source'], row['publisher_version'])
        if key in mappings:
            issue('MTH_VSAB_MAPPING', 'Publisher source/version mappings must be unambiguous.', path)
        mappings[key] = row['version']
    for index, row in enumerate(decisions):
        path = '/artifacts/source-plan/data/dispositions/' + str(index)
        if not isinstance(row, dict):
            issue('MTH_DISPOSITIONS', 'Each disposition must be a typed decision.', path)
            continue
        reviewed(row, path)
        source, target, disposition = row.get('source'), row.get('version'), row.get('disposition')
        if not token(source) or not token(target) or not isinstance(disposition, str) or disposition not in DISPOSITIONS:
            issue('MTH_DISPOSITION_VALUE', 'Use canonical source/version identities and one of the six reviewed dispositions.', path)
            continue
        if (source, target) in seen:
            issue('MTH_DISPOSITION_DUPLICATE', 'Duplicate source/version decisions are not permitted.', path)
        seen.add((source, target))
        excluded = row.get('excluded_termgroups')
        if not isinstance(excluded, list) or not all(token(x) for x in excluded) or len(set(excluded)) != len(excluded):
            issue('MTH_EXCLUDED_TERMGROUPS', 'Excluded termgroups must be an explicit distinct list, including an empty list.', path)
        if disposition in ACTIVE:
            if source in active:
                issue('MTH_MULTIPLE_ACTIVE', 'Only one active version may be selected per source.', path)
            active.add(source)
            if not token(row.get('publisher_version')) or mappings.get((source, row.get('publisher_version'))) != target:
                issue('MTH_VSAB_BINDING', 'An active disposition must agree with its publisher-to-NCImeta mapping.', path)
        prior = row.get('prior_version')
        if 'prior_version' not in row:
            issue('MTH_PRIOR_SOURCE_VERSION', 'Declare prior_version explicitly, using null when inapplicable.', path)
        if disposition in {'KEEP', 'UPDATE', 'REMOVE'}:
            if not token(prior) or installed.get(source) != prior:
                issue('MTH_PRIOR_SOURCE_VERSION', 'KEEP/UPDATE/REMOVE must bind the saved installed source version.', path)
        if disposition == 'KEEP' and target != prior:
            issue('MTH_KEEP_VERSION', 'KEEP cannot silently select a new NCImeta version.', path)
        if disposition == 'UPDATE' and target == prior:
            if selection_bound and source == excluded_background and source not in selected_sources:
                facts['retained_background_choices'].append({'code': 'MTH_NONSELECTED_SAME_VERSION_UPDATE',
                    'source': source, 'version': target, 'disposition': disposition,
                    'reason': 'Original staff UPDATE retained outside the canonical prepared REST subset; no UPDATE of this source is executed.'})
            else:
                issue('MTH_UPDATE_VERSION', 'A selected UPDATE must identify a different reviewed source version; background retention requires bound canonical REST exclusion evidence.', path)
        if disposition == 'REMOVE' and target != prior:
            issue('MTH_REMOVE_VERSION', 'REMOVE must identify the actual installed version being removed.', path)
        if disposition == 'NEW' and (prior is not None or source in installed):
            issue('MTH_NEW_ALREADY_INSTALLED', 'NEW requires no installed or prior source identity.', path)
        if disposition == 'SPECIAL':
            rule = row.get('special_handling')
            special_rules = policy.get('special_disposition_rules', [])
            if not token(rule) or not isinstance(special_rules, list) or rule not in special_rules:
                issue('MTH_SPECIAL_RULE', 'SPECIAL requires an explicitly reviewed policy rule.', path, 'blocker')
    mth_decisions = [row for row in decisions if isinstance(row, dict) and row.get('source') == 'MTH' and
                     isinstance(row.get('disposition'), str) and row['disposition'] in ACTIVE]
    if len(mth_decisions) != 1 or mth_decisions[0].get('version') != version or mth_decisions[0].get('disposition') != 'UPDATE':
        issue('MTH_ROOT_DISPOSITION', 'The current MTH source must have one explicit UPDATE decision.', '/artifacts/source-plan/data/dispositions')
    root = plan.get('src_root')
    if (not isinstance(root, dict) or root.get('source') != 'MTH' or root.get('version') != version or
            root.get('term_type') != 'SSN' or root.get('status') != 'R' or
            not isinstance(root.get('name'), str) or not root.get('name', '').strip() or
            any(x in root.get('name', '') for x in '|\r\n')):
        issue('MTH_SRC_ROOT', 'Provide the current MTH SSN root declaration with an explicit safe name.',
              '/artifacts/source-plan/data/src_root')
    bounds = config.get('source_atom_ids')
    if not isinstance(bounds, dict):
        issue('MTH_FINAL_RANGE_REQUIRED', 'Final ID bounds and evidence are required before a shadow inversion.',
              '/configuration/source_atom_ids', 'blocker')
    else:
        _, allocation = get(bounds.get('provenance_ref'), 'id-allocation', '/configuration/source_atom_ids/provenance_ref', version)
        if allocation.get('stage') != 'final' or allocation.get('reserved_SRC_atoms') != 2:
            issue('MTH_FINAL_ALLOCATION', 'Use a separately identified final range with two MTH SRC positions; an estimate is insufficient.',
                  '/artifacts/id-allocation/data', 'blocker')
        if any(allocation.get(key) != bounds.get(key) for key in ('start', 'end', 'bound_kind')):
            issue('MTH_ALLOCATION_BINDING', 'Allocation evidence must match the entire selected range.', '/configuration/source_atom_ids')
        if all(type(bounds.get(key)) is int for key in ('start', 'end')):
            if bounds['start'] <= 0 or bounds['start'] + 3 > bounds['end']:
                issue('MTH_RANGE_CAPACITY', 'The range must allow two SRC positions and ordinary atom allocation.', '/configuration/source_atom_ids')
            facts['legacy_allocation'] = {'SRCbuilder_start': bounds['start'], 'SourceAtomIdBase': bounds['start'] + 2,
                                           'first_ordinary_atom': bounds['start'] + 3, 'SourceAtomIdLimit': bounds['end']}
        else:
            issue('MTH_RANGE_VALUES', 'MTH final ID bounds must be integer identifiers, excluding booleans.', '/configuration/source_atom_ids')
    facts.update(source='MTH', version=version, replacement_baseline=baseline,
                 publisher_previous=publisher_previous, publisher_release_chain=chain,
                 publisher_history_artifacts=len(references), source_dispositions=len(decisions),
                 active_sources=sorted(active), source_data_stage=inputs.get('source_data_stage'),
                 comparison_baseline=config.get('comparison_baseline'), ranking_targets_verified=False,
                 MetamorphoSys_required=False if inputs.get('source_data_stage') == 'prepared' else None,
                 declared_prepared_inputs_consistent=not any(item['severity'] in ('error', 'blocker') for item in issues))
    return {'issues': issues, 'facts': facts, 'planned_outputs': list(PLANNED_OUTPUTS)}
