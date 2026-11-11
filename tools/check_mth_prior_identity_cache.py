#!/usr/bin/env python3
"""Real local cache/47-artifact/snapshot/native lifecycle; no server or AWS."""
import base64
import copy
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import cache_mth_prior_identity as cache
import capture_mth_prior as captured_prior
import check_capture_mth_prior as prior_fixtures
import check_curate_archived_mth as fixtures
import check_execute_release_mth as native
import check_mth_background_selection as archive_fixture
import curate_archived_mth as curator
import execute_release_mth as execution
import inversion_worker as legacy
import prepare_snomed_candidate
import release_manifest
import release_worker


def _write(path, raw, mode=0o444):
    if path.exists():path.chmod(0o644)
    path.write_bytes(raw);path.chmod(mode)


@contextmanager
def cache_only_fixture():
    """Small actual captured DATA for publication guards; no native pipeline."""
    with tempfile.TemporaryDirectory(prefix='mth-cache-publication-') as temporary:
        root = Path(temporary).resolve();meme = root / 'MEME5'
        (meme / 'inv/sources').mkdir(parents=True);(meme / 'inv/qa').mkdir()
        raw = prior_fixtures.archive();request = prior_fixtures.request(raw)
        with patch.object(cache,'MEME_ROOT',meme), patch.object(cache.socket,'gethostname',return_value='ncias-d3777-c'), \
                patch.object(cache.pwd,'getpwuid',return_value=SimpleNamespace(pw_name='tomcata')), \
                patch.object(cache.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)), \
                patch.object(captured_prior,'ROOT',meme/'inv/sources'),patch.object(captured_prior,'guard'), \
                patch.object(captured_prior,'publish',side_effect=cache.publish):
            captured=captured_prior.capture(request,prior_fixtures.FakeClient(raw,request))
            yield captured
        for path,_,_ in os.walk(root):Path(path).chmod(0o700)


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='mth-identity-cache-') as temporary:
        directory = Path(temporary).resolve()
        captured, target, code = fixtures.fixture(directory, skipped=True)
        meme = directory / 'MEME5';inv = meme / 'inv';(inv / 'qa').mkdir()
        prior_version = 'MTH_2026AA';prior_path = inv / 'sources' / prior_version
        substitutions = {b'C1': b'C0000001', b'C2': b'C0000002', b'C3': b'C0000003', b'C4': b'C0000004',
                         b'COLD': b'C0000005', b'COLD2': b'C0000006', b'COLD3': b'C0000007'}
        pattern = re.compile(rb'(?<![A-Za-z0-9_])(?:COLD3|COLD2|COLD|C1|C2|C3|C4)(?![A-Za-z0-9_])')
        def realistic(raw):return pattern.sub(lambda match: substitutions[match[0]], raw)
        # Keep actual RRF inputs at the standard mirrored locations and make
        # native tiny identifiers conform to the real prior-capture CUI dialect.
        for descriptor in captured['prepared']['files']:
            source = Path(descriptor['uri'].removeprefix('file://'))
            raw = realistic(source.read_bytes())
            destination = meme / 'mr/umls' / captured['version'][4:] / 'subset3/METASUBSET' / descriptor['role']
            _write(destination, raw)
            descriptor.update(uri=destination.as_uri(), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            if descriptor['role'] in captured['prepared']['facts']:
                captured['prepared']['facts'][descriptor['role']].update(sha256=descriptor['sha256'], bytes=len(raw))
        prior_descriptor = captured['prior_identity']['files'][0]
        mapping = realistic(Path(prior_descriptor['uri'].removeprefix('file://')).read_bytes())
        raw_archive = io.BytesIO()
        with tarfile.open(fileobj=raw_archive, mode='w:gz') as handle:
            item = tarfile.TarInfo(prior_version + '/src/cui_said_map');item.size = len(mapping);handle.addfile(item, io.BytesIO(mapping))
            item = tarfile.TarInfo(prior_version + '/unselected-code.pl');body = b'NEVER COPIED OR EXECUTED\n';item.size = len(body);handle.addfile(item, io.BytesIO(body))
        raw_archive = raw_archive.getvalue()
        request = {'source': 'MTH', 'version': prior_version, 'bucket': 'nci-evs-meme',
            'key': 'inv/sources/' + prior_version + '.tgz', 'capture_id': 'SYNTHETIC-prior-identity-cache',
            'object_identity': {'ContentLength': len(raw_archive), 'ETag': '"SYNTHETIC-prior-archive"',
                                'LastModified': '2024-01-01T00:00:00+00:00', 'VersionId': None}}
        free = SimpleNamespace(free=100 * 1024 ** 3)
        with patch.object(cache, 'MEME_ROOT', meme), patch.object(cache.socket, 'gethostname', return_value='ncias-d3777-c'), \
                patch.object(cache.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='tomcata')), \
                patch.object(cache.shutil, 'disk_usage', return_value=free), \
                patch.object(captured_prior, 'ROOT', inv / 'sources'), patch.object(captured_prior, 'guard'), \
                patch.object(captured_prior, 'publish', side_effect=cache.publish), \
                patch.object(release_worker, 'ROOT', inv), patch.object(release_worker, 'CONTROL', inv / 'qa/replay-requests'), \
                patch.object(prepare_snomed_candidate, 'publish', side_effect=cache.publish):
            original = captured_prior.capture(request, prior_fixtures.FakeClient(raw_archive, request))
            source = prior_path / 'src/cui_said_map'
            captured['prior_identity'] = {'version': prior_version, 'files': [{'role': 'cui_said_map', 'uri': source.as_uri(),
                'sha256': original['map_identity']['sha256'], 'bytes': original['map_identity']['bytes']}],
                'facts': {**original['map_identity'], 'malformed_rows': 0}}
            # The first native pass independently creates the reference bytes.
            provisional = curator.curate(captured, fixtures.ENGINE, 'SYNTHETIC-identity-cache-review')['manifest']
            assert provisional is not None
            plan = execution.build_plan(provisional['configuration'], provisional['artifacts'], code)
            for item in plan['input_files']:
                if item['role'] == 'cui_said_map':_write(execution.input_path(item, target), mapping)
            for item in plan['generated_files']:_write(target / item['relative_path'], base64.b64decode(item['data_b64']))
            run = directory / 'run';(run / 'native-plan.json').write_text(json.dumps(plan))
            native.run_tiny(plan, target, run)
            for name in execution.OUTPUT_NAMES:archive_fixture._capture_body(captured, 'src/' + name, (target / 'src' / name).read_bytes())
            archive_fixture._refresh_archive(captured)
            archive = inv / 'sources' / (captured['version'] + '.tgz')
            archive.write_bytes(Path(captured['archive']['uri'].removeprefix('file://')).read_bytes());archive.chmod(0o444)
            captured['archive']['uri'] = archive.as_uri()
            manifest = curator.curate(captured, fixtures.ENGINE, 'SYNTHETIC-identity-cache-review')['manifest']
            assert manifest is not None
            plan = execution.build_plan(manifest['configuration'], manifest['artifacts'], code)
            yield directory, captured, original, manifest, plan, target, run, code
        # Readonly cache directories are deliberately never relaxed by product
        # code. Confined test teardown owns and removes its synthetic tree.
        for path, dirs, _ in os.walk(directory):Path(path).chmod(0o700)


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def rejected(function, label):
        try:function()
        except (ValueError, RuntimeError, OSError):checks.append(label);return
        raise AssertionError(label)
    with fixture() as (directory, captured, original, manifest, initial_plan, target, run, code):
        prior = Path(original['target']);source = prior / 'src/cui_said_map'
        source_bytes = source.read_bytes();source_receipt_bytes = (prior / captured_prior.RECEIPT).read_bytes()
        original_manifest = json.dumps(manifest, sort_keys=True).encode();original_receipt = copy.deepcopy(original)
        # Dev/account/path safeguards are actual helper entry checks.
        with patch.object(cache.socket, 'gethostname', return_value='meme-edit'):
            rejected(lambda: cache.publish_cache(original), 'production hostname rejected')
        with patch.object(cache.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='someone-else')):
            rejected(lambda: cache.publish_cache(original), 'different effective operator rejected')
        modified = copy.deepcopy(original);modified['map_identity']['bytes'] += 1
        rejected(lambda: cache.publish_cache(modified), 'changed original capture seal rejected')
        modified = copy.deepcopy(original);modified['target'] = '/tmp/arbitrary';modified['receipt_sha256'] = captured_prior.digest({k:v for k,v in modified.items() if k!='receipt_sha256'})
        rejected(lambda: cache.publish_cache(modified), 'arbitrary source path rejected despite self-consistent new seal')
        with patch.object(cache.shutil, 'disk_usage', return_value=SimpleNamespace(free=original['map_identity']['bytes'] + cache.RESERVE - 1)):
            rejected(lambda: cache.publish_cache(original), 'copy requires full map payload plus 12GiB reserve')
        cached = cache.publish_cache(original);cache_path = Path(cached['cache_directory']);cache_map = cache_path / cache.MAP
        good(cache_map.read_bytes() == source_bytes and cache_map.stat().st_ino != source.stat().st_ino and cache_map.stat().st_nlink == 1, 'actual cached map is byte-identical independent inode, never symlink or hardlink')
        good({path.name for path in cache_path.iterdir()} == {cache.MAP, cache.RECEIPT}, 'content-addressed directory contains only map and sealed receipt')
        good(cache_path.name == original['map_identity']['sha256'] and cache_path.parent.name == original['version'], 'cache locator is exact version plus complete map SHA256')
        good(cache_path.stat().st_mode & 0o777 == 0o555 and all(path.stat().st_mode & 0o777 == 0o444 for path in cache_path.iterdir()), 'cache map/receipt/directory are readonly')
        good(cached['original_capture_receipt'] == original and cached['map_identity'] == original['map_identity'] and cached['copy_reserve_bytes'] == 12 * 1024 ** 3, 'original seal, S3/container provenance and complete map facts retained')
        good(source.read_bytes() == source_bytes and (prior / captured_prior.RECEIPT).read_bytes() == source_receipt_bytes and original == original_receipt, 'canonical stub and original receipt bytes remain unchanged')
        good(cache.publish_cache(original) == cached, 'matching sealed cache verified and reused')
        issues = [];old_rows = release_manifest.verify_files(manifest['artifacts'], True, issues)
        good(not issues and len(old_rows) == 47 and all(row['status']=='VERIFIED' for row in old_rows), 'original source descriptor set has actual47 verified input/reference bytes')
        derivative = copy.deepcopy(manifest);derivative['artifacts']['mth-identity']['files'] = [copy.deepcopy(cached['cache_file'])]
        derivative['artifacts']['mth-identity']['data']['immutable_cache_publication'] = copy.deepcopy(cached)
        plan = execution.build_plan(derivative['configuration'], derivative['artifacts'], code)
        good(plan == initial_plan, 'stable prior input locator changes no native plan or seven generated files')
        previous = target.with_name(target.name + '.before-cache-fixture');target.rename(previous)
        prior.rename(prior.with_name(prior.name + '.preserved-fixture'))
        (prior / 'src').mkdir(parents=True);(prior / 'src/cui_said_map').write_bytes(b'C0000003|999\n')
        good(cache.publish_cache(original) == cached and cache_map.read_bytes() == source_bytes, 'cache reuse succeeds after canonical prior folder and old receipt are replaced')
        issues = [];rows = release_manifest.verify_files(derivative['artifacts'], True, issues)
        good(not issues and len(rows)==47 and all(row['status']=='VERIFIED' for row in rows), 'all47 derivative artifact byte checks pass after real canonical prior replacement')
        old_issues=[];old_now=release_manifest.verify_files(manifest['artifacts'], True, old_issues)
        good(bool(old_issues) and any(row['artifact']=='mth-identity' and row['status']!='VERIFIED' for row in old_now), 'old canonical locator reproduces lifecycle failure without revising its original record')
        good(json.dumps(manifest,sort_keys=True).encode()==original_manifest and len(old_rows)==47 and all(row['status']=='VERIFIED' for row in old_rows), 'original manifest and original47 verification rows remain unmodified historical facts')
        full_code = [{**item,'relative_path':item['repository_path'].removeprefix(execution.PACKAGE+'/'),
                      'kind':'file','bytes':len(base64.b64decode(item['data_b64']))} for item in code]
        lock = {'manifest':derivative,'configuration':derivative['configuration'],'plan':plan,'code_files':full_code,
                'profile':{'handler':'execute_release_mth'},'request':{'source':'MTH','version':plan['version']},
                'run_id':'native-cache-fixture','lock_sha256':'SYNTHETIC-unittest-admission'}
        fresh_run=directory/'MEME5/inv/qa/replay-requests/native-cache-fixture';fresh_run.mkdir(parents=True)
        # Production prepare/materialize/physical validation, with the actual
        # cross-platform kernel-exclusive publication primitive substituted.
        prepared = release_worker.prepare(lock,target,fresh_run)
        good(prepared['physical_validation']['passed'] and prepared['code_from_git'], 'common preparation materializes actual stable cache into candidate snapshot and validates inputs')
        snapshot=target/'orig/identity'/original['version']/'src/cui_said_map'
        good(snapshot.read_bytes()==source_bytes and (target/'old').is_symlink() and os.readlink(target/'old')=='orig/identity/'+original['version'], 'native old/src access resolves to independent candidate-local snapshot')
        (run/'native-plan.json').write_text(json.dumps(plan));native.run_tiny(plan,target,run)
        good(execution.validate_outputs(plan,target)['passed'], 'complete second tiny native pipeline preserves retained identity and bounds')
        for name in execution.OUTPUT_NAMES:
            good((target/'src'/name).read_bytes()==(previous/'src'/name).read_bytes(), 'stable-cache lifecycle leaves native output byte-identical: '+name)
        comparison=release_worker.compare(lock,target)
        good(comparison['acceptance']['status']=='PASS_EXACT', 'all23 actual tiny native outputs match independently archived current references')
        (fresh_run/'status.json').write_text(json.dumps({'status':'complete'}))
        (fresh_run/'result.json').write_text(json.dumps({'lock_sha256':lock['lock_sha256'],
            'comparison':{k:v for k,v in comparison.items() if k!='acceptance'},'acceptance':comparison['acceptance']}))
        with patch.object(release_worker,'verify_lock',return_value=target), patch.object(legacy,'guard'), \
                patch.object(legacy,'idle'), patch.object(legacy,'runtime'):
            verified=release_worker.verify_retained(lock)
            good(verified['status']=='PASS_NATIVE_RELEASE_VERIFICATION' and verified['inputs_verified']==47,
                 'actual retained scanner verifies47 original artifacts plus candidate snapshot after prior canonical replacement (host/runtime/admission plumbing confined)')
            _write(snapshot,b'C0000003|999\n')
            rejected(lambda:release_worker.verify_retained(lock),'candidate snapshot mutation still fails common retained verification')
            _write(snapshot,source_bytes)
            _write(cache_map,b'C0000003|999\n')
            rejected(lambda:cache.publish_cache(original),'cache byte/row mutation rejected independently of canonical origin')
            rejected(lambda:release_worker.verify_retained(lock),'cache mutation fails full retained artifact verification despite intact snapshot')
            _write(cache_map,source_bytes)
            unrelated=next(item for item in derivative['artifacts']['mth-prepared']['files'] if item['role']=='MRDOC.RRF')
            unrelated=Path(unrelated['uri'].removeprefix('file://'));raw=unrelated.read_bytes();_write(unrelated,raw+b'x')
            rejected(lambda:release_worker.verify_retained(lock),'unrelated prepared-input mutation remains a hard failure')
            _write(unrelated,raw)
            good(release_worker.verify_retained(lock)['inputs_verified']==47,'exact restoration revalidates all47 artifacts without conversion rerun')
        cache_map.chmod(0o644)
        rejected(lambda:cache.publish_cache(original),'writable cache rejected rather than adopted')
        cache_map.chmod(0o444)
        receipt_path=cache_path/cache.RECEIPT;raw=receipt_path.read_bytes();_write(receipt_path,raw.replace(b'PUBLISHED_PRIOR_IDENTITY_CACHE',b'INVALID_PRIOR_IDENTITY_CACHE'))
        rejected(lambda:cache.publish_cache(original),'changed cache receipt seal rejected')
        _write(receipt_path,raw)
        good(cache.publish_cache(original)==cached,'complete cache reuse remains independent of absent original receipt after negative checks')
    with cache_only_fixture() as original:
        _,source,target=cache.select(original);target.mkdir(parents=True)
        before=source.read_bytes()
        rejected(lambda:cache.publish_cache(original),'unsealed existing empty cache directory is never overwritten')
        good(not list(target.iterdir()) and source.read_bytes()==before,'empty competing cache and canonical original stay untouched')
    with cache_only_fixture() as original:
        _,source,target=cache.select(original)
        primitive=cache.publish
        def race(staging,destination):
            destination.mkdir()
            primitive(staging,destination)
        with patch.object(cache,'publish',side_effect=race):
            rejected(lambda:cache.publish_cache(original),'actual kernel no-clobber refuses empty destination appearing at publication')
        staging=target.parent/('.'+target.name+'.publishing')
        good(target.is_dir() and not list(target.iterdir()) and {p.name for p in staging.iterdir()}=={cache.MAP,cache.RECEIPT},
             'publication race preserves competing target and exact sealed copied evidence')
    with cache_only_fixture() as original:
        _,source,target=cache.select(original)
        with patch.object(cache,'publish',side_effect=OSError('SYNTHETIC interrupted final publication')):
            rejected(lambda:cache.publish_cache(original),'interrupted final publication retains complete sealed stage')
        before=(target.parent/('.'+target.name+'.publishing')/cache.MAP).stat().st_ino
        source.parent.parent.rename(source.parent.parent.with_name(original['version']+'.preserved-fixture'))
        receipt=cache.publish_cache(original)
        good((target/cache.MAP).stat().st_ino==before and receipt['cache_directory']==str(target),
             'sealed-stage publication retry reuses the same independent inode without requiring canonical origin')
    with cache_only_fixture() as original:
        _,source,target=cache.select(original);before=source.read_bytes()
        free=[SimpleNamespace(free=100*1024**3),SimpleNamespace(free=cache.RESERVE-1)]
        with patch.object(cache.shutil,'disk_usage',side_effect=free):
            rejected(lambda:cache.publish_cache(original),'copy stops before crossing the fixed12GiB reserve')
        stage=target.parent/('.'+target.name+'.publishing')
        good(not target.exists() and (stage/'publication-failed.json').is_file() and source.read_bytes()==before,
             'failed private copy retains evidence and never modifies canonical data')
        rejected(lambda:cache.publish_cache(original),'retained partial stage blocks blind duplicate copying')
        good(len(list(target.parent.glob('.*.publishing')))==1,'retry creates no second partial copy')
    with cache_only_fixture() as original:
        receipt=cache.publish_cache(original);target=Path(receipt['cache_directory']);path=target/cache.MAP
        alias=target.parent/'synthetic-hardlink';os.link(path,alias)
        rejected(lambda:cache.publish_cache(original),'hardlinked cache data rejected')
        alias.unlink();target.chmod(0o755);path.unlink();target.chmod(0o555)
        rejected(lambda:cache.publish_cache(original),'missing cached map rejected instead of falling back to canonical origin')
    with cache_only_fixture() as original:
        receipt=cache.publish_cache(original);target=Path(receipt['cache_directory']);path=target/cache.MAP
        target.chmod(0o755);path.unlink();path.symlink_to(Path(original['target'])/'src/cui_said_map');target.chmod(0o555)
        rejected(lambda:cache.publish_cache(original),'symlink cache alias to canonical map rejected')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
