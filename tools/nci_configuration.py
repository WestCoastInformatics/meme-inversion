#!/usr/bin/env python3
"""Render NCIt compatibility settings from the common configuration and artifacts."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import nci_source_plan

PROFILE = 'nci-properties-v1'
PACKAGE = 'engines/nci'
ROLES = ('annotationDeclaration', 'objectDeclaration', 'classDeclaration', 'relations', 'hierarchy')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def properties(raw):
    result = {}
    for line in raw.decode().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('Malformed compatibility property')
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or key in result:
            raise ValueError('Duplicate/empty compatibility property: ' + key)
        result[key] = value
    return result


def release(version):
    if not isinstance(version, str) or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', version):
        raise ValueError('Unsupported NCIt version identity')
    return version.removeprefix('NCI_')


def positive(value):
    return type(value) is int and value > 0


def artifact(artifacts, reference, role):
    item = artifacts.get(reference)
    if not item or item['role'] != role or reference != 'sha256:' + digest(item['value']):
        raise ValueError('Missing or changed ' + role + ' artifact')
    return item['value']


def render_template(config, template, root):
    values = {'release': release(config['version']), 'source_atom_ids.start': str(config['source_atom_ids']['start']), 'identity_state.root_atom_id': str(root['root_atom_id'])}
    text = base64.b64decode(template['data_b64'], validate=True).decode()
    if set(re.findall(r'\{\{([^{}]+)\}\}', text)) != set(values):
        raise ValueError('Unreviewed or incomplete template parameters')
    text = re.sub(r'\{\{([^{}]+)\}\}', lambda match: values[match[1]], text)
    if '{{' in text or '}}' in text:
        raise ValueError('Unresolved template parameter')
    return text.encode()


def generate(config, artifacts, template, metadata_model=None):
    if config['source'] != 'NCI' or config['source_options'] != {} or config['inputs']['source_data_stage'] != 'publisher':
        raise ValueError('Unsupported NCIt configuration/options/input stage')
    current = release(config['version'])
    prior = config['replacement_baseline']
    if not isinstance(prior, dict) or prior.get('source') != 'NCI' or release(prior.get('version')) >= current:
        raise ValueError('An explicit earlier NCIt replacement baseline is required')
    if not re.fullmatch('[0-9a-f]{40}', config['engine_ref']):
        raise ValueError('An immutable source engine commit is required')
    if config['output_stage'] != 'inversion-src' or config['publisher_history'] or config['comparison_baseline'] is not None:
        raise ValueError('This core profile has no additional history/change-detection stages')
    policy = artifact(artifacts, config['policy_ref'], 'nci-representation-policy')
    planned = policy['profile'] == nci_source_plan.PROFILE
    if policy['profile'] not in (PROFILE, nci_source_plan.PROFILE) or policy['engine_ref'] != config['engine_ref']:
        raise ValueError('Policy/source engine differs')
    raw = base64.b64decode(template['data_b64'], validate=True)
    if template['repository_path'] != PACKAGE + '/nci.cfg.in' or template['repository_path'] != policy['template_repository_path'] or sha(raw) != template['sha256'] or template['sha256'] != policy['template_sha256']:
        raise ValueError('Configuration template differs from pinned policy')
    root = artifact(artifacts, config['inputs']['identity_state'], 'saved-hierarchy-root')
    if not positive(root['root_atom_id']):
        raise ValueError('Invalid saved root identity')
    bounds = config['source_atom_ids']
    proof = artifact(artifacts, bounds['provenance_ref'], 'isolated-historical-ID-range')
    if not positive(bounds['start']) or not positive(bounds['end']) or bounds['start'] > bounds['end'] or (bounds['start'], bounds['end']) != (proof['start'], proof['end']):
        raise ValueError('Complete ID bounds differ from their evidence')
    if bounds.get('bound_kind') != 'historical-emitted-range' or proof['production_reservation'] is not False:
        raise ValueError('This profile consumes observed historical IDs, not a new production reservation')
    plan = artifact(artifacts, config['inputs']['source_plan'], 'reviewed-nci-source-plan' if planned else 'reviewed-historical-transition')
    for key in ('replacement_baseline', 'comparison_baseline', 'publisher_history'):
        if plan[key] != config[key]:
            raise ValueError('Release plan differs: ' + key)
    if len(config['inputs']['source_data']) != 1:
        raise ValueError('One complete native export bundle is required')
    native = artifact(artifacts, config['inputs']['source_data'][0], 'source-data')
    inputs = {}
    for item in native:
        path = PurePosixPath(item['path'])
        match = re.fullmatch(r'(annotationDeclaration|objectDeclaration|classDeclaration|relations|hierarchy)-[0-9]{8}\.txt', path.name)
        if path.is_absolute() or '..' in path.parts or path.parent.as_posix() != config['version'] + '/orig/fromprovider' or not match or match[1] in inputs or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Unexpected, ambiguous or unsafe native input')
        inputs[match[1]] = {'relative_path': path.relative_to(config['version']).as_posix(), 'sha256': item['sha256']}
    if set(inputs) != set(ROLES) or len(native) != 5:
        raise ValueError('All five distinct native input roles are required')
    metadata = artifact(artifacts, config['inputs']['reference_ncimeta'], 'reviewed-nci-metadata-model' if planned else 'preserved-reference-metadata')
    if planned:
        if not metadata_model or metadata_model['repository_path'] != PACKAGE + '/metadata-policy.json' or metadata_model['repository_path'] != metadata['repository_path'] or metadata_model['sha256'] != metadata['sha256']:
            raise ValueError('Missing or substituted reviewed metadata model')
        model_raw = base64.b64decode(metadata_model['data_b64'], validate=True)
        if sha(model_raw) != metadata_model['sha256']:
            raise ValueError('Metadata model bytes changed')
    elif len(metadata) != 2 or {x['path'] for x in metadata} != {config['version'] + '/src/' + x for x in ('sources.src', 'termgroups.src')}:
        raise ValueError('The two declared source metadata files are required')
    rendered = render_template(config, template, root)
    props = properties(rendered)
    source_plan = None
    if planned:
        source_plan = nci_source_plan.generate(config, plan, nci_source_plan.load(model_raw), props)
        if any(x['native_sha256'] != {PurePosixPath(item['relative_path']).name: item['sha256'] for item in inputs.values()} for x in source_plan['historical_exceptions']):
            raise ValueError('Historical exception differs from the complete native input manifest')
        # Preserve all effective legacy properties and append only reviewed additions.
        props = source_plan['properties']
        rendered = ''.join(key + ' = ' + value + '\n' for key, value in props.items()).encode()
    if props['VSAB'] != config['version'] or props['RSAB'] != config['source'] or props['HC.RootNodeCode'] != root['root_code'] or props['HC.RootNodeName'] != root['root_name']:
        raise ValueError('Generated source/root properties differ from the plan')
    paths = {key: '../' + item['relative_path'] for key, item in inputs.items()}
    result = {'profile': policy['profile'], 'template': template,
            'files': [{'relative_path': 'etc/nci.cfg', 'mode': '0o444', 'sha256': sha(rendered), 'data_b64': base64.b64encode(rendered).decode()}],
            'preparation_arguments': {'role-groups': [paths['relations']], 'create-tref': [paths[role] for role in ROLES]},
            'bindings': {'source': config['source'], 'version': config['version'], 'engine_ref': config['engine_ref'],
                         'replacement_baseline': prior, 'comparison_baseline': config['comparison_baseline'], 'publisher_history': config['publisher_history'],
                         'source_atom_ids': bounds, 'identity_state': root, 'native_inputs': inputs,
                         'metadata_inputs': [] if planned else metadata, 'policy_ref': config['policy_ref']}}
    if planned:
        result.update(metadata_model=metadata_model, source_plan=source_plan)
        result['files'] += source_plan['files']
    return result


def from_lock(lock):
    spec = lock['case'].get('configuration_generation')
    recipe = lock.get('configuration_generation')
    if not spec or not recipe or spec['profile'] not in (PROFILE, nci_source_plan.PROFILE) or spec['profile'] != recipe['profile']:
        raise ValueError('Missing reviewed configuration-generation contract')
    if any(recipe['template'][key] != spec[key] for key in ('repository_path', 'sha256')):
        raise ValueError('Frozen template differs from reviewed case')
    expected = generate(lock['configuration'], lock['case']['artifacts'], recipe['template'], recipe.get('metadata_model'))
    if recipe != expected:
        raise ValueError('Generated compatibility settings or bindings changed')
    legacy = lock['case']['legacy_case']
    native = {lock['configuration']['version'] + '/' + x['relative_path']: x['sha256'] for x in expected['bindings']['native_inputs'].values()}
    metadata = expected['bindings']['metadata_inputs']
    if expected['profile'] == nci_source_plan.PROFILE:
        if recipe['metadata_model']['repository_path'] != spec['metadata_repository_path'] or recipe['metadata_model']['sha256'] != spec['metadata_sha256']:
            raise ValueError('Frozen metadata model differs from reviewed case')
        # Historical metadata is an independent expected result, never a seed file.
        metadata = [{'path': lock['configuration']['version'] + '/' + x['relative_path'], 'sha256': x['sha256']} for x in expected['files'] if x['relative_path'].startswith('src/')]
        if {x['path']: x['sha256'] for x in metadata} != {x['path']: x['sha256'] for x in legacy['archived_metadata_inputs']}:
            raise ValueError('Generated metadata differs from the historical compatibility oracle')
    if native != {x['path']: x['sha256'] for x in legacy['native_inputs']} or (expected['profile'] == PROFILE and metadata != legacy['archived_metadata_inputs']) or legacy['replacement_baseline'] != lock['configuration']['replacement_baseline']:
        raise ValueError('Legacy preparation inputs/baseline differ from the common plan')
    return expected


def verify_metadata(recipe, target):
    bindings = recipe['bindings']
    if recipe['profile'] == nci_source_plan.PROFILE:
        for item in recipe['files']:
            if item['relative_path'].startswith('src/'):
                path = target / item['relative_path']
                if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != item['sha256']:
                    raise ValueError('Generated source metadata changed')
    for item in bindings['metadata_inputs']:
        path = target / PurePosixPath(item['path']).relative_to(bindings['version'])
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != item['sha256']:
            raise ValueError('Frozen source metadata changed')
    rows = [line.split('|') for line in (target / 'src/sources.src').read_text().splitlines() if line.startswith(bindings['version'] + '|')]
    if len(rows) != 1 or rows[0][1] != bindings['replacement_baseline']['version']:
        raise ValueError('Replacement baseline disagrees with saved source metadata')


def verify_files(recipe, target):
    for item in recipe['files']:
        path = target / item['relative_path']
        if path.is_symlink() or not path.is_file() or sha(path.read_bytes()) != item['sha256'] or path.stat().st_mode & 0o222:
            raise ValueError('Generated configuration changed or is writable')


def receipt(recipe):
    result = {**{key: value for key, value in recipe.items() if key not in ('template', 'files', 'metadata_model', 'source_plan')},
            'template': {key: value for key, value in recipe['template'].items() if key != 'data_b64'},
            'files': [{key: value for key, value in item.items() if key != 'data_b64'} for item in recipe['files']]}
    if 'metadata_model' in recipe:
        result['metadata_model'] = {key: value for key, value in recipe['metadata_model'].items() if key != 'data_b64'}
        result['source_plan'] = {key: recipe['source_plan'][key] for key in ('new_subsources', 'new_termgroups', 'historical_exceptions')}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lock', type=Path)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument('--output-dir', type=Path)
    output.add_argument('--metadata-policy-preview', type=Path)
    args = parser.parse_args()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    lock = json.loads(args.lock.read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + value)))
    if lock['lock_sha256'] != digest({key: value for key, value in lock.items() if key != 'lock_sha256'}):
        raise ValueError('Run lock changed')
    recipe = from_lock(lock)
    if args.metadata_policy_preview:
        if recipe['profile'] != nci_source_plan.PROFILE:
            raise ValueError('Metadata-policy promotion requires a reviewed source plan')
        config = lock['configuration']
        model = nci_source_plan.load(base64.b64decode(recipe['metadata_model']['data_b64']))
        plan = lock['case']['artifacts'][config['inputs']['source_plan']]['value']
        base_properties = properties(render_template(config, recipe['template'], recipe['bindings']['identity_state']))
        promoted = nci_source_plan.promote_model(config, plan, model, base_properties)
        promoted['provenance'].update(base_model_file_sha256=recipe['metadata_model']['sha256'], base_engine_ref=config['engine_ref'],
            input_lock_apparatus_ref=lock['apparatus_ref'], generator_sha256={
                'nci_configuration.py': sha(Path(__file__).read_bytes()),
                'nci_source_plan.py': sha(Path(nci_source_plan.__file__).read_bytes())})
        with args.metadata_policy_preview.open('x') as handle:
            json.dump(promoted, handle, indent=2, ensure_ascii=False, sort_keys=True);handle.write('\n')
        args.metadata_policy_preview.chmod(0o444)
        print(json.dumps({'metadata_policy_preview': str(args.metadata_policy_preview), 'requires_review': True, 'installed_state_updated': False}))
        raise SystemExit(0)
    args.output_dir.mkdir()  # never replace an existing rendered plan
    for item in recipe['files']:
        path = args.output_dir / item['relative_path'];path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(base64.b64decode(item['data_b64'], validate=True))
        path.chmod(int(item['mode'], 8))
    (args.output_dir / 'configuration-generation.json').write_text(json.dumps(receipt(recipe), indent=2) + '\n')
    print(json.dumps({'version': recipe['bindings']['version'], 'output_dir': str(args.output_dir), 'files': receipt(recipe)['files']}))
