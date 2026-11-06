#!/usr/bin/env python3
"""Check run locking and preservation contracts without operational paths."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import replay_mth_core as replay


def check():
    values = []
    def require(condition, label):
        assert condition, label
        values.append(label)
    def rejected(action, label):
        try:
            action()
        except (RuntimeError, FileNotFoundError):
            values.append(label)
        else:
            raise AssertionError(label)
    with patch.multiple(replay, RUN_ID=replay.RUN_ID, RUN=replay.RUN):
        replay.configure_case({'engine_ref': replay.BASELINE, 'run_id': 'candidate-20261106'})
        require(replay.RUN.name == 'candidate-20261106', 'Explicit case receives a separate run directory')
        for run_id in ['../other', '/tmp/other', 'bad name', '']:
            rejected(lambda: replay.configure_case({'engine_ref': replay.BASELINE, 'run_id': run_id}), 'Unsafe run identity rejected: ' + repr(run_id))
        rejected(lambda: replay.configure_case({'engine_ref': 'HEAD'}), 'Mutable engine name rejected')
        rejected(lambda: replay.configure_case({'engine_ref': replay.BASELINE, 'runtime_ref': 'other'}), 'Unreviewed shared runtime rejected')
    with tempfile.TemporaryDirectory(prefix='mth-case-lock-') as temporary:
        root = Path(temporary)
        active = root / 'replay-active-run.json'
        state = {'status': 'complete', 'run_id': 'original', 'engine_ref': replay.BASELINE}
        active.write_text(json.dumps(state))
        result = root / 'qa/replay-runs/original/result.json'
        result.parent.mkdir(parents=True)
        result.write_text('{"complete":true}\n')
        output = root / 'src/classes_atoms.src'
        output.parent.mkdir()
        output.write_bytes(b'baseline data\n')
        package = {'reference_files': [{'output_name': output.name}], 'previous_run': {'run_id': 'original', 'engine_ref': replay.BASELINE,
                   'result_sha256': hashlib.sha256(result.read_bytes()).hexdigest(), 'outputs': [{'output_name': output.name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}]}}
        with patch.multiple(replay, TARGET=root, ACTIVE=active):
            replay.verify_previous_run(package)
            values.append('Complete prior result and every original output verified')
            bad = copy.deepcopy(package)
            bad['previous_run']['outputs'] = []
            rejected(lambda: replay.verify_previous_run(bad), 'Incomplete prior-output contract rejected')
            state['status'] = 'running'
            active.write_text(json.dumps(state))
            rejected(lambda: replay.verify_previous_run(package), 'Active previous inversion cannot be replaced')
            state['status'] = 'complete'
            active.write_text(json.dumps(state))
            output.write_bytes(b'changed data\n')
            rejected(lambda: replay.verify_previous_run(package), 'Modified prior output cannot be preserved as verified baseline')
        source = root / 'invert2.s'
        source.write_text('    $INV_HOME_OLD/bin/autoinv.pl ../range$subset.spec inv1.spec >>& autoinv.log\n    echo retained\n    ln -s aui_said_map aui_said_map2\n')
        require(replay.source_identity_script(source) == 'set subset=3\n    echo retained\n', 'Identity recipe comes from the selected source file')
        source.write_text('unknown producer layout\n')
        rejected(lambda: replay.source_identity_script(source), 'Unknown producer layout fails before execution')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH case-lock checks passed')
