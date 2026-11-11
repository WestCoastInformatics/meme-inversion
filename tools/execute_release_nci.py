#!/usr/bin/env python3
"""Plan/validate NCIt native execution from a preserved preparation closure.

No function here acquires files, queries NCImeta or launches a native process.
The common worker supplies pinned Git code, immutable inputs and serialization.
Runtime validation uses only the standard library and frozen apparatus helpers.
"""
import base64
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

import nci_source_plan as source_plan
import compare_nci_core

PROFILE = 'nci-preserved-preparation-v1'
PACKAGE = 'engines/nci'
ROLES = ('annotationDeclaration', 'objectDeclaration', 'classDeclaration', 'relations', 'hierarchy')
STATE_ROLES = {'sources-src': 'src/sources.src', 'termgroups-src': 'src/termgroups.src',
               'nci-configuration': 'etc/preserved-nci.cfg'}
OUTPUTS = tuple('src/' + name for name in ('classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src'))
PATH_PROPERTIES = {'ORIGDIR': '../orig', 'TEMPDIR': '../tmp', 'SRCDIR': '../src', 'ETCDIR': '../etc', 'ETCQADIR': '../etc/qa',
                   'File.Source': '<SRCDIR>/sources.src', 'File.Termgroup': '<SRCDIR>/termgroups.src',
                   'FILE.MRCONSO': '<ORIGDIR>/MRCONSO.TREF', 'FILE.MRREL': '<ORIGDIR>/MRREL.TREF',
                   'FILE.MRSAT': '<ORIGDIR>/MRSAT.TREF', 'FILE.MRDOC': '<ORIGDIR>/MRDOC.TREF'}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', value):
        raise ValueError('An exact NCIt version is required')
    return value[4:]


def _positive(value):
    return type(value) is int and value > 0


def _properties(raw):
    result = {}
    for line in raw.decode('utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('Malformed preserved NCIt configuration property')
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or key in result or any(c in key + value for c in '\r\n\x00'):
            raise ValueError('Duplicate, empty or unsafe preserved property')
        result[key] = value
    return result


def _file(path, raw):
    return {'relative_path': path, 'data_b64': base64.b64encode(raw).decode(), 'sha256': _sha(raw), 'mode': '0o444'}


def _artifact(artifacts, reference, kind, version):
    item = artifacts.get(reference)
    if not isinstance(item, dict) or item.get('artifact_type') != kind or item.get('source') != 'NCI' or item.get('version') != version:
        raise ValueError('Missing or mismatched NCIt ' + kind + ' artifact: ' + str(reference))
    if not isinstance(item.get('data'), dict):
        raise ValueError('Artifact data must be an object')
    return item


def _roles(item, expected):
    files = item.get('files')
    if not isinstance(files, list) or len(files) != len(expected) or {row.get('role') for row in files} != set(expected):
        raise ValueError('Incomplete or duplicate preserved NCIt file roles')
    return {row['role']: row for row in files}


def _template(code_files):
    if code_files is None:
        return None
    matches = [row for row in code_files if row.get('relative_path') == 'nci.cfg.in' or row.get('repository_path') == PACKAGE + '/nci.cfg.in']
    if len(matches) != 1:
        raise ValueError('Exactly one pinned Git NCIt configuration template is required')
    raw = base64.b64decode(matches[0]['data_b64'], validate=True)
    if _sha(raw) != matches[0]['sha256']:
        raise ValueError('Pinned NCIt configuration template changed')
    return raw


def build_plan(configuration, artifacts, code_files=None):
    """Local admission planner, including the reviewed source-plan schema."""
    return _build_plan(configuration, artifacts, code_files, validate_schema=True)


def rebuild_plan(configuration, artifacts, code_files):
    """Stdlib worker rebuild for exact equality with the admitted native recipe.

    This does not establish schema/admission approval. The worker first verifies
    the frozen committed capsule, then compares this source-fixed recipe with
    its frozen plan; changed commands cannot approve themselves by resealing.
    """
    return _build_plan(configuration, artifacts, code_files, validate_schema=False)


def _build_plan(configuration, artifacts, code_files, *, validate_schema):
    """Build the common deterministic recipe; never read artifact locations.

    Preserved ncimeta-state.data has profile/replacement_baseline/properties.
    Its three files are sources-src, termgroups-src and nci-configuration. The
    last is parsed as DATA and must physically match the declared properties.
    Six fresh backend assurances are inapplicable to consuming these exact
    conversion inputs; this does not approve any new exporter or installation.
    """
    config = configuration
    if config.get('source') != 'NCI' or config.get('source_options') != {} or config.get('output_stage') != 'inversion-src':
        raise ValueError('NCIt archived execution requires NCI, empty options and inversion-src')
    current = _version(config['version'])
    prior = config['replacement_baseline']
    if not isinstance(prior, dict) or set(prior) != {'source', 'version'} or prior['source'] != 'NCI' or _version(prior['version']) >= current:
        raise ValueError('An explicit earlier NCIt predecessor is required; skipped months are allowed')
    if config.get('comparison_baseline') is not None or config.get('publisher_history') != []:
        raise ValueError('This NCIt core profile has no separate history/change-detection preparation')
    inputs = config['inputs']
    if inputs['source_data_stage'] != 'publisher' or len(inputs['source_data']) != 1:
        raise ValueError('One complete publisher bundle is required')
    publisher = _artifact(artifacts, inputs['source_data'][0], 'publisher-bundle', config['version'])
    files = _roles(publisher, ROLES)
    state = _artifact(artifacts, inputs['reference_ncimeta'], 'ncimeta-state', config['version'])
    state_files = _roles(state, STATE_ROLES)
    saved = state['data']
    if set(saved) != {'profile', 'replacement_baseline', 'properties'} or saved['profile'] != PROFILE or saved['replacement_baseline'] != prior:
        raise ValueError('This executor requires the explicit preserved preparation profile and predecessor')
    properties = copy.deepcopy(saved['properties'])
    if not isinstance(properties, dict) or not properties or any(not isinstance(k, str) or not k or not isinstance(v, str) or any(c in k + v for c in '\r\n\x00') for k, v in properties.items()):
        raise ValueError('Preserved properties must be safe literal string pairs')
    identity = _artifact(artifacts, inputs['identity_state'], 'identity-state', prior['version'])['data']
    if identity.get('profile') != 'saved-hierarchy-root-v1' or identity.get('replacement_baseline') != prior or not _positive(identity.get('root_atom_id')):
        raise ValueError('The predecessor-bound saved hierarchy root is required')
    bounds = config['source_atom_ids']
    if not isinstance(bounds, dict) or not all(_positive(bounds.get(key)) for key in ('start', 'end')) or bounds['start'] > bounds['end']:
        raise ValueError('Exact positive inclusive source-atom bounds are required')
    allocation = _artifact(artifacts, bounds['provenance_ref'], 'id-allocation', config['version'])['data']
    if not all(_positive(allocation.get(key)) for key in ('start', 'end')) or any(allocation.get(key) != bounds.get(key) for key in ('start', 'end', 'bound_kind')):
        raise ValueError('Allocation data must match the complete exact typed range')
    if bounds.get('bound_kind') not in ('reserved-historical-range', 'historical-emitted-range', 'dev-reservation', 'production-reservation'):
        raise ValueError('Unknown allocation evidence kind')
    expected = {'VSAB': config['version'], 'RSAB': 'NCI', 'SaidStart': str(bounds['start']),
                'HC.RootNodeSaid': str(identity['root_atom_id']), 'HC.RootNodeCode': identity['root_code'], 'HC.RootNodeName': identity['root_name']}
    if any(properties.get(key) != value for key, value in expected.items()):
        raise ValueError('Preserved configuration source, allocation seed or saved hierarchy root differs from manifest')
    if any(properties.get(key) != value for key, value in PATH_PROPERTIES.items()):
        raise ValueError('Preserved native paths differ from the fixed standard candidate layout')
    if properties.get('LogFile') != 'invert_<VSAB>.log' or properties.get('ofReport') != '<ETCDIR>/qa/QaReport.<VSAB>.txt':
        raise ValueError('Preserved log/report paths differ from the reviewed fixed layout')
    template = _template(code_files)
    if template is not None:
        known = set(_properties(template))
        for key in properties:
            if key not in known and key not in ('NCI.SourcePlan.Roots', 'NCI.SourcePlan.Termgroups') and not re.fullmatch(r'(?:vsab|rsab|in2tty|in2Otty|inl2tty)\.[^=\r\n\x00]+|[A-Za-z0-9_.-]+\.RSSN', key):
                raise ValueError('Preserved property has no reviewed native configuration meaning: ' + key)
    plan = _artifact(artifacts, inputs['source_plan'], 'source-plan', config['version'])['data']
    # Schema validation is local planning only; workers need no jsonschema.
    if validate_schema:
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1] / 'docs/inversion-review/nci-source-plan.schema.json').read_text())
        errors = list(Draft202012Validator(schema).iter_errors(plan))
        if errors:
            raise ValueError('Invalid reviewed NCIt source plan: ' + errors[0].message)
    for key in ('source', 'version', 'replacement_baseline', 'comparison_baseline', 'publisher_history'):
        if plan[key] != config[key]:
            raise ValueError('Source plan differs from manifest: ' + key)
    policy = _artifact(artifacts, config['policy_ref'], 'policy', config['version'])['data']
    model = policy['metadata_model']
    required_vocab = ('publisher_termgroups', 'publisher_properties', 'publisher_labels', 'relationship_roles')
    if policy.get('profile') != source_plan.PROFILE or not isinstance(model, dict) or any(key not in model for key in required_vocab):
        raise ValueError('Reviewed publisher representation vocabulary is required')
    native = {}
    staged = []
    for role in ROLES:
        item = files[role]
        name = PurePosixPath(item.get('archive_member', urlsplit(item['uri']).path)).name
        if not re.fullmatch(re.escape(role) + r'-[0-9]{8}\.txt', name):
            raise ValueError('Native filename differs from the explicit role/date contract')
        destination = 'orig/fromprovider/' + name
        staged.append({'artifact': inputs['source_data'][0], 'role': role, 'destination': destination})
        native[role] = {'relative_path': destination, 'sha256': item['sha256'], 'bytes': item['bytes']}
    for role, destination in STATE_ROLES.items():
        staged.append({'artifact': inputs['reference_ncimeta'], 'role': role, 'destination': destination})
    variables = {'release': current, 'replacement_release': _version(prior['version'])}
    roots, tokens = [], {}
    for addition in plan['new_subsources']:
        row = source_plan.row(addition['metadata'], source_plan.SOURCE_FIELDS, variables)
        name = source_plan.identifier(row['stripped_source'])
        root = addition['root']
        roots.append((name, source_plan.text(root['preferred_term']), source_plan.text(root['short_name'])))
        if not all(roots[-1]):
            raise ValueError('New root names must be complete')
        for alias in addition['publisher_names']:
            if properties.get('vsab.' + alias) != row['source_name'] or properties.get('rsab.' + alias) != name:
                raise ValueError('Preserved publisher mappings disagree with explicit new-root plan')
    if len({row[0] for row in roots}) != len(roots):
        raise ValueError('Duplicate planned subsource root')
    for key, value in plan['property_updates'].items():
        if properties.get(key) != value:
            raise ValueError('Preserved configuration lacks an explicit term-type mapping decision')
    declared = {tuple(row) for row in model['publisher_termgroups']}
    for addition in plan['new_termgroups']:
        row = source_plan.row(addition['metadata'], source_plan.TERMGROUP_FIELDS, variables)
        vsab, tty = row['termgroup_name'].rsplit('/', 1)
        aliases = [key[5:] for key, value in properties.items() if key.startswith('vsab.') and value == vsab]
        if vsab == config['version']:
            aliases = ['NCI']
        if not aliases:
            raise ValueError('Planned termgroup has no preserved publisher alias')
        for incoming in addition['input_ttys']:
            output = incoming if incoming in ('PT', 'SY') else properties.get('in2tty.' + incoming, properties.get('in2Otty.' + incoming, properties.get('inl2tty.' + incoming)))
            if output != tty:
                raise ValueError('Planned native term type lacks a matching preserved mapping')
            for alias in aliases:
                token = alias + incoming
                if token in tokens and tokens[token] != (alias, incoming):
                    raise ValueError('Ambiguous planned native termgroup token')
                tokens[token] = (alias, incoming)
                declared.add((alias, incoming))
    token_pairs = {}
    for alias, incoming in declared:
        source_plan.text(alias);source_plan.identifier(incoming)
        token = alias + incoming
        if token in token_pairs and token_pairs[token] != (alias, incoming):
            raise ValueError('Ambiguous existing/planned native publisher termgroup token')
        token_pairs[token] = (alias, incoming)
    new_groups = [source_plan.row(row['metadata'], source_plan.TERMGROUP_FIELDS, variables)['termgroup_name'] for row in plan['new_termgroups']]
    if len(new_groups) != len(set(new_groups)) or any(not any(name.startswith(source + '_' + current + '/') for name in new_groups) for source, _, _ in roots):
        raise ValueError('Duplicate planned termgroup or a new root without its explicit termgroups')
    properties['NCI.SourcePlan.Roots'] = '../etc/new-subsources.tsv'
    properties['NCI.SourcePlan.Termgroups'] = '../etc/planned-termgroups.tsv'
    config_raw = ''.join(key + ' = ' + properties[key] + '\n' for key in sorted(properties)).encode()
    generated = [_file('etc/nci.cfg', config_raw), _file('etc/new-subsources.tsv', ''.join('\t'.join(row) + '\n' for row in roots).encode()),
                 _file('etc/planned-termgroups.tsv', ''.join('\t'.join((token, *value)) + '\n' for token, value in sorted(tokens.items())).encode())]
    arguments = ['../' + native[role]['relative_path'] for role in ROLES]
    stages = [{'name': 'role-groups', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'create_rolegroups.pl', arguments[3]]},
              {'name': 'sort-role-groups', 'cwd': 'bin', 'argv': ['/usr/bin/sort', '../tmp/rolegroups.tmp', '-o', '../tmp/rolegroups.sorted.tmp']},
              {'name': 'repeated-role-groups', 'cwd': 'bin', 'argv': ['/usr/bin/uniq', '-d', '../tmp/rolegroups.sorted.tmp'], 'stdout': 'orig/rels_needing_relgrp.txt'},
              {'name': 'create-tref', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'create_tref.pl'] + arguments},
              {'name': 'deduplicate-tref', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'delete_dup_tref_lines.pl']},
              {'name': 'core-inversion', 'cwd': 'bin', 'argv': ['/usr/bin/perl', 'invert_NCI.pl']}]
    validation = {'profile': PROFILE, 'replacement_baseline': copy.deepcopy(prior), 'source_atom_ids': copy.deepcopy(bounds),
                  'saved_hierarchy_root': copy.deepcopy(identity), 'preserved_properties': copy.deepcopy(saved['properties']),
                  'source_plan': copy.deepcopy(plan), 'effective_properties': properties,
                  'publisher_vocabulary': {key: copy.deepcopy(model[key]) for key in required_vocab},
                  'publisher_termgroups': [list(row) for row in sorted(declared)], 'native_inputs': native,
                  'state_files': {STATE_ROLES[role]: {'sha256': row['sha256'], 'bytes': row['bytes']} for role, row in state_files.items()},
                  'template_sha256': None if template is None else _sha(template),
                  'fresh_capture_authenticated': False, 'preserved_inputs_only': True}
    return {'schema_version': 1, 'source': 'NCI', 'version': config['version'], 'engine_package': PACKAGE,
            'input_files': staged, 'generated_files': generated, 'symlinks': [], 'stages': stages,
            'output_files': list(OUTPUTS), 'validation': validation}


def _path(target, relative):
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts or str(name) != relative:
        raise ValueError('Unsafe candidate-relative path')
    path = Path(target) / str(name)
    if path.resolve() != path.absolute() or not path.is_file():
        raise ValueError('Expected an unlinked regular candidate file: ' + relative)
    return path


def _check_file(target, relative, expected):
    path = _path(target, relative)
    digest = hashlib.sha256();size = 0
    with path.open('rb') as handle:
        before = path.stat()
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(chunk);size += len(chunk)
        after = path.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Input changed during verification: ' + relative)
    if digest.hexdigest() != expected['sha256'] or ('bytes' in expected and size != expected['bytes']):
        raise ValueError('Candidate bytes differ from frozen input: ' + relative)
    return path


def _metadata(path, fields):
    rows = []
    with path.open('rb') as handle:
        for raw in handle:
            if not raw.endswith(b'\n') or b'\x00' in raw or b'\r' in raw:
                raise ValueError('Metadata requires UTF-8 pipe rows with final newlines')
            pieces = raw.decode('utf-8').removesuffix('\n').split('|')
            if len(pieces) != len(fields) + 1 or pieces[-1] != '':
                raise ValueError('Metadata row differs from the captured loader field contract')
            rows.append(dict(zip(fields, pieces[:-1])))
    if not rows or len({row[fields[0]] for row in rows}) != len(rows):
        raise ValueError('Empty or duplicate source/termgroup metadata')
    return rows


def validate_inputs(plan, target):
    """Verify real preserved metadata, generated bytes and every publisher row."""
    issues = [];facts = {'preserved_inputs_only': True, 'fresh_capture_authenticated': False}
    try:
        v = plan['validation']
        if not v['template_sha256']:
            raise ValueError('Pinned Git template verification is required for execution')
        for relative, descriptor in v['state_files'].items():
            _check_file(target, relative, descriptor)
        for item in plan['generated_files']:
            _check_file(target, item['relative_path'], item)
        actual = _properties(_path(target, 'etc/preserved-nci.cfg').read_bytes())
        if actual != v['preserved_properties']:
            raise ValueError('Actual preserved nci.cfg differs from its declared effective properties')
        sources = _metadata(_path(target, 'src/sources.src'), source_plan.SOURCE_FIELDS)
        groups = _metadata(_path(target, 'src/termgroups.src'), source_plan.TERMGROUP_FIELDS)
        primary = [row for row in sources if row['source_name'] == plan['version']]
        if len(primary) != 1 or primary[0]['low_source'] != v['replacement_baseline']['version']:
            raise ValueError('Physical source metadata differs from the explicit predecessor')
        source_names = {row['source_name'] for row in sources}
        suffix = _version(plan['version'])
        for row in sources:
            if row['source_name'] != row['normalized_source'] or row['source_name'] != row['stripped_source'] + '_' + suffix or row['version'] != suffix or row['source_family'] != 'NCI':
                raise ValueError('Physical source metadata has inconsistent identities/family/version')
        for row in groups:
            vsab, tty = row['termgroup_name'].rsplit('/', 1)
            if vsab not in source_names or tty != row['tty'] or any(row[key] not in ('Y', 'N') for key in source_plan.TERMGROUP_FIELDS[2:5]):
                raise ValueError('Physical termgroup metadata has inconsistent identities/flags')
        variables = {'release': suffix, 'replacement_release': _version(v['replacement_baseline']['version'])}
        for key, rows, fields, name, anchor in (('new_subsources', sources, source_plan.SOURCE_FIELDS, 'stripped_source', 'after_source'),
                                               ('new_termgroups', groups, source_plan.TERMGROUP_FIELDS, 'termgroup_name', 'after_termgroup')):
            additions = [source_plan.row(row['metadata'], fields, variables) for row in v['source_plan'][key]]
            reconstructed = [row for row in rows if row[name] not in {entry[name] for entry in additions}]
            for addition in v['source_plan'][key]:
                expected = source_plan.row(addition['metadata'], fields, variables)
                expected_anchor = source_plan.render(addition[anchor], variables)
                source_plan.insert(reconstructed, expected, expected_anchor, name)
            if reconstructed != rows:
                raise ValueError('Preserved metadata does not match explicit optional-addition row/order')
        native_counts = {}
        minimum = {'annotationDeclaration': 1, 'objectDeclaration': 1, 'classDeclaration': 3, 'relations': 4, 'hierarchy': 2}
        for role, item in v['native_inputs'].items():
            path = _check_file(target, item['relative_path'], item)
            count = 0
            with path.open('rb') as handle:
                for raw in handle:
                    count += 1
                    if not raw.endswith(b'\n') or b'\x00' in raw:
                        raise ValueError('Malformed publisher newline/NUL: ' + role)
                    row = raw.decode('utf-8').rstrip('\r\n').split('|')
                    if len(row) < minimum[role] or not row[0] or (role == 'hierarchy' and not row[1]) or (role in ('annotationDeclaration', 'objectDeclaration') and len(row) > 1 and 'label' in row[1] and len(row) < 3):
                        raise ValueError('Malformed physical publisher role: ' + role)
            if not count:
                raise ValueError('Empty publisher role: ' + role)
            native_counts[role] = count
        recipe = {'bindings': {'native_inputs': v['native_inputs']}, 'source_plan': {
            **v['publisher_vocabulary'], 'publisher_termgroups': v['publisher_termgroups'],
            'properties': v['effective_properties'], 'source_names': sorted(source_names),
            'historical_exceptions': v['source_plan']['historical_exceptions']}}
        discovery = source_plan.discover(recipe, Path(target))
        facts.update(native_rows=native_counts, source_rows=len(sources), termgroup_rows=len(groups), discovery=discovery)
        for row in discovery['historical_findings']:
            issues.append({'severity': 'warning', 'code': 'NCI_RETAINED_HISTORICAL_FINDING', 'message': row['identifier'] + ': ' + row['reason'], 'path': 'validation/source_plan'})
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError, OSError) as error:
        issues.append({'severity': 'error', 'code': 'NCI_PHYSICAL_INPUT_VALIDATION', 'message': str(error), 'path': 'inputs'})
    return {'passed': not any(row['severity'] in ('error', 'blocker') for row in issues), 'issues': issues, 'facts': facts}


def validate_outputs(plan, target):
    """Independent structures, digests, typed endpoints and full SAID bounds."""
    issues = [];facts = {'production_eligible': False}
    try:
        v = plan['validation']
        for relative, descriptor in v['state_files'].items():
            _check_file(target, relative, descriptor)
        for item in plan['generated_files']:
            _check_file(target, item['relative_path'], item)
        paths = {PurePosixPath(name).name: _path(target, name) for name in OUTPUTS}
        groups = _metadata(_path(target, 'src/termgroups.src'), source_plan.TERMGROUP_FIELDS)
        declared = {row['termgroup_name'].encode() for row in groups}
        structure = compare_nci_core.structure(paths, v['saved_hierarchy_root']['root_atom_id'], declared)
        facts['structure'] = structure
        if not structure['checks_passed']:
            raise ValueError('NCIt output structures, digests, termgroups or typed references failed')
        bounds = v['source_atom_ids']
        atoms = structure['atom_ids']
        if atoms['minimum'] < bounds['start'] or atoms['maximum'] > bounds['end']:
            raise ValueError('Emitted atom IDs escape the complete inclusive manifest range')
        sources = _metadata(_path(target, 'src/sources.src'), source_plan.SOURCE_FIELDS)
        known = {row['source_name'].encode() for row in sources} | {b'SRC'}
        atom_ids = set()
        with paths['classes_atoms.src'].open('rb') as handle:
            for row in handle:
                pieces = row.split(b'|', 3)
                value = pieces[0]
                if not value.isdigit() or int(value) <= 0 or str(int(value)).encode() != value or int(value) in atom_ids:
                    raise ValueError('Atom IDs must be canonical unique positive integers')
                atom_ids.add(int(value))
                if pieces[1] not in known or pieces[2].split(b'/', 1)[0] != pieces[1]:
                    raise ValueError('An emitted atom source/termgroup disagrees with preserved metadata')
        for name in ('attributes.src', 'relationships.src'):
            seen = set()
            with paths[name].open('rb') as handle:
                for row in handle:
                    value = row.split(b'|', 1)[0]
                    if not value.isdigit() or int(value) <= 0 or str(int(value)).encode() != value or value in seen:
                        raise ValueError('Duplicate/nonpositive generated row ID: ' + name)
                    seen.add(value)
        facts['source_atom_ids'] = {key: bounds[key] for key in ('start', 'end', 'bound_kind')}
    except (ValueError, KeyError, IndexError, TypeError, UnicodeError, OSError) as error:
        issues.append({'severity': 'error', 'code': 'NCI_OUTPUT_VALIDATION', 'message': str(error), 'path': 'src'})
    return {'passed': not issues, 'issues': issues, 'facts': facts}
