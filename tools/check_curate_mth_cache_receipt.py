#!/usr/bin/env python3
"""Pure receipt projection checked against a real confined cache publication."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

import cache_mth_prior_identity as cache
import check_mth_prior_identity_cache as fixtures
import curate_archived_mth as curator
import release_mth


def seal(receipt):
    receipt['receipt_sha256'] = release_mth.artifact_sha256({key: value for key, value in receipt.items() if key != 'receipt_sha256'})


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def rejected(receipt, label):
        try:curator.prior_identity_from_cache_receipt(receipt)
        except (ValueError, KeyError):checks.append(label);return
        raise AssertionError(label)
    with fixtures.cache_only_fixture() as original:
        receipt = cache.publish_cache(original);before = copy.deepcopy(receipt)
        with patch.object(Path, 'open', side_effect=AssertionError('Pure projection opened filesystem data')):
            projected = curator.prior_identity_from_cache_receipt(receipt)
        good(projected['files'] == [receipt['cache_file']] and projected['facts'] == {**receipt['map_identity'], 'malformed_rows': 0},
             'pure curator projects exact captured cache SHA/bytes/row facts without filesystem reads')
        good(projected['immutable_cache_publication'] == receipt and receipt == before,
             'full original S3/container/cache receipt provenance is preserved without mutation')
        original_path = Path(original['target']);original_path.rename(original_path.with_name(original_path.name + '.preserved-fixture'))
        good(curator.prior_identity_from_cache_receipt(receipt) == projected,
             'projection does not depend on the canonical origin or its receipt remaining present')
        normalized = curator.normalize({'version': 'MTH_2024AA', 'archive': {'uri': 's3://synthetic-bucket/source.tgz',
            'sha256': 'a' * 64, 'bytes': 100}, 'members': {}, 'prior_identity': receipt})
        good(normalized['prior_identity'] == projected, 'normalized capture accepts explicit sealed cache receipt as prior identity')
        good(curator.normalize(normalized) == normalized, 'cache receipt normalization is idempotent')
        for field in ('locator', 'facts'):
            changed = copy.deepcopy(normalized)
            if field == 'locator':changed['prior_identity']['files'][0]['uri'] = receipt['original_locator']
            else:changed['prior_identity']['facts']['rows'] += 1
            try:curator.normalize(changed)
            except ValueError:checks.append('normalized cache projection cannot hide changed ' + field)
            else:raise AssertionError('Altered projected cache descriptor accepted')
        changed = copy.deepcopy(receipt);changed['cache_file']['bytes'] += 1
        rejected(changed, 'modified cache seal rejected')
        changed = copy.deepcopy(receipt);changed['cache_file']['uri'] = changed['original_locator'];seal(changed)
        rejected(changed, 'canonical origin cannot be promoted to active descriptor by resealing outer receipt')
        changed = copy.deepcopy(receipt);changed['cache_directory'] += '.alternate';seal(changed)
        rejected(changed, 'nonstandard independent cache directory rejected')
        changed = copy.deepcopy(receipt);changed['map_identity']['rows'] += 1;seal(changed)
        rejected(changed, 'cache map facts must match original captured identity')
        changed = copy.deepcopy(receipt);changed['original_capture_receipt']['archive_sha256'] = 'b' * 64;seal(changed)
        rejected(changed, 'outer seal cannot hide changed original capture seal')
        changed = copy.deepcopy(receipt);changed['original_capture_receipt']['request']['key'] = 'inv/sources/unrelated.tgz'
        seal(changed['original_capture_receipt']);changed['original_capture_receipt_sha256'] = changed['original_capture_receipt']['receipt_sha256'];seal(changed)
        rejected(changed, 'original source namespace remains independently constrained after both seals recomputed')
        for key, value in [('independent_copy', False), ('hardlink_used', True), ('symlink_used', True),
                           ('native_execution_performed', True), ('production_eligible', True), ('copy_reserve_bytes', 0)]:
            changed = copy.deepcopy(receipt);changed[key] = value;seal(changed)
            rejected(changed, 'unsupported cache publication claim rejected: ' + key)
        changed = copy.deepcopy(receipt);changed['original_signature_at_copy'][2] += 1;seal(changed)
        rejected(changed, 'copy signature must describe original captured map size')
    print(json.dumps({'passed': len(checks), 'checks': checks}, indent=2))


if __name__ == '__main__':check()
