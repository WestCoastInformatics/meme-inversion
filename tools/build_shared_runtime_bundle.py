#!/usr/bin/env python3
"""Build an exact shared-runtime bundle from a recorded production Git snapshot."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def build(repository, source_ref, expected_host, expected_cshrc_sha256=None):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repository), *args])
    commit = git('rev-parse', source_ref + '^{commit}').decode().strip()
    manifest = json.loads(git('show', commit + ':baseline/manifest.json'))
    records = {x['repository_path']: x for x in manifest['files'] if x['repository_path'].startswith(('INV/', 'ENV/'))}
    archive = git('archive', '--format=tar', commit, 'INV', 'ENV')
    files = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
        for member in tar:
            if member.isdir():
                continue
            if not member.isfile() or member.name not in records:
                raise RuntimeError('Unexpected shared archive member: ' + member.name)
            raw = tar.extractfile(member).read()
            record = records[member.name]
            sha = hashlib.sha256(raw).hexdigest()
            if sha != record['imported_sha256']:
                raise RuntimeError('Snapshot/manifest disagreement: ' + member.name)
            files.append({'path': member.name, 'sha256': sha, 'mode': record['mode'], 'data_b64': base64.b64encode(raw).decode()})
    if {x['path'] for x in files} != set(records):
        raise RuntimeError('Incomplete shared runtime bundle')
    checks = []
    for name in ['create_rolegroups.pl', 'create_tref.pl', 'delete_dup_tref_lines.pl', 'tref_2_relational_files.pl', 'invert_NCI.pl']:
        path = 'sources/NCI_2026_10D/bin/' + name
        raw = git('show', commit + ':' + path)
        shebang = raw.splitlines()[0].decode('ascii')
        interpreter = Path(shebang[2:].split()[0]).name
        if not shebang.startswith('#!') or interpreter not in ('perl', 'tcsh'):
            raise RuntimeError('Unsupported compile-check interpreter: ' + path)
        checks.append({'path': path, 'interpreter': interpreter, 'sha256': hashlib.sha256(raw).hexdigest(), 'data_b64': base64.b64encode(raw).decode()})
    return {'schema_version': 1, 'source_ref': source_ref, 'source_commit': commit, 'expected_host': expected_host,
            'expected_cshrc_sha256': expected_cshrc_sha256, 'files': files, 'compile_checks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--source-ref', default='production-snapshot-20261103')
    parser.add_argument('--expected-host', default='ncias-d3777-c')
    parser.add_argument('--expected-cshrc-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    payload = build(args.repository, args.source_ref, args.expected_host, args.expected_cshrc_sha256)
    args.output.write_text(json.dumps(payload, separators=(',', ':')))
    args.output.chmod(0o600)
    print(json.dumps({'source_commit': payload['source_commit'], 'files': len(payload['files']), 'compile_checks': len(payload['compile_checks']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
