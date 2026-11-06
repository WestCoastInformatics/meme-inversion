#!/usr/bin/env python3
"""Exercise reference acquisition with real archives/files and stubbed S3 calls."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import acquire_inversion_reference as acquire


def bundle(version, duplicate=False, changed=False):
    stream = io.BytesIO()
    cfg = 'MDR.cfg' if version.startswith('MDR_') else 'RADLEX.cfg'
    items = [('etc/' + cfg, b'VSAB = ' + version.encode() + b'\nSaidStart = 100\nHC.RootNodeSaid = 42\n'),
             ('bin/engine.pl', b'fixture producer\n'), ('bin/inactive.csh', b'fixture-private-marker\n'),
             ('orig/native.txt', b'changed native input\n' if changed else b'native input\n'), ('src/sources.src', b'fixture metadata\n'),
             ('src/attributes.orig', b'original pre-insertion row\n'),
             ('src/attributes.src', b'original pre-insertion row\nappended semantic type\n')]
    if duplicate:items.append(items[-1])
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, raw in items:
            info = tarfile.TarInfo(version + '/' + name);info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


def check():
    values = []
    def require(condition, label):
        assert condition, label
        values.append(label)
    def rejected(action, label):
        try:action()
        except (ValueError, RuntimeError):values.append(label)
        else:raise AssertionError(label)
    for source, version in [('NCI', 'NCI_2026_10D'), ('SNOMEDCT_US', 'SNOMEDCT_US_2026_09_01'),
                            ('MTH', 'MTH_2026AA'), ('MDR', 'MDR_29_1'), ('RADLEX', 'RADLEX_4_3')]:
        acquire.validate_release(source, version);values.append('Reviewed acquisition source accepted: ' + source)
    for source, version in [('UNKNOWN', 'UNKNOWN_1'), ('MDR', 'RADLEX_4_3'), ('MDR', 'MDR_../x'),
                            ('MDR', 'MDR_1;echo'), ('MDR', 'MDR_1\n'), ([], 'MDR_1'), ('MDR', None)]:
        rejected(lambda: acquire.validate_release(source, version), 'Invalid source/version rejected: ' + repr((source, version)))
    with tempfile.TemporaryDirectory(prefix='reference-acquisition-') as temporary:
        base = Path(temporary)
        helper = base / 'pull_s3.csh';helper.write_bytes(b'reviewed fixture helper\n')
        for source, version in [('MDR', 'MDR_29_1'), ('RADLEX', 'RADLEX_4_3')]:
            for scenario in ('normal', 'changed-object', 'duplicate-member', 'unreceipted-cache', 'missing-frozen-cache'):
                root = base / (source + '-' + scenario);root.mkdir()
                raw = bundle(version, duplicate=scenario == 'duplicate-member')
                identity = {'ContentLength': len(raw), 'ETag': 'fixture', 'LastModified': '2026-11-06T00:00:00+00:00', 'VersionId': None}
                request = {'source': source, 'version': version, 'engine_ref': '1' * 40,
                           'pull_helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                           'expected_code': [{'path': version + '/bin/engine.pl', 'sha256': hashlib.sha256(b'fixture producer\n').hexdigest()}]}
                calls = []
                def run(command, **options):
                    calls.append(command)
                    if command[0] == '/usr/bin/aws':
                        observed = dict(identity)
                        if scenario == 'changed-object' and len(calls) > 1:observed['ETag'] = 'changed'
                        return SimpleNamespace(returncode=0, stdout=json.dumps(observed), stderr='')
                    assert command == ['tcsh', '-f', str(helper), 'inv', version, '--download-only']
                    assert options['umask'] == 0o077 and options['env']['AWS_PROFILE'] == 'meme'
                    path = root / (version + '.tgz');path.write_bytes(raw);path.chmod(0o600)
                    return SimpleNamespace(returncode=0, stdout=b'downloaded')
                archive = root / (version + '.tgz')
                reference = root / (version + '.tgz.reference.json')
                if scenario == 'unreceipted-cache':archive.write_bytes(raw)
                if scenario == 'missing-frozen-cache':reference.write_text(json.dumps({'source': source, 'version': version}))
                with patch.multiple(acquire, ROOT=root, PULL=helper), patch('socket.gethostname', return_value='ncias-d3777-c'), \
                        patch('pwd.getpwuid', return_value=SimpleNamespace(pw_name='tomcata')), patch.object(acquire.subprocess, 'run', side_effect=run):
                    quiet = lambda *args, **kwargs: None
                    if scenario != 'normal':
                        rejected(lambda: acquire.acquire(request, quiet), source + ' rejects ' + scenario)
                        require(not (root / version).exists(), source + ' failure never restores a source tree: ' + scenario)
                        if scenario in ('unreceipted-cache', 'missing-frozen-cache'):
                            require(not calls, source + ' ambiguous cache does not trigger a replacement download')
                        continue
                    result = acquire.acquire(request, quiet)
                    inventory = json.loads((root / (version + '.tgz.inventory.json')).read_text())
                    require(result['code_matches_snapshot'] and result['archive_sha256'] == hashlib.sha256(raw).hexdigest(), source + ' freezes archive and imported producer hashes')
                    require(archive.stat().st_mode & 0o777 == 0o400 and not (root / version).exists(), source + ' archive is owner-only and never extracted')
                    require('fixture-private-marker' not in json.dumps(result) + json.dumps(inventory), source + ' inventory never publishes inactive script content')
                    metadata = inventory['metadata_summary'][version + '/etc/' + ('MDR.cfg' if source == 'MDR' else 'RADLEX.cfg')]
                    require(metadata['settings']['HC.RootNodeSaid'] == '42', source + ' saved external root identity is visible as configuration evidence')
                    outputs = {item['path'].rsplit('/', 1)[1]: item for item in inventory['stages']['src']}
                    require(outputs['attributes.orig']['newline_count'] == 1 and outputs['attributes.src']['newline_count'] == 2 and
                            outputs['attributes.orig']['sha256'] != outputs['attributes.src']['sha256'], source + ' pre/post-insertion attribute stages remain distinct')
                    before_calls = len(calls)
                    require(not acquire.acquire(request, quiet)['downloaded_this_run'] and len(calls) == before_calls, source + ' frozen cache is reused without silently selecting a new S3 object')
                    prior_reference = reference.read_bytes()
                    archive.chmod(0o600);archive.write_bytes(bundle(version, changed=True))
                    rejected(lambda: acquire.acquire(request, quiet), source + ' altered cached archive is rejected')
                    require(reference.read_bytes() == prior_reference and not (root / ('.' + version + '.reference.lock')).exists(), source + ' failure preserves receipt and releases the acquisition lock')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'reference acquisition checks passed')
