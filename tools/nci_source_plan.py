#!/usr/bin/env python3
"""Render reviewed NCIt metadata/additions and reject unreviewed native values."""
import base64
import hashlib
import json
from pathlib import Path
import re

PROFILE = 'nci-source-plan-v1'
SOURCE_FIELDS = ('source_name', 'low_source', 'restriction_level', 'normalized_source',
                 'stripped_source', 'version', 'source_family', 'official_name',
                 'nlm_contact', 'acquisition_contact', 'content_contact', 'license_contact',
                 'inverter', 'context_type', 'url', 'language', 'citation', 'license_info',
                 'character_set', 'rel_directionality_flag')
TERMGROUP_FIELDS = ('termgroup_name', 'low_termgroup', 'suppressible_flag', 'exclude_flag',
                    'norm_exclude_flag', 'tty')
ROOTS = 'etc/new-subsources.tsv'
TOKENS = 'etc/planned-termgroups.tsv'
NORMALIZATIONS = ((r'CTCAE 3\.0', 'CTCAE_3'), (r'CTCAE 5\.0', 'CTCAE_5'),
                  (r'BRIDG 3\.0\.3', 'BRIDG_3_0_3'), (r'BRIDG 5\.3', 'BRIDG_5_3'),
                  ('ACC/AHA', 'ACC-AHA'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate source-plan key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Missing or unknown ' + label + ' fields')


def text(value):
    if not isinstance(value, str) or any(c in value for c in '|\r\n\t\x00'):
        raise ValueError('Unsafe metadata/plan value')
    return value


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', text(value)):
        raise ValueError('Invalid source/term-type identifier')
    return value


def render(value, variables):
    value = text(value)
    for key, replacement in variables.items():
        value = value.replace('{{' + key + '}}', replacement)
    if '{{' in value or '}}' in value:
        raise ValueError('Unknown metadata template parameter')
    return value


def row(value, fields, variables):
    keys(value, fields, 'metadata')
    return {key: render(value[key], variables) for key in fields}


def insert(rows, item, after, key):
    positions = [i for i, value in enumerate(rows) if value[key] == after]
    if len(positions) != 1:
        raise ValueError('No unique metadata insertion anchor: ' + after)
    rows.insert(positions[0] + 1, item)


def ranking(rows, name, low, external):
    names = [x[name] for x in rows]
    if len(names) != len(set(names)):
        raise ValueError('Duplicate metadata identity')
    links = {x[name]: x[low] for x in rows}
    for start in names:
        seen = set()
        node = start
        while node in links:
            if node in seen:
                raise ValueError('Cyclic metadata ranking: ' + start)
            seen.add(node)
            node = links[node]
        if node not in external:
            raise ValueError('Unknown metadata ranking target: ' + node)


def file_record(path, raw):
    return {'relative_path': path, 'mode': '0o444', 'sha256': sha(raw),
            'data_b64': base64.b64encode(raw).decode()}


def generate(config, plan, model, properties):
    keys(plan, ('schema_version', 'source', 'version', 'replacement_baseline',
                'comparison_baseline', 'publisher_history', 'new_subsources',
                'new_termgroups', 'property_updates', 'historical_exceptions'), 'source plan')
    if type(plan['schema_version']) is not int or plan['schema_version'] != 1 or model['schema_version'] != 1 or model['source'] != 'NCI':
        raise ValueError('Unsupported source plan or metadata model')
    for key in ('source', 'version', 'replacement_baseline', 'comparison_baseline', 'publisher_history'):
        if plan[key] != config[key]:
            raise ValueError('Source plan differs from common configuration: ' + key)
    for key in ('new_subsources', 'new_termgroups', 'historical_exceptions'):
        if not isinstance(plan[key], list):
            raise ValueError('Explicit addition/exception arrays are required')
    variables = {'release': config['version'].removeprefix('NCI_'),
                 'replacement_release': config['replacement_baseline']['version'].removeprefix('NCI_')}
    for exception in plan['historical_exceptions']:
        keys(exception, ('kind', 'identifier', 'reason', 'version', 'native_sha256'), 'historical exception')
        if exception['kind'] not in ('unmapped-publisher-source', 'unverified-termgroup-ranking') or exception['version'] != config['version'] or not text(exception['reason']) or not text(exception['identifier']) or not isinstance(exception['native_sha256'], dict):
            raise ValueError('Unbound historical exception')
    sources = [row(x, SOURCE_FIELDS, variables) for x in model['sources']]
    groups = [row(x, TERMGROUP_FIELDS, variables) for x in model['termgroups']]
    previous_sources = {x['stripped_source'] + '_' + variables['replacement_release'] for x in sources}
    previous_groups = {x['termgroup_name'].replace('_' + variables['release'] + '/', '_' + variables['replacement_release'] + '/') for x in groups}
    previous_groups.update(x['identifier'] for x in plan['historical_exceptions'] if x['kind'] == 'unverified-termgroup-ranking')
    props = dict(properties)
    roots, tokens, added_sources = [], {}, set()
    def bind(key, value):
        if key in props and props[key] != value:
            raise ValueError('Addition conflicts with existing representation policy: ' + key)
        props[key] = value
    for addition in plan['new_subsources']:
        keys(addition, ('metadata', 'after_source', 'publisher_names', 'root'), 'new subsource')
        entry = row(addition['metadata'], SOURCE_FIELDS, variables)
        source = identifier(entry['stripped_source'])
        if source in added_sources:
            raise ValueError('Duplicate new-subsource decision: ' + source)
        # The catalog defines known representation, not installed root state.
        # A first-release decision replaces its default established-source rank.
        sources = [x for x in sources if x['stripped_source'] != source]
        keys(addition['root'], ('preferred_term', 'short_name'), 'root')
        names = addition['publisher_names']
        if not isinstance(names, list) or not names or len(names) != len(set(names)):
            raise ValueError('Unique publisher aliases required')
        for name in names:
            if not text(name) or any(x in name for x in "='\""):
                raise ValueError('Invalid publisher alias')
            bind('vsab.' + name, entry['source_name'])
            bind('rsab.' + name, source)
        short = text(addition['root']['short_name'])
        preferred = text(addition['root']['preferred_term'])
        if not preferred or not short:
            raise ValueError('Complete root names required')
        bind(entry['source_name'] + '.RSSN', short)
        insert(sources, entry, identifier(addition['after_source']), 'stripped_source')
        roots.append((source, preferred, short))
        added_sources.add(source)
        if "'" + source + "'" not in props['CFG2RSAB']:
            props['CFG2RSAB'] += ", '" + source + "'"
    if not isinstance(plan['property_updates'], dict):
        raise ValueError('Typed term-type mappings required')
    for key, value in plan['property_updates'].items():
        if not re.fullmatch(r'(in2tty|in2Otty|inl2tty)\.[A-Za-z0-9_-]+', key):
            raise ValueError('Only explicit new term-type mappings are allowed')
        bind(key, identifier(value))
    declared = {tuple(x) for x in model['publisher_termgroups']}
    added_groups = set()
    for addition in plan['new_termgroups']:
        keys(addition, ('metadata', 'after_termgroup', 'input_ttys'), 'new termgroup')
        entry = row(addition['metadata'], TERMGROUP_FIELDS, variables)
        if entry['termgroup_name'] in added_groups:
            raise ValueError('Duplicate new-termgroup decision')
        added_groups.add(entry['termgroup_name'])
        groups = [x for x in groups if x['termgroup_name'] != entry['termgroup_name']]
        vsab, tty = entry['termgroup_name'].rsplit('/', 1)
        aliases = [key[5:] for key, value in props.items() if key.startswith('vsab.') and value == vsab]
        if vsab == props['VSAB']:
            aliases = [props['RSAB']]
        inputs = addition['input_ttys']
        if not aliases or not isinstance(inputs, list) or not inputs or len(inputs) != len(set(inputs)):
            raise ValueError('New termgroup needs unambiguous publisher bindings')
        for incoming in inputs:
            identifier(incoming)
            output = incoming if incoming in ('PT', 'SY') else props.get('in2tty.' + incoming, props.get('in2Otty.' + incoming, props.get('inl2tty.' + incoming)))
            if output != tty:
                raise ValueError('New native term type lacks its reviewed output mapping')
            for alias in aliases:
                token = alias + incoming
                if token in tokens and tokens[token] != (alias, incoming):
                    raise ValueError('Ambiguous native source/term-type concatenation')
                tokens[token] = (alias, incoming)
                declared.add((alias, incoming))
        insert(groups, entry, render(addition['after_termgroup'], variables), 'termgroup_name')
    source_names = {x['source_name'] for x in sources}
    for entry in sources:
        if entry['source_name'] != entry['normalized_source'] or entry['source_name'] != entry['stripped_source'] + '_' + variables['release'] or entry['version'] != variables['release'] or entry['source_family'] != 'NCI' or entry['restriction_level'] not in ('0', '1', '2', '3'):
            raise ValueError('Inconsistent source metadata identity')
    for entry in groups:
        vsab, tty = entry['termgroup_name'].rsplit('/', 1)
        if vsab not in source_names or tty != entry['tty'] or any(entry[key] not in ('Y', 'N') for key in TERMGROUP_FIELDS[2:5]):
            raise ValueError('Inconsistent termgroup identity/flags')
    if any(not any(name.startswith(source + '_' + variables['release'] + '/') for name in added_groups) for source in added_sources):
        raise ValueError('New subsource has no declared termgroups')
    previous_sources -= {source + '_' + variables['replacement_release'] for source in added_sources}
    previous_groups -= {name.replace('_' + variables['release'] + '/', '_' + variables['replacement_release'] + '/') for name in added_groups}
    previous_groups = {name for name in previous_groups if not any(name.startswith(source + '_' + variables['replacement_release'] + '/') for source in added_sources)}
    ranking(sources, 'source_name', 'low_source', previous_sources)
    ranking(groups, 'termgroup_name', 'low_termgroup', previous_groups)
    main = [x for x in sources if x['source_name'] == config['version']]
    if len(main) != 1 or main[0]['low_source'] != config['replacement_baseline']['version']:
        raise ValueError('Metadata replacement baseline differs from the common plan')
    if config['source_atom_ids']['end'] - config['source_atom_ids']['start'] + 1 < 2 * len(sources) + 3 * len(roots):
        raise ValueError('Declared ID range cannot contain even the required SRC atoms')
    serialize = lambda rows, fields: ''.join('|'.join(x[key] for key in fields) + '|\n' for x in rows).encode()
    files = [file_record('src/sources.src', serialize(sources, SOURCE_FIELDS)),
             file_record('src/termgroups.src', serialize(groups, TERMGROUP_FIELDS)),
             file_record(ROOTS, ''.join('\t'.join(x) + '\n' for x in roots).encode()),
             file_record(TOKENS, ''.join('\t'.join((key, *value)) + '\n' for key, value in sorted(tokens.items())).encode())]
    props['NCI.SourcePlan.Roots'] = '../' + ROOTS
    props['NCI.SourcePlan.Termgroups'] = '../' + TOKENS
    return {'files': files, 'properties': props, 'publisher_termgroups': [list(x) for x in sorted(declared)],
            'source_names': sorted(source_names), 'historical_exceptions': plan['historical_exceptions'],
            'publisher_properties': model['publisher_properties'], 'publisher_labels': model['publisher_labels'],
            'relationship_roles': model['relationship_roles'],
            'new_subsources': [x[0] for x in roots], 'new_termgroups': len(plan['new_termgroups'])}


def discover(recipe, target):
    """Inspect all pinned exports before invoking a producer or publishing a tree."""
    policy = recipe['source_plan']
    declared = {tuple(x) for x in policy['publisher_termgroups']}
    properties = policy['properties']
    observed, used, roles, labels, maps = set(), set(), set(), {}, set()
    identities = {}
    for role, item in recipe['bindings']['native_inputs'].items():
        path = target / item['relative_path']
        if path.is_symlink() or not path.is_file():
            raise ValueError('Missing regular native input')
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for raw in handle:
                digest.update(raw)
                line = raw.decode('utf-8').rstrip('\r\n')
                for old, new in NORMALIZATIONS:
                    line = re.sub(old, new, line, count=1)
                fields = line.split('|')
                if role == 'classDeclaration':
                    if len(fields) < 3:
                        raise ValueError('Malformed native class record')
                    used.add(fields[1])
                    if fields[1] == 'P90':
                        if len(fields) < 7 or fields[3] != 'P383' or fields[5] != 'P384':
                            raise ValueError('Unreviewed native termgroup qualifier structure')
                        observed.add((fields[6], fields[4]))
                    if fields[1] == 'P375':
                        maps.add(fields[4] if len(fields) > 4 else '')
                elif role in ('annotationDeclaration', 'objectDeclaration') and len(fields) > 2 and 'label' in fields[1]:
                    if fields[0] in labels and labels[fields[0]] != fields[2]:
                        raise ValueError('Conflicting publisher property labels')
                    labels[fields[0]] = fields[2]
                elif role == 'relations':
                    if len(fields) < 4:
                        raise ValueError('Malformed native relationship')
                    roles.add(fields[2])
        identities[path.name] = digest.hexdigest()
        if digest.hexdigest() != item['sha256']:
            raise ValueError('Native input identity differs: ' + path.name)
    if any(x['native_sha256'] != identities for x in policy['historical_exceptions']):
        raise ValueError('Historical findings are bound to a different native input set')
    findings = [x for x in policy['historical_exceptions'] if x['kind'] == 'unverified-termgroup-ranking']
    exceptions = {x['identifier']: x for x in policy['historical_exceptions'] if x['kind'] == 'unmapped-publisher-source'}
    for source, tty in sorted(observed):
        if (source, tty) not in declared:
            raise ValueError('Unreviewed publisher source/term type: ' + source + '/' + tty)
        mapped = properties['VSAB'] if source == properties['RSAB'] else properties.get('vsab.' + source)
        if mapped not in policy['source_names']:
            exception = exceptions.get(source)
            if not exception or exception['native_sha256'] != identities:
                raise ValueError('Publisher source lacks reviewed metadata/mapping: ' + source)
            if exception not in findings:
                findings.append(exception)
    if used - set(policy['publisher_properties']) or roles - set(policy['relationship_roles']):
        raise ValueError('Unreviewed publisher property or relationship role')
    for key in used | roles:
        if key in policy['publisher_labels'] and labels.get(key) != policy['publisher_labels'][key]:
            raise ValueError('Publisher representation label changed: ' + key)
    if maps - {'Has Synonym', 'Broader Than', 'Narrower Than', 'Related To'}:
        raise ValueError('Unreviewed Maps_To relationship')
    return {'status': 'PASS_HISTORICAL_WITH_DECLARED_FINDINGS' if findings else 'PASS',
            'native_inputs': identities, 'publisher_termgroups_observed': len(observed),
            'publisher_properties_observed': len(used), 'relationship_roles_observed': len(roles),
            'historical_findings': findings, 'production_eligible': False}
