#!/usr/bin/env python3
"""End-to-end common acceptance of a disposable reviewed NCIt QA view."""
from contextlib import contextmanager
import copy
import json
from unittest.mock import patch

import apply_native_nci_qa as qa
import check_apply_native_nci_qa as fixtures
import native_acceptance as acceptance
import release_operations as operations


@contextmanager
def fixture(change=None):
    """Yield lock,target,result,decision,scratch with complete native stages."""
    with fixtures.fixture(change) as values:
        lock,target,result,decision,scratch=values
        lock['source_profile']='nci-publisher-inputs-v1'
        result['stages']=[{'stage':x['name'],'exit_status':0} for x in lock['plan']['stages']]
        fixtures.reseal(lock,result,decision)
        yield values


def evaluate(args,policy='nci-reviewed-qa-v1',decision=True):
    lock,target,result,qa_decision,scratch=args
    return acceptance.evaluate(lock,target,result,policy,scratch_parent=scratch,
                               qa_decision=qa_decision if decision else None)


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label):
        try:action()
        except (ValueError,RuntimeError,KeyError,OSError):checks.append(label);return
        raise AssertionError(label)
    with fixture() as args:
        raw=copy.deepcopy(args[2]);decision=copy.deepcopy(args[3]);before={str(p):(p.read_bytes(),p.stat().st_mode) for p in args[1].rglob('*') if p.is_file()}
        review=evaluate(args)
        good(review['accepted'] and review['status']=='PASS_WITH_REVIEWED_QA','common policy accepts complete reviewed QA-view proof')
        good(not raw['comparison']['validation']['passed'] and review['proof']['post_qa_validation']['passed'],'failed raw validation remains distinct from clean post-QA validation')
        good(review['raw_acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW' and args[2]==raw and args[3]==decision,'original strict comparison, failed validation and reviewed decision remain unchanged')
        good(review['accepted_output_stage']=='temporary-post-inversion-QA-view' and not review['persistent_application_authorized'],'acceptance scope explicitly excludes persistent native application')
        good(review['exact_outputs']==2 and review['compared_outputs']==5,'original five-file raw comparison counts are preserved')
        good(not review['raw_comparison_changed'] and not review['native_data_modified'] and not review['production_eligible'] and not review['inversion_executed'],'review grants no raw-data mutation, production or inversion authority')
        good(before=={str(p):(p.read_bytes(),p.stat().st_mode) for p in args[1].rglob('*') if p.is_file()} and not list(args[4].iterdir()),'actual common evaluation preserves raw files/modes and removes QA scratch')
        value=copy.deepcopy(review);signature=value.pop('review_content_sha256');good(signature==qa.manifests.digest(value),'separate accepted review has a complete content digest')
        unaccepted=evaluate(args,'exact-v1')
        good(not unaccepted['accepted'] and unaccepted['status']=='REVIEW_REQUIRED','exact policy still refuses original failed raw validation')
        reject(lambda:evaluate(args,decision=False),'QA policy requires explicit reviewed decision')
        reject(lambda:evaluate(args,'mth-retained-identity-v1'),'MTH correction policy cannot accept NCIt output')
    for label,alter in [
        ('proposed QA decision remains rejected',lambda l,t,r,d,s:d.update(review_status='proposed')),
        ('false declared-input integrity blocks QA acceptance',lambda l,t,r,d,s:r.update(declared_inputs_unchanged=False)),
        ('failed native stage blocks QA acceptance',lambda l,t,r,d,s:r['stages'][0].update(exit_status=1)),
        ('forged exact flag blocks QA acceptance',lambda l,t,r,d,s:r['comparison']['files'][qa.CLASS].update(exact_match=True)),
    ]:
        with fixture() as args:
            alter(*args);reject(lambda:evaluate(args),label)
    with fixture() as args:
        lock,target,result,decision,scratch=args;lock['source_profile']='mth-prepared-inputs-v1';fixtures.reseal(lock,result,decision)
        reject(lambda:evaluate(args),'unreviewed NCIt source capability cannot use QA policy')
    with fixture() as args:
        lock,target,result,decision,scratch=args;lock['configuration']['source']='MTH';result['source']='MTH';fixtures.reseal(lock,result,decision)
        reject(lambda:evaluate(args),'cross-source request cannot use NCIt QA policy')
    def invalid_digest(rows,reference,plan,manifest):rows['src/attributes.src']=rows['src/attributes.src'].replace(b'|Alpha|',b'|Different|')
    with fixture(invalid_digest) as args:reject(lambda:evaluate(args),'real invalid post-QA attribute digest cannot bypass raw validation guard')
    with fixture() as args:
        lock,target,result,decision,scratch=args;decision['bindings']['qa_member_sha256']='0'*64
        reject(lambda:evaluate(args),'review status alone cannot approve unbound QA evidence')
    for label,alter in [
        ('false helper post-QA validation cannot be accepted',lambda proof:proof['post_qa_validation'].update(passed=False)),
        ('false helper complete-proof flag cannot be accepted',lambda proof:proof.update(passed=False)),
        ('helper native mutation flag cannot be accepted',lambda proof:proof.update(native_data_modified=True)),
        ('helper raw comparison mutation flag cannot be accepted',lambda proof:proof.update(raw_comparison_changed=True)),
        ('helper retained scratch flag cannot be accepted',lambda proof:proof.update(scratch_removed=False)),
    ]:
        with fixture() as args:
            proof={'passed':True,'post_qa_validation':{'passed':True},'scratch_removed':True,'native_data_modified':False,'raw_comparison_changed':False}
            alter(proof)
            with patch.object(qa,'apply_and_validate',return_value=proof):reject(lambda:evaluate(args),label)
    with fixture() as args:
        seen={}
        def freeze(operation,parameters,seeds):seen.update(operation=operation,parameters=parameters,seeds=seeds);return seen
        with patch.object(operations,'freeze',side_effect=freeze):
            capsule=operations.review_capsule(args[0],'nci-reviewed-qa-v1',None,'separate-nci-review',qa_decision=args[3])
        good(capsule['operation']=='review-native' and capsule['parameters']['qa_decision']==args[3] and capsule['parameters']['policy']=='nci-reviewed-qa-v1','common review transport preserves exact reviewed QA decision and selected policy')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
