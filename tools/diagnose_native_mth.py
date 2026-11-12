#!/usr/bin/env python3
"""Read-only ordered MTH diagnostics from a frozen native lock/result.

Stream selected official tar members without extracting reference files. Count
all positional row/field differences and report bounded examples. Separately
prove ordered deletion-only subsequences, preserving duplicate occurrences.
Positional shifts and failed greedy subsequences are not semantic edit counts.
No sorting, ID normalization, native writes, acceptance or correction waiver.
Identity-map Counters use an explicit per-input cap (128MiB default,256MiB
maximum); they preserve duplicate rows and separate order from binding changes.

Example: python3 -B diagnose_native_mth.py --lock case.lock.json --target
/local/content/MEME/MEME5/inv/sources/MTH_YYYYAA --result result.json
"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile
from urllib.parse import unquote, urlsplit

RAW = 'src/classes_atoms.src.raw'
HELPERS = {'src/aui_said_map', 'src/said.ptsaid', 'src/ptsaid.order'}
MAPS = {'src/aui_said_map', 'src/cui_said_map', 'src/rel_cui_said_map'}
ATOM = ['src_atom_id', 'source', 'termgroup', 'code', 'status', 'tobereleased', 'released',
        'atom_name', 'suppressible', 'source_aui', 'source_cui', 'source_dui', 'language', 'order_id']
ATTR = ['source_attribute_id', 'id', 'attribute_level', 'attribute_name', 'attribute_value', 'source',
        'status', 'tobereleased', 'released', 'suppressible', 'id_type', 'id_qualifier', 'source_atui', 'hashcode', 'trailing_empty']
FIELDS = {'classes_atoms.src.raw': ATOM + ['moved', 'cui', 'aui'],
          'classes_atoms.unfiltered.raw': ATOM + ['moved', 'cui', 'aui'],
          'classes_atoms.src': ATOM + ['last_release_cui'], 'attributes.src': ATTR,
          'attributes.contexts-all.src': ATTR,
          'contexts.src': ['src_atom_id_1', 'relationship_name', 'relationship_attribute', 'src_atom_id_2',
              'source', 'source_of_label', 'hierarchy_code', 'parent_path', 'release_mode', 'source_rui',
              'relationship_group', 'id_1', 'id_type_1', 'id_qualifier_1', 'id_2', 'id_type_2',
              'id_qualifier_2', 'trailing_empty', 'second_trailing_empty'],
          'aui_said_map': ['aui', 'cui', 'said'], 'cui_said_map': ['cui', 'said'],
          'rel_cui_said_map': ['cui', 'said'], 'said.ptsaid': ['said', 'preferred_said'],
          'ptsaid.order': ['preferred_said']}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def load(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:raise ValueError('Duplicate JSON key: ' + key)
            value[key] = item
        return value
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def _relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or str(path) != value or '\\' in value:
        raise ValueError('Unsafe relative input path')
    return value


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def opened(path):
    path = Path(path)
    if path.parent.resolve() != path.parent or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Regular unlinked diagnostic input required: ' + str(path))
    before = _stamp(path.lstat())
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as handle:
        if _stamp(os.fstat(handle.fileno())) != before:raise ValueError('Input changed before opening')
        yield handle
        if _stamp(os.fstat(handle.fileno())) != before or _stamp(path.lstat()) != before:
            raise ValueError('Diagnostic input changed while being read: ' + str(path))


class Rows:
    def __init__(self, handle):
        self.handle = handle;self.hash = hashlib.sha256();self.bytes = self.rows = 0

    def next(self):
        raw = self.handle.readline()
        if not raw:return None
        self.hash.update(raw);self.bytes += len(raw);self.rows += 1
        return raw

    def identity(self):
        return {'sha256': self.hash.hexdigest(), 'bytes': self.bytes, 'rows': self.rows}


class Compressed:
    def __init__(self, handle):
        self.handle = handle;self.hash = hashlib.sha256();self.bytes = 0

    def read(self, count=-1):
        raw = self.handle.read(count);self.hash.update(raw);self.bytes += len(raw)
        return raw

    def finish(self):
        while self.read(4 * 1024 ** 2):pass
        return {'sha256': self.hash.hexdigest(), 'bytes': self.bytes}


def shown(value, limit=512):
    if value is None:return {'missing': True}
    return {'text': value[:limit].decode('utf-8', errors='backslashreplace'), 'bytes': len(value),
            'sha256': hashlib.sha256(value).hexdigest(), 'truncated': len(value) > limit}


def record(raw, number):
    return {'line': number, 'row': shown(raw, 2048),
            'fields': [shown(value) for value in raw.removesuffix(b'\n').split(b'|')]}


class Ordered:
    def __init__(self, name, examples):
        self.names = FIELDS.get(Path(name).name, []);self.limit = examples
        self.equal = self.different = self.missing_reference = self.missing_candidate = self.endings = 0
        self.fields = Counter();self.samples = []

    def add(self, left, right, number):
        if left == right:self.equal += 1;return
        self.different += 1;self.missing_reference += left is None;self.missing_candidate += right is None
        self.endings += (left.endswith(b'\n') if left is not None else None) != (right.endswith(b'\n') if right is not None else None)
        a = left.removesuffix(b'\n').split(b'|') if left is not None else []
        b = right.removesuffix(b'\n').split(b'|') if right is not None else []
        changes = []
        for index, (old, new) in enumerate(itertools.zip_longest(a, b)):
            if old == new:continue
            field = self.names[index] if index < len(self.names) else 'field_' + str(index + 1)
            self.fields[field] += 1
            if len(self.samples) < self.limit:changes.append({'field': field, 'position': index + 1, 'reference': shown(old), 'candidate': shown(new)})
        if len(self.samples) < self.limit:
            self.samples.append({'position': number, 'reference_row': shown(left, 2048),
                'candidate_row': shown(right, 2048), 'field_changes': changes})

    def report(self):
        return {'equal_positions': self.equal, 'different_positions': self.different,
                'missing_reference_positions': self.missing_reference, 'missing_candidate_positions': self.missing_candidate,
                'line_ending_differences': self.endings, 'field_differences': dict(self.fields), 'examples': self.samples,
                'positional_counts_are_not_semantic_edit_counts': True,
                'all_positions_counted': True, 'sorting_or_normalization_applied': False}


class Deletions:
    def __init__(self, candidate, examples):
        self.candidate = candidate;self.limit = examples;self.pending = candidate.next()
        self.kept = self.deleted = 0;self.examples = []

    def add(self, raw, number):
        if raw == self.pending:self.kept += 1;self.pending = self.candidate.next()
        else:
            self.deleted += 1
            if len(self.examples) < self.limit:self.examples.append(record(raw, number))

    def finish(self):
        unmatched = 0;examples = []
        while self.pending is not None:
            unmatched += 1
            if len(examples) < self.limit:examples.append(record(self.pending, self.candidate.rows))
            self.pending = self.candidate.next()
        return {'ordered_deletion_only': unmatched == 0, 'matched_occurrences': self.kept,
                'deleted_reference_occurrences': self.deleted, 'unmatched_candidate_occurrences': unmatched,
                'deleted_examples': self.examples, 'unmatched_candidate_examples': examples,
                'method': 'Greedy byte-exact ordered subsequence; duplicates are separate occurrences. Failure counts are not edit distance.',
                'candidate': self.candidate.identity()}


class Focus:
    def __init__(self,name,identifiers,examples):
        self.name=Path(name).name;self.limit=examples
        self.patterns=[(value.encode(),re.compile(rb'(?<![A-Za-z0-9_])'+re.escape(value.encode())+rb'(?![A-Za-z0-9_])')) for value in identifiers]
        self.buckets={value:{side:{'rows':0,'examples':[]} for side in ('reference','candidate')} for value in identifiers}
        if self.name=='contexts.src':self.buckets['empty_context_subject_or_id1']={side:{'rows':0,'examples':[]} for side in ('reference','candidate')}
        if self.name in ('attributes.src','attributes.contexts-all.src'):self.buckets['empty_attribute_subject']={side:{'rows':0,'examples':[]} for side in ('reference','candidate')}

    def add(self,side,raw,number):
        if raw is None:return
        matches=[token.decode() for token,pattern in self.patterns if token in raw and pattern.search(raw)]
        if self.name in ('contexts.src','attributes.src','attributes.contexts-all.src'):
            fields=raw.removesuffix(b'\n').split(b'|')
            if self.name=='contexts.src' and len(fields)>11 and (not fields[0] or not fields[11]):matches.append('empty_context_subject_or_id1')
            if self.name!='contexts.src' and len(fields)>1 and not fields[1]:matches.append('empty_attribute_subject')
        for key in matches:
            bucket=self.buckets[key][side];bucket['rows']+=1
            if len(bucket['examples'])<self.limit:bucket['examples'].append(record(raw,number))

    def report(self):
        return {'buckets':self.buckets,'all_matching_rows_counted':True,
                'method':'Literal identifier token occurrences (including embedded context metadata) and explicit empty subject fields; full original rows/IDs retained. This does not filter the ordered comparison or infer causation.'}


def multiset_delta(left, right, examples):
    removed, added = left - right, right - left
    keys = {raw.split(b'|', 1)[0] for raw in itertools.chain(removed, added)}
    def samples(counter):
        return [{'occurrences': count, 'row': shown(raw, 2048)}
                for raw, count in itertools.islice(counter.items(), examples)]
    return {'performed':True,'row_multiset_equal':left==right,
            'reference_occurrences':sum(left.values()),'candidate_occurrences':sum(right.values()),
            'reference_only_occurrences':sum(removed.values()),'candidate_only_occurrences':sum(added.values()),
            'keys_with_different_row_occurrences':len(keys),
            'reference_only_examples':samples(removed),'candidate_only_examples':samples(added),
            'method':'Full raw-row Counters preserve every duplicate occurrence and byte. Ordering is separate; differing positional rows are not changed bindings.'}


def scan(reference, paths, name, examples, deletion_path=None, count_multiset=False, identifiers=()):
    """One reference pass; streaming unless bounded identity-map Counters selected."""
    with ExitStack() as stack:
        targets = {label: Rows(stack.enter_context(opened(path))) for label, path in paths.items()}
        ordered = {label: Ordered(name, examples) for label in targets}
        deletion = Deletions(Rows(stack.enter_context(opened(deletion_path))), examples) if deletion_path else None
        old_rows, new_rows = (Counter(), Counter()) if count_multiset else (None, None)
        focused=Focus(name,identifiers,examples)
        number = 0
        while True:
            raw = reference.next()
            if raw is None:break
            number += 1
            focused.add('reference',raw,number)
            if old_rows is not None:old_rows[raw] += 1
            for label, target in targets.items():
                current = target.next();ordered[label].add(raw, current, number)
                if label=='candidate':focused.add('candidate',current,target.rows)
                if new_rows is not None and label=='candidate' and current is not None:new_rows[current] += 1
            if deletion:deletion.add(raw, number)
        for label, target in targets.items():
            position = number
            while True:
                raw = target.next()
                if raw is None:break
                position += 1;ordered[label].add(None, raw, position)
                if label=='candidate':focused.add('candidate',raw,target.rows)
                if new_rows is not None and label=='candidate':new_rows[raw] += 1
        result = {'reference': reference.identity(), 'comparisons': {
            label: {'candidate': target.identity(), 'ordered': ordered[label].report()} for label, target in targets.items()}}
        if deletion:result['deletion_only'] = deletion.finish()
        if old_rows is not None:result['row_multiset'] = multiset_delta(old_rows,new_rows,examples)
        if focused.buckets:result['focused_rows']=focused.report()
        return result


def _identity_matches(observed, expected):
    return all(observed.get(key) == expected.get(key) for key in ('sha256', 'bytes'))


def diagnose(lock, target, result=None, examples=5, roles=None, map_max_bytes=128*1024**2, identifiers=(), progress=lambda message: None):
    if type(examples) is not int or not 0 <= examples <= 20:raise ValueError('Examples must be an integer from0 through20')
    if type(map_max_bytes) is not int or not 0 <= map_max_bytes <= 256*1024**2:raise ValueError('Map Counter input cap must be0 through256MiB per map')
    if (not isinstance(identifiers,(list,tuple)) or len(identifiers)>20 or
            any(not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',value) or
                value in ('empty_context_subject_or_id1','empty_attribute_subject') for value in identifiers) or
            len(set(identifiers))!=len(identifiers)):
        raise ValueError('Supply at most20 distinct literal identifier tokens of at most64 characters')
    if (lock.get('artifact_type') != 'ncimeta-native-release-lock' or lock.get('schema_version') != 1 or
            lock.get('lock_sha256') != digest({key:value for key,value in lock.items() if key != 'lock_sha256'})):
        raise ValueError('A complete unchanged frozen native release lock is required')
    config, manifest, plan = lock['configuration'], lock['manifest'], lock['plan']
    target = Path(target)
    if (config != manifest['configuration'] or config.get('source') != 'MTH' or target.name != config['version'] or
            lock['manifest_sha256'] != digest(manifest) or lock['plan_sha256'] != digest(plan) or
            plan.get('source') != 'MTH' or plan.get('version') != config['version']):
        raise ValueError('Lock manifest/plan/current target identity differs')
    reference = manifest['artifacts'][config['replay']['reference_ref']]
    files = reference['files'];references = {item['role']: item for item in files}
    if ((reference['artifact_type'],reference['source'],reference['version'],reference['data'].get('reference_stage')) !=
            ('reference-inversion','MTH',config['version'],'inversion-src') or
            len(files) != len(references) or set(references) != set(plan['output_files']) or RAW not in references):
        raise ValueError('Complete current-release inversion reference descriptors are required')
    if result is not None and 'records' in result:result = result['records']['result.json']
    comparisons = result['comparison']['files'] if result else {}
    if result is not None:
        if (result.get('source') != 'MTH' or result.get('version') != config['version'] or
                result.get('run_id') != lock.get('run_id') or result.get('lock_sha256') != lock['lock_sha256'] or set(comparisons) != set(references)):
            raise ValueError('Raw result belongs to a different lock/release or has incomplete output coverage')
        for name, item in comparisons.items():
            if (not _identity_matches(item['reference'],references[name]) or
                    item['exact_match'] != _identity_matches(item['reference'],item['candidate'])):
                raise ValueError('Raw result reference or exact-match declaration differs')
    selected = set(roles) if roles is not None else {name for name in references if not comparisons or not comparisons[name]['exact_match']}
    selected.add(RAW)
    if not selected <= set(references):raise ValueError('Selected diagnostic role is outside the frozen outputs')
    unfiltered = target / 'src/classes_atoms.unfiltered.raw'
    groups = {}
    for name in sorted(selected):
        _relative(name);item = references[name];_relative(item['archive_member'])
        uri = urlsplit(item['uri']);path = Path(unquote(uri.path))
        if uri.scheme != 'file' or uri.netloc or uri.query or uri.fragment or item.get('archive_format') != 'tar.gz':
            raise ValueError('Diagnostics require local hash-bound official tar archive members')
        key = (str(path),item['archive_sha256'],item['archive_bytes'])
        wanted = groups.setdefault(key,{})
        if item['archive_member'] in wanted:raise ValueError('Two selected roles bind the same reference member')
        wanted[item['archive_member']] = name
    watched = {path:_stamp(path.lstat()) for path in {target/name for name in selected} | {unfiltered} | {Path(key[0]) for key in groups}}
    report = {'schema_version':1,'artifact_type':'ncimeta-native-mth-diagnostic','source':'MTH','version':config['version'],
        'lock_sha256':lock['lock_sha256'],'run_id':lock.get('run_id'),'selected_roles':sorted(selected),'files':{},
        'diagnostic_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'raw_result_content_sha256':digest(result) if result else None,
        'archive_observations':[],'examples_limit':examples,'identity_map_counter_input_cap_bytes':map_max_bytes,
        'native_data_modified':False,'acceptance_changed':False,
        'raw_result_acceptance':result.get('acceptance') if result else None,
        'scope':'Read-only diagnostic, not acceptance or a correction waiver. Positional shifts are not semantic edit counts; no IDs/bytes/duplicates are normalized.'}
    for (archive_path,archive_sha,archive_bytes), wanted in groups.items():
        found = set();seen = set()
        with opened(archive_path) as handle:
            compressed = Compressed(handle)
            with tarfile.open(fileobj=compressed,mode='r|gz') as archive:
                for member in archive:
                    name = member.name.removeprefix('./').rstrip('/')
                    if name == '.':continue
                    _relative(name)
                    if name in seen:raise ValueError('Duplicate reference archive member')
                    seen.add(name)
                    if name not in wanted:continue
                    role = wanted[name];expected = references[role]
                    if not member.isfile() or member.size != expected['bytes']:raise ValueError('Selected reference member type/size differs')
                    progress('Diagnosing ' + role)
                    paths = {'candidate':target/role}
                    if role == RAW:paths['unfiltered_allocation'] = unfiltered
                    counters = role in MAPS and map_max_bytes>0 and max(expected['bytes'],(target/role).stat().st_size)<=map_max_bytes
                    with archive.extractfile(member) as incoming:
                        observed = scan(Rows(incoming),paths,role,examples,target/role if role == RAW or role in HELPERS else None,counters,identifiers)
                    if role in MAPS and not counters:
                        observed['row_multiset'] = {'performed':False,'reason':'Map exceeds the configured bounded Counter input cap, or cap is disabled; no binding-equality inference made.'}
                    if not _identity_matches(observed['reference'],expected):raise ValueError('Reference member bytes differ from the frozen descriptor')
                    if result and not _identity_matches(observed['comparisons']['candidate']['candidate'],comparisons[role]['candidate']):
                        raise ValueError('Candidate changed since its raw comparison: ' + role)
                    if 'deletion_only' in observed and not _identity_matches(observed['deletion_only']['candidate'],observed['comparisons']['candidate']['candidate']):
                        raise ValueError('Candidate changed between independent ordered/subsequence scans')
                    report['files'][role] = observed;found.add(name)
            actual = compressed.finish()
            if actual != {'sha256':archive_sha,'bytes':archive_bytes}:raise ValueError('Complete compressed reference archive identity differs')
            if found != set(wanted):raise ValueError('Missing selected reference members')
            report['archive_observations'].append({'path':archive_path,**actual})
    with opened(unfiltered) as incoming:
        retention = scan(Rows(incoming),{},RAW,examples,target/RAW)
    raw = report['files'][RAW]
    if (not _identity_matches(retention['reference'],raw['comparisons']['unfiltered_allocation']['candidate']) or
            not _identity_matches(retention['deletion_only']['candidate'],raw['comparisons']['candidate']['candidate'])):
        raise ValueError('Raw atom intermediate changed between scans')
    report['raw_atom_retention'] = {'official_raw_vs_unfiltered':raw['comparisons']['unfiltered_allocation'],
        'official_raw_to_retained':raw['deletion_only'],'unfiltered_to_retained':retention['deletion_only']}
    if any(_stamp(path.lstat())!=before for path,before in watched.items()):
        raise ValueError('An input/output changed during the complete diagnostic')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock',required=True,type=Path);parser.add_argument('--target',required=True,type=Path)
    parser.add_argument('--result',type=Path);parser.add_argument('--examples',type=int,default=5)
    parser.add_argument('--map-max-bytes',type=int,default=128*1024**2,help='Per-map input cap for full duplicate-preserving Counters, default128MiB, maximum256MiB')
    parser.add_argument('--identifier',action='append',default=[],help='Literal token from observed map/native evidence; count all matching rows and retain bounded full-row examples')
    parser.add_argument('--role',action='append',help='Explicit frozen src/ relative role; defaults to raw-result mismatches')
    args = parser.parse_args()
    value = diagnose(load(args.lock),args.target,load(args.result) if args.result else None,args.examples,args.role,
                     map_max_bytes=args.map_max_bytes,
                     identifiers=args.identifier,
                     progress=lambda message:print(message,file=sys.stderr,flush=True))
    json.dump(value,sys.stdout,indent=2);sys.stdout.write('\n')


if __name__ == '__main__':main()
