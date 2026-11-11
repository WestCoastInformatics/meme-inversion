#!/usr/bin/env python3
"""Resolve a release manifest into a committed, dev-only native execution capsule.

Historical replay cases are independent oracles, never release admission records.
This module runs locally; the frozen worker and source adapters use the stdlib.
"""
import ast
import base64
import importlib
import posixpath
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import inversion_request as historical
import release_manifest as manifests

ROOT = historical.ROOT
PROFILES = ROOT / 'docs/inversion-review/native-execution-profiles.json'
HANDLERS = {'nci-publisher-inputs-v1': 'execute_release_nci',
            'snomed-us-snapshot-inputs-v1': 'execute_release_snomed',
            'mth-prepared-inputs-v1': 'execute_release_mth'}
DEFERRED = {'INPUT_BYTES_UNVERIFIED', 'PREFLIGHT_NOT_EXECUTION_AUTHORITY',
            'NCI_PUBLISHER_DISCOVERY_REQUIRED', 'NCI_HISTORICAL_ALLOCATION_ONLY',
            'NCI_PHYSICAL_INPUT_VALIDATION_REQUIRED'}


def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('A canonical relative path is required')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) != value or value == '.':
        raise ValueError('A canonical relative path is required: ' + value)
    return value


def file_record(raw, relative_path, mode='0o444'):
    return {'relative_path': relative_path, 'mode': mode, 'bytes': len(raw),
            'sha256': manifests.hashlib.sha256(raw).hexdigest(),
            'data_b64': base64.b64encode(raw).decode()}


def verify_locations(manifest, target):
    for artifact in manifest['artifacts'].values():
        for file in artifact['files']:
            parsed = urlsplit(file['uri'])
            if parsed.scheme != 'file' or parsed.netloc:
                raise ValueError('Native admission needs standard local file/cache descriptors; acquisition may populate a missing declared cache')
            local = Path(posixpath.normpath(unquote(parsed.path)))
            if not local.is_relative_to(target.parents[2]):
                raise ValueError('Native inputs must use the mirrored MEME storage paths on dev')
            if local.is_relative_to(target):
                raise ValueError('Input/oracle is inside the replaceable current source folder; bind an independent archive member or stable publisher cache')
            if local.is_relative_to(target.parent) and len(local.relative_to(target.parent).parts) > 1:
                raise ValueError('Input/oracle is inside a replaceable source tree; bind an independent archive member or immutable input cache so older replays cannot invalidate it')


def verify_profile(profile):
    fields = {'handler', 'engine_package', 'reviewed_package_sha256', 'runtime_ref',
              'runtime_inventory_sha256', 'minimum_free_disk_gib', 'pull_helper_sha256'}
    if set(profile) != fields or profile['handler'] not in HANDLERS.values():
        raise ValueError('Unsupported native source capability fields')
    relative(profile['engine_package'])
    if not profile['engine_package'].startswith('engines/'):
        raise ValueError('Native code must use a canonical Git engine package')
    if type(profile['minimum_free_disk_gib']) is not int or profile['minimum_free_disk_gib'] < 12:
        raise ValueError('Native capacity floor must preserve the fixed disk reserve')
    if not re.fullmatch(r'[0-9a-f]{40}', profile['runtime_ref']):raise ValueError('Native runtime requires a full pinned Git commit')
    if not isinstance(profile['reviewed_package_sha256'], list) or any(not re.fullmatch(r'[0-9a-f]{64}', v) for v in profile['reviewed_package_sha256']):
        raise ValueError('Invalid reviewed native package identities')
    for key in ('runtime_inventory_sha256', 'pull_helper_sha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', profile[key]):raise ValueError('Invalid native capability digest')


def verify_plan(plan, manifest, code_files=()):
    config, artifacts = manifest['configuration'], manifest['artifacts']
    required = {'schema_version', 'source', 'version', 'engine_package', 'input_files',
                'generated_files', 'symlinks', 'stages', 'output_files', 'validation'}
    if not required <= set(plan) or plan['schema_version'] != 1:
        raise ValueError('Source execution plan has an unsupported contract')
    if (plan['source'], plan['version']) != (config['source'], config['version']):
        raise ValueError('Source execution plan release identity differs')
    excluded = set(plan.get('code_excludes', []))
    code_names = {relative(item['relative_path']) for item in code_files}
    if not excluded <= code_names:raise ValueError('Plan excludes unrecognized code paths')
    destinations = {('candidate', name) for name in code_names - excluded}
    for item in plan['input_files']:
        scope = item.get('scope', 'candidate')
        destination = relative(item['destination'])
        if scope not in ('candidate', 'inv', 'meme'):
            raise ValueError('Unsupported input destination scope')
        if (scope, destination) in destinations:
            raise ValueError('Two inputs have the same destination')
        destinations.add((scope, destination))
        artifact = artifacts[item['artifact']]
        matches = [file for file in artifact['files'] if file['role'] == item['role']]
        if len(matches) != 1 or artifact['artifact_type'] == 'reference-inversion':
            raise ValueError('Candidate input requires one independent non-reference file')
        if scope == 'inv':
            allowed = {v['version'] for v in (config['replacement_baseline'], config['comparison_baseline']) if v}
            allowed |= {artifacts[name]['version'] for name in config['publisher_history']}
            parts = PurePosixPath(destination).parts
            if len(parts) < 3 or parts[0] != 'sources' or parts[1] not in allowed:
                raise ValueError('External source input is outside declared prior releases')
        if scope == 'meme':
            parts = PurePosixPath(destination).parts
            allowed = {config['version'].removeprefix('MTH_')}
            allowed |= {artifacts[name]['version'].removeprefix('MTH_') for name in config['publisher_history']}
            if config['source'] != 'MTH' or len(parts) < 6 or parts[:2] != ('mr', 'umls') or parts[2] not in allowed or 'METASUBSET' not in parts:
                raise ValueError('External native input is outside declared standard prepared bundles')
    for item in plan['generated_files']:
        name = relative(item['relative_path'])
        if ('candidate', name) in destinations:
            raise ValueError('Generated setting would overwrite a selected input')
        destinations.add(('candidate', name))
        raw = base64.b64decode(item['data_b64'], validate=True)
        if manifests.hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Generated settings checksum differs')
    for link in plan['symlinks']:
        name = relative(link['relative_path'])
        if ('candidate', name) in destinations:
            raise ValueError('Symlink would overwrite another plan destination')
        destinations.add(('candidate', name))
        if not isinstance(link['target'], str) or not link['target'] or '\x00' in link['target']:
            raise ValueError('Invalid link target')
    stages = set()
    for stage in plan['stages']:
        if not re.fullmatch(r'[a-z][a-z0-9-]*', stage['name']) or stage['name'] in stages:
            raise ValueError('Invalid or duplicate stage name')
        stages.add(stage['name'])
        if stage['cwd'] != '.':relative(stage['cwd'])
        if not isinstance(stage['argv'], list) or not stage['argv'] or any(not isinstance(v, str) or '\x00' in v for v in stage['argv']):
            raise ValueError('Native stage requires an argument array')
        if 'stdout' in stage:relative(stage['stdout'])
    if not stages or not plan['output_files'] or len(set(plan['output_files'])) != len(plan['output_files']):
        raise ValueError('Native plan needs distinct stages and outputs')
    for name in plan['output_files']:
        relative(name)
        if not name.startswith('src/') or ('candidate', name) in destinations:
            raise ValueError('Regenerated outputs cannot also be candidate inputs')
    leaves = [path for scope, path in destinations if scope == 'candidate']
    for name in leaves:
        if any(str(parent) in leaves for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('One planned file is the parent of another file')
    for stage in plan['stages']:
        if 'stdout' in stage and ('candidate', stage['stdout']) in destinations:
            raise ValueError('Native stage stdout would overwrite a frozen constructor/code file')
    return plan


def _modules(handler):
    """Freeze the actual transitive repository imports, including lazy imports."""
    declaration = manifests.HANDLERS[next(key for key, value in HANDLERS.items() if value == handler)]
    names = {'release_worker.py', handler + '.py', declaration + '.py'}
    available = {p.stem: p for p in (ROOT / 'tools').glob('*.py')}
    pending = list(names)
    while pending:
        name = pending.pop()
        for node in ast.walk(ast.parse((ROOT / 'tools' / name).read_bytes(), filename=name)):
            imports = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                       [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for imported in imports:
                stem = imported.split('.', 1)[0]
                if stem in available and stem + '.py' not in names:
                    names.add(stem + '.py');pending.append(stem + '.py')
    return sorted(names)


def _tree(ref, directory):
    result = []
    for line in historical.git('ls-tree', '-r', '--full-tree', ref, '--', directory).decode().splitlines():
        header, name = line.split('\t', 1);mode, kind, _ = header.split()
        if kind != 'blob':raise ValueError('Unsupported Git package entry')
        relative_path = str(PurePosixPath(name).relative_to(directory))
        if mode == '120000':
            result.append({'relative_path': relative_path, 'repository_path': name, 'kind': 'symlink',
                           'mode': '0o777', 'target': historical.blob(ref, name).decode()})
        elif mode in ('100644', '100755'):
            record = file_record(historical.blob(ref, name), relative_path,
                                 '0o555' if mode == '100755' else '0o444')
            result.append({**record, 'repository_path': name, 'kind': 'file'})
        else:raise ValueError('Unsupported Git package file mode')
    if not result:raise ValueError('Canonical source package is absent from selected engine')
    return result


def resolve(manifest, run_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', run_id):raise ValueError('Invalid run identity')
    report = manifests.preflight(manifest)
    if not report['manifest_valid'] or not report['declarations_valid']:
        raise ValueError('Manifest declaration preflight failed; inspect preflight-release first')
    blocked = [i for i in report['issues'] if i['severity'] in ('error', 'blocker') and i['code'] not in DEFERRED]
    if blocked:raise ValueError('Unresolved release decisions: ' + ', '.join(sorted({i['code'] for i in blocked})))
    config, artifacts = manifest['configuration'], manifest['artifacts']
    verify_locations(manifest, Path('/local/content/MEME/MEME5/inv/sources') / config['version'])
    if manifest['purpose'] != 'historical-replay' or 'replay' not in config:
        raise ValueError('Initial native admission requires a preserved historical oracle; shadow admission remains separate')
    if config['replay']['comparison_profile'] != 'exact':
        raise ValueError('Generic native admission initially uses exact comparison; no historical correction waivers')
    if not re.fullmatch(r'[0-9a-f]{40}', config['engine_ref']):
        raise ValueError('Native manifests require an immutable full Git engine commit')
    handler = HANDLERS.get(manifest['profile'])
    profiles = manifests.load(PROFILES)
    profile = profiles['profiles'].get(manifest['profile'])
    if not handler or not profile or profile['handler'] != handler:
        raise ValueError('No reviewed native source profile')
    verify_profile(profile)
    if any(a['provenance']['evidence_kind'] == 'synthetic-fixture' for a in artifacts.values()):
        raise ValueError('Synthetic evidence cannot authorize a native server run')
    engine = historical.commit(config['engine_ref'])
    code = _tree(engine, profile['engine_package'])
    identity = [{k: v for k, v in row.items() if k != 'data_b64'} for row in code]
    if manifests.digest(identity) not in profile['reviewed_package_sha256']:
        raise ValueError('Canonical engine package differs from reviewed native capability')
    runtime = []
    runtime_ref = historical.commit(profile['runtime_ref'])
    for directory in ('INV', 'ENV'):
        for row in _tree(runtime_ref, directory):
            if row['kind'] != 'file':raise ValueError('Shared runtime links need a separate reviewed capability')
            row['relative_path'] = row['repository_path'];runtime.append(row)
    if len(runtime) != 169:raise ValueError('Complete reviewed 169-file runtime is required')
    runtime_identity = [{k: v for k, v in row.items() if k != 'data_b64'} for row in runtime]
    if manifests.digest(runtime_identity) != profile['runtime_inventory_sha256']:
        raise ValueError('Shared runtime inventory differs from the reviewed native profile')
    plan = importlib.import_module(handler).build_plan(config, artifacts, code)
    verify_plan(plan, manifest, code)
    if plan['engine_package'] != profile['engine_package']:raise ValueError('Native plan selects another code package')
    refs = artifacts[config['replay']['reference_ref']]['files']
    if {f['role'] for f in refs} != set(plan['output_files']):
        raise ValueError('Official reference roles must cover each complete planned output path exactly')
    ref = historical.commit('HEAD');provenance = [];modules = {}
    paths = ['tools/' + n for n in _modules(handler)] + ['tools/release_execution.py', 'tools/inversion_remote.py',
        'docs/inversion-review/native-execution-profiles.json',
        'docs/inversion-review/release-manifest.schema.json', 'docs/inversion-review/source-profiles.json',
        'docs/inversion-review/source-profiles.schema.json']
    paths += [item['repository_path'] for item in report['code_provenance']['files']]
    module_names = set(_modules(handler))
    for path in sorted(set(paths)):
        raw = historical.blob(ref, path)
        if (ROOT / path).read_bytes() != raw:raise ValueError('Commit consumed apparatus before resolving: ' + path)
        provenance.append({'repository_path': path, 'sha256': manifests.hashlib.sha256(raw).hexdigest()})
        if path.startswith('tools/') and Path(path).name in module_names:
            modules[Path(path).name] = base64.b64encode(raw).decode()
    historical.validate_module_dependencies({n: base64.b64decode(v) for n, v in modules.items()})
    lock = {'schema_version': 1, 'artifact_type': 'ncimeta-native-release-lock', 'run_id': run_id,
            'request': {key: config[key] for key in ('source', 'version', 'engine_ref')},
            'manifest': manifest, 'configuration': config, 'profile': profile, 'profile_sha256': manifests.digest(profile),
            'profiles_registry_b64': base64.b64encode(PROFILES.read_bytes()).decode(),
            'source_profile': manifest['profile'], 'plan': plan, 'plan_sha256': manifests.digest(plan),
            'manifest_sha256': manifests.digest(manifest), 'apparatus_ref': ref, 'provenance': provenance,
            'modules_b64': modules, 'code_files': code, 'runtime_files': runtime, 'runtime_ref': runtime_ref,
            'input_verification': 'Required on dev before any source preservation/publication',
            'production_eligible': False, 'insertion_executed': False, 'execution_enabled': True}
    lock['request']['engine_ref'] = engine
    lock['lock_sha256'] = manifests.digest(lock)
    return lock
