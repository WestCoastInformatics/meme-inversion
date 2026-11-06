#!/usr/bin/env python3
"""Validate correction predictions against the actual unchanged MTH producer."""
from collections import Counter
import hashlib
import io
import os
import shlex
from pathlib import Path
import subprocess
import tempfile

import audit_mth_corrections as audit


def check():
    values = []
    def require(value, label):
        assert value, label
        values.append(label)
    def rejected(action, label):
        try:action()
        except RuntimeError:values.append(label)
        else:raise AssertionError(label)
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='mth-correction-audit-') as temporary:
        base = Path(temporary);old = base / 'old';new = base / 'new';native = base / 'native'
        for path in (old, new, native):path.mkdir()
        ordinary = (b'C1000010', b'A10', b'770000001')
        moved = (b'C8888888', b'A88', b'771888888')
        def atom(said, cui, aui, source=b'LNC_2_82', code=b'ordinary', moved=b'N'):
            return audit.row([said, source, source + b'/HC', code, b'R', b'Y', b'A', b'fixture', b'N', b'', b'', b'', b'ENG', b'needs_order_id', moved, cui, aui])
        raw = [atom(ordinary[2], ordinary[0], ordinary[1]),
               atom(b'771038403', audit.CCS, b'A8298300', b'SRC', b'V-CCS_2005'),
               atom(b'771038404', audit.CCS, b'A8298289', b'SRC', b'V-CCS_2005'),
               atom(audit.PART[2], audit.PART[0], audit.PART[1], code=b'MTHU000999'),
               atom(moved[2], moved[0], moved[1], moved=b'Y')]
        retained = [raw[0], raw[3], raw[4]]
        (old / 'classes_atoms.src.raw').write_bytes(b''.join(raw))
        (new / 'classes_atoms.unfiltered.raw').write_bytes(b''.join(raw))
        (new / 'classes_atoms.src.raw').write_bytes(b''.join(retained))
        final = b''.join(audit.row(f[:14] + [f[15]]) for f in [x.rstrip(b'\n').split(b'|') for x in retained])
        for path in (old, new):(path / 'classes_atoms.src').write_bytes(final)
        old_auis = {ordinary[1]: ordinary[2], b'A8298300': b'771038403', b'A8298289': b'771038404'}
        new_auis = {ordinary[1]: ordinary[2], audit.PART[1]: audit.PART[2]}
        old_cuis = {ordinary[0]: ordinary[2], audit.CCS: b'771038403', moved[0]: moved[2]}
        new_cuis = {ordinary[0]: ordinary[2], audit.PART[0]: audit.PART[2], moved[0]: moved[2]}
        cui_for_aui = {ordinary[1]: ordinary[0], b'A8298300': audit.CCS, b'A8298289': audit.CCS, audit.PART[1]: audit.PART[0]}
        for path, auis, cuis in [(old, old_auis, old_cuis), (new, new_auis, new_cuis)]:
            (path / 'aui_said_map').write_bytes(b''.join(audit.row([aui, cui_for_aui[aui], said]) for aui, said in auis.items()))
            (path / 'moved_aui_said_map').write_bytes(audit.row([moved[1], moved[0], moved[2]]))
            (path / 'cui_splitonly_said_map').write_bytes(audit.row([moved[0], moved[2]]))
            cui_map = b''.join(audit.row([cui, cuis[cui]]) for cui in sorted(cuis))
            (path / 'cui_said_map').write_bytes(cui_map);(path / 'rel_cui_said_map').write_bytes(cui_map)
        lookup, old_map, new_map, result = audit.expected_maps(old, new)
        require(result['final_atoms_exact'] and old_map == old_cuis and new_map == new_cuis, 'Complete native-derived old/new map predictions match retained atoms')
        saved = (new / 'aui_said_map').read_bytes();(new / 'aui_said_map').write_bytes(saved.splitlines(keepends=True)[0])
        rejected(lambda: audit.expected_maps(old, new), 'A missing retained AUI mapping is rejected')
        (new / 'aui_said_map').write_bytes(saved)
        def rrf(path, rows):(native / path).write_bytes(b''.join(audit.row(fields) for fields in rows))
        rrf('MRSAT.RRF', [
            [audit.PART[0], b'', b'', audit.PART[1], b'AUI', b'HC', b'', b'SATUI-1', b'FLAG', b'LNC_2_82', b'native', b'N', b''],
            [audit.CCS, b'', b'', b'A8298300', b'AUI', b'V-CCS_2005', b'', b'SATUI-2', b'FLAG', b'SRC', b'obsolete', b'N', b''],
            [audit.PART[0], b'', b'', b'', b'CUI', b'HC', b'', b'SATUI-3', b'CUSTOM', b'LNC_2_82', b'cui-level', b'N', b''],
            [audit.PART[0], b'', b'', b'', b'CUI', b'HC', b'', b'SATUI-4', b'DA', b'LNC_2_82', b'excluded', b'N', b'']])
        rrf('MRSTY.RRF', [[cui, b'T1', b'STN', sty, b'', b''] for cui, sty in [(ordinary[0], b'Entity'), (audit.CCS, b'Intellectual Product'), (audit.PART[0], b'Conceptual Entity')]])
        rrf('MRDEF.RRF', [[audit.PART[0], audit.PART[1], b'', b'DEF-1', b'LNC_2_82', 'native caf\u00e9 definition'.encode(), b'N', b'']])
        def rel(cui, aui, kind=b'AUI', name=b'RO', direction=b'Y', group=b''):
            return [cui, aui, kind, name, ordinary[0], ordinary[1] if kind == b'AUI' else b'', kind, b'related_to', b'R1', b'', b'LNC_2_82', b'LNC_2_82', group, direction, b'N', b'']
        rrf('MRREL.RRF', [rel(audit.PART[0], audit.PART[1]), rel(audit.PART[0], audit.PART[1]),
                           rel(audit.CCS, b'A8298300'), rel(audit.PART[0], b'', b'CUI', b'RB'),
                           rel(audit.PART[0], audit.PART[1], name=b'PAR'),
                           rel(audit.PART[0], audit.PART[1], direction=b'N')])
        changes, trace = audit.native_changes(native, lookup, old_map, new_map, progress=lambda *a, **k: None)
        require(sum(changes['attributes.src']['removed'].values()) == 2 and sum(changes['attributes.src']['added'].values()) == 4, 'Native attribute predictions retain STYPE rules, semantic types, definitions and exclusions')
        require(sum(changes['relationships.src']['removed'].values()) == 1 and sum(changes['relationships.src']['added'].values()) == 3, 'Native relationship predictions preserve duplicate multiplicity and direction/hierarchy rules')
        spec = (root / 'sources/MTH_2026AA/src/inv2.spec').read_text()
        producer = root / 'sources/MTH_2026AA/autoinv.pl'
        normalize = next(line.strip() for line in (root / 'sources/MTH_2026AA/invert2.s').read_text().splitlines()
                         if line.strip().startswith("awk 'BEGIN{FS=OFS="))
        normalize_args = shlex.split(normalize)
        require(normalize_args[-1] == '>relationships.src', 'Actual source relationship-normalization stage identified')
        for path, auis, cuis in [(old, old_auis, old_cuis), (new, new_auis, new_cuis)]:
            for name in ('MRSAT.RRF', 'MRSTY.RRF', 'MRDEF.RRF', 'MRREL.RRF'):(path / name).write_bytes((native / name).read_bytes())
            (path / 'aui_said_map2').write_bytes((path / 'aui_said_map').read_bytes())
            (path / 'rel_cui_said_map2').write_bytes((path / 'rel_cui_said_map').read_bytes())
            for name in ('attr_src', 'rel_src', 'merge_src', 'auis_nonupdatedSAB_moved', 'cui_merges'):(path / name).write_bytes(b'')
            (path / 'fixture.spec').write_text(spec.replace('/local/content/MEME/MEME5/inv/sources/MTH_2026AA/src', str(path)))
            p = subprocess.run(['/usr/bin/perl', str(producer), 'fixture.spec'], cwd=path, capture_output=True, env=dict(os.environ, LANG='C'), timeout=30)
            require(p.returncode == 0, 'Actual unchanged native producer executes for ' + path.name + ': ' + p.stderr.decode(errors='replace'))
            (path / 'relationships.src').rename(path / 'relationships1.src')
            with (path / 'relationships.src').open('wb') as out:
                subprocess.run(normalize_args[:-1], cwd=path, stdout=out, check=True, timeout=30)
        for name in ('attributes.src', 'relationships.src'):
            with (old / name).open('rb') as a, (new / name).open('rb') as b:
                result = audit.compare_transition(a, b, changes[name]['removed'], changes[name]['added'])
            require(result['every_generated_id_verified'], 'Independent native prediction accounts for the actual producer: ' + name)
        def run_pair(old_bytes, new_bytes, name):
            return audit.compare_transition(io.BytesIO(old_bytes), io.BytesIO(new_bytes), changes[name]['removed'], changes[name]['added'])
        original = (new / 'relationships.src').read_bytes()
        mutated = original.replace(b'CUI_CURRENT', b'CUI_PREVIOUS')
        rejected(lambda: run_pair((old / 'relationships.src').read_bytes(), mutated, 'relationships.src'), 'CUI current/previous role changes cannot pass the correction audit')
        lines = original.splitlines(keepends=True);removed_duplicate = b''.join(str(i).encode() + b'|' + line.split(b'|', 1)[1] for i, line in enumerate(lines[1:], 1))
        rejected(lambda: run_pair((old / 'relationships.src').read_bytes(), removed_duplicate, 'relationships.src'), 'Loss of one added native duplicate is rejected even after valid renumbering')
        attrs = (new / 'attributes.src').read_bytes()
        rejected(lambda: run_pair((old / 'attributes.src').read_bytes(), attrs.replace(b'1|', b'99|', 1), 'attributes.src'), 'Unaccounted generated attribute ID changes rejected')
        (old / 'said.ptsaid').write_bytes(b'770000001|770000001\n771038403|771038403\n771038404|771038403\n771405764|771405764\n')
        (new / 'said.ptsaid').write_bytes(b'770000001|770000001\n771405764|771405764\n')
        (old / 'ptsaid.order').write_bytes(b'770000001\n771038403\n771405764\n');(new / 'ptsaid.order').write_bytes(b'770000001\n771405764\n')
        audit.preferred(old, new);values.append('Preferred helpers change only for removed and unreferenced CCS identities')
        scratch = base / 'scratch';scratch.mkdir()
        ctx = [b'', b'PAR', b'', b'770620428', b'LNC_2_82', b'LNC_2_82', b'', b'770620428', b'11', b'', b'', b'', b'SRC_ATOM_ID', b'', b'770620428', b'SRC_ATOM_ID', b'', b'', b'']
        (old / 'contexts.src').write_bytes(audit.row(ctx))
        ctx[0] = ctx[11] = audit.PART[2];(new / 'contexts.src').write_bytes(audit.row(ctx))
        def context_attribute(identifier, target, value):
            return audit.row([str(identifier).encode(), target, b'S', b'CONTEXT', value, b'LNC_2_82', b'R', b'n', b'N', b'N', b'SRC_ATOM_ID', b'', b'', hashlib.md5(value).hexdigest().encode(), b''])
        missing = b'1\t::~~SRC_ATOM_ID~~~SRC_ATOM_ID~\tLOINC Root\tLOINCPARTS\t\t'
        mapped = missing.replace(b'::~~SRC_ATOM_ID~~~SRC_ATOM_ID~', b'::~771405764~SRC_ATOM_ID~~771405764~SRC_ATOM_ID~')
        (old / 'attributes.contexts-all.src').write_bytes(context_attribute(20, b'773000001', b'ordinary context') + context_attribute(21, b'', missing))
        expected = context_attribute(11, audit.PART[2], mapped) + context_attribute(12, b'773000001', b'ordinary context')
        (new / 'attributes.contexts-all.src').write_bytes(expected)
        result = audit.contexts(old, new, scratch, 10)
        require(result['context_attribute_file_predicted_byte_exact'], 'Corrected node metadata, MD5, reordered rows and all context attribute IDs predicted exactly')
        (new / 'attributes.contexts-all.src').write_bytes(expected.replace(b'LOINCPARTS', b'changed'))
        rejected(lambda: audit.contexts(old, new, scratch, 10), 'An additional context content change cannot be waived')
        require(audit.stream_sha(io.BytesIO(b'complete context suffix')) == hashlib.sha256(b'complete context suffix').hexdigest(), 'Full attribute suffix verified without loading it into memory')
        report = base / 'audit.json';audit.save_report(report, {'status': 'fixture'})
        original = report.read_bytes()
        try:audit.save_report(report, {'status': 'replaced'})
        except FileExistsError:pass
        else:raise AssertionError('Audit report was overwritten')
        require(report.read_bytes() == original and not report.stat().st_mode & 0o222, 'Completed audit evidence cannot be overwritten')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'MTH correction-audit checks passed')
