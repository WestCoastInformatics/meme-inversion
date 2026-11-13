#!/usr/bin/env python3
"""Oracle-free worker lifecycle and later comparison, with conversion mocked."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import check_release_execution as fixtures
import compare_shadow as later
import release_worker as worker
import shadow_execution as shadow


def prepare(lock,run,path):
    reference=lock['manifest']['artifacts'].pop('official')
    lock['manifest']['purpose']='shadow';lock['configuration'].pop('replay')
    lock['manifest']['artifacts'][lock['configuration']['environment_profile']]['data']['shadow_resource_budget']={
        'review_status':'reviewed','review_id':'tiny-shadow-fixture','basis':'Complete tiny native inputs and bounded fixture outputs',
        'output_bytes':16*1024**2,'scratch_bytes':32*1024**2}
    lock['plan']=fixtures.nci.build_plan(lock['configuration'],lock['manifest']['artifacts'],lock['code_files'])
    fixtures.seal(lock);path.write_text(json.dumps(lock));return reference


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label):
        try:action()
        except (ValueError,RuntimeError,OSError,KeyError):checks.append(label);return
        raise AssertionError(label)
    with fixtures.fixture('NCI_2027_02B','NCI_2026_12C') as (lock,root,run,path,gold):
        reference=prepare(lock,run,path);target=root/'sources'/lock['request']['version']
        good(worker.verify_lock(lock)==target,'complete frozen shadow lock admits no replay/reference artifact')
        good('replay' not in lock['configuration'] and not any(x['artifact_type']=='reference-inversion' for x in lock['manifest']['artifacts'].values()),'all current official dependencies absent')
        for change,label in [(lambda m:m['artifacts'][m['configuration']['environment_profile']]['data'].pop('shadow_resource_budget'),'missing reviewed resource budget rejected'),
                             (lambda m:m['artifacts'][m['configuration']['environment_profile']]['data']['shadow_resource_budget'].update(output_bytes=True),'boolean output estimate rejected'),
                             (lambda m:m['artifacts'][m['configuration']['environment_profile']]['data']['shadow_resource_budget'].update(review_status='proposed'),'proposed budget rejected'),
                             (lambda m:m['configuration']['source_atom_ids'].update(bound_kind='historical-emitted-range'),'unreserved emitted bounds cannot authorize shadow'),
                             (lambda m:m['configuration'].update(replay={'reference_ref':'late'}),'shadow cannot secretly add replay'),
                             (lambda m:m['artifacts'].update(official=reference),'unused official artifact still prohibited')]:
            bad=copy.deepcopy(lock['manifest']);change(bad);reject(lambda:shadow.budget(bad),label)
        with patch.object(worker,'available_memory',return_value=32*1024**3),patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=128*1024**3)):
            capacity=worker.capacity(lock)
        good(capacity['required_free_bytes']>=18*1024**3,'source capacity floor remains mandatory without oracle sizes')
        large=copy.deepcopy(lock);large['manifest']['artifacts'][large['configuration']['environment_profile']]['data']['shadow_resource_budget']['scratch_bytes']=30*1024**3
        with patch.object(worker,'available_memory',return_value=32*1024**3),patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=128*1024**3)):
            good(worker.capacity(large)['required_free_bytes']>42*1024**3,'explicit scratch/output/materialization reservation adds to12GiB reserve')
        def conversion(argv,**kwargs):
            if argv==lock['plan']['stages'][-1]['argv']:fixtures.nci_fixture.outputs(lock['plan'],target)
            return {'exit_status':0,'network':'disabled','fixture_native_stage':True}
        opened=fixtures.manifests._open
        def no_oracle(p):
            if Path(p).is_relative_to(gold):raise AssertionError('Oracle consumed before official availability')
            return opened(p)
        with patch.object(fixtures.legacy,'guard'),patch.object(fixtures.legacy,'idle'),patch.object(fixtures.legacy,'runtime'),patch.object(worker,'capacity'),patch.object(worker,'execute',side_effect=conversion),patch.object(fixtures.manifests,'_open',side_effect=no_oracle):
            worker.worker(path)
        result=fixtures.manifests.load(run/'result.json');state=fixtures.manifests.load(run/'status.json')
        good(state['status']=='complete' and state['purpose']=='shadow','common lifecycle completes shadow preparation/conversion/validation')
        good(result['acceptance']['status']=='SHADOW_VALIDATED_COMPARISON_PENDING' and not result['acceptance']['accepted'],'clean shadow result remains unaccepted pending official comparison')
        good(all(x['reference'] is None and x['exact_match'] is None for x in result['comparison']['files'].values()),'unknown reference/byte equality are null, never false success')
        raw=(run/'result.json').read_bytes()
        with patch.object(fixtures.legacy,'guard'),patch.object(fixtures.legacy,'idle'),patch.object(fixtures.legacy,'runtime'):
            verified=worker.verify_retained(lock)
        good(verified['status']=='PASS_SHADOW_RETAINED_VERIFICATION' and not verified['comparison_complete'],'fresh independent verification preserves pending comparison semantics')
        changed=target/'src/classes_atoms.src';original=changed.read_bytes();original_open=shadow.manifests._open
        def replaced(p):
            handle=original_open(p)
            if p==changed:
                temporary=p.with_suffix('.atomic');temporary.write_bytes(original);temporary.replace(p)
            return handle
        with patch.object(shadow.manifests,'_open',side_effect=replaced):reject(lambda:shadow.assess(lock,target),'atomic replacement cannot pair stale FD hash with current physical validation')
        changed.write_bytes(original)
        # Existing verified input data remain the shadow constructor. Official
        # output enters only here, after the original result is complete.
        issues=[];rows=fixtures.manifests.verify_files({'late':reference},True,issues);assert not issues and all(x['status']=='VERIFIED' for x in rows)
        compared=later.compare(lock,target,result,reference)
        good(compared['status']=='PASS_EXACT' and compared['comparison_complete'],'later verified current reference yields separate exact verdict')
        cap={'artifact_type':'ncimeta-release-operation','operation':'compare-shadow','apparatus_ref':'2'*40,
             'parameters':{'lock':lock,'reference':reference,'comparison_id':'late-unit-comparison'}}
        cap['capsule_sha256']=fixtures.manifests.digest(cap)
        with patch.object(fixtures.legacy,'guard'),patch.object(fixtures.legacy,'idle'),patch.object(fixtures.legacy,'runtime'),patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=128*1024**3)):
            receipt=later.run(cap)
        good(receipt['parent_result_sha256']==hashlib.sha256(raw).hexdigest() and receipt['reference_files_verified']==5,
             'late child workflow independently verifies reference bytes and binds exact parent result')
        good(fixtures.manifests.load(root/'qa/replay-requests/late-unit-comparison/status.json')['status']=='complete',
             'late child has inspectable completion state')
        badcap=copy.deepcopy(cap);badcap['parameters']['comparison_id']='late-unit-failed';badcap['parameters']['reference']['files'][0]['sha256']='0'*64
        badcap['capsule_sha256']=fixtures.manifests.digest({k:v for k,v in badcap.items() if k!='capsule_sha256'})
        with patch.object(fixtures.legacy,'guard'),patch.object(fixtures.legacy,'idle'),patch.object(fixtures.legacy,'runtime'),patch.object(worker.shutil,'disk_usage',return_value=SimpleNamespace(free=128*1024**3)):
            reject(lambda:later.run(badcap),'bad official bytes cannot create a comparison pass')
        good(fixtures.manifests.load(root/'qa/replay-requests/late-unit-failed/status.json')['status']=='failed',
             'late acquisition or comparison failure records a failed child state')
        conflict=copy.deepcopy(reference);missing=root/'sources'/(lock['request']['version']+'.tgz')
        for number,item in enumerate(conflict['files']):item.update(uri=missing.as_uri(),archive_format='tar.gz',archive_member=lock['request']['version']+'/'+item['role'],archive_sha256='a'*64,archive_bytes=1000+number)
        badcap=copy.deepcopy(cap);badcap['parameters'].update(comparison_id='late-unit-conflict',reference=conflict)
        badcap['capsule_sha256']=fixtures.manifests.digest({k:v for k,v in badcap.items() if k!='capsule_sha256'})
        with patch.object(fixtures.legacy,'guard'),patch.object(fixtures.legacy,'idle'),patch.object(fixtures.legacy,'runtime'),patch.object(worker,'acquire_and_verify',side_effect=AssertionError('No download for conflicting reserve')):
            reject(lambda:later.run(badcap),'conflicting archive sizes rejected before download')
        good((run/'result.json').read_bytes()==raw and result['acceptance']['status']=='SHADOW_VALIDATED_COMPARISON_PENDING','late comparison never rewrites original pending record')
        bad=copy.deepcopy(reference);bad['version']=lock['configuration']['replacement_baseline']['version']
        reject(lambda:later.compare(lock,target,result,bad),'prior release cannot substitute for official current output')
        bad=copy.deepcopy(reference);bad['data']['reference_stage']='insertion-package'
        reject(lambda:later.compare(lock,target,result,bad),'insertion stage cannot stand in for inversion-src')
        bad=copy.deepcopy(reference);bad['files'][0]['uri']=(target/bad['files'][0]['role']).as_uri()
        reject(lambda:later.validate_reference(lock,bad),'candidate cannot become its own late oracle')
        bad=copy.deepcopy(reference);bad['files'].pop()
        reject(lambda:later.compare(lock,target,result,bad),'late reference must cover all outputs exactly')
        bad=copy.deepcopy(reference);bad['files'][0]['sha256']='0'*64
        compared=later.compare(lock,target,result,bad)
        good(compared['status']=='DIFFERENCES_REQUIRE_REVIEW' and not compared['accepted'],'late byte differences stay review-required')
        changed.write_bytes(original+b'wrong\n')
        reject(lambda:later.compare(lock,target,result,reference),'mutated retained candidate cannot be compared as original shadow')
        changed.write_bytes(original)
        small=copy.deepcopy(lock);small['manifest']['artifacts'][small['configuration']['environment_profile']]['data']['shadow_resource_budget']['output_bytes']=1
        good(shadow.assess(small,target)['acceptance']['status']=='SHADOW_VALIDATION_FAILED','exceeded reviewed output estimate cannot be validated')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
