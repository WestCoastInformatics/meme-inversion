#!/usr/bin/env python3
"""Compare all SNOMED core record bytes, including IDs and multiplicity."""
from collections import Counter
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from compare_nci_core import FIELDS, compare_sorted
from prepare_snomed_candidate import CORE_NAMES, TARGET, VERSION, guard, info, now, require_hash, save

FRAMEWORK_TERMGROUPS = {b'SRC/VPT', b'SRC/VAB', b'SRC/RPT', b'SRC/RAB', b'SRC/SSN'}
ID_TYPES = {b'SRC_ATOM_ID', b'SOURCE_CUI', b'SOURCE_AUI', b'SOURCE_RUI', b'SOURCE_ATUI',
            b'CODE_SOURCE', b'CODE_ROOT_SOURCE', b'CODE_TERMGROUP', b'ROOT_SOURCE_CUI'}


def structure(paths, termgroups, said_bounds):
    """Validate native record structure and current atom/context references.

    SOURCE_RUI/ATUI and cross-source identifiers are reported by type but are not
    resolved against a database. No generated ID is removed from comparisons.
    """
    atoms, atom_cuis, source_auis = set(), {}, set()
    declared = set(termgroups) | FRAMEWORK_TERMGROUPS
    unknown_groups = Counter()
    atom_duplicates = atom_out_of_range = 0
    with paths['classes_atoms.src'].open('rb') as handle:
        for row in handle:
            fields = row.removesuffix(b'\n').split(b'|')
            if len(fields) != 15:
                continue
            atom_duplicates += fields[0] in atoms
            atoms.add(fields[0])
            atom_cuis[fields[0]] = fields[10]
            if fields[9]:
                source_auis.add(fields[9])
            if fields[2] not in declared:
                unknown_groups[fields[2].decode(errors='replace')] += 1
            atom_out_of_range += not fields[0].isdigit() or not said_bounds[0] <= int(fields[0]) <= said_bounds[1]
    result = {'atom_ids': {'unique': len(atoms), 'duplicates': atom_duplicates, 'out_of_reserved_range': atom_out_of_range},
              'unknown_termgroups': dict(unknown_groups), 'files': {}}
    for name, path in paths.items():
        widths, types, attribute_names = Counter(), Counter(), Counter()
        generated_ids = set()
        bad = Counter()
        rows = 0
        with path.open('rb') as handle:
            for row in handle:
                rows += 1
                bad['missing_newline'] += not row.endswith(b'\n')
                bad['nul'] += b'\0' in row
                try:
                    row.decode('utf-8')
                except UnicodeDecodeError:
                    bad['invalid_utf8'] += 1
                fields = row.removesuffix(b'\n').split(b'|')
                widths[len(fields)] += 1
                if len(fields) != len(FIELDS[name]):
                    bad['field_count'] += 1
                    continue
                if name != 'classes_atoms.src':
                    bad['nonempty_trailing_field'] += fields[-1] != b''
                endpoints = []
                if name in {'attributes.src', 'relationships.src'}:
                    bad['invalid_generated_id'] += not fields[0].isdigit()
                    bad['duplicate_generated_id'] += fields[0] in generated_ids
                    generated_ids.add(fields[0])
                if name == 'attributes.src':
                    attribute_names[fields[3].decode(errors='replace')] += 1
                    bad['attribute_digest'] += hashlib.md5(fields[4]).hexdigest().encode() != fields[13]
                    endpoints = [(fields[1], fields[10], fields[11])]
                    # The production cleanup promises no dangling description attributes.
                    if fields[10] == b'SOURCE_AUI' and fields[11] == VERSION.encode():
                        bad['dangling_description_attribute'] += fields[1] not in source_auis
                elif name == 'relationships.src':
                    endpoints = [(fields[2], fields[12], fields[13]), (fields[5], fields[14], fields[15])]
                    bad['unmapped_relationship'] += fields[3].startswith(b'XX-') or b'###' in fields[3] or b'###' in fields[4]
                elif name == 'mergefacts.src':
                    endpoints = [(fields[0], fields[8], fields[9]), (fields[2], fields[10], fields[11])]
                elif name == 'contexts.src':
                    endpoints = [(fields[11], fields[12], fields[13]), (fields[14], fields[15], fields[16])]
                    chain = fields[7].split(b'.') if fields[7] else []
                    bad['unresolved_context_atom'] += fields[0] not in atoms or fields[3] not in atoms
                    bad['unresolved_context_path'] += any(x not in atoms for x in chain)
                    bad['context_parent_path_mismatch'] += not chain or chain[-1] != fields[3]
                    if fields[12] == b'SOURCE_CUI' and fields[13] == VERSION.encode():
                        bad['context_child_identity'] += atom_cuis.get(fields[0]) != fields[11]
                    if fields[15] == b'SOURCE_CUI' and fields[16] == VERSION.encode():
                        bad['context_parent_identity'] += atom_cuis.get(fields[3]) != fields[14]
                for value, kind, qualifier in endpoints:
                    types[kind.decode(errors='replace') + '|' + qualifier.decode(errors='replace')] += 1
                    bad['unknown_identifier_type'] += kind not in ID_TYPES
                    if kind == b'SRC_ATOM_ID':
                        bad['unresolved_atom_id'] += value not in atoms
        result['files'][name] = {'rows': rows, 'field_counts': dict(widths), 'violations': {k: v for k, v in bad.items() if v},
                                 'identifier_types_and_qualifiers': dict(types)}
        if attribute_names:
            result['files'][name]['attribute_names'] = dict(attribute_names)
    result['passed'] = bool(atoms) and not atom_duplicates and not atom_out_of_range and not unknown_groups and all(not x['violations'] for x in result['files'].values())
    result['scope'] = 'Field structure, UTF-8, unique generated IDs (gaps permitted), reserved atom bounds, declared/framework termgroups, attribute digests, cleanup description references and context atom/path/identity consistency. Full-record comparison retains all typed qualifiers, groups, mapping values and IDs. Not complete release/domain validation.'
    return result


def multiset(reference, candidate, scratch):
    sorted_files = [scratch / 'reference.sorted', scratch / 'candidate.sorted']
    try:
        for source, output in zip([reference, candidate], sorted_files):
            subprocess.run(['/usr/bin/sort', '-S', '256M', '-T', str(scratch), str(source), '-o', str(output)],
                           env=dict(os.environ, LC_ALL='C'), check=True, timeout=3600)
        with sorted_files[0].open('rb') as left, sorted_files[1].open('rb') as right:
            result = compare_sorted(iter(left), iter(right))
        result['reference_sorted_sha256'] = info(sorted_files[0])['sha256']
        result['candidate_sorted_sha256'] = info(sorted_files[1])['sha256']
        return result
    finally:
        for file in sorted_files:
            file.unlink(missing_ok=True)


def verdict(files, validation_passed):
    exact = set(files) == CORE_NAMES and all(x['exact_match'] for x in files.values())
    equal = set(files) == CORE_NAMES and all(x['exact_match'] or x.get('full_record_multiset', {}).get('equal_preserving_multiplicity', False) for x in files.values())
    status = ('PASS_EXACT' if exact else 'PASS_RECORD_EQUIVALENT') if equal and validation_passed else ('REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS' if equal else 'DIFFERENCES_REQUIRE_REVIEW')
    return {'status': status, 'all_five_exact': exact, 'all_five_full_record_equivalent': equal,
            'independent_structure_checks_passed': validation_passed,
            'ignored_columns': [], 'generated_identifiers_reindexed': False,
            'scope': 'Five core inversion outputs after documented dangling-attribute cleanup, with archived source metadata and ICD inventories; excludes their acquisition, MRDOC, legacy/API QA, insertion and release eligibility'}


def compare(contract, core, progress=print):
    guard()
    archive = Path(contract['reference']['archive_path'])
    require_hash(archive, contract['reference']['archive_sha256'])
    expected = {x['reference_path']: x for x in contract['reference_file_map']}
    candidate = {name: TARGET / 'src' / name for name in CORE_NAMES}
    if core['exit_status'] != 0 or core['cleanup_exit_status'] != 0:
        raise RuntimeError('Successful core conversion and cleanup are required')
    for name, item in core['files'].items():
        require_hash(candidate[name], item['sha256'])
    scratch = Path(tempfile.mkdtemp(prefix='snomed-comparison-', dir=str(TARGET / 'tmp')))
    result = {'source': 'SNOMEDCT_US', 'version': VERSION, 'engine_ref': contract['engine_ref'],
              'run_id': contract['run_id'], 'started_at': now(), 'files': {}, 'reference_stage': 'inversion-src',
              'archive_sha256': contract['reference']['archive_sha256'], 'candidate_modified': False,
              'insertion_executed': False, 'comparison_profile': 'snomed-core-v1: exact bytes or full-record multiset, retaining every field and duplicate; no generated-ID waiver'}
    try:
        references = {}
        with tarfile.open(archive, 'r|gz') as tar:
            for member in tar:
                name = member.name.removeprefix('./')
                if name not in expected:
                    continue
                item = expected[name]
                output_name = item['output_name']
                if not member.isfile() or output_name in references:
                    raise RuntimeError('Reference member is not unique and regular')
                destination = scratch / ('reference-' + output_name)
                progress('PHASE: reading official reference ' + name, flush=True)
                with destination.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 4194304)
                observed = info(destination)
                if observed['sha256'] != item['sha256'] or observed['newline_count'] != item['newline_count'] or observed['bytes'] != item['size']:
                    raise RuntimeError('Reference member identity changed')
                references[output_name] = destination
                result['files'][output_name] = {'reference_member': name, 'reference': observed, 'candidate': core['files'][output_name],
                                                'exact_match': observed['sha256'] == core['files'][output_name]['sha256']}
        if set(references) != CORE_NAMES:
            raise RuntimeError('Missing official core reference')
        for name in sorted(CORE_NAMES):
            entry = result['files'][name]
            if not entry['exact_match']:
                progress('PHASE: comparing all record fields and duplicates for ' + name, flush=True)
                entry['full_record_multiset'] = multiset(references[name], candidate[name], scratch)
        groups = {row.split(b'|', 1)[0] for row in (TARGET / 'src/termgroups.src').read_bytes().splitlines()}
        progress('PHASE: independent structure and context checks', flush=True)
        result['candidate_validation'] = structure(candidate, groups, (777343593, 779143592))
        if not all(x['exact_match'] for x in result['files'].values()):
            progress('PHASE: checking the official reference under the same validation rules', flush=True)
            result['reference_validation'] = structure(references, groups, (777343593, 779143592))
        else:
            result['reference_validation'] = {'same_bytes_as_candidate': True, 'passed': result['candidate_validation']['passed']}
        result['acceptance'] = verdict(result['files'], result['candidate_validation']['passed'])
        result['completed_at'] = now()
        save(TARGET / 'etc/replay-comparison.json', result)
        return result
    finally:
        shutil.rmtree(scratch)
