#!/usr/bin/env python3
"""Exercise SNOMED stage selection, strict comparison and runtime preservation."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

import compare_snomed_core as comparison
import prepare_snomed_candidate as preparation
import run_snomed_core_replay as runner


def check(contract):
    passed = []
    def require(value, name):
        if not value:
            raise AssertionError(name)
        passed.append(name)
    preparation.selected_inputs(contract)
    require(True, 'eighteen declared conversion/metadata inputs and original attributes reference accepted')
    for problem in ['enriched-reference', 'generated-input', 'missing-native']:
        invalid = copy.deepcopy(contract)
        if problem == 'enriched-reference':
            next(x for x in invalid['reference_file_map'] if x['output_name'] == 'attributes.src')['reference_path'] = preparation.VERSION + '/src/attributes.src'
        elif problem == 'generated-input':
            invalid['conversion_inputs'][0]['path'] = preparation.VERSION + '/src/classes_atoms.src'
        else:
            invalid['conversion_inputs'][0]['present'] = False
        try:
            preparation.selected_inputs(invalid)
        except RuntimeError:
            require(True, problem + ' rejected before candidate preparation')
        else:
            raise AssertionError(problem + ' was accepted')
    files = {name: {'exact_match': True} for name in preparation.CORE_NAMES}
    require(comparison.verdict(files, True)['status'] == 'PASS_EXACT', 'all five exact files with passing checks accepted')
    require(comparison.verdict(files, False)['status'] == 'REFERENCE_REPRODUCED_WITH_VALIDATION_FINDINGS', 'reference equality cannot suppress independent validation findings')
    files['attributes.src'] = {'exact_match': False, 'full_record_multiset': {'equal_preserving_multiplicity': True}}
    require(comparison.verdict(files, True)['status'] == 'PASS_RECORD_EQUIVALENT', 'only full-record reordering can pass non-exact comparison')
    files['attributes.src']['full_record_multiset']['equal_preserving_multiplicity'] = False
    require(comparison.verdict(files, True)['status'] == 'DIFFERENCES_REQUIRE_REVIEW', 'changed IDs or any record content cannot be waived')
    del files['contexts.src']
    require(comparison.verdict(files, True)['status'] == 'DIFFERENCES_REQUIRE_REVIEW', 'incomplete output set rejected')
    version = preparation.VERSION
    left, right = '777343593', '777343594'
    def row(fields):
        return '|'.join(fields) + '\n'
    def atom(said, cui, aui):
        return [said, version, version + '/PT', cui, 'R', 'Y', 'N', 'Synthetic term', 'N', aui, cui, '', 'ENG', '1', '']
    def attribute(number, endpoint, kind):
        return [number, endpoint, 'S', 'DESCRIPTION_LENGTH', '1', version, 'R', 'n', 'N', 'N', kind, version, '', hashlib.md5(b'1').hexdigest(), '']
    fixture = {
        'classes_atoms.src': [atom(left, '138875005', '10010'), atom(right, '1001', '10011')],
        'attributes.src': [attribute('3', '10011', 'SOURCE_AUI'), attribute('7', right, 'SRC_ATOM_ID')],
        'relationships.src': [['1', 'S', '138875005', 'RT', 'mapped_to', '1001', version, version, 'R', 'Y', 'N', 'N', 'SOURCE_CUI', version, 'SOURCE_CUI', version, '123', '2', '']],
        'mergefacts.src': [['10011', 'SY', '1001', version, '', 'N', 'N', 'SNOMEDCT_US-SCUI', 'SOURCE_AUI', version, 'SOURCE_CUI', version, '']],
        'contexts.src': [[right, 'PAR', 'isa', left, version, version, '', left, '00', '123', '0', '1001', 'SOURCE_CUI', version, '138875005', 'SOURCE_CUI', version, '']]}
    with tempfile.TemporaryDirectory(prefix='snomed-replay-check-') as directory:
        root = Path(directory)
        paths = {name: root / name for name in fixture}
        def validate(rows):
            for name, data in rows.items():
                paths[name].write_text(''.join(row(x) for x in data))
            return comparison.structure(paths, {(version + '/PT').encode()}, (777343593, 779143592))
        require(validate(fixture)['passed'], 'valid typed records and non-contiguous attribute IDs accepted')
        for defect, name, index, column, value in [
            ('duplicate attribute ID', 'attributes.src', 1, 0, '3'),
            ('dangling description attribute', 'attributes.src', 0, 1, '999999'),
            ('attribute value digest corruption', 'attributes.src', 0, 4, 'changed'),
            ('missing term type', 'classes_atoms.src', 1, 2, version + '/'),
            ('unmapped relationship', 'relationships.src', 0, 3, 'XX-999'),
            ('unknown endpoint type', 'mergefacts.src', 0, 8, 'UNKNOWN'),
            ('unresolved context path', 'contexts.src', 0, 7, '999999'),
            ('wrong context child identity', 'contexts.src', 0, 11, '999999'),
            ('wrong context parent identity', 'contexts.src', 0, 14, '999999'),
            ('out-of-range atom ID', 'classes_atoms.src', 0, 0, '777343592')]:
            damaged = copy.deepcopy(fixture)
            damaged[name][index][column] = value
            require(not validate(damaged)['passed'], defect + ' detected')
        for failure in [False, True]:
            case = root / ('preserve-failure' if failure else 'runtime-success')
            library = case / 'INV/lib/Hierarchy.pm'
            library.parent.mkdir(parents=True)
            library.write_bytes(b'old candidate library\n')
            (case / 'candidate-runtime.json').write_text('{}\n')
            run = case / 'run'
            run.mkdir()
            raw = b'baseline library\n'
            package = {'runtime_files': [{'relative_path': 'INV/lib/Hierarchy.pm', 'sha256': hashlib.sha256(raw).hexdigest()}],
                       'previous_hierarchy_sha256': preparation.info(library)['sha256'],
                       'baseline_hierarchy_b64': base64.b64encode(raw).decode()}
            try:
                with patch.multiple(runner, ROOT=case, RUN=run), patch.object(runner, 'require_idle'):
                    if failure:
                        original_copy = shutil.copy2
                        def failing_copy(source, destination):
                            if Path(source).name == 'candidate-runtime.json':
                                raise OSError('simulated receipt preservation failure')
                            return original_copy(source, destination)
                        with patch.object(runner.shutil, 'copy2', side_effect=failing_copy):
                            try:
                                runner.activate_baseline(package)
                            except OSError:
                                pass
                            else:
                                raise AssertionError('Preservation failure was ignored')
                        require(library.read_bytes() == b'old candidate library\n', 'late preservation failure leaves installed library unchanged')
                    else:
                        runner.activate_baseline(package)
                        require(library.read_bytes() == raw, 'only declared baseline library installed')
                        preserved = run / 'runtime-before/Hierarchy.pm'
                        require(preserved.read_bytes() == b'old candidate library\n' and not preserved.stat().st_mode & 0o222, 'prior library bytes preserved read-only before runtime activation')
            finally:
                for path in case.rglob('*'):
                    if path.is_dir():
                        path.chmod(0o700)
    return passed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/inversion-review/snomedct-us-2026-09-01-input-output-contract.json')
    arguments = parser.parse_args()
    checks = check(json.loads(arguments.contract.read_text()))
    for item in checks:
        print('PASS ' + item)
    print(str(len(checks)) + ' SNOMED replay checks passed')
