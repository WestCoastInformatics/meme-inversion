#!/usr/bin/env python3
"""NCIt release declarations only; no acquisition, native discovery or execution.

The common resolver validates/freezes the envelope, artifact bytes and code. This
adapter checks source semantics without opening any artifact URI. Source plans
and representation catalogs retain the existing generator's vocabulary. A v2
installed-state declaration is not a verified export: its raw bindings and all
six existing capture assurances remain separate, mandatory gates.
"""
import base64
import copy
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
import nci_source_plan


PROFILE = 'nci-publisher-inputs-v1'
ROLES = ('annotationDeclaration', 'objectDeclaration', 'classDeclaration', 'relations', 'hierarchy')
PLANNED_OUTPUTS = ('etc/nci.cfg', 'src/sources.src', 'src/termgroups.src',
                   'etc/new-subsources.tsv', 'etc/planned-termgroups.tsv')
DOCS = Path(__file__).resolve().parents[1] / 'docs/inversion-review'
CAPTURE_BLOCKERS = {
    'DEPLOYMENT_IDENTITY_UNVERIFIED': 'No deployed build-to-code acceptance contract has been enrolled.',
    'PROJECT_BINDING_UNVERIFIED': 'The selected deployed project and source-to-project binding are unverified.',
    'EXPORTER_PROFILE_NOT_ACCEPTED': 'No real exporter acceptance profile exists; a declared profile cannot approve itself.',
    'HANDLER_SELECTION_UNVERIFIED': 'Declared handler names do not establish active deployed response behavior.',
    'EXPORT_COMPLETENESS_UNVERIFIED': 'Selected rows and hashes cannot establish exhaustive scope or pagination completeness.',
    'CONSISTENT_CAPTURE_UNVERIFIED': 'No supported coherent multi-export capture boundary has been validated.',
}


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', value):
        raise ValueError('Expected an exact NCIt version such as NCI_2026_10D')
    return value[4:]


def _keys(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError('Missing or unknown ' + label + ' fields')


def _positive(value):
    return type(value) is int and value > 0


def _validate(value, filename):
    schema = json.loads((DOCS / filename).read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: str(list(error.path)))
    if errors:
        first = errors[0]
        raise ValueError('/'.join(map(str, first.path)) + ': ' + first.message)


def analyze(configuration, artifacts):
    """Return deterministic declaration findings; never fetch or mutate inputs.

    Artifact references are logical names. The common resolver owns generic
    schema/URI/hash/provenance checks. No result from this adapter enables a run.
    """
    issues = []
    facts = {'profile': PROFILE, 'production_eligible': False, 'execution_authorized': False,
             'validation_scope': 'declarations only; no publisher row discovery or raw backend binding verification'}

    def issue(severity, code, message, path):
        issues.append({'severity': severity, 'code': code, 'message': message, 'path': path})

    def fail(code, message, path):
        issue('error', code, message, path)

    def data(reference, kind, version, path):
        if not isinstance(reference, str) or not reference or not isinstance(artifacts, dict):
            raise ValueError('An explicit logical ' + kind + ' artifact reference is required')
        artifact = artifacts.get(reference)
        if not isinstance(artifact, dict) or artifact.get('artifact_type') != kind:
            raise ValueError('Missing or incorrectly typed ' + kind + ' artifact: ' + reference)
        if artifact.get('source') != 'NCI' or artifact.get('version') != version:
            raise ValueError('Artifact source/version differs from its declared NCIt dependency: ' + reference)
        if not isinstance(artifact.get('data'), dict):
            raise ValueError('Artifact data must be an object: ' + reference)
        provenance = artifact.get('provenance')
        if isinstance(provenance, dict) and provenance.get('evidence_kind') == 'synthetic-fixture':
            issue('blocker', 'NCI_SYNTHETIC_EVIDENCE', 'Synthetic artifact cannot establish operational evidence.', path)
        return artifact['data'], artifact

    def checked(code, path, operation):
        try:
            return operation()
        except (ValueError, KeyError, TypeError, IndexError) as error:
            fail(code, str(error), path)
            return None

    def transition():
        if configuration.get('source') != 'NCI':
            raise ValueError('This adapter accepts only canonical source NCI')
        current = _version(configuration.get('version'))
        prior = configuration.get('replacement_baseline')
        _keys(prior, ('source', 'version'), 'replacement baseline')
        if prior['source'] != 'NCI' or _version(prior['version']) >= current:
            raise ValueError('An explicit earlier NCIt replacement is required; calendar adjacency is not required')
        if configuration.get('source_options') != {} or configuration.get('output_stage') != 'inversion-src':
            raise ValueError('This NCIt profile requires empty source_options and inversion-src output')
        if configuration.get('comparison_baseline') is not None or configuration.get('publisher_history') != []:
            raise ValueError('This profile has no comparison-baseline or publisher-history preparation stage')
        inputs = configuration['inputs']
        if inputs.get('source_data_stage') != 'publisher':
            raise ValueError('This profile accepts publisher inputs; prepared NCIt bundles are not characterized here')
        return prior, inputs

    selected = checked('NCI_TRANSITION_INVALID', '/configuration', transition)
    if selected is None:
        return {'issues': issues, 'facts': facts, 'planned_outputs': []}
    prior, inputs = selected
    facts.update(source='NCI', version=configuration['version'], replacement_baseline=copy.deepcopy(prior),
                 predecessor_selection='explicit; skipped calendar months permitted')

    def publisher():
        refs = inputs['source_data']
        if not isinstance(refs, list) or len(refs) != 1:
            raise ValueError('One complete five-role NCIt publisher bundle is required')
        value, artifact = data(refs[0], 'publisher-bundle', configuration['version'], '/configuration/inputs/source_data')
        _keys(value, ('profile',), 'NCIt publisher bundle data')
        if value['profile'] != PROFILE:
            raise ValueError('Unsupported NCIt publisher-bundle profile')
        files = artifact['files']
        if not isinstance(files, list) or len(files) != len(ROLES):
            raise ValueError('Exactly five publisher files are required')
        result, identities = {}, set()
        for item in files:
            role = item['role']
            if role not in ROLES or role in result:
                raise ValueError('Missing, duplicate or unknown NCIt publisher role')
            name = PurePosixPath(item.get('archive_member', urlsplit(item['uri']).path)).name
            if not re.fullmatch(re.escape(role) + r'-[0-9]{8}\.txt', name):
                raise ValueError('Publisher filename must identify its declared native role and export date')
            identity = (item['uri'], item.get('archive_member'))
            if identity in identities:
                raise ValueError('Two publisher roles cannot name the same input member')
            identities.add(identity)
            result[role] = {'name': name, 'sha256': item['sha256']}
        if set(result) != set(ROLES):
            raise ValueError('All five distinct publisher roles are required')
        return result

    native = checked('NCI_PUBLISHER_BUNDLE_INVALID', '/configuration/inputs/source_data', publisher)
    if native is not None:
        facts['publisher_roles'] = native
    issue('blocker', 'NCI_PUBLISHER_DISCOVERY_REQUIRED',
          'Declaration checks do not inspect native rows; frozen publisher discovery and review remain required.',
          '/configuration/inputs/source_data')

    def plan_value():
        value, _ = data(inputs['source_plan'], 'source-plan', configuration['version'], '/configuration/inputs/source_plan')
        _validate(value, 'nci-source-plan.schema.json')
        for key in ('source', 'version', 'replacement_baseline', 'comparison_baseline', 'publisher_history'):
            if value[key] != configuration[key]:
                raise ValueError('Source plan differs from common configuration: ' + key)
        if native is not None:
            manifest = {item['name']: item['sha256'] for item in native.values()}
            for entry in value['historical_exceptions']:
                if entry['native_sha256'] != manifest:
                    raise ValueError('Historical exception is not bound to this complete native bundle')
        return value

    plan = checked('NCI_SOURCE_PLAN_INVALID', '/configuration/inputs/source_plan', plan_value)
    if plan is not None:
        facts['optional_decisions'] = {key: len(plan[key]) for key in ('new_subsources', 'new_termgroups')}
        for entry in plan['historical_exceptions']:
            issue('blocker', 'NCI_HISTORICAL_FINDING_REQUIRES_REVIEW',
                  entry['identifier'] + ': ' + entry['kind'] + ': ' + entry['reason'],
                  '/configuration/inputs/source_plan')

    def policy_value():
        value, _ = data(configuration['policy_ref'], 'policy', configuration['version'], '/configuration/policy_ref')
        _keys(value, ('profile', 'metadata_model', 'properties'), 'NCIt policy data')
        if value['profile'] != nci_source_plan.PROFILE:
            raise ValueError('Unsupported NCIt representation policy profile')
        if not isinstance(value['properties'], dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value['properties'].items()):
            raise ValueError('Reviewed legacy properties must be a string-to-string object')
        if any(not k or any(c in k + v for c in '\r\n\x00') for k, v in value['properties'].items()):
            raise ValueError('A legacy property cannot introduce another configuration line')
        if value['properties'].get('VSAB') != configuration['version'] or value['properties'].get('RSAB') != 'NCI':
            raise ValueError('Reviewed legacy properties disagree with the NCIt source/version')
        model = value['metadata_model']
        if not isinstance(model, dict):
            raise ValueError('A representation catalog object is required')
        required = {'schema_version', 'source', 'provenance', 'sources', 'termgroups',
                    'publisher_termgroups', 'publisher_properties', 'publisher_labels', 'relationship_roles'}
        if not required <= set(model) or set(model) - required - {'property_bindings', 'termgroup_bindings'}:
            raise ValueError('Missing or unknown representation catalog fields')
        if type(model['schema_version']) is not int or model['schema_version'] != 1 or model['source'] != 'NCI':
            raise ValueError('Unsupported representation catalog source/schema')
        if not isinstance(model['provenance'], dict) or not isinstance(model['publisher_labels'], dict) or any(not isinstance(model[key], list) for key in ('sources', 'termgroups', 'publisher_termgroups', 'publisher_properties', 'relationship_roles')):
            raise ValueError('Incorrectly typed representation catalog fields')
        return value

    policy = checked('NCI_POLICY_INVALID', '/configuration/policy_ref', policy_value)
    facts['representation_catalog_proves_installation'] = False

    def identity_value():
        value, _ = data(inputs['identity_state'], 'identity-state', prior['version'], '/configuration/inputs/identity_state')
        _keys(value, ('profile', 'root_atom_id', 'root_code', 'root_name', 'replacement_baseline'), 'saved hierarchy root data')
        if value['profile'] != 'saved-hierarchy-root-v1' or not _positive(value['root_atom_id']):
            raise ValueError('A saved hierarchy root requires an exact positive SAID')
        if value['replacement_baseline'] != prior or any(not isinstance(value[key], str) or not value[key].strip() or any(c in value[key] for c in '\r\n\t\x00|') for key in ('root_code', 'root_name')):
            raise ValueError('Saved hierarchy root names/baseline are incomplete or mismatched')
        if policy is not None and any(policy['properties'].get(prop) != value[key] for prop, key in (('HC.RootNodeCode', 'root_code'), ('HC.RootNodeName', 'root_name'))):
            raise ValueError('Saved hierarchy root differs from reviewed legacy properties')
        return value

    identity = checked('NCI_IDENTITY_STATE_INVALID', '/configuration/inputs/identity_state', identity_value)
    if identity is not None:
        facts['saved_hierarchy_root_atom_id'] = identity['root_atom_id']

    def allocation_value():
        bounds = configuration.get('source_atom_ids')
        if bounds is None:
            issue('blocker', 'NCI_ALLOCATION_REQUIRED', 'Final inclusive allocation evidence is absent; full source-plan validation is deferred.', '/configuration/source_atom_ids')
            return None
        _keys(bounds, ('start', 'end', 'bound_kind', 'provenance_ref'), 'source atom bounds')
        if not _positive(bounds['start']) or not _positive(bounds['end']) or bounds['start'] > bounds['end']:
            raise ValueError('An ordered inclusive pair of exact positive integer bounds is required')
        if bounds['bound_kind'] not in ('historical-emitted-range', 'reserved-historical-range', 'dev-reservation', 'production-reservation'):
            raise ValueError('Unknown NCIt allocation evidence kind')
        value, _ = data(bounds['provenance_ref'], 'id-allocation', configuration['version'], '/configuration/source_atom_ids/provenance_ref')
        _keys(value, ('start', 'end', 'bound_kind'), 'allocation data')
        if not _positive(value['start']) or not _positive(value['end']) or value != {key: bounds[key] for key in value}:
            raise ValueError('Configured bounds differ from their allocation artifact')
        if bounds['bound_kind'] in ('historical-emitted-range', 'reserved-historical-range'):
            issue('blocker', 'NCI_HISTORICAL_ALLOCATION_ONLY', 'Historical bounds do not reserve a new operational range.', '/configuration/source_atom_ids')
        return bounds

    bounds = checked('NCI_ALLOCATION_INVALID', '/configuration/source_atom_ids', allocation_value)
    generated = None
    if plan is not None and policy is not None and bounds is not None:
        generated = checked('NCI_SOURCE_PLAN_SEMANTICS_INVALID', '/configuration/inputs/source_plan',
                            lambda: nci_source_plan.generate(configuration, plan, policy['metadata_model'], policy['properties']))
    if generated is None:
        issue('blocker', 'NCI_SOURCE_PLAN_SEMANTICS_NOT_EVALUATED', 'Complete declaration dependencies are required to validate metadata/root/ranking plans.', '/configuration/inputs/source_plan')
    else:
        facts['new_subsources'] = generated['new_subsources']
        facts['new_termgroups'] = generated['new_termgroups']

    state_ref = inputs.get('reference_ncimeta')
    if state_ref is None:
        issue('blocker', 'NCI_INSTALLED_STATE_REQUIRED', 'No installed-state declaration is supplied; catalog membership proves neither roots nor ranking.', '/configuration/inputs/reference_ncimeta')
    else:
        def state_value():
            state, _ = data(state_ref, 'ncimeta-state', configuration['version'], '/configuration/inputs/reference_ncimeta')
            _validate(state, 'nci-installed-state-v2.schema.json')
            if state['scope'] != {key: configuration[key] for key in ('source', 'version', 'replacement_baseline')}:
                raise ValueError('Installed-state scope differs from this exact NCIt transition')
            if state['project']['source_atom_id_key'] != state['project']['terminology'] + '-SRC':
                raise ValueError('Source SAID alternate-ID key differs from the selected project terminology')
            roots = state['source_roots']
            if len({r['source'] for r in roots}) != len(roots) or len({r['source_atom_id'] for r in roots}) != len(roots):
                raise ValueError('Source roots must have unique source identities and SAIDs')
            if any(not _positive(r[key]) for r in roots for key in ('source_atom_id', 'backend_atom_id')):
                raise ValueError('SAIDs and backend IDs must be exact positive integers and remain distinct fields')
            if any(r['code_id'] != 'V-' + r['source'] for r in roots):
                raise ValueError('Declared SRC/RPT root code must select V- followed by the exact root source')
            return state

        state = checked('NCI_INSTALLED_STATE_INVALID', '/configuration/inputs/reference_ncimeta', state_value)
        if state is not None:
            facts['installed_state_validation'] = 'schema and limited declaration comparisons; raw bindings unverified'
            if generated is not None:
                _compare_declared_state(configuration, plan, generated, state, issue)
        issue('blocker', 'NCI_BACKEND_PREFLIGHT_REQUIRED', 'Existing v2 raw-binding and complete semantic preflight has not been performed by this declaration adapter.', '/configuration/inputs/reference_ncimeta')
    for code, message in CAPTURE_BLOCKERS.items():
        issue('blocker', code, message, '/configuration/inputs/reference_ncimeta')
    issues.sort(key=lambda row: (row['path'], row['severity'], row['code'], row['message']))
    return {'issues': issues, 'facts': facts, 'planned_outputs': list(PLANNED_OUTPUTS)}


def _compare_declared_state(config, plan, generated, state, issue):
    """Limited comparisons of unverified declarations; never an export acceptance."""
    path = '/configuration/inputs/reference_ncimeta'
    def block(code, message):
        issue('blocker', code, message, path)
    aliases = {}
    for row in state['version_aliases']:
        identity = (row['source'], row['backend_version'])
        if row['versioned_source'] in aliases:
            block('NCI_STATE_ALIAS_AMBIGUOUS', 'Duplicate versioned-source alias: ' + row['versioned_source'])
        aliases[row['versioned_source']] = identity
    baseline = aliases.get(config['replacement_baseline']['version'])
    replacements = {(row['source'], row['backend_version']) for row in state['replacement_sources']}
    current = {(row['source'], row['backend_version']) for row in state['source_versions'] if row['current']}
    if baseline is None or baseline[0] != 'NCI' or baseline not in replacements or baseline not in current:
        block('NCI_REPLACEMENT_STATE_MISMATCH', 'Explicit primary baseline alias must resolve to a currently selected NCI replacement; no backend-version inference is permitted.')
    sources = next(x for x in generated['files'] if x['relative_path'] == 'src/sources.src')
    rows = [dict(zip(nci_source_plan.SOURCE_FIELDS, line.split('|')[:-1])) for line in base64.b64decode(sources['data_b64']).decode().splitlines()]
    identities = {row['source_name']: (row['stripped_source'], row['version']) for row in rows}
    for vsab, identity in identities.items():
        if vsab in aliases and aliases[vsab] != identity:
            block('NCI_STATE_ALIAS_CONFLICT', 'Generated metadata and captured alias disagree: ' + vsab)
        aliases[vsab] = identity
    roots = {row['source'] for row in state['source_roots']}
    additions = set(generated['new_subsources'])
    families = {row['source']: row['source_family'] for row in state['families']}
    for source in sorted({row['stripped_source'] for row in rows} - additions):
        if families.get(source) != 'NCI':
            block('NCI_ESTABLISHED_FAMILY_MISMATCH', 'Established source requires declared RootTerminology.family=NCI: ' + source)
    for source in sorted(additions & roots):
        block('NCI_NEW_ROOT_ALREADY_PRESENT', 'A new-root decision names an existing declared source root: ' + source)
    for source in sorted({row['stripped_source'] for row in rows} - additions - roots):
        block('NCI_ESTABLISHED_ROOT_MISSING', 'No declared installed root for established source: ' + source)
    groups = next(x for x in generated['files'] if x['relative_path'] == 'src/termgroups.src')
    groups = [dict(zip(nci_source_plan.TERMGROUP_FIELDS, line.split('|')[:-1])) for line in base64.b64decode(groups['data_b64']).decode().splitlines()]
    variables = {'release': config['version'][4:], 'replacement_release': config['replacement_baseline']['version'][4:]}
    new_names = {nci_source_plan.render(row['metadata']['termgroup_name'], variables) for row in plan['new_termgroups']}
    def pair(name):
        vsab, tty = name.rsplit('/', 1)
        identity = aliases.get(vsab)
        return None if identity is None else (identity[0], tty)
    for role in ('default', 'project'):
        existing = {(row['source'], row['tty']) for row in state['precedence_lists'][role]['entries']}
        pending = []
        for row in groups:
            high, low = pair(row['termgroup_name']), pair(row['low_termgroup'])
            if high is None or low is None:
                block('NCI_RANK_ALIAS_MISSING', role + ': no explicit source alias for ' + row['termgroup_name'] + ' or ' + row['low_termgroup'])
            elif row['termgroup_name'] in new_names:
                if high in existing:
                    block('NCI_NEW_RANK_ALREADY_PRESENT', role + ': new pair already declared installed: ' + '/'.join(high))
                else:
                    pending.append((high, low))
            elif high not in existing:
                block('NCI_ESTABLISHED_RANK_MISSING', role + ': established pair is absent: ' + '/'.join(high))
        while pending:
            ready = [(high, low) for high, low in pending if low in existing]
            if not ready:
                for high, low in pending:
                    block('NCI_NEW_RANK_ANCHOR_MISSING', role + ': ' + '/'.join(high) + ' needs ' + '/'.join(low))
                break
            existing.update(high for high, _ in ready)
            pending = [row for row in pending if row not in ready]
