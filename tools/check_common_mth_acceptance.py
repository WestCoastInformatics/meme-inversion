#!/usr/bin/env python3
"""Test correction-profile acceptance, immutable raw evidence and failure handling.

The native-data audit has its own producer-backed fixtures. These checks exercise
the common worker's orchestration and report binding without a full inversion.
"""
import base64
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import audit_mth_corrections as audit
import inversion_remote as remote
import inversion_worker as worker


def fixture(root):
    target = root / 'sources/MTH_2026AA'
    (target / 'src').mkdir(parents=True)
    run = root / 'qa/replay-requests/fixture-corrections'
    run.mkdir(parents=True)
    files = {}
    for number in range(23):
        name = 'fixture-output-' + str(number)
        path = target / 'src' / name
        path.write_bytes(('unchanged candidate ' + str(number) + '\n').encode())
        files[name] = {'candidate': {'sha256': worker.sha(path)}}
    request = {'source': 'MTH', 'version': 'MTH_2026AA', 'engine_ref': worker.MTH_CORRECTION_ENGINE,
               'case_variant': 'consistent-retained-identities', 'comparison_profile': 'reviewed-corrections'}
    runtime = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
    lock = {'request': request, 'run_id': run.name, 'apparatus_ref': '1' * 40, 'runtime_ref': runtime,
            'case': {'correction_audit': copy.deepcopy(worker.MTH_CORRECTION_AUDIT),
                     'legacy_case': {'execute_source_stages': True, 'validate_identity_state': True,
                                     'reference_files': [{'output_name': name} for name in files]}},
            'modules_b64': {'audit_mth_corrections.py': base64.b64encode(Path(audit.__file__).read_bytes()).decode()},
            'code_files': [], 'runtime_files': []}
    acceptance = {'status': 'DIFFERENCES_REQUIRE_REVIEW', 'all_compared_outputs_exact': False}
    result = {'source': 'MTH', 'version': 'MTH_2026AA', 'engine_ref': request['engine_ref'], 'run_id': run.name,
              'acceptance': copy.deepcopy(acceptance),
              'comparison': {'files': files, 'acceptance': copy.deepcopy(acceptance),
                             'validation': {'passed': True, 'identity_state': {'passed': True}}}}
    report = {'status': 'PASS_REVIEWED_CORRECTIONS', 'engine_ref': request['engine_ref'], 'run_id': run.name,
              'conversion_apparatus_ref': lock['apparatus_ref'], 'audit_tool_sha256': worker.sha(Path(audit.__file__)),
              'raw_comparison_status': 'DIFFERENCES_REQUIRE_REVIEW', 'independent_validation_passed': True,
              'raw_comparison_rewritten': False, 'production_eligible': False}
    return lock, target, run, result, report


def check():
    passed = []
    def require(condition, label):
        assert condition, label
        passed.append(label)
    def rejected(action, label):
        try:
            action()
        except (ValueError, RuntimeError, FileExistsError):
            passed.append(label)
        else:
            raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='common-mth-acceptance-') as temporary:
        root = Path(temporary)
        lock, target, run, result, report = fixture(root / 'success')
        original = copy.deepcopy(result)
        def child(command, **options):
            assert command[-2:] == ['--result', str(run / 'raw-result.json')]
            assert json.loads((run / 'raw-result.json').read_text()) == original
            assert options['timeout'] == 3600
            assert options['namespace_user'] == 'current'
            options['progress']({'elapsed_seconds': 1})
            audit.save_report(run / 'correction-audit.json', report)
            return {'exit_status': 0, 'network': 'disabled'}
        with patch.object(worker, 'execute', side_effect=child), patch('replay_mth_core.verify_inputs') as verify:
            worker.review_corrections(lock, target, run, result)
            require(verify.call_count == 1, 'Declared inputs are reverified after the correction audit')
        require(result['acceptance']['status'] == 'PASS_REVIEWED_CORRECTIONS', 'Only a successful bound audit grants correction acceptance')
        require(result['comparison'] == original['comparison'] and result['raw_acceptance'] == original['acceptance'],
                'Raw comparison and original difference verdict remain unchanged')
        require(json.loads((run / 'raw-result.json').read_text()) == original and not (run / 'raw-result.json').stat().st_mode & 0o222,
                'The complete raw result is independently preserved read-only')
        require(result['raw_result_sha256'] == worker.sha(run / 'raw-result.json') and result['correction_audit'] == report,
                'Accepted result binds the preserved raw result and exact audit report')
        require(json.loads((run / 'correction-audit-package.json').read_text())['apparatus_ref'] == lock['apparatus_ref'],
                'Audit package identifies the actual common execution apparatus')
        worker.save(run / 'result.json', result)
        worker.save(run / 'status.json', {'status': 'complete'})
        program = remote.read_program('MTH', run.name, True).replace('/local/content/MEME/MEME5/inv', str(root / 'success'))
        body = program.split('\n', 1)[1].rsplit('\nNCIM_COMMON_READ', 1)[0]
        output = io.StringIO()
        with patch('socket.gethostname', return_value='ncias-d3777-c'), redirect_stdout(output):
            exec(compile(body, '<fixture-collection>', 'exec'), {})
        collected = json.loads(output.getvalue().split('BEGIN_COMMON_REPLAY_RESULT\n', 1)[1].split('\nEND_COMMON_REPLAY_RESULT', 1)[0])['records']
        require(collected['raw-result.json'] == original and collected['correction-audit.json'] == report and
                collected['correction-audit-execution.json']['exit_status'] == 0,
                'Common collection retrieves raw comparison, independent audit and execution evidence together')
        rejected(lambda: worker.review_corrections(lock, target, run, result), 'A completed acceptance cannot be rerun over existing evidence')

        for key, value in [('source', 'NCI'), ('version', 'MTH_2025AB'), ('case_variant', 'as-produced'), ('engine_ref', '2' * 40)]:
            bad = copy.deepcopy(lock);bad['request'][key] = value
            rejected(lambda: worker.correction_profile(bad), 'Correction profile rejects an unreviewed request ' + key)
        for mutation, label in [
            (lambda x: x['case'].pop('correction_audit'), 'Missing correction contract rejected'),
            (lambda x: x['modules_b64'].clear(), 'Missing frozen audit module rejected'),
            (lambda x: x['case']['legacy_case'].update(validate_identity_state=False), 'Retained-identity validation cannot be disabled'),
            (lambda x: x['case']['legacy_case'].update(execute_source_stages=False), 'Corrected source stages cannot be replaced with baseline shell fragments'),
            (lambda x: x.update(runtime_ref='2' * 40), 'Correction profile cannot select a different shared runtime')]:
            bad = copy.deepcopy(lock);mutation(bad)
            rejected(lambda: worker.correction_profile(bad), label)

        for number, scenario in enumerate(('raw-run-identity', 'core-validation', 'identity-validation', 'incomplete-outputs', 'raw-verdict',
                                            'child-failure', 'missing-report', 'wrong-engine', 'wrong-run', 'wrong-apparatus',
                                            'wrong-tool', 'wrong-verdict', 'raw-rewritten', 'production-approval',
                                            'symlink-report', 'changed-raw-result', 'changed-output', 'changed-input')):
            lock, target, run, result, report = fixture(root / str(number))
            original = copy.deepcopy(result)
            if scenario == 'raw-run-identity':result['run_id'] = 'another-run'
            elif scenario == 'core-validation':result['comparison']['validation']['passed'] = False
            elif scenario == 'identity-validation':result['comparison']['validation']['identity_state']['passed'] = False
            elif scenario == 'incomplete-outputs':result['comparison']['files'].pop(next(iter(result['comparison']['files'])))
            elif scenario == 'raw-verdict':result['acceptance']['status'] = 'PASS_EXACT'
            def bad_child(command, **options):
                if scenario == 'child-failure':raise RuntimeError('Injected failed native audit')
                if scenario == 'missing-report':return {'exit_status': 0}
                changes = {'wrong-engine': ('engine_ref', '2' * 40), 'wrong-run': ('run_id', 'another-run'),
                           'wrong-apparatus': ('conversion_apparatus_ref', '2' * 40), 'wrong-tool': ('audit_tool_sha256', '0' * 64),
                           'wrong-verdict': ('status', 'DIFFERENCES_REQUIRE_REVIEW'), 'raw-rewritten': ('raw_comparison_rewritten', True),
                           'production-approval': ('production_eligible', True)}
                if scenario in changes:
                    key, value = changes[scenario];report[key] = value
                if scenario == 'symlink-report':
                    elsewhere = run / 'elsewhere.json';elsewhere.write_text(json.dumps(report))
                    (run / 'correction-audit.json').symlink_to(elsewhere)
                else:audit.save_report(run / 'correction-audit.json', report)
                if scenario == 'changed-raw-result':
                    path = run / 'raw-result.json';path.chmod(0o600);path.write_text('{}')
                if scenario == 'changed-output':next((target / 'src').iterdir()).write_bytes(b'unreviewed change')
                return {'exit_status': 0}
            def verify_inputs(*args):
                if scenario == 'changed-input':raise RuntimeError('Frozen native input changed')
            with patch.object(worker, 'execute', side_effect=bad_child), patch('replay_mth_core.verify_inputs', side_effect=verify_inputs):
                rejected(lambda: worker.review_corrections(lock, target, run, result), 'Failed acceptance remains closed: ' + scenario)
            require(result['acceptance']['status'] != 'PASS_REVIEWED_CORRECTIONS' and 'correction_audit' not in result,
                    'Rejected ' + scenario + ' cannot publish an accepted verdict')
            if scenario == 'child-failure':
                require(json.loads((run / 'raw-result.json').read_text()) == original,
                        'A failed audit retains the complete raw result for investigation')
        lock['request']['comparison_profile'] = 'exact'
        before = copy.deepcopy(result)
        with patch.object(worker, 'execute') as execute:
            worker.review_corrections(lock, target, run, result)
            require(not execute.called and result == before, 'Exact comparison never inherits correction-profile acceptance')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'common MTH acceptance checks passed')
