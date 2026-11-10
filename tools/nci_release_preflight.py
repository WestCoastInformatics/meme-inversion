#!/usr/bin/env python3
"""Offline NCIt release-state preflight; never authorizes execution or insertion."""
import base64
from datetime import datetime
import hashlib
import json
import re

import nci_source_plan as plans

PROFILE = 'ncimeta-installed-state-v1'


def content_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Missing or unknown ' + label + ' fields')


def _identity(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise ValueError('Invalid ' + label + ' identity')
    return value


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _snapshot(configuration, state, expected_sha256):
    if not _sha(expected_sha256) or content_sha256(state) != expected_sha256:
        raise ValueError('Installed-state content differs from its selected identity')
    _keys(state, ('schema_version', 'profile', 'scope', 'capture', 'complete_for',
                  'sources', 'replacement_sources', 'source_roots', 'termgroups'), 'installed-state')
    if type(state['schema_version']) is not int or state['schema_version'] != 1 or state['profile'] != PROFILE:
        raise ValueError('Unsupported installed-state profile')
    _keys(state['scope'], ('source', 'replacement_baseline'), 'installed-state scope')
    if state['scope'] != {key: configuration[key] for key in ('source', 'replacement_baseline')}:
        raise ValueError('Installed-state scope differs from the selected replacement')
    _keys(state['capture'], ('snapshot_id', 'captured_at', 'evidence_sha256'), 'capture')
    _identity(state['capture']['snapshot_id'], 'snapshot')
    if not _sha(state['capture']['evidence_sha256']):
        raise ValueError('Capture evidence identity is required')
    try:
        captured = datetime.fromisoformat(state['capture']['captured_at'].replace('Z', '+00:00'))
        if captured.tzinfo is None or captured.utcoffset() is None:
            raise ValueError('Capture timestamp must include a timezone')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Invalid installed-state capture timestamp') from exc
    _keys(state['complete_for'], ('sources', 'source_roots', 'termgroups'), 'coverage')
    if any(value is not True for value in state['complete_for'].values()):
        raise ValueError('Complete source, source-root and termgroup inventories are required')
    if not all(isinstance(state[key], list) for key in ('sources', 'replacement_sources', 'source_roots', 'termgroups')):
        raise ValueError('Explicit inventory arrays are required')
    sources, versions, roots, root_ids, groups = {}, {}, {}, set(), set()
    for row in state['sources']:
        _keys(row, ('source', 'version', 'source_family'), 'installed source')
        source = _identity(row['source'], 'source')
        version = _identity(row['version'], 'versioned source')
        _identity(row['source_family'], 'source family')
        if (row['source_family'] == 'NCI'
                and not re.fullmatch(re.escape(source) + r'_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', version)) or version in versions:
            raise ValueError('Duplicate or inconsistent installed source')
        if source in sources and sources[source][0]['source_family'] != row['source_family']:
            raise ValueError('Installed source versions disagree on source family')
        sources.setdefault(source, []).append(row)
        versions[version] = source
    replacement_sources = {}
    for version in state['replacement_sources']:
        _identity(version, 'replacement source')
        if version not in versions or versions[version] in replacement_sources:
            raise ValueError('Unknown or duplicate replacement source identity')
        source = versions[version]
        if sources[source][0]['source_family'] != 'NCI':
            raise ValueError('Replacement source set must describe the NCI family')
        replacement_sources[source] = version
    if replacement_sources.get(configuration['source']) != configuration['replacement_baseline']['version']:
        raise ValueError('Installed primary source does not match the explicit replacement baseline')
    for row in state['source_roots']:
        _keys(row, ('source', 'root_atom_id'), 'installed source root')
        source = _identity(row['source'], 'source-root source')
        if (source not in sources or source in roots or type(row['root_atom_id']) is not int
                or row['root_atom_id'] <= 0 or row['root_atom_id'] in root_ids):
            raise ValueError('Duplicate, unknown or invalid installed source root')
        roots[source] = row['root_atom_id']
        root_ids.add(row['root_atom_id'])
    for name in state['termgroups']:
        if not isinstance(name, str) or name.count('/') != 1:
            raise ValueError('Invalid installed termgroup')
        version, tty = name.rsplit('/', 1)
        _identity(tty, 'term type')
        if version not in versions or name in groups:
            raise ValueError('Duplicate or unknown installed termgroup')
        groups.add(name)
    return sources, versions, roots, groups, replacement_sources


def _rows(generated, path, fields):
    matches = [item for item in generated['files'] if item['relative_path'] == path]
    if len(matches) != 1:
        raise ValueError('Generated metadata file is missing or ambiguous')
    raw = base64.b64decode(matches[0]['data_b64'], validate=True)
    if plans.sha(raw) != matches[0]['sha256']:
        raise ValueError('Generated metadata content identity differs')
    result = []
    for line in raw.decode().splitlines():
        cells = line.split('|')
        if len(cells) != len(fields) + 1 or cells[-1] != '':
            raise ValueError('Unexpected generated metadata field count')
        result.append(dict(zip(fields, cells[:-1])))
    return result


def analyze(configuration, source_plan, metadata_model, properties,
            installed_state, expected_state_sha256):
    """Compare generated NCIt metadata against explicitly supplied frozen state.

    The snapshot's hash is checked, not the truth of a database export. A caller
    must review/retain its capture evidence. The snapshot is NOT substituted for
    the historical profile's representation catalog or saved hierarchy root.
    """
    if configuration.get('source') != 'NCI':
        raise ValueError('This preflight supports only NCIt')
    baseline = configuration.get('replacement_baseline')
    if (not isinstance(baseline, dict) or set(baseline) != {'source', 'version'}
            or baseline['source'] != 'NCI'
            or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', str(baseline.get('version')))
            or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', str(configuration.get('version')))
            or baseline['version'] >= configuration['version']):
        raise ValueError('An explicit earlier NCIt replacement baseline is required')
    sources, versions, roots, groups, replacement_sources = _snapshot(configuration, installed_state, expected_state_sha256)
    generated = plans.generate(configuration, source_plan, metadata_model, properties)
    source_rows = _rows(generated, 'src/sources.src', plans.SOURCE_FIELDS)
    group_rows = _rows(generated, 'src/termgroups.src', plans.TERMGROUP_FIELDS)
    candidate_sources = {row['stripped_source'] for row in source_rows}
    candidate_versions = {row['source_name']: row['stripped_source'] for row in source_rows}
    candidate_groups = {row['termgroup_name'] for row in group_rows}
    new_sources = set(generated['new_subsources'])
    variables = {'release': configuration['version'].removeprefix('NCI_'),
                 'replacement_release': baseline['version'].removeprefix('NCI_')}
    new_groups = {plans.render(row['metadata']['termgroup_name'], variables)
                  for row in source_plan['new_termgroups']}
    findings = []

    def finding(code, identity, reason):
        findings.append({'code': code, 'identifier': identity, 'severity': 'blocking', 'reason': reason})

    for row in source_rows:
        source = row['stripped_source']
        if row['source_name'] in versions:
            finding('CURRENT_VERSION_ALREADY_INSTALLED', row['source_name'],
                    'The proposed versioned source already exists in the supplied installed metadata.')
        if source in new_sources:
            if source in sources or source in roots:
                finding('NEW_SOURCE_ALREADY_INSTALLED', source,
                        'A NEW decision conflicts with installed source metadata or a source root.')
        else:
            if source not in sources:
                finding('UNDECLARED_NEW_SOURCE', source,
                        'Generated source metadata has no installed source and no reviewed NEW decision.')
            if source not in roots:
                finding('SOURCE_ROOT_MISSING', source,
                        'An established source has no captured installed source root; catalog membership is insufficient.')
        if row['low_source'] not in candidate_versions and row['low_source'] not in versions:
            finding('SOURCE_RANK_TARGET_MISSING', row['source_name'],
                    'low_source is absent from the generated batch and frozen installed source inventory: ' + row['low_source'])

    installed_pairs = {(versions[name.rsplit('/', 1)[0]], name.rsplit('/', 1)[1]) for name in groups}
    candidate_pairs = set()
    for row in group_rows:
        name = row['termgroup_name']
        version, tty = name.rsplit('/', 1)
        pair = (candidate_versions[version], tty)
        candidate_pairs.add(pair)
        if name in new_groups and pair in installed_pairs:
            finding('NEW_TERMGROUP_ALREADY_INSTALLED', name,
                    'A NEW termgroup decision conflicts with an installed source/term-type identity.')
        elif name not in new_groups and pair not in installed_pairs:
            finding('UNDECLARED_NEW_TERMGROUP', name,
                    'Generated termgroup metadata has no installed identity and no reviewed NEW decision.')
        if row['low_termgroup'] not in candidate_groups and row['low_termgroup'] not in groups:
            finding('TERMGROUP_RANK_TARGET_MISSING', name,
                    'low_termgroup is absent from the generated batch and frozen installed termgroup inventory: ' + row['low_termgroup'])

    for source in replacement_sources:
        if source not in candidate_sources:
            finding('SOURCE_REMOVAL_UNREVIEWED', source,
                    'An installed NCI-family source is absent from generated metadata; removal policy is not implemented.')
    replacement_pairs = {(versions[name.rsplit('/', 1)[0]], name.rsplit('/', 1)[1])
                         for name in groups if name.rsplit('/', 1)[0] in replacement_sources.values()}
    for source, tty in replacement_pairs:
        if source in candidate_sources and (source, tty) not in candidate_pairs:
            finding('TERMGROUP_REMOVAL_UNREVIEWED', source + '/' + tty,
                    'An installed termgroup is absent from generated metadata; removal policy is not implemented.')
    for exception in source_plan['historical_exceptions']:
        finding('HISTORICAL_EXCEPTION_REQUIRES_REVIEW', exception['identifier'],
                exception['kind'] + ': ' + exception['reason'])
    findings.sort(key=lambda item: (item['code'], item['identifier'], item['reason']))
    return {'schema_version': 1, 'profile': 'nci-release-preflight-v1',
            'status': 'BLOCKED' if findings else 'PASS_RELEASE_PREFLIGHT',
            'production_eligible': False, 'execution_authorized': False,
            'source': configuration['source'], 'version': configuration['version'],
            'replacement_baseline': dict(baseline), 'findings': findings,
            'bindings': {'configuration_sha256': content_sha256(configuration),
                         'source_plan_sha256': content_sha256(source_plan),
                         'metadata_model_sha256': content_sha256(metadata_model),
                         'properties_sha256': content_sha256(properties),
                         'installed_state_sha256': expected_state_sha256,
                         'capture': dict(installed_state['capture']),
                         'generated_files': [{'relative_path': item['relative_path'], 'sha256': item['sha256']}
                                             for item in generated['files']]},
            'decisions': {'new_subsources': sorted(new_sources), 'new_termgroups': sorted(new_groups)},
            'coverage': {'installed_sources': len(versions), 'replacement_sources': len(replacement_sources), 'installed_source_roots': len(roots),
                         'installed_termgroups': len(groups), 'generated_sources': len(source_rows),
                         'generated_termgroups': len(group_rows)},
            'limits': ['Supplied snapshot capture evidence requires review; no live database was queried.',
                       'Source roots are SRC source identities, not the saved hierarchy root.',
                       'Publisher discovery, production ID allocation, legacy QA and insertion remain separate gates.']}
