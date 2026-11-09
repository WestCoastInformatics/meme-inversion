#!/usr/bin/env python3
"""Record versioned impact evidence for the reviewed Hierarchy.pm change.

This is a bounded code review check, not a Perl call-graph analyzer or a
substitute for the affected sources' full native regression runs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / 'docs/inversion-review'
ORIGINAL = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
STABLE = 'bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09'
CASES = {
    'NCI': ('nci-stable-context-order', 'bin/invert_NCI.pl'),
    'MDR': ('mdr-consistent-history-context', 'bin/invert_mdr.pl'),
    'RADLEX': ('radlex-stable-context-order', 'bin/makesrc.pl'),
    'SNOMEDCT_US': ('snomedct_us-as-produced', 'bin/invert_rf2.pl'),
    'MTH': ('mth-consistent-retained-identities', 'autoinv.pl'),
}


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def blob(ref, path):
    return git('show', ref + ':' + path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def evidence(ref, path):
    data = blob(ref, path)
    return {'path': path, 'ref': ref, 'sha256': sha(data)}


def matching_lines(data, pattern, comments=False):
    return [
        {'line': number, 'text': line.strip()}
        for number, line in enumerate(data.decode().splitlines(), 1)
        if re.search(pattern, line)
        and (comments or not line.lstrip().startswith('#'))
    ]


def review():
    cases = {source: json.loads((DOCS / 'case-catalog' / (name + '.json')).read_text())
             for source, (name, _) in CASES.items()}
    old_manifest = {e['relative_path']: e for e in cases['SNOMEDCT_US']['runtime_files']}
    new_manifest = {e['relative_path']: e for e in cases['NCI']['runtime_files']}
    assert len(old_manifest) == len(new_manifest) == 169
    assert old_manifest.keys() == new_manifest.keys()
    changed = []
    for path in sorted(old_manifest):
        old, new = blob(ORIGINAL, path), blob(STABLE, path)
        assert sha(old) == old_manifest[path]['sha256'], path
        assert sha(new) == new_manifest[path]['sha256'], path
        assert old_manifest[path]['mode'] == new_manifest[path]['mode'], path
        if old != new:
            changed.append(path)
    assert changed == ['INV/lib/Hierarchy.pm'], changed
    old, new = blob(ORIGINAL, changed[0]), blob(STABLE, changed[0])
    before = b'foreach $nd (keys ( %{$parRef} )) {'
    after = b'foreach $nd (sort keys ( %{$parRef} )) {'
    method_start = old.index(b'  sub dumpCxtsAttrs {')
    assert old[method_start:].count(before) == 1
    assert old[:method_start] + old[method_start:].replace(before, after, 1) == new
    runtime = {
        'original_ref': ORIGINAL, 'stable_ref': STABLE,
        'verified_file_count_per_runtime': 169, 'changed_files': changed,
        'original_sha256': sha(old), 'stable_sha256': sha(new),
        'method': 'Hierarchy::dumpCxtsAttrs',
        'before': before.decode(), 'after': after.decode(),
        'no_other_runtime_byte_or_manifest_mode_changes': True,
    }
    sources = {}
    for source, (_, relative) in CASES.items():
        case = cases[source]
        ref = case['reviewed_engine_refs'][0]
        path = 'sources/' + case['version'] + '/' + relative
        data = blob(ref, path)
        calls = matching_lines(data, r'->dumpCxtsAttrs\b')
        entry = {
            'version': case['version'], 'engine_ref': ref,
            'entry_point': evidence(ref, path),
            'active_changed_method_call_sites': calls,
            'complete_native_changed_runtime_regression_required': source in ('NCI', 'MDR', 'RADLEX'),
        }
        if source in ('NCI', 'MDR', 'RADLEX'):
            assert calls, source
            entry['impact'] = 'Active context writer calls the changed method'
        elif source == 'SNOMEDCT_US':
            assert not calls
            assert matching_lines(data, r'&dumpCxts;')
            assert matching_lines(data, r'^sub dumpCxts\s*\{')
            assert matching_lines(data, r'->prepareCxts;')
            assert matching_lines(data, r'foreach \$said \(sort keys %\{\$parRef\}\)')
            commented = matching_lines(data, r'->dumpCxtsAttrs\b', comments=True)
            assert len(commented) == 1 and commented[0]['text'].startswith('#')
            entry.update({
                'impact': 'Selected core uses its own context writer and unchanged Hierarchy accessors',
                'custom_writer_evidence': matching_lines(data, r'&dumpCxts;|^sub dumpCxts\s*\{|->prepareCxts;|foreach \$said \(sort keys'),
                'commented_legacy_call': commented,
            })
        else:
            assert not calls
            closure = []
            for item in case['source_files']:
                source_path = 'sources/' + case['version'] + '/' + item['relative_path']
                source_data = blob(ref, source_path)
                if 'sha256' in item:
                    assert sha(source_data) == item['sha256'], source_path
                else:
                    assert item['kind'] == 'symlink' and source_data.decode() == item['target'], source_path
                assert not matching_lines(source_data, r'Hierarchy|NLMInv|dumpCxtsAttrs'), source_path
                closure.append(evidence(ref, source_path))
            runtime_paths = ['INV/bin/SRCbuilder.pl', 'INV/bin/print.raw3.to.attributes.pl', 'ENV/bin/env.pl']
            for runtime_path in runtime_paths:
                assert not matching_lines(blob(ORIGINAL, runtime_path), r'Hierarchy|NLMInv|dumpCxtsAttrs')
            entry.update({
                'impact': 'Selected autoinv/specification and raw-context pipeline has no Hierarchy dependency',
                'source_entries_checked': len(closure), 'source_closure': closure,
                'selected_runtime_entry_points': [evidence(ORIGINAL, p) for p in runtime_paths],
                'adapter': evidence(git('rev-parse', 'HEAD').decode().strip(), 'tools/replay_mth_core.py'),
            })
        sources[source] = entry
    return {
        'status': 'PASS_BOUNDED_CODE_IMPACT_REVIEW', 'runtime_change': runtime,
        'sources': sources,
        'limits': [
            'Applies only to the exact captured source cases, runtime pair and selected core execution paths.',
            'This static evidence is not a general dynamic Perl dependency proof.',
            'Affected NCI, MDR and RADLEX still require complete native executions and independent comparison.',
            'Does not claim an alternate-runtime SNOMED or MTH full execution, metadata QA or insertion coverage.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = review()
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x') as handle:
            handle.write(payload)
    print(json.dumps({'status': result['status'], 'runtime_files': 169,
                      'affected_sources': ['NCI', 'MDR', 'RADLEX'],
                      'source_cases_reviewed': len(result['sources'])}))
