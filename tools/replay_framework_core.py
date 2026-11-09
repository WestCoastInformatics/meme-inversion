#!/usr/bin/env python3
"""Fresh bounded MDR/RADLEX core runs at mirrored dev paths using Git code."""
import base64
import datetime
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

import compare_framework_core as comparison
from prepare_snomed_candidate import publish
from replay_mth_core import save
from replay_process import available_memory, execute, runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')
ENGINE = '36f1e10aeadb9faa184fd386573f82e6dd9b53c8'
MDR_ENGINE = 'dd7ae6610557074c1b7b66690538a0591987d056'
MDR_RUNTIME = 'bfda2ce9b0d0ab23db3182d37aab4b1f5a13fd09'
CASES = {'MDR': ('MDR_29_1', 777143593, 124407941, 'V-MDR'),
         'RADLEX': ('RADLEX_4_3', 767743593, 116482203, 'V-RADLEX')}
SCRIPTS = {'MDR': ['invert_mdr.pl', 'append_atn.pl'],
           'RADLEX': ['makesrc.pl', 'remove_dup_rels.pl', 'remove_dup_classes.pl', 'remove_dup_attributes.pl']}
INPUTS = {'MDR': {'orig/fromprovider/MedAscii/'+name for name in ['soc.asc','intl_ord.asc','hlgt.asc','hlt.asc','pt.asc','llt.asc','smq_list.asc','smq_content.asc','soc_hlgt.asc','hlgt_hlt.asc','hlt_pt.asc','mdhier.asc']} | {'etc/MG_Abbreviations','orig/mdr_by_version.txt','src/sources.src','src/termgroups.src'},
          'RADLEX': {'orig/radlex_pipe.txt','src/sources.src','src/termgroups.src'}}


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(4194304),b''):value.update(block)
    return value.hexdigest()


def require(path, expected):
    if path.is_symlink() or not path.is_file() or sha(path)!=expected:raise RuntimeError('Frozen input/code differs: '+str(path))


def relative(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or path.as_posix()!=name:raise ValueError('Unsafe relative path')
    return name


def guard(package, target):
    if socket.gethostname().split('.')[0]!='ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name!='tomcata':
        raise RuntimeError('Framework replay requires tomcata on dev')
    expected=CASES.get(package['source'])
    corrected=package.get('case_variant')=='consistent-history-context'
    engine=MDR_ENGINE if corrected and package['source']=='MDR' else ENGINE
    if expected!=(package['version'],package['source_atom_ids']['start'],package['root_atom_id'],package['root_code']) or package['engine_ref']!=engine:
        raise RuntimeError('Unreviewed source/version/engine/identity contract')
    if corrected and (package['source']!='MDR' or package.get('runtime_ref')!=MDR_RUNTIME or package.get('perl_hash_seed') not in ('1','12345')):raise RuntimeError('Unreviewed corrected MDR runtime/seed')
    if len(package['input_files'])!=len(INPUTS[package['source']]) or {x['relative_path'] for x in package['input_files']}!=INPUTS[package['source']]:
        raise RuntimeError('The complete reviewed starting input set is required')
    required_code={'bin/'+name for name in SCRIPTS[package['source']]} | {'etc/'+('MDR.cfg' if package['source']=='MDR' else 'RADLEX.cfg')}
    if not required_code <= {x['relative_path'] for x in package['code_files']}:raise RuntimeError('An active source script/configuration is missing')
    if Path(package['archive_path'])!=ROOT/'sources'/(package['version']+'.tgz'):raise RuntimeError('Unexpected frozen archive path')
    if package['source_atom_ids']['end']!={'MDR':777343592,'RADLEX':767813671}[package['source']]:raise RuntimeError('Unreviewed historical ID upper bound')
    if target!=ROOT/'sources'/package['version'] or any(path.is_symlink() for path in [ROOT,ROOT/'sources',target]):
        raise RuntimeError('Unexpected mirrored source path')
    if os.environ.get('INV_HOME')!=str(ROOT/'INV') or os.environ.get('LC_COLLATE')!='C':raise RuntimeError('Mirrored environment is required')


def verify_capsule(package):
    unsigned={key:value for key,value in package.items() if key!='capsule_sha256'}
    raw=json.dumps(unsigned,sort_keys=True,separators=(',', ':'),ensure_ascii=True).encode()
    if package.get('capsule_sha256')!=hashlib.sha256(raw).hexdigest():raise RuntimeError('Characterization capsule changed')
    if package.get('artifact_type')!='ncimeta-framework-characterization':raise RuntimeError('Unexpected characterization contract')
    if not __import__('re').fullmatch(r'[a-z0-9][a-z0-9-]{1,70}',package['run_id']):raise RuntimeError('Invalid run identity')
    guard(package,ROOT/'sources'/package['version'])


def capacity(package=None):
    # Measured MDR retained outputs are <1.2 GiB/run; comparison scratch <6 GiB.
    # The bounded correction case keeps 12 GiB reserve plus an 8 GiB work budget.
    minimum=20 if package and package.get('case_variant')=='consistent-history-context' else 50
    if available_memory()<24*1024**3 or shutil.disk_usage(ROOT).free<minimum*1024**3:raise RuntimeError('Dev capacity reserve is unavailable')


def inspect_previous(package,expected_run):
    verify_capsule(package);target=ROOT/'sources'/package['version']
    if package['source']!='MDR':raise RuntimeError('Correction preservation is scoped to MDR')
    from inversion_worker import idle,manifest,digest
    with runtime_lock(ROOT):
        idle();state=json.loads((target/'etc/replay-active-run.json').read_text())
        if state.get('status')!='complete' or state.get('run_id')!=expected_run:raise RuntimeError('Previous completed MDR run differs')
        result_path=ROOT/'qa/replay-requests'/expected_run/'result.json';result=json.loads(result_path.read_text())
        if result['run_id']!=expected_run or result['engine_ref']!=state['engine_ref']:raise RuntimeError('Previous MDR result differs')
        for name,item in result['comparison']['files'].items():require(target/'src'/name,item['candidate']['sha256'])
        receipt={'source':'MDR','version':target.name,'root_mode':oct(target.stat().st_mode&0o777),'manifest':manifest(target),
                 'previous_run_id':expected_run,'previous_result_sha256':sha(result_path)}
        receipt['receipt_sha256']=digest(receipt);return receipt


def launch(package):
    """Freeze an explicitly scoped baseline case, then detach under the dev lock."""
    verify_capsule(package)
    target=ROOT/'sources'/package['version'];control=ROOT/'qa/replay-requests'
    if (ROOT/'qa').is_symlink() or control.is_symlink():raise RuntimeError('Unexpected control path symlink')
    with runtime_lock(ROOT) as held:
        from replay_mth_core import idle
        idle();capacity(package)
        if target.exists() and not package.get('previous_source_receipt'):raise RuntimeError('Existing candidate requires an immutable preservation receipt')
        if package.get('previous_source_receipt') and package.get('case_variant')!='consistent-history-context':raise RuntimeError('Only reviewed corrected MDR cases may preserve a predecessor')
        for item in package['runtime_files']:require(ROOT/relative(item['relative_path']),item['sha256'])
        require(Path(package['archive_path']),package['archive_sha256'])
        control.mkdir(parents=True,exist_ok=True);run=control/package['run_id'];run.mkdir()
        apparatus=run/'apparatus';apparatus.mkdir()
        for name,encoded in package['modules_b64'].items():
            if Path(name).name!=name or not name.endswith('.py'):raise RuntimeError('Invalid frozen module name')
            raw=base64.b64decode(encoded,validate=True)
            if hashlib.sha256(raw).hexdigest()!=package['apparatus_sha256'].get(name):raise RuntimeError('Frozen module changed')
            path=apparatus/name;path.write_bytes(raw);path.chmod(0o444)
        package_path=run/'characterization.lock.json';save(package_path,package);package_path.chmod(0o400)
        entry=run/'worker.py'
        entry.write_text('import os,sys\nsys.dont_write_bytecode=True\nsys.path.insert(0,'+repr(str(apparatus))+')\nfrom replay_framework_core import worker\nwith os.fdopen('+str(held.fileno())+",'a') as held:\n worker("+repr(str(package_path))+',inherited_lock=held)\n')
        entry.chmod(0o444)
        save(run/'status.json',{'status':'launching','source':package['source'],'run_id':package['run_id']})
        with (run/'worker.log').open('xb') as out:
            process=subprocess.Popen([sys.executable,'-B','-u',str(entry)],stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,
                                     start_new_session=True,close_fds=True,pass_fds=(held.fileno(),))
        receipt={'source':package['source'],'version':package['version'],'run_id':package['run_id'],'worker_pid':process.pid,
                 'run_directory':str(run),'capsule_sha256':package['capsule_sha256'],'engine_ref':package['engine_ref'],
                 'apparatus_ref':package['apparatus_ref'],'launched_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'scope':'Fresh source-specific baseline characterization, not a completed common-adapter integration'}
        save(run/'launch.json',receipt);return receipt


def verify_inputs(package, target):
    guard(package,target)
    require(Path(package['archive_path']),package['archive_sha256'])
    if len(package['runtime_files'])!=169:raise RuntimeError('Complete production shared runtime is required')
    for item in package['runtime_files']:require(ROOT/relative(item['relative_path']),item['sha256'])
    for item in package['input_files']:require(target/relative(item['relative_path']),item['sha256'])
    for item in package['code_files']:
        if item['kind']!='file':raise RuntimeError('This captured source has only regular code files')
        require(target/relative(item['relative_path']),item['sha256'])
    cfg=target/'etc'/('MDR.cfg' if package['source']=='MDR' else 'RADLEX.cfg')
    values={}
    for line in cfg.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
        key,value=(x.strip() for x in line.split('=',1));values[key]=value
    for key,value in [('VSAB',package['version']),('RSAB',package['source']),('SaidStart',str(package['source_atom_ids']['start'])),
                      ('HC.RootNodeSaid',str(package['root_atom_id'])),('HC.RootNodeCode',package['root_code'])]:
        if values.get(key)!=value:raise RuntimeError('Captured configuration conflicts with case: '+key)
    if package['source']=='MDR' and int(values['SaidEnd'])!=package['source_atom_ids']['end']:raise RuntimeError('Captured MDR ID end differs')
    rows=[line.split('|') for line in (target/'src/sources.src').read_text().splitlines() if line.startswith(package['version']+'|')]
    if len(rows)!=1 or rows[0][1]!=package['replacement_baseline']:raise RuntimeError('Replacement baseline differs from archived metadata')


def prepare(package, progress=print):
    target=ROOT/'sources'/package['version'];guard(package,target)
    if target.exists():raise RuntimeError('Common preservation must precede fresh preparation')
    require(Path(package['archive_path']),package['archive_sha256'])
    staging=Path(tempfile.mkdtemp(prefix='.'+package['version']+'.prepare-',dir=str(ROOT/'sources')))
    try:
        for name in ['bin','etc/qa','src','orig','tmp','insert']:(staging/name).mkdir(parents=True,exist_ok=True)
        for item in package['code_files']:
            name=relative(item['relative_path'])
            if not name.startswith(('bin/','etc/')) or item['kind']!='file':raise RuntimeError('Unexpected captured source-code path')
            raw=base64.b64decode(item['data_b64'],validate=True)
            if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise RuntimeError('Git source payload differs')
            path=staging/name;path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as handle:handle.write(raw)
            path.chmod(int(item['mode'],8))
        wanted={package['version']+'/'+relative(item['relative_path']):item for item in package['input_files']};found=set()
        if len(wanted)!=len(package['input_files']):raise RuntimeError('Duplicate input declaration')
        for name,item in wanted.items():
            rel=item['relative_path']
            if rel.startswith('src/') and rel not in ('src/sources.src','src/termgroups.src'):raise RuntimeError('Generated output cannot be a candidate input')
        with tarfile.open(package['archive_path'],'r|gz') as archive:
            for member in archive:
                name=PurePosixPath(member.name).as_posix()
                if name not in wanted:continue
                if not member.isfile() or name in found:raise RuntimeError('Input member is not unique and regular')
                item=wanted[name];path=staging/item['relative_path'];path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as handle:shutil.copyfileobj(archive.extractfile(member),handle,4194304)
                require(path,item['sha256']);path.chmod(0o400);found.add(name)
        if found!=set(wanted) or any((staging/'src'/name).exists() for name in comparison.OUTPUTS):raise RuntimeError('Incomplete inputs or seeded generated output')
        publish(staging,target)
        verify_inputs(package,target)
        result={'source':package['source'],'version':package['version'],'engine_ref':package['engine_ref'],
                'input_files':package['input_files'],'code_files':[{k:v for k,v in item.items() if k!='data_b64'} for item in package['code_files']],
                'starting_stage':package['starting_stage'],'replacement_baseline':package['replacement_baseline'],
                'saved_external_root':{'said':package['root_atom_id'],'code':package['root_code']},
                'generated_outputs_seeded':False,'insertion_executed':False,'prepared_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        save(target/'etc/replay-preparation.json',result)
        return result
    finally:
        if staging.exists():shutil.rmtree(staging)


def worker(package_path, inherited_lock=None):
    package=json.loads(Path(package_path).read_text());verify_capsule(package);target=ROOT/'sources'/package['version']
    run=Path(package_path).parent;active=target/'etc/replay-active-run.json'
    state={'source':package['source'],'version':package['version'],'engine_ref':package['engine_ref'],'run_id':package['run_id'],
           'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running','worker_pid':os.getpid()}
    prepared=False
    def state_save():
        save(run/'status.json',state)
        if prepared:save(active,state)
    state_save();stages={};snapshots={}
    def stage(name,script,syntax=False):
        print('PHASE: '+name,flush=True)
        command=['/usr/bin/perl']+(['-c'] if syntax else [])+[str(target/'bin'/script)]
        env=os.environ.copy()
        if package.get('perl_hash_seed'):env.update(PERL_HASH_SEED=package['perl_hash_seed'],PERL_PERTURB_KEYS='2')
        stages[name]=execute(command,cwd=target/'bin',stdout=run/(name+'.stdout.log'),stderr=run/(name+'.stderr.log'),env=env,
                             progress=lambda metrics:save(run/'progress.json',{'stage':name,**metrics}),timeout=3600)
        save(run/'stages.json',stages)
    def preserve(name,label):
        source=target/'src'/name;destination=run/(label+'.'+name)
        if source.is_symlink() or not source.is_file():raise RuntimeError('Expected generated stage output absent: '+name)
        shutil.copyfile(source,destination);destination.chmod(0o400)
        snapshots[label+'.'+name]=comparison.file_info(destination)
    def replace(name,output):
        source=target/'tmp'/name
        if source.is_symlink() or not source.is_file() or not source.stat().st_size:raise RuntimeError('Cleanup output is absent: '+name)
        shutil.copyfile(source,target/'src'/output)
    try:
        with runtime_lock(ROOT,inherited_lock):
            from replay_mth_core import idle
            idle();capacity(package)
            preserved=None
            if package.get('previous_source_receipt'):
                from inversion_worker import preserve,restore
                receipt=package['previous_source_receipt']
                require(ROOT/'qa/replay-requests'/receipt['previous_run_id']/'result.json',receipt['previous_result_sha256'])
                preserved=preserve(target,package['run_id'],receipt,before_publish=idle)
            try:preparation=prepare(package)
            except BaseException:
                if preserved and not target.exists():restore(preserved,target,receipt)
                raise
            prepared=True;preparation['preserved_source']=str(preserved) if preserved else None
            save(run/'preparation.json',preparation);state_save()
            verify_inputs(package,target)
            if any((target/'src'/name).exists() for name in comparison.OUTPUTS):raise RuntimeError('Candidate already contains generated outputs')
            for script in SCRIPTS[package['source']]:stage('syntax-'+script,script,True)
            stage('inversion',SCRIPTS[package['source']][0])
            if package['source']=='MDR':
                preserve('attributes.src','before-history')
                stage('append-history-attributes','append_atn.pl')
            else:
                for name in ['classes_atoms.src','attributes.src','relationships.src','mergefacts.src']:preserve(name,'before-cleanup')
                stage('remove-duplicate-relationships','remove_dup_rels.pl');replace('relationships_no_dups_no_self_refs.tmp','relationships.src')
                stage('remove-duplicate-atoms-and-merges','remove_dup_classes.pl');replace('classes_unique.txt','classes_atoms.src');replace('mergefacts_new.txt','mergefacts.src')
                stage('remove-duplicate-attributes','remove_dup_attributes.pl');replace('attributes_unique.txt','attributes.src')
            state.update(status='comparing',conversion_completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat());state_save()
            result=comparison.compare(package,target,run)
            verify_inputs(package,target)
            for name,item in result['files'].items():require(target/'src'/name,item['candidate']['sha256'])
            result={'source':package['source'],'version':package['version'],'engine_ref':package['engine_ref'],'run_id':package['run_id'],
                    'stages':stages,'preserved_stage_outputs':snapshots,'comparison':result,'acceptance':result['acceptance'],
                    'input_engine_runtime_and_output_hashes_verified_after_run':True,'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'capsule_sha256':package['capsule_sha256'],'apparatus_ref':package['apparatus_ref'],
                    'common_adapter_integration_executed':False,'insertion_executed':False,'production_eligible':False}
            if package.get('case_variant')=='consistent-history-context':
                save(run/'raw-result.json',result);(run/'raw-result.json').chmod(0o400)
                from audit_mdr_corrections import audit
                state.update(status='auditing');state_save()
                reviewed=audit(package,target,run,result);save(run/'correction-audit.json',reviewed)
                result['correction_audit']=reviewed;result['raw_acceptance']=result['acceptance']
                result['acceptance']={'status':reviewed['status'],'raw_official_comparison_status':result['raw_acceptance']['status'],'all_five_exact':False,'independent_checks_passed':True}
                result['runtime_ref']=package['runtime_ref'];result['perl_hash_seed']=package['perl_hash_seed']
                verify_inputs(package,target)
                for name,item in result['comparison']['files'].items():require(target/'src'/name,item['candidate']['sha256'])
            save(run/'result.json',result);state.update(status='complete',acceptance_status=result['acceptance']['status'],completed_at=result['completed_at']);state_save()
            print('RESULT: '+result['acceptance']['status'],flush=True)
    except BaseException as error:
        state.update(status='failed',error=str(error),completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat());state_save()
        traceback.print_exc();raise
