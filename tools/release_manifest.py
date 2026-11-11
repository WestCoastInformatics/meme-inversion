#!/usr/bin/env python3
"""Offline manifest/profile preflight, independent of historical replay cases."""
import hashlib
import importlib
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/inversion-review'
HANDLERS = {'nci-publisher-inputs-v1': 'release_nci',
            'snomed-us-snapshot-inputs-v1': 'release_snomed',
            'mth-prepared-inputs-v1': 'release_mth'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:raise ValueError('Duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + value)))


def issue(severity, code, message, path=''):
    return {'severity': severity, 'code': code, 'message': message, 'path': path}


def schema_errors(value, schema):
    def offline(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key in ('$ref', '$dynamicRef', '$recursiveRef') and isinstance(child, str) and not child.startswith('#'):
                    raise RuntimeError('External schema retrieval is disabled in offline preflight')
                offline(child)
        elif isinstance(item, list):
            for child in item:offline(child)
    offline(schema)
    try:from jsonschema import Draft202012Validator
    except ImportError as error:raise RuntimeError('Install tools/requirements-runner.txt in an isolated Python environment') from error
    Draft202012Validator.check_schema(schema)
    return [issue('error', 'SCHEMA_INVALID', error.message, '/'.join(map(str, error.absolute_path)))
            for error in sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: str(list(item.path)))]


def _git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.PIPE)


@lru_cache(maxsize=64)
def _package_inventory(ref, package):
    inventory = []
    for line in _git('ls-tree', '-r', '--full-tree', ref, '--', package).decode().splitlines():
        header, path = line.split('\t', 1);mode, kind, blob = header.split()
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Unsupported canonical package entry: ' + path)
        raw = _git('show', ref + ':' + path)
        inventory.append({'repository_path': path, 'mode': mode, 'sha256': hashlib.sha256(raw).hexdigest()})
    return inventory


def _engine(ref, profile, issues):
    if not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or ref.startswith('-'):
        issues.append(issue('error', 'INVALID_ENGINE_REF', 'A Git revision without shell syntax or placeholders is required', 'configuration/engine_ref'))
        return None, []
    try:
        resolved = _git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    except subprocess.CalledProcessError:
        issues.append(issue('error', 'ENGINE_NOT_FOUND', 'Engine commit is unavailable in this repository', 'configuration/engine_ref'))
        return None, []
    package = profile['canonical_engine_package']
    try:inventory = _package_inventory(resolved, package)
    except ValueError as error:
        issues.append(issue('blocker', 'ENGINE_PACKAGE_LAYOUT_UNREVIEWED', str(error), package));inventory = []
    approved = resolved in profile['reviewed_engine_refs']
    if inventory and not approved:
        approved = any(inventory == _package_inventory(ref, package) for ref in profile['reviewed_engine_refs'])
    if not approved:
        issues.append(issue('blocker', 'ENGINE_PROFILE_UNREVIEWED', 'Engine package does not match a reviewed source profile', 'configuration/engine_ref'))
    if not inventory:
        issues.append(issue('blocker', 'CANONICAL_ENGINE_PACKAGE_PENDING', 'The release-independent Git package is not implemented for this profile yet', package))
    return resolved, inventory


def provenance(handler):
    names = ['tools/release_manifest.py', 'tools/inversion_request.py',
             'docs/inversion-review/release-manifest.schema.json',
             'docs/inversion-review/source-profiles.schema.json', 'docs/inversion-review/source-profiles.json']
    if handler:names.append('tools/' + handler + '.py')
    if handler == 'release_nci':
        names += ['tools/nci_source_plan.py', 'tools/execute_release_nci.py', 'docs/inversion-review/nci-source-plan.schema.json',
                  'docs/inversion-review/nci-installed-state-v2.schema.json']
    ref = _git('rev-parse', 'HEAD').decode().strip()
    entries = [];committed = True
    for name in names:
        path = ROOT / name
        if not path.is_file():
            committed = False;continue
        raw = path.read_bytes();entries.append({'repository_path': name, 'sha256': hashlib.sha256(raw).hexdigest()})
        try:committed = committed and _git('show', ref + ':' + name) == raw
        except subprocess.CalledProcessError:committed = False
    return {'git_ref': ref if committed else None, 'committed': committed, 'files': entries}


def _relative(name):
    if not isinstance(name, str) or not name or '\\' in name or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError('Unsafe path')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name or name == '.':
        raise ValueError('A canonical relative path is required')
    return path


def location(file, synthetic):
    uri = file['uri']
    if any(ord(char) < 32 or ord(char) == 127 for char in uri):raise ValueError('Control character in URI')
    parsed = urlsplit(uri)
    if parsed.query or parsed.fragment:raise ValueError('URI query/fragment is unsupported; bind archive identity explicitly')
    path = unquote(parsed.path)
    if any(ord(char) < 32 or ord(char) == 127 for char in path):raise ValueError('Encoded control character in URI')
    if parsed.scheme == 'repo':
        if not synthetic or parsed.netloc:raise ValueError('repo: input locations are restricted to synthetic fixtures')
        relative = _relative(path)
        if relative.parts[:3] != ('tools', 'fixtures', 'release-manifests'):
            raise ValueError('repo: input must be inside the synthetic release fixture tree')
        result = ROOT / str(relative)
    elif parsed.scheme == 'file':
        if parsed.netloc or not path.startswith('/') or '..' in PurePosixPath(path).parts or '\\' in path:
            raise ValueError('A local absolute file URI is required')
        result = Path(path)
        if str(result) != path:raise ValueError('Noncanonical local file URI')
    elif parsed.scheme == 's3':
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', parsed.netloc):raise ValueError('Invalid S3 bucket')
        _relative(path.removeprefix('/'))
        result = None
    else:raise ValueError('Supported input schemes are file:, s3: and synthetic repo:')
    if result is not None and result.resolve().is_relative_to(ROOT / 'tools/fixtures/release-manifests') and not synthetic:
        raise ValueError('Known synthetic fixture locations cannot be declared real release evidence')
    if 'archive_member' in file:_relative(file['archive_member'])
    return result


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, stat.S_IMODE(info.st_mode))


def _hash_stream(handle):
    value = hashlib.sha256();size = 0
    for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
        value.update(block);size += len(block)
    return value.hexdigest(), size


def _open(path):
    if path.resolve() != path:raise ValueError('Linked file or ancestor is prohibited')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    handle = os.fdopen(fd, 'rb')
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        handle.close();raise ValueError('A regular input file is required')
    return handle


def verify_files(artifacts, enabled, issues):
    rows = [];groups = {}
    for name, artifact in artifacts.items():
        roles = set()
        synthetic = artifact['provenance']['evidence_kind'] == 'synthetic-fixture'
        for number, file in enumerate(artifact['files']):
            path = 'artifacts/' + name + '/files/' + str(number)
            row = {'artifact': name, 'role': file['role'], 'uri': file['uri'], 'status': 'DECLARED_NOT_VERIFIED'}
            rows.append(row)
            if type(file['bytes']) is not int or ('archive_bytes' in file and type(file['archive_bytes']) is not int):
                row['status'] = 'INVALID_DECLARATION';issues.append(issue('error', 'INVALID_BYTE_COUNT', 'Byte counts must be exact integers', path));continue
            if file['role'] in roles:issues.append(issue('error', 'DUPLICATE_FILE_ROLE', 'Duplicate file role within one artifact', path))
            roles.add(file['role'])
            try:
                local = location(file, synthetic)
                if file['sha256'] in ('0' * 64, 'f' * 64):raise ValueError('Placeholder file checksum')
                if not enabled:continue
                if local is None:
                    row['status'] = 'REMOTE_NOT_VERIFIED'
                    issues.append(issue('blocker', 'REMOTE_INPUT_NOT_VERIFIED', 'Acquire exact bytes using the existing source acquisition workflow before local verification', path));continue
                key = (str(local), file.get('archive_format'), file.get('archive_sha256'), file.get('archive_bytes'))
                groups.setdefault(key, []).append((file, row, path))
            except (ValueError, OSError) as error:
                row['status'] = 'INVALID_LOCATION';issues.append(issue('error', 'INVALID_INPUT_LOCATION', str(error), path))
    for key, items in groups.items():
        local = Path(key[0])
        try:
            with _open(local) as raw:
                before = _stamp(os.fstat(raw.fileno()))
                checksum, size = _hash_stream(raw)
                if _stamp(os.fstat(raw.fileno())) != before or _stamp(local.lstat()) != before:raise ValueError('Input changed during hash verification')
                if key[1] is None:
                    for file, row, path in items:
                        if checksum != file['sha256'] or size != file['bytes']:raise ValueError('Input size or SHA-256 differs from its manifest')
                        row.update(status='VERIFIED', sha256=checksum, bytes=size, local_path=str(local), snapshot=list(before))
                else:
                    if checksum != key[2] or size != key[3]:raise ValueError('Container size or SHA-256 differs from its manifest')
                    raw.seek(0);wanted = {file['archive_member'] for file, _, _ in items};found = {};seen = set()
                    sizes = {member: {file['bytes'] for file, _, _ in items if file['archive_member'] == member} for member in wanted}
                    if key[1] == 'tar.gz':
                        with tarfile.open(fileobj=raw, mode='r|gz') as archive:
                            for member in archive:
                                name = member.name.removeprefix('./').rstrip('/')
                                if name == '.':continue
                                _relative(name)
                                if name in seen:raise ValueError('Duplicate container member')
                                seen.add(name)
                                if name in wanted:
                                    if not member.isfile():raise ValueError('Selected container member is not a regular file')
                                    if sizes[name] != {member.size}:raise ValueError('Selected member size differs from its manifest')
                                    with archive.extractfile(member) as incoming:found[name] = _hash_stream(incoming)
                    else:
                        with zipfile.ZipFile(raw) as archive:
                            for member in archive.infolist():
                                name = member.filename.rstrip('/');_relative(name)
                                if name in seen:raise ValueError('Duplicate container member')
                                seen.add(name)
                                if name in wanted:
                                    kind = stat.S_IFMT(member.external_attr >> 16)
                                    if member.is_dir() or kind not in (0, stat.S_IFREG):raise ValueError('Selected container member is not a regular file')
                                    if sizes[name] != {member.file_size}:raise ValueError('Selected member size differs from its manifest')
                                    with archive.open(member) as incoming:found[name] = _hash_stream(incoming)
                    for file, row, path in items:
                        actual = found.get(file['archive_member'])
                        if actual != (file['sha256'], file['bytes']):raise ValueError('Selected member missing or content differs')
                        row.update(status='VERIFIED', sha256=actual[0], bytes=actual[1], archive_member=file['archive_member'], archive_sha256=checksum,
                                   local_path=str(local), snapshot=list(before))
                if _stamp(os.fstat(raw.fileno())) != before or _stamp(local.lstat()) != before:raise ValueError('Input changed during content verification')
        except (OSError, ValueError, RuntimeError, NotImplementedError, tarfile.TarError, zipfile.BadZipFile, EOFError) as error:
            for _, row, path in items:
                row['status'] = 'VERIFICATION_FAILED';issues.append(issue('blocker', 'INPUT_BYTES_NOT_VERIFIED', str(error), path))
    if any(row['status'] == 'DECLARED_NOT_VERIFIED' for row in rows):
        issues.append(issue('blocker', 'INPUT_BYTES_UNVERIFIED', 'File declarations are not proof of available input bytes; use --verify-files', 'artifacts'))
    return rows


def _references(config):
    for name in ('policy_ref', 'environment_profile', 'validation_profile'):yield name, config[name]
    for name in ('reference_ncimeta', 'identity_state', 'source_plan'):
        if config['inputs'][name] is not None:yield 'inputs/' + name, config['inputs'][name]
    for number, name in enumerate(config['inputs']['source_data']):yield 'inputs/source_data/' + str(number), name
    for number, name in enumerate(config['publisher_history']):yield 'publisher_history/' + str(number), name
    if config['source_atom_ids'] is not None:yield 'source_atom_ids/provenance_ref', config['source_atom_ids']['provenance_ref']
    if 'replay' in config:yield 'replay/reference_ref', config['replay']['reference_ref']


def _common(config, artifacts, profile, issues):
    if config['source'] != profile['source'] or not config['version'].startswith(profile['version_prefix']) or '.before-' in config['version']:
        issues.append(issue('error', 'SOURCE_VERSION_PROFILE_MISMATCH', 'Source/version does not belong to the selected profile', 'configuration/version'))
    if config['inputs']['source_data_stage'] != profile['input_stage']:
        issues.append(issue('error', 'INPUT_STAGE_PROFILE_MISMATCH', 'Selected profile does not implement this input stage', 'configuration/inputs/source_data_stage'))
    for item in schema_errors(config['source_options'], profile['source_options_schema']):
        item['path'] = 'configuration/source_options/' + item['path'];issues.append(item)
    expected = {'policy_ref': {'policy'}, 'environment_profile': {'environment-profile'}, 'validation_profile': {'validation-profile'},
                'inputs/reference_ncimeta': {'ncimeta-state'}, 'inputs/identity_state': {'identity-state'},
                'inputs/source_plan': {'source-plan'}, 'source_atom_ids/provenance_ref': {'id-allocation'},
                'replay/reference_ref': {'reference-inversion'}}
    for path, name in _references(config):
        if name not in artifacts:
            issues.append(issue('error', 'ARTIFACT_REFERENCE_MISSING', 'Unresolved artifact: ' + name, 'configuration/' + path));continue
        kind = artifacts[name]['artifact_type']
        allowed = expected.get(path)
        if path.startswith('inputs/source_data/'):
            allowed = {'publisher-bundle' if profile['input_stage'] == 'publisher' else 'prepared-bundle'}
        if path.startswith('publisher_history/'):allowed = {'publisher-history'}
        if allowed and kind not in allowed:issues.append(issue('error', 'ARTIFACT_ROLE_MISMATCH', 'Artifact type does not satisfy this role: ' + name, 'configuration/' + path))
        if kind in ('publisher-bundle', 'prepared-bundle', 'source-plan', 'id-allocation') and (artifacts[name]['source'], artifacts[name]['version']) != (config['source'], config['version']):
            issues.append(issue('error', 'ARTIFACT_RELEASE_MISMATCH', 'Release-bound artifact belongs to another source/version', 'artifacts/' + name))
    for ref_field, expected_id in [('environment_profile', profile['environment_profile_id']), ('validation_profile', profile['validation_profile_id'])]:
        value = artifacts.get(config[ref_field])
        if value and value['data'].get('profile_id') != expected_id:
            issues.append(issue('blocker', 'PROFILE_ARTIFACT_UNREVIEWED', 'Expected profile_id ' + expected_id, 'artifacts/' + config[ref_field]))
    for baseline in ('replacement_baseline', 'comparison_baseline'):
        value = config[baseline]
        if value and (value['source'] != config['source'] or not value['version'].startswith(profile['version_prefix']) or '.before-' in value['version']):
            issues.append(issue('error', 'BASELINE_SOURCE_MISMATCH', 'Baseline has a different or unsafe source/version', 'configuration/' + baseline))
    if config['replacement_baseline'] and config['replacement_baseline']['version'] == config['version']:
        issues.append(issue('error', 'SELF_REPLACEMENT', 'A release cannot replace itself', 'configuration/replacement_baseline'))
    bounds = config['source_atom_ids']
    if bounds is None:
        issues.append(issue('blocker', 'ID_ALLOCATION_REQUIRED', 'Explicit inclusive range and provenance are required before execution', 'configuration/source_atom_ids'))
    elif any(type(bounds[key]) is not int for key in ('start', 'end')):
        issues.append(issue('error', 'INVALID_ID_RANGE_TYPES', 'Source atom identifiers must be exact integers', 'configuration/source_atom_ids'))
    elif bounds['start'] > bounds['end']:
        issues.append(issue('error', 'REVERSED_ID_RANGE', 'Inclusive ID range is reversed', 'configuration/source_atom_ids'))
    else:
        allocation = artifacts.get(bounds['provenance_ref'])
        if allocation and (any(type(allocation['data'].get(key)) is not int for key in ('start', 'end'))
                           or any(allocation['data'].get(key) != bounds[key] for key in ('start', 'end', 'bound_kind'))):
            issues.append(issue('error', 'ID_ALLOCATION_BINDING_MISMATCH', 'Declared range differs from its allocation artifact', 'configuration/source_atom_ids'))
    if config['output_stage'] != 'inversion-src':
        issues.append(issue('blocker', 'OUTPUT_STAGE_UNIMPLEMENTED', 'This increment does not implement insertion preparation', 'configuration/output_stage'))
    if 'replay' in config:
        reference = artifacts.get(config['replay']['reference_ref'])
        if reference and (reference['source'], reference['version']) != (config['source'], config['version']):
            issues.append(issue('error', 'COMPARISON_REFERENCE_MISMATCH', 'Official replay oracle must describe the current release, independently of prior change-detection baselines', 'configuration/replay'))
        if config['replay']['reference_stage'] != config['output_stage']:
            issues.append(issue('error', 'COMPARISON_STAGE_MISMATCH', 'Candidate output and official reference stages differ', 'configuration/replay'))
        if reference and reference['data'].get('reference_stage') != config['replay']['reference_stage']:
            issues.append(issue('blocker' if reference['data'].get('reference_stage') is None else 'error',
                                'REFERENCE_STAGE_PROVENANCE_MISMATCH', 'Official artifact must identify the selected reference stage', 'artifacts/' + config['replay']['reference_ref']))
    return _engine(config['engine_ref'], profile, issues)


def _seal(report):
    report['report_sha256'] = digest({key: value for key, value in report.items() if key != 'report_sha256'})
    return report


def preflight(manifest, verify=False):
    issues = schema_errors(manifest, load(DOCS / 'release-manifest.schema.json'))
    report = {'schema_version': 1, 'artifact_type': 'ncimeta-release-preflight', 'manifest_sha256': digest(manifest),
              'manifest_valid': not issues, 'declarations_valid': False, 'status': 'INVALID_MANIFEST',
              'issues': issues, 'artifact_bindings': {}, 'input_files': [], 'source_preflight': None,
              'execution_eligible': False, 'production_eligible': False, 'network_access': False,
              'source_data_changed': False, 'new_allocations_performed': False}
    if issues:return _seal(report)
    registry = load(DOCS / 'source-profiles.json')
    if schema_errors(registry, load(DOCS / 'source-profiles.schema.json')):raise RuntimeError('Source-profile registry is invalid')
    config, artifacts = manifest['configuration'], manifest['artifacts']
    report.update(source=config['source'], version=config['version'], profile=manifest['profile'], purpose=manifest['purpose'])
    profile = registry['profiles'].get(manifest['profile'])
    if profile is None:
        issues.append(issue('blocker', 'UNKNOWN_SOURCE_PROFILE', 'No reviewed profile is registered for this request', 'profile'))
        report['status'] = 'BLOCKED';report['code_provenance'] = provenance(None);return _seal(report)
    report['profile_sha256'] = digest(profile)
    for name, value in artifacts.items():
        report['artifact_bindings'][name] = {'reference': 'sha256:' + digest(value), 'artifact_type': value['artifact_type']}
    report['input_files'] = verify_files(artifacts, verify, issues)
    engine, inventory = _common(config, artifacts, profile, issues)
    report.update(resolved_engine_ref=engine, engine_package=profile['canonical_engine_package'], engine_package_inventory=inventory)
    handler = HANDLERS.get(manifest['profile'])
    if handler and profile['handler'] != handler:raise RuntimeError('Registered source handler differs from reviewed dispatch')
    if handler and not any(item['severity'] == 'error' for item in issues):
        result = importlib.import_module(handler).analyze(config, artifacts)
        if not isinstance(result, dict) or set(result) != {'issues', 'facts', 'planned_outputs'}:
            raise RuntimeError('Source preflight returned an invalid contract')
        for item in result['issues']:
            if set(item) != {'severity', 'code', 'message', 'path'} or item['severity'] not in ('error', 'blocker', 'warning'):
                raise RuntimeError('Source preflight returned an invalid issue')
        for path in result['planned_outputs']:_relative(path)
        issues.extend(result['issues']);report['source_preflight'] = result
    elif not handler:
        issues.append(issue('blocker', 'SOURCE_PREFLIGHT_PENDING', 'Source is registered but its manifest adapter has not been implemented', 'profile'))
    synthetic = [name for name, value in artifacts.items() if value['provenance']['evidence_kind'] == 'synthetic-fixture']
    if synthetic:issues.append(issue('blocker', 'SYNTHETIC_EVIDENCE', 'Synthetic fixtures are examples/test evidence, not real release provenance: ' + ', '.join(sorted(synthetic)), 'artifacts'))
    issues.append(issue('blocker', 'PREFLIGHT_NOT_EXECUTION_AUTHORITY', 'Preflight reports/review locks do not authorize execution; resolve-release performs separate native admission', 'profile'))
    errors = any(item['severity'] == 'error' for item in issues)
    report['declarations_valid'] = not errors and report['source_preflight'] is not None
    report['status'] = 'INVALID_RELEASE_CONTRACT' if errors else 'BLOCKED'
    report['code_provenance'] = provenance(handler)
    return _seal(report)


def freeze(manifest, report):
    if report.get('report_sha256') != digest({key: value for key, value in report.items() if key != 'report_sha256'}):
        raise ValueError('Preflight report changed after validation')
    if report['manifest_sha256'] != digest(manifest) or not report['manifest_valid'] or not report['declarations_valid']:
        raise ValueError('Only a schema/contract-valid manifest can produce a review lock')
    current = provenance(HANDLERS.get(manifest['profile']))
    if not current['committed'] or report['code_provenance'] != current:
        raise ValueError('Commit preflight/schema/profile changes before freezing a lock')
    if (report['source'], report['version'], report['profile']) != (manifest['configuration']['source'], manifest['configuration']['version'], manifest['profile']):
        raise ValueError('Report release identity differs from its manifest')
    if report['execution_eligible'] is not False or report['production_eligible'] is not False:
        raise ValueError('A preflight report cannot authorize execution')
    bindings = {name: {'reference': 'sha256:' + digest(value), 'artifact_type': value['artifact_type']} for name, value in manifest['artifacts'].items()}
    if report['artifact_bindings'] != bindings:
        raise ValueError('Report artifact bindings differ from its manifest')
    registry = load(DOCS / 'source-profiles.json');profile = registry['profiles'][manifest['profile']]
    engine, inventory = _engine(manifest['configuration']['engine_ref'], profile, [])
    if report['profile_sha256'] != digest(profile) or report['resolved_engine_ref'] != engine or report['engine_package_inventory'] != inventory:
        raise ValueError('Report profile or engine identity differs from current resolution')
    descriptors = {(name, file['role']): (file, value['provenance']['evidence_kind'] == 'synthetic-fixture')
                   for name, value in manifest['artifacts'].items() for file in value['files']}
    if len(report['input_files']) != len(descriptors):raise ValueError('File-verification inventory differs')
    keys = [(row['artifact'], row['role']) for row in report['input_files']]
    if len(set(keys)) != len(keys) or set(keys) != set(descriptors):raise ValueError('File-verification inventory is incomplete or duplicated')
    for row in report['input_files']:
        file, synthetic = descriptors[(row['artifact'], row['role'])]
        if row['uri'] != file['uri']:raise ValueError('File location differs from its manifest')
        if row['status'] == 'VERIFIED':
            local = location(file, synthetic)
            if (local is None or str(local) != row['local_path'] or not stat.S_ISREG(local.lstat().st_mode)
                    or list(_stamp(local.lstat())) != row['snapshot'] or local.resolve() != local
                    or (row['sha256'], row['bytes']) != (file['sha256'], file['bytes'])):
                raise ValueError('Verified input changed before freezing')
            if 'archive_member' in file and (row.get('archive_member'), row.get('archive_sha256')) != (file['archive_member'], file['archive_sha256']):
                raise ValueError('Verified archive member binding changed')
    value = {'schema_version': 1, 'artifact_type': 'ncimeta-release-preflight-lock',
             'manifest_sha256': report['manifest_sha256'], 'source': report['source'], 'version': report['version'],
             'profile': report['profile'], 'profile_sha256': report['profile_sha256'],
             'artifact_bindings': report['artifact_bindings'], 'engine_ref': report['resolved_engine_ref'],
             'engine_package_inventory': report['engine_package_inventory'], 'code_provenance': report['code_provenance'],
             'input_files': report['input_files'], 'preflight_sha256': digest(report),
             'execution_eligible': False, 'production_eligible': False}
    value['lock_sha256'] = digest(value)
    return value


def write_new(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, 'w') as out:json.dump(value, out, indent=2, allow_nan=False);out.write('\n')
