#!/usr/bin/env python3
"""Submit, inspect or retrieve a dev replay using an existing authenticated SSH socket."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys

from inversion_request import ADAPTERS, digest, load, write_new

HOST = 'ncias-d3777-c.nci.nih.gov'
SOURCES = {'NCI': 'NCI_2026_10D', 'SNOMEDCT_US': 'SNOMEDCT_US_2026_09_01', 'MTH': 'MTH_2026AA'}


def bootstrap(lock, operation, previous=None):
    if digest({k: v for k, v in lock.items() if k != 'lock_sha256'}) != lock['lock_sha256']:
        raise ValueError('Run lock changed')
    if operation not in ('submit', 'inspect-current', 'activate-runtime'):
        raise ValueError('Unsupported bootstrap operation')
    payload = base64.b64encode(json.dumps({'lock': lock, 'previous': previous}).encode()).decode()
    # Payload is base64; no request value is interpolated into shell code. Python
    # imports only the pinned, hash-checked apparatus in a private temporary tree.
    program = """import base64,hashlib,json,pathlib,sys,tempfile
payload=json.loads(base64.b64decode(PAYLOAD))
lock=payload['lock']
hashes={pathlib.Path(x['repository_path']).name:x['sha256'] for x in lock['provenance'] if x['repository_path'].startswith('tools/')}
with tempfile.TemporaryDirectory(prefix='ncim-request-') as temporary:
 root=pathlib.Path(temporary)
 for name,encoded in lock['modules_b64'].items():
  if pathlib.Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid apparatus path')
  raw=base64.b64decode(encoded,validate=True)
  if hashlib.sha256(raw).hexdigest()!=hashes.get(name):raise ValueError('Apparatus changed')
  (root/name).write_bytes(raw)
 sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 import inversion_worker as worker
 worker.verify_lock(lock)
 operation=OPERATION
 if operation=='submit':result=worker.launch(lock,payload['previous'])
 elif operation=='activate-runtime':result=worker.activate_runtime(lock)
 else:result=worker.inspect_current(lock['request']['source'])
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD', repr(payload)).replace('OPERATION', repr(operation))
    return "python3 -B - <<'NCIM_COMMON_REQUEST'\n" + program + '\nNCIM_COMMON_REQUEST\nexit\n'


def read_program(source, run_id, collect):
    if source not in SOURCES or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', run_id):
        raise ValueError('Invalid source or run identity')
    # Also inspect the already executed characterization runs, without changing
    # or relabeling their historical apparatus/engine identities.
    locations = [f'/local/content/MEME/MEME5/inv/qa/replay-requests/{run_id}',
                 f'/local/content/MEME/MEME5/inv/sources/{SOURCES[source]}/qa/replay-runs/{run_id}',
                 f'/local/content/MEME/MEME5/inv/sources/{SOURCES[source]}/etc/qa/replay-runs/{run_id}']
    program = """import json,pathlib,socket
if socket.gethostname().split('.')[0]!='ncias-d3777-c':raise RuntimeError('Wrong server')
locations=[pathlib.Path(x) for x in LOCATIONS]
# A common run has a control report plus an inner legacy run. MTH also has
# etc -> . compatibility links, so two legacy spellings can be one directory.
found=[locations[0].resolve()] if locations[0].is_dir() else sorted({x.resolve() for x in locations[1:] if x.is_dir()})
if len(found)!=1:raise RuntimeError('No unique run directory')
root=found[0]
names=['status.json','progress.json','launch.json','result.json','preparation.json','acquisition.json','raw-result.json','correction-audit.json','correction-audit-execution.json'] if COLLECT else ['status.json','progress.json']
result={'source':SOURCE,'run_id':RUN_ID,'run_directory':str(root),'records':{}}
for name in names:
 path=root/name
 if path.is_symlink():raise RuntimeError('Unexpected report symlink')
 if path.is_file():result['records'][name]=json.loads(path.read_text())
if root==locations[0].resolve():
 adapters=sorted({x.resolve() for x in locations[1:] if x.is_dir()})
 if len(adapters)>1:raise RuntimeError('No unique inner adapter run')
 if adapters:
  adapter=adapters[0]
  for name,path in [('adapter_progress.json',adapter/'progress.json'),('adapter_active.json',adapter.parents[2]/'replay-active-run.json')]:
   if path.is_symlink():raise RuntimeError('Unexpected adapter report symlink')
   if path.is_file():
    record=json.loads(path.read_text())
    if name=='adapter_progress.json' or record.get('run_id')==RUN_ID:result['records'][name]=record
else:
 path=root.parents[2]/'replay-active-run.json'
 if path.is_file():
  active=json.loads(path.read_text())
  if active.get('run_id')==RUN_ID:result['records']['active']=active
print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('LOCATIONS', repr(locations)).replace('COLLECT', repr(collect)).replace('SOURCE', repr(source)).replace('RUN_ID', repr(run_id))
    return "python3 -B - <<'NCIM_COMMON_READ'\n" + program + '\nNCIM_COMMON_READ\nexit\n'


def remote(program, socket_path, account):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', account):
        raise ValueError('Invalid SSH account')
    command = ['ssh', '-T', '-S', str(Path(socket_path).resolve()), '-o', 'HostKeyAlias=ncias-d3777-c',
               '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', account + '@' + HOST, 'sudo su - tomcata']
    result = subprocess.run(command, input=program, capture_output=True, text=True, timeout=1800)
    if result.returncode:
        raise RuntimeError('Dev command failed: ' + result.stderr[-3000:] + result.stdout[-3000:])
    begin, end = 'BEGIN_COMMON_REPLAY_RESULT\n', '\nEND_COMMON_REPLAY_RESULT'
    if result.stdout.count(begin) != 1 or result.stdout.count(end) != 1:
        raise RuntimeError('No unique structured dev result: ' + result.stderr[-1000:] + result.stdout[-1000:])
    return json.loads(result.stdout.split(begin, 1)[1].split(end, 1)[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', required=True, help='Existing authenticated dev SSH control socket')
    parser.add_argument('--account', default='shapirod2')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('submit', 'inspect-current', 'activate-runtime'):
        command = commands.add_parser(name)
        command.add_argument('lock')
        command.add_argument('--previous-receipt') if name == 'submit' else None
        command.add_argument('--output', required=True)
    for name in ('status', 'collect'):
        command = commands.add_parser(name)
        command.add_argument('--source', choices=tuple(ADAPTERS), required=True)
        command.add_argument('--run-id', required=True)
        command.add_argument('--output', required=True)
    args = parser.parse_args()
    if Path(args.output).exists():
        raise ValueError('Output already exists; previous evidence is never overwritten')
    if args.command in ('submit', 'inspect-current', 'activate-runtime'):
        lock = load(args.lock)
        previous = load(args.previous_receipt) if getattr(args, 'previous_receipt', None) else None
        program = bootstrap(lock, args.command, previous)
    else:
        program = read_program(args.source, args.run_id, args.command == 'collect')
    result = remote(program, args.socket, args.account)
    write_new(args.output, result)
    records = result.get('records', {})
    status = result.get('status') or records.get('status.json', {}).get('status') or records.get('active', {}).get('status')
    stage = records.get('progress.json', records.get('adapter_progress.json', {})).get('stage')
    adapter_status = records.get('adapter_active.json', {}).get('status')
    if status == 'converting' and adapter_status == 'comparing':
        stage = 'comparison'
    elif status == 'converting' and adapter_status == 'complete':
        stage = 'verifying-final-artifacts'
    elif status in ('complete', 'failed'):
        stage = status
    print(json.dumps({'saved': args.output, 'run_id': result.get('run_id'), 'status': status,
                      'stage': stage}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
