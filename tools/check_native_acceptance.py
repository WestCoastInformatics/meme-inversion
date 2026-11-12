#!/usr/bin/env python3
"""Confined end-to-end proofs and rejection cases for separate acceptance."""
import copy
import json
from pathlib import Path
import tempfile

import check_explain_native_mth as fixture
import diagnose_native_mth as diagnostic
import native_acceptance as acceptance


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
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
