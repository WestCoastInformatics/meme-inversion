#!/usr/bin/env python3
"""Confined checks of archive curation; no network, native job or production data."""
import base64
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile

import check_execute_release_mth as fixtures
import curate_archived_mth as curator
import execute_release_mth as execution
import release_manifest
import release_mth

ROOT = Path(__file__).resolve().parents[1]
ENGINE = 'b2611abcf929981628bb2e5051afb450b8525b70'


def fixture(directory, skipped):
    manifest, plan, target, run, code = fixtures.fixture(directory, skipped, preserved_decisions=True)
    config, artifacts = manifest['configuration'], manifest['artifacts']
    current = config['version']
    data = artifacts['mth-plan']['data']
    baseline, previous = config['replacement_baseline']['version'], data['publisher_previous']['version']
    values = {'rel': current[4:], 'prevrel': previous[4:]}
    for index, version in enumerate(data['publisher_release_chain'][:-2], 2):
        values['prevrel' + str(index)] = version[4:]
    def predicate(kind, field):
        tokens = []
        for release in data['history_selection'][kind]:
            key = next(key for key, value in values.items() if value == release[4:])
            tokens.append('$' + str(field) + '=="\'$' + key + '\'"')
        return ' || '.join(tokens)
    script = '#!/bin/tcsh -f\n' + ''.join('set ' + key + '=' + value + '\n' for key, value in values.items())
    script += "awk -F\\| '$9==\"Y\" && (" + predicate('moved_aui_releases', 3) + "){print $1 \"|\" $8}' Meta/MRAUI.RRF >auis.moved\n"
    script += "awk -F\\| '$3==\"SY\" && $7==\"Y\" && (" + predicate('cui_merge_releases', 2) + "){print $1 \"|\" $6}' Meta/MRCUI.RRF >cui_merges\n"
    script += "#awk -F\\| '$2==\"1900AA\"' Meta/MRCUI.RRF >cui_merges\n"
    raw = {role: (target / role).read_bytes() for role in release_mth.METADATA_ROLES}
    raw.update({role: (target / 'orig/source-plan' / role).read_bytes() for role in curator.DECISIONS})
    raw.update({'invert1.s': script.encode(), 'range3.spec': (target / 'range3.spec').read_bytes(),
                # Archived native specs scan MRCUI*, while canonical rendering
                # deliberately names its composed history file explicitly.
                'src/inv3.spec': (target / 'src/inv3.spec').read_bytes().replace(b'bequeathal_history.RRF', b'MRCUI*')})
    raw.update({'src/' + name: ('SYNTHETIC reference descriptor only: ' + name + '\n').encode()
                for name in execution.OUTPUT_NAMES})
    archive = directory / 'synthetic-source.tgz'
    with tarfile.open(archive, 'w:gz') as handle:
        for path, content in raw.items():
            info = tarfile.TarInfo(current + '/' + path);info.size = len(content)
            handle.addfile(info, io.BytesIO(content))
        for name, version in [('old', baseline), ('prev', previous)]:
            info = tarfile.TarInfo(current + '/' + name);info.type = tarfile.SYMTYPE;info.linkname = '../' + version
            handle.addfile(info)
    members = {path: {'kind': 'file', 'sha256': curator.digest(content), 'bytes': len(content),
                      'data_b64': base64.b64encode(content).decode()} for path, content in raw.items()}
    members.update({name: {'kind': 'symlink', 'target': '../' + version}
                    for name, version in [('old', baseline), ('prev', previous)]})
    prepared_files = copy.deepcopy(artifacts['mth-prepared']['files'])
    facts = {}
    for role, index in [('MRAUI.RRF', 2), ('MRCUI.RRF', 1)]:
        descriptor = next(item for item in prepared_files if item['role'] == role)
        rows = Path(descriptor['uri'].removeprefix('file://')).read_bytes().splitlines(keepends=True)
        versions = {}
        for row in rows:
            version = execution._fields(row)[index].decode();versions[version] = versions.get(version, 0) + 1
        facts[role] = {**curator._identity(descriptor, role), 'rows': len(rows), 'malformed_rows': 0, 'versions': versions}
    mrsab = next(item for item in prepared_files if item['role'] == 'MRSAB.RRF')
    identity = artifacts['mth-identity']['files'][0]
    capture = {'version': current, 'evidence_kind': 'synthetic-fixture',
        'archive': {'uri': archive.as_uri(), 'sha256': curator.digest(archive.read_bytes()), 'bytes': archive.stat().st_size},
        'members': members, 'prepared': {'files': prepared_files, 'facts': facts,
            'mrsab_data_b64': base64.b64encode(Path(mrsab['uri'].removeprefix('file://')).read_bytes()).decode(),
            'subset_directory': 'subset3/METASUBSET',
            'history_coverage': copy.deepcopy(data['history_selection']),
            'history_coverage_evidence': 'SYNTHETIC complete fixture history; no real release claim'},
        'prior_identity': {'version': baseline, 'files': [copy.deepcopy(identity)],
            'facts': {**curator._identity(identity, 'prior'), 'rows': 2, 'malformed_rows': 0}},
        'reference_stage_evidence': {'reference_stage': 'inversion-src',
            'description': 'SYNTHETIC descriptor fixture only; no native output equivalence asserted'}}
    capture['prepared']['history_coverage'].pop('review_status', None)
    return capture, target, code


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def blocked(capture, code, label, review='SYNTHETIC-PRESERVATION-REVIEW', engine=ENGINE):
        result = curator.curate(capture, engine, review)
        good(result['manifest'] is None and any(issue['code'] == code for issue in result['issues']), label)
    with tempfile.TemporaryDirectory(prefix='mth-curation-') as temporary:
        base = Path(temporary)
        for skipped in (False, True):
            directory = base / str(skipped);directory.mkdir()
            capture, target, code = fixture(directory, skipped)
            result = curator.curate(capture, ENGINE, 'SYNTHETIC-PRESERVATION-REVIEW')
            good(result['manifest'] is not None and not result['issues'], 'complete ' + ('skipped' if skipped else 'direct') + ' transition curated')
            manifest = result['manifest'];artifacts = manifest['artifacts'];config = manifest['configuration']
            good(not release_manifest.schema_errors(manifest, json.loads((ROOT / 'docs/inversion-review/release-manifest.schema.json').read_text())), 'manifest JSON schema ' + str(skipped))
            good(not release_mth.analyze(config, artifacts)['issues'], 'independent source preflight ' + str(skipped))
            plan = execution.build_plan(config, artifacts, code)
            good(execution.validate_inputs(plan, target)['passed'], 'independent physical input scan and preserved decision projection ' + str(skipped))
            good(next(item for item in plan['input_files'] if item['role'] == 'cui_said_map')['destination'].startswith('orig/identity/'), 'prior identity stays frozen inside candidate ' + str(skipped))
            good(all(item['provenance']['evidence_kind'] == 'synthetic-fixture' for item in artifacts.values()), 'synthetic origin cannot masquerade as real capture ' + str(skipped))
            good(config['source_atom_ids']['start'] + 2 == int((target / 'range3.spec').read_text().splitlines()[0].split('|')[1]), 'native base maps to SRC-inclusive range ' + str(skipped))
            good(config['replacement_baseline']['version'] != artifacts['mth-plan']['data']['publisher_previous']['version'] if skipped else config['replacement_baseline']['version'] == artifacts['mth-plan']['data']['publisher_previous']['version'], 'inserted and publisher predecessors retain distinct meanings ' + str(skipped))
            good(artifacts['mth-allocation']['data']['new_allocation_performed'] is False and not result['facts']['production_eligible'], 'curation performs no allocation/admission ' + str(skipped))
            again = curator.curate(capture, ENGINE, 'SYNTHETIC-PRESERVATION-REVIEW')
            good(result == again, 'deterministic repeated curation ' + str(skipped))
        mutation_directory = base / 'mutations'
        mutation_directory.mkdir()
        capture, target, code = fixture(mutation_directory, True)
        blocked(capture, 'MTH_CURATION_REVIEW', 'review cannot be inferred', review=None)
        blocked(capture, 'MTH_CURATION_ENGINE', 'mutable engine ref rejected', engine='HEAD')
        changed = copy.deepcopy(capture);changed.pop('prepared')
        blocked(changed, 'MTH_CAPTURE_PREPARED_CLOSURE', 'missing prepared bundle withholds manifest')
        changed = copy.deepcopy(capture);changed['prepared']['files'].pop()
        blocked(changed, 'MTH_CAPTURE_PREPARED_CLOSURE', 'missing native RRF withholds manifest')
        changed = copy.deepcopy(capture);changed['prepared']['mrsab_data_b64'] = base64.b64encode(b'changed').decode()
        blocked(changed, 'MTH_CAPTURE_MRSAB', 'MRSAB body must match frozen identity')
        changed = copy.deepcopy(capture);changed['members']['old']['target'] = '../MTH_1900AA'
        blocked(changed, 'MTH_CAPTURE_LINEAGE', 'old link cannot override saved installed state')
        changed = copy.deepcopy(capture);changed['members']['prev']['target'] = '../MTH_1900AA'
        blocked(changed, 'MTH_CAPTURE_LINEAGE', 'publisher previous must agree with actual script')
        changed = copy.deepcopy(capture);changed['members']['invert1.s']['data_b64'] = base64.b64encode(b'changed').decode()
        blocked(changed, 'MTH_CAPTURE_INVALID', 'captured member byte mutation rejected')
        changed = copy.deepcopy(capture);changed['members']['../outside'] = changed['members']['invert1.s']
        blocked(changed, 'MTH_CAPTURE_INVALID', 'unsafe member rejected')
        changed = copy.deepcopy(capture);changed['prepared'].pop('history_coverage_evidence')
        blocked(changed, 'MTH_CAPTURE_HISTORY_COVERAGE', 'observed rows cannot invent completeness')
        changed = copy.deepcopy(capture);changed['prepared']['facts']['MRAUI.RRF']['sha256'] = '0' * 64
        blocked(changed, 'MTH_CAPTURE_HISTORY_COVERAGE', 'history scan must match exact prepared object')
        changed = copy.deepcopy(capture);changed['prepared']['history_coverage']['cui_merge_releases'] = []
        blocked(changed, 'MTH_CAPTURE_HISTORY_COVERAGE', 'missing skipped-release history rejected')
        changed = copy.deepcopy(capture);changed['prior_identity']['version'] = capture['version']
        blocked(changed, 'MTH_CAPTURE_PRIOR_IDENTITY', 'current map cannot become prior identity')
        changed = copy.deepcopy(capture);changed['prior_identity']['facts']['rows'] = 0
        blocked(changed, 'MTH_CAPTURE_PRIOR_IDENTITY', 'empty prior identity rejected')
        changed = copy.deepcopy(capture);changed['reference_stage_evidence']['reference_stage'] = 'insertion-package'
        blocked(changed, 'MTH_CAPTURE_REFERENCE_STAGE', 'insertion-mutated reference stage rejected')
        changed = copy.deepcopy(capture);changed['members'].pop('src/attributes.src')
        blocked(changed, 'MTH_CAPTURE_REFERENCE_FILES', 'partial reference output set rejected')
        changed = copy.deepcopy(capture);changed['prepared']['subset_directory'] = '../META'
        blocked(changed, 'MTH_CAPTURE_SUBSET', 'arbitrary native destination rejected')
        # Recompute captured identity after an intentional evidence edit: this is
        # a semantic contradiction, rather than merely a stale digest test.
        changed = copy.deepcopy(capture)
        raw = base64.b64decode(changed['members']['src/inv3.spec']['data_b64'])
        raw = raw.replace(b"<REL> eq 'RN'", b"<REL> eq 'XX'")
        changed['members']['src/inv3.spec'] = {'kind': 'file', 'sha256': curator.digest(raw), 'bytes': len(raw), 'data_b64': base64.b64encode(raw).decode()}
        blocked(changed, 'MTH_CAPTURE_LINEAGE', 'all three bequeathal branches must establish same selection')
        changed = copy.deepcopy(capture);raw = b'SourceAtomIdBase|1002\nSourceAtomIdBase|1003\nSourceAtomIdLimit|1009\n'
        changed['members']['range3.spec'] = {'kind': 'file', 'sha256': curator.digest(raw), 'bytes': len(raw), 'data_b64': base64.b64encode(raw).decode()}
        blocked(changed, 'MTH_CAPTURE_RANGE', 'duplicate captured range settings rejected')
        # Exercise the actual root capture wrapper adapter, preserving its
        # inventory/body identity boundary independently of normalized form.
        entries = [{'path': capture['version'], 'size': 0, 'kind': 'directory'}]
        bodies = {}
        for path, member in capture['members'].items():
            entry = {key: value for key, value in member.items() if key != 'data_b64'}
            entry.update(path=capture['version'] + '/' + path, size=entry.pop('bytes', 0));entries.append(entry)
            if 'data_b64' in member:bodies[entry['path']] = {key: member[key] for key in ('sha256', 'bytes', 'data_b64')}
        wrapper = {'result': {'mth_existing': {'version': capture['version'],
            'reference': {'version': capture['version'], 'bucket': 'synthetic-bucket', 'key': 'fixture.tgz',
                          'archive_sha256': capture['archive']['sha256'], 'archive_bytes': capture['archive']['bytes']},
            'inventory': {'version': capture['version'], 'archive_sha256': capture['archive']['sha256'],
                          'archive_bytes': capture['archive']['bytes'], 'entries': entries}, 'captures': bodies}}}
        normalized = curator.normalize(wrapper)
        good(curator._lineage(normalized)['publisher_release_chain'] == curator._lineage(capture)['publisher_release_chain'], 'real wrapper adapter preserves lineage evidence')
        partial = curator.curate(wrapper, ENGINE, 'SYNTHETIC-PRESERVATION-REVIEW')
        good(partial['manifest'] is None and partial['facts']['preserved_staff_decisions']['rows'] == 3, 'partial inventory still reports original decision facts')
        broken = copy.deepcopy(wrapper);broken['result']['mth_existing']['inventory']['entries'][1]['sha256'] = '0' * 64
        blocked(broken, 'MTH_CAPTURE_INVALID', 'inventory/body conflicting identities rejected')
        try:
            curator.normalize(wrapper, {'version': 'MTH_1900AA'})
            raise AssertionError('supplement overwrote captured version')
        except ValueError:
            passed.append('supplement cannot overwrite captured evidence')
    print(json.dumps({'passed': len(passed), 'checks': passed}, indent=2))


if __name__ == '__main__':
    check()
