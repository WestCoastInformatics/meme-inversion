#!/usr/bin/env python3
"""Read-only NCIt output diagnostics; no conversion acceptance or corrections.

Every full row/field and duplicate count remains part of the raw comparison.
The attribute-ID view is separate and drops column zero only. No reference
tree, sorted copy or candidate rewrite is created.
"""
import argparse
import base64
from collections import Counter
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import socket
import stat
import tarfile

import compare_nci_core
import release_worker as worker
import release_manifest as manifests
from replay_process import runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
OUTPUTS = tuple('src/' + name for name in compare_nci_core.FIELDS)
FRAMEWORK = {b'SRC/VPT', b'SRC/VAB', b'SRC/RPT', b'SRC/RAB', b'SRC/SSN'}
SAMPLE_COUNT = 5
SAMPLE_BYTES = 16384


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Native NCIt diagnosis requires tomcata on dev')
    for path in (ROOT, ROOT / 'sources', ROOT / 'qa/replay-requests'):
        if path.resolve() != path or not path.is_dir():raise ValueError('Unexpected standard diagnostic root')


def _regular(path):
    if path.resolve() != path or not path.is_file() or path.is_symlink():
        raise ValueError('Expected an unlinked regular diagnostic input: ' + str(path))
    return path


def _stamp(path):
    item = _regular(path).lstat()
    return [item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns, stat.S_IMODE(item.st_mode)]


def _encoded(raw):
    try:return {'encoding': 'utf-8', 'value': raw.decode('utf-8')}
    except UnicodeError:return {'encoding': 'base64', 'value': base64.b64encode(raw).decode()}


def _counter(delta):
    samples = {'reference_only': [], 'candidate_only': []};omitted = 0
    for row, count in sorted(delta.items()):
        if not count:continue
        side = 'candidate_only' if count > 0 else 'reference_only'
        if len(samples[side]) >= SAMPLE_COUNT:continue
        if len(row) > SAMPLE_BYTES:
            omitted += 1;continue
        samples[side].append({'row': _encoded(row), 'multiplicity': abs(count), 'bytes': len(row), 'sha256': hashlib.sha256(row).hexdigest()})
    removed = sum(-value for value in delta.values() if value < 0)
    added = sum(value for value in delta.values() if value > 0)
    return {'equal_preserving_all_row_bytes_and_multiplicity': not removed and not added,
            'reference_only_rows': removed, 'candidate_only_rows': added,
            'samples': samples, 'oversize_full_row_samples_omitted': omitted,
            'sample_limits': {'per_side': SAMPLE_COUNT, 'full_row_bytes': SAMPLE_BYTES}}


def _subtract(counter, row):
    value = counter.get(row, 0) - 1
    if value:counter[row] = value
    elif row in counter:del counter[row]


class _Stats:
    def __init__(self, name, termgroups):
        self.name = name;self.termgroups = termgroups
        self.hash = hashlib.sha256();self.rows = self.bytes = self.bad_utf8 = self.bad_newline = self.nuls = 0
        self.widths = Counter();self.ids = set();self.bad_ids = self.duplicate_ids = self.bad_digest = 0
        self.id_sequence = hashlib.sha256();self.unknown = Counter()
        self.noncontext_hash = hashlib.sha256();self.noncontext_rows = self.noncontext_bytes = 0

    def observe(self, raw):
        self.hash.update(raw);self.rows += 1;self.bytes += len(raw)
        self.bad_newline += not raw.endswith(b'\n');self.nuls += b'\0' in raw
        try:raw.decode('utf-8')
        except UnicodeError:self.bad_utf8 += 1
        fields = raw.removesuffix(b'\n').split(b'|');self.widths[len(fields)] += 1
        if self.name in ('classes_atoms.src', 'attributes.src'):
            key = fields[0];self.id_sequence.update(key + b'\0')
            if len(key) > 128 or not re.fullmatch(rb'[1-9][0-9]*', key):self.bad_ids += 1
            else:
                value = int(key);self.duplicate_ids += value in self.ids;self.ids.add(value)
        if self.name == 'classes_atoms.src' and len(fields) >= 3 and fields[2] not in self.termgroups:
            self.unknown[fields[2]] += 1
        if self.name == 'attributes.src':
            if len(fields) != 15:self.bad_digest += 1
            elif hashlib.md5(fields[4], usedforsecurity=False).hexdigest().encode() != fields[13]:self.bad_digest += 1
            if len(fields) < 4 or fields[3] != b'CONTEXT':
                self.noncontext_hash.update(raw);self.noncontext_rows += 1;self.noncontext_bytes += len(raw)
        return fields

    def summary(self):
        result = {'sha256': self.hash.hexdigest(), 'bytes': self.bytes, 'rows': self.rows,
                  'field_counts': dict(self.widths), 'invalid_utf8_rows': self.bad_utf8,
                  'missing_final_newline_rows': self.bad_newline, 'nul_rows': self.nuls}
        if self.name in ('classes_atoms.src', 'attributes.src'):
            id_hash = hashlib.sha256()
            for value in sorted(self.ids):id_hash.update(str(value).encode() + b'\n')
            result['identifiers'] = {'invalid': self.bad_ids, 'duplicates': self.duplicate_ids, 'unique': len(self.ids),
                'minimum': min(self.ids) if self.ids else None, 'maximum': max(self.ids) if self.ids else None,
                'set_sha256': id_hash.hexdigest(), 'ordered_sha256': self.id_sequence.hexdigest()}
        if self.name == 'attributes.src':
            result.update(attribute_digest_mismatches=self.bad_digest,
                non_context_full_records={'sha256': self.noncontext_hash.hexdigest(), 'bytes': self.noncontext_bytes, 'rows': self.noncontext_rows})
        if self.name == 'classes_atoms.src':
            result['missing_termgroup_definitions'] = [{'termgroup': _encoded(key), 'rows': count} for key, count in sorted(self.unknown.items())]
        return result


def _same_identity_order(left, right):
    a, b = left['identifiers'], right['identifiers']
    return left['rows'] == right['rows'] and a['ordered_sha256'] == b['ordered_sha256'] and not any(a[key] or b[key] for key in ('invalid', 'duplicates'))


def _compare(name, candidate, reference, termgroups):
    full = Counter();attribute_ids = Counter();noncontext = Counter()
    left = _Stats(name, termgroups);right = _Stats(name, termgroups)
    with candidate.open('rb') as incoming:
        for raw in incoming:
            fields = left.observe(raw);full[raw] += 1
            if name == 'attributes.src':
                attribute_ids[raw.split(b'|', 1)[1] if b'|' in raw else raw] += 1
                if len(fields) < 4 or fields[3] != b'CONTEXT':noncontext[raw] += 1
    changes = Counter();changed = 0;samples = [];aligned = None
    if name == 'classes_atoms.src':aligned = candidate.open('rb')
    try:
        for number, raw in enumerate(reference, 1):
            fields = right.observe(raw);_subtract(full, raw)
            if name == 'attributes.src':
                _subtract(attribute_ids, raw.split(b'|', 1)[1] if b'|' in raw else raw)
                if len(fields) < 4 or fields[3] != b'CONTEXT':_subtract(noncontext, raw)
            if aligned is not None:
                fresh = next(aligned, None)
                if fresh != raw:
                    changed += 1;different = []
                    current = fresh.removesuffix(b'\n').split(b'|') if fresh is not None else []
                    for index, (old, new) in enumerate(itertools.zip_longest(fields, current)):
                        if old == new:continue
                        label = compare_nci_core.FIELDS[name][index] if index < len(compare_nci_core.FIELDS[name]) else 'extra_field_' + str(index + 1)
                        changes[label] += 1
                        different.append({'field': label, 'reference': None if old is None else _encoded(old), 'candidate': None if new is None else _encoded(new)})
                    if len(samples) < SAMPLE_COUNT and len(raw) + (len(fresh) if fresh else 0) <= SAMPLE_BYTES:
                        samples.append({'line': number, 'source_atom_id': _encoded(fields[0]), 'differences': different,
                                        'reference_full_row': _encoded(raw), 'candidate_full_row': None if fresh is None else _encoded(fresh)})
    finally:
        if aligned is not None:aligned.close()
    a, b = left.summary(), right.summary()
    result = {'candidate': a, 'reference': b, 'ordered_bytes_equal': (a['sha256'], a['bytes']) == (b['sha256'], b['bytes']),
              'full_row_multiset': _counter(full)}
    if name == 'classes_atoms.src':
        eligible = _same_identity_order(a, b)
        result['aligned_field_differences'] = {'same_positive_unique_said_order': eligible,
            'changed_positions': changed if eligible else None, 'changed_fields': dict(changes) if eligible else None,
            'samples': samples if eligible else [], 'scope': 'Field alignment is reported only for identical valid SAID order and row count'}
    if name == 'attributes.src':
        normalized = _counter(attribute_ids)
        valid = all(not stats[key] for stats in (a, b) for key in ('attribute_digest_mismatches', 'invalid_utf8_rows', 'missing_final_newline_rows', 'nul_rows'))
        valid = valid and all(not stats['identifiers'][key] for stats in (a, b) for key in ('invalid', 'duplicates')) and all(set(stats['field_counts']) == {15} for stats in (a, b))
        result['attribute_views'] = {'non_context_full_rows': _counter(noncontext),
            'non_context_full_rows_ordered_equal': a['non_context_full_records'] == b['non_context_full_records'],
            'all_rows_dropping_only_generated_id': normalized, 'dropped_field': 'source_attribute_id (column0) only',
            'positive_unique_ids_and_digests_valid_on_both_sides': valid,
            'same_generated_identifier_set': a['identifiers']['set_sha256'] == b['identifiers']['set_sha256'],
            'scope': 'Separate diagnostic view; every other byte/field and duplicate count is retained; no acceptance follows'}
    return result


class _HashReader:
    def __init__(self, raw):self.raw = raw;self.sha = hashlib.sha256();self.bytes = 0
    def read(self, size=-1):
        data = self.raw.read(size);self.sha.update(data);self.bytes += len(data);return data
    def finish(self):
        while self.read(4 * 1024 * 1024):pass
        return self.sha.hexdigest(), self.bytes


def diagnose(lock, target, archive, progress=lambda text: None):
    guard();target = Path(target);archive = Path(archive)
    with runtime_lock(ROOT):
        worker.legacy.idle()
        if worker.verify_lock(lock) != target or lock['request']['source'] != 'NCI':raise ValueError('Diagnostic target differs from verified NCIt native lock')
        version = lock['request']['version'];run = ROOT / 'qa/replay-requests' / lock['run_id']
        if target != ROOT / 'sources' / version or archive != ROOT / 'sources' / (version + '.tgz'):
            raise ValueError('Exact standard current candidate and archive paths are required')
        if manifests.digest(lock) != manifests.digest(manifests.load(_regular(run / 'case.lock.json'))):raise ValueError('Terminal run uses another native lock')
        state_path = _regular(run / 'status.json');state = manifests.load(state_path)
        if state.get('status') not in ('complete', 'failed') or any(state.get(key) != lock['request'][key] for key in ('source', 'version')) or state.get('run_id') != lock['run_id'] or state.get('lock_sha256') != lock['lock_sha256']:
            raise ValueError('One terminal native job with matching source/version/lock is required')
        worker.legacy.runtime(lock)
        reference = lock['manifest']['artifacts'][lock['configuration']['replay']['reference_ref']]
        if (reference['artifact_type'], reference['source'], reference['version'], reference['data']['reference_stage']) != ('reference-inversion', 'NCI', version, 'inversion-src'):
            raise ValueError('Current-release inversion-stage oracle required')
        descriptors = {row['role']: row for row in reference['files']}
        if len(reference['files']) != 5 or set(descriptors) != set(OUTPUTS):raise ValueError('Five distinct complete current oracle outputs are required')
        expected_archive = {(row['archive_sha256'], row['archive_bytes']) for row in descriptors.values()}
        if len(expected_archive) != 1:raise ValueError('Oracle outputs must bind one immutable archive')
        members = {}
        for role, row in descriptors.items():
            if row['archive_format'] != 'tar.gz' or worker._local(row) != archive:raise ValueError('Oracle descriptor selects another archive')
            name = row['archive_member']
            if name != version + '/' + role:
                proof = reference['data'].get('attribute_stage_proof')
                if role != 'src/attributes.src' or name != version + '/src/attributes.orig' or not proof or proof.get('original_member') != name or proof.get('original_sha256') != row['sha256'] or proof.get('archive_sha256') != row['archive_sha256']:
                    raise ValueError('Oracle member is outside the declared current inversion stage')
            if name in members:raise ValueError('Duplicate selected oracle member')
            members[name] = role
        candidate_paths = {role: _regular(target / role) for role in OUTPUTS}
        tg_path = _regular(target / 'src/termgroups.src')
        expected_tg = lock['plan']['validation']['state_files']['src/termgroups.src']
        if worker.legacy.sha(tg_path) != expected_tg['sha256']:raise ValueError('Preserved candidate termgroups changed')
        termgroups = {raw.split(b'|', 1)[0] for raw in tg_path.read_bytes().splitlines()} | FRAMEWORK
        observed = [archive, state_path, run / 'case.lock.json', tg_path] + list(candidate_paths.values())
        result_path = run / 'result.json';completed = None
        if result_path.exists():
            _regular(result_path);completed = manifests.load(result_path);observed.append(result_path)
            if any(completed.get(key) != state.get(key) for key in ('source', 'version', 'run_id', 'lock_sha256')):raise ValueError('Completed result belongs to another native job')
        elif state['status'] == 'complete':raise ValueError('Terminal completed native job lacks its immutable result')
        before = {str(path): _stamp(path) for path in observed}
        files = {};seen = set()
        with archive.open('rb') as incoming:
            hashed = _HashReader(incoming)
            with tarfile.open(fileobj=hashed, mode='r|gz') as archive_stream:
                for member in archive_stream:
                    name = member.name.removeprefix('./').rstrip('/')
                    if name not in members:continue
                    if name in seen or not member.isfile():raise ValueError('Selected oracle member is duplicate or not regular')
                    seen.add(name);role = members[name];descriptor = descriptors[role]
                    if member.size != descriptor['bytes']:raise ValueError('Selected oracle member size differs')
                    progress('Comparing full rows: ' + role)
                    with archive_stream.extractfile(member) as stream:
                        files[role] = _compare(PurePosixPath(role).name, candidate_paths[role], stream, termgroups)
                    actual = files[role]['reference']
                    if (actual['sha256'], actual['bytes']) != (descriptor['sha256'], descriptor['bytes']):raise ValueError('Selected oracle member hash/size differs')
            container = hashed.finish()
        if seen != set(members) or container not in expected_archive:raise ValueError('Complete archive bytes or selected-member inventory differs')
        if completed is not None:
            for role, row in files.items():
                frozen = completed['comparison']['files'][role]['candidate']
                if any(row['candidate'][key] != frozen[key] for key in ('sha256', 'bytes')):raise ValueError('Candidate changed after terminal native result: ' + role)
        if before != {str(path): _stamp(path) for path in observed}:raise ValueError('Diagnostic inputs changed while comparing')
        worker.legacy.runtime(lock)
        return {'schema_version': 1, 'artifact_type': 'ncimeta-native-nci-diagnostic', 'status': 'DIAGNOSTIC_ONLY',
                'source': 'NCI', 'version': version, 'run_id': lock['run_id'], 'lock_sha256': lock['lock_sha256'],
                'native_job_status': state['status'], 'terminal_result_bound': completed is not None,
                'archive_sha256': container[0], 'archive_bytes': container[1], 'files': files,
                'candidate_before_after_stamps': before, 'candidate_changed': False, 'reference_tree_extracted': False,
                'acceptance_authorized': False, 'production_eligible': False, 'correction_waiver_applied': False,
                'scope': 'Raw bytes, all full-row fields and multiplicity; separate attribute-ID diagnostic view only. Independent source validation and official acceptance remain separate.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('lock', 'target', 'archive', 'output'):parser.add_argument('--' + name, required=True)
    args = parser.parse_args();lock = manifests.load(args.lock)
    destination = Path(args.output)
    if destination.parent != ROOT / 'qa/replay-requests' / lock['run_id'] or destination.exists() or destination.is_symlink():raise ValueError('Diagnostic output must be a new file in its terminal run control directory')
    report = diagnose(lock, args.target, args.archive, progress=lambda value: print(value, flush=True))
    manifests.write_new(destination, report)
    print(json.dumps({'output': str(destination), 'status': report['status'], 'acceptance_authorized': False}))
