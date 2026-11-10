#!/usr/bin/env python3
"""Preview MTH legacy specs from a frozen common historical configuration.

This module never runs legacy programs or prepares publisher/subset inputs.  Its
bounded profile renders the accepted 2026AA final-range prepared-input case.
"""
import base64
import copy
import hashlib
import json
from pathlib import PurePosixPath
import re

PROFILE = 'mth-prepared-spec-preview-v1'
EXECUTION_PROFILE = 'mth-prepared-spec-v1'
VERSION = 'MTH_2026AA'
PREVIOUS = 'MTH_2025AB'
ENGINES = {'3b125edc1d29f7c7a91673da2a8d752bb0adff44',
           'b2611abcf929981628bb2e5051afb450b8525b70'}
RRF_NAMES = {'MRCONSO.RRF', 'MRREL.RRF', 'MRSAT.RRF', 'MRSTY.RRF',
             'MRDEF.RRF', 'MRCUI.RRF', 'MRCXT.RRF', 'MRSAB.RRF',
             'MRRANK.RRF', 'MRAUI.RRF', 'MRDOC.RRF'}
METADATA = {'src/sources.src', 'src/termgroups.src', 'src/vsab.updates',
            'src/sabs_updated_umls', 'src/rsabs-updated.umls',
            'src/vcodes_updated', 'ncimid.sources', 'ncimid.termgroups'}
TEMPLATE_NAMES = {'inv1.spec', 'inv2.spec', 'inv3.spec', 'src/inv1.spec',
                  'src/inv2.spec', 'src/inv3.spec', 'range3.spec',
                  'ncisources.spec', 'sab.vsab.map', 'src_data', 'invert1.s',
                  'old', 'prev'}
DISPOSITIONS = {'KEEP', 'UPDATE', 'NEW', 'EXCLUDE', 'REMOVE', 'SPECIAL'}
TOKEN = re.compile(r'[A-Za-z0-9_.-]+')
SHA = re.compile(r'[0-9a-f]{64}')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True).encode()).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(artifacts, reference, role):
    item = artifacts.get(reference)
    if (not isinstance(item, dict) or set(item) != {'role', 'value'} or
            item['role'] != role or reference != 'sha256:' + digest(item['value'])):
        raise ValueError('Missing or changed ' + role + ' artifact')
    return item['value']


def raw_file(item, name):
    if (item.get('kind') != 'file' or item.get('relative_path') != name or
            item.get('repository_path') != 'sources/' + VERSION + '/' + name):
        raise ValueError('Unexpected frozen MTH template: ' + name)
    raw = base64.b64decode(item['data_b64'], validate=True)
    if sha(raw) != item.get('sha256') or (item.get('bytes') is not None and item['bytes'] != len(raw)):
        raise ValueError('Frozen MTH template bytes changed: ' + name)
    raw.decode('utf-8')
    if b'\r' in raw or b'\0' in raw:
        raise ValueError('Unsupported control character in ' + name)
    return raw


def source_decisions(raw):
    """Expose the saved source decisions; never guess a disposition."""
    rows, seen, active = [], set(), set()
    for line in raw.decode().splitlines():
        fields = line.split('|')
        if len(fields) != 4:
            raise ValueError('Expected four ncisources.spec fields')
        source, version, disposition, note = fields
        if not TOKEN.fullmatch(source) or not TOKEN.fullmatch(version) or disposition not in DISPOSITIONS:
            raise ValueError('Invalid or unresolved MTH source disposition')
        if (source, version) in seen:
            raise ValueError('Duplicate MTH source/version decision')
        seen.add((source, version))
        excluded = []
        if note:
            prefix = 'exclude termgroups: '
            if not note.startswith(prefix):
                raise ValueError('Unreviewed MTH source-decision qualifier')
            excluded = [x.strip() for x in note[len(prefix):].split(',')]
            if not excluded or len(set(excluded)) != len(excluded) or any(not TOKEN.fullmatch(x) for x in excluded):
                raise ValueError('Invalid excluded MTH termgroups')
        if disposition in {'KEEP', 'UPDATE', 'NEW'}:
            if source in active:
                raise ValueError('Multiple active versions for one MTH source')
            active.add(source)
        rows.append({'source': source, 'version': version,
                     'disposition': disposition, 'excluded_termgroups': excluded})
    if not rows or [row for row in rows if row['source'] == 'MTH'] != [
            {'source': 'MTH', 'version': VERSION, 'disposition': 'UPDATE',
             'excluded_termgroups': ['CV', 'XM']}]:
        raise ValueError('The captured MTH source decision is missing or changed')
    return rows


def vsab_mappings(raw):
    lines = raw.decode().splitlines()
    if not lines or lines[0] != ' RSAB | UMLS VSAB | NCI VSAB':
        raise ValueError('Missing captured VSAB mapping header')
    rows, seen = [], set()
    for line in lines[1:]:
        fields = line.split('|')
        if len(fields) != 3 or any(not TOKEN.fullmatch(x) for x in fields):
            raise ValueError('Malformed saved MTH VSAB mapping')
        source, native, target = fields
        if source in seen:
            raise ValueError('Duplicate saved MTH VSAB mapping')
        seen.add(source)
        rows.append({'source': source, 'publisher_version': native,
                     'version': native if target == 'same' else target})
    if [row for row in rows if row['source'] == 'MTH'] != [
            {'source': 'MTH', 'publisher_version': 'MTH', 'version': VERSION}]:
        raise ValueError('Missing or changed MTH VSAB mapping')
    return rows


def release_settings(raw):
    result = {}
    for key in ('rel', 'prevrel'):
        matches = re.findall(r'^set ' + key + r'=([A-Za-z0-9]+)$', raw.decode(), re.MULTILINE)
        if len(matches) != 1:
            raise ValueError('Ambiguous captured MTH ' + key)
        result[key] = matches[0]
    return result


def render_spec(raw, name, version, previous):
    text = raw.decode()
    source_dir = 'SourceDir|/local/content/MEME/MEME5/inv/sources/MTHrelease'
    if text.splitlines().count(source_dir) != 1:
        raise ValueError('Unknown MTH SourceDir template in ' + name)
    text = text.replace(source_dir + '\n', source_dir.removesuffix('MTHrelease') + version + '/src\n')
    if name in {'inv2.spec', 'inv3.spec'}:
        line = 'DefineConst|MTHSAB|MTHrelease'
        if text.splitlines().count(line) != 1:
            raise ValueError('Unknown MTHSAB template in ' + name)
        text = text.replace(line + '\n', 'DefineConst|MTHSAB|' + version + '\n')
    if name == 'inv3.spec':
        # All three bequeathal predicates use the explicitly frozen transition.
        if text.count("(<VER> eq 'prevrel1')") != 3 or text.count('prevrel1') != 3:
            raise ValueError('Unknown MTH bequeathal-history template')
        text = text.replace("(<VER> eq 'prevrel1')", "(<VER> eq '" + previous.removeprefix('MTH_') + "')")
    if 'MTHrelease' in text or 'prevrel1' in text:
        raise ValueError('Unresolved MTH template parameter')
    return text.encode()


def file_record(name, raw):
    return {'relative_path': name, 'mode': '0o444', 'sha256': sha(raw),
            'data_b64': base64.b64encode(raw).decode()}


def generate(config, artifacts, templates):
    """Return a deterministic, non-executable preview from verified saved inputs.

    ``templates`` is a map of TEMPLATE_NAMES to frozen code-file descriptors.
    Historical config translation is deliberately narrower than release creation.
    """
    if (config.get('schema_version') != 1 or config.get('source') != 'MTH' or
            config.get('version') != VERSION or config.get('engine_ref') not in ENGINES or
            config.get('source_options') != {} or config.get('output_stage') != 'inversion-src'):
        raise ValueError('Unsupported MTH configuration/profile')
    if config.get('replacement_baseline') != {'source': 'MTH', 'version': PREVIOUS}:
        raise ValueError('Only the reviewed explicit MTH replacement transition is supported')
    if config.get('comparison_baseline') is not None or config.get('publisher_history') != []:
        raise ValueError('This prepared historical case has no additional comparison/history stage')
    inputs = config['inputs']
    if inputs.get('source_data_stage') != 'prepared' or len(inputs.get('source_data', [])) != 1:
        raise ValueError('One complete preserved prepared MTH bundle is required')
    if set(templates) != TEMPLATE_NAMES:
        raise ValueError('Incomplete or unexpected frozen MTH template set')
    raw = {name: raw_file(templates[name], name) for name in sorted(TEMPLATE_NAMES - {'old', 'prev'})}
    for name in ('old', 'prev'):
        item = templates[name]
        if (item.get('kind') != 'symlink' or item.get('relative_path') != name or
                item.get('target') != '../' + PREVIOUS):
            raise ValueError('Captured MTH ' + name + ' identity differs')
    settings = release_settings(raw['invert1.s'])
    if settings != {'rel': '2026AA', 'prevrel': '2025AB'}:
        raise ValueError('Captured publisher transition differs; new transitions need review')
    policy = artifact(artifacts, config['policy_ref'], 'captured-representation-policy')
    if policy.get('engine_ref') != config['engine_ref']:
        raise ValueError('MTH policy/engine differs')
    plan = artifact(artifacts, inputs['source_plan'], 'reviewed-historical-transition')
    for name in ('replacement_baseline', 'comparison_baseline', 'publisher_history'):
        if plan.get(name) != config[name]:
            raise ValueError('MTH source plan differs: ' + name)
    if plan.get('no_additional_history_required') is not True:
        raise ValueError('Prepared MTH history closure is not declared')
    evidence = artifact(artifacts, config['source_atom_ids']['provenance_ref'], 'isolated-historical-ID-range')
    if evidence != {'kind': 'captured-range3.spec-and-SRCbuilder-offset',
                    'reserved_SRC_atoms': 2, 'production_reservation': False}:
        raise ValueError('Unknown MTH historical range evidence')
    bounds = config['source_atom_ids']
    if (set(bounds) - {'start', 'end', 'provenance_ref', 'bound_kind'} or
            bounds.get('bound_kind') not in (None, 'reserved-historical-range') or
            any(type(bounds.get(key)) is not int or bounds[key] <= 0 for key in ('start', 'end')) or
            bounds['start'] + 2 > bounds['end']):
        raise ValueError('Invalid complete MTH final ID bounds')
    rendered_range = ('SourceAtomIdBase|' + str(bounds['start'] + 2) + '\n' +
                      'SourceAtomIdLimit|' + str(bounds['end']) + '\n').encode()
    if rendered_range != raw['range3.spec']:
        raise ValueError('MTH range differs from captured numeric allocation evidence')
    native = artifact(artifacts, inputs['source_data'][0], 'source-data')
    if any(native.get(key) != value for key, value in
           [('source', 'MTH'), ('version', VERSION), ('umls_release', '2026AA')]):
        raise ValueError('Prepared MTH input release identity differs')
    files = native.get('files', [])
    native_paths = set()
    for item in files:
        path = PurePosixPath(item['relative_path'])
        identity = item['identity']
        if (path.as_posix() != 'subset3/METASUBSET/' + path.name or path.name not in RRF_NAMES or
                path.name in native_paths or not SHA.fullmatch(identity.get('sha256', '')) or
                type(identity.get('bytes')) is not int or identity['bytes'] <= 0 or
                type(identity.get('newline_count')) is not int or identity['newline_count'] <= 0):
            raise ValueError('Malformed or ambiguous MTH prepared input')
        native_paths.add(path.name)
    if native_paths != RRF_NAMES or len(files) != len(RRF_NAMES):
        raise ValueError('All eleven preserved MTH prepared input roles are required')
    if native.get('request', {}).get('umls_release') != '2026AA':
        raise ValueError('Prepared input acquisition receipt release differs')
    metadata = artifact(artifacts, inputs['reference_ncimeta'], 'preserved-reference-metadata')
    if (len(metadata) != len(METADATA) or {item['relative_path'] for item in metadata} != METADATA or
            any(not SHA.fullmatch(item.get('sha256', '')) for item in metadata)):
        raise ValueError('Eight distinct saved MTH metadata roles are required')
    identity = artifact(artifacts, inputs['identity_state'], 'persistent-identity-state')
    prior_map = identity.get('prior_map', {})
    if (prior_map.get('path') != PREVIOUS + '/src/cui_said_map' or prior_map.get('kind') != 'file' or
            not SHA.fullmatch(prior_map.get('sha256', '')) or
            type(prior_map.get('newline_count')) is not int or prior_map['newline_count'] <= 0 or
            not SHA.fullmatch(identity.get('prior_archive_sha256', '')) or
            identity.get('prior_archive_path') != '/local/content/MEME/MEME5/inv/sources/' + PREVIOUS + '.tgz'):
        raise ValueError('Missing or mismatched replacement CUI identity state')
    decisions = source_decisions(raw['ncisources.spec'])
    mappings = vsab_mappings(raw['sab.vsab.map'])
    if raw['src_data'] != b'MTH_2026AA|R|SSN|UMLS Metathesaurus\n':
        raise ValueError('Saved MTH SRC root declaration differs')
    generated = [file_record('range3.spec', rendered_range)]
    for name in ('inv1.spec', 'inv2.spec', 'inv3.spec'):
        rendered = render_spec(raw[name], name, VERSION, 'MTH_' + settings['prevrel'])
        if rendered != raw['src/' + name]:
            raise ValueError('Rendered MTH spec differs from independent frozen effective spec: ' + name)
        generated.append(file_record('src/' + name, rendered))
    generated += [file_record(name, raw[name]) for name in ('ncisources.spec', 'sab.vsab.map', 'src_data')]
    return {'profile': PROFILE, 'files': generated,
            'bindings': {'source': 'MTH', 'version': VERSION, 'engine_ref': config['engine_ref'],
                         'policy_ref': config['policy_ref'],
                         'replacement_baseline': copy.deepcopy(config['replacement_baseline']),
                         'comparison_baseline': None, 'publisher_history': [],
                         'publisher_previous': {'source': 'MTH', 'version': 'MTH_' + settings['prevrel'],
                             'evidence': ['invert1.s:set prevrel', 'prev:captured symlink'],
                             'role': 'publisher history selection in captured preparation; independent of old'},
                         'source_atom_ids': copy.deepcopy(bounds),
                         'legacy_allocation': {'SourceAtomIdBase': bounds['start'] + 2,
                                               'SourceAtomIdLimit': bounds['end'],
                                               'SRCbuilder_start': bounds['start'], 'reserved_SRC_atoms': 2},
                         'inputs': copy.deepcopy(inputs),
                         'identity_state': copy.deepcopy(identity),
                         'metadata_inputs': copy.deepcopy(metadata),
                         'native_inputs': copy.deepcopy(files),
                         'source_decisions': decisions, 'vsab_mappings': mappings,
                         'source_plan_ref': inputs['source_plan'],
                         'source_decision_inputs': {name: templates[name]['sha256'] for name in
                                                   ('ncisources.spec', 'sab.vsab.map', 'src_data')},
                         'template_inputs': {name: templates[name]['sha256'] for name in
                                             sorted(TEMPLATE_NAMES - {'old', 'prev'})}},
            'coverage': {'source_data_stage': 'prepared', 'range_stage': 'final',
                         'generated_specs_match_captured_effective_specs': True,
                         'source_decisions': 'preserved reviewed files; no new dispositions generated',
                         'publisher_preparation_executed': False, 'native_inversion_executed': False,
                         'production_eligible': False}}


def preview_from_lock(lock):
    """Consume frozen lock bytes, never the current checkout's legacy settings.

    The common caller additionally verifies the saved lock/provenance. This
    adapter verifies the reviewed case agreement and every consumed descriptor.
    """
    case, config = lock['case'], lock['configuration']
    if (case.get('source') != 'MTH' or case.get('version') != VERSION or
            case.get('adapter') != 'mth-2026aa-v1' or config != case.get('configuration') or
            config.get('engine_ref') not in case.get('reviewed_engine_refs', []) or
            lock.get('case_sha256') != digest(case)):
        raise ValueError('MTH preview differs from its reviewed historical case')
    expected = {}
    for item in case['source_files']:
        name = item['relative_path']
        if name in expected:
            raise ValueError('Duplicate captured MTH file identity')
        expected[name] = item
    frozen = {}
    for item in lock['code_files']:
        name = item['relative_path']
        if name in frozen:
            raise ValueError('Duplicate frozen MTH file identity')
        frozen[name] = item
    if not TEMPLATE_NAMES <= set(frozen) or not TEMPLATE_NAMES <= set(expected):
        raise ValueError('Missing pinned MTH configuration producer/input')
    for name in TEMPLATE_NAMES:
        item = frozen[name]
        if any(item.get(key) != value for key, value in expected[name].items()):
            raise ValueError('MTH frozen file differs from reviewed descriptor: ' + name)
    return generate(config, case['artifacts'], {name: frozen[name] for name in TEMPLATE_NAMES})


def execution_recipe(config, case, code_files):
    """Build the reviewed execution recipe before a final lock checksum exists.

    The same independently frozen effective specs remain compatibility oracles;
    the execution recipe has its own identity, separate from offline previews.
    """
    if case.get('configuration_generation') != {'profile': EXECUTION_PROFILE}:
        raise ValueError('Missing reviewed MTH generated-execution contract')
    result = preview_from_lock({'configuration': config, 'case': case,
                                'case_sha256': digest(case), 'code_files': code_files})
    return for_execution(result)


def for_execution(preview):
    """Assign the separate execution profile without claiming a native outcome."""
    if preview.get('profile') != PROFILE:
        raise ValueError('Expected MTH preview recipe before execution binding')
    result = copy.deepcopy(preview)
    result['profile'] = EXECUTION_PROFILE
    result['coverage'].pop('native_inversion_executed')
    result['coverage']['native_conversion'] = 'separate worker execution; outcome recorded in run result'
    return result


def execution_recipe_from_lock(lock):
    """Verify the exact resolved recipe against its frozen construction inputs."""
    if lock.get('case_sha256') != digest(lock['case']):
        raise ValueError('Frozen MTH configuration-generation case changed')
    expected = execution_recipe(lock['configuration'], lock['case'], lock['code_files'])
    if lock.get('configuration_generation') != expected:
        raise ValueError('Frozen MTH configuration-generation recipe changed')
    return expected


def receipt(recipe):
    """Return a compact receipt while retaining all generation input bindings."""
    if recipe.get('profile') not in {PROFILE, EXECUTION_PROFILE}:
        raise ValueError('Unknown MTH configuration-generation profile')
    result = copy.deepcopy(recipe)
    result['recipe_sha256'] = digest(recipe)
    result['files'] = [{key: value for key, value in item.items() if key != 'data_b64'}
                       for item in recipe['files']]
    return result
