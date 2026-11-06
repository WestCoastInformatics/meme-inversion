#!/usr/bin/env python3
"""Resolve the common request into an immutable, source-aware dev replay capsule."""
import argparse
import base64
import copy
import hashlib
from functools import lru_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/inversion-review'
MODULES = ('inversion_worker.py', 'replay_process.py', 'replay_mth_core.py',
           'compare_mth_core.py', 'acquire_mth_subset.py', 'compare_nci_core.py',
           'acquire_inversion_reference.py', 'inspect_inversion_archive.py',
           'prepare_nci_candidate.py', 'advance_nci_replay.py',
           'prepare_snomed_candidate.py', 'run_snomed_core_replay.py', 'compare_snomed_core.py')
ADAPTERS = {'NCI': 'nci-oct2026-v1', 'SNOMEDCT_US': 'snomed-sep2026-v1', 'MTH': 'mth-2026aa-v1'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + value)))


def validate(value, filename):
    try:
        from jsonschema import Draft202012Validator
    except ImportError as error:
        raise RuntimeError('Install tools/requirements-runner.txt in an isolated Python environment') from error
    schema = load(DOCS / filename)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError('; '.join('/'.join(map(str, e.path)) + ': ' + e.message for e in errors))


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], stderr=subprocess.PIPE)


def commit(ref):
    if not isinstance(ref, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', ref) or ref.startswith('-') or '<' in ref:
        raise ValueError('A Git revision without placeholders or command syntax is required')
    value = git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('Git did not resolve an immutable commit')
    return value


@lru_cache(maxsize=2048)
def blob(ref, path):
    relative = PurePosixPath(path)
    if relative.is_absolute() or '..' in relative.parts or ':' in path:
        raise ValueError('Invalid repository artifact path')
    return git('show', ref + ':' + path)


def frozen_file(ref, path, mode=None):
    raw = blob(ref, path)
    return {'repository_path': path, 'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw), 'mode': mode, 'data_b64': base64.b64encode(raw).decode()}


def select_case(request):
    validate(request, 'request.schema.json')
    registry = load(DOCS / 'source-registry.json')
    source = registry['sources'].get(request['source'])
    if source is None:
        raise ValueError('Unregistered source: ' + request['source'])
    if request['source'] not in ADAPTERS or not source['common_adapter_implemented'] or not source['adapter_ref']:
        raise ValueError(request['source'] + ' is registered; its reviewed replay case and adapter are pending')
    index = load(DOCS / 'case-catalog/index.json')
    matches = [entry for entry in index['cases'] if all(entry[key] == request[key]
               for key in ('source', 'version', 'case_variant'))]
    if len(matches) != 1:
        raise ValueError('No unique reviewed case for the exact source, version and case_variant')
    name = matches[0]['path']
    if Path(name).name != name:
        raise ValueError('Invalid case catalog path')
    case = load(DOCS / 'case-catalog' / name)
    if case['adapter'] != ADAPTERS[request['source']]:
        raise ValueError('The reviewed source adapter does not match')
    for key in ('source', 'version', 'case_variant', 'reference_stage', 'comparison_profile'):
        if request[key] != case[key]:
            raise ValueError('Request conflicts with the reviewed case: ' + key)
    engine = commit(request['engine_ref'])
    if engine not in case['reviewed_engine_refs']:
        raise ValueError('Engine commit has no reviewed compatibility/acceptance contract for this case')
    configuration = copy.deepcopy(case['configuration'])
    configuration['engine_ref'] = engine
    validate(configuration, 'configuration.schema.json')
    if configuration['source_atom_ids']['start'] > configuration['source_atom_ids']['end']:
        raise ValueError('Source atom ID range is reversed')
    refs = [configuration[key] for key in ('policy_ref', 'environment_profile', 'validation_profile')]
    refs += configuration['inputs']['source_data'] + configuration['publisher_history']
    refs += [configuration['inputs'][key] for key in ('reference_ncimeta', 'identity_state', 'source_plan')]
    refs += [configuration['source_atom_ids']['provenance_ref'], configuration['replay']['reference_ref']]
    for ref in filter(None, refs):
        if ref not in case['artifacts'] or ref != 'sha256:' + digest(case['artifacts'][ref]['value']):
            raise ValueError('An artifact reference has no verified content identity: ' + str(ref))
    return case, configuration, name


def resolve(request, run_id):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', run_id):
        raise ValueError('run_id requires 2–71 lowercase letters, numbers or hyphens')
    case, configuration, case_name = select_case(request)
    apparatus_ref = commit('HEAD')
    # The executable catalog, schemas and apparatus must be committed. Never label
    # uncommitted worktree bytes as code from HEAD.
    paths = ['tools/' + name for name in MODULES] + ['tools/inversion_request.py', 'tools/inversion_remote.py',
        'baseline/manifest.json', 'docs/inversion-review/mth-2026aa-baseline-case.json'] + [
        'docs/inversion-review/' + name for name in ('request.schema.json', 'configuration.schema.json',
        'source-registry.json', 'case-catalog/index.json', 'case-catalog/' + case_name)]
    provenance = []
    modules = {}
    for path in paths:
        raw = blob(apparatus_ref, path)
        if (ROOT / path).read_bytes() != raw:
            raise ValueError('Commit apparatus/catalog changes before resolving: ' + path)
        provenance.append({'repository_path': path, 'sha256': hashlib.sha256(raw).hexdigest()})
        if Path(path).name in MODULES and path.startswith('tools/'):
            modules[Path(path).name] = base64.b64encode(raw).decode()
    engine = configuration['engine_ref']
    code_files = []
    for item in case['source_files']:
        record = copy.deepcopy(item)
        path = 'sources/' + request['version'] + '/' + item['relative_path']
        if item['kind'] == 'symlink':
            if blob(engine, path).decode() != item['target']:
                raise ValueError('Captured source link differs from selected Git engine')
        else:
            frozen = frozen_file(engine, path, item['mode'])
            if frozen['sha256'] != item['sha256']:
                raise ValueError('Source code differs from the reviewed compatibility contract')
            record.update(frozen)
        code_files.append(record)
    runtime_ref = case['runtime_ref']
    runtime_files = []
    for item in case['runtime_files']:
        frozen = frozen_file(runtime_ref, item['relative_path'], item['mode'])
        if frozen['sha256'] != item['sha256']:
            raise ValueError('Shared runtime differs from the reviewed compatibility contract')
        runtime_files.append(frozen)
    lock = {'schema_version': 1, 'artifact_type': 'ncimeta-dev-replay-lock', 'run_id': run_id,
            'request': {**request, 'engine_ref': engine}, 'configuration': configuration,
            'case': case, 'case_sha256': digest(case), 'apparatus_ref': apparatus_ref,
            'provenance': provenance, 'modules_b64': modules, 'code_files': code_files,
            'runtime_files': runtime_files,
            'runtime_ref': runtime_ref, 'execution_enabled': case['execution_enabled'],
            'network': 'disabled during conversion', 'insertion_executed': False}
    lock['lock_sha256'] = digest(lock)
    return lock


def write_new(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    with os.fdopen(descriptor, 'w') as out:
        json.dump(value, out, indent=2)
        out.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    resolve_parser = commands.add_parser('resolve', help='Validate and freeze a reviewed request; no server changes')
    resolve_parser.add_argument('request')
    resolve_parser.add_argument('--run-id', required=True)
    resolve_parser.add_argument('--output', required=True)
    inspect_parser = commands.add_parser('show', help='Show a lock without executable code payloads')
    inspect_parser.add_argument('lock')
    args = parser.parse_args()
    if args.command == 'resolve':
        lock = resolve(load(args.request), args.run_id)
        write_new(args.output, lock)
        print(json.dumps({'lock': args.output, 'lock_sha256': lock['lock_sha256'],
                          'source': lock['request']['source'], 'version': lock['request']['version'],
                          'execution_enabled': lock['execution_enabled']}))
    else:
        lock = load(args.lock)
        expected = lock.pop('lock_sha256')
        if digest(lock) != expected:
            raise ValueError('Run lock content changed')
        print(json.dumps({'run_id': lock['run_id'], 'lock_sha256': expected,
                          'configuration': lock['configuration'], 'execution_enabled': lock['execution_enabled'],
                          'apparatus_ref': lock['apparatus_ref'], 'case_sha256': lock['case_sha256'],
                          'source_files': len(lock['code_files']), 'runtime_files': len(lock['runtime_files'])}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
