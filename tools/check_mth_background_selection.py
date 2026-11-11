#!/usr/bin/env python3
"""Preserved background SCT UPDATE versus actual REST selection; no server/S3."""
import base64
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile

import check_curate_archived_mth as fixtures
import check_execute_release_mth as native
import check_release_mth
import curate_archived_mth as curator
import execute_release_mth as execution
import release_mth


def _capture_body(capture, role, raw):
    capture['members'][role] = {'kind': 'file', 'sha256': curator.digest(raw),
                                'bytes': len(raw), 'data_b64': base64.b64encode(raw).decode()}


def _refresh_archive(capture):
    path = Path(capture['archive']['uri'].removeprefix('file://'))
    with tarfile.open(path, 'w:gz') as handle:
        for relative, value in capture['members'].items():
            entry = tarfile.TarInfo(capture['version'] + '/' + relative)
            if value.get('kind') == 'symlink':
                entry.type = tarfile.SYMTYPE;entry.linkname = value['target'];handle.addfile(entry)
            else:
                raw = base64.b64decode(value['data_b64']);entry.size = len(raw);handle.addfile(entry, io.BytesIO(raw))
    capture['archive'].update(sha256=curator.digest(path.read_bytes()), bytes=path.stat().st_size)


def fixture(directory):
    capture, target, code = fixtures.fixture(directory, skipped=True)
    sct = 'SNOMEDCT_US_2027_03_01'
    additions = {'ncisources.spec': ('SNOMEDCT_US|' + sct + '|UPDATE|exclude termgroups: IS,XM\nSRC|SRC|KEEP|\n').encode(),
                 'sab.vsab.map': ('SNOMEDCT_US|' + sct + '|same\nSRC|SRC|same\n').encode(),
                 'ncimid.sources': ('SNOMEDCT_US|' + sct + '\nSRC|SRC\n').encode()}
    for role, raw in additions.items():_capture_body(capture, role, curator._body(capture, role) + raw)
    descriptor = next(item for item in capture['prepared']['files'] if item['role'] == 'MRSAB.RRF')
    path = Path(descriptor['uri'].removeprefix('file://'))
    raw = path.read_bytes()
    for source, version in [('SNOMEDCT_US', sct), ('SRC', 'SRC')]:
        columns = [''] * 25
        columns[:7] = ['VC' + source, 'RC' + source, version, source, 'SYNTHETIC ' + source, source, version]
        columns[21:23] = ['Y', 'Y']
        raw += ('|'.join(columns) + '|\n').encode()
    path.write_bytes(raw);descriptor.update(sha256=curator.digest(raw), bytes=len(raw))
    capture['prepared']['mrsab_data_b64'] = base64.b64encode(raw).decode()
    _refresh_archive(capture)
    result = curator.curate(capture, fixtures.ENGINE, 'SYNTHETIC-PRESERVED-BACKGROUND-REVIEW')
    assert result['manifest'] is not None, result['issues']
    manifest = result['manifest']
    plan = execution.build_plan(manifest['configuration'], manifest['artifacts'], code)
    for item in plan['input_files']:
        descriptor = next(value for value in manifest['artifacts'][item['artifact']]['files'] if value['role'] == item['role'])
        path = Path(descriptor['uri'].removeprefix('file://'))
        if 'archive_member' in descriptor:
            with tarfile.open(path, 'r:gz') as handle:raw = handle.extractfile(descriptor['archive_member']).read()
        else:
            raw = path.read_bytes()
        destination = execution.input_path(item, target)
        if destination.exists():destination.chmod(0o644)
        destination.write_bytes(raw);destination.chmod(0o444)
    for item in plan['generated_files']:
        path = target / item['relative_path']
        if path.exists():path.chmod(0o644)
        path.write_bytes(base64.b64decode(item['data_b64']));path.chmod(0o444)
    run = directory / 'run'
    (run / 'native-plan.json').write_text(json.dumps(plan))
    return capture, result, manifest, plan, target, run, code


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def rejects(manifest, code, label):
        check_release_mth.bind_producer_inputs(manifest)
        result = release_mth.analyze(manifest['configuration'], manifest['artifacts'])
        good(any(item['code'] == code and item['severity'] in ('error', 'blocker') for item in result['issues']), label)
    with tempfile.TemporaryDirectory(prefix='mth-background-') as temporary:
        root = Path(temporary).resolve();directory = root / 'with-background';directory.mkdir()
        captured, result, manifest, plan, target, run, code = fixture(directory)
        data = manifest['artifacts']['mth-plan']['data'];prepared = manifest['artifacts']['mth-prepared']['data']
        background = next(item for item in data['dispositions'] if item['source'] == 'SNOMEDCT_US')
        good(background['disposition'] == 'UPDATE' and background['version'] == background['prior_version'], 'original same-version staff SCT UPDATE remains unchanged')
        good(set(prepared['selected_sources']) == {'MTH', 'TEST', 'NEWSOURCE'} and 'SNOMEDCT_US' not in prepared['selected_sources'] and 'SRC' not in prepared['selected_sources'], 'actual REST VSAB updates omit canonical SCT and SRC background rows')
        facts = result['facts']['source_preflight']
        good(result['issues'] == [] and facts['declared_prepared_inputs_consistent'], 'bound preserved background choice passes declared source preflight')
        good(facts['retained_background_choices'] == [{'code': 'MTH_NONSELECTED_SAME_VERSION_UPDATE',
            'source': 'SNOMEDCT_US', 'version': background['version'], 'disposition': 'UPDATE',
            'reason': 'Original staff UPDATE retained outside the canonical prepared REST subset; no UPDATE of this source is executed.'}], 'retained background UPDATE is an explicit informational fact')
        good(execution.validate_inputs(plan, target)['passed'], 'actual original decision data, saved installed inventory, MRSAB and REST metadata validate together')
        generated = next(item for item in plan['generated_files'] if item['relative_path'] == 'ncisources.spec')
        good(('SNOMEDCT_US|' + background['version'] + '|UPDATE|exclude termgroups: IS,XM\n').encode() in base64.b64decode(generated['data_b64']), 'generated policy does not rewrite UPDATE to KEEP or EXCLUDE')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-prepared']['data']['selected_sources'].append('SNOMEDCT_US')
        rejects(changed, 'MTH_UPDATE_VERSION', 'selected same-version SCT UPDATE rejected')
        rejects(changed, 'MTH_PREPARED_SELECTION', 'selecting excluded SCT cannot bypass canonical REST branch')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-prepared']['data']['selected_sources'].remove('TEST')
        rejects(changed, 'MTH_PREPARED_SELECTION', 'arbitrarily omitted active source rejected')
        rejects(changed, 'MTH_UPDATE_VERSION', 'arbitrary omission also revokes background retention evidence')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-prepared']['data'].pop('selected_sources')
        rejects(changed, 'MTH_UPDATE_VERSION', 'missing selected set cannot imply background exclusion')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-prepared']['data'].pop('selection_evidence')
        rejects(changed, 'MTH_UPDATE_VERSION', 'selected names without original byte evidence cannot admit background UPDATE')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-prepared']['data']['selection_evidence']['vsab_updates_sha256'] = '0' * 64
        rejects(changed, 'MTH_PREPARED_SELECTION_BINDING', 'different saved VSAB-update bytes revoke retention evidence')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-plan']['data']['preserved_snapshot_sha256']['MRSAB.RRF'] = '0' * 64
        rejects(changed, 'MTH_PREPARED_SELECTION_BINDING', 'background source must bind actual prepared MRSAB projection')
        changed = copy.deepcopy(manifest);changed['artifacts']['mth-plan']['files'].pop()
        rejects(changed, 'MTH_UPDATE_VERSION', 'missing original decision data cannot approve background UPDATE')
        changed = copy.deepcopy(manifest)
        next(item for item in changed['artifacts']['mth-plan']['data']['dispositions'] if item['source'] == 'TEST')['disposition'] = 'UPDATE'
        rejects(changed, 'MTH_UPDATE_VERSION', 'selected same-version ordinary UPDATE remains invalid with otherwise complete evidence')
        changed = copy.deepcopy(manifest)
        next(item for item in changed['artifacts']['mth-plan']['data']['dispositions'] if item['source'] == 'SNOMEDCT_US')['review_status'] = 'proposed'
        rejects(changed, 'MTH_REVIEW_REQUIRED', 'background retention cannot approve a proposed staff decision')
        # Prove actual original-byte reparsing rather than trusting the typed
        # background assertion. A locked original raw change is still rejected.
        original_path = target / 'orig/source-plan/ncisources.spec';raw = original_path.read_bytes()
        original_path.chmod(0o644);original_path.write_bytes(raw.replace(b'|UPDATE|exclude termgroups: IS,XM', b'|KEEP|exclude termgroups: IS,XM'));original_path.chmod(0o444)
        physical = execution.validate_inputs(plan, target)
        good(not physical['passed'] and any(item['code'] == 'MTH_PRESERVED_DECISION_MISMATCH' for item in physical['issues']), 'physical preserved background policy contradicting typed choices is rejected')
        original_path.chmod(0o644);original_path.write_bytes(raw);original_path.chmod(0o444)
        updates = target / 'src/vsab.updates';raw = updates.read_bytes()
        updates.chmod(0o644);updates.write_bytes(raw.replace(b'|TEST_2026\n', b''));updates.chmod(0o444)
        physical = execution.validate_inputs(plan, target)
        good(not physical['passed'] and any(item['code'] == 'MTH_PREPARED_SUBSET' for item in physical['issues']), 'actual omitted VSAB-update source cannot bypass physical subset validation')
        updates.chmod(0o644);updates.write_bytes(raw);updates.chmod(0o444)
        good(execution.validate_inputs(plan, target)['passed'], 'restoring exact original bytes restores physical input acceptance')
        baseline_directory = root / 'baseline';baseline_directory.mkdir()
        _, baseline_plan, baseline_target, baseline_run, _ = native.fixture(baseline_directory, skipped=True, preserved_decisions=True)
        native.run_tiny(baseline_plan, baseline_target, baseline_run)
        native.run_tiny(plan, target, run)
        good(execution.validate_outputs(plan, target)['passed'], 'actual tiny conversion with background SCT passes retained-identity/range/core validation')
        for name in execution.OUTPUT_NAMES:
            good((target / 'src' / name).read_bytes() == (baseline_target / 'src' / name).read_bytes(), 'background staff choice leaves native prepared REST output byte-identical: ' + name)
    print(json.dumps({'passed': len(passed), 'checks': passed}, indent=2))


if __name__ == '__main__':check()
