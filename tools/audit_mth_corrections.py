#!/usr/bin/env python3
"""Account for MTH retained-identity changes using official output and native RRF.

This is a separate correction audit, never a replacement for the raw comparison.
It predicts map changes, native dependent rows and context serialization changes;
all other records and every allocated atom ID must remain unchanged.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

from acquire_mth_subset import identity
from replay_mth_core import guard

PART = (b'C1976636', b'A32818398', b'771405764')
REMOVED = {b'771038403': b'A8298300', b'771038404': b'A8298289'}
CCS = b'C1541964'
VERSION = b'MTH_2026AA'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def row(fields):
    return b'|'.join(fields) + b'\n'


def sha(path):
    return identity(path)['sha256']


def stream_sha(handle):
    value = hashlib.sha256()
    for block in iter(lambda: handle.read(4194304), b''):value.update(block)
    return value.hexdigest()


def save_report(path, report):
    """Publish a complete immutable audit without replacing prior evidence."""
    descriptor, name = tempfile.mkstemp(prefix='.correction-audit-', dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as out:
            json.dump(report, out, indent=2);out.write('\n')
        temporary.chmod(0o444)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def expected_maps(reference, candidate):
    """Derive complete old/new current maps from official raw atom allocations."""
    old_cuis, old_auis, retained_special, removed_rows = {}, {}, {}, []
    old_aui_hash, new_aui_hash, moved_hash, raw_hash = [hashlib.sha256() for _ in range(4)]
    with (reference / 'classes_atoms.src.raw').open('rb') as handle:
        for raw in handle:
            f = raw.removesuffix(b'\n').split(b'|')
            require(len(f) == 17, 'Unexpected official raw atom shape')
            excluded = f[1] == b'SRC' and f[3] == b'V-CCS_2005'
            if excluded:
                require(f[0] in REMOVED and f[16] == REMOVED[f[0]] and f[15] == CCS, 'Unexpected CCS exclusion identity')
                removed_rows.append(f[0])
            else:
                raw_hash.update(raw)
            if f[14] == b'Y':
                require(not excluded, 'Unexpected moved CCS atom')
                moved_hash.update(row([f[16], f[15], f[0]]))
            if f[14] != b'N':
                continue
            require(f[15] and f[16], 'A native current atom has empty identity')
            record = row([f[16], f[15], f[0]])
            if f[15] != PART[0]:
                old_aui_hash.update(record)
                require(f[16] not in old_auis, 'Duplicate native AUI in old current mapping')
                old_auis[f[16]] = f[0]
                old_cuis.setdefault(f[15], f[0])
            else:
                require((f[15], f[16], f[0]) == PART, 'Unexpected LOINCPARTS identity')
            if not excluded:
                new_aui_hash.update(record)
                if f[15] in (CCS, PART[0]):
                    retained_special.setdefault(f[15], f[0])
    require(set(removed_rows) == set(REMOVED) and len(removed_rows) == 2, 'Exactly the two known CCS atoms must be excluded')
    require(old_aui_hash.hexdigest() == sha(reference / 'aui_said_map'), 'Official AUI map does not follow the characterized native allocation')
    require(new_aui_hash.hexdigest() == sha(candidate / 'aui_said_map'), 'Candidate AUI map is incomplete or has an unexplained change')
    require(raw_hash.hexdigest() == sha(candidate / 'classes_atoms.src.raw'), 'Candidate raw atoms differ beyond the two retained-set exclusions')
    require(sha(reference / 'classes_atoms.src.raw') == sha(candidate / 'classes_atoms.unfiltered.raw'), 'Original atom allocation changed')
    require(sha(reference / 'classes_atoms.src') == sha(candidate / 'classes_atoms.src'), 'Final atom IDs/content changed')
    require(moved_hash.hexdigest() == sha(reference / 'moved_aui_said_map') == sha(candidate / 'moved_aui_said_map'), 'Moved AUI identities changed')
    require(sha(reference / 'cui_splitonly_said_map') == sha(candidate / 'cui_splitonly_said_map'), 'Split-only CUI identities changed')
    with (reference / 'cui_splitonly_said_map').open('rb') as handle:
        for raw in handle:
            cui, said = raw.rstrip(b'\n').split(b'|')
            require(cui not in old_cuis, 'Split-only CUI overlaps an existing current CUI')
            old_cuis[cui] = said
    new_cuis = old_cuis.copy()
    for cui in (CCS, PART[0]):
        if cui in retained_special:new_cuis[cui] = retained_special[cui]
        else:new_cuis.pop(cui, None)
    def map_sha(values):
        value = hashlib.sha256()
        for cui in sorted(values):value.update(row([cui, values[cui]]))
        return value.hexdigest()
    require(map_sha(old_cuis) == sha(reference / 'cui_said_map') == sha(reference / 'rel_cui_said_map'), 'Official CUI selection differs from the characterized first-current identity rule')
    require(map_sha(new_cuis) == sha(candidate / 'cui_said_map') == sha(candidate / 'rel_cui_said_map'), 'Candidate CUI maps differ from the retained identity prediction')
    def aui(value, new=False):
        if new and value in REMOVED.values():return None
        if new and value == PART[1]:return PART[2]
        return old_auis.get(value)
    return aui, old_cuis, new_cuis, {'removed_atom_ids': [x.decode() for x in removed_rows],
                                    'restored_identity': [x.decode() for x in PART], 'final_atoms_exact': True,
                                    'full_current_AUI_CUI_and_moved_maps_predicted': True}


def attribute(fields):
    return row(fields[:-1] + [hashlib.md5(fields[3]).hexdigest().encode(), b''])


def native_changes(native, aui, old_cuis, new_cuis, progress=print):
    changes = {name: {'removed': Counter(), 'added': Counter()} for name in ('attributes.src', 'relationships.src')}
    traces = []
    targets = (CCS + b'|', PART[0] + b'|', PART[1] + b'|', *(value + b'|' for value in REMOVED.values()))
    def record(name, old, new, filename, number):
        if old == new:return
        if old:changes[name]['removed'][old] += 1
        if new:changes[name]['added'][new] += 1
        traces.append({'native_file': filename, 'native_line': number, 'output': name,
                       'removed_content': old.decode() if old else None, 'added_content': new.decode() if new else None})
    for filename in ('MRSAT.RRF', 'MRSTY.RRF', 'MRDEF.RRF', 'MRREL.RRF'):
        progress('AUDIT: native dependents in ' + filename, flush=True)
        with (native / filename).open('rb') as handle:
            for number, raw in enumerate(handle, 1):
                if not any(value in raw for value in targets):continue
                f = raw.removesuffix(b'\n').split(b'|')
                def render(new):
                    cuis = new_cuis if new else old_cuis
                    if filename == 'MRSAT.RRF':
                        if f[4] == b'CUI':
                            if f[8] in (b'DA', b'MR', b'ST') or f[0] not in cuis:return None
                            identifier, kind = f[0], b'CUI'
                        else:
                            identifier, kind = aui(f[3], new), b'SRC_ATOM_ID'
                            if identifier is None:return None
                        return attribute([identifier, b'S', f[8], f[10], f[9], b'R', b'Y', b'N', f[11], kind, b'', f[7], b''])
                    if filename == 'MRSTY.RRF':
                        identifier = cuis.get(f[0])
                        if identifier is None:return None
                        return attribute([identifier, b'C', b'SEMANTIC_TYPE', f[3], b'E-' + VERSION, b'R', b'Y', b'N', b'N', b'SRC_ATOM_ID', b'', b'', b''])
                    if filename == 'MRDEF.RRF':
                        identifier = aui(f[1], new)
                        if identifier is None:return None
                        return attribute([identifier, b'S', b'DEFINITION', f[5], f[4], b'R', b'Y', b'N', f[6], b'SRC_ATOM_ID', b'', f[3], b''])
                    if f[3] in (b'PAR', b'CHD', b'SIB'):return None
                    if f[2] != b'CUI' or f[6] != b'CUI':
                        first, second, kind = aui(f[1], new), aui(f[5], new), b'SRC_ATOM_ID'
                        if first is None or second is None:return None
                        if not (f[13] == b'Y' or (f[13] != b'N' and (f[12] or f[1] <= f[5]))):return None
                    else:
                        first, second, kind = f[0], f[4], b'CUI_CURRENT'
                        if first not in cuis or second not in cuis:return None
                        if not (f[13] == b'Y' or (f[13] != b'N' and first <= second)):return None
                    rel = {b'RB': b'BT', b'RN': b'NT', b'RO': b'RT', b'RQ': b'RT?'}.get(f[3], f[3])
                    return row([b'S', first, rel, f[7], second, f[10], f[11], b'R', b'Y', b'N', f[14], kind, b'', kind, b'', b'~DA:' + f[12] if f[12] else b'', f[12], b''])
                record('relationships.src' if filename == 'MRREL.RRF' else 'attributes.src', render(False), render(True), filename, number)
    return changes, traces


def compare_transition(reference, candidate, removed, added, old_rows=None, new_rows=None):
    """Retain every unchanged row in order; account for each native delta and ID."""
    removed, added = removed.copy(), added.copy()
    counts = [0, 0]
    def records(handle, index, limit):
        source = handle if limit is None else itertools.islice(handle, limit)
        for raw in source:
            counts[index] += 1
            identifier, content = raw.split(b'|', 1)
            require(identifier == str(counts[index]).encode(), 'Generated ID is not the complete sequential allocation at row ' + str(counts[index]))
            yield content
    left, right = iter(records(reference, 0, old_rows)), iter(records(candidate, 1, new_rows))
    a, b = next(left, None), next(right, None)
    matched = deleted = inserted = 0
    while a is not None or b is not None:
        if a is not None and a == b:
            matched += 1;a, b = next(left, None), next(right, None)
        elif a is not None and removed[a]:
            removed[a] -= 1;deleted += 1;a = next(left, None)
        elif b is not None and added[b]:
            added[b] -= 1;inserted += 1;b = next(right, None)
        else:
            raise RuntimeError('Unexplained ordered record change near old/new rows ' + str(counts) +
                               ': old=' + repr(a[:256] if a else None) + '; new=' + repr(b[:256] if b else None))
    require(not any(removed.values()) and not any(added.values()), 'A predicted native correction was not emitted with its full multiplicity')
    require(old_rows is None or counts[0] == old_rows, 'Official native attribute prefix is incomplete')
    require(new_rows is None or counts[1] == new_rows, 'Candidate native attribute prefix is incomplete')
    return {'old_rows': counts[0], 'new_rows': counts[1], 'unchanged_content_in_order': matched,
            'removed_native_records': deleted, 'added_native_records': inserted, 'every_generated_id_verified': True}


def preferred(reference, candidate):
    value = hashlib.sha256();removed_targets = set();remaining_targets = set()
    with (reference / 'said.ptsaid').open('rb') as handle:
        for raw in handle:
            first, second = raw.rstrip(b'\n').split(b'|')
            if first in REMOVED:removed_targets.add(second)
            else:
                require(second not in REMOVED, 'A retained atom still depends on a deleted CCS preferred atom')
                remaining_targets.add(second);value.update(raw)
    require(value.hexdigest() == sha(candidate / 'said.ptsaid'), 'Preferred mappings changed beyond the two removed atoms')
    value = hashlib.sha256()
    with (reference / 'ptsaid.order').open('rb') as handle:
        for raw in handle:
            identifier = raw.rstrip(b'\n')
            if identifier not in removed_targets or identifier in remaining_targets:value.update(raw)
    require(value.hexdigest() == sha(candidate / 'ptsaid.order'), 'Preferred ordering changed beyond removed unreferenced CCS targets')


def sorted_file(source, output, scratch, stable_subject=False):
    command = ['/usr/bin/sort', '-S', '256M', '-T', str(scratch)]
    if stable_subject:command += ['-s', '-t', '|', '-k1,1']
    subprocess.run(command + [str(source), '-o', str(output)], env=dict(os.environ, LC_ALL='C'), check=True, timeout=3600)


def generated_id_reference_check(validation, framework_relationships):
    """Exclude generated-ID references while retaining exact framework code refs.

    SRCbuilder.pl:338 emits the version/root relationship using CODE_TERMGROUP
    with SRC/VPT and SRC/RPT qualifiers. These are code identities, not generated
    attribute/relationship IDs. Require exactly the types/counts in the unchanged
    frozen rel_src input; do not add a general unknown-type allowance.
    """
    allowed = {'CUI', 'CUI_CURRENT', 'CUI_PREVIOUS', 'SRC_ATOM_ID'}
    framework = Counter()
    with framework_relationships.open('rb') as handle:
        for raw in handle:
            f = raw.rstrip(b'\n').split(b'|')
            require(len(f) == 19, 'Unexpected framework relationship layout')
            for kind, qualifier in ((f[12], f[13]), (f[14], f[15])):
                require(kind == b'CODE_TERMGROUP' and qualifier in (b'SRC/VPT', b'SRC/RPT'), 'Unreviewed framework reference type')
                framework[(kind + b'|' + qualifier).decode()] += 1
    for name, item in validation['files'].items():
        extra = {key: count for key, count in item['identifier_types_and_qualifiers'].items() if key.split('|', 1)[0] not in allowed}
        require(extra == dict(framework) if name == 'relationships.src' else not extra,
                'Unreviewed reference type could depend on generated attribute/relationship IDs: ' + name)
    return {'no_generated_attribute_or_relationship_ID_references': True,
            'unchanged_framework_code_references': dict(framework),
            'producer_evidence': 'INV/bin/SRCbuilder.pl:338; INV/etc/inv_defaults.cfg Relation fields 13/15'}


def contexts(reference, candidate, scratch, native_count):
    unsorted, expected = scratch / 'contexts.unsorted', scratch / 'contexts.expected'
    changed = 0
    with unsorted.open('wb') as out, (reference / 'contexts.src').open('rb') as source:
        for raw in source:
            f = raw.rstrip(b'\n').split(b'|')
            if not f[0]:
                require(not f[11] and f[3] == b'770620428' and f[4] == b'LNC_2_82', 'Unrecognized missing context identity')
                f[0] = f[11] = PART[2];raw = row(f);changed += 1
            out.write(raw)
    require(changed == 1, 'Expected exactly one official blank LOINCPARTS context')
    sorted_file(unsorted, expected, scratch)
    require(sha(expected) == sha(candidate / 'contexts.src'), 'Contexts differ beyond the predicted native node restoration')
    unsorted, expected = scratch / 'context-attributes.unsorted', scratch / 'context-attributes.sorted'
    changed = 0
    with unsorted.open('wb') as out, (reference / 'attributes.contexts-all.src').open('rb') as source:
        for raw in source:
            f = raw.rstrip(b'\n').split(b'|')[1:]
            if not f[0]:
                require(f[2] == b'CONTEXT' and b'LOINCPARTS' in f[3] and b'::~~SRC_ATOM_ID~~~SRC_ATOM_ID~' in f[3], 'Unrecognized blank CONTEXT attribute')
                f[0] = PART[2]
                f[3] = f[3].replace(b'::~~SRC_ATOM_ID~~~SRC_ATOM_ID~', b'::~' + PART[2] + b'~SRC_ATOM_ID~~' + PART[2] + b'~SRC_ATOM_ID~')
                f[12] = hashlib.md5(f[3]).hexdigest().encode();changed += 1
            out.write(row(f))
    require(changed == 1, 'Expected exactly one official blank-node CONTEXT attribute')
    sorted_file(unsorted, expected, scratch, stable_subject=True)
    value = hashlib.sha256();count = 0
    with expected.open('rb') as handle:
        for count, raw in enumerate(handle, 1):value.update(str(native_count + count).encode() + b'|' + raw)
    require(value.hexdigest() == sha(candidate / 'attributes.contexts-all.src'), 'CONTEXT attribute content/order/ID reassignment differs from the explicit node-restoration prediction')
    return {'context_rows_corrected': 1, 'context_attributes_corrected': 1, 'context_attribute_rows': count,
            'context_file_predicted_byte_exact': True, 'context_attribute_file_predicted_byte_exact': True}


def audit(package, target, result, run, progress=print):
    require(not (run / 'correction-audit.json').exists(), 'A completed correction audit already exists; preserve it before a separately named review')
    require(package['engine_ref'] == 'b2611abcf929981628bb2e5051afb450b8525b70', 'This correction audit applies only to the separate reviewed source candidate')
    require(result['engine_ref'] == package['engine_ref'] and result['comparison']['validation']['passed'], 'Successful independent validation of the matching candidate is required')
    require(sha(Path(package['archive_path'])) == package['archive_sha256'], 'Official reference archive changed')
    candidate = target / 'src'
    with tempfile.TemporaryDirectory(prefix='.mth-correction-audit-', dir=str(run)) as temporary:
        scratch = Path(temporary);reference = scratch / 'official';reference.mkdir()
        wanted = {item['path']: item for item in package['reference_files']};found = set()
        with tarfile.open(package['archive_path'], 'r|gz') as archive:
            for member in archive:
                if member.name not in wanted:continue
                item = wanted[member.name];name = item['output_name']
                require(member.isfile() and name not in found and Path(name).name == name, 'Invalid/duplicate reference member')
                import shutil
                with (reference / name).open('xb') as out:shutil.copyfileobj(archive.extractfile(member), out, 4194304)
                require(sha(reference / name) == item['sha256'], 'Official member differs from frozen reference')
                found.add(name)
        require(found == {x['output_name'] for x in wanted.values()}, 'Incomplete official reference')
        aui, old_cuis, new_cuis, maps = expected_maps(reference, candidate)
        native = target / 'src/Meta'
        changes, traces = native_changes(native, aui, old_cuis, new_cuis, progress)
        attributes = changes['attributes.src'];relationships = changes['relationships.src']
        old_native = identity(reference / 'attributes.src')['newline_count'] - identity(reference / 'attributes.contexts-all.src')['newline_count']
        new_native = old_native - sum(attributes['removed'].values()) + sum(attributes['added'].values())
        with (reference / 'attributes.src').open('rb') as old, (candidate / 'attributes.src').open('rb') as new:
            attr_result = compare_transition(old, new, attributes['removed'], attributes['added'], old_native, new_native)
            require(stream_sha(new) == sha(candidate / 'attributes.contexts-all.src'), 'Final attributes do not append the verified context-attribute helper exactly')
        with (reference / 'relationships.src').open('rb') as old, (candidate / 'relationships.src').open('rb') as new:
            rel_result = compare_transition(old, new, relationships['removed'], relationships['added'])
        preferred(reference, candidate)
        context_result = contexts(reference, candidate, scratch, new_native)
        changed = {'aui_said_map', 'cui_said_map', 'rel_cui_said_map', 'classes_atoms.src.raw',
                   'said.ptsaid', 'ptsaid.order', 'attributes.src', 'relationships.src',
                   'contexts.src', 'attributes.contexts-all.src'}
        unaffected = [name for name in found if name not in changed]
        require(all(sha(reference / name) == sha(candidate / name) for name in unaffected), 'An unrelated reference output changed')
        id_reference_check = generated_id_reference_check(result['comparison']['validation'], reference / 'rel_src')
        for name, entry in result['comparison']['files'].items():
            require(sha(candidate / name) == entry['candidate']['sha256'], 'Output changed after the full comparison')
        report = {'status': 'PASS_REVIEWED_CORRECTIONS', 'engine_ref': package['engine_ref'], 'run_id': package['run_id'],
                  'conversion_apparatus_ref': package['apparatus_ref'], 'audit_tool_sha256': sha(Path(__file__)),
                  'raw_comparison_status': result['acceptance']['status'], 'independent_validation_passed': True,
                  'maps': maps, 'attributes': attr_result, 'relationships': rel_result, 'contexts': context_result,
                  'native_changes': traces, 'unaffected_outputs_exact': sorted(unaffected),
                  'generated_ID_reference_check': id_reference_check,
                  'all_atom_allocations_unchanged': True, 'preferred_state_predicted': True,
                  'generated_ID_changes_accounted_for_by_native_insertions_deletions_and_context_reordering': True,
                  'raw_comparison_rewritten': False, 'production_eligible': False}
        save_report(run / 'correction-audit.json', report)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path);parser.add_argument('target', type=Path);parser.add_argument('run', type=Path)
    args = parser.parse_args();guard()
    result = json.loads((args.run / 'result.json').read_text())
    print(json.dumps(audit(json.loads(args.package.read_text()), args.target, result, args.run), indent=2))
