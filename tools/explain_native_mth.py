#!/usr/bin/env python3
"""Bounded read-only explanation of a retained-identity MTH difference family.

Derive identities from complete frozen diagnostics, then independently predict
full maps, native semantic-type attributes and one native-bound blank context.
Unknown changes fail closed. This never invokes the old audit(), changes strict
comparison acceptance, executes an inversion or writes native data. Only sort
scratch and one small reference helper are temporary; they are removed.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import threading

import audit_mth_corrections as wire
import diagnose_native_mth as diagnostic
from execute_release_mth import input_path

ATTR='src/attributes.src';CTX='src/contexts.src';CTXATTR='src/attributes.contexts-all.src'
AUI='src/aui_said_map';CUI='src/cui_said_map';RELCUI='src/rel_cui_said_map'
PREF='src/said.ptsaid';ORDER='src/ptsaid.order';RAW=diagnostic.RAW
CHANGED={ATTR,CTX,CTXATTR,AUI,CUI,RELCUI,PREF,ORDER,RAW}
SORT_INPUT_LIMIT=768*1024**2
SCRATCH_LIMIT=2*1024**3
SMALL_HELPER_LIMIT=64*1024**2
MAX_MATCHES=32


def require(value,message):
    if not value:raise RuntimeError(message)


class Observed:
    def __init__(self,handle):self.handle=handle;self.hash=hashlib.sha256();self.bytes=self.rows=0
    def read(self,size=-1):
        raw=self.handle.read(size);self.hash.update(raw);self.bytes+=len(raw);self.rows+=raw.count(b'\n');return raw
    def readline(self,size=-1):
        raw=self.handle.readline(size);self.hash.update(raw);self.bytes+=len(raw);self.rows+=raw.count(b'\n');return raw
    def __iter__(self):return self
    def __next__(self):
        raw=self.readline()
        if not raw:raise StopIteration
        return raw
    def identity(self):return {'sha256':self.hash.hexdigest(),'bytes':self.bytes,'rows':self.rows}


def _shown_row(value):
    require(value.get('truncated') is False,'Complete diagnostic row examples required, not truncated text')
    raw=value['text'].encode()
    require(diagnostic._identity_matches({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)},value),'Diagnostic row example hash/size differs')
    return raw


def _delta(report,role):
    value=report['files'][role]['row_multiset'];require(value.get('performed') is True,'Complete map Counter diagnostic required')
    result=[]
    for side in ('reference','candidate'):
        entries=value[side+'_only_examples'];counter=Counter()
        require(len(entries)<=MAX_MATCHES,'Difference family exceeds bounded map scope')
        for entry in entries:
            require(type(entry['occurrences']) is int and entry['occurrences']>0,'Invalid occurrence count')
            counter[_shown_row(entry['row'])]+=entry['occurrences']
        require(sum(counter.values())==value[side+'_only_occurrences'],'Diagnostic examples do not contain EVERY map delta')
        result.append(counter)
    return tuple(result)


def _fields(raw):return raw.removesuffix(b'\n').split(b'|')


def _native(lock,target,role,predicate):
    bundle=lock['configuration']['inputs']['source_data'][0]
    items=[item for item in lock['plan']['validation']['input_identities'] if item['role']==role and item['artifact']==bundle]
    require(len(items)==1,'One frozen current prepared native role required: '+role)
    item=items[0];rows=[];width={'MRCONSO.RRF':18,'MRSTY.RRF':6,'MRCXT.RRF':15}[role]
    with diagnostic.opened(input_path(item,target)) as incoming:
        source=Observed(incoming)
        for number,raw in enumerate(source,1):
            f=_fields(raw)
            if f[-1]==b'':f=f[:-1]
            require(len(f)==width and raw.endswith(b'|\n'),'Unexpected native wire shape: '+role)
            if predicate(f):
                require(len(rows)<MAX_MATCHES,'Native target family exceeds bounded scope')
                rows.append((number,raw,f))
        require(diagnostic._identity_matches(source.identity(),item),'Frozen native input changed: '+role)
    return rows,source.identity()


def _mapping_hash(values):
    value=hashlib.sha256()
    for key in sorted(values):value.update(key+b'|'+values[key]+b'\n')
    return value.hexdigest()


def _derive(lock,target,result,report,refs):
    old_cui,new_cui=_delta(report,CUI);require((old_cui,new_cui)==_delta(report,RELCUI),'CUI/relationship CUI deltas differ')
    require(sum(old_cui.values())==sum(new_cui.values())==1,'Scope requires one removed and one restored CUI binding')
    old_cui_row=next(iter(old_cui));new_cui_row=next(iter(new_cui));old_id,old_said=_fields(old_cui_row);new_id,new_said=_fields(new_cui_row)
    require(old_id!=new_id,'Same-CUI retargeting requires a separate explanation')
    old_aui,new_aui=_delta(report,AUI)
    require(sum(new_aui.values())==1 and 0<sum(old_aui.values())<=MAX_MATCHES,'Scope requires one restored AUI and bounded excluded AUIs')
    restored_aui,restored_cui,restored_said=_fields(next(iter(new_aui)))
    require((restored_cui,restored_said)==(new_id,new_said),'Restored AUI/CUI identities disagree')
    removed={}
    for raw,count in old_aui.items():
        aui,cui,said=_fields(raw);require(count==1 and cui==old_id,'Removed AUI family differs from removed CUI')
        removed[said]=aui
    require(old_said in removed,'Old first-current CUI binding is not a removed atom')
    contexts,native_ctx=_native(lock,target,'MRCXT.RRF',lambda f:f[2]==restored_aui or f[10]==restored_aui)
    ancestors=[f for _,_,f in contexts if f[2]==restored_aui and f[6]==b'ANC' and f[10]!=restored_aui]
    require(len(ancestors)==1,'One explicit native ancestor is required for this blank-node family')
    parent_aui=ancestors[0][10];parent_cui=ancestors[0][9]
    wanted_auis=set(removed.values())|{restored_aui,parent_aui}
    conso,native_conso=_native(lock,target,'MRCONSO.RRF',lambda f:f[7] in wanted_auis)
    native_atoms={f[7]:f for _,_,f in conso}
    require(len(native_atoms)==len(conso)==len(wanted_auis),'Each affected/root AUI needs exactly one native atom')
    old_maps,new_maps={},{};old_aui_hash,new_aui_hash,retained_hash,unfiltered_hash=[hashlib.sha256() for _ in range(4)]
    raw_targets={};removed_rows=[]
    with diagnostic.opened(target/'src/classes_atoms.unfiltered.raw') as incoming:
        for raw in incoming:
            unfiltered_hash.update(raw);f=_fields(raw);require(len(f)==17,'Raw atom layout differs')
            excluded=f[1]==b'SRC' and f[3]==b'V-CCS_2005'
            if excluded:
                require(f[0] in removed and f[16]==removed[f[0]] and f[15]==old_id,'Unexpected native CCS exclusion')
                removed_rows.append(raw)
            else:retained_hash.update(raw)
            if f[16] in wanted_auis:raw_targets[f[16]]=f
            if f[14]!=b'N':continue
            if f[16]!=restored_aui:
                old_aui_hash.update(f[16]+b'|'+f[15]+b'|'+f[0]+b'\n');old_maps.setdefault(f[15],f[0])
            if not excluded:
                new_aui_hash.update(f[16]+b'|'+f[15]+b'|'+f[0]+b'\n');new_maps.setdefault(f[15],f[0])
            require(max(len(old_maps),len(new_maps))<=4_000_000,'Map derivation exceeds bounded memory scope')
    require(len(removed_rows)==len(removed) and set(raw_targets)==wanted_auis,'Incomplete affected raw allocations')
    require(unfiltered_hash.hexdigest()==refs[RAW]['sha256'],'Original unfiltered atom allocation is not byte-exact')
    require(retained_hash.hexdigest()==result['comparison']['files'][RAW]['candidate']['sha256'],'Retained raw differs from the source retention predicate')
    require(old_aui_hash.hexdigest()==refs[AUI]['sha256'] and new_aui_hash.hexdigest()==result['comparison']['files'][AUI]['candidate']['sha256'],'Full AUI map changes not predicted by retained native atoms')
    for aui,f in raw_targets.items():
        native=native_atoms[aui]
        require((f[15],f[16],f[1],f[2],f[3],f[7])==(native[0],native[7],native[11],native[11]+b'/'+native[12],native[13],native[14]),'Native atom/raw allocation identity differs')
    require(raw_targets[restored_aui][0]==restored_said and raw_targets[parent_aui][15]==parent_cui,'Restored/root raw binding differs')
    with diagnostic.opened(target/'src/cui_splitonly_said_map') as incoming:
        for raw in incoming:
            cui,said=_fields(raw);require(cui not in old_maps and cui not in new_maps,'Split-only/current CUI overlap')
            old_maps[cui]=new_maps[cui]=said
    require(_mapping_hash(old_maps)==refs[CUI]['sha256']==refs[RELCUI]['sha256'],'Full original CUI maps not predicted by original current bindings')
    require(_mapping_hash(new_maps)==result['comparison']['files'][CUI]['candidate']['sha256']==result['comparison']['files'][RELCUI]['candidate']['sha256'],'Full retained CUI maps not predicted')
    actual_old=Counter(cui+b'|'+said+b'\n' for cui,said in old_maps.items() if new_maps.get(cui)!=said)
    actual_new=Counter(cui+b'|'+said+b'\n' for cui,said in new_maps.items() if old_maps.get(cui)!=said)
    require((actual_old,actual_new)==(old_cui,new_cui),'Unaccounted full CUI-map bindings')
    sty,native_sty=_native(lock,target,'MRSTY.RRF',lambda f:f[0] in (old_id,new_id))
    removed_attr,added_attr=Counter(),Counter();version=lock['configuration']['version'].encode()
    for _,_,f in sty:
        for mapping,other,counter in ((old_maps,new_maps,removed_attr),(new_maps,old_maps,added_attr)):
            if mapping.get(f[0])!=other.get(f[0]) and f[0] in mapping:
                content=wire.attribute([mapping[f[0]],b'C',b'SEMANTIC_TYPE',f[3],b'E-'+version,b'R',b'Y',b'N',b'N',b'SRC_ATOM_ID',b'',b'',b''])
                counter[content]+=1
    require(removed_attr and added_attr,'Native semantic-type explanation is empty')
    node=raw_targets[restored_aui];parent=raw_targets[parent_aui]
    require(all(f[3]==node[1] for _,_,f in contexts),'Native context namespaces differ')
    self_contexts=[f for _,_,f in contexts if f[2]==f[10]==restored_aui and f[6]==b'CCP']
    require(len(self_contexts)==1,'Exactly one native self context is required')
    del old_maps,new_maps
    return {'removed':removed,'removed_raw':removed_rows,'node':node,'parent':parent,
        'context_root_label':ancestors[0][8],'context_node_label':self_contexts[0][8],
        'removed_attr':removed_attr,'added_attr':added_attr,
        'native':{name:{**meta,'matched_rows':[{'line':n,'row':raw.decode()} for n,raw,_ in rows]} for name,meta,rows in (
            ('MRCONSO.RRF',native_conso,conso),('MRSTY.RRF',native_sty,sty),('MRCXT.RRF',native_ctx,contexts))}}


def _sort_hash(rows,scratch,native_count=None,stable_subject=False):
    command=['/usr/bin/sort','-S','128M','-T',str(scratch)]
    if stable_subject:command+=['-s','-t','|','-k1,1']
    errors=[];fed={'bytes':0,'rows':0};value=hashlib.sha256();size=count=0
    with tempfile.TemporaryFile(dir=scratch) as stderr:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,env=dict(os.environ,LC_ALL='C'))
        def write():
            try:
                for raw in rows:
                    fed['bytes']+=len(raw);fed['rows']+=1
                    require(fed['bytes']<=SORT_INPUT_LIMIT,'Sort input exceeds bounded diagnostic family')
                    process.stdin.write(raw)
            except BaseException as error:errors.append(error)
            finally:process.stdin.close()
        writer=threading.Thread(target=write,daemon=True);writer.start()
        try:
            for raw in process.stdout:
                count+=1
                if native_count is not None:raw=str(native_count+count).encode()+b'|'+raw
                value.update(raw);size+=len(raw)
            process.stdout.close();writer.join(timeout=1800);require(not writer.is_alive(),'Sort writer did not finish')
            code=process.wait(timeout=1800)
            if errors:raise errors[0]
            require(code==0,'C-locale sort failed')
        finally:
            if process.poll() is None:process.kill();process.wait()
        require(count==fed['rows'],'Sorting changed duplicate multiplicity')
    return {'sha256':value.hexdigest(),'bytes':size,'rows':count,'sort_input_bytes':fed['bytes']}


def explain(lock,target,result,report,scratch_parent,progress=lambda message:None):
    target=Path(target);scratch_parent=Path(scratch_parent)
    if 'records' in result:result=result['records']['result.json']
    if 'report' in report:report=report['report']
    require(lock.get('schema_version')==1 and lock.get('artifact_type')=='ncimeta-native-release-lock' and
            lock['lock_sha256']==diagnostic.digest({k:v for k,v in lock.items() if k!='lock_sha256'}),'Frozen lock changed')
    require(lock['configuration']==lock['manifest']['configuration'] and
            lock['manifest_sha256']==diagnostic.digest(lock['manifest']) and lock['plan_sha256']==diagnostic.digest(lock['plan']) and
            lock['plan']['source']=='MTH' and lock['plan']['version']==lock['configuration']['version'],'Frozen manifest/plan identity differs')
    require(report['lock_sha256']==result['lock_sha256']==lock['lock_sha256'],'Lock/result/diagnostic identity differs')
    require(result['source']==report['source']=='MTH' and result['version']==report['version']==lock['configuration']['version'] and
            result['run_id']==report['run_id']==lock['run_id'],'Run/release identity differs')
    require(report['raw_result_content_sha256']==diagnostic.digest(result),'Diagnostic is not bound to the original raw result')
    require(lock['configuration']['source']=='MTH' and target.name==lock['configuration']['version'],'Wrong source/target')
    require(result['comparison']['validation']['passed'],'Clean independent candidate physical validation is required')
    require(result['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW','This helper explains a preserved strict-difference result only')
    reference=lock['manifest']['artifacts'][lock['configuration']['replay']['reference_ref']]
    require((reference['artifact_type'],reference['source'],reference['version'],reference['data'].get('reference_stage'))==
            ('reference-inversion','MTH',lock['configuration']['version'],'inversion-src'),'Current-release inversion reference required')
    refs={item['role']:item for item in reference['files']}
    files=result['comparison']['files'];require(set(files)==set(refs),'Incomplete frozen comparison')
    require(len(refs)==len(reference['files']) and set(refs)==set(lock['plan']['output_files']),'Duplicate/incomplete declared outputs')
    require({name for name,item in files.items() if not item['exact_match']}==CHANGED,'Unexpected difference family; do not broaden this explanation')
    require(scratch_parent.resolve()==scratch_parent and scratch_parent.is_dir() and not scratch_parent.is_relative_to(target.parent),'Scratch must be outside all replaceable source trees')
    watched={}
    for name,item in files.items():
        require(diagnostic._identity_matches(item['reference'],refs[name]),'Reference descriptor differs')
        require(type(item['exact_match']) is bool and item['exact_match']==diagnostic._identity_matches(item['reference'],item['candidate']),
                'Raw exact-match flag contradicts candidate/reference identities')
        path=target/name;watched[path]=diagnostic._stamp(path.lstat())
        with diagnostic.opened(path) as incoming:
            source=Observed(incoming)
            while source.read(4*1024**2):pass
            require(diagnostic._identity_matches(source.identity(),item['candidate']),'Output changed since raw result: '+name)
        if name in report['files']:
            require(diagnostic._identity_matches(report['files'][name]['reference'],refs[name]) and
                    diagnostic._identity_matches(report['files'][name]['comparisons']['candidate']['candidate'],item['candidate']),'Diagnostic file binding differs')
    generated_ids=wire.generated_id_reference_check(result['comparison']['validation']['facts']['structure'],target/'src/rel_src')
    progress('Deriving native retained identity and semantic-type records')
    derived=_derive(lock,target,result,report,refs)
    old_native=report['files'][ATTR]['reference']['rows']-report['files'][CTXATTR]['reference']['rows']
    new_native=report['files'][ATTR]['comparisons']['candidate']['candidate']['rows']-report['files'][CTXATTR]['comparisons']['candidate']['candidate']['rows']
    require(new_native==old_native-sum(derived['removed_attr'].values())+sum(derived['added_attr'].values()),'Native attribute counts differ beyond predicted MRSTY changes')
    node,parent=derived['node'],derived['parent'];node_said,parent_said=node[0],parent[0]
    wanted={refs[name]['archive_member']:name for name in (ATTR,CTX,CTXATTR,PREF,ORDER)}
    archive_keys={(refs[name]['uri'],refs[name]['archive_sha256'],refs[name]['archive_bytes']) for name in (ATTR,CTX,CTXATTR,PREF,ORDER)}
    require(len(archive_keys)==1,'Selected explanation members must share one frozen source archive')
    from urllib.parse import urlsplit,unquote
    uri,archive_sha,archive_bytes=next(iter(archive_keys));parsed=urlsplit(uri)
    require(parsed.scheme=='file' and not parsed.netloc,'A frozen local archive is required')
    archive_path=Path(unquote(parsed.path));found=set();out={};removed_targets=Counter();remaining_targets=Counter()
    pref_deleted=report['files'][PREF]['deletion_only'];require(pref_deleted['ordered_deletion_only'],'Preferred helper is not deletion-only')
    require(pref_deleted['deleted_reference_occurrences']==len(pref_deleted['deleted_examples'])==len(derived['removed']),'Incomplete removed preferred helper evidence')
    for example in pref_deleted['deleted_examples']:
        said,preferred=_fields(_shown_row(example['row']));require(said in derived['removed'],'Unexpected preferred deletion')
        removed_targets[preferred]+=1
    require(max(refs[CTX]['bytes'],refs[CTXATTR]['bytes'])+1024<=SORT_INPUT_LIMIT and refs[ORDER]['bytes']<=SMALL_HELPER_LIMIT,'Reference exceeds conservative <2GiB scratch family')
    with tempfile.TemporaryDirectory(prefix='.mth-explanation-',dir=scratch_parent) as temporary:
        scratch=Path(temporary);order_file=scratch/'reference-preferred-order'
        with diagnostic.opened(archive_path) as handle:
            compressed=diagnostic.Compressed(handle)
            with tarfile.open(fileobj=compressed,mode='r|gz') as archive:
                seen=set()
                for member in archive:
                    name=member.name.removeprefix('./').rstrip('/')
                    if name=='.':continue
                    diagnostic._relative(name);require(name not in seen,'Duplicate archive member');seen.add(name)
                    if name not in wanted:continue
                    role=wanted[name];require(member.isfile() and member.size==refs[role]['bytes'],'Reference member shape differs')
                    progress('Predicting '+role)
                    with archive.extractfile(member) as raw_source:
                        source=Observed(raw_source)
                        if role==ATTR:
                            with diagnostic.opened(target/ATTR) as candidate:
                                current=Observed(candidate)
                                transition=wire.compare_transition(source,current,derived['removed_attr'],derived['added_attr'],old_native,new_native)
                                old_prefix=source.identity();new_prefix=current.identity()
                                old_suffix=Observed(source);new_suffix=Observed(current)
                                while old_suffix.read(4*1024**2):pass
                                while new_suffix.read(4*1024**2):pass
                                require(diagnostic._identity_matches(old_suffix.identity(),refs[CTXATTR]) and diagnostic._identity_matches(new_suffix.identity(),files[CTXATTR]['candidate']),'Full attribute suffix is not the corresponding context helper')
                                out[role]={'native_prefix':transition,'reference_prefix':old_prefix,'candidate_prefix':new_prefix,'both_full_context_suffixes_exact':True}
                        elif role in (CTX,CTXATTR):
                            changed=[0]
                            def corrected():
                                for number,raw in enumerate(source,1):
                                    f=_fields(raw)
                                    if role==CTX:
                                        require(len(f)==19,'Context layout differs')
                                        if not f[0]:
                                            require(not f[11] and f[1]==b'PAR' and f[3]==f[7]==f[14]==parent_said and f[4]==f[5]==node[1] and f[12]==f[15]==b'SRC_ATOM_ID','Blank context is not bound to the native restored/root identities')
                                            f[0]=f[11]=node_said;raw=wire.row(f);changed[0]+=1
                                    else:
                                        require(len(f)==15 and f[0]==str(old_native+number).encode(),'Original context-attribute generated IDs differ')
                                        if not f[1]:
                                            old=b'::~~SRC_ATOM_ID~~~SRC_ATOM_ID~';new=b'::~'+node_said+b'~SRC_ATOM_ID~~'+node_said+b'~SRC_ATOM_ID~'
                                            require(f[2:4]==[b'S',b'CONTEXT'] and f[5]==node[1] and f[10]==b'SRC_ATOM_ID' and f[4].count(old)==1 and
                                                    derived['context_node_label'] in f[4] and derived['context_root_label'] in f[4],
                                                    'Blank CONTEXT attribute is not native-bound')
                                            f[1]=node_said;f[4]=f[4].replace(old,new);f[13]=hashlib.md5(f[4]).hexdigest().encode();changed[0]+=1
                                        raw=wire.row(f[1:])
                                    yield raw
                            predicted=_sort_hash(corrected(),scratch,new_native if role==CTXATTR else None,role==CTXATTR)
                            require(changed[0]==1,'Scope requires exactly one native-bound blank node per context representation')
                            require(diagnostic._identity_matches(predicted,files[role]['candidate']),'Full predicted context serialization differs')
                            out[role]={'corrected_native_bound_rows':changed[0],'full_predicted_identity':predicted,'all_other_content_and_duplicate_counts_preserved':True}
                        elif role==PREF:
                            value=hashlib.sha256();deleted=[]
                            for raw in source:
                                said,preferred=_fields(raw)
                                if said in derived['removed']:deleted.append(raw)
                                else:
                                    value.update(raw)
                                    if preferred in removed_targets:remaining_targets[preferred]+=1
                            require(len(deleted)==len(derived['removed']) and value.hexdigest()==files[PREF]['candidate']['sha256'],'Complete preferred mapping changes exceed removed native atoms')
                            out[role]={'removed_rows':[raw.decode() for raw in deleted],'full_candidate_hash_predicted':True}
                        else:
                            with order_file.open('xb') as destination:
                                for raw in source:destination.write(raw)
                        require(diagnostic._identity_matches(source.identity(),refs[role]),'Selected reference bytes differ: '+role)
                    found.add(name)
            require(compressed.finish()=={'sha256':archive_sha,'bytes':archive_bytes},'Full compressed archive differs')
        require(found==set(wanted),'Missing reference explanation members')
        value=hashlib.sha256();deleted=[]
        with order_file.open('rb') as incoming:
            for raw in incoming:
                identifier=raw.rstrip(b'\n')
                if identifier in removed_targets and not remaining_targets[identifier]:deleted.append(identifier)
                else:value.update(raw)
        require(value.hexdigest()==files[ORDER]['candidate']['sha256'],'Preferred ordering differs beyond unreferenced removed targets')
        require(report['files'][ORDER]['deletion_only']['ordered_deletion_only'] and len(deleted)==report['files'][ORDER]['deletion_only']['deleted_reference_occurrences'],'Preferred-order deletion count differs')
        out[ORDER]={'removed_targets':[value.decode() for value in deleted],'full_candidate_hash_predicted':True}
    require(all(diagnostic._stamp(path.lstat())==before for path,before in watched.items()),'Output changed during explanation')
    return {'schema_version':1,'artifact_type':'ncimeta-native-mth-difference-explanation','source':'MTH','version':lock['configuration']['version'],
        'lock_sha256':lock['lock_sha256'],'raw_result_content_sha256':diagnostic.digest(result),'diagnostic_content_sha256':diagnostic.digest(report),
        'every_difference_explained':True,'scope':'Bounded native-derived diagnostic only; no acceptance/waiver or native-data modification.',
        'raw_acceptance':copy.deepcopy(result['acceptance']),'acceptance_changed':False,'native_data_modified':False,
        'all_original_atom_allocations_exact':True,'full_retained_maps_predicted':True,
        'removed_raw_atoms':[raw.decode() for raw in derived['removed_raw']],
        'restored_native_identity':{'said':node[0].decode(),'cui':node[15].decode(),'aui':node[16].decode(),'source':node[1].decode(),'code':node[3].decode()},
        'native_evidence':derived['native'],'output_explanations':out,'unaffected_outputs_exact':sorted(set(files)-CHANGED),
        'generated_ID_reference_check':generated_ids,
        'scratch_removed':True,'conservative_scratch_upper_bound_bytes':2*SORT_INPUT_LIMIT+SMALL_HELPER_LIMIT+64*1024**2,
        'scratch_limit_bytes':SCRATCH_LIMIT,'explanation_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('lock','target','result','diagnostic','scratch-parent'):parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    value=explain(diagnostic.load(args.lock),args.target,diagnostic.load(args.result),diagnostic.load(args.diagnostic),args.scratch_parent,
                  progress=lambda message:print(message,flush=True,file=__import__('sys').stderr))
    print(json.dumps(value,indent=2))


if __name__=='__main__':main()
