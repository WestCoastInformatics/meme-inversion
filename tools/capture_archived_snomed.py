#!/usr/bin/env python3
"""Read-only TAR capture of archived SNOMED evidence and physical RF2 facts.

No extraction, database query, source execution or network operation is used.
The first pass captures small producer/metadata inputs and oracle scope; a second
pass scans only the native files selected by that archived producer's cfg.
"""
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import tarfile

ROLES = {
    'CONCEPTS': 'rf2-concepts', 'DESCRIPTIONS': 'rf2-descriptions', 'RELATIONS': 'rf2-relationships',
    'CONCRETERELS': 'rf2-concrete-values', 'DEFINITIONS': 'rf2-text-definitions',
    'REFSETS': 'rf2-refset-descriptor', 'DESCRFORMAT': 'rf2-description-type',
    'MODULEDEP': 'rf2-module-dependency', 'LANGUAGESETS': 'rf2-language',
    'SIMPLEMAPS': 'rf2-simple-map', 'EXTENDEDMAPS': 'rf2-extended-map',
    'ATTRIBUTES': 'rf2-attribute-value', 'SUBSETS': 'rf2-simple-refset', 'ASSOCIATIONS': 'rf2-association',
}
SMALL = ('etc/sct.cfg', 'src/sources.src', 'src/termgroups.src', 'bin/invert_rf2.pl', 'bin/rmdanglingattrs.pl')
CORE = {'src/classes_atoms.src': (15, 1), 'src/attributes.orig': (15, 5),
        'src/relationships.src': (19, 6), 'src/mergefacts.src': (13, 3), 'src/contexts.src': (18, 4)}


def _stamp(path):
    info = path.stat()
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, stat.S_IMODE(info.st_mode)]


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as incoming:
        for block in iter(lambda: incoming.read(8 * 1024**2), b''): digest.update(block)
    return digest.hexdigest()


def _name(name):
    name = name.removeprefix('./').rstrip('/')
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or str(path) != name or
            '\\' in name or any(ord(c) < 32 for c in name)):
        raise ValueError('Unsafe archive member name')
    return name


def properties(text):
    values, pending = {}, ''
    for line in text.splitlines():
        if not pending and (not line.strip() or line.lstrip().startswith(('#', '!'))): continue
        line = pending + line.lstrip() if pending else line
        if line.endswith('\\'): pending = line[:-1]; continue
        pending = ''; key, separator, value = line.partition('='); key = key.strip()
        if not separator or not key or key in values: raise ValueError('Malformed/duplicate archived cfg property')
        values[key] = value.strip()
    if pending: raise ValueError('Unterminated archived cfg property')
    return values


def expand(values, key, seen=frozenset()):
    if key not in values or key in seen: raise ValueError('Unresolved archived cfg property: ' + key)
    return re.sub(r'<([^<>]+)>', lambda m: expand(values, m[1], seen | {key}), values[key])


def _expected(entries, name, count, checksum):
    item = entries.get(name)
    if (not item or item.get('kind') != 'file' or item.get('size', item.get('bytes')) != count or
            item.get('sha256') != checksum):
        raise ValueError('Captured payload differs from frozen archive inventory: ' + name)


def _small(handle, member, entries, name):
    if member.size > 2 * 1024**2: raise ValueError('Unexpectedly large small producer/metadata file')
    raw = handle.read()
    _expected(entries, name, len(raw), hashlib.sha256(raw).hexdigest())
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'text': raw.decode('utf-8')}


def _core_scope(handle, entries, name, width, source_column, original=None):
    digest = hashlib.sha256(); size = rows = 0; sources = Counter(); widths = Counter(); semantic = Counter()
    prefix = hashlib.sha256(); suffix_rows = 0; suffix_bad = 0; split_boundary = False
    original_size = original.get('size', original.get('bytes')) if original else None
    for line in handle:
        digest.update(line); fields = line.rstrip(b'\r\n').split(b'|'); widths[len(fields)] += 1; rows += 1
        if len(fields) == width:
            sources[fields[source_column].decode('utf-8')] += 1
            if width == 15 and source_column == 5 and fields[3] == b'SEMANTIC_TYPE': semantic[fields[5].decode('utf-8')] += 1
        if original_size is not None:
            remaining = max(0, original_size - size)
            if remaining: prefix.update(line[:remaining])
            if size < original_size < size + len(line): split_boundary = True
            if size >= original_size:
                suffix_rows += 1
                suffix_bad += len(fields) != 15 or fields[3] != b'SEMANTIC_TYPE' or not fields[5].startswith(b'E-')
        size += len(line)
    _expected(entries, name, size, digest.hexdigest())
    result = {'sha256': digest.hexdigest(), 'bytes': size, 'rows': rows, 'source_counts': dict(sources),
              'field_widths': dict(widths), 'semantic_type_sources': dict(semantic)}
    if original:
        result['pre_enrichment_prefix'] = {'original_sha256': original['sha256'], 'prefix_sha256': prefix.hexdigest(),
            'original_bytes': original_size, 'complete_row_boundary': not split_boundary,
            'prefix_equal': size >= original_size and prefix.hexdigest() == original['sha256'] and not split_boundary,
            'suffix_rows': suffix_rows, 'suffix_non_semantic_type_or_source_rows': suffix_bad}
    return result


def capture(archive, inventory):
    archive = Path(archive).resolve()
    if not archive.is_file() or archive.is_symlink(): raise ValueError('A regular frozen local archive is required')
    version = inventory['version']
    if not re.fullmatch(r'SNOMEDCT_US_[0-9]{4}_[0-9]{2}_[0-9]{2}', version): raise ValueError('Invalid archive source version')
    before = _stamp(archive)
    if before[2] != inventory['archive_bytes'] or _hash(archive) != inventory['archive_sha256']:
        raise ValueError('Archive bytes differ from frozen inventory')
    entries = {item['path']: item for item in inventory['entries']}
    if len(entries) != len(inventory['entries']): raise ValueError('Duplicate inventory entry')
    small = {}; oracle = {}; enriched = None; seen = set()
    originals = entries.get(version + '/src/attributes.orig')
    with tarfile.open(archive, 'r|gz') as incoming:
        for member in incoming:
            name = _name(member.name)
            if name in seen: raise ValueError('Duplicate archive member')
            seen.add(name)
            relative = name.removeprefix(version + '/')
            if relative not in SMALL and relative not in CORE and relative != 'src/attributes.src': continue
            if name != version + '/' + relative or not member.isfile(): raise ValueError('Selected evidence is not a regular version-bound member')
            with incoming.extractfile(member) as handle:
                if relative in SMALL: small[relative] = _small(handle, member, entries, name)
                elif relative == 'src/attributes.src': enriched = _core_scope(handle, entries, name, 15, 5, originals)
                else: oracle[relative] = _core_scope(handle, entries, name, *CORE[relative])
    if set(small) != set(SMALL) or set(oracle) != set(CORE):
        raise ValueError('Complete small producer evidence and five inversion-stage oracle files are required')
    cfg = properties(small['etc/sct.cfg']['text'])
    if expand(cfg, 'VSAB') != version or expand(cfg, 'RSAB') != 'SNOMEDCT_US' or expand(cfg, 'Release') != 'Snapshot':
        raise ValueError('Archived cfg release/view does not match the selected Snapshot source archive')
    source_rows = [line.split('|') for line in small['src/sources.src']['text'].splitlines()]
    logical_source_rows = [row[:-1] if len(row) == 21 and row[-1] == '' else row for row in source_rows]
    diagnostics = []
    if (len(logical_source_rows) != 1 or len(logical_source_rows[0]) != 20 or logical_source_rows[0][0] != version or
            logical_source_rows[0][1] != expand(cfg, 'VSABOLD')):
        # Evidence collection is not release admission. Retain genuine producer
        # and metadata values even if copied settings or staff edits disagree.
        diagnostics.append({'code':'SOURCE_METADATA_CFG_LINEAGE_DISAGREEMENT',
            'message':'Saved metadata and legacy configuration require explicit lineage review; no predecessor was inferred.',
            'sources_row_widths':[len(row) for row in source_rows],
            'sources_current':[row[0] if row else None for row in source_rows],
            'sources_low_source':[row[1] if len(row)>1 else None for row in source_rows],
            'cfg_current':expand(cfg,'VSAB'),'cfg_previous':expand(cfg,'VSABOLD')})
    native_members = {}
    for legacy, role in ROLES.items():
        value = expand(cfg, 'File.INP.' + legacy)
        member = posixpath.normpath(version + '/bin/' + value)
        if not member.startswith(version + '/orig/fromprovider/') or entries.get(member, {}).get('kind') != 'file':
            raise ValueError('Required native input is absent/unbound: ' + legacy + ' ' + member)
        if member in native_members: raise ValueError('Native roles share one ambiguous file')
        native_members[member] = role
    optional = posixpath.normpath(version + '/bin/' + expand(cfg, 'File.INP.COMPLEXMAPS'))
    if entries.get(optional, {}).get('kind') == 'file': native_members[optional] = 'rf2-complex-map'
    headers = {}; files = {}; active = {}; fsns = defaultdict(set); descriptions = {}; counts = Counter(); modules = set(); deps = []
    observed = {key: set() for key in ('relationship_types','association_refsets','description_types','attribute_refsets','concrete_types','refset_patterns','map_correlations')}
    atn_candidates = defaultdict(set); patterns = set(); map_candidates = defaultdict(set)
    effective_min, effective_max = None, None
    seen = set()
    with tarfile.open(archive, 'r|gz') as incoming:
        for member in incoming:
            name = _name(member.name)
            if name not in native_members: continue
            if name in seen or not member.isfile(): raise ValueError('Duplicate or linked selected native input')
            seen.add(name); role = native_members[name]; digest = hashlib.sha256(); size = 0; native_ids = set()
            with incoming.extractfile(member) as handle:
                raw = handle.readline(); digest.update(raw); size += len(raw)
                header = raw.rstrip(b'\r\n').decode('utf-8').split('\t')
                if not {'id','effectiveTime','active','moduleId'} <= set(header) or len(set(header)) != len(header): raise ValueError('Unsupported physical RF2 header')
                headers[role] = header
                for line in handle:
                    digest.update(line); size += len(line); values = line.rstrip(b'\r\n').decode('utf-8').split('\t')
                    if len(values) != len(header) or not line.endswith(b'\n'): raise ValueError('Malformed actual RF2 row: ' + role)
                    row = dict(zip(header, values)); counts[role] += 1
                    if row['id'] in native_ids or row['active'] not in ('0','1'): raise ValueError('Duplicate/invalid Snapshot row identity')
                    native_ids.add(row['id'])
                    date = row['effectiveTime']; datetime.datetime.strptime(date,'%Y%m%d')
                    effective_min = date if effective_min is None else min(effective_min,date)
                    effective_max = date if effective_max is None else max(effective_max,date)
                    if row['active']=='1': modules.add(row['moduleId'])
                    if role == 'rf2-concepts': active[row['id']] = row['active']=='1'
                    elif role == 'rf2-descriptions':
                        descriptions[row['id']] = (row['active']=='1',row['conceptId'])
                        observed['description_types'].add(row['typeId'])
                        if cfg.get('TTY.' + row['typeId']) == 'FN':
                            fsns[row['conceptId']].add(row['term'].replace('|','&#x7C;').rstrip(' '))
                    elif role=='rf2-relationships' and row['active']=='1': observed['relationship_types'].add(row['typeId'])
                    elif role=='rf2-association' and row['active']=='1': observed['association_refsets'].add(row['refsetId'])
                    elif role in ('rf2-attribute-value','rf2-simple-map') and row['active']=='1': atn_candidates[row['refsetId']].add(row['referencedComponentId'])
                    elif role=='rf2-concrete-values' and row['active']=='1': observed['concrete_types'].add(row['typeId'])
                    elif role=='rf2-refset-descriptor' and row['active']=='1': patterns.add(row['referencedComponentId'])
                    elif role=='rf2-module-dependency' and row['active']=='1':
                        deps.append({'source_module_id':row['moduleId'],'target_module_id':row['referencedComponentId'],'source_effective_time':row['sourceEffectiveTime'],'target_effective_time':row['targetEffectiveTime']})
                    elif role in ('rf2-complex-map','rf2-extended-map') and row['active']=='1': map_candidates[row['correlationId']].add(row['referencedComponentId'])
            _expected(entries,name,size,digest.hexdigest())
            files[role] = {'path':name,'sha256':digest.hexdigest(),'bytes':size,'rows':counts[role]}
    if seen != set(native_members): raise ValueError('Native inputs disappeared during second pass')
    for identifier,(flag,concept) in descriptions.items(): active[identifier] = flag and active.get(concept,False)
    observed['attribute_refsets'] = {key for key, values in atn_candidates.items() if any(active.get(value) for value in values)}
    observed['refset_patterns'] = {value for value in patterns if active.get(value)}
    observed['map_correlations'] = {key for key, values in map_candidates.items() if any(value in active for value in values)}
    type_ids = observed['relationship_types'] | observed['association_refsets']
    labels = {key:sorted(fsns.get(key,[])) for key in sorted(type_ids)}
    if _stamp(archive) != before: raise ValueError('Frozen archive changed during capture')
    return {'schema_version':1,'artifact_type':'archived-snomed-physical-capture','source':'SNOMEDCT_US','version':version,
            'archive':{'path':str(archive),'sha256':inventory['archive_sha256'],'bytes':inventory['archive_bytes'],'snapshot':before},
            'small_files':small,'oracle_files':oracle,'enriched_attributes':enriched,'diagnostics':diagnostics,
            'native':{'files':files,'headers':headers,'active_modules':sorted(modules),'module_dependencies':deps,
                      'effective_time_bounds':{'minimum':effective_min,'maximum':effective_max},
                      'discovery':{key:sorted(value) for key,value in observed.items()},'type_fsn_labels':labels},
            'selected_payloads_inventory_verified':True,'expanded_files_created':False,'native_conversion_executed':False,'network_access':False}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--inventory',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(capture(args.archive,json.loads(args.inventory.read_text())),sort_keys=True))
