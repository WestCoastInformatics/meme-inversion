#!/usr/bin/env python3
"""Offline checks that incomplete or changed UMLS inputs cannot be published."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import acquire_mth_subset as subset


def check():
    passed = []
    def require(value, label):
        if not value:
            raise AssertionError(label)
        passed.append(label)
    data = {name: (name + '\n').encode() for name in subset.NAMES}
    objects = [{'key': 'mr/umls/2026AA/subset3/METASUBSET/' + name, 'bytes': len(raw),
                'etag': '"' + hashlib.md5(raw).hexdigest() + '"'} for name, raw in data.items()]
    request = {'source': 'MTH', 'version': 'MTH_2026AA', 'umls_release': '2026AA', 'objects': objects}
    require(len(subset.select(request)) == 11, 'all eleven explicit prepared inputs accepted')
    for damage in ['traversal', 'missing-object', 'missing-identity']:
        invalid = copy.deepcopy(request)
        if damage == 'traversal':
            invalid['objects'][0]['key'] = 'mr/umls/2026AA/../../unexpected'
        elif damage == 'missing-object':
            invalid['objects'].pop()
        else:
            invalid['objects'][0]['etag'] = ''
        try:
            subset.select(invalid)
        except RuntimeError:
            require(True, damage + ' rejected before acquisition')
        else:
            raise AssertionError(damage + ' accepted')
    with tempfile.TemporaryDirectory(prefix='mth-subset-check-') as directory:
        for mode in ['success', 'head-mismatch', 'changed-after-copy', 'copy-failure']:
            root = Path(directory) / mode
            root.mkdir()
            requests = {}
            def aws(arguments, env):
                if arguments[0] == 's3api':
                    key = arguments[arguments.index('--key') + 1]
                    name = Path(key).name
                    item = next(x for x in objects if x['key'] == key)
                    requests[key] = requests.get(key, 0) + 1
                    etag = item['etag']
                    if mode == 'head-mismatch' or mode == 'changed-after-copy' and requests[key] > 1:
                        etag = '"changed"'
                    return {'ContentLength': len(data[name]), 'ETag': etag, 'LastModified': 'fixed', 'VersionId': 'fixed'}
                assert arguments[:2] == ['s3', 'cp']
                name = Path(arguments[2]).name
                Path(arguments[3]).write_bytes(b'partial' if mode == 'copy-failure' else data[name])
                if mode == 'copy-failure':
                    raise RuntimeError('simulated failed download')
            def publish(source, destination):
                if destination.exists():
                    raise FileExistsError(destination)
                source.rename(destination)
            with patch.object(subset, 'ROOT', root), patch.object(subset, 'guard'), patch.object(subset, 'aws', side_effect=aws), patch.object(subset, 'publish', side_effect=publish), patch.object(subset.shutil, 'disk_usage', return_value=type('Space', (), {'free': 80 * 1024 ** 3})()):
                if mode != 'success':
                    try:
                        subset.acquire(request, progress=lambda *a, **k: None)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError(mode + ' was published')
                    require(not (root / '2026AA').exists(), mode + ' leaves the complete release path absent')
                    require(len(list(root.glob('.2026AA.inputs-*/acquisition-failed.json'))) == 1, mode + ' retains diagnostic staging and failure receipt')
                else:
                    receipt = subset.acquire(request, progress=lambda *a, **k: None)
                    target = root / '2026AA'
                    require(len(receipt['files']) == 11 and (target / 'DVDIMAGE').is_dir(), 'complete subset and production symlink compatibility directory published')
                    require(all(not (target / x['relative_path']).stat().st_mode & 0o222 for x in receipt['files']), 'frozen input files are read-only')
                    require(subset.acquire(request) == receipt, 'verified frozen inputs reused without downloading')
                    first = target / receipt['files'][0]['relative_path']
                    first.chmod(0o600)
                    first.write_bytes(b'corrupted')
                    try:
                        subset.acquire(request)
                    except RuntimeError:
                        require(first.read_bytes() == b'corrupted', 'changed cache is rejected without overwriting evidence')
                    else:
                        raise AssertionError('Changed cache was accepted')
    return passed


if __name__ == '__main__':
    results = check()
    for label in results:
        print('PASS ' + label)
    print(str(len(results)) + ' prepared-subset acquisition checks passed')
