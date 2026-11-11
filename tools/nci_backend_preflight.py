#!/usr/bin/env python3
"""Review an explicitly supplied NCImeta v2 state artifact; no live capture or execution."""
import argparse
import base64
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from jsonschema import Draft202012Validator, FormatChecker

import nci_configuration
import nci_release_preflight as v1
import nci_source_plan as plans

SCHEMA = Path(__file__).resolve().parents[1] / 'docs/inversion-review/nci-installed-state-v2.schema.json'
PROFILE = 'ncimeta-installed-state-v2'


def _load(raw):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON value')))


def _path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or '..' in path.parts or str(path) != value:
        raise ValueError('Unsafe raw-export path')
    return path


def _pointer(value, pointer):
    if pointer == '':
        return value
    if not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise ValueError('Invalid raw JSON pointer')
    try:
        for key in pointer[1:].split('/'):
            key = key.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                if not re.fullmatch(r'0|[1-9][0-9]*', key):
                    raise ValueError('Invalid raw array index')
                value = value[int(key)]
            else:
                value = value[key]
        return value
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('Raw JSON binding is absent') from exc


def _pairs(rows):
    result = [(row['source'], row['tty']) for row in rows]
    if len(result) != len(set(result)):
        raise ValueError('Duplicate precedence pair')
    return result


def _insert_pairs(existing, changes, label):
    """Mirror missing-pair insertion separately for each reviewed precedence list."""
    result = list(existing)
    pending = [(high, low) for high, low in changes if high not in result]
    while pending:
        progress = False
        for high, low in list(pending):
            if high in result:
                pending.remove((high, low));progress = True
            elif low in result:
                result.insert(result.index(low), high)
                pending.remove((high, low));progress = True
        if not progress:
            break
    return result, [{'code': label + '_PRECEDENCE_UNRESOLVED', 'identifier': '/'.join(high),
                     'reason': 'No insertion progress; required low pair is ' + '/'.join(low)}
                    for high, low in pending]


def analyze_backend(configuration, source_plan, metadata_model, properties,
                    installed_state, expected_state_sha256, raw_exports):
    """Validate bytes and preview semantics; no exporter/deployment is accepted yet."""
    if (not isinstance(installed_state, dict) or installed_state.get('profile') != PROFILE
            or not isinstance(expected_state_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_state_sha256)
            or v1.content_sha256(installed_state) != expected_state_sha256):
        raise ValueError('Changed or unsupported v2 state artifact')
    schema_raw = SCHEMA.read_bytes()
    errors = sorted(Draft202012Validator(_load(schema_raw), format_checker=FormatChecker())
                    .iter_errors(installed_state), key=lambda error: str(list(error.path)))
    if errors:
        raise ValueError('Invalid v2 artifact at ' + '/'.join(map(str, errors[0].path)) + ': ' + errors[0].message)
    state, config = installed_state, configuration
    if config.get('source') != 'NCI' or state['scope'] != {key: config[key] for key in ('source', 'version', 'replacement_baseline')}:
        raise ValueError('V2 state scope differs from the common NCIt transition')
    current = nci_configuration.release(config['version'])
    baseline = config['replacement_baseline']
    if baseline['source'] != 'NCI' or nci_configuration.release(baseline['version']) >= current:
        raise ValueError('An explicit earlier NCIt replacement is required')
    project = state['project']
    integer_values = [state['schema_version'], project['id'], project['precedence_list_id']]
    integer_values += [row[key] for row in state['source_roots'] for key in ('source_atom_id', 'backend_atom_id')]
    integer_values += [row['id'] for row in state['precedence_lists'].values()]
    integer_values += [row['bytes'] for row in state['raw_exports']]
    if any(type(value) is not int for value in integer_values):
        raise ValueError('Schema versions, IDs and byte counts must be exact integers')
    if project['source_atom_id_key'] != project['terminology'] + '-SRC':
        raise ValueError('Source atom ID key differs from the selected project terminology')
    started = datetime.fromisoformat(state['capture']['started_at'].replace('Z', '+00:00'))
    completed = datetime.fromisoformat(state['capture']['completed_at'].replace('Z', '+00:00'))
    if completed < started:
        raise ValueError('Capture completion precedes capture start')
    if not isinstance(raw_exports, dict):
        raise ValueError('Raw exports must be an explicit path-to-original-bytes mapping')
    parsed, identities, descriptions = {}, {}, {}
    for item in state['raw_exports']:
        name = item['path'];_path(name)
        if name in descriptions:
            raise ValueError('Duplicate raw-export identity')
        descriptions[name] = item
        raw = raw_exports.get(name)
        if not isinstance(raw, bytes) or len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Missing or changed raw-export bytes: ' + name)
        parsed[name] = _load(raw) if item['encoding'] == 'json' else None
        identities[name] = {'bytes': len(raw), 'sha256': item['sha256'], 'encoding': item['encoding']}
    if set(raw_exports) != set(descriptions):
        raise ValueError('Undeclared raw-export bytes supplied')
    evidence_paths = [state['deployment']['evidence_path'], state['capture']['consistency_boundary']['evidence_path']]
    evidence_paths += list(state['capture']['completeness_evidence'].values())
    for path in evidence_paths:
        if path is not None and path not in descriptions:
            raise ValueError('Evidence reference names an undeclared raw export')
    raw_findings, bindings = [], []

    def bind(row, mapping, label):
        binding = row['binding'];name = binding['path']
        if name not in descriptions:
            raise ValueError('Row names an undeclared raw export: ' + label)
        if parsed[name] is None:
            raw_findings.append({'code': 'RAW_BINDING_ENCODING_UNSUPPORTED', 'identifier': label,
                                 'reason': 'Bytes are pinned but this preview cannot verify JSON field bindings in an opaque export.'})
            return None
        raw = _pointer(parsed[name], binding['json_pointer'])
        if not isinstance(raw, dict):
            raise ValueError('Raw row binding must select an object: ' + label)
        for normalized, field in mapping.items():
            if field not in raw or type(raw[field]) is not type(row[normalized]) or raw[field] != row[normalized]:
                raise ValueError('Raw field differs from normalized state: ' + label + '/' + normalized)
        bindings.append({'identifier': label, 'path': name, 'json_pointer': binding['json_pointer']})
        return raw

    bind(project, {'id': 'id', 'terminology': 'terminology', 'version': 'version', 'branch': 'branch',
                   'precedence_list_id': 'precedenceListId'}, 'project')
    families, versions, captured_aliases, roots, root_saids, backend_ids = {}, {}, {}, {}, set(), set()
    for row in state['families']:
        if row['source'] in families:
            raise ValueError('Duplicate root-terminology metadata')
        bind(row, {'source': 'terminology', 'source_family': 'family'}, 'family:' + row['source'])
        families[row['source']] = row['source_family']
    for row in state['source_versions']:
        pair = (row['source'], row['backend_version'])
        if pair in versions:
            raise ValueError('Duplicate source/version state')
        bind(row, {'source': 'terminology', 'backend_version': 'version', 'current': 'current'}, 'version:' + '/'.join(pair))
        versions[pair] = row
    for row in state['version_aliases']:
        name = row['versioned_source'];identity = (row['source'], row['backend_version'])
        if name in captured_aliases or identity not in versions:
            raise ValueError('Duplicate source-version alias or alias without captured version metadata')
        bind(row, {'versioned_source': 'source_name', 'source': 'stripped_source', 'backend_version': 'version'}, 'alias:' + name)
        captured_aliases[name] = identity
    for row in state['source_roots']:
        source = row['source']
        if source in roots or row['source_atom_id'] in root_saids or row['backend_atom_id'] in backend_ids:
            raise ValueError('Duplicate or ambiguous source-root identity')
        if row['code_id'] != 'V-' + source or row['branch'] != project['branch']:
            raise ValueError('Source root differs from its explicit SRC/RPT selector')
        raw = bind(row, {'backend_atom_id': 'id', 'atom_terminology': 'terminology', 'atom_version': 'version',
                         'term_type': 'termType', 'code_id': 'codeId', 'branch': 'branch'}, 'root:' + source)
        if raw is not None and (not isinstance(raw.get('alternateTerminologyIds'), dict)
                                or raw['alternateTerminologyIds'].get(project['source_atom_id_key']) != str(row['source_atom_id'])):
            raise ValueError('Source-root SAID is absent from the selected project alternate-ID entry')
        roots[source] = row;root_saids.add(row['source_atom_id']);backend_ids.add(row['backend_atom_id'])
    precedences = {}
    for role, row in state['precedence_lists'].items():
        pairs = _pairs(row['entries'])
        raw = bind(row, {'id': 'id', 'terminology': 'terminology', 'version': 'version'}, role + '-precedence')
        if raw is not None:
            try:
                raw_pairs = [(pair['key'], pair['value']) for pair in raw['precedence']['keyValuePairs']]
            except (KeyError, TypeError) as exc:
                raise ValueError('Raw precedence binding lacks its ordered key/value pairs') from exc
            if raw_pairs != pairs:
                raise ValueError('Normalized precedence differs from raw pair identities/order')
        precedences[role] = pairs
    default, selected = state['precedence_lists']['default'], state['precedence_lists']['project']
    if (default['terminology'], default['version']) != (project['terminology'], project['version']) or selected['id'] != project['precedence_list_id']:
        raise ValueError('Precedence lists differ from the selected default/project identities')
    if default['id'] == selected['id'] and (default != selected):
        # One underlying list may be selected twice, but cannot have two states.
        if {key: default[key] for key in ('terminology', 'version', 'entries')} != {key: selected[key] for key in ('terminology', 'version', 'entries')}:
            raise ValueError('One precedence-list ID has conflicting captured states')
    term_types = {}
    for row in state['term_types']:
        if row['tty'] in term_types:
            raise ValueError('Duplicate generic term-type definition')
        if (row['terminology'], row['version']) != (project['terminology'], project['version']):
            raise ValueError('Generic term-type metadata belongs to another project terminology/version')
        bind(row, {'tty': 'abbreviation', 'suppressible': 'suppressible', 'exclude': 'exclude', 'norm_exclude': 'normExclude',
                   'terminology': 'terminology', 'version': 'version'}, 'TTY:' + row['tty'])
        term_types[row['tty']] = row
    replacement = set()
    for row in state['replacement_sources']:
        pair = (row['source'], row['backend_version'])
        if pair in replacement or any(x[0] == pair[0] for x in replacement):
            raise ValueError('Duplicate replacement-source membership')
        if pair not in versions or not versions[pair]['current'] or families.get(pair[0]) != 'NCI':
            raise ValueError('Replacement-source membership lacks matching current NCI-family state')
        replacement.add(pair)
    generated = plans.generate(config, source_plan, metadata_model, properties)
    source_rows = v1._rows(generated, 'src/sources.src', plans.SOURCE_FIELDS)
    group_rows = v1._rows(generated, 'src/termgroups.src', plans.TERMGROUP_FIELDS)
    semantic, observations, previews = [], [], {}

    def finding(code, identity, reason):
        semantic.append({'code': code, 'identifier': identity, 'reason': reason})

    if not raw_findings:
        expected_primary = ('NCI', nci_configuration.release(baseline['version']))
        primary_current = [pair for pair, row in versions.items() if pair[0] == 'NCI' and row['current']]
        if primary_current != [expected_primary] or expected_primary not in replacement or captured_aliases.get(baseline['version']) != expected_primary:
            finding('PRIMARY_REPLACEMENT_MISMATCH', 'NCI', 'Captured current primary version and reviewed replacement membership must match the explicit baseline.')
        current_counts = {}
        for (source, _), row in versions.items():
            if row['current']:
                current_counts[source] = current_counts.get(source, 0) + 1
            if source not in families:
                finding('SOURCE_FAMILY_MISSING', source, 'Current/version metadata lacks captured root-terminology family metadata.')
        for source, count in current_counts.items():
            if count > 1:
                finding('AMBIGUOUS_CURRENT_VERSION', source, 'More than one source version is marked current.')
        candidate_sources = {row['stripped_source'] for row in source_rows}
        version_identities = {row['source_name']: (row['stripped_source'], row['version']) for row in source_rows}
        for name, identity in captured_aliases.items():
            if name in version_identities and version_identities[name] != identity:
                raise ValueError('Captured/generated mappings disagree for the same source-version label')
            version_identities[name] = identity
        aliases = {name: identity[0] for name, identity in version_identities.items()}
        for source in families:
            if source in aliases and aliases[source] != source:
                raise ValueError('A root-source name collides with a different versioned-source alias')
            aliases[source] = source
        new_sources = set(generated['new_subsources'])
        for row in source_rows:
            source = row['stripped_source']
            if source in new_sources:
                if source in roots:
                    finding('NEW_SOURCE_ROOT_ALREADY_PRESENT', source, 'A root-creation decision conflicts with a captured SRC/RPT source root.')
                elif source in families or any(pair[0] == source for pair in versions):
                    finding('SOURCE_METADATA_WITHOUT_NEW_ROOT', source, 'Existing source metadata with no root requires a reviewed reconciliation decision.')
            elif source not in roots:
                finding('ESTABLISHED_SOURCE_ROOT_MISSING', source, 'Known representation does not establish an installed SRC/RPT source atom.')
            if source not in new_sources and families.get(source) != 'NCI':
                finding('SOURCE_FAMILY_MISMATCH', source, 'Established NCI-family metadata is absent or belongs to another family.')
            if (source, current) in versions:
                finding('PROPOSED_VERSION_ALREADY_PRESENT', row['source_name'], 'The proposed source/version already exists in captured metadata.')
            if row['low_source'] not in version_identities:
                finding('SOURCE_RANK_ALIAS_MISSING', row['source_name'], 'No exact generated/captured metadata mapping resolves low_source: ' + row['low_source'])
        for source, _ in replacement:
            if source not in candidate_sources:
                finding('SOURCE_REMOVAL_REQUIRES_REVIEW', source, 'A reviewed replacement source is absent from generated metadata.')

        def pair(name):
            source_name, tty = name.rsplit('/', 1)
            if source_name not in aliases:
                finding('TERMGROUP_SOURCE_UNRESOLVED', name, 'No exact captured/generated source alias resolves this termgroup label.')
                return None
            return aliases[source_name], tty

        variables = {'release': current, 'replacement_release': nci_configuration.release(baseline['version'])}
        declared_new_groups = {plans.render(row['metadata']['termgroup_name'], variables) for row in source_plan['new_termgroups']}
        changes, flags = [], {}
        for row in group_rows:
            high, low = pair(row['termgroup_name']), pair(row['low_termgroup'])
            if high is not None and low is not None:
                changes.append((high, low))
                present = [role for role in ('default', 'project') if high in precedences[role]]
                if row['termgroup_name'] in declared_new_groups and present:
                    finding('NEW_RANK_PAIR_ALREADY_PRESENT', '/'.join(high), 'The declared new pair already occurs in: ' + ','.join(present))
                elif row['termgroup_name'] not in declared_new_groups:
                    for role in ('default', 'project'):
                        if role not in present:
                            finding('UNDECLARED_RANK_PAIR_ADDITION', role + ':' + '/'.join(high), 'A pair missing from this list needs a reviewed addition/reconciliation decision.')
            flags.setdefault(row['tty'], set()).add(tuple(row[key] == 'Y' for key in ('suppressible_flag', 'exclude_flag', 'norm_exclude_flag')))
        high_pairs = {high for high, _ in changes}
        for high, low in changes:
            if low not in precedences['default'] and (low not in high_pairs or low == high):
                finding('DEFAULT_PRECEDENCE_LOW_MISSING', '/'.join(high), 'Low pair is absent from default precedence and other incoming high pairs: ' + '/'.join(low))
        for role in ('default', 'project'):
            preview, unresolved = _insert_pairs(precedences[role], changes, role.upper())
            previews[role] = [{'source': source, 'tty': tty} for source, tty in preview]
            semantic.extend(unresolved)
        replacement_names = {source for source, _ in replacement}
        for role in ('default', 'project'):
            for source, tty in precedences[role]:
                if source in replacement_names and source in candidate_sources and (source, tty) not in high_pairs:
                    observations.append({'code': 'EXISTING_RANK_PAIR_RETAINED', 'identifier': role + ':' + source + '/' + tty,
                                         'reason': 'The insertion-only loader retains this existing pair even though the current metadata batch omits it.'})
        for tty, choices in flags.items():
            if len(choices) > 1:
                finding('CONFLICTING_GLOBAL_TTY_FLAGS', tty, 'The loader retains one global TTY definition; incoming rows disagree.')
            if tty in term_types:
                actual = tuple(term_types[tty][key] for key in ('suppressible', 'exclude', 'norm_exclude'))
                if any(choice != actual for choice in choices):
                    finding('EXISTING_TTY_FLAG_CHANGE_NOT_APPLIED', tty, 'The reviewed backend ignores input flag changes for existing generic term types.')
            elif any(pair[1] == tty for pairs in precedences.values() for pair in pairs):
                finding('GENERIC_TTY_METADATA_MISSING', tty, 'An existing rank pair lacks captured generic term-type metadata.')
        for exception in source_plan['historical_exceptions']:
            finding('HISTORICAL_EXCEPTION_REQUIRES_REVIEW', exception['identifier'], exception['kind'] + ': ' + exception['reason'])
    blockers = [
        ('DEPLOYMENT_IDENTITY_UNVERIFIED', 'No deployed build-to-code acceptance contract has been enrolled.'),
        ('PROJECT_BINDING_UNVERIFIED', 'The selected project and source-to-project binding require verified deployed evidence.'),
        ('EXPORTER_PROFILE_NOT_ACCEPTED', 'No real exporter acceptance profile exists; a client-supplied profile name cannot approve itself.'),
        ('HANDLER_SELECTION_UNVERIFIED', 'Captured handler names/bytes do not establish the active deployed response behavior.'),
        ('EXPORT_COMPLETENESS_UNVERIFIED', 'Row bindings prove selected values, not exhaustive export scope or pagination/index completeness.'),
        ('CONSISTENT_CAPTURE_UNVERIFIED', 'No supported coherent multi-export boundary has been validated.')]
    capture_findings = [{'code': code, 'identifier': 'capture', 'reason': reason} for code, reason in blockers]
    capture_findings += raw_findings
    semantic.sort(key=lambda row: (row['code'], row['identifier'], row['reason']))
    return {'schema_version': 2, 'profile': 'nci-backend-preflight-v2', 'status': 'BLOCKED_PENDING_CAPTURE_VERIFICATION',
            'semantic_status': 'NOT_EVALUATED' if raw_findings else 'FINDINGS_REQUIRE_REVIEW' if semantic else 'PASS',
            'production_eligible': False, 'execution_authorized': False,
            'source': config['source'], 'version': config['version'], 'replacement_baseline': dict(baseline),
            'capture_findings': capture_findings, 'semantic_findings': semantic,
            'observations': sorted(observations, key=lambda row: (row['code'], row['identifier'])), 'precedence_previews': previews,
            'bindings': {'configuration_sha256': v1.content_sha256(config), 'source_plan_sha256': v1.content_sha256(source_plan),
                         'metadata_model_sha256': v1.content_sha256(metadata_model), 'properties_sha256': v1.content_sha256(properties),
                         'installed_state_sha256': expected_state_sha256, 'schema_sha256': hashlib.sha256(schema_raw).hexdigest(),
                         'raw_exports': identities, 'verified_raw_rows': bindings,
                         'source_atom_id_key': project['source_atom_id_key'],
                         'preview_code': {Path(module.__file__).name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                                          for module in (nci_configuration, v1, plans)},
                         'analyzer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         'generated_files': [{'relative_path': item['relative_path'], 'sha256': item['sha256']} for item in generated['files']]},
            'limits': ['No database/API call, exporter implementation, production approval or historical lock mutation occurred.',
                       'Versioned metadata labels resolve to exact root-source/TTY rank pairs; the two lists remain separate.',
                       'The full-concept route is a code-supported candidate, not a validated complete deployed export.',
                       'Native publisher discovery, ID allocation, legacy QA and insertion remain separate gates.']}


def inputs_from_lock(lock):
    if lock.get('lock_sha256') != v1.content_sha256({key: value for key, value in lock.items() if key != 'lock_sha256'}):
        raise ValueError('Frozen common lock identity changed')
    if lock.get('artifact_type') != 'ncimeta-dev-replay-lock' or lock.get('schema_version') != 1:
        raise ValueError('An existing common dev replay lock is required')
    config = lock['configuration']
    if (config != lock['case']['configuration'] or lock['request']['source'] != 'NCI'
            or lock['request']['version'] != config['version'] or lock['request']['case_variant'] != 'source-plan'):
        raise ValueError('An unchanged reviewed NCIt source-plan lock is required')
    recipe = nci_configuration.from_lock(lock)
    if recipe['profile'] != plans.PROFILE:
        raise ValueError('Source-plan configuration-generation profile is required')
    plan = nci_configuration.artifact(lock['case']['artifacts'], config['inputs']['source_plan'], 'reviewed-nci-source-plan')
    model = plans.load(base64.b64decode(recipe['metadata_model']['data_b64']))
    properties = nci_configuration.properties(nci_configuration.render_template(config, recipe['template'], recipe['bindings']['identity_state']))
    return config, plan, model, properties


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--installed-state', type=Path, required=True)
    parser.add_argument('--installed-state-sha256', required=True)
    parser.add_argument('--raw-export-directory', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    lock, state = _load(args.lock.read_bytes()), _load(args.installed_state.read_bytes())
    root = args.raw_export_directory.resolve(strict=True)
    raw = {}
    for item in state.get('raw_exports', []):
        relative = _path(item['path']);path = root / relative
        if path.is_symlink() or not path.is_file() or path.resolve() != path:
            raise ValueError('Raw export or its ancestor is absent/linked')
        raw[item['path']] = path.read_bytes()
    result = analyze_backend(*inputs_from_lock(lock), state, args.installed_state_sha256, raw)
    data = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as handle:
            handle.write(data)
        args.output.chmod(0o444)
    else:
        print(data, end='')
    return 2  # All current v2 reports remain blocked pending real capture verification.


if __name__ == '__main__':
    raise SystemExit(main())
