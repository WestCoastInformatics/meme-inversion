#!/usr/bin/env python3
"""Freeze/submit the two reviewed MDR/RADLEX baseline characterization cases."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path

from inversion_remote import remote
from inversion_request import DOCS, MODULES, ROOT, blob, commit, digest, load, validate_module_dependencies, write_new

ENGINE='36f1e10aeadb9faa184fd386573f82e6dd9b53c8'
RUNTIME='3b125edc1d29f7c7a91673da2a8d752bb0adff44'


def build(source,run_id,variant='as-produced',seed=None,previous_receipt=None):
    if source not in ('MDR','RADLEX'):raise ValueError('No reviewed characterization case')
    version={'MDR':'MDR_29_1','RADLEX':'RADLEX_4_3'}[source]
    stem={'MDR':'mdr-29-1','RADLEX':'radlex-4-3'}[source]
    ref=load(DOCS/(stem+'-reference.json'));inventory=load(DOCS/(stem+'-archive-inventory.json'))
    stage=load(DOCS/'additional-source-stage-review-20261106.json')['records'][version]
    ids=load(DOCS/'additional-source-historical-identities.json')[version]
    additions=load(ROOT/'baseline/additions-20261105.json')
    apparatus=commit('HEAD');modules={};hashes={};provenance=[]
    names=tuple(dict.fromkeys(MODULES+('replay_framework_core.py','compare_framework_core.py','audit_mdr_corrections.py','mdr_correction_runtime.py')))
    paths=['tools/'+name for name in names]+['tools/framework_characterization.py',
        'docs/inversion-review/'+stem+'-reference.json','docs/inversion-review/'+stem+'-archive-inventory.json',
        'docs/inversion-review/additional-source-stage-review-20261106.json',
        'docs/inversion-review/additional-source-historical-identities.json',
        'docs/inversion-review/case-catalog/mth-as-produced.json','baseline/additions-20261105.json']
    for path in paths:
        raw=blob(apparatus,path)
        if (ROOT/path).read_bytes()!=raw:raise ValueError('Commit characterization artifacts before freezing: '+path)
        sha=hashlib.sha256(raw).hexdigest();provenance.append({'repository_path':path,'sha256':sha})
        if path.startswith('tools/') and Path(path).name in names:
            name=Path(path).name;modules[name]=base64.b64encode(raw).decode();hashes[name]=sha
    validate_module_dependencies({name:base64.b64decode(raw) for name,raw in modules.items()})
    code=[]
    for item in additions['files']:
        prefix='sources/'+version+'/'
        if not item['repository_path'].startswith(prefix):continue
        relative=item['repository_path'][len(prefix):]
        if relative.startswith('src/'):continue
        raw=blob(ENGINE,item['repository_path'])
        if hashlib.sha256(raw).hexdigest()!=item['imported_sha256']:raise ValueError('Selected source engine differs from production capture')
        code.append({'relative_path':relative,'kind':'file','mode':oct(int(item['git_mode'],8)&0o777),
                     'sha256':item['imported_sha256'],'data_b64':base64.b64encode(raw).decode()})
    runtime=copy.deepcopy(load(DOCS/'case-catalog/mth-as-produced.json')['runtime_files'])
    for item in runtime:
        if hashlib.sha256(blob(RUNTIME,item['relative_path'])).hexdigest()!=item['sha256']:raise ValueError('Production runtime differs')
    references=[]
    for name in ('classes_atoms.src','attributes.src','relationships.src','mergefacts.src','contexts.src'):
        member=version+'/src/'+('attributes.orig' if name=='attributes.src' else name)
        found=[x for x in inventory['entries'] if x['path']==member and x['kind']=='file']
        if len(found)!=1:raise ValueError('No unique official reference')
        references.append({**{k:found[0][k] for k in ('path','sha256','newline_count')},'output_name':name})
    bounds={'start':ids['atom_ids']['minimum'],'end':777343592 if source=='MDR' else ids['atom_ids']['maximum'],
            'provenance_kind':'captured SaidStart/SaidEnd configuration' if source=='MDR' else 'captured SaidStart plus observed historical emitted-ID upper bound; production reservation end unknown',
            'production_reservation_end_assessed':source=='MDR'}
    result={'schema_version':1,'artifact_type':'ncimeta-framework-characterization','source':source,'version':version,
            'run_id':run_id,'engine_ref':ENGINE,'runtime_ref':RUNTIME,'apparatus_ref':apparatus,
            'archive_path':ref['archive_path'],'archive_sha256':ref['archive_sha256'],'object_identity':ref['object_identity'],
            'replacement_baseline':ids['metadata']['replacement_baseline'],'starting_stage':'publisher' if source=='MDR' else 'prepared',
            'root_atom_id':124407941 if source=='MDR' else 116482203,'root_code':'V-'+source,'source_atom_ids':bounds,
            'input_files':stage['declared_starting_bundle'],'code_files':code,'runtime_files':runtime,'reference_files':references,
            'modules_b64':modules,'apparatus_sha256':hashes,'provenance':provenance,
            'known_limits':['Fresh core conversion and archived-output comparison; not a completed common-adapter integration.',
                            'Metadata generation, RADLEX upstream CSV preparation, legacy QA, insertion and production eligibility are outside this case.']}
    if variant!='as-produced':
        if source!='MDR' or variant!='consistent-history-context' or seed not in ('1','12345'):raise ValueError('Unreviewed correction variant/source/seed')
        from replay_framework_core import MDR_ENGINE,MDR_RUNTIME
        changed=git_paths=__import__('subprocess').check_output(['git','-C',str(ROOT),'diff','--name-only',ENGINE,MDR_ENGINE]).decode().splitlines()
        if set(changed)!={'sources/MDR_29_1/bin/append_atn.pl','sources/MDR_29_1/bin/invert_mdr.pl'}:raise ValueError('MDR correction scope changed')
        for item in result['code_files']:
            raw=blob(MDR_ENGINE,'sources/MDR_29_1/'+item['relative_path']);item['sha256']=hashlib.sha256(raw).hexdigest();item['data_b64']=base64.b64encode(raw).decode()
        result['prior_runtime_files']=copy.deepcopy(runtime);result['prior_runtime_ref']=RUNTIME
        for item in runtime:
            raw=blob(MDR_RUNTIME,item['relative_path']);sha=hashlib.sha256(raw).hexdigest()
            if sha!=item['sha256']:
                if item['relative_path']!='INV/lib/Hierarchy.pm':raise ValueError('Unreviewed runtime change')
                result['runtime_override']={'relative_path':item['relative_path'],'prior_sha256':item['sha256'],'sha256':sha,'data_b64':base64.b64encode(raw).decode()};item['sha256']=sha
        if not result.get('runtime_override'):raise ValueError('Missing stable serializer dependency')
        result.update(engine_ref=MDR_ENGINE,runtime_ref=MDR_RUNTIME,case_variant=variant,perl_hash_seed=seed,previous_source_receipt=previous_receipt)
    elif seed is not None or previous_receipt is not None:raise ValueError('Seeds/preservation are supported only by reviewed MDR corrections')
    result['capsule_sha256']=digest(result);return result


def bootstrap(package,operation='submit',expected_run=None):
    if operation not in ('submit','inspect','activate','restore'):raise ValueError('Unsupported operation')
    payload=base64.b64encode(json.dumps({'package':package,'operation':operation,'expected_run':expected_run}).encode()).decode()
    program="""import base64,hashlib,json,pathlib,sys,tempfile
payload=json.loads(base64.b64decode(PAYLOAD));package=payload['package']
with tempfile.TemporaryDirectory(prefix='framework-characterization-') as temporary:
 root=pathlib.Path(temporary)
 for name,encoded in package['modules_b64'].items():
  if pathlib.Path(name).name!=name or not name.endswith('.py'):raise ValueError('Invalid module path')
  raw=base64.b64decode(encoded,validate=True)
  if hashlib.sha256(raw).hexdigest()!=package['apparatus_sha256'].get(name):raise ValueError('Module changed')
  (root/name).write_bytes(raw)
 sys.path.insert(0,str(root));sys.dont_write_bytecode=True
 from replay_framework_core import launch,inspect_previous
 if payload['operation']=='submit':result=launch(package)
 elif payload['operation']=='inspect':result=inspect_previous(package,payload['expected_run'])
 else:
  from mdr_correction_runtime import switch
  result=switch(package,restore=payload['operation']=='restore')
 print('BEGIN_COMMON_REPLAY_RESULT');print(json.dumps(result));print('END_COMMON_REPLAY_RESULT',flush=True)
""".replace('PAYLOAD',repr(payload))
    return "python3 -B - <<'NCIM_FRAMEWORK_CHARACTERIZATION'\n"+program+'\nNCIM_FRAMEWORK_CHARACTERIZATION\nexit\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    freeze=commands.add_parser('freeze');freeze.add_argument('source',choices=['MDR','RADLEX']);freeze.add_argument('--run-id',required=True);freeze.add_argument('--output',required=True)
    freeze.add_argument('--variant',default='as-produced',choices=['as-produced','consistent-history-context']);freeze.add_argument('--seed',choices=['1','12345']);freeze.add_argument('--previous-receipt')
    for operation in ('submit','inspect','activate','restore'):
        submit=commands.add_parser(operation);submit.add_argument('capsule');submit.add_argument('--socket',required=True);submit.add_argument('--output',required=True)
        if operation=='inspect':submit.add_argument('--expected-run',required=True)
    args=parser.parse_args()
    if args.command=='freeze':
        result=build(args.source,args.run_id,args.variant,args.seed,load(args.previous_receipt) if args.previous_receipt else None);write_new(args.output,result)
        print(json.dumps({key:result[key] for key in ('source','version','run_id','capsule_sha256','apparatus_ref')}))
    else:
        result=remote(bootstrap(load(args.capsule),args.command,getattr(args,'expected_run',None)),args.socket,'shapirod2');write_new(args.output,result)
        print(json.dumps({k:v for k,v in result.items() if k!='manifest'}))


if __name__=='__main__':main()
