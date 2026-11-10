#!/usr/bin/env python3
"""Render NCIt compatibility settings from the common configuration and artifacts."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

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


def generate(config, artifacts, template):
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
    if policy['profile'] != PROFILE or policy['engine_ref'] != config['engine_ref']:
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
    plan = artifact(artifacts, config['inputs']['source_plan'], 'reviewed-historical-transition')
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
    metadata = artifact(artifacts, config['inputs']['reference_ncimeta'], 'preserved-reference-metadata')
    if len(metadata) != 2 or {x['path'] for x in metadata} != {config['version'] + '/src/' + x for x in ('sources.src', 'termgroups.src')}:
        raise ValueError('The two declared source metadata files are required')
    values = {'release': current, 'source_atom_ids.start': str(bounds['start']), 'identity_state.root_atom_id': str(root['root_atom_id'])}
    text = raw.decode()
    if set(re.findall(r'\{\{([^{}]+)\}\}', text)) != set(values):
        raise ValueError('Unreviewed or incomplete template parameters')
    text = re.sub(r'\{\{([^{}]+)\}\}', lambda match: values[match[1]], text)
    if '{{' in text or '}}' in text:
        raise ValueError('Unresolved template parameter')
    rendered = text.encode()
    props = properties(rendered)
    if props['VSAB'] != config['version'] or props['RSAB'] != config['source'] or props['HC.RootNodeCode'] != root['root_code'] or props['HC.RootNodeName'] != root['root_name']:
        raise ValueError('Generated source/root properties differ from the plan')
    paths = {key: '../' + item['relative_path'] for key, item in inputs.items()}
    return {'profile': PROFILE, 'template': template,
            'files': [{'relative_path': 'etc/nci.cfg', 'mode': '0o444', 'sha256': sha(rendered), 'data_b64': base64.b64encode(rendered).decode()}],
            'preparation_arguments': {'role-groups': [paths['relations']], 'create-tref': [paths[role] for role in ROLES]},
            'bindings': {'source': config['source'], 'version': config['version'], 'engine_ref': config['engine_ref'],
                         'replacement_baseline': prior, 'comparison_baseline': config['comparison_baseline'], 'publisher_history': config['publisher_history'],
                         'source_atom_ids': bounds, 'identity_state': root, 'native_inputs': inputs,
                         'metadata_inputs': metadata, 'policy_ref': config['policy_ref']}}


def from_lock(lock):
    spec = lock['case'].get('configuration_generation')
    recipe = lock.get('configuration_generation')
    if not spec or not recipe or spec['profile'] != PROFILE:
        raise ValueError('Missing reviewed configuration-generation contract')
    if any(recipe['template'][key] != spec[key] for key in ('repository_path', 'sha256')):
        raise ValueError('Frozen template differs from reviewed case')
    expected = generate(lock['configuration'], lock['case']['artifacts'], recipe['template'])
    if recipe != expected:
        raise ValueError('Generated compatibility settings or bindings changed')
    legacy = lock['case']['legacy_case']
    native = {lock['configuration']['version'] + '/' + x['relative_path']: x['sha256'] for x in expected['bindings']['native_inputs'].values()}
    if native != {x['path']: x['sha256'] for x in legacy['native_inputs']} or expected['bindings']['metadata_inputs'] != legacy['archived_metadata_inputs'] or legacy['replacement_baseline'] != lock['configuration']['replacement_baseline']:
        raise ValueError('Legacy preparation inputs/baseline differ from the common plan')
    return expected


def verify_metadata(recipe, target):
    bindings = recipe['bindings']
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
    return {**{key: value for key, value in recipe.items() if key not in ('template', 'files')},
            'template': {key: value for key, value in recipe['template'].items() if key != 'data_b64'},
            'files': [{key: value for key, value in item.items() if key != 'data_b64'} for item in recipe['files']]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lock', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    lock = json.loads(args.lock.read_text(), object_pairs_hook=unique)
    if lock['lock_sha256'] != digest({key: value for key, value in lock.items() if key != 'lock_sha256'}):
        raise ValueError('Run lock changed')
    recipe = from_lock(lock)
    args.output_dir.mkdir()  # never replace an existing rendered plan
    for item in recipe['files']:
        path = args.output_dir / item['relative_path'];path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(base64.b64decode(item['data_b64'], validate=True))
        path.chmod(int(item['mode'], 8))
    (args.output_dir / 'configuration-generation.json').write_text(json.dumps(receipt(recipe), indent=2) + '\n')
    print(json.dumps({'version': recipe['bindings']['version'], 'output_dir': str(args.output_dir), 'files': receipt(recipe)['files']}))
