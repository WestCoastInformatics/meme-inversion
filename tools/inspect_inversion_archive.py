#!/usr/bin/env python3
"""Inventory and hash a completed inversion archive without extracting its files."""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
import tarfile

CONFIGS = ('etc/nci.cfg', 'etc/sct.cfg', 'etc/MDR.cfg', 'etc/RADLEX.cfg')

def role(path):
    parts = PurePosixPath(path).parts
    relative = '/'.join(parts[1:])
    name = parts[-1]
    if relative.startswith('orig/fromprovider/'):
        return 'publisher-input'
    if relative in ('src/sources.src', 'src/termgroups.src'):
        return 'prepared-metadata-input'
    if relative.startswith('src/'):
        return 'official-inversion-output-or-state'
    if relative.startswith('insert/'):
        return 'archived-insert-state-needs-version-review'
    if relative.startswith('orig/'):
        return 'prepared-intermediate-or-source-input'
    if relative.startswith('tmp/'):
        return 'derived-intermediate-or-scratch'
    if relative.startswith('bin/'):
        return 'execution-log' if name.endswith('.log') else 'source-code-or-script-variant'
    if relative.startswith('etc/qa/'):
        return 'validation-record'
    if relative.startswith('etc/'):
        if name.endswith('.cfg') or name.startswith('README'):
            return 'configuration-or-runbook'
        return 'preparation-metadata-or-derived-state'
    return 'unclassified-state'


def inspect(path, version, progress=None):
    archive_sha = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            archive_sha.update(chunk)
    entries = []
    metadata = {}
    with tarfile.open(path, mode='r|gz') as tar:
        for member in tar:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != version:
                raise ValueError('Unexpected archive path: ' + member.name)
            normalized = p.as_posix()
            item = {'path': normalized, 'size': member.size, 'mode': oct(member.mode),
                    'mtime': member.mtime, 'role': role(normalized)}
            if member.isfile():
                item['kind'] = 'file'
                sha = hashlib.sha256()
                lines = 0
                capture = bytearray() if normalized in tuple(version + '/' + name for name in CONFIGS + ('src/sources.src', 'src/termgroups.src')) and member.size <= 2000000 else None
                handle = tar.extractfile(member)
                for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
                    sha.update(chunk)
                    lines += chunk.count(b'\n')
                    if capture is not None:
                        capture.extend(chunk)
                item.update(sha256=sha.hexdigest(), newline_count=lines)
                if capture is not None:
                    text = capture.decode('utf-8', errors='replace')
                    summary = {'release_tags_seen': dict(collections.Counter(re.findall(r'20\d{2}(?:_\d{2}(?:_\d{2}|[A-Z])|[A-Z]{2})', text))), 'scope': 'Observed text tags; dependency roles not inferred'}
                    if normalized in tuple(version + '/' + name for name in CONFIGS):
                        wanted = {'VSAB', 'RSAB', 'VSABOLD', 'Release', 'EngNum', 'EngNumOld', 'SaidStart', 'SaidEnd', 'Atidstart', 'Rlidstart', 'AtidStart', 'RlidStart', 'ORIGDIR', 'TEMPDIR', 'SRCDIR', 'ETCDIR', 'MakeRoot', 'MakeTrans', 'HC.RootNodeSaid', 'HC.RootNodeCode', 'HC.RootNodeName'}
                        summary['settings'] = {}
                        for line in text.splitlines():
                            if line.lstrip().startswith('#') or '=' not in line:
                                continue
                            key, value = (x.strip() for x in line.split('=', 1))
                            if key in wanted or key.lower().startswith('file.'):
                                summary['settings'][key] = value
                    metadata[normalized] = summary
            elif member.isdir():
                item['kind'] = 'directory'
            elif member.issym() or member.islnk():
                item.update(kind='symlink' if member.issym() else 'hardlink', target=member.linkname)
            else:
                raise ValueError('Unsupported archive member type: ' + member.name)
            entries.append(item)
            if progress:
                progress(len(entries), member.name)
    if len({x['path'].rstrip('/') for x in entries}) != len(entries):
        raise ValueError('Archive contains duplicate member paths; a unique reference requires review')
    stages = {stage: [x for x in entries if x['path'].startswith(version + '/' + stage + '/') and x['kind'] == 'file'] for stage in ('src', 'insert')}
    return {'version': version, 'archive_path': str(path), 'archive_bytes': path.stat().st_size,
            'archive_sha256': archive_sha.hexdigest(), 'member_count': len(entries),
            'regular_file_bytes': sum(x['size'] for x in entries if x['kind'] == 'file'),
            'entries': entries, 'stages': stages, 'metadata_summary': metadata, 'extracted': False,
            'classification_scope': 'Provisional roles by location; code-level input/output review is still required'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.archive, args.version)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['archive_bytes', 'archive_sha256', 'member_count', 'regular_file_bytes', 'extracted']}))


if __name__ == '__main__':
    main()
