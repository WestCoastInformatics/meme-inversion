#!/usr/bin/env python3
"""Actual streamed tar/current-file diagnostics with independently known deltas."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch

import diagnose_native_mth as diagnose
from execute_release_mth import OUTPUT_NAMES


def identity(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def seal(lock):
    lock['manifest_sha256']=diagnose.digest(lock['manifest']);lock['plan_sha256']=diagnose.digest(lock['plan'])
    lock['lock_sha256']=diagnose.digest({key:value for key,value in lock.items() if key!='lock_sha256'})


def raw_atom(number):
    return ('|'.join([str(555000000+number),'SRC' if number in (2,4,6) else 'TEST_1','TEST_1/PT',
        'V-SYNTHETIC-'+str(number),'R','Y','A','SYNTHETIC atom'+str(number),'N','','','','ENG','needs_order_id','N',
        'C'+str(number).zfill(7),'A'+str(number).zfill(8)])+'\n').encode()


def attribute(number,value,subject=b'555000001'):
    return b'|'.join([str(number).encode(),subject,b'S',b'SYNTHETIC',value,b'MTH_2028AB',b'R',b'Y',b'N',b'N',
                      b'SRC_ATOM_ID',b'',b'',hashlib.md5(value).hexdigest().encode(),b''])+b'\n'


def fixture(directory):
    version='MTH_2028AB';target=directory/version;(target/'src').mkdir(parents=True)
    reference={'src/'+name:b'' for name in OUTPUT_NAMES}
    reference[diagnose.RAW]=b''.join(raw_atom(i) for i in range(1,7))
    retained=b''.join(raw_atom(i) for i in (1,3,5))
    reference['src/classes_atoms.src']=b''.join(b'|'.join(row.removesuffix(b'\n').split(b'|')[:14]+[row.removesuffix(b'\n').split(b'|')[15]])+b'\n' for row in retained.splitlines(keepends=True))
    reference['src/aui_said_map']=b''.join(('A'+str(i).zfill(8)+'|C'+str(i).zfill(7)+'|'+str(555000000+i)+'\n').encode() for i in range(1,5001))
    reference['src/cui_said_map']=b'C0000001|555000001\nC0000002|555000002\nC0000003|555000003\n'
    reference['src/rel_cui_said_map']=reference['src/cui_said_map']
    reference['src/said.ptsaid']=b'555000001|555000001\n555000002|555000002\n555000002|555000002\n555000003|555000003\n'
    reference['src/ptsaid.order']=b'555000001\n555000002\n555000003\n'
    context=[b'',b'PAR',b'',b'555000003',b'TEST_1',b'TEST_1',b'root',b'555000003',b'',b'',b'',b'',b'SRC_ATOM_ID',b'',b'555000003',b'SRC_ATOM_ID',b'',b'',b'']
    reference['src/contexts.src']=b'|'.join(context)+b'\n'
    reference['src/attributes.contexts-all.src']=attribute(201,b'root::~~SRC_ATOM_ID~~~SRC_ATOM_ID~',b'')
    reference['src/attributes.src']=b''.join(attribute(i,b'old'+str(i).encode()) for i in range(1,201))+reference['src/attributes.contexts-all.src']
    candidate=copy.deepcopy(reference);candidate[diagnose.RAW]=retained
    candidate['src/aui_said_map']=b''.join(row for i,row in enumerate(reference['src/aui_said_map'].splitlines(keepends=True),1) if i not in (100,800,4500))
    candidate['src/cui_said_map']=b'C0000003|555000003\nC0000001|555000001\nC0000002|555000002\n'
    candidate['src/rel_cui_said_map']=b'C0000003|555000003\nC0000001|555000001\nC0000002|555000009\n'
    candidate['src/said.ptsaid']=b'555000001|555000001\n555000002|555000002\n555000003|555000003\n'
    candidate['src/ptsaid.order']=b'555000001\n555000003\n'
    context[0]=context[11]=b'555000001';candidate['src/contexts.src']=b'|'.join(context)+b'\n'
    candidate['src/attributes.contexts-all.src']=attribute(201,b'root::~555000001~SRC_ATOM_ID~~555000001~SRC_ATOM_ID~')
    candidate['src/attributes.src']=b''.join(attribute(i,(b'new' if i<=80 else b'old')+str(i).encode()) for i in range(1,201))+candidate['src/attributes.contexts-all.src']
    for name,raw in candidate.items():(target/name).write_bytes(raw)
    (target/'src/classes_atoms.unfiltered.raw').write_bytes(reference[diagnose.RAW])
    archive=directory/(version+'.tgz')
    def package(duplicate=False):
        with tarfile.open(archive,'w:gz') as handle:
            for name,raw in reference.items():
                member=tarfile.TarInfo(version+'/'+name);member.size=len(raw);handle.addfile(member,io.BytesIO(raw))
            member=tarfile.TarInfo(version+'/unselected/large.txt');member.size=200000;handle.addfile(member,io.BytesIO(b'x'*member.size))
            if duplicate:
                member=tarfile.TarInfo(version+'/'+diagnose.RAW);member.size=len(reference[diagnose.RAW]);handle.addfile(member,io.BytesIO(reference[diagnose.RAW]))
    package()
    files=[{'role':name,'uri':archive.as_uri(),**identity(raw),'archive_member':version+'/'+name,
            'archive_format':'tar.gz','archive_sha256':identity(archive.read_bytes())['sha256'],'archive_bytes':archive.stat().st_size}
           for name,raw in reference.items()]
    config={'source':'MTH','version':version,'replay':{'reference_ref':'official'}}
    manifest={'configuration':config,'artifacts':{'official':{'artifact_type':'reference-inversion','source':'MTH','version':version,
        'data':{'reference_stage':'inversion-src'},'files':files}}}
    lock={'schema_version':1,'artifact_type':'ncimeta-native-release-lock','configuration':config,'manifest':manifest,
          'plan':{'source':'MTH','version':version,'output_files':list(reference)},'run_id':'SYNTHETIC-diagnostic-only',
          'scope':'Synthetic read-only diagnostic fixture, not an execution admission record'}
    seal(lock)
    def result():
        return {'source':'MTH','version':version,'run_id':lock['run_id'],'lock_sha256':lock['lock_sha256'],
            'comparison':{'files':{name:{'reference':identity(raw),'candidate':identity((target/name).read_bytes()),
               'exact_match':raw==(target/name).read_bytes()} for name,raw in reference.items()}},
            'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW','production_eligible':False}}
    return lock,target,result,reference,candidate,archive,package


def check():
    checks=[]
    def good(value,label):
        assert value,label
        checks.append(label)
    def rejected(function,label):
        try:function()
        except (ValueError,OSError,tarfile.TarError):checks.append(label);return
        raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='mth-readonly-diagnostic-') as temporary:
        base=Path(temporary).resolve();lock,target,result,reference,candidate,archive,package=fixture(base)
        frozen_result=result();before_result=copy.deepcopy(frozen_result);before_lock=copy.deepcopy(lock)
        def snapshot():return {str(path.relative_to(base)):(identity(path.read_bytes()),path.stat().st_mode) for path in base.rglob('*') if path.is_file()}
        before=snapshot();real_open=os.open
        def readonly_open(path,flags,*args,**kwargs):
            assert not flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC),'Diagnostic attempted a filesystem write'
            return real_open(path,flags,*args,**kwargs)
        with patch.object(diagnose.os,'open',side_effect=readonly_open),patch.object(tarfile.TarFile,'extractall',side_effect=AssertionError('Extracted reference tree')), \
                patch.object(tarfile.TarFile,'extract',side_effect=AssertionError('Extracted reference member')):
            report=diagnose.diagnose(lock,target,frozen_result,examples=2)
        good(snapshot()==before and frozen_result==before_result and lock==before_lock,'diagnosis opens native inputs only for read and changes no input/result/lock/file/mode')
        good(len(report['files'])==9 and report['version']=='MTH_2028AB','frozen future-version result selects all9 mismatches without release/ID special cases')
        good(report['raw_result_acceptance']==frozen_result['acceptance'] and not report['acceptance_changed'] and not report['native_data_modified'],'strict raw verdict is preserved without diagnostic acceptance')
        good(not any(path.name=='large.txt' for path in base.rglob('*')) and report['archive_observations'][0]['bytes']==archive.stat().st_size,'selected members are streamed; large unselected payload never materialized and full container counted')
        raw=report['raw_atom_retention']
        good(raw['official_raw_vs_unfiltered']['ordered']['different_positions']==0,'complete official raw allocation equals independently observed unfiltered candidate bytes')
        for key in ('official_raw_to_retained','unfiltered_to_retained'):
            value=raw[key]
            good(value['ordered_deletion_only'] and value['matched_occurrences']==3 and value['deleted_reference_occurrences']==3 and value['unmatched_candidate_occurrences']==0,'all retained raw atoms are ordered byte-exact subsequence: '+key)
            good(len(value['deleted_examples'])==2 and value['deleted_examples'][0]['line']==2,'deleted raw examples bounded while all3 removals are counted: '+key)
        aui=report['files']['src/aui_said_map']
        good(aui['comparisons']['candidate']['ordered']['different_positions']>4000 and aui['deletion_only']['deleted_reference_occurrences']==3 and aui['deletion_only']['ordered_deletion_only'],'positional map shifts are distinguished from3 actual ordered deletions')
        good(aui['row_multiset']['reference_only_occurrences']==3 and aui['row_multiset']['candidate_only_occurrences']==0 and len(aui['row_multiset']['reference_only_examples'])==2,'full-map Counter preserves complete delta counts with bounded examples')
        mapping=report['files']['src/cui_said_map']
        good(mapping['comparisons']['candidate']['ordered']['different_positions']==3 and mapping['row_multiset']['row_multiset_equal'] and mapping['row_multiset']['keys_with_different_row_occurrences']==0,'reordered CUI bindings are not mislabeled as changed bindings')
        mapping=report['files']['src/rel_cui_said_map']['row_multiset']
        good(not mapping['row_multiset_equal'] and mapping['reference_only_occurrences']==mapping['candidate_only_occurrences']==1 and mapping['keys_with_different_row_occurrences']==1,'one altered binding is isolated independently of3 positional shifts')
        preferred=report['files']['src/said.ptsaid']['deletion_only']
        good(preferred['ordered_deletion_only'] and preferred['deleted_reference_occurrences']==1 and preferred['matched_occurrences']==3,'duplicate preferred rows retain physical multiplicity; deleting one occurrence is visible')
        order=report['files']['src/ptsaid.order']
        good(order['comparisons']['candidate']['ordered']['different_positions']==2 and order['deletion_only']['deleted_reference_occurrences']==1,'preferred ordering distinguishes shifted positions from one removed row')
        attributes=report['files']['src/attributes.src']['comparisons']['candidate']['ordered']
        good(attributes['different_positions']==81 and attributes['field_differences']['attribute_value']==81 and attributes['field_differences']['hashcode']==81 and attributes['field_differences']['id']==1,'every native and context-attribute field difference counted beyond first examples')
        good(len(attributes['examples'])==2,'ordered mismatch examples are bounded independently of complete counts')
        context=report['files']['src/contexts.src']['comparisons']['candidate']['ordered']
        good(context['field_differences']=={'src_atom_id_1':1,'id_1':1},'MTH19-field context layout names both changed endpoint columns accurately')
        focused=diagnose.diagnose(lock,target,frozen_result,examples=2,identifiers=['555000001'])
        bucket=focused['files']['src/attributes.src']['focused_rows']['buckets']['555000001']
        good(bucket['reference']['rows']==200 and bucket['candidate']['rows']==201 and len(bucket['candidate']['examples'])==2,'explicit token focus counts all matching rows beyond bounded samples without filtering comparison')
        empty=focused['files']['src/attributes.contexts-all.src']['focused_rows']['buckets']['empty_attribute_subject']
        fixed=focused['files']['src/attributes.contexts-all.src']['focused_rows']['buckets']['555000001']
        good(empty['reference']['rows']==1 and empty['candidate']['rows']==0 and fixed['candidate']['rows']==1 and
             empty['reference']['examples'][0]['fields'][1]['text']=='' and fixed['candidate']['examples'][0]['fields'][1]['text']=='555000001',
             'exact original blank-context attribute and repaired node row captured with unchanged generated IDs')
        empty=focused['files']['src/contexts.src']['focused_rows']['buckets']['empty_context_subject_or_id1']
        fixed=focused['files']['src/contexts.src']['focused_rows']['buckets']['555000001']
        good(empty['reference']['rows']==1 and fixed['candidate']['rows']==1 and len(fixed['candidate']['examples'][0]['fields'])==19,
             'exact19-field old/new context node rows retained independently of positional alignment')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result,identifiers=['unbounded token with spaces']),'identifier focus is literal and bounded')
        zero=diagnose.diagnose(lock,target,frozen_result,examples=0)
        good(not zero['files']['src/attributes.src']['comparisons']['candidate']['ordered']['examples'] and zero['raw_atom_retention']['official_raw_to_retained']['deleted_reference_occurrences']==3,'zero examples still counts every difference/deleted occurrence')
        capped=diagnose.diagnose(lock,target,frozen_result,map_max_bytes=1)
        good(capped['files']['src/cui_said_map']['row_multiset']['performed'] is False and 'row_multiset_equal' not in capped['files']['src/cui_said_map']['row_multiset'],'map size cap skips memory diagnostic without claiming binding equality')
        explicit=diagnose.diagnose(lock,target,{'records':{'result.json':frozen_result}},roles=['src/cui_said_map'])
        good(set(explicit['files'])=={diagnose.RAW,'src/cui_said_map'},'collected result wrapper and explicit role selection preserve mandatory raw allocation proof')
        unfiltered=target/'src/classes_atoms.unfiltered.raw';saved=unfiltered.read_bytes();unfiltered.write_bytes(saved.replace(b'SYNTHETIC atom3',b'UNEXPLAINED atom3'))
        changed=diagnose.diagnose(lock,target,frozen_result)
        good(not changed['raw_atom_retention']['unfiltered_to_retained']['ordered_deletion_only'] and changed['raw_atom_retention']['official_raw_vs_unfiltered']['ordered']['different_positions']==1,'unexplained unfiltered allocation alteration cannot pass deletion-only proof')
        unfiltered.write_bytes(saved)
        path=target/'src/aui_said_map';saved=path.read_bytes();path.write_bytes(saved+b'A99999999|C9999999|555999999\n')
        inserted=diagnose.diagnose(lock,target,result())['files']['src/aui_said_map']
        good(not inserted['deletion_only']['ordered_deletion_only'] and inserted['row_multiset']['candidate_only_occurrences']==1,'added mapping prevents deletion-only claim and full Counter reports actual addition')
        path.write_bytes(saved)
        path=target/'src/cui_said_map';saved=path.read_bytes();path.write_bytes(saved+b'C0000001|555000001\n')
        duplicates=diagnose.diagnose(lock,target,result())['files']['src/cui_said_map']['row_multiset']
        good(not duplicates['row_multiset_equal'] and duplicates['candidate_only_occurrences']==1,'duplicate map addition cannot disappear through set comparison')
        path.write_bytes(saved)
        path=target/'src/attributes.src';saved=path.read_bytes();path.write_bytes(saved.removesuffix(b'\n'))
        endings=diagnose.diagnose(lock,target,result())['files']['src/attributes.src']['comparisons']['candidate']['ordered']
        good(endings['line_ending_differences']==1,'terminal newline differences remain exact byte differences')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result),'candidate mutation since frozen raw result is rejected')
        path.write_bytes(saved)
        bad=copy.deepcopy(lock);bad['configuration']['version']='MTH_2099AA'
        rejected(lambda:diagnose.diagnose(bad,target,frozen_result),'changed frozen lock rejected')
        bad=copy.deepcopy(frozen_result);bad['run_id']='another-run'
        rejected(lambda:diagnose.diagnose(lock,target,bad),'other-run raw result rejected')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result,roles=['../../outside']),'unbound diagnostic role rejected')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result,examples=21),'example count bounded')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result,map_max_bytes=257*1024**2),'identity-map Counter cap bounded')
        saved_archive=archive.read_bytes();archive.write_bytes(saved_archive+b'UNVERIFIED TAIL')
        rejected(lambda:diagnose.diagnose(lock,target,frozen_result),'complete compressed archive hash includes bytes beyond tar end marker')
        archive.write_bytes(saved_archive)
        bad=copy.deepcopy(lock);file=next(item for item in bad['manifest']['artifacts']['official']['files'] if item['role']=='src/attributes.src');file['sha256']='a'*64;seal(bad)
        rejected(lambda:diagnose.diagnose(bad,target,roles=['src/attributes.src']),'selected member full hash independently checked')
        package(duplicate=True)
        bad=copy.deepcopy(lock)
        for file in bad['manifest']['artifacts']['official']['files']:file.update(archive_sha256=identity(archive.read_bytes())['sha256'],archive_bytes=archive.stat().st_size)
        seal(bad)
        rejected(lambda:diagnose.diagnose(bad,target),'duplicate tar member rejected despite matching new container hash')
        archive.write_bytes(saved_archive)
        # Actual CLI emits only JSON on stdout and progress separately; no report
        # or temporary reference files are written by the executable itself.
        lock_path=base/'lock.json';result_path=base/'result.json';lock_path.write_text(json.dumps(lock));result_path.write_text(json.dumps(frozen_result))
        before=snapshot()
        process=subprocess.run([sys.executable,'-B',str(Path(diagnose.__file__)),'--lock',str(lock_path),'--target',str(target),'--result',str(result_path),'--examples','1'],capture_output=True,text=True,check=True)
        cli=json.loads(process.stdout)
        good(cli['version']=='MTH_2028AB' and 'Diagnosing src/' in process.stderr and snapshot()==before,'actual CLI remains read-only with parseable JSON and separate progress')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
