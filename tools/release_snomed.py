#!/usr/bin/env python3
"""Validate declared, frozen SNOMED Snapshot inputs without enabling execution.

File identities and artifact closure are validated by the shared manifest layer.
Headers, discovered identifiers and metadata rows here are producer declarations
bound to those frozen artifacts, not claims that this module scanned remote data.
"""
import datetime
from pathlib import PurePosixPath
import re
from urllib.parse import urlparse

PROFILE = 'snomed-us-snapshot-inputs-v1'
BASE_HEADER = ['id', 'effectiveTime', 'active', 'moduleId', 'refsetId', 'referencedComponentId']
DESCRIPTION_HEADER = ['id', 'effectiveTime', 'active', 'moduleId', 'conceptId', 'languageCode', 'typeId', 'term', 'caseSignificanceId']
RELATIONSHIP_HEADER = ['id', 'effectiveTime', 'active', 'moduleId', 'sourceId', 'destinationId', 'relationshipGroup', 'typeId', 'characteristicTypeId', 'modifierId']
HEADERS = {
    'rf2-concepts': ['id', 'effectiveTime', 'active', 'moduleId', 'definitionStatusId'],
    'rf2-descriptions': DESCRIPTION_HEADER,
    'rf2-relationships': RELATIONSHIP_HEADER,
    'rf2-concrete-values': ['id', 'effectiveTime', 'active', 'moduleId', 'sourceId', 'value', 'relationshipGroup', 'typeId', 'characteristicTypeId', 'modifierId'],
    'rf2-text-definitions': DESCRIPTION_HEADER,
    'rf2-refset-descriptor': BASE_HEADER + ['attributeDescription', 'attributeType', 'attributeOrder'],
    'rf2-description-type': BASE_HEADER + ['descriptionFormat', 'descriptionLength'],
    'rf2-module-dependency': BASE_HEADER + ['sourceEffectiveTime', 'targetEffectiveTime'],
    'rf2-language': BASE_HEADER + ['acceptabilityId'],
    'rf2-simple-map': BASE_HEADER + ['mapTarget'],
    'rf2-extended-map': BASE_HEADER + ['mapGroup', 'mapPriority', 'mapRule', 'mapAdvice', 'mapTarget', 'correlationId', 'mapCategoryId'],
    'rf2-attribute-value': BASE_HEADER + ['valueId'],
    'rf2-simple-refset': BASE_HEADER,
    'rf2-association': BASE_HEADER + ['targetComponentId'],
}
OPTIONAL_HEADERS = {'rf2-complex-map': BASE_HEADER + ['mapGroup', 'mapPriority', 'mapRule', 'mapAdvice', 'mapTarget', 'correlationId']}
PREFIXES = dict(zip(HEADERS, [
    'sct2_Concept_', 'sct2_Description_', 'sct2_Relationship_', 'sct2_RelationshipConcreteValues_',
    'sct2_TextDefinition_', 'der2_cciRefset_RefsetDescriptor', 'der2_ciRefset_DescriptionType',
    'der2_ssRefset_ModuleDependency', 'der2_cRefset_Language', 'der2_sRefset_SimpleMap',
    'der2_iisssccRefset_ExtendedMap', 'der2_cRefset_AttributeValue', 'der2_Refset_Simple',
    'der2_cRefset_Association']))
PREFIXES['rf2-complex-map'] = 'der2_iissscRefset_ComplexMap'
CATEGORIES = ('relationship_types', 'association_refsets', 'description_types', 'attribute_refsets',
              'concrete_types', 'refset_patterns', 'map_correlations')
METADATA_ROLES = ('sources-src', 'termgroups-src', 'icd10-target-inventory', 'icd10cm-target-inventory')
MRDOC_ROLES = ('rela-inverse', 'expanded-form', 'tty-class')


def _date(value, compact=False):
    pattern = r'[0-9]{8}' if compact else r'[0-9]{4}-[0-9]{2}-[0-9]{2}'
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Expected an explicit calendar date')
    return datetime.datetime.strptime(value, '%Y%m%d' if compact else '%Y-%m-%d').date()


def _release(value):
    if not isinstance(value, str) or not re.fullmatch(r'SNOMEDCT_US_[0-9]{4}_[0-9]{2}_[0-9]{2}', value):
        raise ValueError('Expected an exact SNOMEDCT_US version')
    return _date(value.removeprefix('SNOMEDCT_US_').replace('_', '-'))


def _safe_text(value, allow_empty=False):
    return isinstance(value, str) and (allow_empty or bool(value.strip())) and not any(c in value for c in '\r\n|\t')


def analyze(configuration, artifacts):
    """Return source findings/facts and planned legacy paths; never enable a run."""
    result = {'issues': [], 'facts': {'profile': PROFILE, 'execution_enabled': False,
                                    'evidence_scope': 'frozen producer declarations; no remote record scan'},
              'planned_outputs': ['etc/sct.cfg', 'src/sources.src', 'src/termgroups.src',
                                  'etc/icd10.inmeta', 'etc/icd10cm.inmeta']}

    def issue(code, message, path, severity='error'):
        result['issues'].append({'severity': severity, 'code': code, 'message': message, 'path': path})

    def selected(reference, artifact_type, path):
        item = artifacts.get(reference)
        if not isinstance(item, dict) or item.get('artifact_type') != artifact_type:
            issue('SNOMED_ARTIFACT_ROLE', 'Expected a ' + artifact_type + ' artifact.', path)
            return None
        release_bound = artifact_type in ('publisher-bundle', 'source-plan', 'id-allocation')
        allowed_sources = ('SNOMEDCT_US', 'NCIMETA') if artifact_type == 'ncimeta-state' else ('SNOMEDCT_US',)
        if item.get('source') not in allowed_sources or (release_bound and item.get('version') != configuration['version']):
            issue('SNOMED_ARTIFACT_RELEASE', 'Artifact source/version differs from the selected transition.', path)
        return item

    def file_roles(item, path):
        found = {}
        for index, entry in enumerate(item.get('files', [])):
            role = entry['role']
            if role in found:
                issue('SNOMED_DUPLICATE_FILE_ROLE', 'A semantic file role is declared more than once.', path + '/files/' + str(index))
            found[role] = entry
        return found

    try:
        config = configuration
        if config.get('source') != 'SNOMEDCT_US':
            issue('SNOMED_SOURCE', 'This profile accepts the canonical SNOMEDCT_US source only.', '/configuration/source')
        current = _release(config['version'])
        result['facts'].update(source='SNOMEDCT_US', version=config['version'], publisher_date=current.isoformat())
        if config.get('source_options') != {'rf2_view': 'Snapshot'}:
            issue('SNOMED_RF2_VIEW', 'Only Snapshot is supported; Full and Delta require a separately tested interpretation.',
                  '/configuration/source_options', 'blocker')
        if config.get('output_stage') != 'inversion-src':
            issue('SNOMED_OUTPUT_STAGE', 'This source preflight covers inversion-src preparation.', '/configuration/output_stage', 'blocker')
        prior = config.get('replacement_baseline')
        if (not isinstance(prior, dict) or prior.get('source') != 'SNOMEDCT_US' or
                _release(prior.get('version')) >= current):
            issue('SNOMED_REPLACEMENT', 'Declare the earlier source actually replaced in NCImeta.', '/configuration/replacement_baseline')
        result['facts']['replacement_baseline'] = prior
        comparison = config.get('comparison_baseline')
        if comparison is not None and (comparison.get('source') != 'SNOMEDCT_US' or _release(comparison.get('version')) >= current):
            issue('SNOMED_COMPARISON', 'A comparison source must be independently identified and earlier.', '/configuration/comparison_baseline')
        if config.get('publisher_history') != []:
            issue('SNOMED_HISTORY_STAGE', 'Snapshot core has no additional publisher-history consumer; review another profile rather than guessing history.', '/configuration/publisher_history', 'blocker')
        inputs = config['inputs']
        if inputs.get('source_data_stage') != 'publisher':
            issue('SNOMED_INPUT_STAGE', 'This profile requires declared publisher RF2 Snapshot inputs.', '/configuration/inputs/source_data_stage')
        if inputs.get('identity_state') is not None:
            issue('SNOMED_IDENTITY_STAGE', 'No prior identity-map consumer is declared in this Snapshot profile.', '/configuration/inputs/identity_state', 'blocker')
        refs = inputs.get('source_data')
        if not isinstance(refs, list) or len(refs) != 1:
            issue('SNOMED_NATIVE_BUNDLE', 'One complete typed native bundle is required.', '/configuration/inputs/source_data')
            return result
        native = selected(refs[0], 'publisher-bundle', '/configuration/inputs/source_data/0')
        metadata = selected(inputs.get('reference_ncimeta'), 'ncimeta-state', '/configuration/inputs/reference_ncimeta')
        plan = selected(inputs.get('source_plan'), 'source-plan', '/configuration/inputs/source_plan')
        policy = selected(config.get('policy_ref'), 'policy', '/configuration/policy_ref')
        if any(item is None for item in (native, metadata, plan, policy)):
            return result
        data, meta, planned, rules = (item['data'] for item in (native, metadata, plan, policy))
        if rules.get('engine_ref') != config.get('engine_ref'):
            issue('SNOMED_POLICY_ENGINE', 'Representation policy must identify the selected production-derived engine revision.', '/artifacts/' + config['policy_ref'] + '/data/engine_ref')
        for key in ('replacement_baseline', 'comparison_baseline', 'publisher_history'):
            if key not in planned or planned[key] != config.get(key):
                issue('SNOMED_TRANSITION_PLAN', 'Reviewed source-plan transition differs: ' + key + '.', '/artifacts/' + inputs['source_plan'] + '/data/' + key)
        if data.get('edition') != 'US' or data.get('rf2_view') != 'Snapshot':
            issue('SNOMED_PACKAGE_VIEW', 'Native package must explicitly identify the US Snapshot view.', '/artifacts/' + refs[0] + '/data', 'blocker')
        if _date(data.get('publisher_release_date')) != current:
            issue('SNOMED_PUBLISHER_DATE', 'Publisher release date differs from the current source version.', '/artifacts/' + refs[0] + '/data/publisher_release_date')
        if not _safe_text(data.get('package_name')):
            issue('SNOMED_PACKAGE_IDENTITY', 'An explicit package name is required; it is never reconstructed from a predecessor.', '/artifacts/' + refs[0] + '/data/package_name')
        native_roles = file_roles(native, '/artifacts/' + refs[0])
        required_roles = set(HEADERS)
        missing = required_roles - set(native_roles)
        unexpected = set(native_roles) - required_roles - set(OPTIONAL_HEADERS)
        if missing:
            issue('SNOMED_MISSING_RF2_ROLES', 'Missing required RF2 roles: ' + ', '.join(sorted(missing)), '/artifacts/' + refs[0] + '/files')
        if unexpected:
            issue('SNOMED_UNSUPPORTED_RF2_ROLES', 'New native roles need reviewed consumers: ' + ', '.join(sorted(unexpected)), '/artifacts/' + refs[0] + '/files', 'blocker')
        headers = data.get('headers', {})
        if set(headers) != set(native_roles):
            issue('SNOMED_HEADER_INVENTORY', 'Declare one header for each selected RF2 file and no undeclared files.', '/artifacts/' + refs[0] + '/data/headers')
        member_names = set()
        for role, entry in native_roles.items():
            if role not in PREFIXES:
                continue
            member = entry.get('archive_member') or urlparse(entry['uri']).path
            name = PurePosixPath(member).name
            # Package/root naming and timestamps are not inferred.  The declared
            # member still has to identify its RF2 role/view/current release.
            if (name in member_names or not name.startswith(PREFIXES[role]) or 'Snapshot' not in name or
                    not name.endswith('_' + current.strftime('%Y%m%d') + '.txt')):
                issue('SNOMED_RF2_MEMBER_IDENTITY', 'Explicit member name does not agree with role, Snapshot view and release date.', '/artifacts/' + refs[0] + '/files/' + role)
            member_names.add(name)
            if headers.get(role) != {**HEADERS, **OPTIONAL_HEADERS}[role]:
                issue('SNOMED_RF2_HEADER', 'Declared RF2 header differs from the reviewed role schema.', '/artifacts/' + refs[0] + '/data/headers/' + role)
        bounds = data.get('effective_time_bounds', {})
        earliest, latest = _date(bounds.get('minimum'), True), _date(bounds.get('maximum'), True)
        if earliest > latest or latest > current:
            issue('SNOMED_EFFECTIVE_TIME', 'Declared record effective dates must be ordered and not later than the publisher release.', '/artifacts/' + refs[0] + '/data/effective_time_bounds')
        result['facts']['older_snapshot_effective_dates_accepted'] = earliest < current
        supported_modules = rules.get('supported_modules', [])
        dependencies = data.get('module_dependencies')
        if not isinstance(dependencies, list) or not dependencies:
            issue('SNOMED_MODULE_DEPENDENCIES', 'Declare the observed module-dependency relationships.', '/artifacts/' + refs[0] + '/data/module_dependencies')
        else:
            seen = set()
            for index, dependency in enumerate(dependencies):
                key = (dependency['source_module_id'], dependency['target_module_id'])
                source_date = _date(dependency['source_effective_time'], True)
                target_date = _date(dependency['target_effective_time'], True)
                if (key in seen or any(not re.fullmatch(r'[0-9]+', value) or value not in supported_modules for value in key) or
                        source_date > current or target_date > source_date):
                    issue('SNOMED_MODULE_COMPATIBILITY', 'Unreviewed, duplicate or temporally inconsistent module dependency.', '/artifacts/' + refs[0] + '/data/module_dependencies/' + str(index))
                seen.add(key)
        metadata_roles = file_roles(metadata, '/artifacts/' + inputs['reference_ncimeta'])
        for role in METADATA_ROLES:
            if role not in metadata_roles:
                issue('SNOMED_METADATA_DEPENDENCY', 'Missing saved preparation input: ' + role + '.', '/artifacts/' + inputs['reference_ncimeta'] + '/files')
        if not _safe_text(meta.get('snapshot_id')) or meta.get('snapshot_id') != metadata['provenance']['capture_id']:
            issue('SNOMED_METADATA_SNAPSHOT', 'Saved metadata must identify its coherent capture boundary.', '/artifacts/' + inputs['reference_ncimeta'] + '/data/snapshot_id')
        rows = meta.get('sources_rows', [])
        if (len(rows) != 1 or len(rows[0]) != 20 or any(not _safe_text(value, True) for value in rows[0]) or rows[0][0] != config['version'] or
                rows[0][1] != (prior or {}).get('version') or rows[0][6] != 'SNOMEDCT_US'):
            issue('SNOMED_SOURCE_METADATA', 'Declared sources.src row must have 20 fields, current version, actual replacement and SNOMEDCT_US source family.', '/artifacts/' + inputs['reference_ncimeta'] + '/data/sources_rows')
        groups, ttys = set(), set()
        group_rows = meta.get('termgroups_rows', [])
        if not group_rows:
            issue('SNOMED_TERMGROUP_METADATA', 'Saved termgroup rows are required.', '/artifacts/' + inputs['reference_ncimeta'] + '/data/termgroups_rows')
        for index, row in enumerate(group_rows):
            if (len(row) != 6 or any(not _safe_text(value, True) for value in row) or not _safe_text(row[5]) or row[0] != config['version'] + '/' + row[5] or row[0] in groups):
                issue('SNOMED_TERMGROUP_METADATA', 'Declared termgroup row must have 6 fields and a unique current source/TTY identity.', '/artifacts/' + inputs['reference_ncimeta'] + '/data/termgroups_rows/' + str(index))
            else:
                groups.add(row[0]); ttys.add(row[5])
        if set(meta.get('target_inventories', [])) != {'ICD10', 'ICD10CM'}:
            issue('SNOMED_ICD_INVENTORY', 'Preserve explicit ICD10 and ICD10CM target inventory identities.', '/artifacts/' + inputs['reference_ncimeta'] + '/data/target_inventories')
        mrdoc = planned.get('mrdoc_required')
        if type(mrdoc) is not bool:
            issue('SNOMED_MRDOC_SELECTION', 'Explicitly select or exclude MRDOC generation in the reviewed plan.', '/artifacts/' + inputs['source_plan'] + '/data/mrdoc_required')
        if mrdoc is True:
            result['planned_outputs'].append('src/MRDOC.RRF')
            for role in MRDOC_ROLES:
                if role not in metadata_roles:
                    issue('SNOMED_MRDOC_DEPENDENCY', 'Selected MRDOC generation requires frozen ' + role + '.', '/artifacts/' + inputs['reference_ncimeta'] + '/files', 'blocker')
        discovery = data.get('discovery', {})
        decisions = planned.get('mapping_decisions', {})
        for at, mappings in (('/artifacts/' + config['policy_ref'] + '/data/mappings', rules.get('mappings', {})),
                             ('/artifacts/' + inputs['source_plan'] + '/data/mapping_decisions', decisions)):
            if set(mappings) != set(CATEGORIES):
                issue('SNOMED_MAPPING_CATEGORIES', 'Declare all reviewed mapping categories, including empty objects; unknown categories are unsupported.', at)
        for category in CATEGORIES:
            observed = discovery.get(category)
            known = rules.get('mappings', {}).get(category, {})
            reviewed = decisions.get(category, {})
            if not isinstance(observed, list) or len(set(observed)) != len(observed) or any(not isinstance(x, str) or not re.fullmatch(r'[0-9]+', x) for x in observed):
                issue('SNOMED_DISCOVERY_INVENTORY', 'Declare the unique observed native identifiers for ' + category + '.', '/artifacts/' + refs[0] + '/data/discovery/' + category)
                continue
            if not isinstance(known, dict) or not isinstance(reviewed, dict):
                issue('SNOMED_MAPPING_SHAPE', 'Mappings and reviewed decisions must be keyed by native identifier.', '/artifacts/' + config['policy_ref'] + '/data/mappings/' + category)
                continue
            effective = dict(known)
            for identifier, decision in reviewed.items():
                if identifier in known and known[identifier] != decision:
                    issue('SNOMED_EXISTING_POLICY_CHANGE', 'Changing an established mapping requires a separate semantic-policy profile/review.', '/artifacts/' + inputs['source_plan'] + '/data/mapping_decisions/' + category + '/' + identifier, 'blocker')
                else:
                    effective[identifier] = decision
            for identifier in observed:
                mapping = effective.get(identifier)
                at = '/artifacts/' + config['policy_ref'] + '/data/mappings/' + category + '/' + identifier
                if not isinstance(mapping, dict):
                    issue('SNOMED_UNRESOLVED_NATIVE_VALUE', 'Observed ' + category + ' identifier has no explicit reviewed representation/exclusion: ' + identifier + '.', at, 'blocker')
                    continue
                if mapping.get('decision') == 'exclude':
                    if not _safe_text(mapping.get('reason')):
                        issue('SNOMED_EXCLUSION_REASON', 'Intentional exclusion requires an explicit rationale.', at)
                elif mapping.get('decision') != 'represent':
                    issue('SNOMED_MAPPING_DECISION', 'Mapping decision must be represent or exclude.', at)
                else:
                    fields = {'relationship_types': ('rel', 'rela', 'inverse_rela'), 'association_refsets': ('rel', 'rela', 'inverse_rela'),
                              'description_types': ('tty',), 'attribute_refsets': ('atn',), 'concrete_types': ('atn',),
                              'refset_patterns': ('pattern',), 'map_correlations': ('rel', 'rela')}[category]
                    if any(not _safe_text(mapping.get(field), allow_empty=(category == 'map_correlations' and field == 'rela')) for field in fields):
                        issue('SNOMED_MAPPING_FIELDS', 'Reviewed representation is missing required fields: ' + ', '.join(fields) + '.', at)
                    if category == 'description_types' and mapping.get('tty') not in ttys:
                        issue('SNOMED_TTY_METADATA', 'A represented description TTY lacks current termgroup metadata.', at)
        labels, expected_labels = discovery.get('labels', {}), rules.get('labels', {})
        required_labels = set(discovery.get('relationship_types', [])) | set(discovery.get('association_refsets', []))
        if not required_labels.issubset(labels):
            issue('SNOMED_DISCOVERY_LABELS', 'Declare current labels for all observed relationship and association identifiers.', '/artifacts/' + refs[0] + '/data/discovery/labels')
        acknowledgments = planned.get('label_decisions', {})
        for identifier, label in labels.items():
            if not _safe_text(label):
                issue('SNOMED_LABEL_VALUE', 'Observed labels must be valid single-field strings.', '/artifacts/' + refs[0] + '/data/discovery/labels/' + identifier)
            if identifier in expected_labels and label != expected_labels[identifier]:
                decision = acknowledgments.get(identifier)
                if (not isinstance(decision, dict) or decision.get('previous_label') != expected_labels[identifier] or
                        decision.get('current_label') != label or not _safe_text(decision.get('reason'))):
                    issue('SNOMED_CHANGED_LABEL', 'Changed label needs a reviewed identifier-bound decision; never silently fall back to name matching.', '/artifacts/' + inputs['source_plan'] + '/data/label_decisions/' + identifier, 'blocker')
        ids = config.get('source_atom_ids')
        if ids is None:
            issue('SNOMED_ID_ALLOCATION_PENDING', 'Final complete inclusive source-atom bounds remain pending.', '/configuration/source_atom_ids', 'blocker')
        else:
            if (any(type(ids.get(key)) is not int or ids[key] <= 0 for key in ('start', 'end')) or
                    ids['start'] > ids['end'] or ids.get('bound_kind') not in
                    ('reserved-historical-range', 'historical-emitted-range', 'dev-reservation', 'production-reservation')):
                issue('SNOMED_ID_BOUNDS', 'Declare positive ordered inclusive bounds with an explicit evidence kind.', '/configuration/source_atom_ids')
            allocation = selected(ids.get('provenance_ref'), 'id-allocation', '/configuration/source_atom_ids/provenance_ref')
            if allocation is not None and any(allocation['data'].get(key) != ids.get(key) for key in ('start', 'end', 'bound_kind')):
                issue('SNOMED_ID_ALLOCATION_BINDING', 'Source-atom bounds differ from their declared evidence.', '/configuration/source_atom_ids')
            result['facts']['source_atom_ids'] = {key: ids.get(key) for key in ('start', 'end', 'bound_kind')}
        result['facts'].update(package_name=data.get('package_name'), rf2_roles=sorted(native_roles),
                               module_dependencies=data.get('module_dependencies'), ncimeta_snapshot_id=meta.get('snapshot_id'),
                               metadata_inputs_preserved=metadata['provenance'].get('evidence_kind') == 'preserved',
                               mrdoc_selected=mrdoc is True,
                               declared_discovery_counts={key: len(discovery.get(key, [])) for key in CATEGORIES},
                               prior_source_directory_required=False,
                               icd_inventory_consumer='mandatory reads retained; direct pairwise relationship emission is disabled in captured core')
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        issue('SNOMED_CONTRACT_SHAPE', 'Malformed or incomplete source declaration: ' + str(error), '/configuration')
    return result
