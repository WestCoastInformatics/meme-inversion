#!/usr/bin/env python3
"""Archive three old dev test trees; expanded copies are retained in this phase."""
import datetime
import json
import os
from pathlib import Path
import tempfile
import traceback

import archive_retained_source as retention

CONTROL = Path(__file__).resolve().parent
SELECTED = [('MTH_2026AA.before-replay-20261105', 'mth-before-replay-20261105-20261110'),
            ('MTH_2026AA.before-consistency-20261106', 'mth-before-consistency-20261106-20261110'),
            ('SNOMEDCT_US_2026_09_01.before-common-snomedct-us-1-20261106', 'snomed-before-common-20261106-20261110')]
state = {'status': 'starting', 'phase': 'archive-and-verify-only', 'archives': [],
         'source_retirement_performed': False}


def save():
    state['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    descriptor, name = tempfile.mkstemp(prefix='.status-', dir=str(CONTROL))
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(state, handle, indent=2)
        handle.write('\n')
    os.replace(name, CONTROL / 'status.json')


try:
    retention.guard()
    save()
    for name, namespace in SELECTED:
        state.update(status='archiving', current_source=name)
        save()
        result = retention.archive(retention.ROOT / 'sources' / name,
                                   retention.ROOT / 'qa/retained-source-archives' / namespace,
                                   retire=False)
        assert result['status'] == 'ARCHIVED_AND_VERIFIED' and result['source_retired'] is False
        state['archives'].append(result)
        save()
    with (CONTROL / 'archive-results.json').open('x') as handle:
        json.dump(state['archives'], handle, indent=2)
        handle.write('\n')
    (CONTROL / 'archive-results.json').chmod(0o444)
    state.update(status='complete', archives_verified=len(state['archives']))
except BaseException as error:
    state.update(status='failed', error=str(error))
    traceback.print_exc()
finally:
    save()
