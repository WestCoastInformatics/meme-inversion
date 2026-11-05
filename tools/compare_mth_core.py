#!/usr/bin/env python3
"""Compare MTH core files and regenerated identity state without ID waivers."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from acquire_mth_subset import identity
from compare_nci_core import compare_sorted

WIDTHS = {'classes_atoms.src': 15, 'attributes.src': 15, 'relationships.src': 19,
          'mergefacts.src': 13, 'bequeathal.relationships.src': 19, 'contexts.src': 19}


def structure(paths, bounds):
    """Check the observed MTH dialect, keeping CUI roles and both context tails."""
    atoms = set()
    duplicates = out_of_range = 0
    with paths['classes_atoms.src'].open('rb') as handle:
        for row in handle:
            value = row.split(b'|', 1)[0]
            duplicates += value in atoms
            atoms.add(value)
            out_of_range += not value.isdigit() or not bounds[0] <= int(value) <= bounds[1]
    result = {'atom_ids': {'unique': len(atoms), 'duplicates': duplicates, 'out_of_range': out_of_range}, 'files': {}}
    for name, path in paths.items():
        widths, problems, types = Counter(), Counter(), Counter()
        generated = set()
        rows = 0
        with path.open('rb') as handle:
            for row in handle:
                rows += 1
                problems['missing_newline'] += not row.endswith(b'\n')
                problems['nul'] += b'\0' in row
                try:
                    row.decode('utf-8')
                except UnicodeDecodeError:
                    problems['invalid_utf8'] += 1
                f = row.removesuffix(b'\n').split(b'|')
                widths[len(f)] += 1
                if len(f) != WIDTHS[name]:
                    problems['field_count'] += 1
                    continue
                if name != 'classes_atoms.src':
                    problems['nonempty_trailing_field'] += f[-1] != b''
                if name == 'contexts.src':
                    problems['nonempty_second_context_tail'] += f[-2] != b''
                if name in {'attributes.src', 'relationships.src', 'bequeathal.relationships.src'}:
                    problems['invalid_generated_id'] += not f[0].isdigit()
                    problems['duplicate_generated_id'] += f[0] in generated
                    generated.add(f[0])
                endpoints = []
                if name == 'attributes.src':
                    problems['attribute_digest'] += hashlib.md5(f[4]).hexdigest().encode() != f[13]
                    endpoints = [(f[1], f[10], f[11])]
                elif name in {'relationships.src', 'bequeathal.relationships.src'}:
                    endpoints = [(f[2], f[12], f[13]), (f[5], f[14], f[15])]
                    problems['unmapped_relationship'] += f[3].startswith(b'XX-') or b'###' in f[3] or b'###' in f[4]
                elif name == 'mergefacts.src':
                    endpoints = [(f[0], f[8], f[9]), (f[2], f[10], f[11])]
                elif name == 'contexts.src':
                    endpoints = [(f[11], f[12], f[13]), (f[14], f[15], f[16]), (f[0], b'SRC_ATOM_ID', b''), (f[3], b'SRC_ATOM_ID', b'')]
                    path_ids = f[7].split(b'.') if f[7] else []
                    problems['unresolved_context_path'] += any(value not in atoms for value in path_ids)
                    if f[1] == b'PAR':
                        problems['context_parent_mismatch'] += not path_ids or path_ids[-1] != f[3]
                for value, kind, qualifier in endpoints:
                    types[kind.decode(errors='replace') + '|' + qualifier.decode(errors='replace')] += 1
                    if kind == b'SRC_ATOM_ID':
                        problems['unresolved_atom_reference'] += value not in atoms
        result['files'][name] = {'rows': rows, 'field_counts': dict(widths), 'violations': {k: v for k, v in problems.items() if v},
                                 'identifier_types_and_qualifiers': dict(types)}
    result['passed'] = bool(atoms) and not duplicates and not out_of_range and all(not x['violations'] for x in result['files'].values())
    result['scope'] = 'Observed MTH field widths and context tails, UTF-8, unique generated IDs, reserved atom bounds including two SRC atoms, attribute digests and current SRC_ATOM_ID references/paths. CUI, CUI_CURRENT and CUI_PREVIOUS remain distinct; database identity/domain validation and legacy QA are separate coverage.'
    return result


def compare(package, target, run, save, progress=print):
    expected = package['reference_files']
    names = {x['output_name'] for x in expected}
    if not set(WIDTHS).issubset(names):
        raise RuntimeError('Six MTH core outputs must be compared')
    scratch = Path(tempfile.mkdtemp(prefix='.mth-comparison-', dir=str(target / 'src')))
    files = {}
    try:
        refs = {x['path']: x for x in expected}
        with tarfile.open(package['archive_path'], 'r|gz') as tar:
            for member in tar:
                if member.name not in refs:
                    continue
                item = refs[member.name]
                name = item['output_name']
                if not member.isfile() or name in files:
                    raise RuntimeError('Reference member is not unique and regular')
                reference = scratch / ('reference-' + name)
                with reference.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 4194304)
                observed = identity(reference)
                if observed['sha256'] != item['sha256'] or observed['newline_count'] != item['newline_count']:
                    raise RuntimeError('Reference member hash/count differs')
                candidate = target / 'src' / name
                if candidate.is_symlink() or not candidate.is_file():
                    raise RuntimeError('Generated output missing: ' + name)
                candidate_identity = identity(candidate)
                entry = {'reference': observed, 'candidate': candidate_identity, 'reference_member': member.name,
                         'exact_match': candidate_identity['sha256'] == observed['sha256']}
                if not entry['exact_match']:
                    progress('PHASE: full-record multiset comparison for ' + name, flush=True)
                    left, right = scratch / 'reference.sorted', scratch / 'candidate.sorted'
                    for source, output in [(reference, left), (candidate, right)]:
                        subprocess.run(['/usr/bin/sort', '-S', '256M', '-T', str(scratch), str(source), '-o', str(output)], env=dict(os.environ, LC_ALL='C'), check=True, timeout=3600)
                    with left.open('rb') as a, right.open('rb') as b:
                        entry['full_record_multiset'] = compare_sorted(iter(a), iter(b))
                    left.unlink()
                    right.unlink()
                files[name] = entry
                progress('COMPARED: ' + name + ' exact=' + str(entry['exact_match']), flush=True)
        if set(files) != names:
            raise RuntimeError('Required reference files missing')
        progress('PHASE: independent MTH structure checks', flush=True)
        validation = structure({name: target / 'src' / name for name in WIDTHS}, (769443591, 773943592))
        exact = all(x['exact_match'] for x in files.values())
        equal = all(x['exact_match'] or x.get('full_record_multiset', {}).get('equal_preserving_multiplicity') for x in files.values())
        status = ('PASS_EXACT' if exact else 'PASS_RECORD_EQUIVALENT') if equal and validation['passed'] else ('REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS' if equal else 'DIFFERENCES_REQUIRE_REVIEW')
        result = {'source': 'MTH', 'version': 'MTH_2026AA', 'files': files, 'validation': validation,
                  'acceptance': {'status': status, 'all_compared_outputs_exact': exact, 'all_compared_records_equal': equal,
                                 'six_core_files_exact': all(files[x]['exact_match'] for x in WIDTHS),
                                 'generated_ids_reindexed': False, 'ignored_fields': [], 'validation_passed': validation['passed']},
                  'scope': 'Final-range core conversion, moved/split CUI/AUI identity maps, bequeathal relationships and contexts from archived prepared subset and metadata. MetamorphoSys generation, source-metadata acquisition, preliminary ID estimation, MRDOC/legacy QA, umlscui.txt and insertion are outside this case.'}
        save(run / 'comparison.json', result)
        return result
    finally:
        shutil.rmtree(scratch)
