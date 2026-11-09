#!/usr/bin/env python3
"""Test fresh preparation isolation, exact closure and frozen-input rejection."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import replay_framework_core as replay


def fixture(root,source):
    version,start,said,code=replay.CASES[source]
    data={name:b'fixture\n' for name in replay.INPUTS[source]}
    prior='MDR_29_0' if source=='MDR' else 'RADLEX_4_1'
    data['src/sources.src']=(version+'|'+prior+'|\n').encode()
    config='\n'.join(k+' = '+str(v) for k,v in [('VSAB',version),('RSAB',source),('SaidStart',start),('SaidEnd',777343592),('HC.RootNodeSaid',said),('HC.RootNodeCode',code)])+'\n'
    files={'bin/'+name:b'# fixture\n' for name in replay.SCRIPTS[source]};files['etc/'+source+'.cfg']=config.encode()
    def entry(name,raw):return {'relative_path':name,'kind':'file','mode':'0o600','sha256':hashlib.sha256(raw).hexdigest(),'data_b64':base64.b64encode(raw).decode()}
    archive=root/'sources'/(version+'.tgz')
    with tarfile.open(archive,'w:gz') as handle:
        # Official generated files may be present in the archive, never as inputs.
        for name,raw in {**data,'src/classes_atoms.src':b'OFFICIAL OUTPUT MUST NOT BE SEEDED\n'}.items():
            member=tarfile.TarInfo(version+'/'+name);member.size=len(raw);handle.addfile(member,io.BytesIO(raw))
    runtime=[]
    for number in range(169):
        name='INV/fixture-'+str(number);path=root/name;path.parent.mkdir(exist_ok=True);path.write_bytes(b'runtime\n')
        runtime.append({'relative_path':name,'sha256':replay.sha(path)})
    return {'source':source,'version':version,'source_atom_ids':{'start':start,'end':777343592 if source=='MDR' else 767813671},
            'root_atom_id':said,'root_code':code,'engine_ref':replay.ENGINE,'archive_path':str(archive),'archive_sha256':replay.sha(archive),
            'input_files':[{'relative_path':name,'sha256':hashlib.sha256(raw).hexdigest()} for name,raw in data.items()],
            'code_files':[entry(name,raw) for name,raw in files.items()],'runtime_files':runtime,'replacement_baseline':prior,'starting_stage':'fixture'}


def check():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='framework-preparation-') as temporary:
        root=Path(temporary);(root/'sources').mkdir()
        def publish(staging,target):
            if target.exists():raise FileExistsError(target)
            staging.rename(target)
        with patch.object(replay,'ROOT',root),patch.object(replay.socket,'gethostname',return_value='ncias-d3777-c'),patch.object(replay.pwd,'getpwuid',return_value=SimpleNamespace(pw_name='tomcata')),patch.dict(replay.os.environ,{'INV_HOME':str(root/'INV'),'LC_COLLATE':'C'}),patch.object(replay,'publish',side_effect=publish):
            for source in ('MDR','RADLEX'):
                package=fixture(root,source);target=root/'sources'/package['version']
                result=replay.prepare(package)
                assert not result['generated_outputs_seeded'] and not (target/'src/classes_atoms.src').exists()
                checks.append(source+' starts from exact declared inputs and Git code, without official outputs')
                try:replay.prepare(package)
                except RuntimeError:checks.append(source+' existing candidate cannot be overwritten')
                else:raise AssertionError('overwrite allowed')
                for label,mutate in [('missing-input',lambda x:x['input_files'].pop()),('seeded-output',lambda x:x['input_files'].append({'relative_path':'src/classes_atoms.src','sha256':'0'*64})),('wrong-version',lambda x:x.update(version='OTHER')),('missing-script',lambda x:x['code_files'].pop(0))]:
                    changed=copy.deepcopy(package);mutate(changed)
                    try:replay.guard(changed,target)
                    except (ValueError,RuntimeError):checks.append(source+' rejects '+label)
                    else:raise AssertionError(label)
                path=target/package['input_files'][0]['relative_path'];path.chmod(0o600);path.write_bytes(b'tampered\n')
                try:replay.verify_inputs(package,target)
                except RuntimeError:checks.append(source+' frozen input mutation fails closed')
                else:raise AssertionError('mutation accepted')
            package['artifact_type']='ncimeta-framework-characterization';package['run_id']='fixture-run'
            package['capsule_sha256']=hashlib.sha256(json.dumps(package,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
            replay.verify_capsule(package);package['run_id']='different-run'
            try:replay.verify_capsule(package)
            except RuntimeError:checks.append('Capsule mutation is rejected before launch')
            else:raise AssertionError('capsule mutation accepted')
    return checks


if __name__=='__main__':
    values=check()
    for value in values:print('PASS',value)
    print(len(values),'framework preparation checks passed')
