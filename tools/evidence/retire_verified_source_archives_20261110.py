#!/usr/bin/env python3
"""Retire only the three expanded copies bound to reviewed archive receipts."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import traceback

import archive_retained_source as retention

CONTROL = Path(__file__).resolve().parent
SELECTED = ['MTH_2026AA.before-replay-20261105', 'MTH_2026AA.before-consistency-20261106',
            'SNOMEDCT_US_2026_09_01.before-common-snomedct-us-1-20261106']
state = {'status': 'preflight', 'retired': [], 'official_archives_changed': False,
         'current_source_directories_changed': False}


def save():
    state['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state['free_disk_gib'] = round(shutil.disk_usage(retention.ROOT).free / 1024**3, 3)
    descriptor, name = tempfile.mkstemp(prefix='.retirement-status-', dir=str(CONTROL))
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(state, handle, indent=2)
        handle.write('\n')
    os.replace(name, CONTROL / 'retirement-status.json')


try:
    retention.guard()
    request = json.loads((CONTROL / 'retirement-request.json').read_text())
    raw = (CONTROL / 'archive-results.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == request['archive_results_sha256']
    results = json.loads(raw)
    assert [Path(item['source']).name for item in results] == SELECTED
    assert results == request['archives']
    assert all(item['status'] == 'ARCHIVED_AND_VERIFIED' and not item['source_retired'] for item in results)
    save()
    for item in results:
        state.update(status='retiring', current_source=Path(item['source']).name)
        save()
        result = retention.retire(item['source'], item['archive'], item['receipt'], item['receipt_sha256'])
        assert result['status'] == 'RETIRED_VERIFIED_EXPANDED_COPY'
        state['retired'].append(result)
        save()
    state.update(status='complete', verified_archives_retained=len(state['retired']))
except BaseException as error:
    state.update(status='failed', error=str(error))
    traceback.print_exc()
finally:
    save()
