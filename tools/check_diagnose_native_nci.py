#!/usr/bin/env python3
"""Real temporary archives/files; mocked dev/job admission, no server calls."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tarfile
from unittest.mock import patch

import check_execute_release_nci as source
import diagnose_native_nci as diagnose


def _attribute(identity, kind, value, version):
    return ('|'.join([str(identity), '10000', 'C', kind, value, version, 'R', 'Y', 'N', 'N', 'SRC_ATOM_ID', '', '',
                     hashlib.md5(value.encode()).hexdigest(), '']) + '\n').encode()


@contextmanager
def fixture(change=None, version='NCI_2026_08E', state='complete', duplicate_member=False, missing_member=False):
    with tempfile.TemporaryDirectory(prefix='check-nci-output-diagnostic-') as directory:
        root = Path(directory).resolve();target = root / 'sources' / version;target.mkdir(parents=True)
        args = source.fixture(version, 'NCI_2026_07D' if version == 'NCI_2026_08E' else 'NCI_2026_12C')
        plan = source.execute.build_plan(args[0]['configuration'], args[0]['artifacts'], args[1])
        source.stage(plan, args[2], target);source.outputs(plan, target)
        rows = {name: (target / name).read_bytes() for name in diagnose.OUTPUTS}
        rows['src/attributes.src'] = _attribute(1, 'DEFINITION', 'Alpha', version) + _attribute(2, 'CONTEXT', 'First', version) + _attribute(3, 'CONTEXT', 'Second', version)
        first = rows['src/contexts.src'];rows['src/contexts.src'] += first.replace(b'|isa|', b'|part_of|')
        reference = copy.deepcopy(rows)
        if change:change(rows, reference)
        for name, raw in rows.items():(target / name).write_bytes(raw)
        archive = root / 'sources' / (version + '.tgz')
        with tarfile.open(archive, mode='w:gz') as out:
            for name, raw in reference.items():
                if missing_member and name == 'src/mergefacts.src':continue
                member = tarfile.TarInfo(version + '/' + name);member.size = len(raw);out.addfile(member, io.BytesIO(raw))
                if duplicate_member and name == 'src/classes_atoms.src':out.addfile(member, io.BytesIO(raw))
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        artifacts = {'official': {'artifact_type': 'reference-inversion', 'source': 'NCI', 'version': version,
            'data': {'reference_stage': 'inversion-src'}, 'files': [{'role': name, 'uri': archive.as_uri(), 'archive_format': 'tar.gz',
                'archive_member': version + '/' + name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                'archive_sha256': checksum, 'archive_bytes': archive.stat().st_size} for name, raw in reference.items()]}}
        config = {'replay': {'reference_ref': 'official'}}
        lock = {'schema_version': 1, 'artifact_type': 'ncimeta-native-release-lock', 'run_id': 'synthetic-diagnostic',
                'request': {'source': 'NCI', 'version': version}, 'configuration': config,
                'manifest': {'artifacts': artifacts}, 'plan': {'validation': {'state_files': plan['validation']['state_files']}}}
        lock['lock_sha256'] = diagnose.manifests.digest(lock)
        run = root / 'qa/replay-requests' / lock['run_id'];run.mkdir(parents=True)
        (run / 'case.lock.json').write_text(json.dumps(lock))
        status = {'source': 'NCI', 'version': version, 'run_id': lock['run_id'], 'lock_sha256': lock['lock_sha256'], 'status': state}
        (run / 'status.json').write_text(json.dumps(status))
        if state == 'complete':
            result = {**{key: status[key] for key in ('source', 'version', 'run_id', 'lock_sha256')},
                'comparison': {'files': {name: {'candidate': {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}} for name, raw in rows.items()}}}
            (run / 'result.json').write_text(json.dumps(result))
        (root / '.replay-runtime.lock').touch()
        with patch.object(diagnose, 'ROOT', root), patch.object(diagnose, 'guard'), patch.object(diagnose.worker, 'ROOT', root), \
             patch.object(diagnose.worker, 'verify_lock', return_value=target), patch.object(diagnose.worker.legacy, 'idle'), patch.object(diagnose.worker.legacy, 'runtime'):
            yield lock, target, archive, root


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def run(args):return diagnose.diagnose(*args[:3])
    def reject(label, args):
        try:run(args)
        except (ValueError, RuntimeError, OSError, tarfile.TarError):checks.append(label)
        else:raise AssertionError(label)
    with fixture() as args:
        before = {str(path): path.read_bytes() for path in args[3].rglob('*') if path.is_file()}
        report = run(args)
        good(report['status'] == 'DIAGNOSTIC_ONLY' and not report['acceptance_authorized'] and not report['production_eligible'], 'Even identical outputs confer no conversion or production acceptance')
        good(all(row['ordered_bytes_equal'] for row in report['files'].values()), 'Raw ordered hash/size equality is retained for all five files')
        good(all(row['full_row_multiset']['equal_preserving_all_row_bytes_and_multiplicity'] for row in report['files'].values()), 'All full rows/fields and duplicate counts compare independently')
        good(report['terminal_result_bound'] and report['native_job_status'] == 'complete', 'Diagnostic binds exact terminal native job and result output hashes')
        good(not report['reference_tree_extracted'] and before == {str(path): path.read_bytes() for path in args[3].rglob('*') if path.is_file()}, 'No source, control record, archive or extracted reference copy is written')
        good(report == run(args), 'Repeated immutable files produce the same complete report')
    imported=subprocess.run([sys.executable,'-S','-c','import sys;sys.path.insert(0,sys.argv[1]);import diagnose_native_nci',str(Path(__file__).resolve().parent)],capture_output=True,text=True)
    good(imported.returncode==0, 'Frozen runtime diagnostic imports without third-party packages')
    binary=b'bad\xff|row\n';delta=diagnose._counter({binary:2})
    good(delta['samples']['candidate_only'][0]['row']['encoding']=='base64' and delta['candidate_only_rows']==2,
         'Invalid UTF-8 full rows retain exact bytes through lossless base64 samples and multiplicity')
    large=diagnose._counter({b'x'*(diagnose.SAMPLE_BYTES+1)+b'\n':1})
    good(large['candidate_only_rows']==1 and not large['samples']['candidate_only'] and large['oversize_full_row_samples_omitted']==1,
         'Oversize rows remain fully compared but are explicitly omitted rather than truncated in bounded samples')
    def one_termgroup(rows, ref):rows['src/classes_atoms.src'] = rows['src/classes_atoms.src'].replace(b'/PT|', b'/SY|', 1)
    with fixture(one_termgroup) as args:
        report = run(args);atoms = report['files']['src/classes_atoms.src']
        good(atoms['aligned_field_differences']['changed_fields'] == {'termgroup': 1} and atoms['aligned_field_differences']['changed_positions'] == 1, 'A single changed TG is isolated by full-field alignment with identical SAID order')
        good(atoms['candidate']['missing_termgroup_definitions'][0]['rows'] == 1 and not atoms['reference']['missing_termgroup_definitions'], 'Missing candidate TG metadata is recorded and never waived')
        sample = atoms['full_row_multiset']['samples']['candidate_only'][0]
        good(sample['row']['value'].endswith('\n') and len(sample['row']['value'].split('|')) == 15, 'Full row sample retains all columns and final record terminator')
    def permutation(rows, ref):rows['src/contexts.src'] = b''.join(reversed(rows['src/contexts.src'].splitlines(keepends=True)))
    with fixture(permutation) as args:
        contexts = run(args)['files']['src/contexts.src']
        good(not contexts['ordered_bytes_equal'] and contexts['full_row_multiset']['equal_preserving_all_row_bytes_and_multiplicity'], 'Context row permutation is distinguished from content change without dropping any field')
    def context_content(rows, ref):rows['src/contexts.src'] = rows['src/contexts.src'].replace(b'|isa|', b'|different|')
    with fixture(context_content) as args:
        good(not run(args)['files']['src/contexts.src']['full_row_multiset']['equal_preserving_all_row_bytes_and_multiplicity'], 'Changed context relationship field remains a content difference')
    def duplicate_context(rows, ref):rows['src/contexts.src'] += rows['src/contexts.src'].splitlines(keepends=True)[0]
    with fixture(duplicate_context) as args:
        good(run(args)['files']['src/contexts.src']['full_row_multiset']['candidate_only_rows'] == 1, 'Duplicate context rows cannot disappear through set comparison')
    def context_id_assignment(rows, ref):
        lines=rows['src/attributes.src'].splitlines(keepends=True)
        rows['src/attributes.src'] = lines[0] + lines[2].replace(b'3|', b'2|', 1) + lines[1].replace(b'2|', b'3|', 1)
    with fixture(context_id_assignment) as args:
        attributes = run(args)['files']['src/attributes.src'];views = attributes['attribute_views']
        good(not attributes['ordered_bytes_equal'] and views['all_rows_dropping_only_generated_id']['equal_preserving_all_row_bytes_and_multiplicity'], 'Attribute generated-ID reassignment is a separate exact-rest-of-row diagnostic')
        good(views['positive_unique_ids_and_digests_valid_on_both_sides'] and views['same_generated_identifier_set'] and views['non_context_full_rows_ordered_equal'], 'Attribute ID view explicitly validates both sets and exact full non-CONTEXT records')
    def duplicate_attribute_id(rows, ref):rows['src/attributes.src'] = rows['src/attributes.src'].replace(b'3|10000|', b'2|10000|')
    with fixture(duplicate_attribute_id) as args:
        attributes = run(args)['files']['src/attributes.src']
        good(attributes['attribute_views']['all_rows_dropping_only_generated_id']['equal_preserving_all_row_bytes_and_multiplicity'] and not attributes['attribute_views']['positive_unique_ids_and_digests_valid_on_both_sides'], 'Duplicate IDs invalidate the ID view even when every remaining byte is identical')
    def digest_corrupt(rows, ref):rows['src/attributes.src'] = rows['src/attributes.src'].replace(b'|Alpha|', b'|Changed|')
    with fixture(digest_corrupt) as args:
        good(run(args)['files']['src/attributes.src']['candidate']['attribute_digest_mismatches'] == 1, 'Changed attribute value with stale digest is detected')
    def zero_id(rows, ref):rows['src/attributes.src'] = b'0|' + rows['src/attributes.src'].split(b'|', 1)[1]
    with fixture(zero_id) as args:good(run(args)['files']['src/attributes.src']['candidate']['identifiers']['invalid'] == 1, 'Zero generated attribute ID is invalid')
    def oversized_id(rows, ref):rows['src/attributes.src'] = b'9'*5000+b'|'+rows['src/attributes.src'].split(b'|',1)[1]
    with fixture(oversized_id) as args:good(run(args)['files']['src/attributes.src']['candidate']['identifiers']['invalid']==1,
        'Pathological identifier length is recorded as invalid without losing the full-row diagnostic')
    with fixture(version='NCI_2027_02B') as args:good(run(args)['version'] == 'NCI_2027_02B', 'The same diagnostic accepts another release without a historical case/version constant')
    with fixture(state='converting') as args:reject('Active native job cannot be diagnosed as terminal', args)
    with fixture(state='failed') as args:good(not run(args)['terminal_result_bound'], 'Terminal failed output may be diagnosed without a completed-conversion claim')
    with fixture(duplicate_member=True) as args:reject('Duplicate selected oracle member is rejected', args)
    with fixture(missing_member=True) as args:reject('Missing declared oracle output is rejected', args)
    with fixture() as args:
        member=args[0]['manifest']['artifacts']['official']['files'][0];member['sha256']='a'*64
        (args[3]/'qa/replay-requests'/args[0]['run_id']/'case.lock.json').write_text(json.dumps(args[0]))
        reject('Corrupt selected-member hash binding is rejected', args)
    with fixture() as args:
        with args[2].open('ab') as out:out.write(b'changed')
        reject('Changed complete compressed archive hash/size is rejected', args)
    with fixture() as args:
        path=args[1]/'src/classes_atoms.src';path.write_bytes(path.read_bytes().replace(b'Alpha',b'Other'))
        reject('Candidate changed after terminal result is rejected', args)
    with fixture() as args:
        original=diagnose._compare
        def mutate(name, path, stream, groups):
            value=original(name,path,stream,groups)
            if name=='classes_atoms.src':path.write_bytes(path.read_bytes()+b'\n')
            return value
        with patch.object(diagnose,'_compare',side_effect=mutate):reject('Concurrent candidate mutation invalidates before/after snapshot', args)
    with fixture() as args:
        tg=args[1]/'src/termgroups.src';tg.write_bytes(tg.read_bytes()+b'unknown\n')
        reject('Modified metadata cannot hide an undeclared candidate TG', args)
    with fixture() as args:
        import fcntl
        with (args[3]/'.replay-runtime.lock').open('a') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            reject('Global runtime lock excludes an overlapping native operation', args)
    return checks


if __name__ == '__main__':
    values=check();print(json.dumps({'status':'PASS','checks':len(values),'scope':'synthetic diagnostics; no native/server execution'}))
