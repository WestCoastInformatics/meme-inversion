#!/usr/bin/env python3
"""Fake conditional streams and real local pipe-fd checks; no AWS calls."""
from contextlib import contextmanager
import base64
import copy
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

import capture_mth_prior as capture

VERSION = 'MTH_2023AB'
MAP = b'C0000001|123\nC0000002|456|\n'
FD_PATH_OPEN_VERIFIED = False


def archive(rows=None, mapping=MAP):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode='w:gz') as outgoing:
        for name, raw, kind in rows or [(VERSION + '/src/cui_said_map', mapping, tarfile.REGTYPE), (VERSION + '/src/unselected.large', b'x' * 1048576, tarfile.REGTYPE)]:
            member = tarfile.TarInfo(name);member.type = kind;member.size = len(raw) if kind == tarfile.REGTYPE else 0
            if kind == tarfile.SYMTYPE:member.linkname = '/external/never-followed'
            outgoing.addfile(member, io.BytesIO(raw) if kind == tarfile.REGTYPE else None)
    return result.getvalue()


def request(raw):
    return {'source': 'MTH', 'version': VERSION, 'bucket': 'nci-evs-meme', 'key': 'inv/sources/' + VERSION + '.tgz',
            'object_identity': {'ContentLength': len(raw), 'ETag': '"synthetic-etag"', 'LastModified': '2024-10-29T16:08:28+00:00', 'VersionId': None},
            'capture_id': 'synthetic-prior-map-fixture'}


class FakeClient:
    def __init__(self, raw, selected, after=None, get=None):
        self.raw = raw;self.expected = copy.deepcopy(selected['object_identity']);self.after = after
        self.get = self.expected if get is None else get;self.heads = 0;self.opens = 0

    def head(self, selected):
        self.heads += 1
        return self.after if self.after is not None and self.heads > 1 else copy.deepcopy(self.expected)

    @contextmanager
    def open(self, selected):
        assert selected['object_identity'] == self.expected
        self.opens += 1
        stream = io.BytesIO(self.raw)
        try:yield SimpleNamespace(stream=stream, finish=lambda: copy.deepcopy(self.get))
        finally:stream.close()


def no_clobber(staging, target):
    if target.exists() or target.is_symlink():raise FileExistsError('Synthetic collision')
    os.rename(staging, target)


@contextmanager
def environment():
    with tempfile.TemporaryDirectory(prefix='check-selective-mth-prior-') as directory:
        root = Path(directory).resolve()
        with patch.object(capture, 'ROOT', root), patch.object(capture, 'guard'), patch.object(capture, 'publish', side_effect=no_clobber), patch.object(capture.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024 ** 3)):
            yield root


def check():
    global FD_PATH_OPEN_VERIFIED
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def reject(label, raw=None, change_request=None, client_options=None, setup=None, collision=False):
        raw = archive() if raw is None else raw;selected = request(raw)
        if change_request:change_request(selected)
        client = FakeClient(raw, selected, **(client_options or {}))
        with environment() as root:
            if setup:setup(root)
            if collision:
                def occupied(staging, target):
                    target.mkdir();(target / 'unrelated').write_text('preserve me');raise FileExistsError('Collision')
                publication = patch.object(capture, 'publish', side_effect=occupied)
            else:publication = patch.object(capture, 'publish', side_effect=no_clobber)
            with publication:
                try:capture.capture(selected, client)
                except (ValueError, RuntimeError, OSError, tarfile.TarError, capture.zlib.error):pass
                else:raise AssertionError(label)
            good(not (root / VERSION / 'src/cui_said_map').exists(), label)
            good(not any(path.suffix == '.tgz' for path in root.rglob('*')), label + ': no full archive cached')
            if client.opens:
                good(bool(list(root.glob('.' + VERSION + '.prior-map-*/capture-failed.json'))), label + ': failure evidence retained')
            if collision:good((root / VERSION / 'unrelated').read_text() == 'preserve me', 'No-clobber publication preserves a competing prior folder')

    raw = archive();selected = request(raw);before = copy.deepcopy(selected);client = FakeClient(raw, selected)
    with environment() as root:
        receipt = capture.capture(selected, client);target = root / VERSION
        good((target / 'src/cui_said_map').read_bytes() == MAP, 'Only the exact selected prior identity bytes are published')
        good({path.relative_to(target).as_posix() for path in target.rglob('*')} == {'src', 'src/cui_said_map', capture.RECEIPT}, 'Published prior folder contains only map and small receipt')
        good(receipt['archive_sha256'] == capture.hashlib.sha256(raw).hexdigest() and receipt['archive_bytes'] == len(raw), 'Full compressed stream is consumed and hashed after the early selected map')
        good(receipt['map_identity']['rows'] == receipt['map_identity']['unique_cuis'] == 2, 'Actual CUI/positive-SAID records and duplicate-CUI scope are validated')
        good(client.heads == 2 and client.opens == 1, 'Before/after HEAD and one conditional stream are required')
        good(not receipt['archive_cached'] and not receipt['archived_code_executed'] and not receipt['production_eligible'], 'Receipt makes no archive-cache, code-execution or production claim')
        good('not a full source restoration or complete database snapshot' in receipt['scope'], 'Selective identity capture is explicitly not a full snapshot')
        good(not (target / 'src/cui_said_map').stat().st_mode & 0o222, 'Published map is readonly')
        good(selected == before, 'Original frozen request remains unchanged')
        cached = capture.capture(selected, client)
        good(cached == receipt and client.opens == 1, 'An exact sealed prior-map receipt is reused without a second S3 download')
        path = target / capture.RECEIPT;path.chmod(0o644);bad = json.loads(path.read_text());bad['archive_sha256'] = 'a' * 64;path.write_text(json.dumps(bad));path.chmod(0o444)
        try:capture.capture(selected, client)
        except ValueError:checks.append('A tampered existing receipt is rejected without replacement')
        else:raise AssertionError('Tampered receipt accepted')
    reject('Truncated gzip trailer is rejected even when frozen HEAD agrees with short bytes', raw=raw[:-8])
    corrupt = bytearray(raw);corrupt[-8] ^= 1
    reject('Corrupt gzip CRC fails despite a matching compressed byte count', raw=bytes(corrupt))
    reject('Duplicate selected map members are rejected', raw=archive([(VERSION + '/src/cui_said_map', MAP, tarfile.REGTYPE)] * 2))
    reject('Missing selected map is rejected', raw=archive([(VERSION + '/src/other', MAP, tarfile.REGTYPE)]))
    reject('Selected symlink is never followed', raw=archive([(VERSION + '/src/cui_said_map', b'', tarfile.SYMTYPE)]))
    reject('Archive traversal member is rejected', raw=archive([(VERSION + '/../escape', MAP, tarfile.REGTYPE)]))
    reject('Duplicate CUI rows are rejected', raw=archive(mapping=b'C0000001|123\nC0000001|456\n'))
    reject('Zero SAID is rejected', raw=archive(mapping=b'C0000001|0\n'))
    reject('Nonnumeric SAID is rejected', raw=archive(mapping=b'C0000001|other\n'))
    reject('Unknown CUI syntax is rejected', raw=archive(mapping=b'not-a-cui|123\n'))
    reject('Missing final record newline is rejected', raw=archive(mapping=b'C0000001|123'))
    reject('Empty selected map is rejected', raw=archive(mapping=b''))
    changed = copy.deepcopy(selected['object_identity']);changed['ETag'] = '"changed"'
    reject('An after-HEAD mutation prevents publication', client_options={'after': changed})
    reject('Different GetObject metadata prevents publication', client_options={'get': changed})
    reject('Expected complete container hash is enforced', change_request=lambda v: v.update(archive_sha256='0' * 64))
    reject('A different bucket is outside acquisition scope', change_request=lambda v: v.update(bucket='unrelated'))
    reject('The exact source release key is required', change_request=lambda v: v.update(key='inv/sources/MTH_2024AA.tgz'))
    reject('An existing unrelated prior folder is not overwritten', setup=lambda root: (root / VERSION).mkdir())
    reject('A competing prior folder cannot be clobbered at publication', collision=True)

    # Separate the platform pathname-open boundary from descriptor inheritance.
    # This Mac sandbox rejects reopening /dev/fd with O_TRUNC. Linux must prove
    # the actual pathname path; no production fallback silently caches a tgz.
    read_fd, write_fd = os.pipe()
    probe = subprocess.Popen([sys.executable, '-c', 'import sys;open(sys.argv[1],"wb").write(b"fd-probe")', '/dev/fd/' + str(write_fd)],
                             pass_fds=(write_fd,), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(write_fd)
    with os.fdopen(read_fd, 'rb') as incoming:probe_body = incoming.read()
    _, probe_error = probe.communicate(timeout=10)
    FD_PATH_OPEN_VERIFIED = probe.returncode == 0 and probe_body == b'fd-probe'
    good(FD_PATH_OPEN_VERIFIED or (sys.platform == 'darwin' and b'PermissionError' in probe_error),
         'Platform /dev/fd pathname open is independently probed; macOS sandbox limitation is explicit')
    # Real subprocess writes to the inherited descriptor directly. Arguments
    # retain the AWS outfile spelling and stdout remains separate JSON metadata.
    identity = request(raw);identity['object_identity']['VersionId'] = 'synthetic-version-id'
    metadata = json.dumps(identity['object_identity'])
    script = ('import base64,json,os,sys;args=sys.argv[1:];meta=json.loads(' + repr(metadata) + ');'
        'assert args[:2] in (["s3api","head-object"],["s3api","get-object"]);'
        '\nif args[1]=="get-object":\n'
        ' assert args[args.index("--if-match")+1]==meta["ETag"]\n'
        ' assert args[args.index("--version-id")+1]==meta["VersionId"]\n'
        ' assert args[-1].startswith("/dev/fd/")\n'
        ' with os.fdopen(int(args[-1].rsplit("/",1)[1]),"wb") as out:out.write(base64.b64decode(' + repr(base64.b64encode(raw).decode()) + '))\n'
        'print(json.dumps(meta))\n')
    actual_client = capture.AwsCliClient([sys.executable, '-c', script])
    with environment() as root:
        captured = capture.capture(identity, actual_client)
        good((root / VERSION / 'src/cui_said_map').read_bytes() == MAP and captured['get_object_identity'] == identity['object_identity'],
             'Real inherited pipe-fd subprocess carries archive body independently of stdout metadata and honors conditional/version arguments')
    return checks


if __name__ == '__main__':
    checks = check();print(json.dumps({'status': 'PASS', 'checks': len(checks), 'live_aws_calls': False,
                                      'fd_path_open_verified': FD_PATH_OPEN_VERIFIED}))
