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


def file_sha(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):value.update(chunk)
    return value.hexdigest()

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
    archive_sha = file_sha(path)
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
            'archive_sha256': archive_sha, 'member_count': len(entries),
            'regular_file_bytes': sum(x['size'] for x in entries if x['kind'] == 'file'),
            'entries': entries, 'stages': stages, 'metadata_summary': metadata, 'extracted': False,
            'classification_scope': 'Provisional roles by location; code-level input/output review is still required'}


def attribute_stage_relation(path, inventory):
    """Prove the original attribute bytes precede only semantic-type additions.

    This checks an archived stage boundary. It does not regenerate either file,
    remove legitimate semantic types from the prefix, or certify its semantics.
    """
    version = inventory['version']
    names = [version + '/src/attributes.orig', version + '/src/attributes.src']
    entries = [[item for item in inventory['entries'] if item['path'] == name] for name in names]
    if any(len(items) != 1 or items[0]['kind'] != 'file' for items in entries):
        raise ValueError('Attribute stages require unique regular archive members')
    original, final = (items[0] for items in entries)
    if not original['size'] or not original['newline_count'] or final['size'] < original['size']:
        raise ValueError('An empty or longer original cannot establish this stage boundary')
    if file_sha(path) != inventory['archive_sha256']:
        raise ValueError('Frozen archive bytes changed')
    whole, prefix = hashlib.sha256(), hashlib.sha256()
    observed = prefix_rows = suffix_rows = found = original_seen = 0
    prefix_names, suffix_names, prefix_widths = collections.Counter(), collections.Counter(), collections.Counter()
    with tarfile.open(path, mode='r|gz') as archive:
        for member in archive:
            name = PurePosixPath(member.name).as_posix()
            if name == names[0]:
                if not member.isfile() or member.size != original['size'] or original_seen:
                    raise ValueError('Original attribute member differs from inventory')
                original_seen += 1;value = hashlib.sha256();rows = 0
                handle = archive.extractfile(member)
                for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
                    value.update(chunk);rows += chunk.count(b'\n')
                if value.hexdigest() != original['sha256'] or rows != original['newline_count']:
                    raise ValueError('Original attribute bytes differ from inventory')
                continue
            if name != names[1]:continue
            if not member.isfile() or member.size != final['size'] or found:
                raise ValueError('Final attribute member differs from inventory')
            found += 1
            for raw in archive.extractfile(member):
                observed += len(raw);whole.update(raw)
                fields = raw.removesuffix(b'\n').split(b'|')
                if observed <= original['size']:
                    prefix.update(raw);prefix_rows += 1;prefix_widths[len(fields)] += 1
                    if len(fields) > 3:prefix_names[fields[3].decode('utf-8', errors='replace')] += 1
                else:
                    if observed - len(raw) < original['size']:
                        raise ValueError('Original byte boundary splits an attribute record')
                    if len(fields) != 15 or fields[3] != b'SEMANTIC_TYPE':
                        raise ValueError('Post-original records include an unreviewed non-semantic-type addition')
                    suffix_rows += 1;suffix_names['SEMANTIC_TYPE'] += 1
    if original_seen != 1 or found != 1 or observed != final['size'] or whole.hexdigest() != final['sha256']:
        raise ValueError('Final attribute bytes differ from frozen inventory')
    if prefix.hexdigest() != original['sha256'] or prefix_rows != original['newline_count']:
        raise ValueError('Original attributes are not the complete unchanged prefix')
    if prefix_rows + suffix_rows != final['newline_count'] or file_sha(path) != inventory['archive_sha256']:
        raise ValueError('Attribute counts or archive bytes changed')
    return {'status': 'PRE_INSERTION_PREFIX_VERIFIED' if suffix_rows else 'IDENTICAL_ATTRIBUTE_STAGES',
            'archive_sha256': inventory['archive_sha256'], 'original_member': names[0], 'final_member': names[1],
            'original_bytes': original['size'], 'original_rows': prefix_rows, 'final_rows': prefix_rows + suffix_rows,
            'original_sha256': original['sha256'], 'final_sha256': final['sha256'],
            'appended_rows': suffix_rows, 'appended_attribute_names': dict(suffix_names),
            'original_attribute_names': dict(prefix_names), 'original_field_counts': dict(prefix_widths),
            'original_prefix_byte_exact': True, 'original_semantic_types_retained': prefix_names['SEMANTIC_TYPE'],
            'candidate_executed': False,
            'scope': 'Frozen archive stage relationship only; candidate replay and independent semantic validation remain separate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-attribute-stages', action='store_true', help='Verify attributes.orig as the exact prefix followed only by semantic types')
    args = parser.parse_args()
    result = inspect(args.archive, args.version)
    if args.verify_attribute_stages:
        result['attribute_stage_relation'] = attribute_stage_relation(args.archive, result)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['archive_bytes', 'archive_sha256', 'member_count', 'regular_file_bytes', 'extracted']}))


if __name__ == '__main__':
    main()
