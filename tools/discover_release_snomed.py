#!/usr/bin/env python3
"""Read-only physical SNOMED Snapshot discovery for the common preparation UI.

The coordinator supplies verified streams. This scanner reports decisions; it
never changes mappings, generates settings, reserves identifiers or authorizes a
run. Native files are read once each and full occurrence counts are retained.
"""
from collections import Counter, defaultdict
import datetime
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

from release_snomed import (HEADERS, OPTIONAL_HEADERS, PREFIXES, CATEGORIES,
                            METADATA_ROLES, MRDOC_ROLES, _release, membership_review)

MAX_COMPONENTS = 5_000_000
MAX_IDENTIFIERS = 10_000
MAX_LABELS_PER_ID = 32
# These are fixed consumer capabilities of the reviewed US Snapshot profile,
# not release-specific dates or names. New values need capability review.
LANGUAGE_REFSETS = {'900000000000508004', '900000000000509007'}
EXTENDED_MAP_REFSETS = {'447562003', '6011000124106'}
FIELDS = {'relationship_types': ('rel', 'rela', 'inverse_rela'),
          'association_refsets': ('rel', 'rela', 'inverse_rela'),
          'description_types': ('tty',), 'attribute_refsets': ('atn',),
          'concrete_types': ('atn',), 'refset_patterns': ('pattern',),
          'map_correlations': ('rel', 'rela')}


def analyze(configuration, artifacts, open_role):
    """Discover actual values using open_role(artifact_ref, role) binary streams."""
    out = {'issues': [], 'decisions': [], 'required_inputs': [],
           'facts': {'source': 'SNOMEDCT_US', 'execution_enabled': False,
                     'scope': 'Physical Snapshot preparation discovery; existing native input validation and operational review remain required.'}}
    facts = out['facts']; issues = out['issues']; inputs = configuration.get('inputs', {})
    def issue(code, message, path, severity='error'):
        issues.append({'code': code, 'severity': severity, 'message': message, 'path': path})
    def artifact(reference, kind, path, current=False):
        value = artifacts.get(reference) if isinstance(reference, str) else None
        if not isinstance(value, dict) or value.get('artifact_type') != kind:
            issue('SNOMED_INPUT_ARTIFACT', 'Supply the declared ' + kind + ' artifact.', path, 'decision')
            return None
        allowed = {'NCIMETA', 'SNOMEDCT_US'} if kind == 'ncimeta-state' else {'SNOMEDCT_US'}
        if value.get('source') not in allowed or current and value.get('version') != configuration.get('version'):
            issue('SNOMED_ARTIFACT_RELEASE', 'Artifact source/version differs from this transition.', path)
            return None
        return value
    def role_map(value, reference):
        found = {}; duplicates = set()
        for entry in (value or {}).get('files', []):
            role = entry.get('role')
            if not isinstance(role, str):
                issue('SNOMED_FILE_ROLE', 'A file needs an explicit semantic role.', '/artifacts/' + str(reference) + '/files');continue
            if role in found:duplicates.add(role)
            found[role] = entry
        for role in sorted(duplicates):
            issue('SNOMED_DUPLICATE_FILE_ROLE', 'Duplicate file role: ' + role + '.', '/artifacts/' + str(reference) + '/files')
            found.pop(role, None)
        return found
    def need(reference, role, present, stage='native-snapshot'):
        out['required_inputs'].append({'artifact_ref': reference, 'role': role,
                                       'required_for': stage, 'declared': present})
    def count(counter, key):
        if key not in counter and len(counter) >= MAX_IDENTIFIERS:
            raise ValueError('Distinct native identifier inventory exceeds the bounded discovery limit')
        counter[key] += 1
    def text(value):return isinstance(value, str) and bool(value.strip()) and not any(c in value for c in '\r\n|\t')
    try:
        if configuration.get('source') != 'SNOMEDCT_US':raise ValueError('Expected canonical source SNOMEDCT_US')
        publication = _release(configuration['version'])
        facts.update(version=configuration['version'], publisher_date=publication.isoformat())
        prior = configuration.get('replacement_baseline');facts['replacement_baseline'] = prior
        if not isinstance(prior, dict) or prior.get('source') != 'SNOMEDCT_US' or _release(prior.get('version')) >= publication:
            issue('SNOMED_REPLACEMENT_REQUIRED', 'Declare the earlier release actually inserted; calendar adjacency is not inferred.', '/configuration/replacement_baseline', 'decision')
        if configuration.get('source_options') != {'rf2_view': 'Snapshot'} or inputs.get('source_data_stage') != 'publisher':
            raise ValueError('This discovery capability accepts publisher US RF2 Snapshot inputs only')
        if configuration.get('publisher_history', []) or inputs.get('identity_state') is not None:
            issue('SNOMED_UNSUPPORTED_HISTORY', 'This Snapshot consumer has no prior-folder/identity-map history input.', '/configuration/inputs/identity_state')
        refs = inputs.get('source_data', [])
        if not isinstance(refs, list) or len(refs) != 1:raise ValueError('One publisher bundle is required')
        ref = refs[0];native = artifact(ref, 'publisher-bundle', '/configuration/inputs/source_data', True)
        if native is None:return out
        data = native.get('data', {})
        if data.get('edition') != 'US' or data.get('rf2_view') != 'Snapshot' or data.get('publisher_release_date') != publication.isoformat():
            raise ValueError('Bundle edition/view/publication does not match the selected US Snapshot release')
        if not text(data.get('package_name')):issue('SNOMED_PACKAGE_IDENTITY', 'Declare the actual publisher package name.', '/artifacts/' + ref + '/data/package_name')
        native_roles = role_map(native, ref)
        unsupported = set(native_roles) - set(HEADERS) - set(OPTIONAL_HEADERS)
        if unsupported:issue('SNOMED_UNSUPPORTED_ROLE', 'Unreviewed native roles: ' + ', '.join(sorted(unsupported)), '/artifacts/' + ref + '/files')
        for role in HEADERS:
            need(ref, role, role in native_roles)
            if role not in native_roles:issue('SNOMED_MISSING_RF2_ROLE', 'Missing required Snapshot role: ' + role + '.', '/artifacts/' + ref + '/files', 'decision')
        metadata_ref = inputs.get('reference_ncimeta');metadata = artifact(metadata_ref, 'ncimeta-state', '/configuration/inputs/reference_ncimeta')
        metadata_roles = role_map(metadata, metadata_ref)
        plan_ref = inputs.get('source_plan');plan = artifact(plan_ref, 'source-plan', '/configuration/inputs/source_plan', True)
        policy_ref = configuration.get('policy_ref');policy = artifact(policy_ref, 'policy', '/configuration/policy_ref')
        rules = (policy or {}).get('data', {});planned = (plan or {}).get('data', {})
        for role in METADATA_ROLES:
            need(metadata_ref, role, role in metadata_roles, 'saved-ncimeta-state')
            if role not in metadata_roles:issue('SNOMED_METADATA_REQUIRED', 'Missing saved metadata input: ' + role + '.', '/artifacts/' + str(metadata_ref) + '/files', 'decision')
        for role in MRDOC_ROLES:
            need(metadata_ref, role, role in metadata_roles, 'operational-mrdoc')
            if role not in metadata_roles:issue('SNOMED_MRDOC_REQUIRED', 'Operational MRDOC requires frozen ' + role + ' input; it has not been supplied.', '/artifacts/' + str(metadata_ref) + '/files', 'decision')
        facts['mrdoc_selected'] = planned.get('mrdoc_required') is True
        facts['mrdoc_input_closure'] = set(MRDOC_ROLES).issubset(metadata_roles)
        facts['mrdoc_semantics_validated'] = False
        if facts['mrdoc_selected']:
            issue('SNOMED_MRDOC_CAPABILITY_REQUIRED', 'Operational MRDOC generation/content validation remains outside the native-core consumer, even when its snapshot files are present.', '/artifacts/' + str(plan_ref) + '/data/mrdoc_required', 'decision')
        if policy is not None and rules.get('engine_ref') != configuration.get('engine_ref'):
            issue('SNOMED_POLICY_ENGINE', 'Representation policy must identify the selected engine commit.', '/artifacts/' + str(policy_ref) + '/data/engine_ref')
        for key in ('replacement_baseline', 'comparison_baseline', 'publisher_history'):
            if plan is not None and planned.get(key) != configuration.get(key):
                issue('SNOMED_PLAN_TRANSITION', 'Source-plan transition differs: ' + key + '.', '/artifacts/' + str(plan_ref) + '/data/' + key)
        known = rules.get('mappings', {});overrides = planned.get('mapping_decisions', {})
        effective = {category: dict(known.get(category, {})) for category in CATEGORIES};unresolved = set()
        for category in CATEGORIES:
            additions = overrides.get(category, {})
            if not isinstance(additions, dict):raise ValueError('Mapping decisions must be identifier-keyed objects')
            for identifier, mapping in additions.items():
                if identifier in effective[category] and effective[category][identifier] != mapping:
                    unresolved.add((category,identifier))
                    issue('SNOMED_MAPPING_CHANGE', 'Changing an established mapping needs separate semantic review: ' + identifier + '.', '/artifacts/' + str(plan_ref) + '/data/mapping_decisions/' + category + '/' + identifier, 'decision')
                else:effective[category][identifier] = mapping
        observed = {category: Counter() for category in CATEGORIES};labels = defaultdict(set)
        components = {};modules = Counter();rows_count = {};active_count = {};scanned = [];failed = []
        type_ids = set();normalization_review = set();dependencies = [];language = Counter();extended_refsets = Counter();refsets_by_role = {};earliest = None;latest = None
        order = ['rf2-concepts', 'rf2-relationships', 'rf2-association', 'rf2-descriptions'] + [role for role in HEADERS if role not in {'rf2-concepts','rf2-relationships','rf2-association','rf2-descriptions'}]
        order += [role for role in OPTIONAL_HEADERS if role in native_roles]
        for role in order:
            if role not in native_roles:continue
            descriptor = native_roles[role];member = descriptor.get('archive_member') or urlsplit(descriptor.get('uri', '')).path
            name = PurePosixPath(member).name
            if not name.startswith(PREFIXES[role]) or 'Snapshot' not in name or not name.endswith('_' + publication.strftime('%Y%m%d') + '.txt'):
                issue('SNOMED_MEMBER_IDENTITY', 'Member name disagrees with its Snapshot role/release: ' + role + '.', '/artifacts/' + ref + '/files/' + role);continue
            schema = {**HEADERS, **OPTIONAL_HEADERS}[role];seen = set();total = active_rows = 0
            declared_headers = data.get('headers', {})
            if role in declared_headers and declared_headers[role] != schema:
                issue('SNOMED_DECLARED_HEADER', 'Declared header contradicts the reviewed physical role schema: ' + role + '.', '/artifacts/' + ref + '/data/headers/' + role)
            try:
                with open_role(ref, role) as incoming:
                    raw_header = incoming.readline()
                    if not raw_header.endswith(b'\n') or b'\x00' in raw_header:raise ValueError('Malformed native header terminator/content')
                    header = raw_header.decode('utf-8').rstrip('\r\n').split('\t')
                    if header != schema:raise ValueError('Actual header does not match the reviewed RF2 role')
                    for number, raw in enumerate(incoming, 2):
                        if not raw.endswith(b'\n') or b'\x00' in raw:raise ValueError('Malformed native line terminator/content at row ' + str(number))
                        f = raw.decode('utf-8').rstrip('\r\n').split('\t')
                        if len(f) != len(schema):raise ValueError('RF2 field count differs at row ' + str(number))
                        row = dict(zip(schema, f));identifier = row['id']
                        if not identifier or identifier in seen or row['active'] not in ('0','1') or not re.fullmatch(r'[0-9]+',row['moduleId']):
                            raise ValueError('Duplicate/invalid Snapshot identity/status/module at row ' + str(number))
                        if len(seen) >= MAX_COMPONENTS:raise ValueError('Snapshot role exceeds bounded identity inventory')
                        seen.add(identifier)
                        date = datetime.datetime.strptime(row['effectiveTime'], '%Y%m%d').date()
                        if not re.fullmatch(r'[0-9]{8}', row['effectiveTime']) or date > publication:raise ValueError('Unpublished/future effective date at row ' + str(number))
                        earliest = date if earliest is None else min(earliest, date);latest = date if latest is None else max(latest, date)
                        total += 1;active = row['active'] == '1';active_rows += active
                        if active:count(modules, row['moduleId'])
                        if active and 'refsetId' in row:count(refsets_by_role.setdefault(role,Counter()),row['refsetId'])
                        if role == 'rf2-concepts':components[identifier] = active
                        elif role == 'rf2-relationships' and active:count(observed['relationship_types'], row['typeId']);type_ids.add(row['typeId'])
                        elif role == 'rf2-association' and active:count(observed['association_refsets'], row['refsetId']);type_ids.add(row['refsetId'])
                        elif role == 'rf2-descriptions':
                            if len(components) >= MAX_COMPONENTS:raise ValueError('Combined component inventory exceeds bounded limit')
                            components[identifier] = active and components.get(row['conceptId'], False)
                            count(observed['description_types'], row['typeId'])
                            if row['conceptId'] in type_ids and effective['description_types'].get(row['typeId'], {}).get('tty') == 'FN':
                                label = row['term'].replace('|', '&#x7C;').rstrip(' ')
                                # The producer resolves FN mappings before its
                                # inactive-description suppression. Keep those
                                # labels too. Full iutl.cleanLine Unicode/space
                                # substitution is deliberately not reimplemented.
                                term = row['term']
                                if not term.isascii() or '  ' in term or ' |' in term or '| ' in term or term.startswith(('Retired procedure',' ')):
                                    normalization_review.add(row['conceptId'])
                                if len(labels[row['conceptId']]) >= MAX_LABELS_PER_ID and label not in labels[row['conceptId']]:raise ValueError('Native label inventory exceeds bounded limit')
                                labels[row['conceptId']].add(label)
                        elif role in ('rf2-simple-map','rf2-attribute-value') and active and components.get(row['referencedComponentId']):count(observed['attribute_refsets'], row['refsetId'])
                        elif role == 'rf2-concrete-values' and active:count(observed['concrete_types'], row['typeId'])
                        elif role == 'rf2-refset-descriptor' and active and components.get(row['referencedComponentId']):count(observed['refset_patterns'], row['referencedComponentId'])
                        elif role == 'rf2-language' and active:count(language, row['refsetId'])
                        elif role in ('rf2-extended-map','rf2-complex-map') and active and row['referencedComponentId'] in components:
                            count(observed['map_correlations'], row['correlationId'])
                            if role == 'rf2-extended-map':count(extended_refsets, row['refsetId'])
                        elif role == 'rf2-module-dependency' and active:
                            source = datetime.datetime.strptime(row['sourceEffectiveTime'], '%Y%m%d').date();target = datetime.datetime.strptime(row['targetEffectiveTime'], '%Y%m%d').date()
                            if source > publication or target > source:raise ValueError('Incompatible module-dependency effective times')
                            if len(dependencies) >= MAX_IDENTIFIERS:raise ValueError('Module dependency inventory exceeds bounded limit')
                            dependencies.append({'source_module_id':row['moduleId'],'target_module_id':row['referencedComponentId'],'source_effective_time':row['sourceEffectiveTime'],'target_effective_time':row['targetEffectiveTime']})
                scanned.append(role)
            except (ValueError, OSError, UnicodeError, KeyError) as error:
                failed.append(role)
                issue('SNOMED_NATIVE_SCAN', role + ': ' + str(error), '/artifacts/' + ref + '/files/' + role)
            rows_count[role] = total;active_count[role] = active_rows
        ttys = set();metadata_read = []
        for role in METADATA_ROLES + MRDOC_ROLES:
            if role not in metadata_roles:continue
            try:
                metadata_rows = 0;seen_groups = set()
                with open_role(metadata_ref, role) as incoming:
                    for raw in incoming:
                        metadata_rows += 1
                        if role not in ('sources-src','termgroups-src'):continue
                        f = raw.decode('utf-8').rstrip('\r\n').split('|')
                        terminal = metadata.get('data', {}).get('metadata_format', {}).get(role, {}).get('terminal_delimiter', False)
                        if type(terminal) is not bool:raise ValueError('Metadata terminal delimiter declaration must be boolean')
                        if terminal:
                            if not f or f[-1]:raise ValueError('Declared terminal metadata delimiter is missing')
                            f.pop()
                        if role == 'sources-src':
                            if len(f) != 20 or f[0] != configuration['version'] or f[1] != (prior or {}).get('version') or f[6] != 'SNOMEDCT_US':raise ValueError('Saved sources.src differs from current/replacement source identities')
                        else:
                            if len(f) != 6 or not f[5] or f[0] != configuration['version'] + '/' + f[5] or f[0] in seen_groups:raise ValueError('Saved termgroup identity/width differs or is duplicated')
                            seen_groups.add(f[0])
                            ttys.add(f[5])
                if not metadata_rows:raise ValueError('Saved metadata role is empty')
                if role == 'sources-src' and metadata_rows != 1:raise ValueError('Saved sources.src must contain exactly one current source row')
                metadata_read.append(role)
            except (ValueError, OSError, UnicodeError, KeyError) as error:issue('SNOMED_METADATA_SCAN', role + ': ' + str(error), '/artifacts/' + str(metadata_ref) + '/files/' + role)
        membership = {}
        if policy is not None:
            try:membership = membership_review(policy, native, configuration['version'])
            except (ValueError, KeyError, TypeError) as error:issue('SNOMED_MEMBERSHIP_REVIEW', str(error), '/artifacts/' + str(policy_ref) + '/data/association_membership_review', 'decision')
        membership_inputs = []
        if membership:
            policy_roles = role_map(policy, policy_ref)
            for role in ('archived-sct.cfg','archived-invert_rf2.pl'):
                need(policy_ref, role, role in policy_roles, 'association-membership-review')
                try:
                    with open_role(policy_ref, role) as incoming:
                        while incoming.read(4*1024**2):pass
                    membership_inputs.append(role)
                except (ValueError, OSError, UnicodeError, KeyError) as error:
                    issue('SNOMED_MEMBERSHIP_INPUT', role + ': ' + str(error), '/artifacts/' + str(policy_ref) + '/files/' + role)
            if len(membership_inputs) != 2:membership = {}
        selected_membership = membership.get('association_refsets', {})
        expected_labels = rules.get('labels', {});label_decisions = planned.get('label_decisions', {})
        label_ids = defaultdict(set)
        for identifier, values in labels.items():
            for label in values:label_ids[label].add(identifier)
        for label, identifiers in sorted(label_ids.items()):
            if len(identifiers) > 1:
                for category in ('relationship_types','association_refsets'):
                    unresolved.update((category,identifier) for identifier in identifiers if identifier in observed[category])
                issue('SNOMED_AMBIGUOUS_LABEL', 'A native FN label belongs to several observed type IDs: ' + repr(label) + ' ' + ', '.join(sorted(identifiers)), '/artifacts/' + ref + '/data/discovery/labels', 'decision')
        for identifier in sorted(normalization_review):
            for category in ('relationship_types','association_refsets'):
                if identifier in observed[category]:unresolved.add((category,identifier))
            issue('SNOMED_LABEL_NORMALIZATION_REVIEW', 'Native FN label needs explicit legacy cleanLine/retired-name interpretation: ' + identifier + '.', '/artifacts/' + ref + '/files/rf2-descriptions', 'decision')
        configured = {category:{} for category in CATEGORIES}
        for category in CATEGORIES:
            for identifier, occurrences in sorted(observed[category].items()):
                previous_issues = len(issues)
                mapping = effective[category].get(identifier);path = '/artifacts/' + str(policy_ref) + '/data/mappings/' + category + '/' + identifier
                record = {'category':category,'identifier':identifier,'occurrences':occurrences,'status':'unresolved','configured_mapping':mapping}
                if category in ('relationship_types','association_refsets'):record['current_fn_labels'] = sorted(labels.get(identifier, ()))
                if not isinstance(mapping, dict):issue('SNOMED_MAPPING_REQUIRED', 'Observed ' + category + ' identifier needs an explicit reviewed mapping: ' + identifier + '.', path, 'decision')
                elif mapping.get('decision') == 'membership-only':
                    evidence = selected_membership.get(identifier)
                    if category != 'association_refsets' or evidence is None or identifier in observed['relationship_types'] or set(labels.get(identifier, ())) != set(evidence['fn_labels']):
                        issue('SNOMED_MEMBERSHIP_PHYSICAL_BINDING', 'Membership-only review does not match actual native identifier/labels/role.', path, 'decision')
                    else:record['status'] = 'configured-membership-only'
                elif mapping.get('decision') != 'represent':issue('SNOMED_UNSUPPORTED_EXCLUSION', 'The captured producer cannot implement a new exclusion/unknown decision for ' + identifier + '.', path, 'decision')
                elif any(not isinstance(mapping.get(key), str) or (not mapping[key] and not (category == 'map_correlations' and key == 'rela')) or any(c in mapping[key] for c in '\r\n|\t') for key in FIELDS[category]):
                    issue('SNOMED_MAPPING_FIELDS', 'Representation needs explicit ' + ', '.join(FIELDS[category]) + '.', path, 'decision')
                else:
                    record['status'] = 'configured'
                    if category == 'description_types' and mapping['tty'] not in ttys:issue('SNOMED_TTY_METADATA_REQUIRED', 'Configured TTY has no saved current termgroup row: ' + mapping['tty'] + '.', path, 'decision')
                    if category in ('relationship_types','association_refsets'):
                        actual = labels.get(identifier, set());expected = expected_labels.get(identifier)
                        if not actual:issue('SNOMED_TYPE_LABEL_REQUIRED', 'No native FN label resolved for ' + identifier + '.', path, 'decision')
                        elif expected is None or actual != {expected}:
                            ack = label_decisions.get(identifier, {})
                            if len(actual) != 1 or ack.get('previous_label') != expected or ack.get('current_label') not in actual or not text(ack.get('reason')):
                                issue('SNOMED_CHANGED_TYPE_LABEL', 'Missing/changed/ambiguous native label needs an identifier-bound decision for ' + identifier + '.', '/artifacts/' + str(plan_ref) + '/data/label_decisions/' + identifier, 'decision')
                if len(issues) > previous_issues or (category,identifier) in unresolved:
                    record['status'] = 'unresolved';out['decisions'].append(record)
                else:
                    configured[category][identifier] = record
        for identifier in sorted(set(language)-LANGUAGE_REFSETS):issue('SNOMED_LANGUAGE_REFSET_REQUIRED', 'Unreviewed language preference refset: ' + identifier + '.', '/artifacts/' + ref + '/files/rf2-language', 'decision')
        for identifier in sorted(set(extended_refsets)-EXTENDED_MAP_REFSETS):issue('SNOMED_MAP_TARGET_REQUIRED', 'Unreviewed extended-map target refset: ' + identifier + '.', '/artifacts/' + ref + '/files/rf2-extended-map', 'decision')
        supported = set(rules.get('supported_modules', []));actual_modules = set(modules) | {row['target_module_id'] for row in dependencies}
        for identifier in sorted(actual_modules-supported):issue('SNOMED_MODULE_REVIEW_REQUIRED', 'Actual native module/dependency is outside the reviewed inventory: ' + identifier + '.', '/artifacts/' + str(policy_ref) + '/data/supported_modules', 'decision')
        if not dependencies:issue('SNOMED_MODULE_DEPENDENCY_REQUIRED', 'No active native module dependency evidence was read.', '/artifacts/' + ref + '/files/rf2-module-dependency', 'decision')
        if metadata is not None:
            meta = metadata.get('data', {})
            if not meta.get('snapshot_id') or meta.get('snapshot_id') != metadata.get('provenance', {}).get('capture_id'):
                issue('SNOMED_METADATA_BOUNDARY_REQUIRED', 'Saved metadata needs a coherent, identified capture boundary.', '/artifacts/' + str(metadata_ref) + '/data/snapshot_id', 'decision')
        facts.update(scanned_roles=scanned, failed_roles=failed, required_rf2_roles=list(HEADERS), core_native_scan_complete=set(HEADERS).issubset(scanned),
                     rows=rows_count, active_rows=active_count, observed={key:dict(sorted(value.items())) for key,value in observed.items()},
                     configured_representations=configured, observations_include_failed_roles=bool(failed),
                     label_collection_scope='All FN descriptions for IDs used by active relationships/associations, including inactive descriptions, as the captured producer resolves these before suppression. Multiple labels/collisions and nontrivial legacy normalization require review; full legacy normalization is not inferred.',
                     native_fn_labels={key:sorted(value) for key,value in sorted(labels.items())}, native_modules=dict(sorted(modules.items())),
                     module_dependencies=dependencies, language_refsets=dict(sorted(language.items())), extended_map_refsets=dict(sorted(extended_refsets.items())),
                     refset_ids_by_role={role:dict(sorted(values.items())) for role,values in sorted(refsets_by_role.items())},
                     generic_membership_review={'prior_refset_inventory_supplied':False,'newness_determined':False,'membership_label_semantics_reviewed':False,
                         'scope':'Active refset occurrences are counted without adding mapping categories. Full prior refset inventory and generic membership-label semantic review remain unresolved; neither is inferred from the replacement version.'},
                     effective_time_bounds={'minimum':earliest.isoformat() if earliest else None,'maximum':latest.isoformat() if latest else None},
                     earlier_snapshot_dates_accepted=bool(earliest and earliest < publication), metadata_roles_read=metadata_read,
                     membership_evidence_roles_read=membership_inputs,
                     no_prior_source_folder_consumer=True, prior_source_directory_inferred=False,
                     inventory_limits={'components':MAX_COMPONENTS,'distinct_identifiers_per_category':MAX_IDENTIFIERS,'labels_per_identifier':MAX_LABELS_PER_ID},
                     operational_metadata_inputs_read=all(role in metadata_read for role in METADATA_ROLES + MRDOC_ROLES),
                     all_occurrences_counted_for_scanned_roles=True, native_validation_still_required=True)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        issue('SNOMED_DISCOVERY_CONTRACT', str(error), '/configuration')
    return out
