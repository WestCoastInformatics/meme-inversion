#!/usr/bin/env python3
"""Offline checks of preservation failure handling and replay acceptance gates."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import advance_nci_replay as replay


def check():
    passed = []

    def require(condition, name):
        if not condition:
            raise AssertionError(name)
        passed.append(name)

    def fixture(root):
        target = root / 'sources' / replay.VERSION
        for name in ['bin', 'src', 'etc/qa', 'tmp']:
            (target / name).mkdir(parents=True, exist_ok=True)
        names = ['classes_atoms.src', 'attributes.src', 'relationships.src', 'mergefacts.src', 'contexts.src']
        for name in names:
            (target / 'src' / name).write_text('previous ' + name + '\n')
        for name, data in [('bin/invert_NCI.pl', 'old code\n'), ('etc/nci.cfg', 'config\n'),
                           ('etc/replay-case.json', '{}\n'), ('src/sources.src', 'source\n'),
                           ('src/termgroups.src', 'termgroup\n')]:
            (target / name).write_text(data)
        archive = root / 'sources' / (replay.VERSION + '.tgz')
        archive.write_bytes(b'fixture archive identity')
        core = {'engine_ref': 'a' * 40, 'started_at': 'start', 'completed_at': 'end', 'exit_status': 0,
                'comparison': [{'path': str(target / 'src' / name), 'sha256': replay.digest(target / 'src' / name)} for name in names]}
        (target / 'etc/replay-core.json').write_text(json.dumps(core))
        new_code = b'new code\n'
        package = {'contract': {'version': replay.VERSION, 'run_id': 'test-next', 'engine_ref': 'b' * 40,
                               'reference': {'archive_path': str(archive), 'archive_sha256': replay.digest(archive)},
                               'native_inputs': [], 'archived_metadata_inputs': [], 'preparation_reference_files': [],
                               'auxiliary_outputs_to_regenerate': []},
                   'previous_core': core, 'runtime_files': [], 'preserve_as': 'test-previous',
                   'previous_code': [{'relative_path': 'bin/invert_NCI.pl', 'sha256': replay.digest(target / 'bin/invert_NCI.pl')}],
                   'engine_files': [{'relative_path': 'bin/invert_NCI.pl', 'sha256': hashlib.sha256(new_code).hexdigest()}],
                   'changed_script_b64': base64.b64encode(new_code).decode()}
        modules = {'advance_nci_replay.py': {'data_b64': base64.b64encode(b'# fixture\n').decode(),
                                           'sha256': hashlib.sha256(b'# fixture\n').hexdigest()}}
        return target, package, modules

    with tempfile.TemporaryDirectory(prefix='nci-preservation-fixture-') as directory:
        root = Path(directory)
        for kind in ['copy-failure', 'success', 'runtime-success', 'runtime-copy-failure']:
            fixture_root = root / kind
            target, package, modules = fixture(fixture_root)
            if kind.startswith('runtime-'):
                library = fixture_root / 'INV/lib/Hierarchy.pm'
                library.parent.mkdir(parents=True)
                library.write_bytes(b'old hierarchy\n')
                package['engine_files'] = copy.deepcopy(package['previous_code'])
                package['previous_runtime_files'] = [{'path': str(library), 'sha256': replay.digest(library)}]
                package['runtime_files'] = [{'path': str(library), 'sha256': hashlib.sha256(b'new hierarchy\n').hexdigest()}]
                package['changed_runtime_b64'] = base64.b64encode(b'new hierarchy\n').decode()
            runs = target / 'etc/qa/replay-runs'
            original = {str(path.relative_to(target)): path.read_bytes() for path in target.rglob('*') if path.is_file()}
            globals_ = dict(ROOT=fixture_root, TARGET=target, RUNS=runs, ACTIVE=target / 'etc/replay-active-run.json', LOCK=runs / 'active.lock.json')
            with patch.multiple(replay, **globals_), patch.object(replay, 'guard'), patch.object(replay, 'core_is_running', return_value=False), patch.object(replay.shutil, 'disk_usage', return_value=SimpleNamespace(free=20 * 1024 ** 3)):
                if kind in {'copy-failure', 'runtime-copy-failure'}:
                    original_copy = replay.shutil.copy2
                    def failing_copy(source, destination):
                        if kind == 'copy-failure' or Path(source).name == 'Hierarchy.pm':
                            raise OSError('simulated copy failure')
                        return original_copy(source, destination)
                    with patch.object(replay.shutil, 'copy2', side_effect=failing_copy):
                        try:
                            replay.start(package, modules)
                        except OSError:
                            pass
                        else:
                            raise AssertionError('Copy failure was accepted')
                    require(all((target / name).read_bytes() == data for name, data in original.items()), 'copy failure preserves every original artifact')
                    require(not replay.LOCK.exists(), 'failed setup releases its lock')
                    if kind == 'runtime-copy-failure':
                        require(library.read_bytes() == b'old hierarchy\n', 'late preservation failure leaves installed runtime unchanged')
                else:
                    def publish(source, destination):
                        if destination.exists():
                            raise FileExistsError(destination)
                        source.rename(destination)
                    with patch.object(replay, 'publish_directory', side_effect=publish), patch.object(replay.subprocess, 'Popen', return_value=SimpleNamespace(pid=12345)):
                        launched = replay.start(package, modules)
                    preserved = runs / 'test-previous'
                    require(all((preserved / name).read_bytes() == data for name, data in original.items()), 'complete baseline copied before current output reset')
                    require({p.name for p in (target / 'src').iterdir()} == {'sources.src', 'termgroups.src'}, 'next candidate starts without generated output')
                    if kind == 'runtime-success':
                        require((preserved / 'engine/INV/lib/Hierarchy.pm').read_bytes() == b'old hierarchy\n', 'shared-runtime original preserved before replacement')
                        require(library.read_bytes() == b'new hierarchy\n' and (target / 'bin/invert_NCI.pl').read_bytes() == b'old code\n', 'shared-runtime update leaves source code unchanged')
                        require(json.loads((fixture_root / 'candidate-runtime.json').read_text())['engine_ref'] == package['contract']['engine_ref'], 'active candidate runtime revision recorded')
                    else:
                        require((target / 'bin/invert_NCI.pl').read_bytes() == b'new code\n' and launched['worker_pid'] == 12345, 'only pinned candidate code installed before launch')
                    require(all(not (p.stat().st_mode & 0o222) for p in preserved.rglob('*')), 'preserved baseline is read-only')
            # Permit fixture cleanup on platforms that enforce read-only directories.
            for path in target.rglob('*'):
                if path.is_dir():
                    path.chmod(0o700)
                elif path.is_file():
                    path.chmod(0o600)
    views = {'rows': 2, 'unique_ids': 2, 'duplicate_ids': 0, 'invalid_ids': 0, 'minimum_id': 1, 'maximum_id': 2,
             'non_context_full_record_sha256': 'same'}
    comparison = {'files': {'classes_atoms.src': {'exact_match': True}, 'relationships.src': {'exact_match': True},
                            'mergefacts.src': {'exact_match': True}, 'contexts.src': {'row_multiset': {'equal_preserving_multiplicity': True}},
                            'attributes.src': {'content_multiset_excluding_generated_attribute_id': {'equal_preserving_multiplicity': True},
                                               'reference_id_view': copy.deepcopy(views), 'candidate_id_view': copy.deepcopy(views)}},
                  'structure': {side: {'checks_passed': True, 'termgroup_validation': {'passed': True},
                                       'files': {'attributes.src': {'identifier_types': {'SRC_ATOM_ID': 2}}}} for side in ['reference', 'candidate']},
                  'other_reference_src': [{'file': name, 'role': 'declared-metadata-input', 'exact_match': True} for name in ['sources.src', 'termgroups.src']]}
    core = {'exit_status': 0, 'metadata_unchanged': True}
    require(replay.verdict(core, comparison)['status'] == 'PASS_EQUIVALENT', 'declared core profile accepts valid record equivalence')
    for defect in ['termgroup', 'duplicate-id', 'attribute-reference', 'non-context-change', 'missing-metadata']:
        bad = copy.deepcopy(comparison)
        if defect == 'termgroup':
            bad['structure']['candidate']['termgroup_validation']['passed'] = False
        elif defect == 'duplicate-id':
            bad['files']['attributes.src']['candidate_id_view']['duplicate_ids'] = 1
        elif defect == 'attribute-reference':
            bad['structure']['candidate']['files']['attributes.src']['identifier_types'] = {'SRC_ATTRIBUTE_ID': 1}
        elif defect == 'non-context-change':
            bad['files']['attributes.src']['candidate_id_view']['non_context_full_record_sha256'] = 'different'
        else:
            bad['other_reference_src'] = []
        require(replay.verdict(core, bad)['status'] == 'FAIL', defect + ' cannot be hidden by generated-ID comparison')
    return passed


if __name__ == '__main__':
    checks = check()
    for name in checks:
        print('PASS ' + name)
    print(str(len(checks)) + ' preservation/profile checks passed')
