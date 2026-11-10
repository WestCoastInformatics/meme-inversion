#!/usr/bin/env python3
"""Preview source compatibility settings from an existing common replay lock."""
import argparse
import base64
import hashlib
import importlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

import inversion_request as request
import inversion_worker as worker

ADAPTERS = {
    'NCI': ('nci_configuration', 'from_lock'),
    'SNOMEDCT_US': ('snomed_configuration', 'preview_from_lock'),
    'MTH': ('mth_configuration', 'preview_from_lock'),
}
REPORT = 'configuration-preview.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def payloads(recipe):
    """Validate the entire output set before creating any preview files."""
    if not isinstance(recipe, dict) or not recipe.get('profile'):
        raise ValueError('Missing source configuration-preview profile')
    if not isinstance(recipe.get('files'), list) or not recipe['files']:
        raise ValueError('The source preview contains no generated files')
    result = {}
    for item in recipe['files']:
        name = item['relative_path']
        if not isinstance(name, str) or not name or '\\' in name or any(ord(char) < 32 or ord(char) == 127 for char in name):
            raise ValueError('Unsafe preview output path')
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or '..' in path.parts or path.as_posix() != name:
            raise ValueError('Unsafe or noncanonical preview output path')
        if path.parts[0] == REPORT or name in result or item.get('mode') != '0o444':
            raise ValueError('Duplicate, reserved or writable preview output')
        raw = base64.b64decode(item['data_b64'], validate=True)
        if not re.fullmatch('[0-9a-f]{64}', item['sha256']) or sha(raw) != item['sha256']:
            raise ValueError('Generated preview payload changed: ' + name)
        if 'bytes' in item and item['bytes'] != len(raw):
            raise ValueError('Generated preview size changed: ' + name)
        result[name] = raw
    for name in result:
        if any(parent.as_posix() in result for parent in PurePosixPath(name).parents):
            raise ValueError('Preview output file/directory collision')
    return result


def without_payloads(value):
    if isinstance(value, dict):
        return {key: without_payloads(item) for key, item in value.items() if key != 'data_b64'}
    if isinstance(value, list):
        return [without_payloads(item) for item in value]
    return value


def provenance(source, preflight=False):
    names = ['inversion_configuration.py', 'inversion_request.py', 'inversion_worker.py', ADAPTERS[source][0] + '.py']
    if source == 'NCI':
        names += ['nci_source_plan.py']
    if preflight:
        names += ['nci_release_preflight.py']
    paths = ['tools/' + name for name in sorted(set(names))]
    paths += ['docs/inversion-review/' + name for name in ('request.schema.json', 'configuration.schema.json')]
    files = []
    current = request.commit('HEAD')
    committed = True
    for path in paths:
        raw = (request.ROOT / path).read_bytes()
        files.append({'repository_path': path, 'sha256': sha(raw)})
        try:
            committed = committed and request.blob(current, path) == raw
        except subprocess.CalledProcessError:
            committed = False
    # Development previews retain actual hashes and never label dirty bytes as HEAD.
    return {'git_ref': current if committed else None, 'files': files}


def preview(lock, installed_state=None, installed_state_sha256=None):
    worker.verify_lock(lock)
    request.validate(lock['request'], 'request.schema.json')
    request.validate(lock['configuration'], 'configuration.schema.json')
    source = lock['configuration']['source']
    if source not in ADAPTERS:
        raise ValueError('No reviewed configuration-preview adapter for ' + source + '; its historical replay adapter is unchanged')
    if (installed_state is None) != (installed_state_sha256 is None):
        raise ValueError('Installed-state evidence requires its explicit expected content SHA256')
    if installed_state is not None and (source != 'NCI' or lock['request']['case_variant'] != 'source-plan'):
        raise ValueError('Installed-state preflight is implemented only for the NCIt source-plan preview')
    artifacts = lock['case']['artifacts']
    for reference, item in artifacts.items():
        if reference != 'sha256:' + request.digest(item['value']):
            raise ValueError('Changed preview input artifact: ' + reference)
    module_name, method = ADAPTERS[source]
    module = importlib.import_module(module_name)
    recipe = getattr(module, method)(lock)
    payloads(recipe)
    report = {
        'schema_version': 1,
        'artifact_type': 'ncimeta-configuration-preview',
        'status': 'PREVIEW_ONLY',
        'source': source,
        'version': lock['configuration']['version'],
        'input_lock': {key: lock[key] for key in ('run_id', 'lock_sha256', 'apparatus_ref', 'runtime_ref')},
        'engine_ref': lock['configuration']['engine_ref'],
        'generator': provenance(source, installed_state is not None),
        'recipe_sha256': request.digest(recipe),
        'recipe': without_payloads(recipe),
        'release_preflight': None,
        'execution_eligible': False,
        'production_eligible': False,
        'scope': 'Offline configuration preview; no staging, conversion, runtime activation, database access or insertion',
    }
    if installed_state is not None:
        import nci_configuration as nci
        import nci_source_plan
        import nci_release_preflight
        config = lock['configuration']
        model = nci_source_plan.load(base64.b64decode(recipe['metadata_model']['data_b64'], validate=True))
        plan = artifacts[config['inputs']['source_plan']]['value']
        properties = nci.properties(nci.render_template(config, recipe['template'], recipe['bindings']['identity_state']))
        report['release_preflight'] = nci_release_preflight.analyze(
            config, plan, model, properties, installed_state, installed_state_sha256)
    return recipe, report


def write_preview(directory, recipe, report):
    files = payloads(recipe)
    if report.get('artifact_type') != 'ncimeta-configuration-preview' or report.get('recipe_sha256') != request.digest(recipe):
        raise ValueError('Preview receipt is not bound to its generated recipe')
    if report.get('recipe') != without_payloads(recipe) or report.get('execution_eligible') is not False or report.get('production_eligible') is not False:
        raise ValueError('Preview receipt contents or eligibility changed')
    directory = Path(directory)
    directory.mkdir()  # Existing directories and links are never reused.
    for name, raw in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(raw)
        path.chmod(0o444)
    path = directory / REPORT
    with path.open('x') as handle:
        json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    path.chmod(0o444)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lock', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--installed-state', type=Path)
    parser.add_argument('--installed-state-sha256', help='Expected canonical JSON content hash from the frozen snapshot manifest')
    args = parser.parse_args()
    state = request.load(args.installed_state) if args.installed_state else None
    recipe, report = preview(request.load(args.lock), state, args.installed_state_sha256)
    receipt = write_preview(args.output_dir, recipe, report)
    print(json.dumps({'status': report['status'], 'source': report['source'], 'version': report['version'],
                      'files': len(recipe['files']), 'receipt': str(receipt),
                      'release_preflight': report['release_preflight']['status'] if report['release_preflight'] else None,
                      'execution_eligible': False, 'production_eligible': False}))
    if report['release_preflight'] and report['release_preflight']['status'] == 'BLOCKED':
        raise SystemExit(3)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
