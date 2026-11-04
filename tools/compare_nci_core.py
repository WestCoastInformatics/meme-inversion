#!/usr/bin/env python3
"""Characterize fresh NCIt core output against the retained official src archive.

Raw hashes are retained. Ordering comparison preserves every byte of every row
and its multiplicity. Attribute-ID comparison is a separate, explicit diagnostic;
it never changes the candidate or turns content differences into a pass.
"""
from collections import Counter
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import socket
import subprocess
import tarfile
import tempfile

VERSION = 'NCI_2026_10D'
ROOT = Path('/local/content/MEME/MEME5/inv/sources')
FIELDS = {
    'classes_atoms.src': ['src_atom_id', 'source', 'termgroup', 'code', 'status', 'tobereleased',
                         'released', 'atom_name', 'suppressible', 'source_aui', 'source_cui',
                         'source_dui', 'language', 'order_id', 'last_release_cui'],
    'attributes.src': ['source_attribute_id', 'id', 'attribute_level', 'attribute_name',
                       'attribute_value', 'source', 'status', 'tobereleased', 'released',
                       'suppressible', 'id_type', 'id_qualifier', 'source_atui', 'hashcode', 'trailing_empty'],
    'relationships.src': ['src_relationship_id', 'level', 'id_1', 'relationship_name',
                          'relationship_attribute', 'id_2', 'source', 'source_of_label',
                          'status', 'tobereleased', 'released', 'suppressible', 'id_type_1',
                          'id_qualifier_1', 'id_type_2', 'id_qualifier_2', 'source_rui',
                          'relationship_group', 'trailing_empty'],
    'mergefacts.src': ['id_1', 'merge_level', 'id_2', 'source', 'integrity_vector', 'make_demotion',
                       'change_status', 'merge_set', 'id_type_1', 'id_qualifier_1',
                       'id_type_2', 'id_qualifier_2', 'trailing_empty'],
    'contexts.src': ['src_atom_id_1', 'relationship_name', 'relationship_attribute', 'src_atom_id_2',
                     'source', 'source_of_label', 'hierarchy_code', 'parent_path', 'release_mode',
                     'source_rui', 'relationship_group', 'id_1', 'id_type_1', 'id_qualifier_1',
                     'id_2', 'id_type_2', 'id_qualifier_2', 'trailing_empty'],
}

# The deployed Atom object retains fields between calls. This probe uses the
# actual configuration and serializer in memory, without opening package output.
TERM_TYPE_PROBE = r'''
use strict;
use warnings;
use NLMConfig;
use Atom;
use IdGen;
use JSON::PP qw(encode_json);
{ package ProbeLog; sub logError { die $_[1]; } }
my $cfg = NLMConfig->new($ARGV[0], 0);
my $log = bless {}, 'ProbeLog';
my $ids = IdGen->new(1, 1, 1);
Atom->init(\$log, \$cfg, \$ids);
my $data = '';
open(my $out, '>', \$data) or die $!;
Atom->setFileHandler($out);
my $pt = Atom->new('');
my %row = (vsab => 'FDA_2026_10D', str => 'probe', scui => 'C1', code => 'probe', suppress => 'N');
$pt->dumpAtom({%row});
$pt->dumpAtom({%row, tty => 'PT'});
$pt->dumpAtom({%row});
close($out);
print encode_json([map { (split(/\|/, $_))[2] } split(/\n/, $data)]);
'''


def diagnose_termgroup():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Dev diagnosis only')
    target = ROOT / VERSION
    comparison = json.loads((target / 'etc/replay-comparison.json').read_text())
    changes = comparison['files']['classes_atoms.src']['aligned_differences']
    if changes['changed_positions'] != 1 or changes['changed_fields'] != {'termgroup': 1}:
        raise RuntimeError('The bounded single-termgroup diagnosis does not apply')
    sample = changes['samples'][0]
    declared = {row.split(b'|', 1)[0] for row in (target / 'src/termgroups.src').read_bytes().splitlines()}
    bad = Counter()
    observed = None
    with (target / 'src/classes_atoms.src').open('rb') as handle:
        for number, row in enumerate(handle, 1):
            pieces = row.removesuffix(b'\n').split(b'|')
            if pieces[2] not in declared:
                bad[pieces[2].decode()] += 1
            if number == sample['line']:
                observed = dict(zip(FIELDS['classes_atoms.src'], [x.decode() for x in pieces]))
    config = (target / 'etc/nci.cfg').read_text()
    sources = dict(re.findall(r'^vsab\.(\S+)\s*=\s*(\S+)', config, flags=re.M))
    native = []
    first_subsource_pt = None
    with (target / 'orig/MRCONSO.TREF').open('r') as handle:
        for number, row in enumerate(handle, 1):
            fields = row.rstrip('\n').split('|')
            if len(fields) < 6:
                continue
            sabtty = fields[4]
            if first_subsource_pt is None and sabtty.endswith('PT') and sabtty[:-2] in sources:
                first_subsource_pt = {'line': number, 'fields': fields}
            if fields[2] == observed['source_cui'] and sabtty == 'FDAPT':
                native.append({'line': number, 'fields': fields})
    with tempfile.TemporaryDirectory(prefix='replay-term-type-probe-', dir=str(target / 'tmp')) as directory:
        combined = Path(directory) / 'combined.cfg'
        combined.write_bytes((ROOT.parent / 'INV/etc/inv_defaults.cfg').read_bytes() + (target / 'etc/nci.cfg').read_bytes())
        process = subprocess.run(['unshare', '--user', '--map-root-user', '--net', '/usr/bin/perl',
                                  '-I' + str(ROOT.parent / 'INV/lib'), '-I' + str(ROOT.parent / 'INV/bin'),
                                  '-e', TERM_TYPE_PROBE, str(combined)], cwd=directory,
                                 capture_output=True, text=True, timeout=30)
    if process.returncode:
        raise RuntimeError('In-memory serializer probe failed: ' + process.stderr)
    probe = json.loads(process.stdout)
    result = {'source': 'NCI', 'version': VERSION, 'atom': observed, 'difference': sample,
              'undeclared_candidate_termgroups': dict(bad),
              'official_termgroup_declared': sample['differences'][0]['reference'].encode() in declared,
              'matching_prepared_input': native, 'first_subsource_pt_input': first_subsource_pt,
              'probe': {'termgroups_in_call_order': probe, 'expected': ['FDA_2026_10D/', 'FDA_2026_10D/PT', 'FDA_2026_10D/PT'],
                        'passed': probe == ['FDA_2026_10D/', 'FDA_2026_10D/PT', 'FDA_2026_10D/PT'],
                        'scope': 'Actual Atom serializer and combined pinned defaults/source config; output held in memory'},
              'code_cause': 'Original-code subsource PT branch omits tty; its shared ptAtom starts with an empty default and later retains PT from a different branch',
              'archive_correction_history': 'Not established; the archived atom contains PT but the pinned generator omits it for this input',
              'candidate_modified': False, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    destination = target / 'etc/replay-atom-diagnosis.json'
    with destination.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    return result


def file_info(path):
    digest = hashlib.sha256()
    lines = 0
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
            lines += block.count(b'\n')
    return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'newline_count': lines}


def compare_sorted(reference, candidate):
    """Merge two sorted row streams, retaining duplicates and all row bytes."""
    a, b = next(reference, None), next(candidate, None)
    equal = removed = added = 0
    samples = {'reference_only': [], 'candidate_only': []}
    while a is not None or b is not None:
        if a is not None and b is not None and a == b:
            equal += 1
            a, b = next(reference, None), next(candidate, None)
        elif b is None or (a is not None and a < b):
            removed += 1
            if len(samples['reference_only']) < 3:
                samples['reference_only'].append(a.decode('utf-8', errors='replace').removesuffix('\n'))
            a = next(reference, None)
        else:
            added += 1
            if len(samples['candidate_only']) < 3:
                samples['candidate_only'].append(b.decode('utf-8', errors='replace').removesuffix('\n'))
            b = next(candidate, None)
    return {'equal_rows': equal, 'reference_only_rows': removed, 'candidate_only_rows': added,
            'equal_preserving_multiplicity': not removed and not added, 'samples': samples}


def aligned_differences(reference, candidate, name):
    changed = 0
    fields = Counter()
    samples = []
    for number, (a, b) in enumerate(itertools.zip_longest(reference, candidate), 1):
        if a == b:
            continue
        changed += 1
        old, new = (a[:-1].split(b'|') if a else []), (b[:-1].split(b'|') if b else [])
        differences = []
        for index, (x, y) in enumerate(itertools.zip_longest(old, new)):
            if x == y:
                continue
            label = FIELDS[name][index] if index < len(FIELDS[name]) else 'extra_field_' + str(index + 1)
            fields[label] += 1
            if len(samples) < 10:
                differences.append({'field': label,
                                    'reference': x.decode('utf-8', errors='replace') if x is not None else None,
                                    'candidate': y.decode('utf-8', errors='replace') if y is not None else None})
        if len(samples) < 10:
            samples.append({'line': number, 'reference_id': old[0].decode() if old else None,
                            'candidate_id': new[0].decode() if new else None, 'differences': differences})
    return {'changed_positions': changed, 'changed_fields': dict(fields), 'samples': samples}


def sort_file(path, output, scratch):
    env = dict(os.environ, LC_ALL='C')
    subprocess.run(['/usr/bin/sort', '-S', '128M', '-T', str(scratch), str(path), '-o', str(output)],
                   check=True, env=env, timeout=600)


def ordered_and_multiset(reference, candidate, scratch):
    a, b = scratch / 'reference.sorted', scratch / 'candidate.sorted'
    sort_file(reference, a, scratch)
    sort_file(candidate, b, scratch)
    with a.open('rb') as left, b.open('rb') as right:
        result = compare_sorted(iter(left), iter(right))
    result.update(reference_sorted_sha256=file_info(a)['sha256'], candidate_sorted_sha256=file_info(b)['sha256'])
    a.unlink()
    b.unlink()
    return result


def attribute_view(path, output):
    ids = set()
    invalid = duplicate = 0
    by_name = Counter()
    non_context = hashlib.sha256()
    non_context_rows = 0
    with path.open('rb') as handle, output.open('xb') as out:
        for row in handle:
            pieces = row[:-1].split(b'|')
            try:
                value = int(pieces[0])
                if value in ids:
                    duplicate += 1
                ids.add(value)
            except ValueError:
                invalid += 1
            by_name[pieces[3].decode('utf-8')] += 1
            if pieces[3] != b'CONTEXT':
                non_context.update(row)
                non_context_rows += 1
            # Retain endpoint types, qualifiers, values, flags, checksum and trailing fields.
            # Only the explicitly identified generated row ID is removed in this view.
            out.write(row.split(b'|', 1)[1])
    return {'rows': sum(by_name.values()), 'unique_ids': len(ids), 'duplicate_ids': duplicate,
            'invalid_ids': invalid, 'minimum_id': min(ids) if ids else None, 'maximum_id': max(ids) if ids else None,
            'attribute_names': dict(by_name), 'non_context_rows': non_context_rows,
            'non_context_full_record_sha256': non_context.hexdigest()}


def structure(paths, configured_root, declared_termgroups=None):
    """Small independent structural check, with explicit external root exception."""
    atoms = set()
    atom_duplicates = 0
    unknown_termgroups = Counter()
    framework_termgroups = {b'SRC/VPT', b'SRC/VAB', b'SRC/RPT', b'SRC/RAB', b'SRC/SSN'}
    allowed_termgroups = None if declared_termgroups is None else set(declared_termgroups) | framework_termgroups
    with paths['classes_atoms.src'].open('rb') as handle:
        for row in handle:
            value = row.split(b'|', 1)[0]
            if value in atoms:
                atom_duplicates += 1
            atoms.add(value)
            if allowed_termgroups is not None:
                termgroup = row.split(b'|', 3)[2]
                if termgroup not in allowed_termgroups:
                    unknown_termgroups[termgroup.decode('utf-8', errors='replace')] += 1
    allowed = atoms | {str(configured_root).encode()}
    result = {'atom_ids': {'unique': len(atoms), 'duplicates': atom_duplicates,
                          'minimum': min(map(int, atoms)), 'maximum': max(map(int, atoms))},
              'external_root_atom_id': configured_root, 'files': {}}
    result['termgroup_validation'] = {
        'enabled': allowed_termgroups is not None, 'unknown_termgroups': dict(unknown_termgroups),
        'passed': allowed_termgroups is not None and not unknown_termgroups,
        'framework_termgroups': sorted(x.decode() for x in framework_termgroups),
        'framework_evidence': 'Pinned INV/lib/QaTGs.pm:402-409'}
    for name, path in paths.items():
        widths, types, missing = Counter(), Counter(), Counter()
        bad_utf8 = bad_newline = nul = bad_digest = trailing_nonempty = rows = 0
        with path.open('rb') as handle:
            for row in handle:
                rows += 1
                bad_newline += not row.endswith(b'\n')
                nul += b'\0' in row
                try:
                    row.decode('utf-8')
                except UnicodeDecodeError:
                    bad_utf8 += 1
                pieces = row.removesuffix(b'\n').split(b'|')
                widths[len(pieces)] += 1
                if len(pieces) != len(FIELDS[name]):
                    continue
                if name != 'classes_atoms.src':
                    trailing_nonempty += pieces[-1] != b''
                endpoints = []
                if name == 'attributes.src':
                    endpoints = [(pieces[1], pieces[10])]
                    bad_digest += hashlib.md5(pieces[4]).hexdigest().encode() != pieces[13]
                elif name == 'relationships.src':
                    endpoints = [(pieces[2], pieces[12]), (pieces[5], pieces[14])]
                elif name == 'mergefacts.src':
                    endpoints = [(pieces[0], pieces[8]), (pieces[2], pieces[10])]
                elif name == 'contexts.src':
                    endpoints = [(pieces[11], pieces[12]), (pieces[14], pieces[15]),
                                 (pieces[0], b'SRC_ATOM_ID'), (pieces[3], b'SRC_ATOM_ID')]
                    endpoints += [(value, b'SRC_ATOM_ID') for value in pieces[7].split(b'.') if value]
                for value, kind in endpoints:
                    types[kind.decode('utf-8')] += 1
                    if kind == b'SRC_ATOM_ID' and value not in allowed:
                        missing[value.decode('utf-8', errors='replace')] += 1
        result['files'][name] = {'rows': rows, 'field_counts': dict(widths), 'invalid_utf8_rows': bad_utf8,
                                'missing_final_newline_rows': bad_newline, 'nul_rows': nul,
                                'nonempty_trailing_field_rows': trailing_nonempty,
                                'attribute_digest_mismatches': bad_digest, 'identifier_types': dict(types),
                                'unresolved_src_atom_references': sum(missing.values()),
                                'unresolved_reference_samples': missing.most_common(5)}
    result['checks_passed'] = atom_duplicates == 0 and not unknown_termgroups and all(
        set(item['field_counts']) == {len(FIELDS[name])} and not any(item[key] for key in
            ['invalid_utf8_rows', 'missing_final_newline_rows', 'nul_rows', 'nonempty_trailing_field_rows',
             'attribute_digest_mismatches', 'unresolved_src_atom_references'])
        for name, item in result['files'].items())
    result['scope'] = 'Structure, attribute value digests, current SRC_ATOM_ID references, optional declared/framework termgroups; not complete domain validation'
    return result


def compare(contract, progress=print, fixture_checks=()):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('This comparison is scoped to tomcata on dev')
    target = ROOT / VERSION
    receipt = json.loads((target / 'etc/replay-core.json').read_text())
    if receipt['exit_status'] != 0 or receipt['engine_ref'] != contract['engine_ref']:
        raise RuntimeError('The completed pinned core run is required')
    archive = Path(contract['reference']['archive_path'])
    if file_info(archive)['sha256'] != contract['reference']['archive_sha256']:
        raise RuntimeError('Frozen reference archive changed')
    report_path = target / 'etc/replay-comparison.json'
    if report_path.exists():
        raise RuntimeError('Comparison report already exists; preserve it before a deliberate rerun')
    expected = {PurePosixPath(item['path']).name: item for item in contract['core_outputs_to_regenerate']}
    candidate = {name: target / 'src' / name for name in expected}
    for item in receipt['comparison']:
        path = Path(item['path'])
        if path != candidate.get(path.name) or path.is_symlink() or file_info(path)['sha256'] != item['sha256']:
            raise RuntimeError('Candidate changed after inversion: ' + str(path))
    result = {'source': 'NCI', 'version': VERSION, 'engine_ref': contract['engine_ref'],
              'run_id': contract.get('run_id'),
              'reference_stage': 'inversion-src', 'archive_sha256': contract['reference']['archive_sha256'],
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'core_exit_status': receipt['exit_status'], 'files': {}, 'other_reference_src': [],
              'fixture_checks': list(fixture_checks),
              'candidate_modified': False, 'insert_in_scope': False}
    scratch = Path(tempfile.mkdtemp(prefix='replay-comparison-', dir=str(target / 'tmp')))
    try:
        reference = {}
        progress('PHASE: reading frozen official src reference only', flush=True)
        with tarfile.open(archive, 'r|gz') as tar:
            for member in tar:
                if not member.name.startswith(VERSION + '/src/') or not member.name.endswith('.src'):
                    continue
                name = PurePosixPath(member.name).name
                if name not in expected:
                    if not member.isfile():
                        raise RuntimeError('Reference src entry is not a regular file')
                    digest = hashlib.sha256()
                    rows = 0
                    source = tar.extractfile(member)
                    for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
                        digest.update(block)
                        rows += block.count(b'\n')
                    other = {'file': name, 'reference_bytes': member.size, 'reference_sha256': digest.hexdigest(),
                             'reference_rows': rows, 'candidate_present': (target / 'src' / name).is_file(),
                             'role': 'declared-metadata-input' if name in ('sources.src', 'termgroups.src') else 'excluded-stage-artifact'}
                    if other['candidate_present']:
                        other['candidate'] = file_info(target / 'src' / name)
                        other['exact_match'] = other['candidate']['sha256'] == other['reference_sha256']
                    result['other_reference_src'].append(other)
                    continue
                if not member.isfile():
                    raise RuntimeError('Reference member must be a regular file')
                path = scratch / name
                with path.open('xb') as handle:
                    shutil.copyfileobj(tar.extractfile(member), handle)
                actual = file_info(path)
                if actual['sha256'] != expected[name]['sha256']:
                    raise RuntimeError('Archived member changed: ' + name)
                reference[name] = path
                observed = file_info(candidate[name])
                result['files'][name] = {'reference': actual, 'candidate': observed,
                                        'exact_match': actual['sha256'] == observed['sha256']}
        if set(reference) != set(expected):
            raise RuntimeError('Incomplete official core reference')
        progress('PHASE: locating atom field differences', flush=True)
        with reference['classes_atoms.src'].open('rb') as a, candidate['classes_atoms.src'].open('rb') as b:
            result['files']['classes_atoms.src']['aligned_differences'] = aligned_differences(a, b, 'classes_atoms.src')
        progress('PHASE: comparing context multisets without changing fields or duplicate counts', flush=True)
        result['files']['contexts.src']['row_multiset'] = ordered_and_multiset(reference['contexts.src'], candidate['contexts.src'], scratch)
        progress('PHASE: comparing attribute content with explicit generated-row-ID scope', flush=True)
        a, b = scratch / 'attributes.reference.content', scratch / 'attributes.candidate.content'
        attributes = result['files']['attributes.src']
        attributes['row_multiset'] = ordered_and_multiset(reference['attributes.src'], candidate['attributes.src'], scratch)
        attributes['reference_id_view'] = attribute_view(reference['attributes.src'], a)
        attributes['candidate_id_view'] = attribute_view(candidate['attributes.src'], b)
        attributes['content_multiset_excluding_generated_attribute_id'] = ordered_and_multiset(a, b, scratch)
        attributes['excluded_field'] = 'source_attribute_id (column 1) only; raw mismatch retained'
        progress('PHASE: validating field shapes, attribute digests and typed atom references', flush=True)
        config = (target / 'etc/nci.cfg').read_text()
        roots = [line.split('=', 1)[1].strip() for line in config.splitlines() if line.startswith('HC.RootNodeSaid =')]
        if len(roots) != 1:
            raise RuntimeError('An explicit configured external hierarchy root is required')
        termgroups = {row.split(b'|', 1)[0] for row in (target / 'src/termgroups.src').read_bytes().splitlines()}
        result['structure'] = {'reference': structure(reference, int(roots[0]), termgroups),
                               'candidate': structure(candidate, int(roots[0]), termgroups)}
        result['status'] = ('exact-match' if all(item['exact_match'] for item in result['files'].values())
                            else 'differences-characterized; review-required')
        result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report_path.write_text(json.dumps(result, indent=2) + '\n')
        return result
    finally:
        shutil.rmtree(scratch)
