#!/usr/bin/env python3
"""Exercise pull_s3.csh on dev using temporary fixtures and no external network."""
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
import tempfile
import uuid


def check(script):
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c':
        raise RuntimeError('These fixture checks are scoped to ncias-d3777-c')
    root = Path('/local/content/MEME/MEME5/inv/sources')
    token = 'NCI_REPLAY_SELFTEST_' + uuid.uuid4().hex
    owned = []
    results = []
    with tempfile.TemporaryDirectory(prefix='.pull-check-', dir=str(root)) as temp:
        fixture = Path(temp)
        mock = fixture / 'aws'
        mock.write_text('''#!/usr/bin/python3
import json,os,pathlib,shutil,sys
a=sys.argv[1:]
with open(os.environ['MOCK_CALLS'],'a') as f:f.write(json.dumps({'args':a,'profile':os.environ.get('AWS_PROFILE')})+'\\n')
if a[:2]==['s3api','head-object']:
 key=a[a.index('--key')+1]
 if os.environ.get('MOCK_FALLBACK')=='1' and key.endswith('.tgz'):sys.exit(4)
 print(json.dumps({'Metadata':{}}));sys.exit(0)
if a[:2]==['s3','cp']:
 target=pathlib.Path(a[2]).name
 if os.environ.get('MOCK_FAILURE')=='1':pathlib.Path(target).write_bytes(b'partial');sys.exit(23)
 shutil.copyfile(os.environ['MOCK_ARCHIVE'],target);sys.exit(0)
sys.exit(90)
''')
        mock.chmod(0o755)

        def execute(label, args, *, failure=False, fallback=False, existing_directory=False, existing_archive=False, invalid_tar=False):
            version = token + '_' + str(len(results))
            archive = root / (version + ('.tar.gz' if fallback else '.tgz'))
            directory = root / version
            owned.extend([archive, root / (version + '.tgz'), directory])
            payload = fixture / 'payload.tgz'
            if invalid_tar:
                payload.write_bytes(b'not a tar archive')
            else:
                with tarfile.open(payload, 'w:gz') as tar:
                    raw = b'fixture-output\n'
                    member = tarfile.TarInfo(version + '/artifact.txt')
                    member.size = len(raw)
                    tar.addfile(member, io.BytesIO(raw))
            if existing_directory:
                directory.mkdir()
                (directory / 'sentinel').write_bytes(b'preserve')
            if existing_archive:
                archive.write_bytes(b'preserve-archive')
            calls = fixture / 'calls.jsonl'
            calls.unlink(missing_ok=True)
            env = dict(os.environ, AWS_BIN=str(mock), AWS_PROFILE='fixture-profile', MOCK_CALLS=str(calls),
                       MOCK_ARCHIVE=str(payload), MOCK_FAILURE='1' if failure else '0', MOCK_FALLBACK='1' if fallback else '0')
            command = ['unshare', '--user', '--map-root-user', '--net', 'tcsh', '-f', str(script)]
            command += [version if value == '<VERSION>' else value for value in args]
            p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=15, env=env)
            records = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            return version, archive, directory, p, records

        try:
            _, a, d, p, calls = execute('download-only', ['inv', '<VERSION>', '--download-only'])
            assert p.returncode == 0 and a.is_file() and not d.exists(), p.stdout.decode()
            assert all(x['profile'] == 'fixture-profile' for x in calls)
            results.append('download-only retains archive without extraction; profile passed through')
            _, a, d, p, _ = execute('keep', ['inv', '<VERSION>', '--keep-archive'])
            assert p.returncode == 0 and a.exists() and (d / 'artifact.txt').read_bytes() == b'fixture-output\n', p.stdout.decode()
            results.append('keep-archive extracts and retains archive')
            _, a, d, p, _ = execute('legacy', ['inv', '<VERSION>'])
            assert p.returncode == 0 and not a.exists() and (d / 'artifact.txt').exists(), p.stdout.decode()
            results.append('legacy two-argument extraction removes archive')
            _, a, d, p, _ = execute('failed-download', ['inv', '<VERSION>', '--keep-archive'], failure=True)
            assert p.returncode != 0 and not d.exists() and a.read_bytes() == b'partial', p.stdout.decode()
            results.append('failed download never extracts or reports success')
            _, a, d, p, _ = execute('failed-extraction', ['inv', '<VERSION>', '--keep-archive'], invalid_tar=True)
            assert p.returncode != 0 and a.exists(), p.stdout.decode()
            results.append('failed extraction retains archive and reports failure')
            for args in [['invalid', '<VERSION>'], ['inv', '<VERSION>', '--invalid'], ['ncim', '<VERSION>', '--download-only']]:
                _, _, _, p, calls = execute('invalid-arguments', args)
                assert p.returncode != 0 and not calls, p.stdout.decode()
                results.append('invalid argument rejected before AWS: ' + ' '.join(args))
            _, a, d, p, _ = execute('existing-version-download', ['inv', '<VERSION>', '--download-only'], existing_directory=True)
            assert p.returncode == 0 and a.exists() and (d / 'sentinel').read_bytes() == b'preserve' and not (d / 'artifact.txt').exists(), p.stdout.decode()
            results.append('download-only leaves an existing source folder untouched')
            _, a, d, p, calls = execute('existing-version-restore', ['inv', '<VERSION>'], existing_directory=True)
            assert p.returncode != 0 and not calls and (d / 'sentinel').read_bytes() == b'preserve', p.stdout.decode()
            results.append('restore refuses to overwrite an existing source folder')
            _, a, d, p, _ = execute('existing-archive', ['inv', '<VERSION>', '--download-only'], existing_archive=True)
            assert p.returncode != 0 and a.read_bytes() == b'preserve-archive' and not d.exists(), p.stdout.decode()
            results.append('existing local archive is never overwritten')
            _, a, d, p, _ = execute('fallback', ['inv', '<VERSION>', '--download-only'], fallback=True)
            assert p.returncode == 0 and a.is_file() and not d.exists(), p.stdout.decode()
            results.append('legacy tar.gz fallback works with download-only')
        finally:
            for p in set(owned):
                if p.parent != root or not p.name.startswith(token):
                    raise RuntimeError('Refusing fixture cleanup outside owned paths')
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
    return {'passed': len(results), 'checks': results, 'network': 'disabled', 'real_aws_calls': 0, 'fixtures_removed': True}
