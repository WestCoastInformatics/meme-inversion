#!/usr/bin/env python3
"""Confined physical-input checks for offline discovery."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import subprocess
import sys
from unittest.mock import patch
import zipfile

import release_preparation as prep


def ident(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def artifact(files):
    return {'schema_version':1,'artifact_type':'publisher-bundle','source':'NCI','version':'NCI_2031_12E',
            'provenance':{'producer':'fixture','producer_version':'1','capture_id':'fixture','evidence_kind':'synthetic-fixture'},'files':files,'data':{}}


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label):
        try:action()
        except (ValueError,OSError):checks.append(label);return
        raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='release-discovery-') as temporary:
        root=Path(temporary).resolve();raw=b'header\na|b\na|b\n';file=root/'native.txt';file.write_bytes(raw)
        descriptor={'role':'native','uri':file.as_uri(),**ident(raw)}
        def read(reader,role='native'):
            with reader.open('publisher',role) as stream:return stream.read()
        inputs=prep.Inputs({'publisher':artifact([descriptor])})
        with inputs.open('publisher','native') as stream:good(stream.readline()==b'header\n','binary streaming interface supports header read')
        good(inputs.verified[('publisher','native')]['bytes']==len(raw),'early consumer exit still verifies all bytes')
        good(read(inputs)==raw,'duplicate row occurrences preserved')
        file.write_bytes(raw+b'changed\n')
        reject(lambda:read(inputs),'failed reread cannot retain old verification')
        good(('publisher','native') not in inputs.verified,'failed reread invalidates the earlier verified role')
        file.write_bytes(raw)
        inputs=prep.Inputs({'publisher':artifact([descriptor])});read(inputs);file.write_bytes(raw+b'changed\n')
        good(inputs.finish() and not inputs.verified,'end-of-scan check detects later input mutation and invalidates its rows')
        file.write_bytes(raw);inputs=prep.Inputs({'publisher':artifact([descriptor])})
        reject(lambda:read(inputs,'missing'),'missing input role rejected')
        wrong=copy.deepcopy(descriptor);wrong['sha256']='0'*64
        reject(lambda:read(prep.Inputs({'publisher':artifact([wrong])})),'incorrect direct file hash rejected')
        wrong=copy.deepcopy(descriptor);wrong['bytes']=1
        reject(lambda:read(prep.Inputs({'publisher':artifact([wrong])})),'incorrect byte bound rejected during stream')
        oracle=artifact([descriptor]);oracle['artifact_type']='reference-inversion'
        reject(lambda:read(prep.Inputs({'publisher':oracle})),'official output cannot be used for discovery')
        linked=root/'link';linked.symlink_to(file);wrong=copy.deepcopy(descriptor);wrong['uri']=linked.as_uri()
        reject(lambda:read(prep.Inputs({'publisher':artifact([wrong])})),'linked source rejected')
        for kind in ('zip','tar.gz'):
            archive=root/('publisher.'+kind);members={'package/one':raw,'package/two':b'other\n'}
            if kind=='zip':
                with zipfile.ZipFile(archive,'w') as out:
                    for name,value in members.items():out.writestr(name,value)
            else:
                with tarfile.open(archive,'w:gz') as out:
                    for name,value in members.items():
                        item=tarfile.TarInfo(name);item.size=len(value);out.addfile(item,io.BytesIO(value))
            files=[{'role':role,'uri':archive.as_uri(),**ident(value),'archive_member':name,
                    'archive_format':kind,'archive_sha256':ident(archive.read_bytes())['sha256'],'archive_bytes':archive.stat().st_size}
                   for role,(name,value) in zip(('native','second'),members.items())]
            reader=prep.Inputs({'publisher':artifact(files)})
            original=prep.manifests._hash_stream
            with patch.object(prep.manifests,'_hash_stream',wraps=original) as counter:
                good(read(reader)==raw and read(reader,'second')==b'other\n',kind+' selected members verified without extraction')
                good(counter.call_count==1,kind+' full archive hash reused only while unchanged')
            good(len(reader.verified)==2 and not (root/'package').exists(),kind+' no archive tree extracted')
            if kind=='zip':
                with patch.object(prep.zipfile.ZipFile,'open',side_effect=RuntimeError('encrypted archive fixture')):
                    reject(lambda:read(reader),'unsupported ZIP read failure becomes a structured input blocker')
            archive.write_bytes(archive.read_bytes()+b'x')
            reject(lambda:read(reader),kind+' changed archive rejected after prior verification')
        manifest=prep.manifests.load(prep.manifests.DOCS/'release-manifests/nci-2026-08e.json')
        manifest['purpose']='shadow';manifest['configuration'].pop('replay',None);manifest['configuration']['source_atom_ids']=None
        good(not prep.validate(manifest),'shared schema accepts pre-allocation shadow discovery without official reference')
        scanner=type('Scanner',(),{'analyze':staticmethod(lambda *args:{'issues':[],'decisions':[{'kind':'new-termgroup'}],'facts':{},'required_inputs':[]})})
        with patch.object(prep.importlib,'import_module',return_value=scanner):
            report=prep.discover(manifest)
        good(report['status']=='DECISIONS_REQUIRED' and not report['execution_eligible'],'unresolved decision list blocks readiness and never permits execution')
        invalid=copy.deepcopy(manifest);invalid['configuration']['invented_parameter']=True
        good(prep.discover(invalid)['status']=='DISCOVERY_BLOCKED','unknown common configuration key rejected')
        dangling=root/'dangling-report';dangling.symlink_to(root/'missing-target')
        for tool,args in [('inversion_request.py',['discover-release','/missing-manifest']),
                          ('inversion_remote.py',['--socket','/missing-socket','discover-release','/missing-manifest'])]:
            run=subprocess.run([sys.executable,'-B',str(prep.manifests.ROOT/'tools'/tool),*args,'--output',str(dangling)],capture_output=True,text=True)
            good(run.returncode==2 and 'already exists' in run.stderr,'dangling output rejected before any input/network work: '+tool)
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
