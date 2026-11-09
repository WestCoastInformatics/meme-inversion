#!/usr/bin/env python3
"""Recheck both complete MDR runs, retained files and restored runtime on dev."""
import argparse
import hashlib
import json
import re

import replay_framework_core as replay
from replay_process import runtime_lock


def verify(first_run,second_run):
    if first_run==second_run or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}',value) for value in [first_run,second_run]):raise ValueError('Two distinct valid run identities are required')
    root=replay.ROOT;control=root/'qa/replay-requests';packages=[];results=[]
    with runtime_lock(root):
        from replay_mth_core import idle
        idle()
        for run_id in [first_run,second_run]:
            run=control/run_id;package=json.loads((run/'characterization.lock.json').read_text());replay.verify_capsule(package)
            result=json.loads((run/'result.json').read_text());state=json.loads((run/'status.json').read_text())
            if package.get('case_variant')!='consistent-history-context' or state['status']!='complete' or result['acceptance']['status']!='PASS_REVIEWED_CORRECTIONS':raise RuntimeError('Both corrected runs must have completed acceptance')
            if result['run_id']!=run_id or result['capsule_sha256']!=package['capsule_sha256']:raise RuntimeError('Result/capsule identity differs')
            if result['correction_audit']['expected_attribute_sha256']!=result['comparison']['files']['attributes.src']['candidate']['sha256']:raise RuntimeError('Complete expected attribute prediction differs')
            known={'SRC_ATOM_ID','SOURCE_DUI','SOURCE_CUI','SOURCE_AUI','ROOT_SOURCE_AUI','CODE_SOURCE','CODE_TERMGROUP','SRC_REL_ID'}
            if any(set(item['identifier_types'])-known for item in result['comparison']['structure']['candidate']['files'].values()):raise RuntimeError('Unreviewed generated-attribute-ID reference dependency')
            packages.append(package);results.append(result)
        if packages[0]['perl_hash_seed']==packages[1]['perl_hash_seed']:raise RuntimeError('Different hash seeds are required')
        for key in ['engine_ref','runtime_ref','input_files','code_files','runtime_files','archive_sha256','apparatus_sha256']:
            if packages[0][key]!=packages[1][key]:raise RuntimeError('Repeatability inputs/code/runtime differ: '+key)
        current=root/'sources/MDR_29_1';retained=current.with_name(current.name+'.before-'+second_run)
        if retained.stat().st_mode&0o222:raise RuntimeError('First run must remain read-only')
        outputs={}
        for path,package,result in zip([retained,current],packages,results):
            for item in package['input_files']+package['code_files']:replay.require(path/item['relative_path'],item['sha256'])
            for name,item in result['comparison']['files'].items():
                actual=replay.comparison.file_info(path/'src'/name)
                if actual!=item['candidate']:raise RuntimeError('Retained/current output changed: '+name)
                if name in outputs and outputs[name]!=actual:raise RuntimeError('Full-run output bytes differ: '+name)
                outputs[name]=actual
        if set(outputs)!=set(replay.comparison.OUTPUTS):raise RuntimeError('All five outputs are required')
        for item in packages[0]['prior_runtime_files']:replay.require(root/item['relative_path'],item['sha256'])
        replay.require(root/'sources/MDR_29_1.tgz',packages[0]['archive_sha256'])
        failed=packages[0]['previous_source_receipt']
        original=json.loads((control/failed['previous_run_id']/'characterization.lock.json').read_text())
        predecessor=original['previous_source_receipt'];baseline=control/predecessor['previous_run_id']/'result.json';replay.require(baseline,predecessor['previous_result_sha256'])
        if json.loads(baseline.read_text())['acceptance']['status']!='DIFFERENCES_REQUIRE_REVIEW':raise RuntimeError('Original raw baseline verdict changed')
        record=failed['previous_control_record'];replay.require(control/failed['previous_run_id']/record['filename'],record['sha256'])
        return {'status':'PASS_FULL_VERIFICATION','source':'MDR','version':'MDR_29_1','run_ids':[first_run,second_run],
                'hash_seeds':[x['perl_hash_seed'] for x in packages],'engine_ref':packages[0]['engine_ref'],'runtime_ref_during_runs':packages[0]['runtime_ref'],
                'execution_apparatus_refs':[x['apparatus_ref'] for x in packages],
                'all_five_byte_identical_between_fresh_runs':True,'files':outputs,'input_and_code_hashes_rechecked_in_both_trees':True,
                'generated_attribute_id_reference_dependencies':False,'original_baseline_and_failed_attempt_unchanged':True,
                'restored_runtime_ref':packages[0]['prior_runtime_ref'],'restored_runtime_files_verified':len(packages[0]['prior_runtime_files']),
                'production_eligible':False,'insertion_executed':False,'scope':'Bounded MDR_29_1 corrected core replay; common-adapter integration and production release remain separate.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('first_run');parser.add_argument('second_run');args=parser.parse_args()
    print(json.dumps(verify(args.first_run,args.second_run),indent=2))
