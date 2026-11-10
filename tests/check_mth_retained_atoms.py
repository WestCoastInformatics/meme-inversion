#!/usr/bin/env python3
"""Exercise retained-atom selection with the actual production autoinverter."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/MTH_2026AA'
PRODUCTION = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'


def check(baseline_spec=None):
    original = Path(baseline_spec).read_text() if baseline_spec else subprocess.check_output(
        ['git', 'show', PRODUCTION + ':sources/MTH_2026AA/inv1.spec'], cwd=ROOT, text=True)
    candidate = (SOURCE / 'inv1.spec').read_text()
    effective = (SOURCE / 'src/inv1.spec').read_text()
    assert candidate.split('\n', 1)[1] == effective.split('\n', 1)[1], 'Template and effective rules differ'
    checks = []
    def require(value, label):
        assert value, label
        checks.append(label)
    def conso(cui, aui, sab, tty, code, text):
        return '|'.join([cui, 'ENG', 'P', 'L1', 'PF', 'S1', 'Y', aui, '', '', '', sab, tty, code, text, '0', 'N', '']) + '\n'
    records = [('C1', 'A1', 'S1', 'PT', 'ONE', 'First'),
               ('C_OLD', 'A_OLD1', 'SRC', 'VPT', 'V-CCS_2005', 'Obsolete version'),
               ('C_OLD', 'A_OLD2', 'SRC', 'VAB', 'V-CCS_2005', 'Obsolete abbreviation'),
               ('C2', 'A2', 'S1', 'PT', 'TWO', 'Second'),
               ('C3', 'A3', 'SRC', 'VPT', 'V-CCS_2005_extra', 'Different version code'),
               ('C4', 'A4', 'S1', 'PT', 'V-CCS_2005', 'Different source'),
               ('C1976636', 'A32818398', 'LNC_2_82', 'HC', 'MTHU000999', 'LOINCPARTS')]
    with tempfile.TemporaryDirectory(prefix='mth-retention-') as temporary:
        directories = []
        for name, spec in [('original', original), ('candidate', candidate)]:
            directory = Path(temporary) / name
            directory.mkdir()
            directories.append(directory)
            (directory / 'MRCONSO.RRF').write_text(''.join(conso(*record) for record in records))
            (directory / 'sabs_updated_umls').write_text('S1\nLNC_2_82\n')
            (directory / 'vcodes_updated').write_text('V-MTH_TEST\n')
            (directory / 'auis_nonupdatedSAB_moved').write_text('')
            (directory / 'class_src').write_text('|'.join(['1999', 'SRC', 'SRC/VPT', 'V-MTH_TEST', 'N', 'Y', 'N', 'Test', 'N', '', '', '', 'ENG', '', '']) + '\n')
            (directory / 'range.spec').write_text('SourceAtomIdBase|2000\nSourceAtomIdLimit|2100\n')
            rendered = 'SourceDir|' + str(directory) + '\n' + spec.split('\n', 1)[1]
            (directory / 'inv1.spec').write_text(rendered)
            result = subprocess.run(['perl', str(SOURCE / 'autoinv.pl'), 'range.spec', 'inv1.spec'], cwd=directory, capture_output=True, text=True)
            require(result.returncode == 0, name + ' production autoinverter execution: ' + result.stderr)
        old, new = directories
        original_rows = (old / 'classes_atoms.src').read_bytes().splitlines(keepends=True)
        retained = [row for row in original_rows if not (row.split(b'|')[1] == b'SRC' and row.split(b'|')[3] == b'V-CCS_2005')]
        require((new / 'classes_atoms.unfiltered.raw').read_bytes() == (old / 'classes_atoms.src').read_bytes(), 'Allocation before filtering reproduces every original raw atom and ID')
        require((new / 'classes_atoms.src').read_bytes() == b''.join(retained), 'Only the intended obsolete SRC atoms are removed')
        atom_ids = {row.split(b'|', 1)[0] for row in retained}
        mappings = [row.split(b'|') for row in (new / 'aui_said_map').read_bytes().splitlines()]
        require(all(row[3] in atom_ids for row in mappings), 'Every generated AUI mapping targets a retained atom')
        require(not any(row[0] in {b'A_OLD1', b'A_OLD2'} for row in mappings), 'Excluded atoms cannot seed downstream CUI/AUI state')
        require([row for row in mappings if row[0] == b'A2'][0][3] == b'2004', 'Following atoms keep their historical IDs with allocation gaps')
        require(any(row[0] == b'A3' for row in mappings) and any(row[0] == b'A4' for row in mappings), 'Similar codes and other sources are retained')
        require(any(row[0] == b'A32818398' and row[3] == b'2007' for row in mappings), 'Retained LOINCPARTS atom has its native AUI mapping')
        (new / 'bin').mkdir()
        stub = new / 'bin/get.saidpts.pl'
        stub.write_text('#!/bin/sh\nprintf "1999|1999\\n"\n')
        stub.chmod(0o755)
        result = subprocess.run([shutil.which('tcsh') or '/bin/tcsh', '-f', str(SOURCE / 'make.meme4classes.s')], cwd=new, capture_output=True)
        require(result.returncode == 0, 'Final production formatter executes')
        expected = b''.join(b'|'.join(row.rstrip(b'\n').split(b'|')[:14] + [row.rstrip(b'\n').split(b'|')[15]]) + b'\n' for row in retained)
        require((new / 'classes_atoms.src').read_bytes() == expected, 'Final formatter changes layout without changing the retained set or IDs')
        require((new / 'classes_atoms.src.raw').read_bytes() == b''.join(retained), 'Preferred-term input and saved raw atoms use the same retained set')
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-spec')
    args = parser.parse_args()
    values = check(args.baseline_spec)
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH retention checks passed')
