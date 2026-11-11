#!/usr/bin/env python3
"""Plan and validate canonical MTH conversion from manifest-bound prepared data.

Acquisition, locking, physical preservation, capacity and stage execution belong
to the common worker. This module never selects live database answers, executes
MetamorphoSys or invokes a historical release's local executable files.
"""
import argparse
import base64
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

import compare_mth_core
import release_mth

PACKAGE = 'engines/mth'
ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ('range3.spec.in', 'inv1.spec.in', 'inv2.spec.in', 'inv3.spec.in')
RRF_WIDTHS = {'MRCONSO.RRF': 18, 'MRREL.RRF': 16, 'MRSAT.RRF': 13, 'MRSTY.RRF': 6,
              'MRDEF.RRF': 8, 'MRCUI.RRF': 7, 'MRCXT.RRF': 15, 'MRSAB.RRF': 25,
              'MRRANK.RRF': 4, 'MRAUI.RRF': 9, 'MRDOC.RRF': 4}
OUTPUT_NAMES = ('classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src',
                'bequeathal.relationships.src', 'contexts.src', 'class_src', 'attr_src', 'rel_src',
                'merge_src', 'auis_nonupdatedSAB_moved', 'cui_merges', 'aui_said_map',
                'cui_said_map', 'rel_cui_said_map', 'moved_aui_said_map', 'cui_splitonly_said_map',
                'attributes.contexts-all.src', 'src-root.cuis.updated', 'classes_atoms.src.raw',
                'said.ptsaid', 'ptsaid.order', 'cui.splitonly.new')
STAGE_NAMES = ('identity-preparation', 'source-metadata-builder', 'atoms-and-initial-map',
               'identity-transitions', 'attributes-relationships-merges', 'bequeathal-relationships',
               'relationship-normalization', 'context-roots', 'raw-contexts', 'context-attributes',
               'contexts', 'context-tails', 'preferred-term-and-final-atoms')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    digest, size = hashlib.sha256(), 0
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return {'sha256': digest.hexdigest(), 'bytes': size}


def _safe_relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != value or not path.parts:
        raise ValueError('Unsafe MTH package/input path: ' + str(value))
    return path


def _template_files(code_files):
    result = {}
    if code_files is None:
        for name in TEMPLATES:
            raw = (ROOT / PACKAGE / 'templates' / name).read_bytes()
            result[name] = {'repository_path': PACKAGE + '/templates/' + name,
                            'sha256': sha(raw), 'data_b64': base64.b64encode(raw).decode()}
        return result
    for item in code_files:
        path = item.get('repository_path') or PACKAGE + '/' + item.get('relative_path', '')
        if not path.startswith(PACKAGE + '/'):
            raise ValueError('MTH code file is outside the canonical package')
        relative = path.removeprefix(PACKAGE + '/')
        _safe_relative(relative)
        if relative.startswith('templates/') and relative.removeprefix('templates/') in TEMPLATES:
            name = relative.removeprefix('templates/')
            raw = base64.b64decode(item['data_b64'], validate=True)
            if name in result or sha(raw) != item['sha256']:
                raise ValueError('Duplicate or changed frozen MTH template')
            result[name] = {'repository_path': path, 'sha256': item['sha256'], 'data_b64': item['data_b64']}
    if set(result) != set(TEMPLATES):
        raise ValueError('The complete canonical MTH template set is required')
    return result


def _generated(path, raw):
    return {'relative_path': path, 'mode': '0o444', 'sha256': sha(raw),
            'data_b64': base64.b64encode(raw).decode()}


def _render(raw, values):
    text = raw.decode()
    names = set(re.findall(r'\{\{([^{}]+)\}\}', text))
    if not names <= set(values):
        raise ValueError('Unknown canonical MTH template parameter')
    text = re.sub(r'\{\{([^{}]+)\}\}', lambda match: values[match[1]], text)
    if '{{' in text or '}}' in text:
        raise ValueError('Unresolved canonical MTH template parameter')
    return text.encode()


def _subset(artifact):
    value = artifact['data'].get('subset_directory', 'subset3/METASUBSET')
    if not isinstance(value, str) or not re.fullmatch(r'subset[1-9][0-9]*/METASUBSET', value):
        raise ValueError('Prepared subset directory must identify an evidenced standard subsetN/METASUBSET')
    return value


def manifest_decisions_from_preserved(ncisources_raw, sabmap_raw, srcdata_raw,
                                      ncimid_sources_raw, mrsab_raw, current_version, review_id=None):
    """Parse authoritative saved decisions; no predecessor or disposition guess.

    A supplied review_id records external review/curation of saved staff choices.
    Omitting it leaves every disposition proposed. Present-day JSON fingerprints
    do not assert that an older producer originally recorded this JSON contract.
    """
    if not isinstance(current_version, str) or not release_mth.RELEASE.fullmatch(current_version):
        raise ValueError('A canonical current MTH release identity is required')
    if review_id is not None and (not isinstance(review_id, str) or not review_id.strip()):
        raise ValueError('A supplied curation review identity must be nonempty')
    review_status = 'reviewed' if review_id is not None else 'proposed'
    installed = {}
    for line in ncimid_sources_raw.decode().splitlines():
        if not line or line.startswith(' '):
            continue
        fields = line.split('|')
        if len(fields) != 2 or any(not release_mth.TOKEN.fullmatch(value) for value in fields) or fields[0] in installed:
            raise ValueError('Saved current_sources is malformed or ambiguous')
        installed[fields[0]] = fields[1]
    native_sources = {}
    for line in mrsab_raw.splitlines(keepends=True):
        fields = _fields(line)
        if len(fields) != 25:
            raise ValueError('Saved prepared MRSAB must have the 25 native columns')
        version, source = fields[2].decode(), fields[3].decode()
        if version in native_sources and native_sources[version] != source:
            raise ValueError('Saved prepared MRSAB has conflicting VSAB identities')
        native_sources[version] = source
    mappings, by_target, seen_maps = [], {}, set()
    for line in sabmap_raw.decode().splitlines():
        if not line or line.startswith(' '):
            continue
        fields = line.split('|')
        if len(fields) != 3 or any(not release_mth.TOKEN.fullmatch(value) for value in fields):
            raise ValueError('Saved VSAB mapping is malformed')
        source, publisher, target = fields
        target = publisher if target == 'same' else target
        key = (source, publisher)
        if key in seen_maps:
            raise ValueError('Saved VSAB mapping is ambiguous')
        seen_maps.add(key)
        mappings.append({'source': source, 'publisher_version': publisher, 'version': target})
        if (source, target) in by_target and by_target[(source, target)] != publisher:
            raise ValueError('Multiple publisher versions normalize to the same current VSAB')
        by_target[(source, target)] = publisher
    dispositions, seen = [], set()
    for line in ncisources_raw.decode().splitlines():
        fields = line.split('|')
        if len(fields) != 4:
            raise ValueError('Saved ncisources.spec must retain all four fields')
        source, version, disposition, note = fields
        if (not release_mth.TOKEN.fullmatch(source) or not release_mth.TOKEN.fullmatch(version) or
                disposition not in release_mth.DISPOSITIONS or (source, version) in seen):
            raise ValueError('Saved source decision is unresolved, duplicated or invalid')
        seen.add((source, version))
        excluded = []
        if note:
            if not note.startswith('exclude termgroups: '):
                raise ValueError('Saved source decision has an unmodeled qualifier requiring review')
            excluded = [value.strip() for value in note.removeprefix('exclude termgroups: ').split(',')]
            if len(set(excluded)) != len(excluded) or any(not release_mth.TOKEN.fullmatch(value) for value in excluded):
                raise ValueError('Saved excluded termgroups are malformed')
        prior = installed.get(source)
        if disposition in ('KEEP', 'UPDATE', 'REMOVE') and prior is None:
            raise ValueError('A saved KEEP/UPDATE/REMOVE decision lacks its installed-state binding: ' + source)
        publisher = by_target.get((source, version))
        if disposition in release_mth.ACTIVE and publisher is None:
            # updatevsabs.pl leaves an unmapped publisher VSAB unchanged. Require
            # that identity in the saved prepared input; never invent a mapping.
            if native_sources.get(version) != source:
                raise ValueError('No preserved/native identity proves the active VSAB mapping: ' + source + '/' + version)
            publisher = version
            mappings.append({'source': source, 'publisher_version': version, 'version': version})
        dispositions.append({'source': source, 'version': version, 'publisher_version': publisher,
                             'disposition': disposition, 'prior_version': None if disposition == 'NEW' else prior,
                             'excluded_termgroups': excluded, 'review_status': review_status})
    root_lines = [line for line in srcdata_raw.decode().splitlines() if line and not line.startswith('#')]
    if len(root_lines) != 1:
        raise ValueError('The preserved MTH root declaration must be singular')
    root_fields = root_lines[0].split('|')
    if root_fields[-1] == '':
        root_fields.pop()
    if len(root_fields) != 4 or root_fields[:3] != [current_version, 'R', 'SSN'] or not root_fields[3].strip():
        raise ValueError('Preserved SRC root declaration does not identify the selected MTH release')
    return {'review_status': review_status, 'review_id': review_id, 'dispositions': dispositions,
            'vsab_mappings': mappings, 'src_root': {'source': 'MTH', 'version': current_version,
                 'status': 'R', 'term_type': 'SSN', 'name': root_fields[3]},
            'observed_installed_sources': [{'source': source, 'version': version} for source, version in installed.items()],
            'preserved_decision_sha256': {'ncisources.spec': sha(ncisources_raw),
                                          'sab.vsab.map': sha(sabmap_raw), 'src_data': sha(srcdata_raw)},
            'preserved_snapshot_sha256': {'ncimid.sources': sha(ncimid_sources_raw), 'MRSAB.RRF': sha(mrsab_raw)},
            'curation_scope': 'Original authoritative saved decision bytes; present-day typed projection, not historical JSON producer attestation'}


def build_plan(configuration, artifacts, code_files=None):
    checked = release_mth.analyze(configuration, artifacts)
    blockers = [item for item in checked['issues'] if item['severity'] in ('error', 'blocker')]
    if blockers:
        raise ValueError('MTH release preflight blocks execution planning: ' + ', '.join(item['code'] for item in blockers))
    config = copy.deepcopy(configuration)
    selected = config['inputs']
    version, baseline = config['version'], config['replacement_baseline']['version']
    source_plan = artifacts[selected['source_plan']]['data']
    active_versions = [row['version'] for row in source_plan['dispositions'] if row['disposition'] in release_mth.ACTIVE]
    if len(set(active_versions)) != len(active_versions):
        raise ValueError('Active MTH NCImeta VSAB identities must be globally unambiguous')
    prepared_ref = selected['source_data'][0]
    prepared = artifacts[prepared_ref]
    templates = _template_files(code_files)
    predicates = ["<VER> eq '" + item.removeprefix('MTH_') + "'" for item in source_plan['history_selection']['bequeathal_releases']]
    values = {'version': version, 'main_atom_base': str(config['source_atom_ids']['start'] + 2),
              'end': str(config['source_atom_ids']['end']), 'bequeathal_predicate': '(' + ' || '.join(predicates) + ')'}
    generated = []
    for name in TEMPLATES:
        path = 'range3.spec' if name == 'range3.spec.in' else 'src/' + name.removesuffix('.in')
        generated.append(_generated(path, _render(base64.b64decode(templates[name]['data_b64']), values)))
    decisions = []
    for item in source_plan['dispositions']:
        note = 'exclude termgroups: ' + ','.join(item['excluded_termgroups']) if item['excluded_termgroups'] else ''
        decisions.append('|'.join((item['source'], item['version'], item['disposition'], note)))
    generated.append(_generated('ncisources.spec', ('\n'.join(decisions) + '\n').encode()))
    mappings = [' RSAB | UMLS VSAB | NCI VSAB'] + ['|'.join((item['source'], item['publisher_version'], item['version']))
                                                         for item in source_plan['vsab_mappings']]
    generated.append(_generated('sab.vsab.map', ('\n'.join(mappings) + '\n').encode()))
    root = source_plan['src_root']
    generated.append(_generated('src_data', '|'.join((version, root['status'], root['term_type'], root['name'])).encode() + b'\n'))
    inputs, identities = [], []

    def add(reference, artifact, scope, destination):
        for item in artifact['files']:
            path = destination(item['role'])
            _safe_relative(path)
            entry = {'artifact': reference, 'role': item['role'], 'scope': scope, 'destination': path}
            inputs.append(entry)
            identities.append({**entry, 'sha256': item['sha256'], 'bytes': item['bytes']})

    subset = _subset(prepared)
    add(prepared_ref, prepared, 'meme', lambda role: 'mr/umls/' + version[4:] + '/' + subset + '/' + role)
    add(selected['reference_ncimeta'], artifacts[selected['reference_ncimeta']], 'candidate', lambda role: role)
    add(selected['identity_state'], artifacts[selected['identity_state']], 'inv',
        lambda role: 'sources/' + baseline + '/src/cui_said_map')
    original_decisions = artifacts[selected['source_plan']]['files']
    if original_decisions:
        if len(original_decisions) != 3 or {item['role'] for item in original_decisions} != {'ncisources.spec', 'sab.vsab.map', 'src_data'}:
            raise ValueError('Preserved source decisions must bind exactly the three data-policy roles')
        add(selected['source_plan'], artifacts[selected['source_plan']], 'candidate', lambda role: 'orig/source-plan/' + role)
    history_refs = [prepared_ref] + config['publisher_history']
    for reference in config['publisher_history']:
        artifact = artifacts[reference]
        history_subset = _subset(artifact)
        add(reference, artifact, 'meme', lambda role, a=artifact, d=history_subset:
            'mr/umls/' + a['version'][4:] + '/' + d + '/' + role)
    histories = {}
    for kind in release_mth.HISTORY_KINDS:
        role = 'MRAUI.RRF' if kind == 'moved_aui_releases' else 'MRCUI.RRF'
        selected_sources = {}
        for release in source_plan['history_selection'][kind]:
            available = [reference for reference in history_refs if release in
                         artifacts[reference]['data'].get('history_coverage', {}).get(kind, [])]
            preferred = [prepared_ref] if prepared_ref in available else available
            if len(preferred) != 1:
                raise ValueError('A history release needs one authoritative input source: ' + kind + '/' + release)
            selected_sources[release[4:]] = next(item for item in inputs if item['artifact'] == preferred[0] and item['role'] == role)
        histories[kind] = selected_sources
    native = '../../../mr/umls/' + version[4:] + '/' + subset
    links = [{'relative_path': 'old', 'target': '../' + baseline},
             {'relative_path': 'METASUBSET3', 'target': native}, {'relative_path': 'Meta3', 'target': 'METASUBSET3'},
             {'relative_path': 'src/Meta', 'target': '../Meta3'}, {'relative_path': 'src/bin', 'target': '../bin'},
             {'relative_path': 'src/src_data', 'target': '../src_data'}]
    links += [{'relative_path': 'src/' + role, 'target': 'Meta/' + role}
              for role in ('MRCONSO.RRF', 'MRSAT.RRF', 'MRSTY.RRF', 'MRDEF.RRF', 'MRREL.RRF', 'MRCUI.RRF')]
    stages = []
    direct = {'atoms-and-initial-map': ['/usr/bin/perl', '{target}/bin/autoinv.pl', '../range3.spec', 'inv1.spec'],
              'attributes-relationships-merges': ['/usr/bin/perl', '{target}/bin/autoinv.pl', 'inv2.spec'],
              'bequeathal-relationships': ['/usr/bin/perl', '{target}/bin/autoinv.pl', 'inv3.spec'],
              'raw-contexts': ['/usr/bin/perl', '{target}/bin/mrcxt2raw3.pl'],
              'contexts': ['/bin/tcsh', '-f', '{target}/bin/raw_to_contexts.csh', 'raw3'],
              'preferred-term-and-final-atoms': ['/bin/tcsh', '-ef', '{target}/bin/make.meme4classes.s']}
    for name in STAGE_NAMES:
        stages.append({'name': name, 'cwd': 'src', 'argv': direct.get(name, [
            '{python}', '{run}/apparatus/execute_release_mth.py', 'stage', name, '{run}/native-plan.json', '{target}'])})
    reference = artifacts.get(config.get('replay', {}).get('reference_ref'))
    return {'schema_version': 1, 'source': 'MTH', 'version': version, 'engine_package': PACKAGE,
            'input_files': inputs, 'generated_files': generated, 'symlinks': links, 'stages': stages,
            'output_files': ['src/' + name for name in OUTPUT_NAMES],
            'validation': {'configuration': config, 'source_plan': copy.deepcopy(source_plan),
                           'prepared_data': copy.deepcopy(prepared['data']), 'metadata_data': copy.deepcopy(artifacts[selected['reference_ncimeta']]['data']),
                           'input_identities': identities, 'history_sources': histories,
                           'template_identities': {name: {'repository_path': item['repository_path'], 'sha256': item['sha256']}
                                                   for name, item in templates.items()},
                           'template_origin': 'frozen-code-files' if code_files is not None else 'local-preview-only',
                           'reference_version': reference['version'] if reference else None,
                           'reference_stage': reference['data'].get('reference_stage') if reference else None,
                           'reference_files': copy.deepcopy(reference['files']) if reference else [],
                           'bounds': copy.deepcopy(config['source_atom_ids']), 'core_widths': dict(compare_mth_core.WIDTHS),
                           'retained_identity_required': True, 'historical_correction_waiver': False}}


def input_path(item, target):
    target = Path(target)
    base = {'candidate': target, 'inv': target.parent.parent, 'meme': target.parents[2]}.get(item.get('scope', 'candidate'))
    if base is None:
        raise ValueError('Unsupported MTH input scope')
    return base / _safe_relative(item['destination'])


def _issue(issues, code, message, path):
    issues.append({'severity': 'error', 'code': code, 'message': message, 'path': str(path)})


def verify_materialized(plan, target):
    target, issues = Path(target), []
    for item in plan['generated_files']:
        path = target / item['relative_path']
        if (path.is_symlink() or not path.is_file() or identity(path)['sha256'] != item['sha256'] or
                path.stat().st_mode & 0o777 != 0o444):
            _issue(issues, 'MTH_GENERATED_CHANGED', 'Generated configuration bytes/mode changed.', path)
    for item in plan['symlinks']:
        path = target / item['relative_path']
        if not path.is_symlink() or os.readlink(path) != item['target']:
            _issue(issues, 'MTH_LINK_CHANGED', 'Declared MTH input/code alias changed.', path)
    return {'passed': not issues, 'issues': issues, 'facts': {'generated_files': len(plan['generated_files'])}}


def _fields(raw):
    values = raw.removesuffix(b'\n').split(b'|')
    return values[:-1] if values and values[-1] == b'' else values


def validate_inputs(plan, target):
    target, issues, facts = Path(target), [], {}
    materialized = verify_materialized(plan, target)
    issues.extend(materialized['issues'])
    mrsab, metadata = {}, {}
    current = plan['version']
    for item in plan['validation']['input_identities']:
        path = input_path(item, target)
        if path.is_symlink() or not path.is_file():
            _issue(issues, 'MTH_INPUT_MISSING', 'A materialized regular input is required.', path)
            continue
        digest, size, rows, malformed = hashlib.sha256(), 0, 0, 0
        role = item['role']
        prior_cuis = set()
        seen_versions = Counter()
        data = []
        with path.open('rb') as handle:
            for raw in handle:
                digest.update(raw);size += len(raw);rows += 1
                try:
                    raw.decode('utf-8')
                except UnicodeDecodeError:
                    malformed += 1
                fields = _fields(raw)
                if role in RRF_WIDTHS:
                    malformed += len(fields) != RRF_WIDTHS[role] or not raw.endswith(b'|\n') or b'\0' in raw or b'\r' in raw
                    if len(fields) != RRF_WIDTHS[role]:
                        continue
                    if role == 'MRCONSO.RRF':
                        malformed += not fields[0] or not fields[7]
                    if role == 'MRSAB.RRF' and item['artifact'] == plan['validation']['configuration']['inputs']['source_data'][0]:
                        if fields[2] in mrsab and mrsab[fields[2]] != fields[3]:
                            malformed += 1
                        mrsab[fields[2]] = fields[3]
                    if role in ('MRAUI.RRF', 'MRCUI.RRF'):
                        index = 2 if role == 'MRAUI.RRF' else 1
                        seen_versions[fields[index].decode(errors='replace')] += 1
                elif role == 'cui_said_map':
                    malformed += len(fields) != 2 or not fields[0] or not fields[-1].isdigit()
                    if fields:
                        malformed += fields[0] in prior_cuis
                        prior_cuis.add(fields[0])
                else:
                    if role in ('src/sources.src', 'src/termgroups.src'):
                        malformed += len(fields) != (20 if role == 'src/sources.src' else 6) or not raw.endswith(b'|\n')
                    data.append(raw.decode('utf-8', errors='replace').rstrip('\n'))
        if (digest.hexdigest(), size) != (item['sha256'], item['bytes']):
            _issue(issues, 'MTH_INPUT_CHANGED', 'Input hash/size differs from the locked artifact.', path)
        if malformed:
            _issue(issues, 'MTH_INPUT_DIALECT', 'Malformed UTF-8, RRF/state fields or record terminators: ' + str(malformed), path)
        if role in ('MRCONSO.RRF', 'MRSAB.RRF', 'MRRANK.RRF', 'cui_said_map', 'src/sources.src',
                    'src/termgroups.src', 'ncimid.sources', 'ncimid.termgroups') and rows == 0:
            _issue(issues, 'MTH_EMPTY_REQUIRED_INPUT', 'This native/identity input cannot be empty.', path)
        facts[item['artifact'] + '/' + role] = {'rows': rows, 'history_versions_seen': dict(seen_versions)}
        if data:
            metadata[role] = data
    if mrsab.get(current.encode()) != b'MTH':
        _issue(issues, 'MTH_PREPARED_NATIVE_RELEASE', 'Prepared MRSAB must contain the declared current MTH version.', 'MRSAB.RRF')
    sources = [row.split('|') for row in metadata.get('src/sources.src', []) if row.startswith(current + '|')]
    baseline = plan['validation']['configuration']['replacement_baseline']['version']
    if (len(sources) != 1 or len(sources[0]) < 8 or sources[0][1] != baseline or
            sources[0][3:5] != [current, 'MTH']):
        _issue(issues, 'MTH_SOURCE_BASELINE', 'Prepared MTH metadata must select the declared last-inserted baseline.', 'src/sources.src')
    observed_installed = {}
    malformed_inventory = False
    for row in metadata.get('ncimid.sources', []):
        if not row or row.startswith(' '):
            continue
        fields = row.split('|')
        if len(fields) != 2 or not all(fields) or fields[0] in observed_installed:
            malformed_inventory = True
        else:
            observed_installed[fields[0]] = fields[1]
    expected_installed = {item['source']: item['version'] for item in plan['validation']['metadata_data']['installed_sources']}
    if malformed_inventory or observed_installed != expected_installed:
        _issue(issues, 'MTH_INSTALLED_SNAPSHOT', 'Physical saved current_sources differs from the manifest state used for source decisions.', 'ncimid.sources')
    decisions = {row['version']: row for row in plan['validation']['source_plan']['dispositions'] if row['disposition'] in release_mth.ACTIVE}
    updates, targets = set(), set()
    for row in metadata.get('src/vsab.updates', []):
        fields = row.split('|')
        if len(fields) != 2 or fields[1] in targets or fields[1] not in decisions:
            _issue(issues, 'MTH_VSAB_UPDATE_DECISION', 'Prepared VSAB updates must identify distinct reviewed active source versions.', 'src/vsab.updates')
            continue
        prior, version = fields
        decision = decisions[version]
        expected = '' if decision['disposition'] == 'KEEP' else ('New' if decision['disposition'] == 'NEW' else decision['prior_version'])
        if prior != expected:
            _issue(issues, 'MTH_VSAB_UPDATE_DECISION', 'Prepared source disposition/prior version conflicts with reviewed plan.', 'src/vsab.updates')
        targets.add(version)
        if prior:
            updates.add(version)
    updated_rsabs = {mrsab[version.encode()].decode() for version in updates if version.encode() in mrsab}
    if current not in updates:
        _issue(issues, 'MTH_CURRENT_UPDATE_MISSING', 'The current MTH UPDATE must appear in the prepared updated source data.', 'src/vsab.updates')
    if len(updated_rsabs) != len(updates) or set(metadata.get('src/sabs_updated_umls', [])) != updates:
        _issue(issues, 'MTH_UPDATED_VSABS', 'Prepared updated-source list must match the reviewed non-KEEP VSAB updates and native MRSAB.', 'src/sabs_updated_umls')
    if set(metadata.get('src/rsabs-updated.umls', [])) != updated_rsabs:
        _issue(issues, 'MTH_UPDATED_RSABS', 'Prepared updated RSAB list differs from native source/version mapping.', 'src/rsabs-updated.umls')
    if set(metadata.get('src/vcodes_updated', [])) != {'V-' + source for source in updated_rsabs}:
        _issue(issues, 'MTH_UPDATED_ROOT_CODES', 'Prepared updated root codes differ from the selected RSABs.', 'src/vcodes_updated')
    preserved_inputs = {item['role']: input_path(item, target) for item in plan['input_files']
                        if item['artifact'] == plan['validation']['configuration']['inputs']['source_plan']}
    if preserved_inputs:
        try:
            projection = manifest_decisions_from_preserved(
                preserved_inputs['ncisources.spec'].read_bytes(), preserved_inputs['sab.vsab.map'].read_bytes(),
                preserved_inputs['src_data'].read_bytes(), (target / 'ncimid.sources').read_bytes(),
                (target / 'src/Meta/MRSAB.RRF').read_bytes(), current,
                review_id=plan['validation']['source_plan']['review_id'])
            declared = plan['validation']['source_plan']
            recorded_hashes = declared.get('preserved_decision_sha256', {})
            if not isinstance(recorded_hashes, dict):
                raise ValueError('Preserved decision fingerprints must be a typed mapping')
            columns = ('source', 'version', 'publisher_version', 'disposition', 'prior_version', 'excluded_termgroups')
            expected_rows = [{key: item.get(key) for key in columns} for item in projection['dispositions']]
            declared_rows = [{key: item.get(key) for key in columns} for item in declared['dispositions']]
            mapping_columns = ('source', 'publisher_version', 'version')
            expected_maps = sorted(tuple(item[key] for key in mapping_columns) for item in projection['vsab_mappings'])
            declared_maps = sorted(tuple(item[key] for key in mapping_columns) for item in declared['vsab_mappings'])
            if (expected_rows != declared_rows or expected_maps != declared_maps or projection['src_root'] != declared['src_root'] or
                    any(recorded_hashes.get(key, value) != value
                        for key, value in projection['preserved_decision_sha256'].items())):
                _issue(issues, 'MTH_PRESERVED_DECISION_MISMATCH', 'Typed manifest source decisions differ from authoritative preserved data.', 'orig/source-plan')
        except (ValueError, KeyError, OSError) as error:
            _issue(issues, 'MTH_PRESERVED_DECISION_MISMATCH', str(error), 'orig/source-plan')
    declared_subset = plan['validation']['prepared_data'].get('selected_sources')
    if declared_subset is not None:
        observed = {decisions[version]['source'] for version in targets}
        if (not isinstance(declared_subset, list) or not all(isinstance(value, str) for value in declared_subset) or
                set(declared_subset) != observed):
            _issue(issues, 'MTH_PREPARED_SUBSET', 'Producer-declared selected sources differ from preserved VSAB update data.', 'prepared-bundle/data/selected_sources')
    facts.update(replacement_baseline=baseline, publisher_previous=plan['validation']['source_plan']['publisher_previous'],
                 observed_updated_sources=sorted(updated_rsabs), historical_DB_reconstruction=False, MetamorphoSys_executed=False)
    return {'passed': not issues, 'issues': issues, 'facts': facts}


def validate_outputs(plan, target):
    target, issues = Path(target), []
    missing = [name for name in plan['output_files'] if (target / name).is_symlink() or not (target / name).is_file()]
    if missing:
        for name in missing:
            _issue(issues, 'MTH_OUTPUT_MISSING', 'A declared regular native output is missing.', name)
        return {'passed': False, 'issues': issues, 'facts': {}}
    bounds = plan['validation']['bounds']
    structural = compare_mth_core.structure({name: target / 'src' / name for name in compare_mth_core.WIDTHS},
                                           (bounds['start'], bounds['end']))
    retained = compare_mth_core.identity_state(target / 'src')
    if not structural['passed']:
        _issue(issues, 'MTH_CORE_STRUCTURE', 'Native core output failed independent dialect/range/reference validation.', 'src')
    if not retained['passed']:
        _issue(issues, 'MTH_RETAINED_IDENTITY', 'Persisted AUI/CUI state does not describe the retained atoms and moved roles.', 'src')
    # Validate complete retained-state coverage, not only the rows that happen
    # to be present in an identity map. Preserve first-current CUI selection and
    # the original split-only exclusion against the last-inserted CUI baseline.
    expected_current, expected_moved = hashlib.sha256(), hashlib.sha256()
    current_cuis, moved_cuis = {}, {}
    with (target / 'src/classes_atoms.src.raw').open('rb') as handle:
        for raw in handle:
            fields = raw.removesuffix(b'\n').split(b'|')
            if len(fields) != 17 or fields[14] not in (b'N', b'Y') or not fields[15] or not fields[16]:
                continue
            record = fields[16] + b'|' + fields[15] + b'|' + fields[0] + b'\n'
            if fields[14] == b'N':
                expected_current.update(record)
                current_cuis.setdefault(fields[15], fields[0])
            else:
                expected_moved.update(record)
                moved_cuis.setdefault(fields[15], fields[0])
    prior_input = next(item for item in plan['input_files'] if item['role'] == 'cui_said_map')
    prior_path = input_path(prior_input, target)
    if prior_path.is_symlink() or not prior_path.is_file():
        _issue(issues, 'MTH_PRIOR_IDENTITY_MISSING', 'Last-inserted identity input must remain intact through output validation.', prior_path)
        prior_cuis = set()
    else:
        with prior_path.open('rb') as handle:
            prior_cuis = {raw.split(b'|', 1)[0] for raw in handle}
    split = {cui: said for cui, said in moved_cuis.items() if cui not in current_cuis and cui not in prior_cuis}
    complete_cuis = {**current_cuis, **split}

    def mapping_hash(values):
        digest = hashlib.sha256()
        for cui in sorted(values):
            digest.update(cui + b'|' + values[cui] + b'\n')
        return digest.hexdigest()

    expected = {'aui_said_map': expected_current.hexdigest(), 'moved_aui_said_map': expected_moved.hexdigest(),
                'cui_said_map': mapping_hash(complete_cuis), 'rel_cui_said_map': mapping_hash(complete_cuis),
                'cui_splitonly_said_map': mapping_hash(split),
                'cui.splitonly.new': sha(b''.join(cui + b'\n' for cui in sorted(split)))}
    for name, checksum in expected.items():
        if identity(target / 'src' / name)['sha256'] != checksum:
            _issue(issues, 'MTH_IDENTITY_COVERAGE', 'Retained atom allocation/current-moved roles/prior-CUI state predict a different complete identity map.', 'src/' + name)
    return {'passed': not issues, 'issues': issues,
            'facts': {'version': plan['version'], 'structure': structural, 'retained_identity': retained,
                      'complete_identity_maps': not any(item['code'] == 'MTH_IDENTITY_COVERAGE' for item in issues),
                      'historical_correction_waiver_applied': False}}


def compare_outputs(plan, target, reference_directory, run_directory=None):
    if (plan['validation']['reference_version'] != plan['version'] or
            plan['validation']['reference_stage'] != 'inversion-src'):
        raise ValueError('Current-release native outputs require current-release reference artifacts')
    references = {item['role']: item for item in plan['validation']['reference_files']}
    if (len(plan['validation']['reference_files']) != len(plan['output_files']) or
            len(references) != len(plan['output_files']) or set(references) != set(plan['output_files'])):
        raise ValueError('Every declared MTH output requires a current-release reference descriptor')
    validation = validate_outputs(plan, target)
    files = {}
    for name in plan['output_files']:
        candidate, reference = Path(target) / name, Path(reference_directory) / name
        if reference.is_symlink() or not reference.is_file():
            raise ValueError('Missing regular current-release reference: ' + name)
        expected, observed = identity(reference), identity(candidate)
        if expected != {key: references[name][key] for key in ('sha256', 'bytes')}:
            raise ValueError('Reference file differs from the declared current-release oracle: ' + name)
        files[name] = {'reference': expected, 'candidate': observed, 'exact_match': expected == observed}
    exact = all(item['exact_match'] for item in files.values())
    return {'source': 'MTH', 'version': plan['version'], 'files': files, 'validation': validation,
            'acceptance': {'status': 'PASS_EXACT' if exact and validation['passed'] else 'DIFFERENCES_REQUIRE_REVIEW',
                           'all_compared_outputs_exact': exact, 'historical_correction_waiver_applied': False,
                           'ignored_fields': [], 'production_eligible': False}}


def _selected_rows(plan, target, kind):
    selection = plan['validation']['history_sources'][kind]
    files = []
    for item in selection.values():
        path = input_path(item, target)
        if path not in files:
            files.append(path)
    for path in files:
        allowed = {release for release, item in selection.items() if input_path(item, target) == path}
        index = 2 if kind == 'moved_aui_releases' else 1
        with path.open('rb') as handle:
            for raw in handle:
                fields = _fields(raw)
                if fields[index].decode() in allowed:
                    yield raw, fields


def _run(argv, src, stdout=None):
    env = dict(os.environ, LANG='C', LC_ALL='C', LC_COLLATE='C', _POSIX2_VERSION='1', PATH_TO_PERL='/usr/bin/perl')
    return subprocess.run(argv, cwd=src, env=env, stdout=stdout, check=True)


def _shell(text, src):
    return _run(['/bin/bash', '-e', '-o', 'pipefail', '-c', text], src)


def run_stage(name, plan, target):
    """Execute only fixed source-specific helper operations selected in code."""
    target, src = Path(target), Path(target) / 'src'
    if name == 'identity-preparation':
        with (src / 'auis.moved.projected').open('xb') as handle:
            for _, fields in _selected_rows(plan, target, 'moved_aui_releases'):
                if fields[8] == b'Y':
                    handle.write(fields[0] + b'|' + fields[7] + b'\n')
        _shell("sort -t\\| +0 -1 -o auis.moved auis.moved.projected\n"
               "awk -F\\| '{print $8 \"|\" $12}' Meta/MRCONSO.RRF |sort -t\\| +0 -1 |join -t\\| -o '2.2,1.1,1.2' auis.moved - |sort -t\\| +0 -1 |join -t\\| -1 2 -o '1.1,2.2,2.3' vsab.updates - |sed -n 's/^|//p' >auis_nonupdatedSAB_moved\n", src)
        with (src / 'cui_merges').open('xb') as handle:
            for _, fields in _selected_rows(plan, target, 'cui_merge_releases'):
                if fields[2] == b'SY' and fields[6] == b'Y':
                    handle.write(fields[0] + b'|' + fields[5] + b'\n')
        with (src / 'bequeathal_history.RRF').open('xb') as handle:
            for raw, _ in _selected_rows(plan, target, 'bequeathal_releases'):
                handle.write(raw)
        (src / 'bequeathal_history.RRF').chmod(0o444)
    elif name == 'source-metadata-builder':
        path, saved = src / 'sources.src', src / '.sources.full-input.src'
        if saved.exists():
            raise FileExistsError(saved)
        os.rename(path, saved)
        try:
            rows = []
            for row in saved.read_text().splitlines():
                if row.startswith(plan['version'] + '|'):
                    fields = row.split('|');fields[5] = plan['version'][4:];rows.append('|'.join(fields))
            if len(rows) != 1:
                raise ValueError('One current MTH metadata row is required')
            path.write_text(rows[0] + '\n')
            _run(['/usr/bin/perl', str(target / 'bin/SRCbuilder.pl'), '-s',
                  str(plan['validation']['bounds']['start'])], src)
        finally:
            if path.exists():
                path.unlink()
            os.rename(saved, path)
    elif name == 'identity-transitions':
        _shell("awk -F\\| '$3==\"Y\"{print $2}' aui_said_map |sort -u -o cuis.withmovedaui\n"
               "awk -F\\| '$3==\"N\"{print $2}' aui_said_map |sort -u |comm -23 cuis.withmovedaui - >cui.splitonly\n"
               "cut -d\\| -f1 ../old/src/cui_said_map |sort |comm -23 cui.splitonly - >cui.splitonly.new\n"
               "cut -d\\| -f2,4 aui_said_map |sort -u -t\\| +0 -1 |join -t\\| - cui.splitonly.new >cui_splitonly_said_map\n"
               "awk -F\\| '$3==\"Y\"{print $1 \"|\" $2 \"|\" $4}' aui_said_map >moved_aui_said_map\n"
               "awk -F\\| '$3==\"N\"{print $1 \"|\" $2 \"|\" $4}' aui_said_map >aui_said_map.without-moved\n"
               "mv aui_said_map.without-moved aui_said_map\n"
               "cut -d\\| -f2,3 aui_said_map |sort -u -t\\| +0 -1 -o cui_said_map - cui_splitonly_said_map\n"
               "sort -u cui_said_map -o rel_cui_said_map\n", src)
        for alias, destination in [('aui_said_map2', 'aui_said_map'), ('rel_cui_said_map2', 'rel_cui_said_map')]:
            (src / alias).symlink_to(destination)
    elif name == 'relationship-normalization':
        _shell("mv relationships.src relationships.before-normalization.src\n"
               "awk 'BEGIN{FS=OFS=\"|\"; map[\"RB\"]=\"BT\"; map[\"RN\"]=\"NT\"; map[\"RO\"]=\"RT\"; map[\"RQ\"]=\"RT?\"} map[$4]!=\"\"{$4=map[$4]} $17==\"~DA:\"{$17=\"\"} {print $0}' relationships.before-normalization.src >relationships.src\n", src)
    elif name == 'context-roots':
        _shell("awk -F\\| '$12==\"SRC\" && $13==\"RPT\"{print substr($14,3) \"|\" $1}' Meta/MRCONSO.RRF |sort -t\\| +0 -1 |join -t\\| -o 1.2 - rsabs-updated.umls |sort -o src-root.cuis.updated\nmkdir raw3\n", src)
    elif name == 'context-attributes':
        output = src / 'attributes.contexts-all.src'
        if (src / 'raw3/newsources.raw3').stat().st_size:
            _run(['/usr/bin/perl', str(target / 'bin/print.raw3.to.attributes.pl'), 'raw3/newsources.raw3'], src)
        else:
            output.write_bytes(b'')
        with output.open('rb') as source, (src / 'attributes.src').open('ab') as destination:
            shutil.copyfileobj(source, destination, 4 * 1024 * 1024)
    elif name == 'context-tails':
        original = src / 'contexts.before-tail.src'
        os.rename(src / 'contexts.src', original)
        with original.open('rb') as source, (src / 'contexts.src').open('xb') as destination:
            for raw in source:
                destination.write(raw.removesuffix(b'\n') + b'||\n')
    else:
        raise ValueError('Unknown fixed MTH helper stage: ' + name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['stage'])
    parser.add_argument('stage', choices=[name for name in STAGE_NAMES if name not in (
        'atoms-and-initial-map', 'attributes-relationships-merges', 'bequeathal-relationships',
        'raw-contexts', 'contexts', 'preferred-term-and-final-atoms')])
    parser.add_argument('plan', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if plan.get('source') != 'MTH' or plan.get('engine_package') != PACKAGE or plan.get('schema_version') != 1:
        raise ValueError('Unknown MTH native execution plan')
    run_stage(args.stage, plan, args.target)
