#!/usr/bin/env python3
"""Confined future-release native-row explanation; no server/acceptance changes."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile

import audit_mth_corrections as wire
import diagnose_native_mth as diagnostic
import execute_release_mth as engine
import explain_native_mth as explain


def ident(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def fixture(root):
    version='MTH_2033AB';target=root/'MEME5/inv/sources'/version;(target/'src').mkdir(parents=True)
    scratch=root/'MEME5/inv/qa';scratch.mkdir();native=root/'MEME5/mr/umls/2033AB/subset3/METASUBSET';native.mkdir(parents=True)
    rows=[]
    def atom(said,cui,aui,source,tty,code,name):
        f=[said,source,source+b'/'+tty,code,b'R',b'Y',b'A',name,b'N',b'',b'',b'',b'ENG',b'needs_order_id',b'N',cui,aui]
        rows.append(f);return f
    old=atom(b'900000001',b'C0000040',b'A0000041',b'SRC',b'VPT',b'V-CCS_2005',b'SYNTHETIC CCS')
    atom(b'900000002',b'C0000040',b'A0000042',b'SRC',b'VAB',b'V-CCS_2005',b'SYNTHETIC CCS abbreviation')
    node=atom(b'900000020',b'C0000030',b'A0000030',b'TEST_9',b'HC',b'NODE9',b'SYNTHETIC NODE')
    ordinary=atom(b'900000025',b'C0000010',b'A0000010',b'TEST_9',b'PT',b'ORD9',b'SYNTHETIC ORDINARY')
    parent=atom(b'900000030',b'C0000020',b'A0000020',b'SRC',b'RPT',b'V-TEST',b'SYNTHETIC ROOT')
    retained=rows[2:];ref={'src/'+name:b'' for name in engine.OUTPUT_NAMES};cur=copy.deepcopy(ref)
    ref[diagnostic.RAW]=b''.join(wire.row(f) for f in rows);cur[diagnostic.RAW]=b''.join(wire.row(f) for f in retained)
    ref['src/classes_atoms.src']=cur['src/classes_atoms.src']=b''.join(wire.row(f[:14]+[f[15]]) for f in retained)
    def maps(values):
        aui=b''.join(wire.row([f[16],f[15],f[0]]) for f in values)
        cuis={}
        for f in values:cuis.setdefault(f[15],f[0])
        return aui,b''.join(wire.row([cui,cuis[cui]]) for cui in sorted(cuis))
    for data,values in ((ref,[f for f in rows if f is not node]),(cur,retained)):
        aui,cuis=maps(values);data[explain.AUI]=aui;data[explain.CUI]=data[explain.RELCUI]=cuis
    def attr_content(said,kind,value,source=version.encode()):
        return wire.attribute([said,b'C',kind,value,source,b'R',b'Y',b'N',b'N',b'SRC_ATOM_ID',b'',b'',b''])
    plain=attr_content(ordinary[0],b'CUSTOM',b'ordinary');other=attr_content(parent[0],b'CUSTOM',b'root')
    semantic_old=attr_content(old[0],b'SEMANTIC_TYPE',b'Intellectual Product',b'E-'+version.encode())
    semantic_new=attr_content(node[0],b'SEMANTIC_TYPE',b'Intellectual Product',b'E-'+version.encode())
    old_prefix=b''.join(str(i).encode()+b'|'+f for i,f in enumerate((plain,semantic_old,other),1))
    new_prefix=b''.join(str(i).encode()+b'|'+f for i,f in enumerate((plain,other,semantic_new),1))
    ctx=[b'',b'PAR',b'',parent[0],node[1],node[1],b'',parent[0],b'',b'',b'',b'',b'SRC_ATOM_ID',b'',parent[0],b'SRC_ATOM_ID',b'',b'',b'']
    unchanged=ctx.copy();unchanged[0]=unchanged[11]=ordinary[0]
    fixed=ctx.copy();fixed[0]=fixed[11]=node[0]
    ref[explain.CTX]=b''.join(sorted((wire.row(ctx),wire.row(unchanged))))
    cur[explain.CTX]=b''.join(sorted((wire.row(fixed),wire.row(unchanged))))
    def context_attr(subject,value):
        return wire.attribute([subject,b'S',b'CONTEXT',value,node[1],b'R',b'Y',b'N',b'N',b'SRC_ATOM_ID',b'',b'',b''])
    old_value=b'1\t::~~SRC_ATOM_ID~~~SRC_ATOM_ID~\t'+parent[7]+b'\t'+node[7]+b'\t\t'
    new_value=old_value.replace(b'::~~SRC_ATOM_ID~~~SRC_ATOM_ID~',b'::~'+node[0]+b'~SRC_ATOM_ID~~'+node[0]+b'~SRC_ATOM_ID~')
    stable=context_attr(ordinary[0],b'unchanged context')
    for data,changed in ((ref,context_attr(b'',old_value)),(cur,context_attr(node[0],new_value))):
        ordered=sorted((stable,changed),key=lambda raw:raw.split(b'|',1)[0])
        data[explain.CTXATTR]=b''.join(str(i).encode()+b'|'+raw for i,raw in enumerate(ordered,4))
    ref[explain.ATTR]=old_prefix+ref[explain.CTXATTR];cur[explain.ATTR]=new_prefix+cur[explain.CTXATTR]
    ref[explain.PREF]=b''.join(wire.row([f[0],old[0] if f[15]==old[15] else f[0]]) for f in rows)
    cur[explain.PREF]=b''.join(wire.row([f[0],f[0]]) for f in retained)
    ref[explain.ORDER]=b''.join(value+b'\n' for value in (old[0],node[0],ordinary[0],parent[0]));cur[explain.ORDER]=b''.join(value+b'\n' for value in (node[0],ordinary[0],parent[0]))
    framework=wire.row([b'1',b'S',b'V-TEST',b'RT',b'',b'R-TEST',b'SRC',b'SRC',b'R',b'Y',b'N',b'N',b'CODE_TERMGROUP',b'SRC/VPT',b'CODE_TERMGROUP',b'SRC/RPT',b'',b'',b''])
    for data in (ref,cur):data['src/rel_src']=data['src/relationships.src']=framework
    for role,raw in cur.items():(target/role).write_bytes(raw)
    (target/'src/classes_atoms.unfiltered.raw').write_bytes(ref[diagnostic.RAW])
    prior=target/'orig/identity/MTH_2033AA/src/cui_said_map';prior.parent.mkdir(parents=True);prior.write_bytes(b'C9999999|800000001\n')
    identities=[];inputs=[]
    def rrffile(role,values):
        raw=b''.join(b'|'.join(f)+b'|\n' for f in values);(native/role).write_bytes(raw)
        entry={'artifact':'prepared','role':role,'scope':'meme','destination':'mr/umls/2033AB/subset3/METASUBSET/'+role}
        inputs.append(entry);identities.append({**entry,**ident(raw)})
    conso=[]
    for f in rows:
        value=[b'']*18;value[0]=f[15];value[7]=f[16];value[11]=f[1];value[12]=f[2].split(b'/')[1];value[13]=f[3];value[14]=f[7];conso.append(value)
    rrffile('MRCONSO.RRF',conso)
    rrffile('MRSTY.RRF',[[cui,b'T170',b'A2.4',b'Intellectual Product',b'AT1',b''] for cui in (old[15],node[15])])
    def context(cui,aui,code,level,cui2,aui2,label):return [cui,b'S1',aui,node[1],code,b'1',level,b'1' if level==b'ANC' else b'',label,cui2,aui2,b'',b'',b'',b'']
    rrffile('MRCXT.RRF',[context(parent[15],parent[16],parent[3],b'CHD',node[15],node[16],node[7]),context(node[15],node[16],node[3],b'ANC',parent[15],parent[16],parent[7]),context(node[15],node[16],node[3],b'CCP',node[15],node[16],node[7])])
    archive=root/'MEME5/inv/sources'/ (version+'.tgz')
    with tarfile.open(archive,'w:gz') as handle:
        for role,raw in ref.items():
            item=tarfile.TarInfo(version+'/'+role);item.size=len(raw);handle.addfile(item,io.BytesIO(raw))
    descriptor=[{'role':role,'uri':archive.as_uri(),**ident(raw),'archive_format':'tar.gz','archive_member':version+'/'+role,
        'archive_sha256':ident(archive.read_bytes())['sha256'],'archive_bytes':archive.stat().st_size} for role,raw in ref.items()]
    config={'source':'MTH','version':version,'inputs':{'source_data':['prepared']},'replay':{'reference_ref':'official'}}
    manifest={'configuration':config,'artifacts':{'official':{'artifact_type':'reference-inversion','source':'MTH','version':version,'data':{'reference_stage':'inversion-src'},'files':descriptor}}}
    plan={'source':'MTH','version':version,'output_files':list(ref),'input_files':inputs+[{'role':'cui_said_map','scope':'candidate','destination':str(prior.relative_to(target))}],
          'validation':{'bounds':{'start':899999999,'end':900001000},'input_identities':identities}}
    lock={'schema_version':1,'artifact_type':'ncimeta-native-release-lock','run_id':'synthetic-native-explanation','configuration':config,'manifest':manifest,'plan':plan}
    lock['manifest_sha256']=diagnostic.digest(manifest);lock['plan_sha256']=diagnostic.digest(plan);lock['lock_sha256']=diagnostic.digest(lock)
    validation=engine.validate_outputs(plan,target);assert validation['passed'],validation
    result={'source':'MTH','version':version,'run_id':lock['run_id'],'lock_sha256':lock['lock_sha256'],
        'comparison':{'validation':validation,'files':{role:{'reference':ident(raw),'candidate':ident(cur[role]),'exact_match':raw==cur[role]} for role,raw in ref.items()}},
        'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW','production_eligible':False}}
    report=diagnostic.diagnose(lock,target,result,examples=5)
    return lock,target,result,report,scratch


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label,reason=None):
        try:action()
        except (RuntimeError,ValueError,OSError) as error:
            if reason is not None:assert reason in str(error),(label,str(error))
            checks.append(label);return
        raise AssertionError(label)
    with tempfile.TemporaryDirectory(prefix='mth-native-explanation-') as temporary:
        lock,target,result,report,scratch=fixture(Path(temporary).resolve())
        before={str(p):(p.read_bytes(),p.stat().st_mode) for p in target.rglob('*') if p.is_file()}
        original=copy.deepcopy(result);proof=explain.explain(lock,target,result,report,scratch)
        good(proof['every_difference_explained'] and not proof['acceptance_changed'] and proof['raw_acceptance']==original['acceptance'],'full future-release diagnostic proof leaves strict DIFF unchanged')
        good(proof['output_explanations'][explain.ATTR]['native_prefix']['removed_native_records']==1 and proof['output_explanations'][explain.ATTR]['native_prefix']['added_native_records']==1,'native MRSTY/map deltas explain every prefix row and generated ID')
        good(proof['output_explanations'][explain.ATTR]['reference_prefix']['sha256']!=proof['output_explanations'][explain.ATTR]['candidate_prefix']['sha256'],'proof explicitly accounts for changed native attribute prefix, not only context suffix')
        good(proof['output_explanations'][explain.CTX]['corrected_native_bound_rows']==proof['output_explanations'][explain.CTXATTR]['corrected_native_bound_rows']==1,'both entire predicted context serializations/re-ID equal actual candidate hashes')
        good(proof['all_original_atom_allocations_exact'] and proof['full_retained_maps_predicted'] and len(proof['removed_raw_atoms'])==2,'all allocations and complete old/new mappings derived without release IDs/count constants')
        good(proof['generated_ID_reference_check']['no_generated_attribute_or_relationship_ID_references'],'exact source framework code/termgroup references checked by unchanged guard')
        good(proof['conservative_scratch_upper_bound_bytes']<2*1024**3 and not list(scratch.iterdir()),'scratch bound below2GiB and all temporary sorting data removed')
        good(result==original and {str(p):(p.read_bytes(),p.stat().st_mode) for p in target.rglob('*') if p.is_file()}==before,'native output bytes/modes and raw result remain unchanged')
        atoms=target/'src/classes_atoms.src';original_atoms=atoms.read_bytes()
        atoms.write_bytes(original_atoms.replace(b'SYNTHETIC NODE',b'UNEXPLAINED NODE'))
        bad=copy.deepcopy(result);bad['comparison']['files']['src/classes_atoms.src']['candidate']=ident(atoms.read_bytes())
        assert bad['comparison']['files']['src/classes_atoms.src']['exact_match'] is True
        assert bad['comparison']['files']['src/classes_atoms.src']['candidate']!=bad['comparison']['files']['src/classes_atoms.src']['reference']
        bad_report=copy.deepcopy(report);bad_report['raw_result_content_sha256']=diagnostic.digest(bad)
        reject(lambda:explain.explain(lock,target,bad,bad_report,scratch),'forged true exact flag cannot overclaim unequal unaffected output',
               'Raw exact-match flag contradicts candidate/reference identities')
        atoms.write_bytes(original_atoms)
        bad=copy.deepcopy(lock);bad['manifest_sha256']='0'*64;bad['lock_sha256']=diagnostic.digest({k:v for k,v in bad.items() if k!='lock_sha256'})
        reject(lambda:explain.explain(bad,target,result,report,scratch),'internally inconsistent manifest digest rejected')
        bad=copy.deepcopy(result);bad['comparison']['validation']['facts']['structure']['files']['attributes.src']['identifier_types_and_qualifiers']['ATTRIBUTE_ID|']=1
        bad_report=copy.deepcopy(report);bad_report['raw_result_content_sha256']=diagnostic.digest(bad)
        reject(lambda:explain.explain(lock,target,bad,bad_report,scratch),'generated attribute ID references cannot be hidden by re-ID prediction')
        bad_report=copy.deepcopy(report);bad_report['files'][explain.AUI]['row_multiset']['reference_only_examples'].pop()
        reject(lambda:explain.explain(lock,target,result,bad_report,scratch),'incomplete map examples cannot stand in for full mapping deltas')
        path=target/'src/attributes.src';raw=path.read_bytes();path.write_bytes(raw.replace(b'root',b'ROOT',1))
        reject(lambda:explain.explain(lock,target,result,report,scratch),'unexplained native prefix change rejected')
        path.write_bytes(raw)
        old_limit=explain.SORT_INPUT_LIMIT;explain.SORT_INPUT_LIMIT=1
        try:reject(lambda:explain.explain(lock,target,result,report,scratch),'sort input cap fails closed before exceeding scratch family')
        finally:explain.SORT_INPUT_LIMIT=old_limit
        good(not list(scratch.iterdir()),'failed explanation also removes all scratch data')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
