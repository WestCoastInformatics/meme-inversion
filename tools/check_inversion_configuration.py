#!/usr/bin/env python3
"""Cross-source preview, historical lock compatibility and output-safety checks."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import inversion_configuration as preview
import inversion_request as request
import inversion_worker as worker


def check():
    passed = []

    def require(value, label):
        if not value:
            raise AssertionError(label)
        passed.append(label)

    def reject(action, label):
        try:
            action()
        except (ValueError, KeyError, TypeError, RuntimeError, OSError):
            passed.append(label)
        else:
            raise AssertionError(label)

    previews = []
    for number, entry in enumerate(request.load(request.DOCS / 'case-catalog/index.json')['cases']):
        case = request.load(request.DOCS / 'case-catalog' / entry['path'])
        value = {key: case[key] for key in ('source', 'version', 'case_variant', 'reference_stage', 'comparison_profile')}
        value.update(schema_version=1, engine_ref=case['reviewed_engine_refs'][0])
        lock = request.resolve(value, 'preview-fixture-' + str(number))
        lock = json.loads(json.dumps(lock))
        before = request.digest(lock)
        worker.verify_lock(lock)
        label = value['source'] + '/' + value['case_variant']
        passed.append('Existing historical lock still validates: ' + label)
        supported = value['source'] in ('SNOMEDCT_US', 'MTH') or value['case_variant'] in ('generated-configuration', 'source-plan')
        if not supported:
            reject(lambda: preview.preview(lock), 'Unsupported configuration preview preserves replay boundary: ' + label)
            require(request.digest(lock) == before, 'Unsupported preview does not mutate historical lock: ' + label)
            continue
        recipe, report = preview.preview(lock)
        require(request.digest(lock) == before, 'Configuration preview never mutates its frozen input: ' + label)
        require(report['recipe_sha256'] == request.digest(recipe) and report['input_lock']['lock_sha256'] == lock['lock_sha256'], 'Receipt binds generated recipe and original lock: ' + label)
        require(report['input_lock']['apparatus_ref'] == lock['apparatus_ref'] and report['engine_ref'] == value['engine_ref'], 'Original apparatus/source identities remain distinct from preview generator: ' + label)
        require(report['execution_eligible'] is False and report['production_eligible'] is False, 'Preview confers no execution/production eligibility: ' + label)
        require(report['source'] == lock['configuration']['source'] and report['version'] == lock['configuration']['version'], 'Same common source/version names drive source preview: ' + label)
        with tempfile.TemporaryDirectory(prefix='configuration-preview-') as temporary:
            target = Path(temporary) / 'preview'
            receipt_path = preview.write_preview(target, recipe, report)
            retained = request.load(receipt_path)
            require(retained == report and not receipt_path.stat().st_mode & 0o222, 'Read-only saved receipt round trips: ' + label)
            require(all((target / name).read_bytes() == raw and not (target / name).stat().st_mode & 0o222 for name, raw in preview.payloads(recipe).items()), 'All generated files retain exact bytes and read-only modes: ' + label)
            reject(lambda: preview.write_preview(target, recipe, report), 'Existing preview cannot be overwritten: ' + label)
            changed = copy.deepcopy(report)
            changed['production_eligible'] = True
            reject(lambda: preview.write_preview(Path(temporary) / 'unauthorized', recipe, changed), 'Receipt cannot promote preview to production: ' + label)
        bad = copy.deepcopy(lock)
        bad['configuration']['source_atom_ids']['start'] += 1
        reject(lambda: preview.preview(bad), 'Changed frozen configuration rejected before generation: ' + label)
        if value['source'] in ('SNOMEDCT_US', 'MTH'):
            frozen = {item['relative_path']: item for item in lock['code_files'] if item.get('kind') != 'symlink'}
            matching = [item for item in recipe['files'] if item['relative_path'] in frozen]
            require(bool(matching) and all(base64.b64decode(item['data_b64'], validate=True) == base64.b64decode(frozen[item['relative_path']]['data_b64'], validate=True) for item in matching), 'Generated historical settings equal independent frozen effective settings: ' + label)
        previews.append((lock, recipe, report))

    nci_lock, nci_recipe, nci_report = next(item for item in previews if item[0]['request']['case_variant'] == 'source-plan')
    from check_nci_release_preflight import fixture as state_fixture
    import nci_release_preflight
    state = state_fixture(historical=True)[-2]
    state_sha = nci_release_preflight.content_sha256(state)
    _, blocked = preview.preview(nci_lock, state, state_sha)
    require(blocked['release_preflight']['status'] == 'BLOCKED' and
            sum(item['code'] == 'HISTORICAL_EXCEPTION_REQUIRES_REVIEW' for item in blocked['release_preflight']['findings']) == 2,
            'Common NCIt preview retains both historical findings as blocked release preflight')
    require(blocked['release_preflight']['bindings']['installed_state_sha256'] == state_sha,
            'Explicit synthetic snapshot identity is bound separately from the historical metadata model')
    reject(lambda: preview.preview(nci_lock, {}, None), 'Installed state cannot be supplied without its expected hash')
    reject(lambda: preview.preview(nci_lock, None, '0' * 64), 'Installed-state hash cannot be supplied without its snapshot')
    other_lock = next(item[0] for item in previews if item[0]['request']['source'] == 'SNOMEDCT_US')
    reject(lambda: preview.preview(other_lock, {}, '0' * 64), 'NCIt-specific preflight evidence cannot silently apply to another source')

    for name in ('', '.', '../escape', '/absolute', 'etc//duplicate', 'etc/./same', 'etc\\escape', 'etc/line\nbreak', preview.REPORT, preview.REPORT + '/nested'):
        recipe = copy.deepcopy(nci_recipe)
        recipe['files'][0]['relative_path'] = name
        reject(lambda: preview.payloads(recipe), 'Unsafe/reserved output rejected before writing: ' + name)
    for label, mutate in [
        ('duplicate path', lambda r: r['files'].append(copy.deepcopy(r['files'][0]))),
        ('file/directory collision', lambda r: r['files'].append({**r['files'][0], 'relative_path': r['files'][0]['relative_path'] + '/child'})),
        ('changed bytes', lambda r: r['files'][0].update(data_b64='Y2hhbmdlZA==')),
        ('changed digest', lambda r: r['files'][0].update(sha256='0' * 64)),
        ('writable mode', lambda r: r['files'][0].update(mode='0o644')),
    ]:
        recipe = copy.deepcopy(nci_recipe)
        mutate(recipe)
        reject(lambda: preview.payloads(recipe), 'Unsafe generated recipe rejected: ' + label)
    with tempfile.TemporaryDirectory(prefix='common-preview-cli-') as temporary:
        folder = Path(temporary)
        lock_path = folder / 'request.lock.json'
        lock_path.write_text(json.dumps(nci_lock))
        result = subprocess.run([sys.executable, '-B', str(request.ROOT / 'tools/inversion_configuration.py'), str(lock_path), '--output-dir', str(folder / 'preview')], capture_output=True, text=True)
        require(result.returncode == 0 and json.loads(result.stdout)['files'] == 5, 'Actual common CLI consumes saved NCIt lock and produces five-file preview')
        state_path = folder / 'synthetic-installed-state.json'
        state_path.write_text(json.dumps(state))
        result = subprocess.run([sys.executable, '-B', str(request.ROOT / 'tools/inversion_configuration.py'), str(lock_path),
                                 '--output-dir', str(folder / 'blocked-preview'), '--installed-state', str(state_path),
                                 '--installed-state-sha256', state_sha], capture_output=True, text=True)
        require(result.returncode == 3 and request.load(folder / 'blocked-preview' / preview.REPORT)['release_preflight']['status'] == 'BLOCKED',
                'CLI retains blocked preflight evidence and returns distinct nonzero status')
        target = folder / 'rejected'
        lock_path.write_text('{"source":"NCI","source":"MTH"}')
        result = subprocess.run([sys.executable, '-B', str(request.ROOT / 'tools/inversion_configuration.py'), str(lock_path), '--output-dir', str(target)], capture_output=True, text=True)
        require(result.returncode == 2 and not target.exists(), 'CLI rejects duplicate JSON before creating output')
        link = folder / 'symlink'
        link.symlink_to(folder / 'preview', target_is_directory=True)
        reject(lambda: preview.write_preview(link, nci_recipe, nci_report), 'Preview refuses an existing symlink destination')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'common configuration-preview checks passed')
