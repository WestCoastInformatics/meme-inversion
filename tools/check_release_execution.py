#!/usr/bin/env python3
"""Confined native admission/lifecycle tests; no server or full inversion."""
import base64
import copy
from contextlib import contextmanager, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import archive_retained_source as storage
import check_execute_release_nci as nci_fixture
import execute_release_nci as nci
import inversion_remote as remote
import inversion_worker as legacy
import prepare_snomed_candidate
import release_execution as admission
import release_manifest as manifests
import release_worker as worker
import replay_retention as retention


@contextmanager
def fixture(version='NCI_2026_10D', prior='NCI_2026_08E'):
    with tempfile.TemporaryDirectory(prefix='native-release-lifecycle-') as directory:
        meme = Path(directory).resolve();root = meme / 'inv'
        (root / 'sources').mkdir(parents=True);(root / 'qa/replay-requests').mkdir(parents=True)
        manifest, code, raw = nci_fixture.fixture(version, prior)
        cache = root / 'native-inputs';cache.mkdir()
        for artifact in manifest['artifacts'].values():
            # This confined fixture constructs a unit-test capsule. The public
            # resolver still rejects synthetic evidence and requires committed code.
            artifact['provenance']['evidence_kind'] = 'preserved'
            for file in artifact['files']:
                path = cache / Path(file['uri']).name;path.write_bytes(raw[file['role']]);file['uri'] = path.as_uri()
        plan = nci.build_plan(manifest['configuration'], manifest['artifacts'], code)
        gold = meme / 'fixture-oracle';(gold / 'src').mkdir(parents=True)
        nci_fixture.outputs(plan, gold)
        reference = copy.deepcopy(manifest['artifacts']['state'])
        reference.update(artifact_type='reference-inversion', data={'reference_stage': 'inversion-src'}, files=[])
        for name in plan['output_files']:
            path = gold / name
            reference['files'].append({'role': name, 'uri': path.as_uri(), 'sha256': legacy.sha(path), 'bytes': path.stat().st_size})
        manifest['artifacts']['official'] = reference
        manifest['purpose'] = 'historical-replay'
        manifest['configuration']['replay'] = {'reference_ref': 'official', 'reference_stage': 'inversion-src', 'comparison_profile': 'exact'}
        for row in code:row.update(kind='file', bytes=len(base64.b64decode(row['data_b64'])), repository_path='engines/nci/' + row['relative_path'])
        runtime = [admission.file_record(b'fixture', 'INV/fixture-' + str(i)) for i in range(169)]
        for row in runtime:row.update(kind='file', repository_path=row['relative_path'])
        profile = {'handler': 'execute_release_nci', 'engine_package': 'engines/nci',
                   'runtime_ref': '1' * 40, 'minimum_free_disk_gib': 18, 'pull_helper_sha256': '3' * 64,
                   'runtime_inventory_sha256': manifests.digest([{k: v for k, v in row.items() if k != 'data_b64'} for row in runtime]),
                   'reviewed_package_sha256': [manifests.digest([{k: v for k, v in row.items() if k != 'data_b64'} for row in code])]}
        registry = json.dumps({'schema_version': 1, 'profiles': {manifest['profile']: profile}}).encode()
        module = Path(nci.__file__).read_bytes()
        lock = {'schema_version': 1, 'artifact_type': 'ncimeta-native-release-lock', 'run_id': 'native-unit-run',
                'manifest': manifest, 'configuration': manifest['configuration'],
                'request': {k: manifest['configuration'][k] for k in ('source', 'version', 'engine_ref')},
                'manifest_sha256': manifests.digest(manifest), 'source_profile': manifest['profile'],
                'profile': profile, 'profile_sha256': manifests.digest(profile),
                'profiles_registry_b64': base64.b64encode(registry).decode(),
                'plan': plan, 'plan_sha256': manifests.digest(plan), 'code_files': code, 'runtime_files': runtime,
                'runtime_ref': profile['runtime_ref'], 'apparatus_ref': '2' * 40,
                'modules_b64': {'execute_release_nci.py': base64.b64encode(module).decode(), 'replay_retention.py': ''},
                'provenance': [{'repository_path': 'tools/execute_release_nci.py', 'sha256': manifests.hashlib.sha256(module).hexdigest()},
                               {'repository_path': 'tools/replay_retention.py', 'sha256': manifests.hashlib.sha256(b'').hexdigest()}],
                'execution_enabled': True, 'production_eligible': False, 'insertion_executed': False}
        lock['provenance'].append({'repository_path': 'docs/inversion-review/native-execution-profiles.json', 'sha256': manifests.hashlib.sha256(registry).hexdigest()})
        seal(lock)
        run = root / 'qa/replay-requests' / lock['run_id'];run.mkdir()
        path = run / 'case.lock.json';path.write_text(json.dumps(lock))
        def local_publish(source, destination):
            # macOS lacks Linux renameat2; this confined single-thread fixture
            # substitutes only that platform primitive, never the server helper.
            if Path(destination).exists():raise FileExistsError(destination)
            Path(source).rename(destination)
        with patch.object(worker, 'ROOT', root), patch.object(worker, 'CONTROL', root / 'qa/replay-requests'), \
                patch.object(legacy, 'ROOT', root), patch.object(legacy, 'CONTROL', root / 'qa/replay-requests'), \
                patch.object(storage, 'ROOT', root), patch.object(retention, 'ROOT', root), \
                patch.object(prepare_snomed_candidate, 'publish', side_effect=local_publish):
            try:yield lock, root, run, path, gold
            finally:
                for base, directories, _ in os.walk(meme):Path(base).chmod(0o700)


def seal(lock):
    lock['manifest_sha256'] = manifests.digest(lock['manifest'])
    lock['plan_sha256'] = manifests.digest(lock['plan'])
    lock['profile_sha256'] = manifests.digest(lock['profile'])
    lock['lock_sha256'] = manifests.digest({k: v for k, v in lock.items() if k != 'lock_sha256'})


def archive_descriptors(lock, root, run):
    """Bind all fixture bytes into one archive with no full-folder extraction."""
    archive = root / 'sources' / (lock['request']['version'] + '.tgz')
    selected = []
    with tarfile.open(archive, 'w:gz') as outgoing:
        for name, artifact in lock['manifest']['artifacts'].items():
            for file in artifact['files']:
                path = Path(file['uri'].removeprefix('file://'));raw = path.read_bytes()
                # Keep publisher role filename shape; official roles bind the
                # independent src output namespace, never constructor paths.
                member = lock['request']['version'] + ('/' + file['role'] if artifact['artifact_type'] == 'reference-inversion' else '/input/' + path.name)
                info = tarfile.TarInfo(member);info.size = len(raw);outgoing.addfile(info, io.BytesIO(raw))
                selected.append((file, member))
    checksum = legacy.sha(archive)
    for file, member in selected:
        file.update(uri=archive.as_uri(), archive_member=member, archive_format='tar.gz',
                    archive_sha256=checksum, archive_bytes=archive.stat().st_size)
    seal(lock);(run / 'case.lock.json').write_text(json.dumps(lock))
    return archive


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def rejected(call, label):
        try:call()
        except (ValueError, RuntimeError, FileExistsError, KeyError):passed.append(label)
        else:raise AssertionError(label)
    with fixture() as (lock, root, run, path, gold):
        target = root / 'sources' / lock['request']['version']
        good(worker.verify_lock(lock) == target, 'Native capsule resolves its declared canonical version without historical case selection')
        shown = subprocess.run([sys.executable, '-B', str(admission.ROOT / 'tools/inversion_request.py'), 'show', str(path)], capture_output=True, text=True)
        good(shown.returncode == 0 and json.loads(shown.stdout)['configuration'] == lock['configuration'], 'The common show command displays native release configuration')
        good('data_b64' not in shown.stdout and 'modules_b64' not in shown.stdout, 'Native show omits executable payload bodies')
        program = remote.bootstrap(lock, 'submit')
        compile(program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_REQUEST', 1)[0], '<native-bootstrap>', 'exec')
        good('release_worker' in program, 'The existing common submit command dispatches native capsules with a compilable bootstrap')
        rejected(lambda: legacy.verify_lock(lock), 'Historical admission cannot mislabel a native capsule as a historical case')
        source = nci_fixture.fixture()[0]
        rejected(lambda: admission.resolve(source, 'synthetic-run'), 'Public native resolver rejects synthetic manifest evidence')
        for key, value in [('production_eligible', True), ('insertion_executed', True), ('execution_enabled', False), ('artifact_type', 'ncimeta-release-preflight-lock')]:
            bad = copy.deepcopy(lock);bad[key] = value;seal(bad)
            rejected(lambda: worker.verify_lock(bad), 'Unsupported native authority rejected: ' + key)
        bad = copy.deepcopy(lock);bad['code_files'][0]['data_b64'] = base64.b64encode(b'changed').decode();seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Resealed source payload change fails package content verification')
        bad = copy.deepcopy(lock);bad['plan']['stages'][0]['argv'] = ['/usr/bin/true'];seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Resealed native argv change fails source-owned deterministic plan regeneration')
        bad = copy.deepcopy(lock);bad['profile']['minimum_free_disk_gib'] = 0.0001;seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Resealed profile swap fails committed registry binding')
        bad = copy.deepcopy(lock);bad['runtime_files'][0]['repository_path'] = 'INV/unreviewed';seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Resealed runtime inventory change fails reviewed runtime identity')
        bad = copy.deepcopy(lock);extra = admission.file_record(b'overwrite', 'nci.cfg.in');bad['plan']['generated_files'].append(extra);seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Generated setting cannot collide with pinned source code')
        bad = copy.deepcopy(lock);bad['manifest']['artifacts']['official']['version'] = 'NCI_2026_08E';seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'A prior-release oracle cannot stand in for current-release official output')
        bad = copy.deepcopy(lock);bad['manifest']['artifacts']['publisher']['files'][0]['uri'] = (target / 'orig/current-input.txt').as_uri();seal(bad)
        rejected(lambda: worker.verify_lock(bad), 'Replaceable current-folder input URI is rejected before preservation can invalidate it')
        def location(uri):
            return admission.verify_locations({'artifacts': {'input': {'files': [{'uri': uri}]}}}, target)
        rejected(lambda: location((target.parent / 'MTH_2023AB/src/cui_said_map').as_uri()),
                 'A prior canonical folder cannot remain a hidden native replay or retained-verification dependency')
        rejected(lambda: location((target.parent / 'MTH_2023AB.before-old-test/src/cui_said_map').as_uri()),
                 'A retained source tree is also mutable through preservation maintenance')
        escaped = (root / 'qa/../sources/MTH_2023AB/src/cui_said_map').as_uri().replace('/qa/../', '/qa/%2e%2e/')
        rejected(lambda: location(escaped), 'Encoded parent aliases cannot bypass source-tree input isolation')
        good(location((target.parent / 'MTH_2023AB.tgz').as_uri()) is None,
             'A separately frozen top-level official archive cache remains a supported native input')
        good(location((root / 'qa/prior-identity-cache/MTH_2023AB' / ('a' * 64) / 'cui_said_map').as_uri()) is None,
             'An immutable prior identity cache outside replaceable trees remains a supported native input')
        for change, label in [
            (lambda p: p['input_files'][0].update(destination='../escape'), 'Input traversal is rejected'),
            (lambda p: p['input_files'].append(copy.deepcopy(p['input_files'][0])), 'Colliding native input destinations are rejected'),
            (lambda p: p['input_files'][0].update(artifact='official', role='src/classes_atoms.src'), 'Completed official outputs cannot become constructor input'),
            (lambda p: p['input_files'][0].update(scope='inv', destination='sources/NCI_1900_01A/src/data'), 'Undeclared external prior release is rejected'),
            (lambda p: p['input_files'][0].update(scope='meme', destination='mr/umls/2026AA/subset3/METASUBSET/MRCONSO.RRF'), 'Unrelated external native destination is rejected'),
            (lambda p: p['output_files'].append(p['output_files'][0]), 'Duplicate native outputs are rejected'),
            (lambda p: p['stages'][0].update(cwd='../bad'), 'Native stage working-directory traversal is rejected'),
            (lambda p: p['stages'][0].update(stdout='../bad'), 'Native stage stdout traversal is rejected')]:
            plan = copy.deepcopy(lock['plan']);change(plan)
            rejected(lambda: admission.verify_plan(plan, lock['manifest']), label)
        good(retention.inventory(root, 'NCI_2025_06A', source='NCI')['admission_available'], 'New compatible versions use explicit registered-source retention capability')
        rejected(lambda: retention.inventory(root, 'NCI_2025_06A'), 'Unbound historical retention calls do not silently gain new version authority')
        rejected(lambda: retention.inventory(root, 'MTH_2025AA', source='NCI'), 'Source capability cannot authorize another source namespace')
        receipt = {'source': 'NCI', 'version': target.name, 'exists': False, 'manifest': [], 'root_mode': None}
        receipt['receipt_sha256'] = manifests.digest(receipt)
        worker.verify_previous(lock, target, receipt)
        target.mkdir();(target / 'manual.txt').write_text('preserve staff/test data')
        rejected(lambda: worker.verify_previous(lock, target, receipt), 'Source appearing after absent-tree inspection blocks replacement')
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'):
            receipt = worker.inspect_current(lock)
        good(receipt['exists'] and len(receipt['manifest']) == 1, 'Read-only current inspection pins actual tree bytes')
        (target / 'manual.txt').write_text('changed after inspection')
        rejected(lambda: worker.verify_previous(lock, target, receipt), 'Changed current source cannot be overwritten using a stale inspection')
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'):
            receipt = worker.inspect_current(lock)
        before = legacy.sha(target / 'manual.txt')
        prior = legacy.preserve(target, lock['run_id'], receipt)
        good(not target.exists() and legacy.sha(prior / 'manual.txt') == before, 'Actual preservation renames and retains exact predecessor data')
        legacy.restore(prior, target, receipt)
        good(legacy.sha(target / 'manual.txt') == before, 'Failed pre-publication preparation can restore the actual predecessor')
        data = b'preserved prepared native input\n'
        destination = root.parent / 'mr/umls/2025AB/subset3/METASUBSET/MRCONSO.RRF'
        key = str(destination.relative_to(root.parent))
        identity = {'ContentLength': len(data), 'ETag': '"object-etag"', 'LastModified': '2025-10-16T00:00:00+00:00', 'VersionId': None}
        artifact = {'artifact_type': 'prepared-bundle', 'source': 'MTH', 'version': 'MTH_2025AB',
                    'data': {'acquisition': {'bucket': 'nci-evs-meme', 'objects': {'MRCONSO.RRF': {'key': key, 'object_identity': identity}}}}}
        file = {'role': 'MRCONSO.RRF', 'uri': destination.as_uri(), 'sha256': manifests.hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        calls = []
        def aws(arguments, **kwargs):
            calls.append(arguments)
            if arguments[2] == 'get-object':Path(arguments[-1]).write_bytes(data)
            return subprocess.CompletedProcess(arguments, 0, json.dumps(identity), '')
        with patch.object(worker.subprocess, 'run', side_effect=aws):
            received = worker.acquire_preserved_object(artifact, file, destination, run)
            good(received['status'] == 'frozen' and destination.read_bytes() == data, 'Generic MTH acquisition downloads only the explicitly selected preserved object at the standard path (AWS mocked)')
            good(len(calls) == 3 and [c[2] for c in calls] == ['head-object', 'get-object', 'head-object'], 'One coherent before/after identity brackets one conditional object download')
            good('--if-match' in calls[1] and not destination.stat().st_mode & 0o222, 'Prepared download binds its ETag and publishes verified read-only bytes')
            rejected(lambda: worker.acquire_preserved_object(artifact, file, destination, run), 'Prepared acquisition refuses to overwrite existing data')
        destination.unlink()
        broken = copy.deepcopy(artifact);broken['data']['acquisition']['objects']['MRCONSO.RRF']['key'] = 'unrelated/key'
        with patch.object(worker.subprocess, 'run', side_effect=AssertionError('No network for bad selection')):
            rejected(lambda: worker.acquire_preserved_object(broken, file, destination, run), 'Prepared S3 selection cannot redirect a standard role to another object key')
        def bad_download(arguments, **kwargs):
            if arguments[2] == 'get-object':Path(arguments[-1]).write_bytes(b'wrong bytes')
            return subprocess.CompletedProcess(arguments, 0, json.dumps(identity), '')
        with patch.object(worker.subprocess, 'run', side_effect=bad_download):
            rejected(lambda: worker.acquire_preserved_object(artifact, file, destination, run), 'Prepared download with incorrect bytes is never published')
        good(not destination.exists() and len(list(destination.parent.glob('.MRCONSO.RRF.download-*'))) == 1, 'Failed object bytes remain one explicit partial for investigation')
        with patch.object(worker.subprocess, 'run', side_effect=AssertionError('No duplicate partial download')):
            rejected(lambda: worker.acquire_preserved_object(artifact, file, destination, run), 'An unresolved prepared-input partial blocks another download instead of accumulating copies')
    # Exercise full common lifecycle control with actual byte/materialization/
    # discovery/comparison and mocked host/runtime/native-conversion only.
    with fixture('NCI_2027_02B', 'NCI_2026_12C') as (lock, root, run, path, gold):
        target = root / 'sources' / lock['request']['version'];stages = []
        def conversion(argv, **kwargs):
            stages.append(argv)
            if argv == lock['plan']['stages'][-1]['argv']:nci_fixture.outputs(lock['plan'], target)
            return {'exit_status': 0, 'network': 'disabled', 'fixture_native_stage': True}
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'), patch.object(legacy, 'runtime'), \
                patch.object(worker, 'capacity', return_value={'fixture_capacity': True}), patch.object(worker, 'execute', side_effect=conversion):
            worker.worker(path)
        state = manifests.load(run / 'status.json');result = manifests.load(run / 'result.json')
        good(state['status'] == 'complete' and len(stages) == 6, 'Common worker completes all six fixed stages through native dispatch (conversion mocked)')
        good(result['acceptance']['status'] == 'PASS_EXACT', 'Exact tiny outputs plus independent physical invariants produce a passing fixture verdict')
        good(result['production_eligible'] is False and result['insertion_executed'] is False, 'Passing dev run cannot authorize production or insertion')
        good(not (target / 'manual.txt').exists() and (run / 'physical-input-validation.json').is_file(), 'Fresh candidate has physical input evidence and no seeded official output')
        good((target / 'etc/qa').is_dir(), 'Standard QA directory exists before native logger/converter starts')
        good(all(v['reused'] is False for v in manifests.load(run / 'preparation.json')['materialized']), 'Only the declared constructor inputs are materialized')
        for version, label in [(lock['request']['version'], 'current-release'), (remote.SOURCES['NCI'], 'wrong-historical-release')]:
            inner = root / 'sources' / version / 'etc/qa/replay-runs' / lock['run_id'];inner.mkdir(parents=True)
            (inner / 'progress.json').write_text(json.dumps({'stage': label}))
        program = remote.read_program('NCI', lock['run_id'], True).split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0]
        program = program.replace('/local/content/MEME/MEME5/inv', str(root))
        output = io.StringIO()
        with patch('socket.gethostname', return_value='ncias-d3777-c'), redirect_stdout(output):exec(compile(program, '<confined-status>', 'exec'), {})
        collected = json.loads(output.getvalue().split('BEGIN_COMMON_REPLAY_RESULT\n')[1].split('\nEND_COMMON_REPLAY_RESULT')[0])
        good(collected['records']['adapter_progress.json']['stage'] == 'current-release', 'Status/collection follows the actual locked release instead of a historical source/version table')
        wrong_source = remote.read_program('MTH', lock['run_id'], False).split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0]
        wrong_source = wrong_source.replace('/local/content/MEME/MEME5/inv', str(root))
        with patch('socket.gethostname', return_value='ncias-d3777-c'):
            rejected(lambda: exec(compile(wrong_source, '<wrong-source-status>', 'exec'), {}), 'Status refuses to label another source run with the caller source')
        (target / 'src/attributes.src').write_bytes(b'difference\n')
        checked = worker.compare(lock, target)
        good(checked['acceptance']['status'] == 'DIFFERENCES_REQUIRE_REVIEW', 'Any output/structure mismatch remains a review verdict without a historical waiver')
    with fixture() as (lock, root, run, path, gold):
        first = worker._descriptor(lock, lock['plan']['input_files'][0]);Path(first['uri'].removeprefix('file://')).write_bytes(b'changed input')
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'), patch.object(legacy, 'runtime'), patch.object(worker, 'capacity'):
            rejected(lambda: worker.worker(path), 'Native input mismatch fails the common worker before candidate publication')
        good(not (root / 'sources' / lock['request']['version']).exists() and manifests.load(run / 'status.json')['status'] == 'failed', 'Failed input verification retains a failed control record and publishes no candidate')
    with fixture() as (lock, root, run, path, gold):
        def failed(argv, **kwargs):raise RuntimeError('native stage fixture failure')
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'), patch.object(legacy, 'runtime'), patch.object(worker, 'capacity'), patch.object(worker, 'execute', side_effect=failed):
            rejected(lambda: worker.worker(path), 'Native process failure is propagated')
        good(manifests.load(run / 'status.json')['status'] == 'failed' and not (run / 'result.json').exists(), 'Failed native conversion cannot create an accepted result')
        good((root / 'sources' / lock['request']['version']).exists(), 'Published partial candidate remains available for troubleshooting')
    with fixture('NCI_2027_02B', 'NCI_2026_12C') as (lock, root, run, path, gold):
        archive = archive_descriptors(lock, root, run)
        archive_raw = archive.read_bytes();archive.unlink()
        with patch.object(worker, 'available_memory', return_value=32 * 1024 ** 3), \
                patch.object(worker.shutil, 'disk_usage', return_value=SimpleNamespace(free=64 * 1024 ** 3)):
            budget = worker.capacity(lock)
        good(budget['missing_download_bytes'] == len(archive_raw), 'Capacity counts one missing shared archive once across all input/oracle roles')
        good(budget['required_free_bytes'] == 18 * 1024 ** 3 + len(archive_raw), 'Acquisition budget preserves the complete native floor after the pending download')
        with patch.object(worker, 'available_memory', return_value=32 * 1024 ** 3), \
                patch.object(worker.shutil, 'disk_usage', return_value=SimpleNamespace(free=budget['required_free_bytes'] - 1)):
            rejected(lambda: worker.capacity(lock), 'Insufficient post-download reserve blocks before any download or source replacement')
        archive.write_bytes(archive_raw)
        selected = root / 'selected-only';selected.mkdir()
        copied = worker.materialize(lock, selected)
        good(len(copied) == 8 and all((selected / item['destination']).is_file() for item in lock['plan']['input_files']), 'One streamed archive materializes only eight declared constructor members')
        good(not any((selected / name).exists() for name in lock['plan']['output_files']), 'Completed official archive outputs are never extracted into the fresh candidate')
        fanout = copy.deepcopy(lock)
        duplicate = copy.deepcopy(lock['plan']['input_files'][0]);duplicate['destination'] = 'orig/second-native-copy.txt'
        fanout['plan']['input_files'].append(duplicate)
        second = root / 'fanout';second.mkdir()
        materialized = worker.materialize(fanout, second)
        good(len(materialized) == 9 and (second / duplicate['destination']).read_bytes() == (selected / lock['plan']['input_files'][0]['destination']).read_bytes(), 'A tar member can safely feed two destinations without backward seeking or duplicate archives')
        target = root / 'sources' / lock['request']['version'];(target / 'src').mkdir(parents=True)
        (target / 'manual.txt').write_text('unique original data')
        (target / 'src/attributes.src').write_bytes((gold / 'src/attributes.src').read_bytes())
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'):
            previous = worker.inspect_current(lock)
        previous_path = run / 'previous-source-receipt.json';previous_path.write_text(json.dumps(previous))
        def conversion(argv, **kwargs):
            if argv == lock['plan']['stages'][-1]['argv']:nci_fixture.outputs(lock['plan'], target)
            return {'exit_status': 0, 'network': 'disabled', 'fixture_native_stage': True}
        with patch.object(legacy, 'guard'), patch.object(legacy, 'idle'), patch.object(legacy, 'runtime'), \
                patch.object(worker, 'capacity'), patch.object(worker, 'execute', side_effect=conversion):
            worker.worker(path, previous_path)
            scan = worker.verify_retained(lock)
        good(scan['status'] == 'PASS_NATIVE_RELEASE_VERIFICATION' and len(scan['files']) == 5, 'A separate read-only scan rechecks a new version without fixed replay/capacity/retention date entries')
        scan_path = root / 'qa/independent-native.json';scan_path.write_text(json.dumps(scan))
        with patch.object(storage, 'guard'), patch.object(retention, '_idle'):
            planned = retention.plan(lock['run_id'], str(scan_path), legacy.sha(scan_path))
        good(planned['duplicate_bytes'] == (gold / 'src/attributes.src').stat().st_size, 'New native acceptance with src/path keys can plan only independently archive-identical predecessor bytes')
        preserved = root / 'sources' / (target.name + '.before-' + lock['run_id'])
        good(storage._source(preserved) == preserved, 'New retention authority verifies the complete actual native capsule')
        minimal = {'artifact_type': 'ncimeta-native-release-lock', 'run_id': lock['run_id'], 'request': {'version': target.name}}
        minimal['lock_sha256'] = manifests.digest(minimal);path.write_text(json.dumps(minimal))
        rejected(lambda: storage._source(preserved), 'A self-sealed minimal pseudo-lock cannot authorize new retention targets')
        path.write_text(json.dumps(lock))
        good((preserved / 'manual.txt').read_text() == 'unique original data' and archive.is_file(), 'Planning leaves unique predecessor files and original recovery archive intact')
        with patch.object(storage, 'guard'), patch.object(retention, '_idle'):
            compacted = retention.compact(planned['plan'], planned['plan_sha256'])
            destination = preserved.with_name(target.name + '.before-native-restored')
            restored = retention.restore(planned['plan'], planned['plan_sha256'], destination)
        good(compacted['status'] == 'COMPACTED' and not compacted['new_archive_created'], 'Native rollback duplicate-only compaction creates no archive')
        good(restored['status'] == 'PASS_RESTORED_TREE_VERIFICATION' and (destination / 'manual.txt').read_text() == 'unique original data', 'Native-version recovery verifies the complete restored tree under the original run capability')
    return passed


if __name__ == '__main__':
    checks = check()
    for label in checks:print('PASS', label)
    print(len(checks), 'shared native release execution checks passed (full native conversion mocked)')
