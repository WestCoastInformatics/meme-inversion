#!/usr/bin/env python3
"""Offline negative fixtures for comparison mistakes that could hide corruption."""
import hashlib
from pathlib import Path
import tempfile

from compare_nci_core import FIELDS, aligned_differences, attribute_view, compare_sorted, structure


def check():
    passed = []

    def multiset(left, right):
        return compare_sorted(iter(sorted(left)), iter(sorted(right)))

    def require(condition, name):
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    a, b = b'a|R|group1|\n', b'b|N|group2|\n'
    require(multiset([a, b, a], [a, a, b])['equal_preserving_multiplicity'], 'reordering preserves duplicates')
    require(multiset([a, a], [a])['reference_only_rows'] == 1, 'duplicate loss detected')
    require(multiset([a], [a, a])['candidate_only_rows'] == 1, 'duplicate addition detected')
    for name, changed in [('status', b'a|N|group1|\n'), ('relationship group', b'a|R|group2|\n'),
                          ('trailing empty field', b'a|R|group1\n'), ('qualifier', b'a|R|group1|SRC|\n')]:
        require(not multiset([a], [changed])['equal_preserving_multiplicity'], name + ' change detected')
    with tempfile.TemporaryDirectory(prefix='nci-comparison-fixtures-') as directory:
        root = Path(directory)
        atom = [b'100', b'NCI', b'NCI/PT', b'C1', b'R', b'Y', b'N', b'Name', b'N', b'', b'C1', b'', b'ENG', b'', b'']
        old = b'|'.join(atom) + b'\n'
        updated = list(atom)
        updated[7] = b'Edited name'
        difference = aligned_differences(iter([old]), iter([b'|'.join(updated) + b'\n']), 'classes_atoms.src')
        require(difference['changed_fields'] == {'atom_name': 1}, 'atom text change isolated by field')
        paths = {}
        for name, labels in FIELDS.items():
            values = [b''] * len(labels)
            if name == 'classes_atoms.src':
                values = atom
            elif name == 'attributes.src':
                values = [b'1', b'100', b'S', b'TEST', b'value', b'NCI', b'R', b'Y', b'N', b'N',
                          b'SRC_ATOM_ID', b'', b'', hashlib.md5(b'value').hexdigest().encode(), b'']
            elif name == 'relationships.src':
                for index, value in [(0, b'1'), (2, b'100'), (5, b'100'), (12, b'SRC_ATOM_ID'), (14, b'SRC_ATOM_ID')]:
                    values[index] = value
            elif name == 'mergefacts.src':
                for index, value in [(0, b'100'), (2, b'100'), (8, b'SRC_ATOM_ID'), (10, b'SRC_ATOM_ID')]:
                    values[index] = value
            else:
                for index, value in [(0, b'100'), (3, b'31926003'), (7, b'31926003'), (11, b'100'),
                                     (12, b'SRC_ATOM_ID'), (14, b'31926003'), (15, b'SRC_ATOM_ID')]:
                    values[index] = value
            paths[name] = root / name
            paths[name].write_bytes(b'|'.join(values) + b'\n')
        require(structure(paths, 31926003)['checks_passed'], 'configured external root accepted')
        require(structure(paths, 31926003, {b'NCI/PT'})['checks_passed'], 'declared preferred-term group accepted')
        paths['classes_atoms.src'].write_bytes(old.replace(b'NCI/PT', b'NCI/'))
        require(not structure(paths, 31926003, {b'NCI/PT'})['checks_passed'], 'missing preferred-term type rejected')
        paths['classes_atoms.src'].write_bytes(old)
        attr = paths['attributes.src'].read_bytes()
        reference_view = root / 'ref.view'
        candidate_view = root / 'candidate.view'
        attribute_view(paths['attributes.src'], reference_view)
        paths['attributes.src'].write_bytes(b'99|' + attr.split(b'|', 1)[1])
        attribute_view(paths['attributes.src'], candidate_view)
        require(reference_view.read_bytes() == candidate_view.read_bytes(), 'explicit generated attribute ID view')
        paths['attributes.src'].write_bytes(attr.replace(b'|value|', b'|changed|'))
        require(not structure(paths, 31926003)['checks_passed'], 'attribute value digest corruption detected')
        bad_view = root / 'bad.view'
        attribute_view(paths['attributes.src'], bad_view)
        require(bad_view.read_bytes() != reference_view.read_bytes(), 'attribute content never discarded')
        paths['attributes.src'].write_bytes(attr + attr)
        duplicate_view = attribute_view(paths['attributes.src'], root / 'duplicate.view')
        require(duplicate_view['duplicate_ids'] == 1, 'duplicate generated attribute IDs detected')
        paths['attributes.src'].write_bytes(attr)
        context = paths['contexts.src'].read_bytes()
        paths['contexts.src'].write_bytes(context.replace(b'31926003', b'999'))
        require(not structure(paths, 31926003)['checks_passed'], 'unresolved context endpoints and paths detected')
        paths['contexts.src'].write_bytes(context)
        paths['classes_atoms.src'].write_bytes(old + old)
        require(not structure(paths, 31926003)['checks_passed'], 'duplicate atom IDs detected')
    return passed


if __name__ == '__main__':
    checks = check()
    print(str(len(checks)) + ' comparison fixtures passed')
    for name in checks:
        print('PASS ' + name)
