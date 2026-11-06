#!/usr/bin/env python3
"""Negative fixtures for final MTH identity-state closure."""
import copy
from pathlib import Path
import tempfile
from compare_mth_core import identity_state


def check():
    passed = []
    def require(value, label):
        assert value, label
        passed.append(label)
    rows = {}
    for said, cui, aui, moved in [('100', 'C1', 'A1', 'N'), ('101', 'C2', 'A2', 'Y')]:
        fields = [said, 'SAB', 'SAB/PT', 'CODE', 'R', 'Y', 'A', 'Synthetic', 'N', '', '', '', 'ENG', '', cui]
        rows.setdefault('classes_atoms.src', []).append('|'.join(fields))
        rows.setdefault('classes_atoms.src.raw', []).append('|'.join(fields[:14] + [moved, cui, aui]))
    rows.update({'aui_said_map': ['A1|C1|100'], 'moved_aui_said_map': ['A2|C2|101'],
                 'cui_said_map': ['C1|100', 'C2|101'], 'rel_cui_said_map': ['C1|100', 'C2|101'],
                 'cui_splitonly_said_map': ['C2|101']})
    with tempfile.TemporaryDirectory(prefix='mth-state-check-') as temporary:
        directory = Path(temporary)
        def validate(data):
            for name, values in data.items():
                (directory / name).write_text(''.join(value + '\n' for value in values))
            return identity_state(directory)
        require(validate(rows)['passed'], 'Retained current and moved identities bind to their actual atoms')
        for name, replacement, violation in [
            ('aui_said_map', 'A1|C1|999', 'unresolved_retained_atom'),
            ('cui_said_map', 'C_WRONG|100', 'cui_binding_mismatch'),
            ('aui_said_map', 'A_WRONG|C1|100', 'aui_binding_mismatch'),
            ('aui_said_map', 'A2|C2|101', 'moved_role_mismatch'),
            ('cui_said_map', '|100', 'empty_identity')]:
            bad = copy.deepcopy(rows)
            bad[name][0] = replacement
            result = validate(bad)
            require(not result['passed'] and result['files'][name]['violations'].get(violation), violation + ' is rejected')
        bad = copy.deepcopy(rows)
        bad['cui_said_map'].append('C1|100')
        require(validate(bad)['files']['cui_said_map']['violations'].get('duplicate_record'), 'Duplicate identity records are rejected')
        bad = copy.deepcopy(rows)
        bad['classes_atoms.src'] = bad['classes_atoms.src'][:1]
        require(validate(bad)['raw_binding_violations'].get('raw_atoms_not_retained') == 1, 'Late atom deletion cannot leave apparently valid persisted state')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH identity-state checks passed')
