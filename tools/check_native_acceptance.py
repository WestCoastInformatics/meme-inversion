#!/usr/bin/env python3
"""Confined end-to-end proofs and rejection cases for separate acceptance."""
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import check_explain_native_mth as fixture
import diagnose_native_mth as diagnostic
import native_acceptance as acceptance
from release_operations import verify_planned_links


def check():
    checks = []
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label):
        try:action()
        except (ValueError,RuntimeError,KeyError):checks.append(label);return
        raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='native-acceptance-') as temporary:
        lock,target,result,report,scratch = fixture.fixture(Path(temporary).resolve())
        lock['source_profile']='mth-prepared-inputs-v1';lock['configuration']['replay']['comparison_profile']='exact'
        lock['plan']['stages']=[{'name':'fixture-native-stage'}]
        lock['manifest_sha256']=diagnostic.digest(lock['manifest']);lock['plan_sha256']=diagnostic.digest(lock['plan'])
        lock['lock_sha256']=diagnostic.digest({k:v for k,v in lock.items() if k!='lock_sha256'})
        result.update(lock_sha256=lock['lock_sha256'],stages=[{'exit_status':0}],declared_inputs_unchanged=True,
                      insertion_executed=False,production_eligible=False)
        report=diagnostic.diagnose(lock,target,result,examples=5)
        original=copy.deepcopy(result);before={str(p):p.read_bytes() for p in target.rglob('*') if p.is_file()}
        proof=acceptance.evaluate(lock,target,result,'mth-retained-identity-v1',report,scratch)
        good(proof['status']=='PASS_WITH_VERIFIED_CORRECTIONS' and proof['accepted'],'complete native-derived proof produces separate corrected acceptance')
        good(proof['raw_acceptance']==original['acceptance'] and result==original,'original strict DIFF remains unchanged')
        good(proof['compared_outputs']==23 and proof['exact_outputs']==14 and proof['proof']['every_difference_explained'],'full23output scope retained')
        good({str(p):p.read_bytes() for p in target.rglob('*') if p.is_file()}==before and not list(scratch.iterdir()),'native data unchanged and scratch removed')
        good(not proof['production_eligible'] and not proof['inversion_executed'],'acceptance grants no production or insertion')
        reject(lambda:acceptance.evaluate(lock,target,result,'exact-v1'),'exact profile cannot waive corrections')
        reject(lambda:acceptance.evaluate(lock,target,result,'anything'),'unknown policy rejected')
        reject(lambda:acceptance.evaluate(lock,target,result,'mth-retained-identity-v1'),'missing complete correction proof rejected')
        bad=copy.deepcopy(result);bad['declared_inputs_unchanged']=False
        reject(lambda:acceptance.evaluate(lock,target,bad,'mth-retained-identity-v1',report,scratch),'changed declared inputs rejected')
        bad=copy.deepcopy(result);bad['stages'][0]['exit_status']=1
        reject(lambda:acceptance.evaluate(lock,target,bad,'mth-retained-identity-v1',report,scratch),'failed native stage rejected')
        bad=copy.deepcopy(result);bad['comparison']['validation']['passed']=False
        review=acceptance.evaluate(lock,target,bad,'mth-retained-identity-v1',report,scratch)
        good(review['status']=='REVIEW_REQUIRED' and not review['accepted'],'validation failure cannot become accepted correction')
        bad=copy.deepcopy(result);bad['comparison']['files']['src/classes_atoms.src']['exact_match']=False
        reject(lambda:acceptance.evaluate(lock,target,bad,'mth-retained-identity-v1',report,scratch),'forged exact status rejected')
        path=target/'src/classes_atoms.src';raw=path.read_bytes();path.write_bytes(raw+b'wrong\n')
        reject(lambda:acceptance.evaluate(lock,target,result,'mth-retained-identity-v1',report,scratch),'retained byte mutation rejected despite saved proof')
        path.write_bytes(raw)
        bad=copy.deepcopy(report);bad['files']['src/cui_said_map']['row_multiset']['candidate_only_examples']=[]
        reject(lambda:acceptance.evaluate(lock,target,result,'mth-retained-identity-v1',bad,scratch),'incomplete native map evidence rejected')
        exact_lock=copy.deepcopy(lock);exact_result=copy.deepcopy(result)
        for item in exact_lock['manifest']['artifacts']['official']['files']:
            item.update(exact_result['comparison']['files'][item['role']]['candidate'])
        for item in exact_result['comparison']['files'].values():
            item['reference']=copy.deepcopy(item['candidate']);item['exact_match']=True
        exact_lock['manifest_sha256']=diagnostic.digest(exact_lock['manifest'])
        exact_lock['lock_sha256']=diagnostic.digest({k:v for k,v in exact_lock.items() if k!='lock_sha256'})
        exact_result['lock_sha256']=exact_lock['lock_sha256'];exact_result['acceptance']['status']='PASS_EXACT'
        good(acceptance.evaluate(exact_lock,target,exact_result,'exact-v1')['status']=='PASS_EXACT','exact policy hashes every retained fixture output')
        original_open=acceptance.manifests._open;path=target/'src/classes_atoms.src';before=path.read_bytes()
        def changing_open(p):
            if p==target/'src/attributes.src':path.write_bytes(before+b'changed\n')
            return original_open(p)
        with patch.object(acceptance.manifests,'_open',side_effect=changing_open):
            reject(lambda:acceptance.evaluate(exact_lock,target,exact_result,'exact-v1'),'later edit of previously verified output rejected by whole-set final check')
        path.write_bytes(before)
        links={'plan':{'symlinks':[{'relative_path':'declared-old','target':'orig/identity/PRIOR'}]}}
        alias=target/'declared-old';alias.symlink_to('orig/identity/PRIOR')
        good(verify_planned_links(links,target)==1,'frozen native link text verified independently of direct input hashes')
        alias.unlink();alias.symlink_to('different-prior')
        reject(lambda:verify_planned_links(links,target),'changed old or Meta link cannot pass retained acceptance')
        alias.unlink();alias.write_text('ordinary file')
        reject(lambda:verify_planned_links(links,target),'regular file cannot substitute for a planned symlink')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
