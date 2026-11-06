#!/usr/bin/env python3
"""Offline MTH dialect, identity-transition and preservation failure checks."""
import copy
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from unittest.mock import patch

import compare_mth_core as comparator
from compare_nci_core import compare_sorted
import replay_mth_core as replay


def check():
    passed = []
    def require(value, label):
        if not value:
            raise AssertionError(label)
        passed.append(label)
    version = 'MTH_2026AA'
    atom = ['769443591', 'SRC', 'SRC/VPT', 'V-MTH_2026AA', 'N', 'Y', 'N', 'Synthetic source', 'N', '', '', '', 'ENG', '', '']
    attr = ['1', '769443591', 'C', 'SEMANTIC_TYPE', 'Intellectual Product', 'SRC', 'R', 'Y', 'N', 'N', 'SRC_ATOM_ID', '', '', hashlib.md5(b'Intellectual Product').hexdigest(), '']
    relationship = ['1', 'C', 'CNEW', 'BT', '', 'COLD', version, version, 'R', 'n', 'N', 'N', 'CUI_CURRENT', '', 'CUI_PREVIOUS', '', '', '', '']
    rows = {'classes_atoms.src': [atom], 'attributes.src': [attr], 'relationships.src': [relationship],
            'bequeathal.relationships.src': [relationship],
            'mergefacts.src': [['COLD', 'SY', 'CNEW', version, '', 'N', 'N', 'META-MERGE', 'CUI', '', 'CUI_CURRENT', '', '']],
            'contexts.src': [['769443591', 'PAR', '', '769443591', version, version, '', '769443591', '11', '', '', '769443591', 'SRC_ATOM_ID', '', '769443591', 'SRC_ATOM_ID', '', '', '']]}
    with tempfile.TemporaryDirectory(prefix='mth-replay-check-') as directory:
        root = Path(directory)
        paths = {name: root / name for name in rows}
        def validate(data):
            for name, records in data.items():
                paths[name].write_text(''.join('|'.join(record) + '\n' for record in records))
            return comparator.structure(paths, (769443591, 773943592))
        good = validate(rows)
        require(good['passed'], 'MTH dialect accepts two reserved SRC IDs and 19-field contexts')
        require('CUI_PREVIOUS|' in good['files']['bequeathal.relationships.src']['identifier_types_and_qualifiers'], 'previous-CUI role retained independently from current-CUI role')
        orphan = copy.deepcopy(rows)
        orphan['attributes.src'][0][1] = '769443592'
        result = validate(orphan)
        require(not result['passed'] and result['files']['attributes.src']['violations'].get('unresolved_atom_reference') == 1,
                'attribute targeting an atom removed after map generation is rejected')
        blank = copy.deepcopy(rows)
        blank['attributes.src'][0][1] = ''
        blank['attributes.src'][0][3] = 'CONTEXT'
        blank['attributes.src'][0][4] = '1\t::~~SRC_ATOM_ID~~~SRC_ATOM_ID~\tSynthetic Root\tPARTS\t\t'
        blank['attributes.src'][0][13] = hashlib.md5(blank['attributes.src'][0][4].encode()).hexdigest()
        blank['contexts.src'][0][0] = ''
        blank['contexts.src'][0][11] = ''
        result = validate(blank)
        require(not result['passed'] and result['files']['attributes.src']['violations'].get('unresolved_atom_reference') == 1
                and result['files']['contexts.src']['violations'].get('unresolved_atom_reference') == 2,
                'blank mapped context node rejects both its context and attribute with explicit endpoint counts')
        for problem, name, index, value in [
            ('atom below the complete reserved range', 'classes_atoms.src', 0, '769443590'),
            ('incorrect attribute digest', 'attributes.src', 4, 'different value'),
            ('unresolved atom endpoint', 'attributes.src', 1, '999999'),
            ('unresolved context path', 'contexts.src', 7, '999999'),
            ('nonempty second context tail', 'contexts.src', 17, 'unexpected'),
            ('unmapped relationship', 'relationships.src', 3, 'XX-unknown')]:
            damaged = copy.deepcopy(rows)
            damaged[name][0][index] = value
            require(not validate(damaged)['passed'], problem + ' rejected')
        damaged = copy.deepcopy(rows)
        damaged['contexts.src'][0].pop()
        require(not validate(damaged)['passed'], 'SNOMED 18-field context shape cannot silently replace MTH shape')
        old = ('|'.join(relationship) + '\n').encode()
        changed = relationship.copy()
        changed[14] = 'CUI_CURRENT'
        require(not compare_sorted(iter([old]), iter([('|'.join(changed) + '\n').encode()]))['equal_preserving_multiplicity'], 'CUI_CURRENT/PREVIOUS change cannot pass full-record comparison')
        require(not compare_sorted(iter([old, old]), iter([old]))['equal_preserving_multiplicity'], 'duplicate historical relationship loss detected')
        # Exercise the actual transition command against a previous installed
        # CUI and a newly split CUI; no database or operational path is used.
        current = root / 'transitions/MTH_2026AA'
        prior = root / 'transitions/MTH_2025AB'
        src = current / 'src'
        src.mkdir(parents=True)
        (prior / 'src').mkdir(parents=True)
        (current / 'old').symlink_to('../MTH_2025AB')
        (prior / 'src/cui_said_map').write_text('C_KEEP|900\n')
        (src / 'aui_said_map').write_text('A1|C_REGULAR|N|1001\nA2|C_KEEP|Y|1002\nA3|C_ANOTHER|N|1003\nA4|C_NEW|Y|1004\nA5|C_OTHER|N|1005\n')
        subprocess.run(['/bin/bash', '-e', '-o', 'pipefail', '-c', replay.SCRIPTS['identity-transitions']], cwd=src,
                       env=dict(os.environ, LC_ALL='C', _POSIX2_VERSION='1'), check=True, capture_output=True)
        require((src / 'moved_aui_said_map').read_text().splitlines() == ['A2|C_KEEP|1002', 'A4|C_NEW|1004'], 'moved AUI identity state regenerated')
        require((src / 'cui.splitonly.new').read_text().splitlines() == ['C_NEW'], 'prior installed CUI excluded from newly split-only CUI set')
        require(len((src / 'aui_said_map').read_text().splitlines()) == 3 and all(len(line.split('|')) == 3 for line in (src / 'aui_said_map').read_text().splitlines()), 'current and moved AUI maps remain distinct')
        # A missing prior-state receipt must not be accepted as an empty map.
        isolated_root = root / 'missing-prior'
        (isolated_root / 'sources/MTH_2025AB').mkdir(parents=True)
        with patch.object(replay, 'ROOT', isolated_root):
            try:
                replay.restore_prior_map({'prior_map': {'sha256': '0' * 64}})
            except RuntimeError:
                require(True, 'unverified prior source folder rejected')
            else:
                raise AssertionError('Missing identity state accepted')
        # Late publication failure must return the original dev tree to its
        # original path, without any generated output becoming a candidate.
        case = root / 'preservation'
        source_root = case / 'sources'
        target = source_root / version
        (target / 'src').mkdir(parents=True)
        (target / 'src/classes_atoms.src').write_bytes(b'previous dev data\n')
        archive = source_root / (version + '.tgz')
        metadata = []
        with tarfile.open(archive, 'w:gz') as tar:
            for relative in replay.METADATA:
                data = (version + '|MTH_2025AB|\n').encode() if relative == 'src/sources.src' else b'fixture\n'
                member = tarfile.TarInfo(version + '/' + relative)
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
                metadata.append({'relative_path': relative, 'sha256': hashlib.sha256(data).hexdigest()})
        package = {'engine_ref': replay.BASELINE, 'metadata_inputs': metadata, 'archive_path': str(archive),
                   'archive_sha256': replay.identity(archive)['sha256'], 'code_files': [],
                   'prior_map': {}, 'prepared_subset': {}}
        def publish(source, destination):
            if source.name.startswith('.MTH_2026AA.prepare-'):
                raise OSError('simulated candidate publication failure')
            source.rename(destination)
        with patch.multiple(replay, ROOT=case, TARGET=target), patch.object(replay, 'guard'), patch.object(replay, 'idle'), patch.object(replay, 'restore_prior_map'), patch.object(replay, 'available_memory', return_value=30 * 1024 ** 3), patch.object(replay.shutil, 'disk_usage', return_value=type('Space', (), {'free': 80 * 1024 ** 3})()), patch.object(replay, 'publish', side_effect=publish):
            try:
                replay.prepare(package, progress=lambda *a, **k: None)
            except OSError:
                require((target / 'src/classes_atoms.src').read_bytes() == b'previous dev data\n', 'late preparation failure restores the original dev path and bytes')
                require(not (source_root / 'MTH_2026AA.before-replay-20261105').exists(), 'failed candidate publication leaves no misleading preserved/current pair')
            else:
                raise AssertionError('Publication failure ignored')
        target.chmod(0o750)
        (target / 'src').chmod(0o750)
        (target / 'src/classes_atoms.src').chmod(0o640)
        def safe_publish(source, destination):
            if destination.exists():
                raise FileExistsError(destination)
            source.rename(destination)
        try:
            with patch.multiple(replay, ROOT=case, TARGET=target), patch.object(replay, 'guard'), patch.object(replay, 'idle'), patch.object(replay, 'restore_prior_map'), patch.object(replay, 'verify_inputs'), patch.object(replay, 'available_memory', return_value=30 * 1024 ** 3), patch.object(replay.shutil, 'disk_usage', return_value=type('Space', (), {'free': 80 * 1024 ** 3})()), patch.object(replay, 'publish', side_effect=safe_publish):
                result = replay.prepare(package, progress=lambda *a, **k: None)
            previous = Path(result['preexisting_dev_preserved'])
            require(previous.stat().st_mode & 0o777 == 0o550 and (previous / 'src/classes_atoms.src').stat().st_mode & 0o777 == 0o440, 'read-only preservation retains restricted original read/execute access')
            require(not (target / 'src/classes_atoms.src').exists(), 'fresh candidate cannot inherit preexisting generated output')
        finally:
            for base, dirs, files in os.walk(case, followlinks=False):
                Path(base).chmod(0o700)
    return passed


if __name__ == '__main__':
    results = check()
    for item in results:
        print('PASS ' + item)
    print(str(len(results)) + ' MTH replay checks passed')
