#!/usr/bin/env python3
"""Compare MDR/RADLEX core files without hiding records, fields or duplicates."""
import datetime
import hashlib
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

from compare_nci_core import FIELDS, attribute_view, file_info, ordered_and_multiset, structure

OUTPUTS = tuple(FIELDS)
FRAMEWORK_TERMGROUPS = {b'SRC/VPT', b'SRC/VAB', b'SRC/RPT', b'SRC/RAB', b'SRC/SSN', b'SRC/VSY'}
# These identify atoms, native codes or native identifiers, never generated AIDs.
NON_ATTRIBUTE_ID_TYPES = {'SRC_ATOM_ID', 'CODE_SOURCE', 'CODE_TERMGROUP', 'SOURCE_CUI',
                          'SOURCE_DUI', 'SOURCE_AUI', 'ROOT_SOURCE_AUI'}


def identifiers(path):
    values = set();duplicates = invalid = 0
    with path.open('rb') as handle:
        for raw in handle:
            token = raw.split(b'|', 1)[0]
            if not token.isdigit() or int(token) <= 0:
                invalid += 1;continue
            value = int(token);duplicates += value in values;values.add(value)
    digest = hashlib.sha256()
    for value in sorted(values):digest.update((str(value) + '\n').encode())
    return {'unique': len(values), 'duplicates': duplicates, 'invalid': invalid,
            'minimum': min(values) if values else None, 'maximum': max(values) if values else None,
            'sorted_identifier_sha256': digest.hexdigest()}


def validation(paths, contract, termgroups):
    try:
        result = structure(paths, contract['root_atom_id'], termgroups | FRAMEWORK_TERMGROUPS)
        atoms = identifiers(paths['classes_atoms.src'])
        result['atom_identifier_set'] = atoms
        bounds = contract['source_atom_ids']
        result['historical_identifier_bounds'] = {'start': bounds['start'], 'end': bounds['end'],
                                                 'provenance_kind': bounds['provenance_kind'],
                                                 'production_reservation_end_assessed': bounds['production_reservation_end_assessed']}
        result['identifier_bounds_passed'] = bool(atoms['unique']) and not atoms['invalid'] and not atoms['duplicates'] and atoms['minimum'] == bounds['start'] and atoms['maximum'] <= bounds['end']
        result['checks_passed'] = result['checks_passed'] and result['termgroup_validation']['passed'] and result['identifier_bounds_passed']
        result['scope'] += '; fixed historical ID bounds and saved external root anchor. Production reservation/domain/database QA remain separately scoped.'
        return result
    except (ValueError, IndexError, UnicodeError) as error:
        return {'checks_passed': False, 'error': type(error).__name__ + ': ' + str(error),
                'scope': 'Malformed records prevented complete independent validation; no acceptance is granted.'}


def record_comparison(reference, candidate, scratch):
    result = ordered_and_multiset(reference, candidate, scratch)
    # Detailed record bytes remain in the protected source/archive, not Git reports.
    result.pop('samples', None)
    return result


def attribute_diagnostics(reference, candidate, scratch):
    files = [scratch / 'reference-attribute-content', scratch / 'candidate-attribute-content']
    try:
        views = [attribute_view(path, output) for path, output in zip((reference, candidate), files)]
        ids = [identifiers(path) for path in (reference, candidate)]
        content = record_comparison(files[0], files[1], scratch)
        return {'reference': views[0], 'candidate': views[1], 'identifier_sets': ids,
                'content_multiset_excluding_generated_attribute_id': content,
                'same_kept_identifier_set': ids[0] == ids[1],
                'non_context_full_records_exact': views[0]['non_context_full_record_sha256'] == views[1]['non_context_full_record_sha256'],
                'positive_unique_ids': all(x['invalid'] == x['duplicates'] == 0 for x in ids)}
    finally:
        for path in files:path.unlink(missing_ok=True)


def acceptance(files, scans):
    raw_exact = all(item['exact_match'] for item in files.values())
    checks = {'all_five_present': set(files) == set(OUTPUTS),
              'atoms_exact': files['classes_atoms.src']['exact_match'],
              'relationships_exact': files['relationships.src']['exact_match'],
              'merges_exact': files['mergefacts.src']['exact_match'],
              'context_full_record_multiset_equal': files['contexts.src']['row_multiset']['equal_preserving_multiplicity']}
    attr = files['attributes.src']['attribute_diagnostics']
    checks.update(attribute_content_and_duplicates_equal=attr['content_multiset_excluding_generated_attribute_id']['equal_preserving_multiplicity'],
                  attribute_ids_positive_unique=attr['positive_unique_ids'],
                  same_kept_attribute_identifier_set=attr['same_kept_identifier_set'],
                  non_context_attribute_records_exact=attr['non_context_full_records_exact'])
    scans_ok = all(scan.get('checks_passed') for scan in scans.values()) and attr['positive_unique_ids']
    checks['independent_reference_and_candidate_checks'] = scans_ok
    atom_sets = [scan.get('atom_identifier_set') for scan in scans.values()]
    checks['same_atom_identifier_set'] = None not in atom_sets and atom_sets[0] == atom_sets[1]
    known_types = all(set(item['identifier_types']) <= NON_ATTRIBUTE_ID_TYPES for scan in scans.values() for item in scan.get('files', {}).values())
    unchanged_aid_bindings = files['attributes.src']['exact_match'] or files['attributes.src'].get('row_multiset', {}).get('equal_preserving_multiplicity', False)
    checks['attribute_id_reference_safety'] = unchanged_aid_bindings or known_types
    content_checks = {key: value for key, value in checks.items() if key != 'independent_reference_and_candidate_checks'}
    equivalent = all(content_checks.values())
    if raw_exact and scans_ok:
        status = 'PASS_EXACT'
    elif equivalent and scans_ok:
        status = 'PASS_EQUIVALENT'
    elif raw_exact or equivalent:
        status = 'REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS'
    else:
        status = 'DIFFERENCES_REQUIRE_REVIEW'
    return {'status': status, 'all_five_exact': raw_exact, 'checks': checks,
            'independent_checks_passed': scans_ok, 'ignored_fields': [], 'candidate_rewritten': False,
            'profile': 'Exact atoms/relationships/merges; complete context rows; attribute content and duplicates with equal kept ID sets and exact non-CONTEXT records. No generated-ID reference allowance.',
            'scope': 'Historical core compatibility with saved preparation inputs and root identity; not metadata generation, legacy QA, insertion or production eligibility.'}


def compare(contract, target, run, progress=print):
    reference_entries = {item['path']: item for item in contract['reference_files']}
    if len(reference_entries) != 5 or {x['output_name'] for x in reference_entries.values()} != set(OUTPUTS):
        raise ValueError('Exactly five reviewed per-output references are required')
    result = {'source': contract['source'], 'version': contract['version'], 'engine_ref': contract['engine_ref'],
              'run_id': contract['run_id'], 'reference_stage': 'inversion-src', 'files': {},
              'archive_sha256': contract['archive_sha256'], 'starting_stage': contract['starting_stage'],
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'candidate_modified': False, 'insertion_executed': False}
    if file_info(Path(contract['archive_path']))['sha256'] != contract['archive_sha256']:
        raise RuntimeError('Frozen official archive differs')
    with tempfile.TemporaryDirectory(prefix='framework-comparison-', dir=str(run)) as temporary:
        scratch = Path(temporary);references = {};found = set()
        with tarfile.open(contract['archive_path'], 'r|gz') as archive:
            for member in archive:
                name = PurePosixPath(member.name).as_posix()
                if name not in reference_entries:continue
                entry = reference_entries[name];output = entry['output_name']
                if not member.isfile() or output in found or Path(output).name != output:
                    raise RuntimeError('Invalid or duplicate official output member')
                path = scratch / output
                with path.open('xb') as handle:
                    import shutil
                    shutil.copyfileobj(archive.extractfile(member), handle, 4194304)
                info = file_info(path)
                if info['sha256'] != entry['sha256'] or info['newline_count'] != entry['newline_count']:
                    raise RuntimeError('Official output differs from frozen member inventory')
                references[output] = path;found.add(output)
        if found != set(OUTPUTS):raise RuntimeError('Official output set is incomplete')
        candidate = {name: target / 'src' / name for name in OUTPUTS}
        for name, path in candidate.items():
            if path.is_symlink() or not path.is_file():raise RuntimeError('Fresh candidate output is absent: ' + name)
            left, right = file_info(references[name]), file_info(path)
            entry = {'reference_member': next(item['path'] for item in reference_entries.values() if item['output_name'] == name),
                     'reference': left, 'candidate': right, 'exact_match': left['sha256'] == right['sha256']}
            if not entry['exact_match'] or name == 'contexts.src':entry['row_multiset'] = record_comparison(references[name], path, scratch)
            if name == 'attributes.src':entry['attribute_diagnostics'] = attribute_diagnostics(references[name], path, scratch)
            result['files'][name] = entry
            progress('COMPARED: ' + name + ' exact=' + str(entry['exact_match']), flush=True)
        termgroups = {row.split(b'|', 1)[0] for row in (target / 'src/termgroups.src').read_bytes().splitlines()}
        result['structure'] = {label: validation(paths, contract, termgroups) for label, paths in [('reference', references), ('candidate', candidate)]}
        result['acceptance'] = acceptance(result['files'], result['structure'])
        for name, item in result['files'].items():
            if file_info(candidate[name]) != item['candidate']:raise RuntimeError('Candidate output changed during comparison')
    result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return result
