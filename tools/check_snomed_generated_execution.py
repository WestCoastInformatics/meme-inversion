#!/usr/bin/env python3
"""Exercise real generated-cfg staging with a tiny archive and immutable locks."""
import base64
import copy
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
from unittest.mock import patch

import check_snomed_configuration as preview_checks
import prepare_snomed_candidate as preparation
import run_snomed_core_replay as runner
import snomed_configuration as sct


def resign(lock):
    lock['case_sha256'] = sct.digest(lock['case'])
    lock['lock_sha256'] = sct.digest({k: v for k, v in lock.items() if k != 'lock_sha256'})


def execution_lock():
    lock = preview_checks.fixture_lock()
    lock['request']['case_variant'] = 'generated-configuration'
    lock['configuration']['replay']['case_variant'] = 'generated-configuration'
    lock['case']['case_variant'] = 'generated-configuration'
    lock['case']['configuration_generation'] = {'profile': sct.EXECUTION_PROFILE,
                                               'repository_path': sct.TEMPLATE_PATH,
                                               'sha256': sct.TEMPLATE_SHA256}
    lock['execution_enabled'] = True
    resign(lock)
    return lock


def staging_fixture(root):
    """Real archive/staging; fake only host/capacity/publish platform boundaries."""
    lock = execution_lock()
    config = lock['configuration']
    artifacts = lock['case']['artifacts']
    contract = lock['case']['legacy_case']['contract']
    payloads = {}
    items = [x for x in contract['conversion_inputs'] if x['required']] + contract['archived_metadata_inputs']
    for number, item in enumerate(items):
        data = ('fixture-' + str(number) + '\n').encode()
        if item['path'].endswith('/src/sources.src'):
            data = (preparation.VERSION + '|SNOMEDCT_US_2026_03_01|0\n').encode()
        elif item['path'].endswith('/src/termgroups.src'):
            data = (preparation.VERSION + '/PT|NCI\n').encode()
        payloads[item['path']] = data
        item.update(sha256=sct.sha(data), size=len(data), newline_count=data.count(b'\n'))
    expected = {item['path']: item for item in items}
    for field in ('source_data', 'reference_ncimeta'):
        references = config['inputs'][field] if field == 'source_data' else [config['inputs'][field]]
        for reference in references:
            value = copy.deepcopy(artifacts[reference]['value'])
            for item in value:
                current = expected[item['path']]
                item.update({key: current[key] for key in ('sha256', 'size', 'newline_count')})
            bound = 'sha256:' + sct.digest(value)
            artifacts[bound] = {'role': artifacts[reference]['role'], 'value': value}
            config['inputs'][field] = [bound] if field == 'source_data' else bound
    source_root = root / 'sources'
    source_root.mkdir()
    archive = source_root / (preparation.VERSION + '.tgz')
    with tarfile.open(archive, 'w:gz') as handle:
        for name, data in payloads.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            handle.addfile(info, io.BytesIO(data))
        # Completed source output must never be selected even if archived beside inputs.
        info = tarfile.TarInfo(preparation.VERSION + '/src/classes_atoms.src')
        info.size = 9
        handle.addfile(info, io.BytesIO(b'official\n'))
    contract['reference'].update(archive_path=str(archive), archive_sha256=sct.sha(archive.read_bytes()))
    resign(lock)
    recipe = sct.execution_recipe_from_lock(lock)
    generation_inputs = {'configuration': config, 'artifacts': artifacts}
    package = {'contract': contract, 'code_files': lock['code_files'],
               'generated_configuration': recipe, 'configuration_generation_inputs': generation_inputs}
    return lock, package, source_root / preparation.VERSION


def staged(package, root, target):
    enough = shutil._ntuple_diskusage(500 * 1024**3, 1, 499 * 1024**3)
    with patch.multiple(preparation, ROOT=root, TARGET=target), patch.object(preparation, 'guard'), \
            patch.object(preparation.shutil, 'disk_usage', return_value=enough), \
            patch.object(preparation, 'publish', side_effect=lambda a, b: a.rename(b)):
        return preparation.prepare(package['contract'], package['code_files'], progress=lambda *a, **k: None,
                                   generated_configuration=package.get('generated_configuration'),
                                   configuration_generation_inputs=package.get('configuration_generation_inputs'))


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def reject(action, label):
        try:
            action()
        except (ValueError, KeyError, RuntimeError):
            passed.append(label)
        else:
            raise AssertionError(label)

    original = preview_checks.fixture_lock()
    original_before = json.dumps(original, sort_keys=True)
    reject(lambda: sct.execution_recipe_from_lock(original), 'Original historical case cannot acquire generated execution implicitly')
    lock = execution_lock()
    unsigned = copy.deepcopy(lock)
    unsigned.pop('lock_sha256')
    recipe = sct.execution_recipe_from_lock(unsigned, verify_checksum=False)
    good(recipe['profile'] == sct.EXECUTION_PROFILE and recipe['production_eligible'] is False,
         'Resolver can build only the reviewed historical execution recipe before its final checksum')
    lock['configuration_generation'] = recipe
    resign(lock)
    good(sct.execution_recipe_from_lock(json.loads(json.dumps(lock))) == recipe,
         'Completed generated lock round-trips and recomputes the entire frozen recipe')
    preview = sct.preview_from_lock(lock)
    good(preview['profile'] == sct.PROFILE and preview['execution_enabled'] is False,
         'A generated execution lock can still produce a distinctly preview-only recipe')
    good(sct.preview_from_lock(original)['profile'] == sct.PROFILE and original_before == json.dumps(original, sort_keys=True),
         'Original preview behavior and input lock remain unchanged')
    for label, mutation in [
        ('changed recipe payload', lambda x: x['configuration_generation']['files'][0].update(data_b64=base64.b64encode(b'changed').decode())),
        ('preview/execution profile substitution', lambda x: x['configuration_generation'].update(profile=sct.PROFILE)),
        ('changed case generation profile', lambda x: x['case']['configuration_generation'].update(profile=sct.PROFILE)),
        ('disabled execution case', lambda x: x['case'].update(execution_enabled=False)),
        ('wrong execution variant', lambda x: x['request'].update(case_variant='as-produced')),
        ('extra template override', lambda x: x['case']['configuration_generation'].update(shell_command='ignored')),
    ]:
        bad = copy.deepcopy(lock)
        mutation(bad)
        resign(bad)
        reject(lambda: sct.execution_recipe_from_lock(bad), 'Reject ' + label)
    checksum = copy.deepcopy(lock)
    checksum['lock_sha256'] = '0' * 64
    reject(lambda: sct.execution_recipe_from_lock(checksum), 'Completed lock requires its exact checksum')
    with tempfile.TemporaryDirectory(prefix='snomed-generated-staging-') as directory:
        root = Path(directory)
        _, package, target = staging_fixture(root)
        result = staged(package, root, target)
        cfg = target / 'etc/sct.cfg'
        sct.verify_generated(package['generated_configuration'], target)
        good(cfg.read_bytes() == base64.b64decode(package['generated_configuration']['files'][0]['data_b64']) and
             cfg.stat().st_mode & 0o777 == 0o444,
             'Real eighteen-input archive preparation writes the generated cfg read-only')
        good(len(result['inputs']) == 18 and not (target / 'src/classes_atoms.src').exists(),
             'Real staging selects eighteen declared inputs and never seeds archived core output')
        good(len(result['code']) == 4 and result['configuration_seeded_from_code_files'] is False and
             result['configuration_templates'][0]['relative_path'] == 'etc/sct.cfg' and
             result['configuration_templates'][0]['mode'] == '0o750',
             'Captured cfg remains a separately recorded template rather than a staged source-code seed')
        good(result['configuration_generation']['files'][0]['sha256'] == sct.TEMPLATE_SHA256 and
             'data_b64' not in result['configuration_generation']['files'][0] and
             'data_b64' not in result['configuration_generation']['template'],
             'Preparation receipt retains generated and template identities without payload duplication')
        with patch.multiple(runner, ROOT=root, TARGET=target, RUN_ID=package['contract']['run_id']):
            runner.verify_case(package)
            passed.append('Existing runner verifies real staged archive/input/code bytes and generated cfg')
            cfg.chmod(0o644)
            reject(lambda: runner.verify_case(package), 'Runner rejects writable generated cfg before conversion')
            cfg.write_bytes(b'changed settings\n')
            cfg.chmod(0o444)
            reject(lambda: runner.verify_generated_configuration(package), 'Runner rejects changed generated cfg after conversion')
        cfg.chmod(0o644)
        cfg.write_bytes(base64.b64decode(package['generated_configuration']['files'][0]['data_b64']))
        cfg.chmod(0o444)
        actual = cfg.with_suffix('.real')
        cfg.rename(actual)
        cfg.symlink_to(actual.name)
        reject(lambda: sct.verify_generated(package['generated_configuration'], target), 'Generated cfg cannot be substituted with a symlink')
        cfg.unlink()
        actual.rename(cfg)
        etc = target / 'etc'
        etc.rename(target / 'etc-saved')
        etc.symlink_to('etc-saved', target_is_directory=True)
        reject(lambda: sct.verify_generated(package['generated_configuration'], target), 'Generated cfg parent cannot be substituted with a symlink')
    for label, mutation in [
        ('tampered generated bytes', lambda p: p['generated_configuration']['files'][0].update(data_b64=base64.b64encode(b'wrong').decode(), sha256=sct.sha(b'wrong'))),
        ('missing generation context', lambda p: p.pop('configuration_generation_inputs')),
        ('context without recipe', lambda p: p.pop('generated_configuration')),
        ('changed common input context', lambda p: p['configuration_generation_inputs']['configuration']['source_atom_ids'].update(end=1)),
        ('changed captured cfg template payload', lambda p: p['code_files'][-1].update(data_b64=base64.b64encode(b'wrong').decode())),
    ]:
        with tempfile.TemporaryDirectory(prefix='snomed-generated-reject-') as directory:
            root = Path(directory)
            _, package, target = staging_fixture(root)
            mutation(package)
            reject(lambda: staged(package, root, target), 'Staging rejects ' + label)
            good(not target.exists() and not list((root / 'sources').glob('.*.prepare-*')),
                 'Rejected ' + label + ' leaves no published candidate or scratch staging')
    with tempfile.TemporaryDirectory(prefix='snomed-original-staging-') as directory:
        root = Path(directory)
        _, package, target = staging_fixture(root)
        package.pop('generated_configuration')
        package.pop('configuration_generation_inputs')
        result = staged(package, root, target)
        good(len(result['code']) == 5 and 'configuration_generation' not in result and
             (target / 'etc/sct.cfg').stat().st_mode & 0o777 == 0o750,
             'Original preparation still stages all five captured files with their original modes')
    return passed


if __name__ == '__main__':
    results = check()
    for label in results:
        print('PASS', label)
    print(len(results), 'SNOMED generated-execution checks passed')
