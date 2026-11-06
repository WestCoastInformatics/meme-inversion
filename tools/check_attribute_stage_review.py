#!/usr/bin/env python3
"""Verify archive-stage evidence without filtering or regenerating any records."""
import copy
import io
from pathlib import Path
import tarfile
import tempfile

from inspect_inversion_archive import attribute_stage_relation, inspect


def attribute(number, name='DEFINITION', value='fixture'):
    return ('|'.join([str(number), '123', 'S', name, value, 'FIXTURE', 'R', 'Y', 'N', 'N',
                      'SRC_ATOM_ID', '', '', 'fixture-digest', '']) + '\n').encode()


def check():
    values = []
    def require(condition, label):
        assert condition, label
        values.append(label)
    def rejected(action, label):
        try:action()
        except ValueError:values.append(label)
        else:raise AssertionError(label)
    version = 'MDR_29_1'
    original = attribute(1, 'SEMANTIC_TYPE') + attribute(2)
    suffix = attribute(3, 'SEMANTIC_TYPE') + attribute(4, 'SEMANTIC_TYPE')
    with tempfile.TemporaryDirectory(prefix='attribute-stage-review-') as temporary:
        root = Path(temporary)
        def archive(name, before, after, symlink=False):
            path = root / (name + '.tgz')
            with tarfile.open(path, 'w:gz') as handle:
                for filename, raw in [('attributes.orig', before), ('attributes.src', after)]:
                    if raw is None:continue
                    item = tarfile.TarInfo(version + '/src/' + filename)
                    if symlink and filename == 'attributes.orig':
                        item.type = tarfile.SYMTYPE;item.linkname = 'attributes.src';handle.addfile(item)
                    else:
                        item.size = len(raw);handle.addfile(item, io.BytesIO(raw))
            return path, inspect(path, version)
        path, inventory = archive('normal', original, original + suffix)
        result = attribute_stage_relation(path, inventory)
        require(result['status'] == 'PRE_INSERTION_PREFIX_VERIFIED' and result['original_rows'] == 2 and result['appended_rows'] == 2,
                'Exact original bytes plus semantic-type-only additions establish the archive stage relation')
        require(result['original_semantic_types_retained'] == 1 and result['original_attribute_names']['SEMANTIC_TYPE'] == 1,
                'Legitimate original semantic types remain in the comparison reference')
        require(not result['candidate_executed'] and not (root / version).exists(), 'Stage review neither executes nor extracts a candidate')
        path, inventory = archive('identical', original, original)
        require(attribute_stage_relation(path, inventory)['status'] == 'IDENTICAL_ATTRIBUTE_STAGES',
                'Identical files do not acquire a claim that semantic types were appended')
        for name, before, after, symlink in [
            ('changed-prefix', original, original.replace(b'fixture', b'changed', 1) + suffix, False),
            ('additional-non-sty', original, original + attribute(3), False),
            ('malformed-suffix', original, original + b'3|123|S|SEMANTIC_TYPE|short\n', False),
            ('missing-original', None, original + suffix, False),
            ('symlink-original', original, original + suffix, True),
            ('split-record-boundary', original + b'partial', original + suffix, False),
            ('empty-original', b'', original, False)]:
            path, inventory = archive(name, before, after, symlink)
            rejected(lambda: attribute_stage_relation(path, inventory), 'Unverified stage boundary rejected: ' + name)
        path, inventory = archive('changed-archive', original, original + suffix)
        with path.open('ab') as handle:handle.write(b'changed bytes')
        rejected(lambda: attribute_stage_relation(path, inventory), 'Changed frozen archive rejected')
        path, inventory = archive('tampered-inventory', original, original + suffix)
        changed = copy.deepcopy(inventory)
        for item in changed['entries']:
            if item['path'].endswith('attributes.orig'):item['sha256'] = '0' * 64
        rejected(lambda: attribute_stage_relation(path, changed), 'Actual original member bytes are checked against the inventory')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'attribute-stage review checks passed')
