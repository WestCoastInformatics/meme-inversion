#!/usr/bin/env python3
"""Plan/validate native US Snapshot runs using a release-independent Git engine.

The common worker owns acquisition, materialization, isolation and execution.
This module never queries a database or edits native inputs.  Representation
decisions remain the captured policy, with mapping target VSABs explicit data.
"""
import base64
from collections import Counter
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit

from release_snomed import HEADERS, OPTIONAL_HEADERS

PACKAGE = 'engines/snomedct_us'
OUTPUTS = ('classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src')
WIDTHS = dict(zip(OUTPUTS, (15, 15, 19, 13, 18)))
METADATA = {'sources-src': 'src/sources.src', 'termgroups-src': 'src/termgroups.src',
            'icd10-target-inventory': 'etc/icd10.inmeta', 'icd10cm-target-inventory': 'etc/icd10cm.inmeta'}
ID_TYPES = {'SRC_ATOM_ID', 'SOURCE_CUI', 'SOURCE_AUI', 'SOURCE_RUI', 'SOURCE_ATUI',
            'CODE_SOURCE', 'CODE_ROOT_SOURCE', 'CODE_TERMGROUP', 'ROOT_SOURCE_CUI', 'ROOT_SOURCE_AUI'}
FRAMEWORK_GROUPS = {'SRC/' + tty for tty in ('VPT', 'VAB', 'RPT', 'RAB', 'SSN', 'RHT', 'RSY', 'VSY')}
ABSENT_COMPLEX_MAP = 'orig/fromprovider/OPTIONAL_COMPLEX_MAP_ABSENT.txt'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_info(path):
    digest = hashlib.sha256(); size = rows = 0
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block); size += len(block); rows += block.count(b'\n')
    return {'sha256': digest.hexdigest(), 'bytes': size, 'rows': rows}


def _relative(value):
    if not isinstance(value, str) or any(char in value for char in '\\<>\r\n\x00'):
        raise ValueError('Unsafe compatibility path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not path.parts or str(path) != value:
        raise ValueError('Expected a canonical release-relative path')
    return value


def _date(version):
    if not isinstance(version, str) or not re.fullmatch(r'SNOMEDCT_US_[0-9]{4}_[0-9]{2}_[0-9]{2}', version):
        raise ValueError('Invalid SNOMED source version')
    return datetime.datetime.strptime(version[12:], '%Y_%m_%d').date()


def _property(value):
    if not isinstance(value, str) or not value or any(char in value for char in '\\<>\r\n\x00'):
        raise ValueError('Unsafe or empty compatibility setting')
    return value


def properties(raw, expand=False):
    values, pending = {}, ''
    for line in raw.decode('utf-8').splitlines():
        if not pending and (not line.strip() or line.lstrip().startswith(('#', '!'))):
            continue
        line = pending + line.lstrip() if pending else line
        if line.endswith('\\'):
            pending = line[:-1]; continue
        pending = ''
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not key or key in values:
            raise ValueError('Malformed/duplicate compatibility property')
        values[key] = value.strip()
    if pending:
        raise ValueError('Unterminated compatibility property')
    if expand:
        resolved = {}
        def get(key, seen):
            if key not in values or key in seen:
                raise ValueError('Unresolved/cyclic compatibility property')
            if key not in resolved:
                resolved[key] = re.sub(r'<([^<>]+)>', lambda m: get(m[1], seen | {key}), values[key])
            return resolved[key]
        for key in values:
            get(key, set())
        return resolved
    return values


def _template(code_files):
    if code_files is None:
        raw = (Path(__file__).resolve().parents[1] / PACKAGE / 'sct.cfg.in').read_bytes()
    else:
        found = [item for item in code_files if item.get('relative_path') == 'sct.cfg.in' or
                 item.get('repository_path') == PACKAGE + '/sct.cfg.in']
        if len(found) != 1:
            raise ValueError('One pinned canonical SNOMED template is required')
        raw = base64.b64decode(found[0]['data_b64'], validate=True)
        if sha(raw) != found[0]['sha256']:
            raise ValueError('Canonical template payload changed')
    return raw


def _destination(entry, data, version):
    explicit = data.get('input_destinations', {}).get(entry['role'])
    if explicit is not None:
        destination = _relative(explicit)
    else:
        member = entry.get('archive_member') or unquote(urlsplit(entry['uri']).path)
        if member.startswith(version + '/'):
            destination = _relative(member[len(version) + 1:])
        elif member.startswith('orig/fromprovider/'):
            destination = _relative(member)
        else:
            package = data['package_name']
            _relative(package)
            parts = PurePosixPath(member).parts
            package_parts = PurePosixPath(package).parts
            positions = [index for index in range(len(parts)) if parts[index:index + len(package_parts)] == package_parts]
            if len(positions) != 1:
                raise ValueError('Declare input_destinations when a native member has no unambiguous publisher package path')
            destination = _relative('orig/fromprovider/' + '/'.join(parts[positions[0]:]))
    if not destination.startswith('orig/fromprovider/'):
        raise ValueError('Native RF2 inputs must retain their declared provider-relative paths')
    return destination


def _metadata_bytes(rows, width):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Reviewed source metadata rows are required')
    for row in rows:
        if len(row) != width or any(not isinstance(value, str) or any(c in value for c in '|\r\n\x00') for value in row):
            raise ValueError('Malformed reviewed metadata row')
    return ''.join('|'.join(row) + '\n' for row in rows).encode('utf-8')


def build_plan(configuration, artifacts, code_files=None):
    """Return only fixed native stages and deterministic compatibility files."""
    config = configuration
    if (config['source'] != 'SNOMEDCT_US' or config['source_options'] != {'rf2_view': 'Snapshot'} or
            config['inputs']['source_data_stage'] != 'publisher' or config['output_stage'] != 'inversion-src' or
            config['publisher_history'] or config['inputs']['identity_state'] is not None):
        raise ValueError('Unsupported SNOMED view, input stage, history or identity consumer')
    current = _date(config['version'])
    prior = config['replacement_baseline']
    if not prior or prior['source'] != config['source'] or _date(prior['version']) >= current:
        raise ValueError('An explicit earlier inserted predecessor is required')
    if len(config['inputs']['source_data']) != 1:
        raise ValueError('One complete Snapshot bundle is required')
    native_name = config['inputs']['source_data'][0]
    metadata_name = config['inputs']['reference_ncimeta']
    native, metadata = artifacts[native_name], artifacts[metadata_name]
    policy = artifacts[config['policy_ref']]['data']
    source_plan = artifacts[config['inputs']['source_plan']]['data']
    if native['artifact_type'] != 'publisher-bundle' or metadata['artifact_type'] != 'ncimeta-state':
        raise ValueError('Invalid native or metadata artifact role')
    for key in ('replacement_baseline', 'comparison_baseline', 'publisher_history'):
        if source_plan.get(key) != config[key]:
            raise ValueError('Source plan/common transition differs: ' + key)
    if source_plan.get('mrdoc_required') is not False:
        raise ValueError('Live/MRDOC generation is outside this offline native-core profile')
    if native['data'].get('edition') != 'US' or native['data'].get('rf2_view') != 'Snapshot' or native['data'].get('publisher_release_date') != current.isoformat():
        raise ValueError('Native bundle is not the selected US Snapshot publication')
    bounds = config['source_atom_ids']
    if not bounds or any(type(bounds[key]) is not int or bounds[key] <= 0 for key in ('start', 'end')) or bounds['start'] > bounds['end']:
        raise ValueError('Complete positive inclusive ID bounds are required')
    allocation = artifacts[bounds['provenance_ref']]
    if allocation['artifact_type'] != 'id-allocation' or any(allocation['data'].get(key) != bounds[key] for key in ('start', 'end', 'bound_kind')):
        raise ValueError('ID bounds differ from their evidence')
    targets = policy.get('mapping_targets', {})
    if set(targets) != {'ICD10', 'ICD10CM', 'ICD9CM'} or any(not re.fullmatch(re.escape(key) + r'_[A-Za-z0-9_.-]+', value) for key, value in targets.items()):
        raise ValueError('Explicit reviewed ICD10/ICD10CM/ICD9CM target VSABs are required; years are never inferred')
    inputs, destinations, fingerprints, native_paths = [], set(), {}, {}
    def add(name, entry, destination):
        destination = _relative(destination)
        if destination in destinations:
            raise ValueError('Two input roles collide at one native destination')
        destinations.add(destination)
        inputs.append({'artifact': name, 'role': entry['role'], 'destination': destination})
        fingerprints[destination] = {key: entry[key] for key in ('sha256', 'bytes')}
    expected = set(HEADERS)
    for entry in native['files']:
        role = entry['role']
        if role not in expected | set(OPTIONAL_HEADERS) or role in native_paths:
            raise ValueError('Unsupported or duplicate RF2 role')
        destination = _destination(entry, native['data'], config['version'])
        native_paths[role] = destination
        add(native_name, entry, destination)
    if not expected.issubset(native_paths):
        raise ValueError('All fourteen declared RF2 core roles are required')
    saved = {}
    for entry in metadata['files']:
        if entry['role'] in METADATA:
            if entry['role'] in saved:
                raise ValueError('Duplicate preserved metadata role')
            saved[entry['role']] = entry
            add(metadata_name, entry, METADATA[entry['role']])
    if set(saved) != set(METADATA):
        raise ValueError('Saved source/termgroup metadata and both ICD inventories are required')
    rendered_metadata = {'src/sources.src': _metadata_bytes(metadata['data']['sources_rows'], 20),
                         'src/termgroups.src': _metadata_bytes(metadata['data']['termgroups_rows'], 6)}
    source_row = metadata['data']['sources_rows']
    if len(source_row) != 1 or source_row[0][0:2] != [config['version'], prior['version']] or source_row[0][6] != config['source']:
        raise ValueError('Source metadata differs from current/inserted source identities')
    group_names = set()
    for row in metadata['data']['termgroups_rows']:
        if row[0] != config['version'] + '/' + row[5] or row[0] in group_names:
            raise ValueError('Termgroup metadata uses a different source version')
        group_names.add(row[0])
    for destination, raw in rendered_metadata.items():
        if (sha(raw), len(raw)) != (fingerprints[destination]['sha256'], fingerprints[destination]['bytes']):
            raise ValueError('Preserved metadata bytes differ from deterministic reviewed row rendering')
    months = 'January February March April May June July August September October November December'.split()
    title = source_plan.get('source_title') or ('SNOMED Clinical Terms US Edition, ' + months[current.month - 1] + ' ' + str(current.day) + ', ' + str(current.year))
    native_root = posixpath.commonpath([posixpath.dirname(value) for value in native_paths.values()])
    values = {'version': config['version'], 'replacement_version': prior['version'],
              'publisher_date': current.strftime('%Y%m%d'), 'replacement_date': _date(prior['version']).strftime('%Y%m%d'),
              'said_start': str(bounds['start']), 'said_end': str(bounds['end']), 'source_title': _property(title),
              'native_root': '../' + native_root, 'mapping_target_icd10': targets['ICD10'],
              'mapping_target_icd10cm': targets['ICD10CM'], 'mapping_target_icd9cm_version': targets['ICD9CM'].removeprefix('ICD9CM_')}
    values.update({role: '../' + destination for role, destination in native_paths.items()})
    values.setdefault('rf2-complex-map', '../' + ABSENT_COMPLEX_MAP)
    template = _template(code_files)
    tokens = set(re.findall(r'\{\{([^{}]+)\}\}', template.decode()))
    if tokens != set(values):
        raise ValueError('Template parameter set differs from the reviewed renderer')
    raw = re.sub(r'\{\{([^{}]+)\}\}', lambda match: _property(values[match[1]]), template.decode()).encode()
    expanded = properties(raw, True)
    for key, value in {'VSAB': config['version'], 'VSABOLD': prior['version'], 'SaidStart': str(bounds['start']), 'SaidEnd': str(bounds['end'])}.items():
        if expanded[key] != value:
            raise ValueError('Generated configuration changed a common identity or bound')
    return {'schema_version': 1, 'source': config['source'], 'version': config['version'], 'engine_package': PACKAGE,
            'input_files': inputs, 'generated_files': [{'relative_path': 'etc/sct.cfg', 'data_b64': base64.b64encode(raw).decode(),
                                                       'sha256': sha(raw), 'mode': '0o444'}], 'symlinks': [],
            'stages': [{'name': 'compile-rf2', 'cwd': 'bin', 'argv': ['/usr/bin/perl', '-c', 'invert_rf2.pl']},
                       {'name': 'compile-cleanup', 'cwd': 'bin', 'argv': ['/usr/bin/perl', '-c', 'rmdanglingattrs.pl']},
                       {'name': 'conversion', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'invert_rf2.pl']},
                       {'name': 'preserve-attributes', 'cwd': 'bin', 'argv': ['/bin/mv', '../src/attributes.src', '../tmp/attributes.before-cleanup.src']},
                       {'name': 'cleanup', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'rmdanglingattrs.pl', '../tmp/attributes.before-cleanup.src'], 'stdout': 'src/attributes.src'}],
            'output_files': ['src/' + name for name in OUTPUTS],
            'validation': {'version': config['version'], 'replacement_baseline': copy.deepcopy(prior),
                           'source_atom_ids': copy.deepcopy(bounds), 'mapping_targets': copy.deepcopy(targets),
                           'properties': expanded, 'native_paths': native_paths, 'input_fingerprints': fingerprints,
                           'rendered_metadata': {key: base64.b64encode(value).decode() for key, value in rendered_metadata.items()},
                           'declared_mappings': copy.deepcopy(policy.get('mappings', {})),
                           'mapping_decisions': copy.deepcopy(source_plan.get('mapping_decisions', {})),
                           'supported_modules': copy.deepcopy(policy.get('supported_modules', [])),
                           'template_sha256': sha(template)}}


def _regular(path, target):
    path = Path(path)
    if path.resolve() != path or not path.is_file() or not path.is_relative_to(Path(target)):
        raise ValueError('Expected a regular unlinked candidate input/output')
    return path


def _cfg(plan, target):
    item = plan['generated_files'][0]
    path = _regular(Path(target) / 'etc/sct.cfg', target)
    if file_info(path)['sha256'] != item['sha256'] or path.stat().st_mode & 0o222:
        raise ValueError('Generated cfg changed or is writable')


def _rows(path, role, publication, counts):
    expected = {**HEADERS, **OPTIONAL_HEADERS}[role]
    seen = set()
    with path.open(encoding='utf-8', newline='') as handle:
        header = handle.readline().rstrip('\r\n').split('\t')
        if header != expected:
            raise ValueError('Actual RF2 header differs from reviewed schema: ' + role)
        for number, line in enumerate(handle, 2):
            if not line.endswith('\n') or '\x00' in line:
                raise ValueError('Malformed native line terminator/content: ' + role)
            values = line.rstrip('\r\n').split('\t')
            if len(values) != len(header):
                raise ValueError('Actual RF2 field count differs at ' + role + ':' + str(number))
            row = dict(zip(header, values))
            if not row['id'] or row['id'] in seen or row['active'] not in ('0', '1') or not row['moduleId'].isdigit():
                raise ValueError('Duplicate/invalid RF2 Snapshot identity/status/module: ' + role + ':' + str(number))
            effective = datetime.datetime.strptime(row['effectiveTime'], '%Y%m%d').date()
            if effective > publication:
                raise ValueError('Unpublished/future RF2 effective date: ' + role)
            seen.add(row['id']); counts[role] += 1
            yield row


def validate_inputs(plan, target):
    """Scan actual RF2 headers/rows and current policy coverage before Perl runs."""
    facts, issues = {}, []
    def fail(code, message):
        issues.append({'severity': 'error', 'code': code, 'message': message, 'path': 'candidate'})
    try:
        target = Path(target)
        _cfg(plan, target)
        validation = plan['validation']; props = validation['properties']; publication = _date(plan['version'])
        for destination, expected in validation['input_fingerprints'].items():
            path = _regular(target / _relative(destination), target)
            actual = file_info(path)
            if (actual['sha256'], actual['bytes']) != (expected['sha256'], expected['bytes']):
                raise ValueError('Materialized input bytes differ: ' + destination)
            if path.stat().st_mode & 0o222:
                raise ValueError('Materialized source inputs must be read-only: ' + destination)
        for destination, encoded in validation['rendered_metadata'].items():
            if (target / destination).read_bytes() != base64.b64decode(encoded, validate=True):
                raise ValueError('Preserved metadata differs from deterministic reviewed rows')
        native = {role: target / destination for role, destination in validation['native_paths'].items()}
        if 'rf2-complex-map' not in native and (target / ABSENT_COMPLEX_MAP).exists():
            raise ValueError('Undeclared optional ComplexMap appeared')
        counts = Counter(); active = {}; observed = {key: set() for key in ('relationship_types', 'association_refsets', 'description_types', 'attribute_refsets', 'concrete_types', 'refset_patterns', 'map_correlations')}
        modules = set(); active_types = set(); resolved = {}; labels = {}; dependencies = []
        def rows(role):
            for row in _rows(native[role], role, publication, counts):
                if row['active'] == '1': modules.add(row['moduleId'])
                yield row
        for row in rows('rf2-concepts'):
            active[row['id']] = row['active'] == '1'
        if not active.get(props['ROOTSCUI']):
            raise ValueError('The declared SNOMED root concept is not active in native data')
        for row in rows('rf2-relationships'):
            if row['active'] == '1':
                active_types.add(row['typeId']); observed['relationship_types'].add(row['typeId'])
        associations = set()
        for row in rows('rf2-association'):
            if row['active'] == '1':
                active_types.add(row['refsetId']); associations.add(row['refsetId']); observed['association_refsets'].add(row['refsetId'])
        name_mappings = {}
        for key, value in props.items():
            if key.startswith('SCT.RELMAP.'):
                name, rela, inverse, relation = value.split('|')
                name_mappings[name] = {'rel': relation, 'rela': rela, 'inverse_rela': inverse}
        for row in rows('rf2-descriptions'):
            active[row['id']] = row['active'] == '1' and active.get(row['conceptId'], False)
            observed['description_types'].add(row['typeId'])
            if 'TTY.' + row['typeId'] not in props:
                raise ValueError('Unknown actual description type: ' + row['typeId'])
            if row['conceptId'] in active_types and props['TTY.' + row['typeId']] == 'FN':
                label = row['term'].replace('|', '&#x7C;').rstrip(' ')
                labels.setdefault(row['conceptId'], set()).add(label)
                if label in name_mappings:
                    mapping = name_mappings[label]
                    if row['conceptId'] in resolved and resolved[row['conceptId']] != mapping:
                        raise ValueError('Conflicting name-derived mapping for native type: ' + row['conceptId'])
                    resolved[row['conceptId']] = mapping
        for identifier in active_types - {'116680003'}:
            if identifier not in resolved:
                raise ValueError('Unreviewed native relationship/refset ID or changed label: ' + identifier + ' ' + repr(sorted(labels.get(identifier, []))))
        resolved.setdefault('116680003', {'rel': 'CHD', 'rela': 'isa', 'inverse_rela': 'inverse_isa'})
        for row in rows('rf2-text-definitions'):
            pass
        for row in rows('rf2-attribute-value'):
            if row['active'] == '1' and active.get(row['referencedComponentId']):
                observed['attribute_refsets'].add(row['refsetId'])
        for row in rows('rf2-simple-map'):
            if row['active'] == '1' and active.get(row['referencedComponentId']):
                observed['attribute_refsets'].add(row['refsetId'])
        for row in rows('rf2-concrete-values'):
            if row['active'] == '1': observed['concrete_types'].add(row['typeId'])
        for identifier in observed['attribute_refsets'] | observed['concrete_types']:
            if 'ATN.' + identifier not in props:
                raise ValueError('Unreviewed actual ATN/refset/concrete type: ' + identifier)
        for row in rows('rf2-refset-descriptor'):
            if row['active'] == '1' and active.get(row['referencedComponentId']):
                observed['refset_patterns'].add(row['referencedComponentId'])
        for identifier in observed['refset_patterns']:
            if 'PATTERN.' + identifier not in props:
                raise ValueError('Unreviewed actual refset pattern: ' + identifier)
        for row in rows('rf2-description-type'):
            pass
        for row in rows('rf2-module-dependency'):
            if row['active'] == '1':
                source = datetime.datetime.strptime(row['sourceEffectiveTime'], '%Y%m%d').date()
                dependency = datetime.datetime.strptime(row['targetEffectiveTime'], '%Y%m%d').date()
                if source > publication or dependency > source:
                    raise ValueError('Incompatible actual module-dependency effective times')
                if row['referencedComponentId'] not in validation['supported_modules']:
                    raise ValueError('Actual module dependency targets an unreviewed module')
                dependencies.append({'source_module_id': row['moduleId'], 'target_module_id': row['referencedComponentId'],
                                     'source_effective_time': row['sourceEffectiveTime'], 'target_effective_time': row['targetEffectiveTime']})
        for row in rows('rf2-language'):
            if row['active'] == '1' and row['refsetId'] not in {props['USREFSET'], props['GBREFSET']}:
                raise ValueError('Unreviewed language preference refset: ' + row['refsetId'])
        for row in rows('rf2-simple-refset'):
            pass
        for role in ('rf2-extended-map', 'rf2-complex-map'):
            if role not in native: continue
            for row in rows(role):
                if row['active'] == '1' and row['referencedComponentId'] in active:
                    if role == 'rf2-extended-map' and row['refsetId'] not in {'447562003', '6011000124106'}:
                        raise ValueError('Unreviewed extended map target refset: ' + row['refsetId'])
                    observed['map_correlations'].add(row['correlationId'])
                    if 'MAPINFO.' + row['correlationId'] not in props:
                        raise ValueError('Unreviewed map correlation: ' + row['correlationId'])
        allowed_modules = set(validation['supported_modules'])
        if not allowed_modules or modules - allowed_modules:
            raise ValueError('Actual native modules exceed the explicit reviewed module inventory: ' + repr(sorted(modules - allowed_modules)))
        if not dependencies:
            raise ValueError('Native package has no active module dependency evidence')
        for category, mappings in validation['mapping_decisions'].items():
            for identifier, decision in mappings.items():
                if identifier not in observed.get(category, set()):
                    raise ValueError('Reviewed mapping decision has no observed native identifier: ' + identifier)
                if decision.get('decision') != 'represent':
                    raise ValueError('The captured producer cannot implement a new exclusion decision')
        actual_mappings = {key: {} for key in observed}
        for category in ('relationship_types', 'association_refsets'):
            actual_mappings[category] = {identifier: {'decision': 'represent', **resolved[identifier]} for identifier in observed[category]}
        for category, prefix, field in (('description_types', 'TTY.', 'tty'), ('attribute_refsets', 'ATN.', 'atn'),
                                         ('concrete_types', 'ATN.', 'atn'), ('refset_patterns', 'PATTERN.', 'pattern')):
            actual_mappings[category] = {identifier: {'decision': 'represent', field: props[prefix + identifier]} for identifier in observed[category]}
        for identifier in observed['map_correlations']:
            relation, rela = props['MAPINFO.' + identifier].split('|')
            actual_mappings['map_correlations'][identifier] = {'decision': 'represent', 'rel': relation, 'rela': rela}
        for category in observed:
            declarations = {**validation['declared_mappings'].get(category, {}), **validation['mapping_decisions'].get(category, {})}
            for identifier in observed[category]:
                if identifier in declarations:
                    mapping = declarations[identifier]
                    expected = actual_mappings[category][identifier]
                    if any(mapping.get(key) != value for key, value in expected.items()):
                        raise ValueError('Declared representation differs from the captured physical mapping: ' + category + '/' + identifier)
        facts.update(actual_headers_verified=True, native_rows=dict(counts), native_modules=sorted(modules), module_dependencies=dependencies,
                     physical_discovery={key: sorted(value) for key, value in observed.items()},
                     resolved_mappings=actual_mappings,
                     mapped_type_labels={key: sorted(value) for key, value in labels.items()},
                     metadata_rows_verified=True, mapping_targets=validation['mapping_targets'],
                     native_inputs_changed=False, previous_source_folder_required=False)
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
        fail('SNOMED_PHYSICAL_INPUTS_INVALID', str(error))
    return {'passed': not issues, 'issues': issues, 'facts': facts}


def _structure(paths, groups, bounds, version):
    atoms, atom_cuis, auis = set(), {}, set()
    bad = Counter(); version = version.encode(); groups = {value.encode() for value in groups | FRAMEWORK_GROUPS}
    with paths['classes_atoms.src'].open('rb') as handle:
        for row in handle:
            fields = row.removesuffix(b'\n').split(b'|')
            if len(fields) != WIDTHS['classes_atoms.src']: continue
            bad['duplicate_atom_id'] += fields[0] in atoms
            atoms.add(fields[0]); atom_cuis[fields[0]] = fields[10]
            if fields[9]: auis.add(fields[9])
            bad['atom_range'] += not fields[0].isdigit() or not bounds['start'] <= int(fields[0]) <= bounds['end']
            bad['undeclared_termgroup'] += fields[2] not in groups
    file_facts = {}
    for name, path in paths.items():
        counts = Counter(); generated = set(); widths = Counter(); rows = 0
        with path.open('rb') as handle:
            for row in handle:
                rows += 1; counts['missing_newline'] += not row.endswith(b'\n'); counts['nul'] += b'\x00' in row
                try: row.decode('utf-8')
                except UnicodeDecodeError: counts['utf8'] += 1
                f = row.removesuffix(b'\n').split(b'|'); widths[len(f)] += 1
                if len(f) != WIDTHS[name]: counts['width'] += 1; continue
                if name != 'classes_atoms.src': counts['trailing_field'] += f[-1] != b''
                endpoints = []
                if name in ('attributes.src', 'relationships.src'):
                    counts['generated_id'] += not f[0].isdigit() or int(f[0]) <= 0
                    counts['duplicate_generated_id'] += f[0] in generated; generated.add(f[0])
                if name == 'classes_atoms.src':
                    counts['source_version'] += f[1] not in {b'SRC', version}
                elif name == 'attributes.src':
                    endpoints = [(f[1], f[10], f[11])]
                    counts['attribute_digest'] += hashlib.md5(f[4]).hexdigest().encode() != f[13]
                    counts['attribute_source'] += f[5] not in {b'SRC', version, b'E-' + version}
                    if f[10] == b'SOURCE_AUI' and f[11] == version: counts['dangling_description'] += f[1] not in auis
                elif name == 'relationships.src':
                    endpoints = [(f[2], f[12], f[13]), (f[5], f[14], f[15])]
                    counts['unmapped_relationship'] += f[3].startswith(b'XX-') or b'###' in f[3] or b'###' in f[4]
                    counts['relationship_source'] += f[6] not in {b'SRC', version} or f[7] not in {b'SRC', version}
                elif name == 'mergefacts.src':
                    endpoints = [(f[0], f[8], f[9]), (f[2], f[10], f[11])]
                    counts['merge_source'] += f[3] not in {b'SRC', version}
                else:
                    endpoints = [(f[11], f[12], f[13]), (f[14], f[15], f[16])]
                    chain = f[7].split(b'.') if f[7] else []
                    counts['context_atom'] += f[0] not in atoms or f[3] not in atoms
                    counts['context_path'] += any(value not in atoms for value in chain)
                    counts['context_parent'] += not chain or chain[-1] != f[3]
                    counts['context_source'] += f[4] not in {b'SRC', version} or f[5] not in {b'SRC', version}
                    if f[12] == b'SOURCE_CUI' and f[13] == version: counts['context_child_identity'] += atom_cuis.get(f[0]) != f[11]
                    if f[15] == b'SOURCE_CUI' and f[16] == version: counts['context_parent_identity'] += atom_cuis.get(f[3]) != f[14]
                for value, kind, qualifier in endpoints:
                    counts['identifier_type'] += kind.decode(errors='replace') not in ID_TYPES
                    if kind == b'SRC_ATOM_ID': counts['atom_endpoint'] += value not in atoms
                    if kind in (b'SOURCE_AUI', b'SOURCE_CUI') and qualifier.startswith(b'SNOMEDCT_US_'):
                        counts['source_qualifier'] += qualifier != version
        file_facts[name] = {'rows': rows, 'field_counts': dict(widths), 'violations': {key: value for key, value in counts.items() if value}}
    return {'passed': bool(atoms) and not any(bad.values()) and all(not item['violations'] for item in file_facts.values()),
            'atom_violations': {key: value for key, value in bad.items() if value}, 'unique_atoms': len(atoms), 'files': file_facts}


def validate_outputs(plan, target):
    issues, facts = [], {}
    try:
        target = Path(target); _cfg(plan, target)
        paths = {name: _regular(target / 'src' / name, target) for name in OUTPUTS}
        groups = {row.split('|')[0] for row in (target / 'src/termgroups.src').read_text().splitlines()}
        structure = _structure(paths, groups, plan['validation']['source_atom_ids'], plan['version'])
        facts.update(structure=structure, files={name: file_info(path) for name, path in paths.items()},
                     compared_identifiers_reindexed=False, ignored_columns=[])
        if not structure['passed']: raise ValueError('Independent release-aware output structure/identity validation failed')
    except (ValueError, KeyError, TypeError, OSError, UnicodeError) as error:
        issues.append({'severity': 'error', 'code': 'SNOMED_OUTPUTS_INVALID', 'message': str(error), 'path': 'src'})
    return {'passed': not issues, 'issues': issues, 'facts': facts}


def compare_outputs(plan, target, reference_directory, run_directory=None):
    """Exact complete-byte comparison; no field/ID/multiplicity allowances."""
    validation = validate_outputs(plan, target)
    files = {}
    for name in OUTPUTS:
        current, official = file_info(Path(target) / 'src' / name), file_info(Path(reference_directory) / name)
        files[name] = {'candidate': current, 'reference': official,
                       'exact_match': (current['sha256'], current['bytes']) == (official['sha256'], official['bytes'])}
    exact = all(item['exact_match'] for item in files.values())
    return {'status': 'PASS_EXACT' if exact and validation['passed'] else
            ('REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS' if exact else 'DIFFERENCES_REQUIRE_REVIEW'),
            'source': plan['source'], 'version': plan['version'], 'files': files, 'validation': validation,
            'ignored_columns': [], 'generated_identifiers_reindexed': False}
