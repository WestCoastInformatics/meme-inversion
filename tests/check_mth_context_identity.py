#!/usr/bin/env python3
"""Reproduce the LOINCPARTS mapping exclusion and test atomic context output."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/MTH_2026AA'
PRODUCTION = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'


def check(production_root=None):
    def original(name):
        if production_root:
            return (Path(production_root) / name).read_text()
        return subprocess.check_output(['git', 'show', PRODUCTION + ':sources/MTH_2026AA/' + name], cwd=ROOT, text=True)
    def mapping_step(text):
        begin = text.index('    $INV_HOME_OLD/bin/autoinv.pl ../range$subset.spec inv1.spec >>& autoinv.log')
        begin = text.index('\n', begin) + 1
        end = text.index('    awk -F\\|', begin)
        return text[begin:end]
    checks = []
    def require(value, label):
        assert value, label
        checks.append(label)
    def context(aui, kind, related, label, rank=''):
        cui = 'C_ROOT' if aui == 'A_ROOT' else 'C1976636'
        code = 'V-LNC' if aui == 'A_ROOT' else 'MTHU000999'
        return '|'.join([cui, 'S1', aui, 'LNC_2_82', code, '1', kind, rank, label,
                         'C_ROOT' if related == 'A_ROOT' else 'C1976636', related, '', '', '', '']) + '\n'
    records = [context('A_ROOT', 'CCP', 'A_ROOT', 'LOINC Root'),
               context('A_ROOT', 'CHD', 'A32818398', 'LOINCPARTS'),
               context('A32818398', 'ANC', 'A_ROOT', 'LOINC Root', '1'),
               context('A32818398', 'CCP', 'A32818398', 'LOINCPARTS')]
    with tempfile.TemporaryDirectory(prefix='mth-context-identity-') as temporary:
        directory = Path(temporary)
        (directory / 'Meta').mkdir()
        (directory / 'raw3').mkdir()
        (directory / 'sabs_updated_umls').write_text('LNC_2_82\n')
        sab = [''] * 25
        sab[2], sab[3], sab[16] = 'LNC_2_82', 'LNC', 'FULL'
        (directory / 'Meta/MRSAB.RRF').write_text('|'.join(sab) + '\n')
        (directory / 'src-root.cuis.updated').write_text('C_ROOT\n')
        original_script = directory / 'original-mrcxt.pl'
        original_script.write_text(original('mrcxt2raw3.pl'))
        raw = directory / 'raw3/newsources.raw3'
        map_file = directory / 'aui_said_map'
        for label, wrapper in [('original', original('invert2.s')), ('candidate', (SOURCE / 'invert2.s').read_text())]:
            map_file.write_text('A_ROOT|C_ROOT|N|100\nA32818398|C1976636|N|101\n')
            done = subprocess.run([shutil.which('tcsh') or '/bin/tcsh', '-f', '-c', mapping_step(wrapper)], cwd=directory, capture_output=True)
            require(done.returncode == 0, label + ' actual wrapper mapping step executes')
            kept = 'A32818398|C1976636|N|101' in map_file.read_text()
            require(kept == (label == 'candidate'), ('Legacy wrapper reproduces the LOINCPARTS mapping loss' if label == 'original' else 'Corrected wrapper retains the existing LOINCPARTS mapping'))
        def run(script, data=records, mapping='A_ROOT|C_ROOT|100\nA32818398|C1976636|101\n', env=None):
            map_file.write_text(mapping)
            (directory / 'Meta/MRCXT.RRF').write_text(''.join(data))
            return subprocess.run([shutil.which('perl') or '/usr/bin/perl', str(script)], cwd=directory, env=env, capture_output=True, text=True)
        require(run(original_script).returncode == 0, 'Original producer accepts fully mapped native context records')
        expected = raw.read_bytes()
        require(run(SOURCE / 'mrcxt2raw3.pl').returncode == 0 and raw.read_bytes() == expected,
                'Corrected producer preserves exact valid-record serialization')
        require(all(row.split(b'|')[0] and row.split(b'|')[5] for row in expected.splitlines()),
                'Root, child, ancestor and self context endpoints all resolve')
        for label, data, mapping in [
            ('subject', [records[3]], 'A_ROOT|C_ROOT|100\n'),
            ('related', [records[1]], 'A_ROOT|C_ROOT|100\n'),
            ('nonnumeric', [records[3]], 'A_ROOT|C_ROOT|100\nA32818398|C1976636|bad\n')]:
            raw.write_bytes(b'previous verified contexts\n')
            done = run(SOURCE / 'mrcxt2raw3.pl', data, mapping)
            require(done.returncode != 0 and 'Unmapped MRCXT endpoint' in done.stderr and 'A32818398' in done.stderr,
                    label + ' mapping failure reports the native identifier and fails')
            require(raw.read_bytes() == b'previous verified contexts\n' and not list((directory / 'raw3').glob('.newsources.*')),
                    label + ' mapping failure preserves existing output and cleans staging')
        fake = directory / 'fake-bin'
        fake.mkdir()
        sort = fake / 'sort'
        sort.write_text('#!/bin/sh\n' + shlex.quote(shutil.which('sort')) + ' "$@"\nexit 7\n')
        sort.chmod(0o755)
        probe = subprocess.run([str(sort), '--version'], capture_output=True)
        require(probe.returncode == 7, 'Injected sort command executes in the fixture work directory')
        raw.write_bytes(b'previous verified contexts\n')
        done = run(SOURCE / 'mrcxt2raw3.pl', env=dict(os.environ, PATH=str(fake) + os.pathsep + os.environ['PATH']))
        require(done.returncode != 0 and 'Context sort failed' in done.stderr and raw.read_bytes() == b'previous verified contexts\n',
                'Sort failure cannot replace the prior verified context artifact: ' + repr((done.returncode, done.stderr, raw.read_bytes()[:120])))
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--production-root')
    args = parser.parse_args()
    values = check(args.production_root)
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH context identity checks passed')
