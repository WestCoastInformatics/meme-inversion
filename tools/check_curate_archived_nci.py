#!/usr/bin/env python3
"""Tiny synthetic archive checks for the NCIt curator; no real-release claim."""
import copy
import base64
import io
import json
import tarfile

import check_execute_release_nci
import curate_archived_nci as curator
import execute_release_nci as execute
import release_nci


def fixture(version='NCI_2026_08E', prior='NCI_2026_06E'):
    original, _, raw = check_execute_release_nci.fixture(version, prior, False)
    config, artifacts = original['configuration'], original['artifacts']
    members = {}
    for descriptor in artifacts['publisher']['files']:
        members[version + '/orig/fromprovider/' + descriptor['uri'].rsplit('/', 1)[1]] = raw[descriptor['role']]
    for role, path in (('sources-src', 'src/sources.src'), ('termgroups-src', 'src/termgroups.src'), ('nci-configuration', 'etc/nci.cfg')):
        members[version + '/' + path] = raw[role]
    members[version + '/bin/invert_NCI.pl'] = b'# SYNTHETIC review-only producer placeholder; never executed\n'
    for name in execute.OUTPUTS:
        members[version + '/' + name] = b'SYNTHETIC oracle placeholder; not a valid inversion\n'
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w:gz') as outgoing:
        for name, value in members.items():
            info = tarfile.TarInfo(name);info.size = len(value);outgoing.addfile(info, io.BytesIO(value))
    compressed = archive.getvalue()
    inventory = {'version': version, 'archive_sha256': execute._sha(compressed), 'archive_bytes': len(compressed),
                 'entries': [{'path': name, 'kind': 'file', 'size': len(value), 'sha256': execute._sha(value), 'newline_count': value.count(b'\n')} for name, value in members.items()]}
    captured = {name: value for name, value in members.items() if name.endswith(('/etc/nci.cfg', '/src/sources.src', '/src/termgroups.src', '/bin/invert_NCI.pl'))}
    args = [inventory, captured, artifacts['release-plan']['data'], artifacts['representation-policy']['data']['metadata_model']]
    kwargs = {'engine_ref': check_execute_release_nci.check_release_nci.ENGINE, 'allocation_end': 10010000,
              'allocation_decision': 'SYNTHETIC isolated-dev cap; no historical or production allocation claim',
              'capture_id': 'synthetic-curation-' + version, 'evidence_kind': 'synthetic-fixture'}
    return args, kwargs


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def reject(label, change):
        args, kwargs = fixture();change(args, kwargs)
        try:curator.curate(*args, **kwargs)
        except (ValueError, KeyError):checks.append(label)
        else:raise AssertionError(label)
    args, kwargs = fixture();before = copy.deepcopy((args, kwargs))
    manifest = curator.curate(*args, **kwargs)
    bundle = {'version': args[0]['version'], 'inventory': args[0], 'reference': {'source': 'NCI', 'version': args[0]['version'], 'archive_sha256': args[0]['archive_sha256'], 'archive_bytes': args[0]['archive_bytes']},
              'captures': {name: {'data_b64': base64.b64encode(raw).decode(), 'sha256': execute._sha(raw), 'bytes': len(raw)} for name, raw in args[1].items()}}
    good(curator.curate_capture(bundle, args[2], args[3], **kwargs) == manifest, 'Existing collector bundle shape produces the identical curated manifest')
    mismatched = copy.deepcopy(bundle);mismatched['reference']['archive_sha256'] = 'a' * 64
    try:curator.curate_capture(mismatched, args[2], args[3], **kwargs)
    except ValueError:checks.append('Acquisition receipt and inventory from different archives are rejected')
    else:raise AssertionError('Mismatched collector receipt was accepted')
    good((args, kwargs) == before, 'Curation leaves all inventory/capture/review/allocation inputs immutable')
    good(manifest == curator.curate(*args, **kwargs), 'Same frozen inventory and review decisions produce identical manifest')
    config, artifacts = manifest['configuration'], manifest['artifacts']
    good(config['version'] == 'NCI_2026_08E' and config['replacement_baseline']['version'] == 'NCI_2026_06E', 'Predecessor comes from physical source metadata and supports skipped calendar months')
    good(config['source_atom_ids']['start'] == 10000 and config['source_atom_ids']['end'] == 10010000 and config['source_atom_ids']['bound_kind'] == 'dev-reservation', 'Native seed comes from captured cfg and isolated cap from explicit caller decision, never oracle rows')
    second, options = fixture('NCI_2027_02B', 'NCI_2026_12C')
    good(curator.curate(*second, **options)['configuration']['replacement_baseline']['version'] == 'NCI_2026_12C', 'One curator supports a second version/predecessor combination without new case constants')
    good(all(value['provenance']['evidence_kind'] == 'synthetic-fixture' for value in artifacts.values()), 'Synthetic archives are never relabeled as genuine preserved evidence')
    good(all(file['archive_sha256'] == args[0]['archive_sha256'] and file['archive_bytes'] == args[0]['archive_bytes'] for value in artifacts.values() for file in value['files']), 'Every selected descriptor binds the complete exact archive identity')
    recipe = execute.build_plan(config, artifacts)
    good(not any(item['artifact'] == 'official-reference' for item in recipe['input_files']), 'Completed official src outputs never become candidate seed files')
    good(not any(item['artifact'] == 'release-plan' for item in recipe['input_files']), 'Archived producer code is review-only evidence and never staged/executed')
    preview = release_nci.analyze(config, artifacts)
    good(not any(row['severity'] == 'error' for row in preview['issues']) and not preview['facts']['execution_authorized'], 'Curated manifest satisfies source declarations while physical/admission gates remain separate')
    reject('Changed captured configuration bytes cannot borrow inventory hashes', lambda a, k: a[1].update({a[0]['version'] + '/etc/nci.cfg': b'SaidStart = 1\n'}))
    reject('A reviewed plan cannot silently choose another predecessor', lambda a, k: a[2].update(replacement_baseline={'source': 'NCI', 'version': 'NCI_2026_07A'}))
    reject('No review-only producer capture means no inferred optional-root decision', lambda a, k: a[1].pop(a[0]['version'] + '/bin/invert_NCI.pl'))
    reject('Oracle outputs cannot be captured as conversion-setting inputs', lambda a, k: a[1].update({a[0]['version'] + '/src/classes_atoms.src': b'not allowed\n'}))
    reject('A duplicate archive member cannot be selected ambiguously', lambda a, k: a[0]['entries'].append(copy.deepcopy(a[0]['entries'][0])))
    reject('Allocation cap cannot be below the preserved starting seed', lambda a, k: k.update(allocation_end=9999))
    reject('A numeric lookalike is not an exact allocation end', lambda a, k: k.update(allocation_end=True))
    reject('An unexplained numeric cap is not allocation evidence', lambda a, k: k.update(allocation_decision=''))
    def ambiguous(a, k):
        value = copy.deepcopy(a[0]['entries'][0]);value['path'] = value['path'].replace('20261001', '20260801');a[0]['entries'].append(value)
    reject('Multiple publisher dates require explicit file selection, not newest-date inference', ambiguous)
    args, kwargs = fixture();ambiguous(args, kwargs)
    selectors = {role: next(row['path'] for row in args[0]['entries'] if '/' + role + '-20261001.txt' in row['path']) for role in execute.ROLES}
    good(curator.curate(*args, **kwargs, native_members=selectors)['artifacts']['publisher']['files'][0]['archive_member'].endswith('annotationDeclaration-20261001.txt'), 'Explicit reviewed native selectors resolve multiple preserved dates')
    def attribute_variant(a, k):
        version = a[0]['version'];final = next(row for row in a[0]['entries'] if row['path'] == version + '/src/attributes.src')
        original = copy.deepcopy(final);original.update(path=version + '/src/attributes.orig', sha256='c' * 64, size=5, newline_count=1)
        final['newline_count'] = 2;a[0]['entries'].append(original)
        return original, final
    reject('Different attributes.orig cannot be selected without archived stage proof', attribute_variant)
    args, kwargs = fixture();original, final = attribute_variant(args, kwargs)
    proof = {'status': 'PRE_INSERTION_PREFIX_VERIFIED', 'archive_sha256': args[0]['archive_sha256'],
             'original_member': original['path'], 'final_member': final['path'], 'original_sha256': original['sha256'], 'final_sha256': final['sha256'],
             'original_bytes': original['size'], 'original_rows': 1, 'final_rows': 2, 'appended_rows': 1,
             'appended_attribute_names': {'SEMANTIC_TYPE': 1}, 'original_prefix_byte_exact': True}
    selected = curator.curate(*args, **kwargs, attribute_stage_relation=proof)
    good(next(row for row in selected['artifacts']['official-reference']['files'] if row['role'] == 'src/attributes.src')['archive_member'].endswith('/attributes.orig'), 'Only explicitly supplied matching stage-proof selects pre-insertion attributes.orig')
    wrong = copy.deepcopy(proof);wrong['archive_sha256'] = 'd' * 64
    try:curator.curate(*args, **kwargs, attribute_stage_relation=wrong)
    except ValueError:checks.append('Stage proof from a different archive cannot approve an attribute boundary')
    else:raise AssertionError('Mismatched stage proof was accepted')
    return checks


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'scope': 'synthetic archive curation only'}))
