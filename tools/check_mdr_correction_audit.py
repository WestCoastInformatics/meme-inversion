#!/usr/bin/env python3
"""Verify full-record MDR correction prediction and rejection of other changes."""
import copy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
from unittest.mock import patch

import audit_mdr_corrections as audit
import compare_framework_core as compare
from check_framework_comparison import row,attribute


def check():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='mdr-audit-fixture-') as temporary:
        base=Path(temporary)
        atoms=b''.join(row([said,'MDR_29_1','MDR_29_1/'+tty,'C'+str(said),'R','Y','A',name,'N','','C'+str(said),'','ENG','','']) for said,tty,name in [(100,'OS','RootA'),(101,'PT','TermA'),(102,'OS','RootB'),(103,'LLT','TermB')])
        root=attribute(2,99,'CONTEXT','1\t::~~~~~~\t\tMedDRA\t\t')
        a=attribute(3,102,'CONTEXT','1\t::~~~~~~\tMedDRA\tRootB\t\tRootA^')
        b=attribute(4,100,'CONTEXT','1\t::~~~~~~\tMedDRA\tRootA\t\tRootB^')
        def history(identifier,code,value,old=False):
            return row([identifier,code,'S','PT_IN_VERSION',value,'MDR_29_1','R','Y','N','N','CODE_SOURCE','MDR_29_1','',hashlib.md5((value+('\r' if old else '')).encode()).hexdigest(),''])
        ordinary=attribute(1,100,'SEMANTIC_TYPE','fixture')
        original=ordinary+root+a+b+history(5,'C101','8.0',True)+history(6,'C103','8.1',True)
        corrected=ordinary+root+b.replace(b'4|',b'3|',1)+a.replace(b'3|',b'4|',1)+history(5,'C101','8.0')+history(6,'C103','8.1')
        files={'classes_atoms.src':atoms,'attributes.src':original,'relationships.src':row([1,'S',100,'BT','',101,'MDR_29_1','MDR_29_1','R','Y','N','N','SRC_ATOM_ID','','SRC_ATOM_ID','','','','']),
               'mergefacts.src':row([101,'SY',103,'MDR_29_1','','N','N','','SRC_ATOM_ID','','SRC_ATOM_ID','','']),
               'contexts.src':row([100,'PAR','',99,'MDR_29_1','MDR_29_1','','99','R','','',100,'SRC_ATOM_ID','',99,'SRC_ATOM_ID','',''])}
        for name,mutate in [('allowed',lambda x:x),('unrelated-value',lambda x:x.replace(b'fixture',b'changed',1)),('wrong-generated-id',lambda x:x.replace(b'3|100|',b'7|100|',1)),('missing-history',lambda x:x.rsplit(b'\n',2)[0]+b'\n')]:
            case=base/name;target=case/'MDR_29_1';(target/'src').mkdir(parents=True);(target/'orig').mkdir();run=case/'run';run.mkdir()
            (target/'src/termgroups.src').write_bytes(b''.join(('MDR_29_1/'+tty+'|fixture\n').encode() for tty in ['OS','PT','LLT']))
            (target/'orig/mdr_by_version.txt').write_bytes(b'C101|8.0\r\nC103|8.1\r\n')
            archive=case/'official.tgz';references=[]
            with tarfile.open(archive,'w:gz') as handle:
                for output,raw in files.items():
                    member='MDR_29_1/src/'+('attributes.orig' if output=='attributes.src' else output);info=tarfile.TarInfo(member);info.size=len(raw);handle.addfile(info,io.BytesIO(raw));references.append({'path':member,'output_name':output,'sha256':hashlib.sha256(raw).hexdigest(),'newline_count':raw.count(b'\n')})
            for output,raw in files.items():(target/'src'/output).write_bytes(mutate(corrected) if output=='attributes.src' else raw)
            package={'source':'MDR','version':'MDR_29_1','case_variant':'consistent-history-context','engine_ref':'fixture','runtime_ref':'fixture','apparatus_ref':'fixture','run_id':name,'root_atom_id':99,
                     'source_atom_ids':{'start':100,'end':103,'provenance_kind':'synthetic','production_reservation_end_assessed':True},'archive_path':str(archive),'archive_sha256':compare.file_info(archive)['sha256'],'reference_files':references,'starting_stage':'fixture'}
            comparison=compare.compare(package,target,run,progress=lambda *args,**kwargs:None);raw={'comparison':comparison,'acceptance':comparison['acceptance']}
            with patch.object(audit,'EXPECTED_COUNTS',(2,3,2)):
                if name=='allowed':
                    result=audit.audit(package,target,run,raw);assert result['status']=='PASS_REVIEWED_CORRECTIONS' and result['context_attributes_predicted_with_exact_ids']==3
                    checks.append('Exact native-derived history corrections and complete generated context ID prediction pass')
                    assert comparison['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW';checks.append('Original raw difference/reference-digest verdict remains unchanged')
                else:
                    try:audit.audit(package,target,run,raw)
                    except RuntimeError:checks.append('Audit rejects '+name)
                    else:raise AssertionError('Unreviewed change passed: '+name)
    return checks


if __name__=='__main__':
    for item in check():print('PASS',item)
