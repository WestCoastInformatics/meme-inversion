#!/usr/bin/env python3
"""Curate an NCIt historical manifest from verified archive inventory/captures.

No network, extraction, native execution or output-derived conversion settings.
Callers supply explicit reviewed source decisions, representation vocabulary and
an isolated dev allocation end. Every captured byte is checked against inventory;
the worker independently verifies the complete archive and selected members.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

import execute_release_nci as execute
import nci_source_plan


def _rows(raw, fields):
    result = []
    for line in raw.splitlines(keepends=True):
        if not line.endswith(b'\n') or b'\r' in line or b'\x00' in line:
            raise ValueError('Captured metadata must have canonical UTF-8 pipe rows')
        values = line.decode().removesuffix('\n').split('|')
        if len(values) != len(fields) + 1 or values[-1] != '':
            raise ValueError('Captured metadata field count differs from the loader')
        result.append(dict(zip(fields, values[:-1])))
    if not result:
        raise ValueError('Captured metadata is empty')
    return result


def curate(inventory, captured_members, reviewed_plan, metadata_model, *, engine_ref,
           allocation_end, allocation_decision, capture_id, evidence_kind,
           attribute_stage_relation=None, native_members=None):
    """Return a genuine-or-explicitly-synthetic historical release manifest.

    captured_members maps canonical archive member names to original bytes.
    Required captures: etc/nci.cfg, src/sources.src, src/termgroups.src and the
    archived bin/invert_NCI.pl (review evidence only, never staged/executed).
    native_members is an optional explicit role->member selector when an archive
    contains multiple dated publisher exports. No latest-date inference occurs.
    """
    version = inventory['version'];execute._version(version)
    if not re.fullmatch(r'[0-9a-f]{40}', engine_ref):
        raise ValueError('An actual full Git source engine commit is required')
    if evidence_kind not in ('preserved', 'synthetic-fixture') or not isinstance(capture_id, str) or not capture_id.strip():
        raise ValueError('Explicit honest preserved/synthetic provenance and capture identity are required')
    if not isinstance(allocation_decision, str) or not allocation_decision.strip() or not execute._positive(allocation_end):
        raise ValueError('An explicit isolated-dev allocation decision and positive end are required')
    archive_sha = inventory['archive_sha256'];archive_bytes = inventory['archive_bytes']
    if not re.fullmatch('[0-9a-f]{64}', archive_sha) or type(archive_bytes) is not int or archive_bytes <= 0:
        raise ValueError('Complete archive byte identity is required')
    entries = {}
    for entry in inventory['entries']:
        name = entry['path'];path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or str(path) != name or name in entries:
            raise ValueError('Unsafe or ambiguous archive inventory member')
        entries[name] = entry
    prefix = version + '/'
    core_members = {prefix + item for item in execute.OUTPUTS} | {prefix + 'src/attributes.orig'}
    for name, raw in captured_members.items():
        if name in core_members:
            raise ValueError('Completed reference outputs are comparison-only, not curator input captures')
        entry = entries.get(name)
        if not name.startswith(prefix) or not isinstance(raw, bytes) or not entry or entry['kind'] != 'file' or len(raw) != entry['size'] or execute._sha(raw) != entry['sha256']:
            raise ValueError('Captured member bytes differ from inventory: ' + name)
    required = [prefix + item for item in ('etc/nci.cfg', 'src/sources.src', 'src/termgroups.src', 'bin/invert_NCI.pl')]
    if any(name not in captured_members for name in required):
        raise ValueError('Exact configuration, source/termgroup metadata and review-only producer captures are required')
    properties = execute._properties(captured_members[prefix + 'etc/nci.cfg'])
    sources = _rows(captured_members[prefix + 'src/sources.src'], nci_source_plan.SOURCE_FIELDS)
    _rows(captured_members[prefix + 'src/termgroups.src'], nci_source_plan.TERMGROUP_FIELDS)
    primary = [row for row in sources if row['source_name'] == version and row['stripped_source'] == 'NCI']
    if len(primary) != 1:
        raise ValueError('One primary source metadata row must establish the explicit predecessor')
    prior_version = primary[0]['low_source'];execute._version(prior_version)
    if prior_version >= version:
        raise ValueError('Captured primary predecessor is not earlier than the current release')
    baseline = {'source': 'NCI', 'version': prior_version}
    try:
        start = int(properties['SaidStart']);root = int(properties['HC.RootNodeSaid'])
    except (KeyError, ValueError) as error:
        raise ValueError('Saved source/root IDs must come from captured configuration') from error
    if start <= 0 or root <= 0 or str(start) != properties['SaidStart'] or str(root) != properties['HC.RootNodeSaid'] or allocation_end < start:
        raise ValueError('Preserved seeds and explicit dev end must be canonical ordered positive IDs')
    if not isinstance(reviewed_plan, dict) or reviewed_plan.get('version') != version or reviewed_plan.get('replacement_baseline') != baseline:
        raise ValueError('A separately reviewed source plan must match captured current/prior identities')
    selected_native = {}
    for role in execute.ROLES:
        candidates = [name for name, entry in entries.items() if entry['kind'] == 'file'
                      and name.startswith(prefix + 'orig/fromprovider/')
                      and re.fullmatch(re.escape(role) + r'-[0-9]{8}\.txt', PurePosixPath(name).name)]
        if native_members is not None:
            selected = native_members.get(role)
            if selected not in candidates:
                raise ValueError('Explicit publisher selection is not an inventoried native role: ' + role)
        elif len(candidates) == 1:
            selected = candidates[0]
        else:
            raise ValueError('An explicit publisher member is required for ambiguous/missing role: ' + role)
        selected_native[role] = selected
    if native_members is not None and set(native_members) != set(execute.ROLES):
        raise ValueError('Explicit native selection must cover the five roles exactly')
    native_hashes = {PurePosixPath(name).name: entries[name]['sha256'] for name in selected_native.values()}
    for finding in reviewed_plan.get('historical_exceptions', []):
        if finding.get('version') != version or finding.get('native_sha256') != native_hashes:
            raise ValueError('A historical finding must be reviewed for this exact release and complete native-byte set')
    archive_uri = 'file:///local/content/MEME/MEME5/inv/sources/' + version + '.tgz'
    def descriptor(role, member):
        entry = entries.get(member)
        if not entry or entry['kind'] != 'file':
            raise ValueError('Selected archive member is not one regular inventoried file: ' + member)
        return {'role': role, 'uri': archive_uri, 'sha256': entry['sha256'], 'bytes': entry['size'],
                'archive_format': 'tar.gz', 'archive_member': member,
                'archive_sha256': archive_sha, 'archive_bytes': archive_bytes}
    attribute_member = prefix + 'src/attributes.src'
    original = entries.get(prefix + 'src/attributes.orig')
    final = entries.get(attribute_member)
    if not final or final['kind'] != 'file':
        raise ValueError('No regular current-release attribute reference')
    stage_proof = None
    if original and original['kind'] == 'file' and original['sha256'] != final['sha256']:
        proof = attribute_stage_relation
        if not isinstance(proof, dict) or proof.get('status') != 'PRE_INSERTION_PREFIX_VERIFIED' or proof.get('archive_sha256') != archive_sha or proof.get('original_member') != original['path'] or proof.get('final_member') != final['path'] or proof.get('original_sha256') != original['sha256'] or proof.get('final_sha256') != final['sha256'] or proof.get('original_bytes') != original['size'] or proof.get('original_rows') != original['newline_count'] or proof.get('final_rows') != final['newline_count'] or proof.get('original_prefix_byte_exact') is not True or type(proof.get('appended_rows')) is not int or proof['appended_rows'] <= 0 or proof.get('appended_attribute_names') != {'SEMANTIC_TYPE': proof['appended_rows']} or proof['original_rows'] + proof['appended_rows'] != proof['final_rows']:
            raise ValueError('Different attributes.orig requires byte-prefix and semantic-type-only suffix proof before selection')
        attribute_member = original['path'];stage_proof = copy.deepcopy(proof)
    provenance = {'producer': 'curate_archived_nci.py (archive-input curation, not NCImeta capture)',
                  'producer_version': 'sha256:' + execute._sha(Path(__file__).read_bytes()),
                  'capture_id': capture_id, 'evidence_kind': evidence_kind}
    def artifact(kind, data, files=None, artifact_version=None):
        return {'schema_version': 1, 'artifact_type': kind, 'source': 'NCI', 'version': artifact_version or version,
                'provenance': copy.deepcopy(provenance), 'files': files or [], 'data': data}
    artifacts = {
        'publisher': artifact('publisher-bundle', {'profile': 'nci-publisher-inputs-v1'}, [descriptor(role, name) for role, name in selected_native.items()]),
        'preserved-preparation': artifact('ncimeta-state', {'profile': execute.PROFILE, 'replacement_baseline': baseline, 'properties': properties},
            [descriptor('sources-src', prefix + 'src/sources.src'), descriptor('termgroups-src', prefix + 'src/termgroups.src'), descriptor('nci-configuration', prefix + 'etc/nci.cfg')]),
        'saved-root': artifact('identity-state', {'profile': 'saved-hierarchy-root-v1', 'root_atom_id': root,
            'root_code': properties['HC.RootNodeCode'], 'root_name': properties['HC.RootNodeName'], 'replacement_baseline': baseline}, artifact_version=prior_version),
        'release-plan': artifact('source-plan', copy.deepcopy(reviewed_plan), [descriptor('review-only-archived-inverter', prefix + 'bin/invert_NCI.pl')]),
        'representation-policy': artifact('policy', {'profile': nci_source_plan.PROFILE, 'metadata_model': copy.deepcopy(metadata_model), 'properties': properties}),
        'allocation': artifact('id-allocation', {'start': start, 'end': allocation_end, 'bound_kind': 'dev-reservation',
            'decision': allocation_decision, 'scope': 'Isolated dev historical replay cap; not a historical or production reservation; insertion excluded'}),
        'environment': artifact('environment-profile', {'profile_id': 'meme-dev-v1'}),
        'validation': artifact('validation-profile', {'profile_id': 'nci-release-core-v1'}),
        'official-reference': artifact('reference-inversion', {'reference_stage': 'inversion-src',
            'attribute_stage_proof': stage_proof, 'selected_attribute_member': attribute_member,
            'scope': 'Current-release comparison oracle only; no completed output seeded'},
            [descriptor(name, attribute_member if name == 'src/attributes.src' else prefix + name) for name in execute.OUTPUTS])}
    config = {'schema_version': 2, 'source': 'NCI', 'version': version, 'engine_ref': engine_ref,
              'policy_ref': 'representation-policy', 'environment_profile': 'environment',
              'replacement_baseline': baseline, 'comparison_baseline': None, 'publisher_history': [],
              'inputs': {'source_data': ['publisher'], 'source_data_stage': 'publisher', 'reference_ncimeta': 'preserved-preparation',
                         'identity_state': 'saved-root', 'source_plan': 'release-plan'},
              'source_atom_ids': {'start': start, 'end': allocation_end, 'bound_kind': 'dev-reservation', 'provenance_ref': 'allocation'},
              'validation_profile': 'validation', 'output_stage': 'inversion-src', 'source_options': {},
              'replay': {'reference_ref': 'official-reference', 'reference_stage': 'inversion-src', 'comparison_profile': 'exact'}}
    # Complete local source semantics are required even though template hashing
    # and all physical bytes remain independent resolver/worker gates.
    execute.build_plan(config, artifacts)
    return {'schema_version': 1, 'artifact_type': 'ncimeta-release-manifest', 'profile': 'nci-publisher-inputs-v1',
            'purpose': 'historical-replay', 'configuration': config, 'artifacts': artifacts}


def curate_capture(bundle, reviewed_plan, metadata_model, **options):
    """Consume the existing root collector's inventory/reference/captures shape."""
    inventory, reference = bundle['inventory'], bundle['reference']
    if bundle['version'] != inventory['version'] or (reference.get('source'), reference.get('version'), reference.get('archive_sha256'), reference.get('archive_bytes')) != ('NCI', inventory['version'], inventory['archive_sha256'], inventory['archive_bytes']):
        raise ValueError('Archive capture, inventory and acquisition receipt identities differ')
    members = {}
    for name, value in bundle['captures'].items():
        raw = base64.b64decode(value['data_b64'], validate=True)
        if type(value['bytes']) is not int or len(raw) != value['bytes'] or execute._sha(raw) != value['sha256']:
            raise ValueError('Collector captured byte identity differs: ' + name)
        members[name] = raw
    return curate(inventory, members, reviewed_plan, metadata_model, **options)


def main():
    import release_manifest
    parser = argparse.ArgumentParser(description=__doc__)
    capture = parser.add_mutually_exclusive_group(required=True)
    capture.add_argument('--capture-bundle');capture.add_argument('--inventory')
    parser.add_argument('--captured-members', help='Member-name to base64 JSON map, required with --inventory')
    for name in ('source-plan', 'metadata-model', 'engine-ref', 'allocation-end', 'allocation-decision', 'capture-id', 'evidence-kind', 'output'):
        parser.add_argument('--' + name, required=True, type=int if name == 'allocation-end' else str)
    parser.add_argument('--attribute-stage-relation');parser.add_argument('--native-members')
    args = parser.parse_args()
    options = {'engine_ref': args.engine_ref, 'allocation_end': args.allocation_end, 'allocation_decision': args.allocation_decision,
               'capture_id': args.capture_id, 'evidence_kind': args.evidence_kind,
               'attribute_stage_relation': release_manifest.load(args.attribute_stage_relation) if args.attribute_stage_relation else None,
               'native_members': release_manifest.load(args.native_members) if args.native_members else None}
    plan = release_manifest.load(args.source_plan);model = release_manifest.load(args.metadata_model)
    if args.capture_bundle:
        if args.captured_members:raise ValueError('A capture bundle already contains captured members')
        result = curate_capture(release_manifest.load(args.capture_bundle), plan, model, **options)
    else:
        if not args.captured_members:raise ValueError('--inventory requires --captured-members')
        captured = release_manifest.load(args.captured_members)
        members = {name: base64.b64decode(raw, validate=True) for name, raw in captured.items()}
        result = curate(release_manifest.load(args.inventory), members, plan, model, **options)
    release_manifest.write_new(args.output, result)
    print(json.dumps({'output': args.output, 'source': 'NCI', 'version': result['configuration']['version'],
                      'replacement_baseline': result['configuration']['replacement_baseline'], 'native_execution_performed': False}))


if __name__ == '__main__':
    main()
