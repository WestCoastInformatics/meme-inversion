#!/usr/bin/env python3
"""Separate acceptance review of completed native output; preserve raw results."""
import copy
import hashlib
import os
from pathlib import Path

import release_manifest as manifests

POLICIES = {
    'exact-v1': {'source':None, 'method':'exact'},
    'mth-retained-identity-v1': {'source':'MTH', 'method':'native-derived-retained-identity'},
}


def require(value, message):
    if not value:raise ValueError(message)


def evaluate(lock, target, result, policy, diagnostic=None, scratch_parent=None, progress=lambda message:None):
    if 'records' in result:result = result['records']['result.json']
    require(policy in POLICIES, 'Unknown reviewed acceptance policy')
    require(lock.get('artifact_type') == 'ncimeta-native-release-lock' and
            lock.get('lock_sha256') == manifests.digest({k:v for k,v in lock.items() if k != 'lock_sha256'}), 'Frozen native lock differs')
    config = lock['configuration'];target = Path(target)
    require(target.name == config['version'] and lock['manifest']['configuration'] == config and
            lock['manifest_sha256'] == manifests.digest(lock['manifest']) and
            lock['plan_sha256'] == manifests.digest(lock['plan']), 'Frozen source/manifest/plan differs')
    require((result['source'],result['version'],result['run_id'],result['lock_sha256']) ==
            (config['source'],config['version'],lock['run_id'],lock['lock_sha256']), 'Completed result belongs to another request')
    require(POLICIES[policy]['source'] in (None,config['source']), 'Acceptance policy belongs to another source')
    require(result.get('declared_inputs_unchanged') is True and result.get('insertion_executed') is False and
            result.get('production_eligible') is False, 'Input integrity or dev-only execution facts missing')
    require(result.get('stages') and len(result['stages']) == len(lock['plan']['stages']) and
            all(item['exit_status'] == 0 for item in result['stages']), 'All declared native stages must complete successfully')
    reference = lock['manifest']['artifacts'][config['replay']['reference_ref']]
    require((reference['artifact_type'],reference['source'],reference['version'],reference['data'].get('reference_stage')) ==
            ('reference-inversion',config['source'],config['version'],'inversion-src'), 'Current pre-insertion official reference required')
    expected = {item['role']:item for item in reference['files']};files = result['comparison']['files']
    require(set(expected) == set(files) == set(lock['plan']['output_files']), 'Complete output coverage required')
    for name,item in files.items():
        manifests._relative(name)
        require(all(item['reference'][key] == expected[name][key] for key in ('sha256','bytes')), 'Official reference descriptor differs')
        exact = all(item['candidate'][key] == item['reference'][key] for key in ('sha256','bytes'))
        require(type(item['exact_match']) is bool and item['exact_match'] == exact, 'Exact-match flag differs from hashes')
    review = {'schema_version':1, 'artifact_type':'ncimeta-native-acceptance-review',
        'source':config['source'], 'version':config['version'], 'run_id':lock['run_id'], 'lock_sha256':lock['lock_sha256'],
        'policy':policy, 'raw_result_content_sha256':manifests.digest(result), 'raw_acceptance':copy.deepcopy(result['acceptance']),
        'raw_comparison_changed':False, 'native_data_modified':False, 'inversion_executed':False,
        'production_eligible':False, 'issues':[], 'status':'REVIEW_REQUIRED', 'accepted':False,
        'exact_outputs':sum(item['exact_match'] for item in files.values()), 'compared_outputs':len(files),
        'scope':'Acceptance of this preserved-input dev inversion only; operational preparation, QA and insertion remain separate gates.'}
    if not result['comparison']['validation']['passed']:
        review['issues'].append({'code':'OUTPUT_VALIDATION_FAILED','message':'Resolve the recorded source/QA findings before acceptance.'})
        review['review_content_sha256'] = manifests.digest(review)
        return review
    if policy == 'exact-v1':
        require(all(item['exact_match'] for item in files.values()) and result['acceptance']['status'] == 'PASS_EXACT', 'Exact policy cannot accept differences')
        for name,item in files.items():
            with manifests._open(target/name) as handle:
                before = manifests._stamp(os.fstat(handle.fileno()))
                actual = manifests._hash_stream(handle)
                require(actual == (item['candidate']['sha256'],item['candidate']['bytes']), 'Retained output changed')
                require(manifests._stamp(os.fstat(handle.fileno())) == before == manifests._stamp((target/name).lstat()), 'Retained output changed during review')
        review.update(status='PASS_EXACT',accepted=True)
    else:
        require(lock['source_profile'] == 'mth-prepared-inputs-v1' and config['replay']['comparison_profile'] == 'exact', 'Unreviewed MTH native capability')
        require(diagnostic is not None and scratch_parent is not None, 'Full MTH diagnostic and external scratch parent required')
        from explain_native_mth import explain
        proof = explain(lock,target,result,diagnostic,scratch_parent,progress=progress)
        require(proof['every_difference_explained'] and proof['scratch_removed'] and not proof['acceptance_changed'] and
                not proof['native_data_modified'], 'Incomplete correction proof')
        review.update(status='PASS_WITH_VERIFIED_CORRECTIONS',accepted=True,proof=proof)
    review['review_content_sha256'] = manifests.digest(review)
    return review
