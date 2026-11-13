#!/usr/bin/env python3
"""Complete tiny MTH shadow inversions without any official output artifact.

These synthetic dev fixtures prove source conversion/validation only. They
cannot establish official equivalence, operational QA or production eligibility.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import check_execute_release_mth as native_fixture
import check_release_mth
import execute_release_mth as execution
import release_mth


def fixture(directory, skipped):
    """Preserve the complete native fixture, then remove the official oracle.

    The reused fixture assembles tiny preserved publisher/state/identity data
    and canonical Git consumer bytes. Its initial historical plan is discarded;
    the plan actually executed below is rebuilt from an oracle-free manifest.
    """
    manifest, historical_plan, target, run, code = native_fixture.fixture(
        directory, skipped=skipped, preserved_decisions=True)
    manifest['purpose'] = 'shadow'
    manifest['configuration'].pop('replay', None)
    for name in list(manifest['artifacts']):
        if manifest['artifacts'][name]['artifact_type'] == 'reference-inversion':
            del manifest['artifacts'][name]
    plan = execution.build_plan(manifest['configuration'], manifest['artifacts'], code)
    (run / 'native-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    return manifest, plan, target, run, code, historical_plan


def run_stages(plan, target, run):
    """Run each real fixed native command, retaining its individual exit status."""
    metrics = []
    env = dict(os.environ, LANG='C', LC_ALL='C', LC_COLLATE='C',
               _POSIX2_VERSION='1', PATH_TO_PERL='/usr/bin/perl')
    for stage in plan['stages']:
        argv = [word.replace('{python}', sys.executable).replace('{target}', str(target)).replace('{run}', str(run))
                for word in stage['argv']]
        completed = subprocess.run(argv, cwd=target / stage['cwd'], env=env,
                                   capture_output=True, timeout=30)
        (run / (stage['name'] + '.stdout')).write_bytes(completed.stdout)
        (run / (stage['name'] + '.stderr')).write_bytes(completed.stderr)
        metrics.append({'stage': stage['name'], 'exit_status': completed.returncode})
        if completed.returncode:
            raise AssertionError((stage['name'], completed.stderr.decode(errors='replace')[-2000:]))
    return metrics


def identities(target, names):
    return {name: execution.identity(target / name) for name in names}


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def rejects(action, label):
        try:
            action()
        except (ValueError, RuntimeError):
            passed.append(label)
        else:
            raise AssertionError(label)

    for skipped in (False, True):
        with tempfile.TemporaryDirectory(prefix='mth-oracle-free-shadow-') as temporary:
            manifest, plan, target, run, code, historical = fixture(Path(temporary).resolve(), skipped)
            config, artifacts = manifest['configuration'], manifest['artifacts']
            version = config['version']
            suffix = ': ' + version
            before = copy.deepcopy(manifest)
            good(manifest['purpose'] == 'shadow' and 'replay' not in config and
                 not any(value['artifact_type'] == 'reference-inversion' for value in artifacts.values()),
                 'Shadow request contains neither replay configuration nor official output artifact' + suffix)
            good(plan['validation']['reference_version'] is None and plan['validation']['reference_stage'] is None and
                 plan['validation']['reference_files'] == [],
                 'Execution plan contains no hidden official expected-output bindings' + suffix)
            good(release_mth.analyze(config, artifacts)['issues'] == [] and
                 execution.build_plan(config, artifacts, code) == plan,
                 'Prepared source preflight and frozen Git template planning work without an oracle' + suffix)
            good(plan['generated_files'] == historical['generated_files'] and
                 plan['input_files'] == historical['input_files'] and plan['stages'] == historical['stages'] and
                 plan['symlinks'] == historical['symlinks'] and plan['output_files'] == historical['output_files'],
                 'Removing comparison affects no native settings, source inputs, commands or output inventory' + suffix)
            good(config['source_atom_ids']['bound_kind'] == 'dev-reservation' and
                 artifacts['mth-plan']['data']['review_status'] == 'reviewed' and
                 all(row['review_status'] == 'reviewed' for row in artifacts['mth-plan']['data']['dispositions']),
                 'Existing explicit dev allocation and reviewed dispositions remain required' + suffix)
            checked = execution.validate_inputs(plan, target)
            good(checked['passed'] and checked['issues'] == [],
                 'Independent physical RRF/state/policy/prior validation passes before any native stage' + suffix)
            good(len(plan['stages']) == 13 and tuple(row['name'] for row in plan['stages']) == execution.STAGE_NAMES and
                 len(plan['output_files']) == 23 and not any((target / name).exists() for name in plan['output_files']),
                 'All thirteen native stages and twenty-three outputs are declared before fresh conversion' + suffix)
            old = config['replacement_baseline']['version']
            prev = artifacts['mth-plan']['data']['publisher_previous']['version']
            good((old != prev) is skipped and (target / 'old').readlink().as_posix() == 'orig/identity/' + old and
                 (target / 'old/src/cui_said_map').read_bytes() == b'C3|777\nCOLD|778\n',
                 'Inserted identity is explicitly snapshotted independently of publisher previous' + suffix)
            history = plan['validation']['history_sources']
            chain = [old, prev, version] if skipped else [old, version]
            good(list(history['moved_aui_releases']) == [value[4:] for value in chain] and
                 list(history['cui_merge_releases']) == [value[4:] for value in chain[:-1]] and
                 list(history['bequeathal_releases']) == [value[4:] for value in chain[:-1]],
                 'Moved, merge and bequeathal windows remain explicit across the selected transition' + suffix)
            inputs_before = {str(execution.input_path(item, target)): execution.identity(execution.input_path(item, target))
                             for item in plan['input_files']}
            generated_before = identities(target, [row['relative_path'] for row in plan['generated_files']])
            metrics = run_stages(plan, target, run)
            good(len(metrics) == 13 and all(row['exit_status'] == 0 for row in metrics) and
                 [row['stage'] for row in metrics] == list(execution.STAGE_NAMES),
                 'All thirteen real Perl/tcsh/Python native stages complete without official source outputs' + suffix)
            good(all((target / name).is_file() and not (target / name).is_symlink() for name in plan['output_files']),
                 'All twenty-three expected native outputs are freshly present as regular files' + suffix)
            output = execution.validate_outputs(plan, target)
            good(output['passed'] and output['issues'] == [] and
                 output['facts']['structure']['passed'] and output['facts']['retained_identity']['passed'] and
                 output['facts']['complete_identity_maps'] and not output['facts']['historical_correction_waiver_applied'],
                 'Independent core/range/reference and full retained-identity validation pass without equality claims' + suffix)
            good('acceptance' not in output and 'comparison' not in output and
                 not any(key in output for key in ('accepted', 'exact_match', 'production_eligible')),
                 'Source physical validation alone returns no comparison acceptance or production claim' + suffix)
            good(execution.validate_inputs(plan, target)['passed'] and
                 inputs_before == {str(execution.input_path(item, target)): execution.identity(execution.input_path(item, target))
                                   for item in plan['input_files']} and
                 generated_before == identities(target, [row['relative_path'] for row in plan['generated_files']]) and
                 all((target / row['relative_path']).stat().st_mode & 0o222 == 0 for row in plan['generated_files']),
                 'Native processing preserves all prepared/state/identity inputs and seven read-only generated settings' + suffix)
            # These expected bindings are literals, independent of the renderer
            # or validation implementation; no generated output becomes oracle.
            expected_maps = {
                'aui_said_map': b'A1|C1|1003\nA2|C2|1004\n',
                'moved_aui_said_map': b'A3|C3|1005\nA4|C4|1006\nA5|C1|1007\n',
                'cui_said_map': b'C1|1003\nC2|1004\nC4|1006\n',
                'rel_cui_said_map': b'C1|1003\nC2|1004\nC4|1006\n',
                'cui_splitonly_said_map': b'C4|1006\n', 'cui.splitonly.new': b'C4\n'}
            good(all((target / 'src' / name).read_bytes() == raw for name, raw in expected_maps.items()),
                 'Independent current/moved/split identity goldens survive the oracle-free route' + suffix)
            good((target / 'src/cui_merges').read_bytes() == b'COLD|C1\n' and
                 (target / 'src/auis_nonupdatedSAB_moved').read_bytes() == b'A3|C3\nA4|C4\nA5|C1\n',
                 'Last-inserted merge and nonupdated moved-AUI evidence retain their distinct roles' + suffix)
            bequeathals = [(row.split('|')[2], row.split('|')[5], row.split('|')[12], row.split('|')[14])
                           for row in (target / 'src/bequeathal.relationships.src').read_text().splitlines()]
            expected_bequeathals = [('C2', 'COLD2', 'CUI_CURRENT', 'CUI_PREVIOUS')] * 2
            if skipped:
                expected_bequeathals.append(('C1', 'COLD3', 'CUI_CURRENT', 'CUI_PREVIOUS'))
            good(bequeathals == expected_bequeathals,
                 'Duplicate historical bequeathals and intermediate publisher window are preserved' + suffix)
            rejects(lambda: execution.compare_outputs(plan, target, Path(temporary) / 'absent-official-outputs'),
                    'No official comparison or PASS_EXACT can be fabricated from a clean shadow validation' + suffix)
            good(manifest == before and not any(value['artifact_type'] == 'reference-inversion' for value in artifacts.values()),
                 'Running shadow stages does not add an oracle or promote source-plan approval' + suffix)

            def output_damage(role, transform, expected_code):
                path = target / role
                original = path.read_bytes()
                path.write_bytes(transform(original))
                failed = execution.validate_outputs(plan, target)
                good(not failed['passed'] and any(row['code'] == expected_code for row in failed['issues']),
                     'Shadow physical validation rejects ' + role + ' damage via ' + expected_code + suffix)
                path.write_bytes(original)

            output_damage('src/aui_said_map', lambda raw: raw.splitlines(keepends=True)[0], 'MTH_IDENTITY_COVERAGE')
            output_damage('src/relationships.src', lambda raw: raw + b'bad|wire|\n', 'MTH_CORE_STRUCTURE')
            path = target / 'src/contexts.src';saved = path.read_bytes();path.unlink()
            failed = execution.validate_outputs(plan, target)
            good(not failed['passed'] and any(row['code'] == 'MTH_OUTPUT_MISSING' for row in failed['issues']),
                 'Missing output fails shadow validation even without an official baseline' + suffix)
            path.write_bytes(saved)
            good(execution.validate_outputs(plan, target)['passed'],
                 'Restored original output bytes recover independent validation' + suffix)
            prior_input = next(item for item in plan['input_files'] if item['role'] == 'cui_said_map')
            prior_path = execution.input_path(prior_input, target)
            original_prior = prior_path.read_bytes()
            prior_path.chmod(0o644);prior_path.write_bytes(b'CREPLACED|777\nCOLD|778\n');prior_path.chmod(0o444)
            damaged_inputs = execution.validate_inputs(plan, target)
            damaged_outputs = execution.validate_outputs(plan, target)
            good(not damaged_inputs['passed'] and any(row['code'] == 'MTH_INPUT_CHANGED' for row in damaged_inputs['issues']) and
                 not damaged_outputs['passed'] and any(row['code'] == 'MTH_IDENTITY_COVERAGE' for row in damaged_outputs['issues']),
                 'Changed retained prior identity fails both frozen input bytes and independent complete-map prediction' + suffix)
            prior_path.chmod(0o644);prior_path.write_bytes(original_prior);prior_path.chmod(0o444)
            good(execution.validate_inputs(plan, target)['passed'] and execution.validate_outputs(plan, target)['passed'],
                 'Restored prior snapshot recovers original physical validation' + suffix)

            # Input and decision gates remain in force without a reference.
            for key, mutation in [
                    ('prior identity release', lambda value: value['artifacts']['mth-identity'].update(version=prev if skipped else 'MTH_2025AB')),
                    ('required history', lambda value: value['artifacts']['mth-prepared']['data']['history_coverage'].update(cui_merge_releases=[])),
                    ('reviewed dispositions', lambda value: value['artifacts']['mth-plan']['data'].update(review_status='proposed', approved=True)),
                    ('saved installed binding', lambda value: value['artifacts']['mth-plan']['data']['dispositions'][1].update(prior_version='TEST_2025')),
                    ('publisher previous selection', lambda value: value['artifacts']['mth-plan']['data']['publisher_previous'].update(
                        version=old if skipped else 'MTH_2025AB')),
                    ('final allocation', lambda value: value['configuration'].update(source_atom_ids=None))]:
                invalid = copy.deepcopy(manifest)
                mutation(invalid)
                check_release_mth.bind_producer_inputs(invalid)
                rejects(lambda invalid=invalid: execution.build_plan(invalid['configuration'], invalid['artifacts'], code),
                        'No-oracle mode does not relax ' + key + suffix)
    return passed


if __name__ == '__main__':
    passed = check()
    print(json.dumps({'passed': len(passed), 'checks': passed}, indent=2))
