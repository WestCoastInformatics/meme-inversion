#!/usr/bin/env python3
"""Frozen transport and dev entry points for read-only preparation/review."""
import ast
import base64
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path

import release_manifest as manifests


def verify_planned_links(lock,target):
    for item in lock['plan']['symlinks']:
        manifests._relative(item['relative_path']);path = target/item['relative_path']
        if not path.is_symlink() or os.readlink(path) != item['target']:
            raise ValueError('Frozen native link differs: '+item['relative_path'])
    return len(lock['plan']['symlinks'])


@contextmanager
def operation_record(folder,lock,identity,stage):
    """A failed child operation stays inspectable; parent records are untouched."""
    import inversion_worker as legacy
    folder.mkdir(mode=0o700)
    state={'status':stage,'source':lock['request']['source'],'version':lock['request']['version'],
           'run_id':identity,'parent_run_id':lock['run_id']}
    legacy.save(folder/'status.json',state)
    try:yield
    except BaseException as error:
        state.update(status='failed',error=str(error));legacy.save(folder/'status.json',state);raise


def freeze(operation, parameters, seeds):
    import inversion_request as requests
    ref = requests.commit('HEAD');names = set(seeds)|{'release_operations.py'};pending = list(names)
    available = {p.stem for p in (requests.ROOT/'tools').glob('*.py')}
    while pending:
        name = pending.pop()
        raw = (requests.ROOT/'tools'/name).read_bytes()
        for node in ast.walk(ast.parse(raw)):
            imports = [a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for imported in imports:
                stem = imported.split('.')[0]
                if stem in available and stem+'.py' not in names:
                    names.add(stem+'.py');pending.append(stem+'.py')
    modules = {};provenance = []
    for name in sorted(names):
        path = 'tools/'+name;raw = requests.blob(ref,path)
        if raw != (requests.ROOT/path).read_bytes():raise ValueError('Commit consumed operation code first: '+path)
        modules[name] = base64.b64encode(raw).decode();provenance.append({'repository_path':path,'sha256':hashlib.sha256(raw).hexdigest()})
    value = {'artifact_type':'ncimeta-release-operation', 'operation':operation, 'parameters':parameters,
        'apparatus_ref':ref, 'modules_b64':modules, 'provenance':provenance}
    value['capsule_sha256'] = manifests.digest(value)
    return value


def review_capsule(lock, policy, diagnostic, review_id, qa_decision=None):
    import re
    from native_acceptance import POLICIES
    if policy not in POLICIES:raise ValueError('Unknown reviewed acceptance policy')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,70}',review_id) or review_id == lock['run_id']:
        raise ValueError('A separate safe review identity is required')
    return freeze('review-native',{'lock':lock,'policy':policy,'diagnostic':diagnostic,'review_id':review_id,'qa_decision':qa_decision},
                  {'native_acceptance.py','release_worker.py','explain_native_mth.py','diagnose_native_mth.py','audit_mth_corrections.py'})


def run_review(capsule):
    import json
    import release_worker as worker
    from native_acceptance import evaluate
    from replay_process import runtime_lock
    if capsule['capsule_sha256'] != manifests.digest({k:v for k,v in capsule.items() if k!='capsule_sha256'}):raise ValueError('Review capsule changed')
    worker.legacy.guard();args = capsule['parameters'];lock = args['lock'];target = worker.verify_lock(lock)
    parent = worker.CONTROL/lock['run_id'];folder = worker.CONTROL/args['review_id']
    with runtime_lock(worker.ROOT):
        worker.legacy.idle();worker.legacy.runtime(lock);worker.verify_candidate_inputs(lock,target)
        verify_planned_links(lock,target)
        with manifests._open(parent/'case.lock.json') as handle:parent_lock = json.load(handle)
        if parent_lock != lock:raise ValueError('Parent run has a different frozen lock')
        with manifests._open(parent/'status.json') as handle:state = json.load(handle)
        if state.get('status') != 'complete':raise ValueError('Native conversion must be complete before review')
        with manifests._open(parent/'result.json') as handle:raw = handle.read()
        result = json.loads(raw)
        with operation_record(folder,lock,args['review_id'],'reviewing'):
            review = evaluate(lock,target,result,args['policy'],args['diagnostic'],folder,
                              progress=lambda message:print(message,flush=True),qa_decision=args.get('qa_decision'))
            worker.legacy.runtime(lock)
            links = verify_planned_links(lock,target)
            if (parent/'result.json').read_bytes() != raw:raise ValueError('Original result changed during review')
            review.update(apparatus_ref=capsule['apparatus_ref'],parent_result_sha256=hashlib.sha256(raw).hexdigest(),
                          review_id=args['review_id'],runtime_files_reverified=169,native_links_reverified=links)
            review.pop('review_content_sha256',None);review['review_content_sha256'] = manifests.digest(review)
            with (folder/'acceptance-review.json').open('x') as out:json.dump(review,out,indent=2);out.write('\n')
            (folder/'acceptance-review.json').chmod(0o444)
            worker.legacy.save(folder/'status.json',{'status':'complete','source':lock['configuration']['source'],'version':target.name,
                           'run_id':args['review_id'],'parent_run_id':lock['run_id'],
                           'acceptance':{'status':review['status'],'accepted':review['accepted'],'production_eligible':False}})
    return review
