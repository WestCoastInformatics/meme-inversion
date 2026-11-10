#!/usr/bin/env python3
"""Preview SNOMED compatibility settings from a common frozen configuration.

This offline adapter renders configuration only.  It does not enable a new
execution case, acquire metadata, allocate identifiers, or assert insertion
readiness.  The shared preview frontend verifies the complete common lock.
"""
import base64
import copy
import datetime
import hashlib
import json
from pathlib import PurePosixPath
import re

PROFILE = 'snomed-properties-preview-v1'
CAPTURED_VERSION = 'SNOMEDCT_US_2026_09_01'
CAPTURED_ENGINE = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
TEMPLATE_PATH = 'sources/' + CAPTURED_VERSION + '/etc/sct.cfg'
TEMPLATE_SHA256 = '56b214ee51d698f716a1701ca387543ac161baf8f1618c9a5f51f044147465b3'
RF2_FILES = {
    'CONCEPTS': 'Terminology/sct2_Concept_Snapshot',
    'DESCRIPTIONS': 'Terminology/sct2_Description_Snapshot-en',
    'RELATIONS': 'Terminology/sct2_Relationship_Snapshot',
    'CONCRETERELS': 'Terminology/sct2_RelationshipConcreteValues_Snapshot',
    'DEFINITIONS': 'Terminology/sct2_TextDefinition_Snapshot-en',
    'REFSETS': 'Refset/Metadata/der2_cciRefset_RefsetDescriptorSnapshot',
    'DESCRFORMAT': 'Refset/Metadata/der2_ciRefset_DescriptionTypeSnapshot',
    'MODULEDEP': 'Refset/Metadata/der2_ssRefset_ModuleDependencySnapshot',
    'LANGUAGESETS': 'Refset/Language/der2_cRefset_LanguageSnapshot-en',
    'SIMPLEMAPS': 'Refset/Map/der2_sRefset_SimpleMapSnapshot',
    'EXTENDEDMAPS': 'Refset/Map/der2_iisssccRefset_ExtendedMapSnapshot',
    'ATTRIBUTES': 'Refset/Content/der2_cRefset_AttributeValueSnapshot',
    'SUBSETS': 'Refset/Content/der2_Refset_SimpleSnapshot',
    'ASSOCIATIONS': 'Refset/Content/der2_cRefset_AssociationSnapshot',
}
TARGET_FILES = {'File.INP.ICD10META': 'etc/icd10.inmeta',
                'File.INP.ICD10CMMETA': 'etc/icd10cm.inmeta'}
UNUSED_INPUT_KEYS = ('File.INP.STATEDRELS', 'File.INP.OldSubset', 'File.INP.URCid2Did')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(artifacts, reference, role):
    item = artifacts.get(reference)
    if (not isinstance(item, dict) or item.get('role') != role or
            reference != 'sha256:' + digest(item.get('value'))):
        raise ValueError('Missing or changed ' + role + ' artifact')
    return item['value']


def release(version):
    if not isinstance(version, str) or not re.fullmatch(r'SNOMEDCT_US_[0-9]{4}_[0-9]{2}_[0-9]{2}', version):
        raise ValueError('Invalid SNOMEDCT_US version')
    return datetime.datetime.strptime(version.removeprefix('SNOMEDCT_US_'), '%Y_%m_%d').date()


def properties(raw, expand=False):
    """Read this reviewed Java-properties subset, including continuation lines."""
    result, pending = {}, ''
    for line in raw.decode('utf-8').splitlines():
        if not pending and (not line.strip() or line.lstrip().startswith(('#', '!'))):
            continue
        line = pending + line.lstrip() if pending else line
        if line.endswith('\\'):
            pending = line[:-1]
            continue
        pending = ''
        if '=' not in line:
            raise ValueError('Malformed compatibility property')
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or key in result:
            raise ValueError('Duplicate or empty compatibility property')
        result[key] = value
    if pending:
        raise ValueError('Unterminated compatibility property')
    if expand:
        resolved = {}

        def resolve(key, seen):
            if key in seen or key not in result:
                raise ValueError('Cyclic or missing compatibility substitution: ' + key)
            if key not in resolved:
                resolved[key] = re.sub(r'<([^<>]+)>', lambda m: resolve(m[1], seen | {key}), result[key])
            return resolved[key]

        for key in result:
            resolve(key, set())
        return resolved
    return result


def checked_template(template):
    if (template.get('repository_path') != TEMPLATE_PATH or
            template.get('sha256') != TEMPLATE_SHA256):
        raise ValueError('Unreviewed SNOMED configuration template')
    raw = base64.b64decode(template['data_b64'], validate=True)
    if sha(raw) != template['sha256']:
        raise ValueError('SNOMED template payload changed')
    properties(raw, expand=True)
    return raw


def manifest(items, expected, role=None):
    if not isinstance(items, list) or len(items) != len(expected):
        raise ValueError('Incomplete or additional declared input files')
    found, paths = {}, set()
    for item in items:
        path = item['path']
        relative = PurePosixPath(path)
        if (relative.is_absolute() or '..' in relative.parts or str(relative) != path or
                path not in expected or path in paths or
                not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or
                type(item.get('size')) is not int or item['size'] < 0 or
                type(item.get('newline_count')) is not int or item['newline_count'] < 0):
            raise ValueError('Unsafe, duplicate, changed or unexpected input identity')
        key = expected[path]
        if key is not None:
            if (item.get('legacy_key') != key or item.get('required') is not True or
                    item.get('present') is not True or item.get('role') != role):
                raise ValueError('Input role does not agree with the declared path')
            if key in found:
                raise ValueError('Duplicate input role')
            found[key] = copy.deepcopy(item)
        paths.add(path)
    if paths != set(expected):
        raise ValueError('Missing declared input identity')
    return found


def generate(config, artifacts, template):
    """Return an immutable-file recipe; consume the existing common field names."""
    if (config.get('schema_version') != 1 or config.get('source') != 'SNOMEDCT_US' or
            config.get('source_options') != {'rf2_view': 'Snapshot'} or
            config['inputs']['source_data_stage'] != 'publisher' or
            config.get('output_stage') != 'inversion-src'):
        raise ValueError('Only the reviewed SNOMED publisher Snapshot core profile is supported')
    current = release(config['version'])
    prior = config['replacement_baseline']
    if not isinstance(prior, dict) or set(prior) != {'source', 'version'} or prior['source'] != config['source'] or release(prior['version']) >= current:
        raise ValueError('An explicit earlier SNOMED replacement baseline is required')
    if config['comparison_baseline'] is not None or config['publisher_history'] != []:
        raise ValueError('This core preview has no prior comparison or publisher-history stage')
    if config['inputs']['identity_state'] is not None:
        raise ValueError('This reviewed core does not consume a prior identity-map bundle')
    if config['engine_ref'] != CAPTURED_ENGINE:
        raise ValueError('The source engine has no reviewed SNOMED configuration-preview policy')
    policy = artifact(artifacts, config['policy_ref'], 'captured-representation-policy')
    if policy.get('engine_ref') != config['engine_ref']:
        raise ValueError('Representation policy and source engine differ')
    plan = artifact(artifacts, config['inputs']['source_plan'], 'reviewed-historical-transition')
    if any(plan[key] != config[key] for key in ('replacement_baseline', 'comparison_baseline', 'publisher_history')) or plan.get('no_additional_history_required') is not True:
        raise ValueError('Reviewed transition differs from the common configuration')
    raw = checked_template(template)
    original = properties(raw)
    bounds = config['source_atom_ids']
    proof = artifact(artifacts, bounds['provenance_ref'], 'isolated-historical-ID-range')
    expected_proof = {'kind': 'captured-sct.cfg', 'start': 'SaidStart', 'end': 'SaidEnd',
                      'production_reservation': False}
    if (proof != expected_proof or any(type(bounds[key]) is not int or bounds[key] <= 0 for key in ('start', 'end')) or
            bounds['start'] > bounds['end'] or
            (bounds['start'], bounds['end']) != (int(original['SaidStart']), int(original['SaidEnd'])) or
            bounds.get('bound_kind') not in (None, 'reserved-historical-range')):
        raise ValueError('ID bounds must match the captured historical configuration evidence')
    if len(config['inputs']['source_data']) != 1:
        raise ValueError('One complete native Snapshot bundle is required')
    native = artifact(artifacts, config['inputs']['source_data'][0], 'source-data')
    metadata = artifact(artifacts, config['inputs']['reference_ncimeta'], 'preserved-reference-metadata')
    engnum = current.strftime('%Y%m%d')
    package = ('orig/fromprovider/SnomedCT_ManagedServiceUS_PRODUCTION_US1000124_' +
               engnum + 'T120000Z/Snapshot')
    expected_native = {config['version'] + '/' + package + '/' + value + '_US1000124_' + engnum + '.txt':
                       'File.INP.' + key for key, value in RF2_FILES.items()}
    native_by_key = manifest(native, expected_native, 'archived-publisher-RF2-Snapshot')
    expected_metadata = {config['version'] + '/src/' + name: None for name in ('sources.src', 'termgroups.src')}
    expected_metadata.update({config['version'] + '/' + path: key for key, path in TARGET_FILES.items()})
    # Metadata rows have no legacy_key; inventory rows carry explicit conversion roles.
    if not isinstance(metadata, list):
        raise ValueError('Metadata must be a declared file inventory')
    for item in metadata:
        if '/src/' in item['path'] and ('legacy_key' in item or item.get('role') == 'official-generated-output-reference'):
            raise ValueError('Source metadata is not an official generated core-output input')
    target_by_key = manifest(metadata, expected_metadata, 'target-terminology-inventory')
    replacements = {'VSAB': config['version'], 'VSABOLD': prior['version'],
                    'Release': 'Snapshot', 'EngNum': engnum,
                    'EngNumOld': release(prior['version']).strftime('%Y%m%d'),
                    'SaidStart': str(bounds['start']), 'SaidEnd': str(bounds['end']),
                    CAPTURED_VERSION + '.VSY.0': 'SNOMED Clinical Terms US Edition, ' +
                    ('January February March April May June July August September October November December'.split()[current.month-1]) +
                    ' ' + str(current.day) + ', ' + str(current.year)}
    lines, counts = [], {key: 0 for key in replacements}
    for line in raw.decode().splitlines(keepends=True):
        match = re.fullmatch(r'([^#\r\n=]+?)(\s*=\s*)([^\r\n]*)(\r?\n)?', line)
        key = match[1].strip() if match else None
        if key in replacements:
            counts[key] += 1
            rendered_key = config['version'] + '.VSY.0' if key.endswith('.VSY.0') else match[1]
            line = rendered_key + match[2] + replacements[key] + (match[4] or '')
        lines.append(line)
    if set(counts.values()) != {1}:
        raise ValueError('Template is missing or repeats a common-derived parameter')
    rendered = ''.join(lines).encode()
    effective = properties(rendered, expand=True)
    for key, item in {**native_by_key, **target_by_key}.items():
        if effective[key] != '../' + str(PurePosixPath(item['path']).relative_to(config['version'])):
            raise ValueError('Generated compatibility input path differs from its pinned artifact')
    if effective['Merge.SB.sgQual2'] != prior['version'] or effective['RSAB'] != config['source']:
        raise ValueError('Generated source/replacement semantics differ')
    return {'profile': PROFILE, 'source': config['source'], 'scope': 'offline-configuration-preview',
            'execution_enabled': False, 'production_eligible': False,
            'template': copy.deepcopy(template),
            'files': [{'relative_path': 'etc/sct.cfg', 'mode': '0o444', 'sha256': sha(rendered),
                       'data_b64': base64.b64encode(rendered).decode()}],
            'bindings': {'source': config['source'], 'version': config['version'],
                         'engine_ref': config['engine_ref'], 'policy_ref': config['policy_ref'],
                         'replacement_baseline': copy.deepcopy(prior),
                         'comparison_baseline': None, 'publisher_history': [],
                         'source_atom_ids': copy.deepcopy(bounds), 'identity_state': None,
                         'native_inputs': copy.deepcopy(native), 'metadata_inputs': copy.deepcopy(metadata),
                         'derived_properties': {config['version'] + '.VSY.0' if k.endswith('.VSY.0') else k: v for k, v in replacements.items()},
                         'unused_legacy_input_keys': list(UNUSED_INPUT_KEYS),
                         'absent_optional_input_keys': ['File.INP.COMPLEXMAPS']},
            'limitations': ['Only the reviewed US1000124 ManagedService package and T120000Z naming convention are supported',
                            'Conditional ComplexMap input is absent in this case; newly present input requires a reviewed dependency change'],
            'remaining_gates': ['Frozen metadata row contents and installed-state validation',
                                'Reviewed generated-settings execution case and full dev replay',
                                'New-release allocation, legacy QA, insertion and production approval']}


def preview_from_lock(lock):
    """Render from the frozen cfg payload; never read working-tree/server files."""
    if (lock.get('schema_version') != 1 or lock.get('artifact_type') != 'ncimeta-dev-replay-lock' or
            lock.get('lock_sha256') != digest({k: v for k, v in lock.items() if k != 'lock_sha256'})):
        raise ValueError('Unsupported or changed common lock')
    case, config = lock['case'], lock['configuration']
    if (lock['case_sha256'] != digest(case) or config != case['configuration'] or
            case.get('adapter') != 'snomed-sep2026-v1' or
            any(lock['request'][key] != config[key] for key in ('source', 'version', 'engine_ref')) or
            config['version'] != CAPTURED_VERSION or config['engine_ref'] not in case['reviewed_engine_refs']):
        raise ValueError('Frozen configuration differs from the reviewed SNOMED case')
    expected = {item['relative_path']: item for item in case['source_files']}
    found = {}
    for item in lock['code_files']:
        path = item['relative_path']
        if (path in found or path not in expected or item.get('kind') != 'file' or
                item.get('repository_path') != 'sources/' + CAPTURED_VERSION + '/' + path or
                any(item.get(key) != expected[path].get(key) for key in ('mode', 'sha256', 'kind')) or
                sha(base64.b64decode(item['data_b64'], validate=True)) != item['sha256']):
            raise ValueError('Frozen source/configuration payload differs from its reviewed identity')
        found[path] = item
    if set(found) != set(expected) or 'etc/sct.cfg' not in found:
        raise ValueError('Incomplete frozen source/configuration inventory')
    template = {key: found['etc/sct.cfg'][key] for key in ('repository_path', 'sha256', 'data_b64')}
    recipe = generate(config, case['artifacts'], template)
    legacy = case['legacy_case']['contract']
    if (legacy['replacement_baseline'] != config['replacement_baseline'] or
            {x['path']: x['sha256'] for x in recipe['bindings']['native_inputs'] + recipe['bindings']['metadata_inputs']} !=
            {x['path']: x['sha256'] for x in legacy['conversion_inputs'] if x['required']} |
            {x['path']: x['sha256'] for x in legacy['archived_metadata_inputs']}):
        raise ValueError('Generated settings differ from the declared legacy input/baseline contract')
    return recipe
