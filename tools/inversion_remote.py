#!/usr/bin/env python3
"""Submit, inspect or retrieve a dev replay using an existing authenticated SSH socket."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import sys

from inversion_request import ADAPTERS, audit_review_capsule, retention_capsule, digest, load, write_new

HOST = 'ncias-d3777-c.nci.nih.gov'
SOURCES = {'NCI': 'NCI_2026_10D', 'SNOMEDCT_US': 'SNOMEDCT_US_2026_09_01', 'MTH': 'MTH_2026AA',
           'MDR': 'MDR_29_1', 'RADLEX': 'RADLEX_4_3'}


def bootstrap(lock, operation, previous=None):
    if digest({k: v for k, v in lock.items() if k != 'lock_sha256'}) != lock['lock_sha256']:
        raise ValueError('Run lock changed')
    if operation not in ('submit', 'inspect-current', 'activate-runtime', 'retention-status', 'verify-native'):
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
 native=lock.get('artifact_type')=='ncimeta-native-release-lock'
 if native:import release_worker as worker
 else:import inversion_worker as worker
 worker.verify_lock(lock)
 operation=OPERATION
 if operation=='submit':result=worker.launch(lock,payload['previous'])
 elif operation=='activate-runtime':result=worker.activate_runtime(lock)
 elif operation=='retention-status':result=worker.retention_status(lock if native else lock['request']['source'])
 elif operation=='verify-native':
  if not native:raise ValueError('Native verification requires a native release lock')
  result=worker.verify_retained(lock)
 else:result=worker.inspect_current(lock if native else lock['request']['source'])
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD', repr(payload)).replace('OPERATION', repr(operation))
    return "python3 -B - <<'NCIM_COMMON_REQUEST'\n" + program + '\nNCIM_COMMON_REQUEST\nexit\n'


def bootstrap_review(capsule):
    payload = base64.b64encode(json.dumps(capsule).encode()).decode()
    program = """import base64,hashlib,json,pathlib,sys,tempfile
capsule=json.loads(base64.b64decode(PAYLOAD))
hashes={pathlib.Path(x['repository_path']).name:x['sha256'] for x in capsule['provenance']}
with tempfile.TemporaryDirectory(prefix='ncim-audit-review-') as temporary:
 root=pathlib.Path(temporary)
 for name,encoded in capsule['modules_b64'].items():
  if pathlib.Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid apparatus path')
  raw=base64.b64decode(encoded,validate=True)
  if hashlib.sha256(raw).hexdigest()!=hashes.get(name):raise ValueError('Apparatus differs')
  (root/name).write_bytes(raw)
 sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 from inversion_worker import launch_audit_review
 result=launch_audit_review(capsule)
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD', repr(payload))
    return "python3 -B - <<'NCIM_COMMON_REVIEW'\n" + program + '\nNCIM_COMMON_REVIEW\nexit\n'


def bootstrap_release_operation(capsule):
    payload = base64.b64encode(json.dumps(capsule).encode()).decode()
    program = """import base64,hashlib,json,pathlib,pwd,os,resource,socket,sys,tempfile
if socket.gethostname().split('.')[0]!='ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name!='tomcata':raise RuntimeError('Wrong dev context')
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
capsule=json.loads(base64.b64decode(PAYLOAD))
hashes={pathlib.Path(x['repository_path']).name:x['sha256'] for x in capsule['provenance']}
with tempfile.TemporaryDirectory(prefix='ncim-release-review-') as temporary:
 root=pathlib.Path(temporary)
 for name,encoded in capsule['modules_b64'].items():
  if pathlib.Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid operation module')
  raw=base64.b64decode(encoded,validate=True)
  if hashlib.sha256(raw).hexdigest()!=hashes.get(name):raise ValueError('Operation code differs')
  (root/name).write_bytes(raw)
 sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 import release_manifest as manifests
 if capsule['capsule_sha256']!=manifests.digest({k:v for k,v in capsule.items() if k!='capsule_sha256'}):raise ValueError('Operation capsule changed')
 if capsule['artifact_type']=='ncimeta-release-discovery-capsule':
  if manifests.digest(capsule['manifest'])!=capsule['manifest_sha256']:raise ValueError('Discovery manifest changed')
  from release_preparation import discover
  result=discover(capsule['manifest'],schema_validated=True)
  result['apparatus_ref']=capsule['apparatus_ref'];result['schema_sha256']=capsule['schema_sha256']
 elif capsule['artifact_type']=='ncimeta-release-operation' and capsule['operation']=='review-native':
  from release_operations import run_review
  result=run_review(capsule)
 else:raise ValueError('Unknown release operation')
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD',repr(payload))
    return "python3 -B - <<'NCIM_RELEASE_OPERATION'\n"+program+'\nNCIM_RELEASE_OPERATION\nexit\n'


def read_program(source, run_id, collect):
    if source not in SOURCES or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}', run_id):
        raise ValueError('Invalid source or run identity')
    # Also inspect the already executed characterization runs, without changing
    # or relabeling their historical apparatus/engine identities.
    locations = [f'/local/content/MEME/MEME5/inv/qa/replay-requests/{run_id}',
                 f'/local/content/MEME/MEME5/inv/sources/{SOURCES[source]}/qa/replay-runs/{run_id}',
                 f'/local/content/MEME/MEME5/inv/sources/{SOURCES[source]}/etc/qa/replay-runs/{run_id}']
    program = """import json,pathlib,re,socket
if socket.gethostname().split('.')[0]!='ncias-d3777-c':raise RuntimeError('Wrong server')
locations=[pathlib.Path(x) for x in LOCATIONS]
# A common run has a control report plus an inner legacy run. MTH also has
# etc -> . compatibility links, so two legacy spellings can be one directory.
found=[locations[0].resolve()] if locations[0].is_dir() else sorted({x.resolve() for x in locations[1:] if x.is_dir()})
if len(found)!=1:raise RuntimeError('No unique run directory')
root=found[0]
names=['status.json','progress.json','launch.json','result.json','preparation.json','acquisition.json','raw-result.json','correction-audit.json','correction-audit-execution.json','parent-records.json','acceptance-review.json'] if COLLECT else ['status.json','progress.json']
result={'source':SOURCE,'run_id':RUN_ID,'run_directory':str(root),'records':{}}
for name in names:
 path=root/name
 if path.is_symlink():raise RuntimeError('Unexpected report symlink')
 if path.is_file():result['records'][name]=json.loads(path.read_text())
if root==locations[0].resolve():
 state=result['records'].get('status.json',{})
 version=state.get('version');actual_source=state.get('source')
 if version is None or actual_source is None:
  lock_path=root/'case.lock.json'
  if not lock_path.exists():
   parent=state.get('parent_run_id')
   if not isinstance(parent,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}',parent):raise RuntimeError('No locked common release identity')
   lock_path=root.parent/parent/'case.lock.json'
  if lock_path.is_symlink():raise RuntimeError('Unexpected common lock symlink')
  request=json.loads(lock_path.read_text())['request']
  version=request['version'];actual_source=request['source']
 if actual_source!=SOURCE or not re.fullmatch(re.escape(SOURCE)+r'_[A-Za-z0-9_]+',version):raise RuntimeError('Common run belongs to another source or unsafe release')
 source_root=pathlib.Path('/local/content/MEME/MEME5/inv/sources')/version
 adapter_locations=[source_root/'qa/replay-runs'/RUN_ID,source_root/'etc/qa/replay-runs'/RUN_ID]
 adapters=sorted({x.resolve() for x in adapter_locations if x.is_dir()})
 if len(adapters)>1:raise RuntimeError('No unique inner adapter run')
 if adapters:
  adapter=adapters[0]
  for name,path in [('adapter_progress.json',adapter/'progress.json'),('adapter_active.json',adapter.parents[2]/'replay-active-run.json')]:
   if path.is_symlink():raise RuntimeError('Unexpected adapter report symlink')
   if path.is_file():
    record=json.loads(path.read_text())
    if name=='adapter_progress.json' or record.get('run_id')==RUN_ID:result['records'][name]=record
 if COLLECT:
  for path in sorted(root.glob('acquisition-*.json')):
   if path.is_symlink() or path.stat().st_size>1048576:raise RuntimeError('Unexpected object acquisition receipt')
   result['records'][path.name]=json.loads(path.read_text())
else:
 path=root.parents[2]/'replay-active-run.json'
 if path.is_file():
  active=json.loads(path.read_text())
  if active.get('run_id')==RUN_ID:result['records']['active']=active
print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('LOCATIONS', repr(locations)).replace('COLLECT', repr(collect)).replace('SOURCE', repr(source)).replace('RUN_ID', repr(run_id))
    return "python3 -B - <<'NCIM_COMMON_READ'\n" + program + '\nNCIM_COMMON_READ\nexit\n'


def bootstrap_retention(capsule):
    payload = base64.b64encode(json.dumps(capsule).encode()).decode()
    program = """import base64,hashlib,json,pathlib,signal,sys,tempfile
signal.signal(signal.SIGHUP,signal.SIG_IGN)
capsule=json.loads(base64.b64decode(PAYLOAD))
unsigned={k:v for k,v in capsule.items() if k!='capsule_sha256'}
raw=json.dumps(unsigned,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
if hashlib.sha256(raw).hexdigest()!=capsule['capsule_sha256']:raise ValueError('Retention capsule changed')
if capsule['artifact_type']!='ncimeta-dev-retention-request':raise ValueError('Wrong retention capsule')
hashes={pathlib.Path(x['repository_path']).name:x['sha256'] for x in capsule['provenance']}
with tempfile.TemporaryDirectory(prefix='ncim-retention-') as temporary:
 root=pathlib.Path(temporary)
 for name,encoded in capsule['modules_b64'].items():
  if pathlib.Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid apparatus path')
  raw=base64.b64decode(encoded,validate=True)
  if hashlib.sha256(raw).hexdigest()!=hashes.get(name):raise ValueError('Retention apparatus differs')
  (root/name).write_bytes(raw)
 sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 import replay_retention
 functions={'status':replay_retention.status,'plan':replay_retention.plan,'compact':replay_retention.compact,'restore':replay_retention.restore}
 if capsule['operation'].startswith('retire-'):
  import retire_replay_bulk
  functions.update({'retire-plan':retire_replay_bulk.plan,'retire-bulk':retire_replay_bulk.apply})
 result=functions[capsule['operation']](**capsule['parameters'])
 result['retention_apparatus_ref']=capsule['apparatus_ref']
 result['retention_capsule_sha256']=capsule['capsule_sha256']
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD', repr(payload))
    return "python3 -B - <<'NCIM_RETENTION'\n" + program + '\nNCIM_RETENTION\nexit\n'


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
    for name in ('submit', 'inspect-current', 'activate-runtime', 'retention-status', 'verify-native'):
        command = commands.add_parser(name)
        command.add_argument('lock')
        command.add_argument('--previous-receipt') if name == 'submit' else None
        command.add_argument('--output', required=True)
    for name in ('status', 'collect'):
        command = commands.add_parser(name)
        command.add_argument('--source', choices=tuple(SOURCES), required=True)
        command.add_argument('--run-id', required=True)
        command.add_argument('--output', required=True)
    review = commands.add_parser('retry-mth-audit', help='Review completed MTH output in a new run; preserve the original failure')
    review.add_argument('--parent-run-id', required=True)
    review.add_argument('--review-id', required=True)
    review.add_argument('--output', required=True)
    discovery = commands.add_parser('discover-release', help='Read source preparation inputs on dev; no inversion or acquisition')
    discovery.add_argument('manifest')
    discovery.add_argument('--output', required=True)
    acceptance = commands.add_parser('review-native', help='Publish a separate acceptance review of completed dev output')
    acceptance.add_argument('lock')
    acceptance.add_argument('--policy', choices=('exact-v1','mth-retained-identity-v1'), required=True)
    acceptance.add_argument('--diagnostic')
    acceptance.add_argument('--review-id', required=True)
    acceptance.add_argument('--output', required=True)
    for name in ('plan', 'compact', 'restore', 'retire-plan', 'retire-bulk'):
        child = commands.add_parser('retention-' + name)
        if name in ('plan', 'retire-plan'):
            child.add_argument('--run-id', required=True)
            if name == 'plan':
                child.add_argument('--verification')
                child.add_argument('--verification-sha256')
        else:
            child.add_argument('--plan-path', required=True)
            child.add_argument('--plan-sha256', required=True)
            if name == 'restore':child.add_argument('--destination', required=True)
        child.add_argument('--output', required=True)
    args = parser.parse_args()
    if Path(args.output).exists():
        raise ValueError('Output already exists; previous evidence is never overwritten')
    if args.command in ('submit', 'inspect-current', 'activate-runtime', 'retention-status', 'verify-native'):
        lock = load(args.lock)
        previous = load(args.previous_receipt) if getattr(args, 'previous_receipt', None) else None
        if args.command == 'retention-status' and lock.get('artifact_type') != 'ncimeta-native-release-lock':
            program = bootstrap_retention(retention_capsule('status', {'version': lock['request']['version']}))
        else:
            program = bootstrap(lock, args.command, previous)
    elif args.command == 'discover-release':
        import release_preparation
        program = bootstrap_release_operation(release_preparation.capsule(load(args.manifest)))
    elif args.command == 'review-native':
        from release_operations import review_capsule
        program = bootstrap_release_operation(review_capsule(load(args.lock),args.policy,
            load(args.diagnostic) if args.diagnostic else None,args.review_id))
    elif args.command == 'retry-mth-audit':
        program = bootstrap_review(audit_review_capsule(args.parent_run_id, args.review_id))
    elif args.command.startswith('retention-'):
        operation = args.command.removeprefix('retention-')
        parameters = {key: value for key, value in vars(args).items()
                      if key not in ('socket', 'account', 'command', 'output')}
        program = bootstrap_retention(retention_capsule(operation, parameters))
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
    if args.command=='discover-release':raise SystemExit(2 if result['status']=='DISCOVERY_BLOCKED' else 3 if result['status']=='DECISIONS_REQUIRED' else 0)
    if args.command=='review-native':raise SystemExit(0 if result['accepted'] else 3)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
