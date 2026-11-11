#!/usr/bin/env python3
"""Actual confined materialization/checkpoint/no-clobber checks; no S3 calls."""
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import capture_mth_prepared as capture
import check_curate_archived_mth as fixtures
import execute_release_mth as execution


class FakeS3:
    def __init__(self, native):
        self.native = native
        self.calls = []
        self.head_overrides = {}
        self.response_override = {}
        self.fail_role = None
        self.fail_once = False
        self.change_after_role = None
        self.request = {'source': 'MTH', 'version': native['version'], 'subset_directory': 'subset3/METASUBSET',
                        'bucket': 'nci-evs-meme', 'objects': []}
        self.data = {}
        self.heads = {}
        for index, descriptor in enumerate(native['prepared']['files']):
            raw = Path(descriptor['uri'].removeprefix('file://')).read_bytes()
            key = 'mr/umls/' + native['version'][4:] + '/subset3/METASUBSET/' + descriptor['role']
            head = {'ContentLength': len(raw), 'ETag': '"SYNTHETIC-opaque-multipart-' + str(index) + '-2"',
                    'LastModified': '2024-01-01T12:00:00+00:00', 'VersionId': 'SYNTHETIC-version-' + str(index) if index % 2 else None}
            self.request['objects'].append({'role': descriptor['role'], 'key': key, 'head': copy.deepcopy(head)})
            self.data[key], self.heads[key] = raw, head

    def head_object(self, **arguments):
        self.calls.append(('HEAD', copy.deepcopy(arguments)))
        value = copy.deepcopy(self.heads[arguments['Key']]);value.update(self.head_overrides.get(arguments['Key'], {}))
        return value

    def get_object(self, **arguments):
        self.calls.append(('GET', copy.deepcopy(arguments)))
        key = arguments['Key'];role = key.split('/')[-1]
        assert arguments['Bucket'] == 'nci-evs-meme'
        assert arguments['IfMatch'] == self.heads[key]['ETag']
        if self.heads[key]['VersionId'] is None:
            assert 'VersionId' not in arguments
        else:
            assert arguments['VersionId'] == self.heads[key]['VersionId']
        start, end = map(int, arguments['Range'].removeprefix('bytes=').split('-'))
        raw = self.data[key][start:end + 1]
        if role == self.fail_role and self.fail_once:
            self.fail_once = False
            class Interrupted(io.BytesIO):
                def __init__(self, value):
                    super().__init__(value);self.first = True
                def read(self, count):
                    if self.first:
                        self.first = False
                        return super().read(min(count, 7))
                    raise OSError('SYNTHETIC interrupted conditional body')
            body = Interrupted(raw)
        else:
            body = io.BytesIO(raw)
        value = {**self.heads[key], 'ContentLength': len(raw),
                 'ContentRange': 'bytes ' + str(start) + '-' + str(end) + '/' + str(len(self.data[key])), 'Body': body}
        value.update(self.response_override)
        if role == self.change_after_role:self.head_overrides[key] = {'ETag': '"SYNTHETIC-CHANGED"'}
        return value


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def rejects(function, label):
        try:
            function()
        except (RuntimeError, ValueError, OSError):
            passed.append(label)
            return
        raise AssertionError(label)

    with tempfile.TemporaryDirectory(prefix='mth-first-capture-') as temporary:
        base = Path(temporary).resolve()
        origin = base / 'fixture';origin.mkdir()
        native, _, _ = fixtures.fixture(origin, skipped=True)
        environment = [patch.object(capture, 'MEME_ROOT', base / 'MEME5'),
                       patch.object(capture.socket, 'gethostname', return_value='ncias-d3777-c.nci.nih.gov'),
                       patch.object(capture.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='tomcata')),
                       patch.object(capture.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024 ** 3)),
                       patch.object(capture, 'CHUNK_BYTES', 32)]
        for item in environment:item.start()
        try:
            client = FakeS3(native);request = client.request
            def reset(name):
                root = base / name
                capture.MEME_ROOT = root
                return root / 'mr/umls' / request['version'][4:] / request['subset_directory']
            # Selection is independent of ETag checksum folklore and preserves
            # version-specific GETs when a VersionId exists.
            selected = capture.select(request)
            good(len(selected['objects']) == 11 and any(item['head']['VersionId'] is None for item in selected['objects']), 'exact native selection accepts opaque ETags and explicit null/version IDs')
            alias = copy.deepcopy(request)
            for item in alias['objects']:item['object_identity'] = item.pop('head')
            good(capture.select(alias) == selected, 'inventory object_identity spelling normalizes without changing facts')
            invalid = copy.deepcopy(request);invalid['objects'][0]['object_identity'] = invalid['objects'][0]['head']
            rejects(lambda: capture.select(invalid), 'ambiguous two HEAD spellings rejected')
            invalid = copy.deepcopy(request);invalid['objects'].pop()
            rejects(lambda: capture.select(invalid), 'partial native role list rejected')
            invalid = copy.deepcopy(request);invalid['objects'][0]['key'] = 'mr/umls/OTHER/subset3/METASUBSET/MRAUI.RRF'
            rejects(lambda: capture.select(invalid), 'different release object path rejected')
            invalid = copy.deepcopy(request);invalid['subset_directory'] = '../outside'
            rejects(lambda: capture.select(invalid), 'arbitrary destination rejected')
            invalid = copy.deepcopy(request);invalid['objects'][0]['head']['ContentLength'] = True
            rejects(lambda: capture.select(invalid), 'boolean object length rejected')
            invalid = copy.deepcopy(request);invalid['objects'][0]['head'].pop('VersionId')
            rejects(lambda: capture.select(invalid), 'unpinned VersionId rejected')
            invalid = copy.deepcopy(request);invalid['objects'][0]['head']['LastModified'] = '2024-01-01T12:00:00'
            rejects(lambda: capture.select(invalid), 'timezone-free LastModified rejected')
            target = reset('guard')
            with patch.object(capture.socket, 'gethostname', return_value='meme-edit'):
                rejects(lambda: capture.capture(request, client), 'production host rejected before filesystem writes')
            good(not capture.MEME_ROOT.exists(), 'rejected host creates no directories')
            with patch.object(capture.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='someone-else')):
                rejects(lambda: capture.capture(request, client), 'different effective account rejected')
            target = reset('disk')
            payload = sum(item['head']['ContentLength'] for item in request['objects'])
            with patch.object(capture.shutil, 'disk_usage', return_value=SimpleNamespace(free=payload + capture.CAPTURE_RESERVE - 1)):
                rejects(lambda: capture.capture(request, client, lambda _: None), 'payload plus 12GiB capture reservation enforced')
            good(not target.exists() and not any(call[0] == 'GET' for call in client.calls), 'capacity failure downloads no native payload')
            target = reset('before-head');client = FakeS3(native)
            client.head_overrides[request['objects'][0]['key']] = {'LastModified': '2024-02-02T00:00:00Z'}
            rejects(lambda: capture.capture(request, client, lambda _: None), 'before-HEAD mutation rejected')
            good(not any(call[0] == 'GET' for call in client.calls) and not target.exists(), 'object mutation blocks all downloads/publication')
            target = reset('success');client = FakeS3(native)
            receipt = capture.capture(request, client, lambda _: None)
            good(target.is_dir() and receipt['complete'] and set(path.name for path in target.iterdir()) == {*execution.RRF_WIDTHS, capture.RECEIPT}, 'actual directory published atomically with exact eleven roles and seal')
            good(all((target / name).read_bytes() == client.data[next(item['key'] for item in request['objects'] if item['role'] == name)] for name in execution.RRF_WIDTHS), 'published bytes equal independent authoritative fake S3 bodies')
            good(all(not (path.stat().st_mode & 0o222) for path in target.iterdir()), 'all native bytes and capture receipt are read-only')
            good(receipt['capture_reserve_bytes'] == 12 * 1024 ** 3 and not receipt['execution_capacity_gate_satisfied'], 'capture does not lower or satisfy independent execution floor')
            good(receipt['facts']['MRCXT.RRF']['rows'] == 0 and receipt['facts']['MRCXT.RRF']['bytes'] == 0, 'legitimate empty optional native input preserved')
            good(sum(receipt['facts']['MRAUI.RRF']['versions'].values()) == receipt['facts']['MRAUI.RRF']['rows'] and 'version_relations' in receipt['facts']['MRCUI.RRF'], 'complete history release/relation counts captured')
            good(receipt['mrsab_data_b64'] == native['prepared']['mrsab_data_b64'], 'small full MRSAB body captured with its real SHA identity')
            good(all(item['sha256'] == capture.sha((target / item['role']).read_bytes()) and item['bytes'] == (target / item['role']).stat().st_size for item in receipt['files']), 'new typed descriptors contain computed full SHA256 and size')
            gets = sum(call[0] == 'GET' for call in client.calls)
            again = capture.capture(request, client, lambda _: None)
            good(again == receipt and sum(call[0] == 'GET' for call in client.calls) == gets, 'exact sealed replay rehashes locally without duplicate S3 download')
            good(all(call[1].get('IfMatch') for call in client.calls if call[0] == 'GET'), 'every ranged GET is conditional on pinned ETag')
            changed = target / 'MRCONSO.RRF';changed.chmod(0o644)
            rejects(lambda: capture.capture(request, client, lambda _: None), 'writable published native input rejected')
            changed.write_bytes(changed.read_bytes() + b'x');changed.chmod(0o444)
            rejects(lambda: capture.capture(request, client, lambda _: None), 'published byte mutation rejected')
            target = reset('existing-empty');target.mkdir(parents=True)
            client = FakeS3(native)
            rejects(lambda: capture.capture(request, client, lambda _: None), 'unsealed existing target never overwritten even when empty')
            good(target.is_dir() and not list(target.iterdir()) and not any(call[0] == 'GET' for call in client.calls), 'existing empty target unchanged')
            # Actual kernel publication refuses an empty destination as well as
            # populated ones; ordinary os.rename would replace the empty one.
            source = base / 'atomic-source';source.mkdir();(source / 'proof').write_text('retained')
            destination = base / 'atomic-target';destination.mkdir()
            rejects(lambda: capture.publish(source, destination), 'kernel no-clobber rejects existing empty publication target')
            good((source / 'proof').read_text() == 'retained' and not list(destination.iterdir()), 'failed atomic publication preserves both directories')
            target = reset('publication-failure');client = FakeS3(native)
            with patch.object(capture, 'publish', side_effect=OSError('SYNTHETIC publication interrupted')):
                rejects(lambda: capture.capture(request, client, lambda _: None), 'safe publication failure retains complete sealed stage')
            gets = sum(operation == 'GET' for operation, _ in client.calls)
            resumed_seal = capture.capture(request, client, lambda _: None)
            good(resumed_seal['complete'] and target.is_dir() and sum(operation == 'GET' for operation, _ in client.calls) == gets,
                 'sealed publication retry verifies bytes and performs no duplicate download')
            target = reset('stream-interrupt');client = FakeS3(native);client.fail_role = 'MRCONSO.RRF';client.fail_once = True
            rejects(lambda: capture.capture(request, client, lambda _: None), 'conditional body interruption retains private checkpoint')
            stages = list(target.parent.glob('.METASUBSET.capture-*'));good(len(stages) == 1 and not target.exists(), 'failure publishes no partial directory or duplicate stage')
            checkpoint = json.loads((stages[0] / capture.STATE).read_text())
            good(checkpoint['progress']['MRCONSO.RRF']['bytes'] == 7 and 'MRAUI.RRF' in checkpoint['completed'], 'interrupted byte prefix and earlier complete role retained')
            calls = len(client.calls)
            resumed = capture.capture(request, client, lambda _: None)
            later = [arguments for operation, arguments in client.calls[calls:] if operation == 'GET']
            good(target.is_dir() and resumed['complete'] and not any(item['Key'].endswith('/MRAUI.RRF') for item in later), 'retry reuses earlier completed native role')
            good(next(item for item in later if item['Key'].endswith('/MRCONSO.RRF'))['Range'].startswith('bytes=7-'), 'retry resumes at exact verified prefix without duplicate prefix download')
            target = reset('tampered-part');client = FakeS3(native);client.fail_role = 'MRCONSO.RRF';client.fail_once = True
            rejects(lambda: capture.capture(request, client, lambda _: None), 'second confined interrupt created')
            stage = next(target.parent.glob('.METASUBSET.capture-*'))
            partial = stage / 'MRCONSO.RRF.part';partial.write_bytes(b'changed')
            count = len(client.calls)
            rejects(lambda: capture.capture(request, client, lambda _: None), 'tampered retained prefix rejected')
            good(not any(operation == 'GET' for operation, _ in client.calls[count:]) and not target.exists(), 'tampered partial cannot cause fresh or duplicate payload download')
            target = reset('after-head');client = FakeS3(native);client.change_after_role = 'MRCONSO.RRF'
            rejects(lambda: capture.capture(request, client, lambda _: None), 'post-download HEAD change rejected')
            good(not target.exists(), 'post-HEAD mutation prevents publication')
            target = reset('bad-response');client = FakeS3(native);client.response_override = {'ContentRange': 'bytes 0-1/2'}
            rejects(lambda: capture.capture(request, client, lambda _: None), 'inconsistent conditional range response rejected')
            good(not target.exists(), 'bad ranged body cannot publish')
            target = reset('bad-native');client = FakeS3(native)
            key = next(item['key'] for item in request['objects'] if item['role'] == 'MRCONSO.RRF')
            client.data[key] = b'x' * len(client.data[key])
            rejects(lambda: capture.capture(request, client, lambda _: None), 'actual malformed RRF body rejected even with matching pinned size')
            good(not target.exists(), 'malformed native bundle never published')
            target = reset('no-current-mth');client = FakeS3(native)
            key = next(item['key'] for item in request['objects'] if item['role'] == 'MRSAB.RRF')
            client.data[key] = client.data[key].replace(native['version'].encode(), b'MTH_1900AA')
            rejects(lambda: capture.capture(request, client, lambda _: None), 'prepared MRSAB wrong release rejected')
            # AWS CLI adapter is tested against actual subprocess arguments,
            # with the process boundary confined rather than calling S3.
            incoming = base / 'cli';incoming.mkdir();adapter = capture.AwsCliS3(incoming)
            call_arguments = {'Bucket': 'nci-evs-meme', 'Key': key, 'VersionId': 'SYNTHETIC-version',
                              'IfMatch': '"SYNTHETIC-etag"', 'Range': 'bytes=0-31'}
            def process(argv, **kwargs):
                good(argv[:3] == ['/usr/bin/aws', 's3api', 'get-object'] and '--if-match' in argv and '--version-id' in argv and '--range' in argv, 'AWS CLI uses explicit conditional/version/range flags')
                good(kwargs['env']['AWS_PROFILE'] == 'meme', 'existing AWS profile retained')
                Path(argv[-1]).write_bytes(b'SYNTHETIC captured body')
                return SimpleNamespace(returncode=0, stdout='{"ContentLength":23,"ETag":"\\"SYNTHETIC-etag\\""}', stderr='')
            with patch.object(capture.subprocess, 'run', side_effect=process):
                result = adapter.get_object(**call_arguments)
                good(result['Body'].read(100) == b'SYNTHETIC captured body', 'AWS CLI completed range body exposed to common validator')
                result['Body'].close()
            good(not list(incoming.iterdir()), 'successful private CLI body removed after consumption')
            with patch.object(capture.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='SYNTHETIC transfer failure')):
                rejects(lambda: adapter.get_object(**call_arguments), 'unconfirmed CLI response retained on command failure')
            with patch.object(capture.subprocess, 'run') as process_mock:
                rejects(lambda: adapter.get_object(**call_arguments), 'uncertain CLI response never overwritten or blindly redownloaded')
                good(not process_mock.called and len(list(incoming.iterdir())) == 1, 'uncertain response blocks duplicate transfer and preserves evidence')
        finally:
            for item in reversed(environment):item.stop()
    print(json.dumps({'passed': len(passed), 'checks': passed}, indent=2))


if __name__ == '__main__':check()
