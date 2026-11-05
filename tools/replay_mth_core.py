#!/usr/bin/env python3
"""Replay the captured MTH final-range conversion from frozen preparation inputs."""
import base64
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import traceback

from acquire_mth_subset import identity, publish
import compare_mth_core
from replay_process import execute, available_memory

ROOT = Path('/local/content/MEME/MEME5/inv')
VERSION = 'MTH_2026AA'
TARGET = ROOT / 'sources' / VERSION
RUN_ID = 'baseline-core-20261105'
RUN = TARGET / 'qa/replay-runs' / RUN_ID
ACTIVE = TARGET / 'replay-active-run.json'
BASELINE = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'
METADATA = {'src/sources.src', 'src/termgroups.src', 'src/vsab.updates', 'src/sabs_updated_umls',
            'src/rsabs-updated.umls', 'src/vcodes_updated', 'ncimid.sources', 'ncimid.termgroups'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require(path, sha):
    if path.is_symlink() or not path.is_file() or identity(path)['sha256'] != sha:
        raise RuntimeError('Pinned artifact differs: ' + str(path))


def guard():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('MTH characterization requires tomcata on dev')
    for path in [ROOT, ROOT / 'sources', TARGET]:
        if path.is_symlink():
            raise RuntimeError('Unexpected source-root symlink')
    if os.environ.get('INV_HOME') != str(ROOT / 'INV') or os.environ.get('LC_COLLATE') != 'C':
        raise RuntimeError('The mirrored inversion environment is required')


def idle():
    names = {'autoinv.pl', 'SRCbuilder.pl', 'mrcxt2raw3.pl', 'invert_NCI.pl', 'invert_rf2.pl', 'invert2.s'}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts = (entry / 'cmdline').read_bytes().split(b'\0')
            if names & {Path(os.fsdecode(x)).name for x in parts if x} and (entry / 'cwd').resolve().is_relative_to(ROOT / 'sources'):
                raise RuntimeError('Another inversion is using the dev source/runtime paths')
        except (FileNotFoundError, PermissionError):
            pass


def verify_inputs(package, target=None):
    target = TARGET if target is None else target
    if package['engine_ref'] != BASELINE or len(package['runtime_files']) != 169:
        raise RuntimeError('The complete unchanged shared production runtime is required')
    for item in package['runtime_files']:
        require(ROOT / item['relative_path'], item['sha256'])
    for item in package['prepared_subset']['files']:
        require(Path('/local/content/MEME/MEME5/mr/umls/2026AA') / item['relative_path'], item['identity']['sha256'])
    for item in package['metadata_inputs']:
        require(target / item['relative_path'], item['sha256'])
    for item in package['code_files']:
        if item['kind'] == 'file':
            require(target / item['relative_path'], item['sha256'])
        elif not (target / item['relative_path']).is_symlink() or os.readlink(target / item['relative_path']) != item['target']:
            raise RuntimeError('Source topology changed')
    require(ROOT / 'sources/MTH_2025AB/src/cui_said_map', package['prior_map']['sha256'])
    for path, sha in [(package['archive_path'], package['archive_sha256']), (package['prior_archive_path'], package['prior_archive_sha256'])]:
        require(Path(path), sha)


def restore_prior_map(package):
    destination = ROOT / 'sources/MTH_2025AB'
    item = package['prior_map']
    if destination.exists():
        if not (destination / 'replay-identity-reference.json').is_file():
            raise RuntimeError('Existing prior source requires a verified identity receipt')
        require(destination / 'src/cui_said_map', item['sha256'])
        return
    require(Path(package['prior_archive_path']), package['prior_archive_sha256'])
    temporary = Path(tempfile.mkdtemp(prefix='.MTH_2025AB.identity-', dir=str(ROOT / 'sources')))
    try:
        (temporary / 'src').mkdir()
        found = False
        with tarfile.open(package['prior_archive_path'], 'r|gz') as tar:
            for member in tar:
                if member.name != item['path']:
                    continue
                if not member.isfile():
                    raise RuntimeError('Prior CUI map is not regular')
                output = temporary / 'src/cui_said_map'
                with output.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 4194304)
                require(output, item['sha256'])
                if identity(output)['newline_count'] <= 0:
                    raise RuntimeError('An empty prior identity baseline is prohibited')
                output.chmod(0o444)
                found = True
                break
        if not found:
            raise RuntimeError('Prior CUI map missing from frozen archive')
        save(temporary / 'replay-identity-reference.json', {'role': 'prior identity input only; no executable code copied',
             'source': 'MTH', 'version': 'MTH_2025AB', 'archive_sha256': package['prior_archive_sha256'], 'file': item})
        publish(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def tree_manifest(root):
    result = []
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            item = {'path': str(path.relative_to(root)), 'mode': oct(path.lstat().st_mode & 0o777)}
            if path.is_symlink():
                item.update(kind='symlink', target=os.readlink(path))
            elif path.is_dir():
                item['kind'] = 'directory'
            else:
                item.update(kind='file', **identity(path))
            result.append(item)
    return sorted(result, key=lambda x: x['path'])


def prepare(package, progress=print):
    guard()
    idle()
    if package['engine_ref'] != BASELINE or {x['relative_path'] for x in package['metadata_inputs']} != METADATA:
        raise RuntimeError('The reviewed production engine and eight preparation metadata inputs are required')
    if shutil.disk_usage(ROOT).free < 45 * 1024 ** 3 or available_memory() < 24 * 1024 ** 3:
        raise RuntimeError('Insufficient replay capacity reserve')
    require(Path(package['archive_path']), package['archive_sha256'])
    preserved = ROOT / 'sources/MTH_2026AA.before-replay-20261105'
    if preserved.exists() or (TARGET / 'replay-preparation.json').exists():
        raise RuntimeError('A preserved/current replay already exists; nothing overwritten')
    restore_prior_map(package)
    staging = Path(tempfile.mkdtemp(prefix='.MTH_2026AA.prepare-', dir=str(ROOT / 'sources')))
    moved = False
    try:
        for directory in ['src', 'qa', 'insert']:
            (staging / directory).mkdir()
        for item in package['code_files']:
            path = staging / item['relative_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            if item['kind'] == 'symlink':
                path.symlink_to(item['target'])
            else:
                raw = base64.b64decode(item['data_b64'], validate=True)
                if hashlib.sha256(raw).hexdigest() != item['sha256']:
                    raise RuntimeError('Git code bundle differs')
                with path.open('xb') as handle:
                    handle.write(raw)
                path.chmod(int(item['mode'], 8))
        allowed = {VERSION + '/' + x['relative_path']: x for x in package['metadata_inputs']}
        found = set()
        with tarfile.open(package['archive_path'], 'r|gz') as tar:
            for member in tar:
                if member.name not in allowed:
                    continue
                item = allowed[member.name]
                if not member.isfile() or member.name in found:
                    raise RuntimeError('Metadata member is not unique and regular')
                path = staging / item['relative_path']
                with path.open('xb') as out:
                    shutil.copyfileobj(tar.extractfile(member), out, 4194304)
                require(path, item['sha256'])
                path.chmod(0o444)
                found.add(member.name)
        if found != set(allowed) or any((staging / 'src' / name).exists() for name in compare_mth_core.WIDTHS):
            raise RuntimeError('Incomplete inputs or seeded generated output')
        mth_source = [row for row in (staging / 'src/sources.src').read_text().splitlines() if row.startswith('MTH_2026AA|')]
        if len(mth_source) != 1 or mth_source[0].split('|')[1] != 'MTH_2025AB':
            raise RuntimeError('Historical replacement baseline mismatch')
        progress('PHASE: verifying the existing dev tree before reversible preservation', flush=True)
        old = tree_manifest(TARGET) if TARGET.exists() else []
        idle()
        if TARGET.exists():
            publish(TARGET, preserved)
            moved = True
            if tree_manifest(preserved) != old:
                raise RuntimeError('Existing dev tree changed during preservation')
        publish(staging, TARGET)
        result = {'source': 'MTH', 'version': VERSION, 'engine_ref': BASELINE, 'prepared_at': now(),
                  'generated_outputs_seeded': False, 'replacement_baseline': 'MTH_2025AB',
                  'preexisting_dev_preserved': str(preserved) if moved else None, 'preexisting_dev_manifest': old,
                  'prior_identity_input': package['prior_map'], 'prepared_subset_reference': package['prepared_subset'],
                  'metadata_inputs': package['metadata_inputs'], 'code_files': [{k: v for k, v in x.items() if k != 'data_b64'} for x in package['code_files']]}
        save(TARGET / 'replay-preparation.json', result)
        if moved:
            for item in old:
                path = preserved / item['path']
                if item['kind'] == 'file':
                    path.chmod(0o444)
            for base, dirs, files in os.walk(preserved, topdown=False, followlinks=False):
                Path(base).chmod(0o555)
        verify_inputs(package)
        return result
    except BaseException:
        if moved and not TARGET.exists():
            publish(preserved, TARGET)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


# These bounded stages transcribe the active commands from captured invert1.s
# and invert2.s. They retain the original selection, sorting and typed values.
SCRIPTS = {
    'identity-preparation': r'''
awk -F\| '$9=="Y" && ($3=="2026AA" || $3=="2025AB"){print $1 "|" $8}' Meta/MRAUI.RRF |sort -t\| +0 -1 -o auis.moved
awk -F\| '{print $8 "|" $12}' Meta/MRCONSO.RRF |sort -t\| +0 -1 |join -t\| -o 2.2 1.1 1.2 auis.moved - |sort -t\| +0 -1 |join -t\| -j1 2 -o 1.1 2.2 2.3 vsab.updates - |sed -n 's/^|//p' >auis_nonupdatedSAB_moved
awk -F\| '$3=="SY" && $7=="Y" && $2=="2025AB"{print $1 "|" $6}' Meta/MRCUI.RRF >cui_merges
''',
    'identity-transitions': r'''
mv aui_said_map aui_said_map.before-transition
grep -v C1976636 aui_said_map.before-transition >aui_said_map
awk -F\| '$3=="Y"{print $2}' aui_said_map |sort -u -o cuis.withmovedaui
awk -F\| '$3=="N"{print $2}' aui_said_map |sort -u |comm -23 cuis.withmovedaui - >cui.splitonly
cut -d\| -f1 ../old/src/cui_said_map |sort |comm -23 cui.splitonly - >cui.splitonly.new
cut -d\| -f2,4 aui_said_map |sort -u -t\| +0 -1 |join -t\| - cui.splitonly.new >cui_splitonly_said_map
awk -F\| '$3=="Y"{print $1 "|" $2 "|" $4}' aui_said_map >moved_aui_said_map
awk -F\| '$3=="N"{print $1 "|" $2 "|" $4}' aui_said_map >aui_said_map.without-moved
mv aui_said_map.without-moved aui_said_map
cut -d\| -f2,3 aui_said_map |sort -u -t\| +0 -1 -o cui_said_map - cui_splitonly_said_map
sort -u cui_said_map -o rel_cui_said_map
''',
    'relationship-normalization': r'''
mv relationships.src relationships.before-normalization.src
awk 'BEGIN{FS=OFS="|"; map["RB"]="BT"; map["RN"]="NT"; map["RO"]="RT"; map["RQ"]="RT?"} map[$4]!=""{$4=map[$4]} $17=="~DA:"{$17=""} {print $0}' relationships.before-normalization.src >relationships.src
''',
    'context-roots': r'''
awk -F\| '$12=="SRC" && $13=="RPT"{print substr($14,3) "|" $1}' Meta/MRCONSO.RRF |sort -t\| +0 -1 |join -t\| -o 1.2 - rsabs-updated.umls |sort -o src-root.cuis.updated
mkdir raw3
''',
    'context-tails': r'''
mv contexts.src contexts.before-tail.src
sed 's/$/||/' contexts.before-tail.src >contexts.src
''',
    'final-atom-format': r'''
sed 's/.*|//' said.ptsaid |sort -u -o ptsaid.order
cp -p classes_atoms.src classes_atoms.src.raw
sed 's/|[^|]*\(|[^|]*\)|[^|]*$/\1/' classes_atoms.src.raw |grep -v SRC/V...V-CCS_2005 >classes_atoms.final.src
mv classes_atoms.final.src classes_atoms.src
'''
}


def worker(package_path):
    guard()
    package = json.loads(Path(package_path).read_text())
    state = {'source': 'MTH', 'version': VERSION, 'engine_ref': BASELINE, 'run_id': RUN_ID,
             'started_at': now(), 'status': 'running', 'worker_pid': os.getpid(), 'run_directory': str(RUN)}
    save(ACTIVE, state)
    stages = {}
    def progress(stage, metrics):
        save(RUN / 'progress.json', {'stage': stage, 'observed_at': now(), **metrics,
             'output_bytes': {name: (TARGET / 'src' / name).stat().st_size for name in compare_mth_core.WIDTHS if (TARGET / 'src' / name).exists()}})
    env = dict(os.environ, LANG='C', LC_COLLATE='C', _POSIX2_VERSION='1', PATH_TO_PERL='/usr/bin/perl')
    def stage(name, command, output=None):
        print('PHASE: ' + name, flush=True)
        stages[name] = execute(command, cwd=TARGET / 'src', stdout=output or RUN / (name + '.stdout.log'),
                              stderr=RUN / (name + '.stderr.log'), env=env,
                              progress=lambda values: progress(name, values))
        save(RUN / 'stages.json', stages)
    def shell(name):
        stage(name, ['/bin/bash', '-e', '-o', 'pipefail', '-c', SCRIPTS[name]])
    def checkpoint(names):
        expected = {x['output_name']: x for x in package['reference_files']}
        for name in names:
            require(TARGET / 'src' / name, expected[name]['sha256'])
        print('CHECKPOINT: exact ' + ', '.join(names), flush=True)
    try:
        with (ROOT / '.replay-runtime.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            verify_inputs(package)
            idle()
            if any((TARGET / 'src' / name).exists() for name in compare_mth_core.WIDTHS):
                raise RuntimeError('This candidate already has generated output')
            shell('identity-preparation')
            checkpoint(['auis_nonupdatedSAB_moved', 'cui_merges'])
            source_metadata = TARGET / 'src/sources.src'
            saved_metadata = RUN / 'sources.full-input.src'
            os.rename(source_metadata, saved_metadata)
            try:
                selected = []
                for row in saved_metadata.read_text().splitlines():
                    if row.startswith('MTH_20'):
                        fields = row.split('|')
                        fields[5] = fields[0][4:]
                        selected.append('|'.join(fields))
                source_metadata.write_text('\n'.join(selected) + '\n')
                stage('source-metadata-builder', ['/usr/bin/perl', str(ROOT / 'INV/bin/SRCbuilder.pl'), '-s', '769443591'])
            finally:
                os.replace(saved_metadata, source_metadata)
            checkpoint(['class_src', 'attr_src', 'rel_src', 'merge_src'])
            stage('atoms-and-initial-map', ['/usr/bin/perl', str(TARGET / 'autoinv.pl'), '../range3.spec', 'inv1.spec'])
            shell('identity-transitions')
            checkpoint(['aui_said_map', 'cui_said_map', 'rel_cui_said_map', 'moved_aui_said_map', 'cui_splitonly_said_map'])
            stage('attributes-relationships-merges', ['/usr/bin/perl', str(TARGET / 'autoinv.pl'), 'inv2.spec'])
            stage('bequeathal-relationships', ['/usr/bin/perl', str(TARGET / 'autoinv.pl'), 'inv3.spec'])
            # Captured invert2.s says "if (subset == 3)", which is false in
            # tcsh (unlike "$subset"). Preserve the observed unfiltered path;
            # do not silently repair the wrapper while establishing baseline.
            shell('relationship-normalization')
            shell('context-roots')
            checkpoint(['src-root.cuis.updated'])
            stage('raw-contexts', ['/usr/bin/perl', str(TARGET / 'mrcxt2raw3.pl')])
            stage('context-attributes', ['/usr/bin/perl', str(ROOT / 'INV/bin/print.raw3.to.attributes.pl'), 'raw3/newsources.raw3'])
            checkpoint(['attributes.contexts-all.src'])
            with (TARGET / 'src/attributes.src').open('ab') as out, (TARGET / 'src/attributes.contexts-all.src').open('rb') as source:
                shutil.copyfileobj(source, out, 4194304)
            stage('contexts', ['/bin/tcsh', '-f', str(TARGET / 'raw_to_contexts.csh'), 'raw3'])
            shell('context-tails')
            stage('preferred-term-order-map', ['/usr/bin/perl', str(TARGET / 'get.saidpts.pl')], TARGET / 'src/said.ptsaid')
            shell('final-atom-format')
            state.update(status='comparing', conversion_completed_at=now())
            save(ACTIVE, state)
            comparison = compare_mth_core.compare(package, TARGET, RUN, save)
            verify_inputs(package)
            for name, item in comparison['files'].items():
                require(TARGET / 'src' / name, item['candidate']['sha256'])
            result = {'source': 'MTH', 'version': VERSION, 'engine_ref': BASELINE, 'run_id': RUN_ID,
                      'stages': stages, 'comparison': comparison, 'acceptance': comparison['acceptance'],
                      'started_at': state['started_at'], 'completed_at': now(),
                      'input_engine_runtime_and_output_hashes_verified_after_run': True,
                      'apparatus_sha256': package['apparatus_sha256'], 'insertion_executed': False}
            save(RUN / 'result.json', result)
            state.update(status='complete', completed_at=result['completed_at'], acceptance_status=result['acceptance']['status'], result_path=str(RUN / 'result.json'))
            save(ACTIVE, state)
            print('RESULT: ' + result['acceptance']['status'], flush=True)
    except BaseException as error:
        state.update(status='failed', completed_at=now(), error=str(error))
        save(ACTIVE, state)
        traceback.print_exc()
        raise


def launch(package, modules):
    guard()
    verify_inputs(package)
    idle()
    if RUN.exists() or ACTIVE.exists():
        raise RuntimeError('Run evidence already exists; deliberate preservation required before another attempt')
    RUN.mkdir(parents=True)
    apparatus = RUN / 'apparatus'
    apparatus.mkdir()
    package['apparatus_sha256'] = {}
    for name, raw in modules.items():
        if Path(name).name != name or not name.endswith('.py'):
            raise RuntimeError('Invalid apparatus filename')
        (apparatus / name).write_bytes(raw)
        (apparatus / name).chmod(0o444)
        package['apparatus_sha256'][name] = hashlib.sha256(raw).hexdigest()
    request = apparatus / 'request-lock.json'
    save(request, package)
    request.chmod(0o444)
    entry = apparatus / 'worker.py'
    entry.write_text('import replay_mth_core as replay\nreplay.worker(' + repr(str(request)) + ')\n')
    entry.chmod(0o444)
    with (RUN / 'worker.log').open('xb') as log:
        process = subprocess.Popen([sys.executable, '-B', str(entry)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, close_fds=True)
    return {'source': 'MTH', 'version': VERSION, 'run_id': RUN_ID, 'engine_ref': BASELINE, 'worker_pid': process.pid,
            'status': 'worker-launched', 'run_directory': str(RUN), 'worker_log': str(RUN / 'worker.log'),
            'launched_at': now(), 'apparatus_sha256': package['apparatus_sha256']}
