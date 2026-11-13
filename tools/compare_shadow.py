#!/usr/bin/env python3
"""Attach a current official reference after an immutable shadow execution."""
import copy
import json
import hashlib
import re
import shutil
from pathlib import Path

import release_manifest as manifests


def validate_reference(lock,reference):
    config=lock['configuration'];files=reference.get('files',[])
    if (lock['manifest']['purpose']!='shadow' or
            (reference.get('artifact_type'),reference.get('source'),reference.get('version'),reference.get('data',{}).get('reference_stage')) !=
            ('reference-inversion',config['source'],config['version'],'inversion-src') or
            reference.get('provenance',{}).get('evidence_kind')=='synthetic-fixture' or
            len(files)!=len(lock['plan']['output_files']) or {x.get('role') for x in files}!=set(lock['plan']['output_files'])):
        raise ValueError('Late reference must cover the exact current shadow source/version and pre-insertion outputs')
    for item in files:
        manifests._relative(item['role']);manifests.location(item,False)
        if type(item.get('bytes')) is not int or item['bytes']<0 or not re.fullmatch('[0-9a-f]{64}',item.get('sha256','')):
            raise ValueError('Late reference requires exact byte counts and SHA-256 values')
    from release_execution import verify_locations
    from release_worker import ROOT
    verify_locations({'artifacts':{'late-reference':reference}},ROOT/'sources'/config['version'])


def compare(lock,target,original,reference):
    """Compare after caller has physically verified the bound reference bytes."""
    from shadow_execution import assess
    validate_reference(lock,reference)
    if (original.get('lock_sha256')!=lock['lock_sha256'] or original.get('run_id')!=lock['run_id'] or
            original.get('comparison',{}).get('comparison_status')!='PENDING_OFFICIAL_REFERENCE' or
            original.get('acceptance',{}).get('comparison_complete') is not False):
        raise ValueError('Original completed shadow result required')
    current=json.loads(json.dumps(assess(lock,target)))
    if original['comparison']!={k:v for k,v in current.items() if k!='acceptance'} or original['acceptance']!=current['acceptance']:
        raise ValueError('Shadow output or validation changed since completion')
    rows={x['role']:x for x in reference['files']};files={}
    for name,item in current['files'].items():
        expected={k:rows[name][k] for k in ('sha256','bytes')};actual=item['candidate']
        files[name]={'candidate':actual,'reference':expected,'exact_match':actual==expected}
    passed=current['validation']['passed'] and current['output_budget']['within_budget'] and all(x['exact_match'] for x in files.values())
    return {'schema_version':1,'artifact_type':'ncimeta-shadow-comparison','source':lock['request']['source'],
        'version':lock['request']['version'],'parent_run_id':lock['run_id'],'lock_sha256':lock['lock_sha256'],
        'reference_artifact_sha256':manifests.digest(reference),'comparison':{'files':files,'validation':current['validation']},
        'comparison_complete':True,'status':'PASS_EXACT' if passed else 'DIFFERENCES_REQUIRE_REVIEW',
        'accepted':passed,'production_eligible':False,'reference_attached_after_execution':True,
        'original_shadow_result_changed':False,'native_inversion_repeated':False,'source_data_changed':False}


def capsule(lock,reference,comparison_id):
    from release_operations import freeze
    validate_reference(lock,reference)
    schema=manifests.load(manifests.DOCS/'release-manifest.schema.json')
    errors=manifests.schema_errors(reference,{'$schema':schema['$schema'],'$defs':schema['$defs'],'$ref':'#/$defs/artifact'})
    if errors:raise ValueError('Invalid late reference: '+errors[0]['message'])
    if not re.fullmatch('[a-z0-9][a-z0-9-]{1,70}',comparison_id) or comparison_id==lock['run_id']:
        raise ValueError('Separate comparison identity required')
    return freeze('compare-shadow',{'lock':lock,'reference':reference,'comparison_id':comparison_id},
                  {'compare_shadow.py','release_worker.py','shadow_execution.py'})


def run(capsule):
    import release_worker as worker
    from release_operations import verify_planned_links,operation_record
    from replay_process import runtime_lock
    if capsule['capsule_sha256']!=manifests.digest({k:v for k,v in capsule.items() if k!='capsule_sha256'}):raise ValueError('Late-comparison capsule changed')
    worker.legacy.guard();args=capsule['parameters'];lock=args['lock'];reference=args['reference']
    target=worker.verify_lock(lock);validate_reference(lock,reference)
    parent=worker.CONTROL/lock['run_id'];folder=worker.CONTROL/args['comparison_id']
    with runtime_lock(worker.ROOT):
        worker.legacy.idle();worker.legacy.runtime(lock);worker.verify_candidate_inputs(lock,target);verify_planned_links(lock,target)
        with manifests._open(parent/'case.lock.json') as h:
            if json.load(h)!=lock:raise ValueError('Original shadow lock differs')
        with manifests._open(parent/'status.json') as h:
            if json.load(h).get('status')!='complete':raise ValueError('Shadow conversion must complete before comparison')
        with manifests._open(parent/'result.json') as h:raw=h.read()
        original=json.loads(raw)
        with operation_record(folder,lock,args['comparison_id'],'comparing-reference'):
            # Reuse the existing reviewed archive downloader and physical verifier.
            # The derived object is acquisition-only, never a new execution lock.
            acquisition={'request':lock['request'],'profile':lock['profile'],'manifest':{'artifacts':{'late-reference':reference}}}
            missing={}
            for item in reference['files']:
                path=worker._local(item)
                if path.exists():continue
                size=item.get('archive_bytes',item['bytes'])
                if str(path) in missing and missing[str(path)]!=size:raise ValueError('Conflicting late archive byte counts')
                missing[str(path)]=size
            if shutil.disk_usage(worker.ROOT).free<12*1024**3+sum(missing.values()):raise ValueError('Late-reference acquisition reserve unavailable')
            verified=worker.acquire_and_verify(acquisition,folder)
            report=compare(lock,target,original,reference)
            if any(list(manifests._stamp(Path(x['local_path']).lstat()))!=x['snapshot'] for x in verified):raise ValueError('Official reference changed during comparison')
            worker.verify_candidate_inputs(lock,target);worker.legacy.runtime(lock);links=verify_planned_links(lock,target)
            if (parent/'result.json').read_bytes()!=raw:raise ValueError('Original shadow result changed')
            report.update(apparatus_ref=capsule['apparatus_ref'],comparison_id=args['comparison_id'],parent_result_sha256=hashlib.sha256(raw).hexdigest(),
                          reference_files_verified=len(verified),runtime_files_verified=169,native_links_verified=links)
            report['report_sha256']=manifests.digest(report)
            with (folder/'shadow-comparison.json').open('x') as h:json.dump(report,h,indent=2);h.write('\n')
            (folder/'shadow-comparison.json').chmod(0o444)
            worker.legacy.save(folder/'status.json',{'status':'complete','source':report['source'],'version':report['version'],'run_id':args['comparison_id'],
                           'parent_run_id':lock['run_id'],'acceptance':{'status':report['status'],'accepted':report['accepted'],'production_eligible':False}})
    return report
