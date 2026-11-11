#!/usr/bin/env python3
"""Confined synthetic TAR capture/curation tests; no server or native run."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

import capture_archived_snomed as capture
import check_execute_release_snomed as fixtures
import curate_archived_snomed as curator
import inspect_inversion_archive as inventory_tool


def archive_fixture(root, terminal=False, index=0):
    manifest=fixtures.fixture(index);version=manifest['configuration']['version'];state=manifest['artifacts']['ncimeta-snapshot']
    state['data']['sources_rows'][0][3]=version
    if terminal:state['data']['metadata_format']={key:{'terminal_delimiter':True} for key in ('sources-src','termgroups-src')}
    metadata_bytes={}
    for role,key,width in [('sources-src','sources_rows',20),('termgroups-src','termgroups_rows',6)]:
        raw=curator.execution._metadata_bytes(state['data'][key],width,terminal)
        row=next(item for item in state['files'] if item['role']==role);row.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));metadata_bytes[role]=raw
    plan=fixtures.plan(manifest);values={}
    for item in plan['input_files']:
        entry=next(x for x in manifest['artifacts'][item['artifact']]['files'] if x['role']==item['role'])
        raw=metadata_bytes.get(item['role'])
        if raw is None:raw=(fixtures.ROOT/entry['uri'].removeprefix('repo:')).read_bytes()
        if item['role']=='rf2-concepts':raw+=b'116680003\t20200131\t1\t900000000000207008\t900000000000074008\n'
        if item['role']=='rf2-descriptions':raw+=b'100012\t20200131\t1\t900000000000207008\t116680003\ten\t900000000000003001\tIs a (attribute)\t900000000000448009\n'
        values[version+'/'+item['destination']]=raw
    values[version+'/etc/sct.cfg']=base64.b64decode(plan['generated_files'][0]['data_b64'])
    for script in ['invert_rf2.pl','rmdanglingattrs.pl']:
        values[version+'/bin/'+script]=subprocess.check_output(['git','-C',str(fixtures.ROOT),'show','3b125edc1d29f7c7a91673da2a8d752bb0adff44:sources/SNOMEDCT_US_2026_09_01/bin/'+script])
    outputs=fixtures.output_fixture(plan)
    for name,rows in outputs.items():
        dest='attributes.orig' if name=='attributes.src' else name
        values[version+'/src/'+dest]=''.join('|'.join(row)+'\n' for row in rows).encode()
    row=copy.deepcopy(outputs['attributes.src'][0]);row[0]='2';row[3]='SEMANTIC_TYPE';row[4]='Finding';row[5]='E-'+version;row[13]=hashlib.md5(b'Finding').hexdigest()
    values[version+'/src/attributes.src']=values[version+'/src/attributes.orig']+('|'.join(row)+'\n').encode()
    archive=root/(version+'.tgz')
    with tarfile.open(archive,'w:gz') as handle:
        for name,raw in values.items():
            member=tarfile.TarInfo(name);member.size=len(raw);handle.addfile(member,io.BytesIO(raw))
    frozen=inventory_tool.inspect(archive,version)
    receipt={'source':'SNOMEDCT_US','version':version,'archive_sha256':frozen['archive_sha256'],
             'archive_bytes':frozen['archive_bytes'],'extracted':False,'object_identity':{'VersionId':'SYNTHETIC-UNIT-TEST'}}
    return archive,frozen,receipt


def check():
    passed=[]
    def good(value,label):assert value,label;passed.append(label)
    def reject(action,label):
        try:action()
        except ValueError:passed.append(label)
        else:raise AssertionError(label)
    for index,terminal in [(0,False),(1,True)]:
        with tempfile.TemporaryDirectory(prefix='snomed-curation-') as directory:
            root=Path(directory).resolve();archive,frozen,receipt=archive_fixture(root,terminal,index)
            before=set(root.rglob('*'));data=capture.capture(archive,frozen)
            good(set(root.rglob('*'))==before and not data['expanded_files_created'], 'Capture does not extract/write native or oracle files '+str(index))
            good(data['selected_payloads_inventory_verified'] and len(data['native']['files'])==14,
                 'Every selected native/producer/oracle payload matches its frozen inventory '+str(index))
            good(data['native']['discovery']['relationship_types']==['116680003'] and data['native']['type_fsn_labels']['116680003']==['Is a (attribute)'],
                 'Actual archive rows supply stable IDs and FN labels '+str(index))
            good(not data['diagnostics'],'Logical source/prior evidence agrees for the archived wire dialect '+str(index))
            engine=subprocess.check_output(['git','-C',str(fixtures.ROOT),'rev-parse','HEAD']).decode().strip()
            manifest,evidence=curator.curate(data,frozen,receipt,engine)
            good(manifest['configuration']['version']==data['version'] and manifest['configuration']['replacement_baseline']['version'] in ('SNOMEDCT_US_2026_03_01','SNOMEDCT_US_2027_03_01'),
                 'Curation uses explicit metadata predecessor across independent publications '+str(index))
            good(evidence['producer_byte_exact_after_target_bindings'] and evidence['cleanup_byte_exact'],
                 'Producer family compatibility is established without executing archived code '+str(index))
            good(all(value['terminal_delimiter'] is terminal for value in manifest['artifacts']['state']['data']['metadata_format'].values()),
                 'Logical20/6metadata rows retain the exact terminal delimiter dialect '+str(index))
            good(manifest['artifacts']['policy']['data']['mapping_targets']['ICD10CM']=='ICD10CM_2027' and not evidence['rendered_cfg_used_as_constructor'],
                 'Mapping target comes from archived producer literal; target cfg is generated separately '+str(index))
            attrs=next(row for row in manifest['artifacts']['official']['files'] if row['role']=='src/attributes.src')
            good(attrs['archive_member'].endswith('/src/attributes.orig') and evidence['oracle_attributes_prefix_proof']['prefix_equal'],
                 'Official inversion attributes select the hash-proved pre-enrichment prefix '+str(index))
            altered=copy.deepcopy(frozen);next(row for row in altered['entries'] if row['path'].endswith('/etc/sct.cfg'))['sha256']='0'*64
            reject(lambda:capture.capture(archive,altered),'Capture rejects a selected payload hash mismatch '+str(index))
            bad=copy.deepcopy(data);bad['enriched_attributes']['pre_enrichment_prefix']['prefix_equal']=False
            reject(lambda:curator.curate(bad,frozen,receipt,engine),'Unproved inversion/insertion stage boundary blocks curation '+str(index))
            bad=copy.deepcopy(data);bad['native']['type_fsn_labels']['116680003']=['Unknown publisher label']
            reject(lambda:curator.curate(bad,frozen,receipt,engine),'New native label is not guessed into an existing mapping '+str(index))
            bad=copy.deepcopy(data);bad['small_files']['bin/invert_rf2.pl']['text']+='\n# unreviewed producer\n'
            reject(lambda:curator.curate(bad,frozen,receipt,engine),'An unreviewed producer family cannot be silently admitted '+str(index))
    return passed


if __name__=='__main__':
    values=check()
    for label in values:print('PASS',label)
    print(len(values),'archived SNOMED capture/curation checks passed')
