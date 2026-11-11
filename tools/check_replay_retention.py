#!/usr/bin/env python3
"""Exercise duplicate-only cleanup, recovery, admission and failure protection."""
from contextlib import contextmanager
import argparse
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from unittest.mock import patch

import archive_retained_source as storage
import inversion_remote as remote
import inversion_request as request
import inversion_worker as worker
import replay_retention as retention
from replay_process import runtime_lock


def put(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


@contextmanager
def fixture(source_id='NCI'):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        (root / 'sources').mkdir();(root / 'qa/replay-requests').mkdir(parents=True)
        version, run_id = retention.VERSIONS[source_id], 'retention-fixture'
        target = root / 'sources' / version;target.mkdir()
        source = target.with_name(version + '.before-' + run_id);source.mkdir()
        for name in ('native', 'src', 'qa', 'logs', 'empty'):(source / name).mkdir()
        contents = {'native/input.txt': b'preserved publisher input\n', 'native/empty.txt': b'',
                    'src/attributes.src': b'official and accepted bytes\n',
                    'manual.txt': b'unique manual edit\n', 'logs/old.log': b'keep even if in archive\n',
                    'qa/result.json': b'{"old":"evidence"}\n', 'other.txt': b'unique intermediate\n'}
        for name, raw in contents.items():(source / name).write_bytes(raw)
        (source / 'prior-link').symlink_to('../NCI_2026_08D')
        put(source / 'replay-active-run.json', {'status': 'complete', 'run_id': 'earlier-accepted'})
        original = {'source': source_id, 'version': version, 'root_mode': oct(source.stat().st_mode & 0o777),
                    'manifest': worker.manifest(source)}
        original['receipt_sha256'] = retention.digest(original)
        for base, dirs, files in os.walk(source):
            for name in files:
                path=Path(base)/name
                if not path.is_symlink():path.chmod(path.stat().st_mode & 0o555)
        for base, dirs, files in os.walk(source,topdown=False):Path(base).chmod(Path(base).stat().st_mode & 0o555)
        archive = root / 'sources' / (version + '.tgz')
        archive_contents = {name:raw for name,raw in contents.items() if name != 'other.txt'}
        archive_contents['manual.txt'] = b'official bytes before the manual edit\n'
        with tarfile.open(archive, 'w:gz') as out:
            for name, raw in archive_contents.items():
                entry=tarfile.TarInfo(version+'/'+name);entry.size=len(raw);out.addfile(entry,io.BytesIO(raw))
        archive.chmod(0o444)
        control = root / 'qa/replay-requests' / run_id;control.mkdir()
        lock={'artifact_type':'ncimeta-dev-replay-lock','run_id':run_id,
              'request':{'source':source_id,'version':version},
              'modules_b64':{'replay_retention.py':'fixture-marker'},
              'case':{'acquisition':{'archives':[{'archive_path':str(archive),'archive_sha256':storage._file_sha(archive)}]}}}
        lock['lock_sha256']=retention.digest(lock);put(control/'case.lock.json',lock)
        put(control/'previous-source-receipt.json',original)
        put(control/'status.json',{'status':'complete','preserved_source':str(source)})
        (target/'src').mkdir()
        outputs={}
        for number in range(23 if source_id=='MTH' else 5):
            name='attributes.src' if number==0 else 'output'+str(number)+'.src'
            raw=contents['src/attributes.src'] if number==0 else ('output '+str(number)).encode()
            (target/'src'/name).write_bytes(raw);outputs[name]=storage._file_sha(target/'src'/name)
        result={'run_id':run_id,'lock_sha256':lock['lock_sha256'],'acceptance':{'status':'PASS_EXACT'},
                'comparison':{'files':{name:{'candidate':{'sha256':sha}} for name,sha in outputs.items()}}}
        if source_id in ('MTH','MDR'):
            put(control/'raw-result.json',result)
            audit={'status':'PASS_FIXTURE_AUDIT'};put(control/'correction-audit.json',audit)
            result.update(raw_result_sha256=storage._file_sha(control/'raw-result.json'),correction_audit=audit)
            result['acceptance']={'status':'PASS_REVIEWED_CORRECTIONS','native_derived_correction_audit_passed':True,'raw_comparison_preserved':True}
        elif source_id=='RADLEX':result['acceptance']['status']='PASS_EQUIVALENT'
        put(control/'result.json',result)
        scan=root/'qa/independent-verification.json'
        put(scan,{'status':'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION','run_id':run_id,
                  'lock_sha256':lock['lock_sha256'],'files':outputs})
        args=(run_id,str(scan),storage._file_sha(scan))
        with patch.object(storage,'ROOT',root),patch.object(retention,'ROOT',root),patch.object(worker,'ROOT',root),patch.object(storage,'guard'),patch.object(retention,'_idle'):
            try:yield root,source,target,control,archive,scan,args
            finally:
                for base,dirs,files in os.walk(root):
                    Path(base).chmod(0o700)


def check(include_transport=True):
    checks=[]
    def require(value,label):
        assert value,label
        checks.append(label)
    def rejected(action,label):
        try:action()
        except (ValueError,RuntimeError,FileExistsError,OSError,KeyError,TypeError):checks.append(label)
        else:raise AssertionError(label)
    with fixture() as (root,source,target,control,archive,scan,args):
        before=storage._tree(source)
        report=retention.plan(*args)
        require(storage._tree(source)==before,'Planning never changes source data')
        require(report['duplicate_files']==3,'Only three exact regular archive duplicates selected')
        plan=storage._load(Path(report['plan']))
        require(set(plan['remove'])=={'native/input.txt','native/empty.txt','src/attributes.src'},'Manual edits, unique intermediates, logs, QA and links stay')
        require(not list(root.rglob('tree.tar.gz')),'Planning creates no retention archive')
        rejected(lambda:retention.check_budget(root,target.name),'A full rollback prevents accumulating another')
        with patch.object(worker,'guard'),patch.object(worker,'verify_lock',return_value=target),patch.object(worker,'idle'),patch.object(worker,'runtime'),patch.object(worker,'capacity') as capacity:
            rejected(lambda:worker.launch({'run_id':'second-run','execution_enabled':True}),'Real common launch blocks before acquisition or preparation')
            require(not capacity.called and not (root/'qa/replay-requests/second-run').exists(),'Blocked launch creates no new run or source tree')
        result=retention.compact(report['plan'],report['plan_sha256'])
        require(result['status']=='COMPACTED' and result['new_archive_created'] is False,'Compaction removes duplicates without making another archive')
        require((source/'manual.txt').read_bytes()==b'unique manual edit\n','Manual edits survive compaction unchanged')
        require((source/'logs/old.log').exists() and (source/'qa/result.json').exists(),'Earlier QA and logs survive even with matching archive content')
        require((source/'empty').is_dir() and (source/'prior-link').is_symlink(),'Empty directories and external prior links survive')
        require(not (source/'native/input.txt').exists(),'Archive-backed duplicate is removed')
        require(retention.check_budget(root,target.name)['compacted_runs']==[str(source)],'Verified compacted tree no longer consumes the expanded rollback slot')
        require(worker.retention_budget(target)['admission_available'],'Common worker uses the shared retention admission rule')
        rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Completed compaction is never overwritten')
        destination=target.with_name(target.name+'.before-restored-fixture')
        restored=retention.restore(report['plan'],report['plan_sha256'],destination)
        require(restored['status']=='PASS_RESTORED_TREE_VERIFICATION','Restore verifies every original path, byte, mode, timestamp and link')
        require(storage._tree(destination)[0]==dict(before[0],source_name=destination.name),'Reconstructed tree exactly matches original capture')
        rejected(lambda:retention.restore(report['plan'],report['plan_sha256'],target),'Recovery cannot overwrite the canonical working folder')
        rejected(lambda:retention.check_budget(root,target.name),'A restored full tree is counted again')
    for mutation,label in (
        (lambda root,s,t,c,a,v:put(c/'status.json',{'status':'failed','preserved_source':str(s)}),'Failed current run blocks cleanup'),
        (lambda root,s,t,c,a,v:(t/'src/attributes.src').write_bytes(b'changed'),'Changed accepted output blocks cleanup'),
        (lambda root,s,t,c,a,v:put(c/'previous-source-receipt.json',{}),'Missing/changed predecessor receipt blocks cleanup'),
        (lambda root,s,t,c,a,v:put(c/'case.lock.json',{}),'Changed run lock blocks cleanup'),
        (lambda root,s,t,c,a,v:(a.chmod(0o644),a.write_bytes(b'changed')),'Changed official archive blocks cleanup'),
        (lambda root,s,t,c,a,v:(s.chmod(0o755),(s/'extra').write_bytes(b'unknown')),'Unexpected prior-tree additions block cleanup'),
        (lambda root,s,t,c,a,v:((s/'manual.txt').chmod(0o644),(s/'manual.txt').write_bytes(b'changed')),'Changed manual input blocks cleanup'),
        (lambda root,s,t,c,a,v:((s/'replay-active-run.json').chmod(0o644),put(s/'replay-active-run.json',{'status':'failed'})),'Changed predecessor failure evidence cannot bypass its capture'),
    ):
        with fixture() as values:
            root,s,t,c,a,v,args=values;mutation(root,s,t,c,a,v)
            rejected(lambda:retention.plan(*args),label)
            require((s/'native/input.txt').exists(),label+' leaves input in place')
    for kind in ('pin','archive','evidence','source','hold','durability'):
        with fixture() as (root,s,t,c,a,v,args):
            report=retention.plan(*args)
            if kind=='pin':report['plan_sha256']='0'*64
            elif kind=='archive':a.chmod(0o644);a.write_bytes(b'corrupt archive')
            elif kind=='evidence':put(c/'result.json',{})
            elif kind=='source':(s/'manual.txt').chmod(0o644);(s/'manual.txt').write_bytes(b'manual change after plan')
            elif kind=='hold':
                holds=root/'qa/replay-retention/holds';holds.mkdir();put(holds/(s.name+'.json'),{'reason':'investigate'})
            if kind=='durability':
                with patch.object(storage,'_sync_dir',side_effect=OSError('fsync failed')):
                    rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Failed durability check prevents deletion')
            else:rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Apply rejects changed '+kind)
            require((s/'native/input.txt').exists(),'Preflight failure '+kind+' deletes nothing')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args);original_unlink=os.unlink;removed=[]
        def interrupt(name,*positional,**named):
            if len(removed)==1:raise OSError('interrupted unlink')
            original_unlink(name,*positional,**named);removed.append(name)
        with patch.object(retention.os,'unlink',side_effect=interrupt):
            rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Interrupted cleanup retains its durable plan and remaining files')
        require(len(removed)==1 and (s/'manual.txt').exists(),'Interruption does not affect unique files')
        rejected(lambda:retention.check_budget(root,t.name),'Incomplete compaction cannot bypass admission')
        require(retention.compact(report['plan'],report['plan_sha256'])['status']=='COMPACTED','Cleanup resumes safely from exactly the pinned deletion set')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args);plan_path=Path(report['plan']);plan=storage._load(plan_path)
        storage._save(plan_path.parent/'started.json',{'status':'COMPACTING','plan_sha256':report['plan_sha256']})
        name=next(iter(plan['remove']));parent=s/Path(name).parent
        original_mode=parent.stat().st_mode & 0o777;parent.chmod(original_mode|0o700);(s/name).unlink()
        # State left by a process killed before its permission-restoration finally block.
        result=retention.compact(report['plan'],report['plan_sha256'])
        require(result['status']=='COMPACTED' and parent.stat().st_mode & 0o777==original_mode,'Abrupt-interruption resume restores temporarily writable parent permissions')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args)
        with runtime_lock(root):
            rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Active worker lock prevents cleanup')
        outside=root/'outside';outside.write_bytes(b'keep outside')
        (s/'native').chmod(0o755);(s/'native/input.txt').unlink();(s/'native/input.txt').symlink_to(outside)
        rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'Changed duplicate symlink is never followed or unlinked')
        require(outside.read_bytes()==b'keep outside','External symlink target remains untouched')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args);retention.compact(report['plan'],report['plan_sha256'])
        s.chmod(0o755);(s/'new-unknown-input').write_bytes(b'unknown')
        rejected(lambda:retention.check_budget(root,t.name),'New files in a compacted tree restore the full rollback accounting')
        rejected(lambda:retention.restore(report['plan'],report['plan_sha256'],t.with_name(t.name+'.before-recovery')),'Recovery refuses unknown compacted-tree changes')
    with fixture() as (root,s,t,c,a,v,args):
        other=root/'sources/MTH_2025AB';other.mkdir();(other/'cui_said_map').write_bytes(b'required prior identity')
        report=retention.plan(*args);retention.compact(report['plan'],report['plan_sha256'])
        require((other/'cui_said_map').read_bytes()==b'required prior identity','True prior-version identity inputs are outside cleanup scope')
        rejected(lambda:retention.inventory(root,'MTH_2025AB'),'Unreviewed/prior versions cannot become cleanup targets')
    for source_id in retention.VERSIONS:
        with fixture(source_id) as (root,s,t,c,a,v,args):
            report=retention.plan(*args)
            require(retention.compact(report['plan'],report['plan_sha256'])['status']=='COMPACTED','Shared cleanup handles '+source_id+' acceptance and complete output inventory')
    with fixture('MTH') as (root,s,t,c,a,v,args):
        review=root/'qa/replay-requests/fixture-mth-finalization';review.mkdir()
        for filename in ('result.json','raw-result.json','correction-audit.json'):(c/filename).rename(review/filename)
        result=storage._load(review/'result.json');result.update(review_id=review.name,parent_run_id=args[0],native_conversion_repeated=False)
        put(review/'result.json',result);put(review/'status.json',{'status':'complete'})
        put(c/'status.json',{'status':'failed','preserved_source':str(s),'error':'original common post-check failure'})
        parent_pin=storage._file_sha(c/'status.json')
        scan=storage._load(v)
        row={key:scan[key] for key in ('run_id','lock_sha256')};row.update(outputs_verified=scan['files'],acceptance='PASS_REVIEWED_CORRECTIONS',finalization_review_id=review.name,original_common_run_status='failed')
        put(v,{'status':'PASS_GENERATED_CONFIGURATION_FINAL_VERIFICATION_WITH_FINALIZATION_REVIEW','runs':[row]})
        report=retention.plan(args[0],str(v),storage._file_sha(v));retention.compact(report['plan'],report['plan_sha256'])
        require(storage._file_sha(c/'status.json')==parent_pin,'MTH separate-review cleanup preserves the original failed worker record')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args)
        plan=storage._load(Path(report['plan']));name=next(iter(plan['remove']))
        (s/Path(name).parent).chmod(0o755);(s/name).unlink()
        rejected(lambda:retention.compact(report['plan'],report['plan_sha256']),'An unrecorded missing file cannot masquerade as resumed compaction')
    with fixture() as (root,s,t,c,a,v,args):
        scan=storage._load(v);scan['files'].pop(next(iter(scan['files'])));put(v,scan)
        rejected(lambda:retention.plan(args[0],str(v),storage._file_sha(v)),'Incomplete independent output inventory cannot authorize cleanup')
    with fixture() as (root,s,t,c,a,v,args):
        (t/'live-input').symlink_to(s/'native/input.txt')
        rejected(lambda:retention.plan(*args),'A live source link into the predecessor prevents compaction')
        require((s/'native/input.txt').exists(),'Live dependency remains available at its original path')
    with fixture() as (root,s,t,c,a,v,args):
        lock=storage._load(c/'case.lock.json');lock['case']['required_input']=str(s/'native/input.txt')
        lock['lock_sha256']=retention.digest({key:value for key,value in lock.items() if key!='lock_sha256'})
        put(c/'case.lock.json',lock)
        rejected(lambda:retention.plan(*args),'A declared predecessor-folder input prevents compaction')
    with fixture() as (root,s,t,c,a,v,args):
        active=s/'replay-active-run.json';active_mode=active.stat().st_mode & 0o777
        active.chmod(active_mode|0o200);put(active,{'status':'failed','error':'retain this diagnostic evidence'});active.chmod(active_mode)
        previous=storage._load(c/'previous-source-receipt.json')
        active_identity=next(item for item in worker.manifest(s) if item['path']=='replay-active-run.json')
        for item in previous['manifest']:
            if item['path']=='replay-active-run.json':item.update({key:value for key,value in active_identity.items() if key!='mode'})
        previous['receipt_sha256']=retention.digest({key:value for key,value in previous.items() if key!='receipt_sha256'})
        put(c/'previous-source-receipt.json',previous)
        put(c/'status.json',{'status':'failed','preserved_source':str(s),'error':'current failed test remains failed'})
        status_pin=storage._file_sha(c/'status.json');active_pin=storage._file_sha(active)
        report=retention.plan(args[0]);result=retention.compact(report['plan'],report['plan_sha256'])
        require(result['verification_scope']=='PRESERVATION_ONLY_NO_RUN_ACCEPTANCE','Storage-only cleanup does not claim a failed run passed')
        require(storage._file_sha(c/'status.json')==status_pin and storage._file_sha(active)==active_pin,'Both current and prior failure records remain byte-identical')
        require(retention.check_budget(root,t.name)['admission_available'],'A failed test can be retried after lossless duplicate compaction')
    with fixture() as (root,s,t,c,a,v,args):
        a.chmod(0o644)
        with tarfile.open(a,'w:gz'):pass
        a.chmod(0o444)
        lock=storage._load(c/'case.lock.json');lock['case']['acquisition']['archives'][0]['archive_sha256']=storage._file_sha(a)
        lock['lock_sha256']=retention.digest({key:value for key,value in lock.items() if key!='lock_sha256'});put(c/'case.lock.json',lock)
        before=storage._tree(s)
        report=retention.plan(args[0]);result=retention.compact(report['plan'],report['plan_sha256'])
        require(result['duplicate_files_removed']==0 and storage._tree(s)==before,'A unique-only folder is recorded without deleting data or claiming freed space')
    with fixture() as (root,s,t,c,a,v,args):
        report=retention.plan(*args);retention.compact(report['plan'],report['plan_sha256'])
        old=t.with_name(t.name+'.before-legacy-standalone');old.mkdir();(old/'diagnostic').write_bytes(b'old investigation')
        inventory=retention.check_budget(root,t.name)
        require(inventory['legacy_rollbacks']==[str(old)] and inventory['admission_available'],'Legacy backlog is reported without retroactively blocking the improved runner')
        extra=t.with_name(t.name+'.before-new-policy-extra');extra.mkdir()
        extra_control=root/'qa/replay-requests/new-policy-extra';extra_control.mkdir()
        lock=storage._load(c/'case.lock.json');lock['run_id']='new-policy-extra';lock['lock_sha256']=retention.digest({key:value for key,value in lock.items() if key!='lock_sha256'});put(extra_control/'case.lock.json',lock)
        rejected(lambda:retention.check_budget(root,t.name),'New managed rollbacks still enforce the one-folder limit beside legacy history')
        lock['run_id']='different-run';put(extra_control/'case.lock.json',lock)
        rejected(lambda:retention.inventory(root,t.name),'Corrupted managed control cannot masquerade as legacy history')
    if not include_transport:
        return checks
    # Exercise the actual frozen transport construction with only Git reads substituted for in-progress bytes.
    original_blob=request.blob;ref=request.commit('HEAD')
    def fixture_blob(ref_arg,name):
        return (request.ROOT/name).read_bytes() if ref_arg==ref and name.startswith('tools/') else original_blob(ref_arg,name)
    with patch.object(request,'blob',side_effect=fixture_blob):
        capsule=request.retention_capsule('plan',{'run_id':'fixture-run','verification':'/tmp/scan.json','verification_sha256':'0'*64})
    program=remote.bootstrap_retention(capsule)
    compile(program.split('\n',1)[1].rsplit('\nNCIM_RETENTION',1)[0],'<retention-bootstrap>','exec')
    require('replay_retention.py' in capsule['modules_b64'],'Retention transport freezes executable retention code and dependencies')
    checks.append('Retention bootstrap compiles without shell interpolation of request parameters')
    return checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filesystem-only',action='store_true')
    args=parser.parse_args()
    values=check(include_transport=not args.filesystem_only)
    for value in values:print('PASS',value)
    print(len(values),'retention policy checks passed')
