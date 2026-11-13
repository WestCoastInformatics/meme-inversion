#!/usr/bin/env python3
"""Oracle-free core shadow contract; validation never implies comparison."""
import copy
import importlib
import os
from pathlib import Path

import release_manifest as manifests


def budget(manifest):
    if manifest['purpose'] != 'shadow':return None
    config, artifacts = manifest['configuration'],manifest['artifacts']
    if 'replay' in config or any(a['artifact_type']=='reference-inversion' for a in artifacts.values()):
        raise ValueError('Initial shadow execution must contain no current official reference')
    bounds = config.get('source_atom_ids')
    if not bounds or bounds.get('bound_kind') not in ('dev-reservation','production-reservation','reserved-historical-range'):
        raise ValueError('Shadow execution requires explicit reserved allocation evidence, not emitted bounds')
    environment = artifacts[config['environment_profile']]
    value = environment['data'].get('shadow_resource_budget')
    if (not isinstance(value,dict) or set(value) != {'review_status','review_id','basis','output_bytes','scratch_bytes'} or
            value['review_status']!='reviewed' or any(not isinstance(value[k],str) or not value[k].strip() or
            len(value[k])>4096 or any(ord(c)<32 for c in value[k]) for k in ('review_id','basis')) or
            type(value['output_bytes']) is not int or value['output_bytes']<=0 or
            type(value['scratch_bytes']) is not int or value['scratch_bytes']<0):
        raise ValueError('Shadow execution requires a reviewed explicit output/scratch planning budget')
    return copy.deepcopy(value)


def assess(lock,target):
    if lock['manifest']['purpose']!='shadow':raise ValueError('Oracle-free assessment requires a shadow lock')
    budget(lock['manifest']);target=Path(target);files={};stamps={}
    for name in lock['plan']['output_files']:
        manifests._relative(name);path=target/name
        with manifests._open(path) as handle:
            before=manifests._stamp(os.fstat(handle.fileno()))
            if manifests._stamp(path.lstat())!=before:raise ValueError('Shadow output replaced while opening')
            checksum,size=manifests._hash_stream(handle)
            if manifests._stamp(os.fstat(handle.fileno()))!=before or manifests._stamp(path.lstat())!=before:raise ValueError('Shadow output changed during hashing')
        files[name]={'candidate':{'sha256':checksum,'bytes':size},'reference':None,'exact_match':None}
        stamps[name]=before
    validation=importlib.import_module(lock['profile']['handler']).validate_outputs(lock['plan'],target)
    if any(manifests._stamp((target/name).lstat())!=before for name,before in stamps.items()):
        raise ValueError('Shadow output set changed during validation')
    resources=budget(lock['manifest']);total=sum(x['candidate']['bytes'] for x in files.values())
    within=total<=resources['output_bytes']
    passed=validation['passed'] and within
    return {'files':files,'validation':validation,'comparison_status':'PENDING_OFFICIAL_REFERENCE',
        'output_budget':{'declared_bytes':resources['output_bytes'],'observed_bytes':total,'within_budget':within},
        'acceptance':{'status':'SHADOW_VALIDATED_COMPARISON_PENDING' if passed else 'SHADOW_VALIDATION_FAILED',
                      'accepted':False,'comparison_complete':False,'production_eligible':False,
                      'historical_correction_waivers_applied':False}}
