#!/usr/bin/env python3
"""Install a pinned INV/ENV bundle on the designated development host.

No source releases, archive tools, services, or database settings are modified.
The bundle is constructed from a Git snapshot by build_shared_runtime_bundle.py.
"""
import argparse
import base64
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import socket
import subprocess
import tempfile

ROOT = Path('/local/content/MEME/MEME5/inv')
BEGIN = '# BEGIN MEME INVERSION BASELINE ENV'
END = '# END MEME INVERSION BASELINE ENV'
ENVIRONMENT = {
    'INV_HOME': str(ROOT / 'INV'),
    'ENV_HOME': str(ROOT / 'ENV'),
    'ENV_FILE': str(ROOT / 'ENV/etc/env.prop'),
    'SRC_ROOT': str(ROOT / 'sources'),
    'MEME_HOME': '/local/content/MEME/MEME5/ncim',
    'LANG': 'en_US.UTF-8',
    'LC_COLLATE': 'C',
    '_POSIX2_VERSION': '1',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_map(root):
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(directory) / name
            if p.is_symlink():
                raise RuntimeError('Unexpected symlink in shared install: ' + str(p))
            if p.is_file():
                result[p.relative_to(root).as_posix()] = p
    return result


def activation_block(shell):
    if shell == 'tcsh':
        return '\n'.join([
            BEGIN,
            'setenv INV_HOME ' + ENVIRONMENT['INV_HOME'],
            'setenv ENV_HOME ' + ENVIRONMENT['ENV_HOME'],
            'setenv ENV_FILE ' + ENVIRONMENT['ENV_FILE'],
            'source $ENV_HOME/bin/env.csh',
            'setenv PATH "${INV_HOME}/bin:$PATH"',
            'setenv LANG en_US.UTF-8',
            'setenv LC_COLLATE C',
            'setenv _POSIX2_VERSION 1',
            END,
        ])
    return '\n'.join([
        BEGIN,
        'export INV_HOME=' + ENVIRONMENT['INV_HOME'],
        'export ENV_HOME=' + ENVIRONMENT['ENV_HOME'],
        'export ENV_FILE=' + ENVIRONMENT['ENV_FILE'],
        '. "$ENV_HOME/bin/env.sh"',
        'export PATH="$INV_HOME/bin:$PATH"',
        'export LANG=en_US.UTF-8',
        'export LC_COLLATE=C',
        'export _POSIX2_VERSION=1',
        END,
    ])


def prepare_profile(path, shell):
    if path.is_symlink():
        raise RuntimeError('Profile symlink needs review: ' + str(path))
    raw = path.read_bytes() if path.exists() else b''
    text = raw.decode('utf-8')
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise RuntimeError('Invalid managed profile markers: ' + str(path))
    unmanaged = re.sub(r'(?ms)^' + re.escape(BEGIN) + r'\n.*?^' + re.escape(END) + r'\n?', '', text)
    for line in unmanaged.splitlines():
        if line.lstrip().startswith('#'):
            continue
        m = re.match(r'\s*(?:(?:export|setenv)\s+)?(INV_HOME|ENV_HOME|ENV_FILE)(?:=|\s+)(.*)', line)
        if m:
            value = m.group(2).strip().strip('"\'')
            if value != ENVIRONMENT[m.group(1)]:
                raise RuntimeError('Existing inversion setting needs review in ' + str(path) + ': ' + m.group(1))
    wanted = (unmanaged.rstrip('\n') + '\n\n' + activation_block(shell) + '\n').encode('utf-8')
    return {'path': path, 'shell': shell, 'before': raw, 'after': wanted, 'existed': path.exists(), 'mode': path.stat().st_mode & 0o777 if path.exists() else 0o644}


def run(args, *, env=None, stdin=None, timeout=25):
    try:
        p = subprocess.run(args, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, env=env, cwd=ROOT)
        return {'status': p.returncode, 'output': p.stdout.decode(errors='replace')[:16000]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': None, 'error': str(exc)}


def atomic_write(path, raw, mode):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.install-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(bundle, apply=False):
    host = socket.gethostname().split('.')[0]
    if host != bundle['expected_host'] or host != 'ncias-d3777-c':
        raise RuntimeError('This deployment is authorized only for ncias-d3777-c')
    if pwd.getpwuid(os.getuid()).pw_name != 'tomcata' or os.getuid() == 0:
        raise RuntimeError('Run as tomcata, not root')
    if ROOT.is_symlink() or not ROOT.is_dir() or not os.access(ROOT, os.W_OK):
        raise RuntimeError('Standard inversion root is not a writable real directory')
    expected = {}
    for f in bundle['files']:
        path = Path(f['path'])
        if path.is_absolute() or '..' in path.parts or len(path.parts) < 2 or path.parts[0] not in ('INV', 'ENV'):
            raise RuntimeError('Invalid bundle path')
        raw = base64.b64decode(f['data_b64'], validate=True)
        if digest(raw) != f['sha256'] or f['path'] in expected or int(f['mode'], 8) & 0o7000:
            raise RuntimeError('Invalid bundle content or mode: ' + f['path'])
        expected[f['path']] = (f, raw)
    for path in ['INV/lib/NLMInv.pm', 'INV/bin/Config/Properties.pm', 'ENV/etc/env.prop', 'ENV/bin/env.sh', 'ENV/bin/env.csh']:
        if path not in expected:
            raise RuntimeError('Required shared component absent: ' + path)
    actions = {}
    for name in ('INV', 'ENV'):
        target = ROOT / name
        if target.is_symlink():
            raise RuntimeError('Install target is a symlink: ' + str(target))
        if target.exists():
            actual = file_map(target)
            wanted = {k[len(name) + 1:]: v for k, v in expected.items() if k.startswith(name + '/')}
            if set(actual) != set(wanted):
                raise RuntimeError('Existing shared tree differs in file inventory: ' + str(target))
            for relative, path in actual.items():
                f, raw = wanted[relative]
                if digest(path.read_bytes()) != f['sha256'] or path.stat().st_mode & 0o7777 != int(f['mode'], 8):
                    raise RuntimeError('Existing shared file differs: ' + str(path))
            actions[name] = 'reuse-verified'
        else:
            actions[name] = 'install-missing'
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    bash_profile = next((home / name for name in ('.bash_profile', '.bash_login', '.profile') if (home / name).exists()), home / '.bash_profile')
    profiles = [prepare_profile(home / '.cshrc', 'tcsh'), prepare_profile(bash_profile, 'bash')]
    if bundle.get('expected_cshrc_sha256') and digest(profiles[0]['before']) != bundle['expected_cshrc_sha256']:
        if BEGIN.encode() not in profiles[0]['before']:
            raise RuntimeError('C-shell profile changed since preflight')
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, 'renameat2'):
        raise RuntimeError('Atomic no-replace directory publication is unavailable')
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    libc.renameat2.restype = ctypes.c_int
    result = {'host': host, 'source_commit': bundle['source_commit'], 'source_ref': bundle['source_ref'],
              'targets': actions, 'files': len(expected), 'profiles': [], 'checks': {}, 'applied': apply}
    if not apply:
        result['profile_paths'] = [str(p['path']) for p in profiles]
        return result
    receipt_path = ROOT / 'installation-receipt.json'
    if receipt_path.is_symlink():
        raise RuntimeError('Installation receipt is a symlink')
    previous = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    source_directories = sorted(x.name for x in (ROOT / 'sources').iterdir())
    for name, action in actions.items():
        if action == 'reuse-verified':
            continue
        staging = Path(tempfile.mkdtemp(prefix='.' + name + '.install-', dir=str(ROOT)))
        try:
            for key, (f, raw) in expected.items():
                if not key.startswith(name + '/'):
                    continue
                path = staging / key[len(name) + 1:]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                path.chmod(int(f['mode'], 8))
                if digest(path.read_bytes()) != f['sha256']:
                    raise RuntimeError('Staged file verification failed')
            target = ROOT / name
            rc = libc.renameat2(-100, os.fsencode(staging), -100, os.fsencode(target), 1)
            if rc:
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code), str(target))
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for profile in profiles:
        path, before, after = profile['path'], profile['before'], profile['after']
        current = path.read_bytes() if path.exists() else b''
        if current != before:
            raise RuntimeError('Profile changed during deployment: ' + str(path))
        backup = None
        if before != after:
            if profile['existed']:
                backup = path.with_name(path.name + '.before-inversion-' + stamp)
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(before)
            atomic_write(path, after, profile['mode'])
        result['profiles'].append({'path': str(path), 'backup': str(backup) if backup else None,
                                   'original_sha256': digest(before), 'installed_sha256': digest(after),
                                   'changed': before != after})
    for key, (f, raw) in expected.items():
        path = ROOT / key
        if digest(path.read_bytes()) != f['sha256'] or path.stat().st_mode & 0o7777 != int(f['mode'], 8):
            raise RuntimeError('Installed file verification failed: ' + key)
    keys = list(ENVIRONMENT) + ['TMP_DIR', 'LVG_HOME', 'INV_HOME_OLD', 'PATH']
    probe = 'import json,os; print("__ENV_BEGIN__"+json.dumps({k:os.environ.get(k) for k in ' + repr(keys) + '})+"__ENV_END__")'
    shell_command = 'python3 -B -c ' + shlex.quote(probe)
    shell_envs = {}
    for shell, args in [('bash', ['bash', '-lc', shell_command]), ('tcsh', ['tcsh', '-c', shell_command])]:
        check = run(args)
        output = check.get('output', '')
        if '__ENV_BEGIN__' in output and '__ENV_END__' in output:
            values = json.loads(output.split('__ENV_BEGIN__', 1)[1].split('__ENV_END__', 1)[0])
            check['environment'] = values
            check['matches_expected'] = all(values.get(k) == v for k, v in ENVIRONMENT.items())
            shell_envs[shell] = values
        else:
            check['matches_expected'] = False
        result['checks'][shell + '_environment'] = check
    env = dict(os.environ)
    env.update({k: v for k, v in shell_envs.get('bash', {}).items() if v is not None})
    isolated = ['unshare', '--user', '--map-root-user', '--net']
    result['checks']['core_module_load'] = run(isolated + ['perl', '-I' + str(ROOT / 'INV/lib'), '-I' + str(ROOT / 'INV/bin'), '-MNLMInv', '-MDigest::MD5', '-MEncode', '-MList::Util', '-e', 'print "NCIt shared modules loaded\n"; print $INC{q(NLMInv.pm)}, "\n"; print $INC{q(Config/Properties.pm)}, "\n";'], env=env)
    for source in bundle['compile_checks']:
        raw = base64.b64decode(source['data_b64'], validate=True)
        if digest(raw) != source['sha256']:
            raise RuntimeError('Compile input hash mismatch')
        if source['interpreter'] == 'perl':
            command = ['perl', '-I' + str(ROOT / 'INV/lib'), '-I' + str(ROOT / 'INV/bin'), '-c', '-']
        elif source['interpreter'] == 'tcsh':
            command = ['tcsh', '-f', '-n']
        else:
            raise RuntimeError('Unsupported compile-check interpreter')
        result['checks'][source['path']] = run(isolated + command, env=env, stdin=raw)
    result['shared_files_verified'] = len(expected)
    result['source_directory_names_unchanged'] = source_directories == sorted(x.name for x in (ROOT / 'sources').iterdir())
    result['completed_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['initial_installation'] = previous.get('initial_installation', {'completed_at': previous['completed_at'], 'source_commit': previous['source_commit'], 'profiles': previous['profiles']}) if previous else {'completed_at': result['completed_at'], 'source_commit': result['source_commit'], 'profiles': result['profiles']}
    if previous:
        result['previous_validation'] = {'completed_at': previous['completed_at'], 'ready_for_case_inputs': previous['ready_for_case_inputs']}
    result['ready_for_case_inputs'] = all(x.get('status') == 0 and x.get('matches_expected', True) for x in result['checks'].values())
    result['pending'] = ['Archived case inputs and frozen official output', 'Historical metadata fixtures for QA/documentation API calls', 'Legacy INV_OLD and MTH runtime dependencies for later source cases']
    result['receipt_path'] = str(ROOT / 'installation-receipt.json')
    result['installed_files'] = [{'path': str(ROOT / key), 'sha256': f['sha256'], 'mode': f['mode']} for key, (f, _) in expected.items()]
    atomic_write(Path(result['receipt_path']), (json.dumps(result, indent=2) + '\n').encode(), 0o644)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', help='JSON bundle path, or - for stdin')
    parser.add_argument('--apply', action='store_true', help='Install after verifying targets and bundle')
    args = parser.parse_args()
    import sys
    bundle = json.load(sys.stdin) if args.bundle == '-' else json.loads(Path(args.bundle).read_text())
    result = install(bundle, apply=args.apply)
    print(json.dumps(result, indent=2))
    if args.apply and not result['ready_for_case_inputs']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
