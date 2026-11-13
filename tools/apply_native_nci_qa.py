#!/usr/bin/env python3
"""Prove one reviewed NCIt termgroup adjustment in a disposable QA view.

Only one temporary classes file is written. Original native data, result and
comparison remain unchanged; no insertion or persistent application is allowed.
"""
import copy
import datetime
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile
import tempfile

import compare_nci_core as core
import diagnose_native_nci as diagnostic
import execute_release_nci as source
import release_manifest as manifests

OUTPUTS=tuple('src/'+name for name in core.FIELDS)
NATIVE_ROLES=set(source.ROLES)
CLASS='src/classes_atoms.src'
CLASS_LIMIT=256*1024**2
COMPARISON_INPUT_LIMIT=512*1024**2
LINE_LIMIT=2*1024**2
SAFE_REFERENCE_TYPES={'SRC_ATOM_ID','SOURCE_CUI','CODE_SOURCE','CUI'}


def require(value,message):
    if not value:raise ValueError(message)


def _same(actual,expected):return all(actual[key]==expected[key] for key in ('sha256','bytes'))


def _hash(path):
    value=hashlib.sha256();size=rows=0
    with manifests._open(path) as handle:
        for block in iter(lambda:handle.read(4*1024**2),b''):
            value.update(block);size+=len(block);rows+=block.count(b'\n')
    return {'sha256':value.hexdigest(),'bytes':size,'rows':rows}


def _rows(handle):
    while True:
        raw=handle.readline(LINE_LIMIT+1)
        if not raw:return
        require(len(raw)<=LINE_LIMIT and raw.endswith(b'\n') and b'\r' not in raw and b'\0' not in raw,'Uncharacterized output row wire shape')
        yield raw


def _decision(lock,result,decision,references):
    config=lock['configuration'];version=config['version']
    require(decision.get('schema_version')==1 and decision.get('artifact_type')=='ncimeta-qa-adjustment', 'Typed QA decision required')
    require(decision.get('review_status')=='reviewed' and all(isinstance(decision.get(k),str) and decision[k].strip() for k in ('decision_id','reviewer','reviewed_at','review_basis','actor')), 'An explicit reviewed QA decision with reviewer/basis/time is required')
    reviewed=datetime.datetime.fromisoformat(decision['reviewed_at'].replace('Z','+00:00'))
    require(reviewed.tzinfo is not None,'Review time requires an explicit timezone')
    require((decision.get('source'),decision.get('version'),decision.get('lock_sha256'),decision.get('stage'),decision.get('output_role'))==
            ('NCI',version,lock['lock_sha256'],'post-inversion-QA',CLASS),'QA decision belongs to another source/release/lock/stage')
    require(decision.get('application_authorized') is False and decision.get('raw_comparison_changed') is False,'This policy permits a disposable QA view only')
    require(all(isinstance(decision.get(k),str) for k in ('before_row','after_row')),'Exact UTF-8 before/after row text required')
    before,after=decision['before_row'].encode(),decision['after_row'].encode()
    require(0<len(before)<=65536 and 0<len(after)<=65536 and before.endswith(b'\n') and after.endswith(b'\n') and
            all(raw.count(b'\n')==1 and b'\r' not in raw and b'\0' not in raw for raw in (before,after)), 'Exact single complete before/after rows required')
    a,b=[raw[:-1].split(b'|') for raw in (before,after)]
    require(len(a)==len(b)==len(core.FIELDS['classes_atoms.src']) and [i for i,(x,y) in enumerate(zip(a,b)) if x!=y]==[2], 'Only one termgroup field may change')
    field=decision['allowed_field_change']
    require(field=={'position':2,'name':'termgroup','before':a[2].decode(),'after':b[2].decode()},'Declared field change differs from exact rows')
    require(re.fullmatch(rb'[1-9][0-9]*',a[0]) is not None and a[2].split(b'/',1)[0]==b[2].split(b'/',1)[0]==a[1], 'Termgroup change must preserve the atom/source identity')
    require(decision['row_key']=={'source_atom_id':a[0].decode(),'source_cui':a[10].decode(),'code':a[3].decode(),'atom_name':a[7].decode()},'QA semantic row key differs')
    require(decision['before_row_sha256']==hashlib.sha256(before).hexdigest() and decision['after_row_sha256']==hashlib.sha256(after).hexdigest(),'Exact reviewed row hashes differ')
    bindings=decision['bindings'];files=result['comparison']['files']
    require(isinstance(bindings,dict),'Typed QA evidence bindings required')
    require(bindings['candidate_file_sha256']==files[CLASS]['candidate']['sha256'] and bindings['official_file_sha256']==references[CLASS]['sha256'], 'Reviewed class file bindings differ')
    require(type(bindings.get('qa_line')) is int and bindings['qa_line']>0 and re.fullmatch(r'[0-9a-f]{64}',bindings.get('qa_member_sha256','')),'Hash-bound QA member/line evidence required')
    manifests._relative(bindings['qa_member'])
    require(PurePosixPath(bindings['qa_member']).parts[:3]==(version,'etc','qa'),'QA evidence is outside the current source QA directory')
    require(isinstance(bindings.get('native_inputs'),dict),'Complete native input bindings required')
    return before,after,bindings


def _validate(lock,target,paths):
    plan=lock['plan'];v=plan['validation'];bounds=v['source_atom_ids']
    require(bounds==lock['configuration']['source_atom_ids'],'Validation bounds differ from the common configuration')
    require(type(v['saved_hierarchy_root']['root_atom_id']) is int and v['saved_hierarchy_root']['root_atom_id']>0,'Explicit saved root source-atom identity required')
    groups=source._metadata(target/'src/termgroups.src',source.source_plan.TERMGROUP_FIELDS)
    sources=source._metadata(target/'src/sources.src',source.source_plan.SOURCE_FIELDS)
    declared={row['termgroup_name'].encode() for row in groups}
    structure=core.structure(paths,v['saved_hierarchy_root']['root_atom_id'],declared)
    require(structure['checks_passed'],'Post-QA output structures, digests, termgroups or references failed')
    require(structure['atom_ids']['minimum']>=bounds['start'] and structure['atom_ids']['maximum']<=bounds['end'],'Post-QA atom IDs escape the frozen inclusive range')
    known={row['source_name'].encode() for row in sources}|{b'SRC'};atom_ids=set()
    with manifests._open(paths['classes_atoms.src']) as handle:
        for raw in _rows(handle):
            f=raw[:-1].split(b'|');value=f[0]
            require(re.fullmatch(rb'[1-9][0-9]*',value) is not None and value not in atom_ids,'Post-QA atom IDs must remain canonical, positive and unique')
            atom_ids.add(value)
            require(f[1] in known and f[2].split(b'/',1)[0]==f[1],'Post-QA source/termgroup differs from frozen source metadata')
    for name in ('attributes.src','relationships.src'):
        seen=set()
        with manifests._open(paths[name]) as handle:
            for raw in _rows(handle):
                value=raw.split(b'|',1)[0]
                require(re.fullmatch(rb'[1-9][0-9]*',value) is not None and value not in seen,'Post-QA generated IDs must remain canonical, positive and unique: '+name)
                seen.add(value)
    for name,item in structure['files'].items():
        require(set(item['identifier_types'])<=SAFE_REFERENCE_TYPES,'Unreviewed reference type could depend on generated attribute IDs: '+name)
    return {'passed':True,'issues':[],'facts':{'structure':structure,'source_atom_ids':copy.deepcopy(bounds)}},declared


def apply_and_validate(lock,target,result,decision,scratch_parent,progress=lambda message:None):
    """Return a complete bounded proof or fail closed on any unmodeled change."""
    if 'records' in result:result=result['records']['result.json']
    target=Path(target);scratch_parent=Path(scratch_parent);original_result=copy.deepcopy(result)
    require(lock.get('artifact_type')=='ncimeta-native-release-lock' and lock.get('schema_version')==1 and
            lock['lock_sha256']==manifests.digest({k:v for k,v in lock.items() if k!='lock_sha256'}),'Frozen native lock changed')
    config=lock['configuration'];plan=lock['plan']
    source._version(config['version'])
    require(config==lock['manifest']['configuration'] and lock['manifest_sha256']==manifests.digest(lock['manifest']) and lock['plan_sha256']==manifests.digest(plan), 'Frozen manifest/configuration/plan differs')
    require(config['source']=='NCI' and target.name==config['version'] and plan['source']=='NCI' and plan['version']==config['version'],'QA target/source/release differs')
    require((result['source'],result['version'],result['run_id'],result['lock_sha256'])==('NCI',config['version'],lock['run_id'],lock['lock_sha256']), 'Completed result is bound to another request')
    require(result['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW' and result.get('declared_inputs_unchanged') is True and result.get('insertion_executed') is False and result.get('production_eligible') is False,'A preserved dev-only strict-difference result is required')
    require(config['output_stage']==config['replay']['reference_stage']=='inversion-src' and config['replay']['comparison_profile']=='exact','Only the pre-insertion strict comparison stage is supported')
    reference=lock['manifest']['artifacts'][config['replay']['reference_ref']]
    require((reference['artifact_type'],reference['source'],reference['version'],reference['data'].get('reference_stage'))==('reference-inversion','NCI',config['version'],'inversion-src'),'Current-release inversion oracle required')
    refs={x['role']:x for x in reference['files']};files=result['comparison']['files']
    require(len(reference['files'])==5 and set(refs)==set(files)==set(plan['output_files'])==set(OUTPUTS),'Exactly five complete output bindings required')
    for name,item in files.items():
        require(_same(item['reference'],refs[name]),'Raw comparison reference differs from lock')
        require(type(item['exact_match']) is bool and item['exact_match']==_same(item['candidate'],item['reference']),'Raw exact-match flag differs from hashes')
        require(max(item['candidate']['bytes'],item['reference']['bytes'])<=COMPARISON_INPUT_LIMIT,'Output exceeds bounded comparison family')
    before,after,bindings=_decision(lock,result,decision,refs)
    require(files[CLASS]['candidate']['bytes']+len(after)-len(before)<=CLASS_LIMIT,'Temporary class view exceeds bounded scratch size')
    require(scratch_parent.resolve()==scratch_parent and scratch_parent.is_dir() and not scratch_parent.is_relative_to(target.parent),'Scratch must be outside all replaceable source trees')
    watched={}
    def observe(path):
        diagnostic._regular(path);watched[path]=diagnostic._stamp(path)
    paths={PurePosixPath(name).name:target/name for name in OUTPUTS}
    for name,item in files.items():
        path=target/name;observe(path)
        require(_same(_hash(path),item['candidate']),'Retained raw output changed after the native result: '+name)
    for name,item in plan['validation']['state_files'].items():
        observe(target/name);source._check_file(target,name,item)
    for item in plan['generated_files']:
        observe(target/item['relative_path']);source._check_file(target,item['relative_path'],item)
    native=plan['validation']['native_inputs'];require(set(native)==NATIVE_ROLES,'Complete five native roles required')
    observed_native={}
    progress('Verifying the five exact native publisher inputs')
    for role,item in native.items():
        manifests._relative(item['relative_path']);path=target/item['relative_path'];observe(path)
        value=_hash(path);require(_same(value,item),'Frozen native publisher input changed: '+role)
        observed_native[config['version']+'/'+item['relative_path']]=value
    require(observed_native==bindings['native_inputs'],'Reviewed QA decision is bound to another complete native input set')
    archives={(x['uri'],x.get('archive_format'),x.get('archive_sha256'),x.get('archive_bytes')) for x in refs.values()}
    require(len(archives)==1,'Five official outputs must bind one complete archive')
    uri,kind,archive_sha,archive_bytes=next(iter(archives));require(kind=='tar.gz','Only a frozen tar.gz oracle is supported')
    require(bindings['official_archive_sha256']==archive_sha,'Reviewed archive differs')
    archive=manifests.location(refs[CLASS],False);require(archive is not None,'A local immutable reference archive is required');observe(archive)
    wanted={}
    for role,item in refs.items():
        manifests._relative(item['archive_member'])
        if item['archive_member']!=config['version']+'/'+role:
            proof=reference['data'].get('attribute_stage_proof')
            require(role=='src/attributes.src' and item['archive_member']==config['version']+'/src/attributes.orig' and isinstance(proof,dict) and
                    proof.get('original_member')==item['archive_member'] and proof.get('original_sha256')==item['sha256'] and proof.get('archive_sha256')==archive_sha,
                    'Official member is outside the explicitly proven current inversion stage')
        require(item['archive_member'] not in wanted,'Two roles select one archive member')
        wanted[item['archive_member']]=role
    qa_member=bindings['qa_member'];require(qa_member not in wanted,'QA evidence cannot substitute for an official output')
    found=set();compared={};qa_line=None;qa_rows=0;view_identity=None
    with tempfile.TemporaryDirectory(prefix='.nci-reviewed-qa-',dir=scratch_parent) as directory:
        view=Path(directory)/'classes_atoms.src';changed=0
        progress('Building one disposable exact-row QA class view')
        with manifests._open(target/CLASS) as incoming,view.open('xb') as out:
            for raw in _rows(incoming):
                if raw==before:raw=after;changed+=1
                out.write(raw)
                require(out.tell()<=CLASS_LIMIT,'Temporary class view exceeds bounded scratch size')
        require(changed==1,'Reviewed before row must occur exactly once')
        view.chmod(0o444);view_identity=_hash(view)
        require(_same(view_identity,refs[CLASS]),'Full adjusted classes file is not the exact reviewed official file')
        qa_paths=dict(paths);qa_paths['classes_atoms.src']=view
        progress('Validating complete post-QA outputs through the existing NCIt structure checker')
        validation,declared=_validate(lock,target,qa_paths)
        with manifests._open(archive) as incoming:
            hashed=diagnostic._HashReader(incoming)
            with tarfile.open(fileobj=hashed,mode='r|gz') as stream:
                seen=set()
                for member in stream:
                    name=member.name.removeprefix('./').rstrip('/')
                    if name=='.':continue
                    manifests._relative(name);require(name not in seen,'Duplicate archive member');seen.add(name)
                    if name==qa_member:
                        require(member.isfile(),'QA evidence must be a regular archive member')
                        value=hashlib.sha256()
                        with stream.extractfile(member) as handle:
                            number=0
                            while True:
                                raw=handle.readline(LINE_LIMIT+1)
                                if not raw:break
                                require(len(raw)<=LINE_LIMIT,'QA evidence line exceeds bounded scope')
                                number+=1
                                value.update(raw);qa_rows=number
                                if number==bindings['qa_line']:qa_line=raw.decode('utf-8').rstrip('\r\n')
                        require(value.hexdigest()==bindings['qa_member_sha256'] and qa_line is not None,'Full QA member hash or bound line differs')
                        expected='****ERR: VUndefinedTG_'+decision['row_key']['source_atom_id']+' => '+decision['allowed_field_change']['before']
                        require(qa_line.strip()==expected,'Bound QA line does not identify the exact undefined before termgroup/atom')
                        found.add(name)
                    elif name in wanted:
                        role=wanted[name];require(member.isfile() and member.size==refs[role]['bytes'],'Official member shape/size differs')
                        progress('Comparing every post-QA row and duplicate count: '+role)
                        with stream.extractfile(member) as handle:compared[role]=diagnostic._compare(PurePosixPath(role).name,qa_paths[PurePosixPath(role).name],handle,declared|diagnostic.FRAMEWORK)
                        require(_same(compared[role]['reference'],refs[role]),'Full official member hash differs')
                        found.add(name)
            require(hashed.finish()==(archive_sha,archive_bytes),'Complete compressed reference archive hash/size differs')
        require(found==set(wanted)|{qa_member},'Missing official output or QA evidence member')
        for name in (CLASS,'src/relationships.src','src/mergefacts.src'):
            require(compared[name]['ordered_bytes_equal'],'Unexplained post-QA whole-file difference: '+name)
        require(compared['src/contexts.src']['full_row_multiset']['equal_preserving_all_row_bytes_and_multiplicity'],'Unexplained context field or duplicate-count difference')
        attrs=compared['src/attributes.src']['attribute_views']
        require(attrs['all_rows_dropping_only_generated_id']['equal_preserving_all_row_bytes_and_multiplicity'] and
                attrs['positive_unique_ids_and_digests_valid_on_both_sides'] and attrs['same_generated_identifier_set'] and
                attrs['non_context_full_rows_ordered_equal'],'Unexplained attribute content, generated IDs, digest or non-CONTEXT ordering difference')
    require(result==original_result,'Original raw result object changed')
    require(all(diagnostic._stamp(path)==stamp for path,stamp in watched.items()),'A raw input/output/archive changed during the complete QA proof')
    return {'schema_version':1,'artifact_type':'ncimeta-native-nci-reviewed-qa-proof','source':'NCI','version':config['version'],
        'lock_sha256':lock['lock_sha256'],'run_id':lock['run_id'],'decision_id':decision['decision_id'],
        'decision_sha256':manifests.digest(decision),'raw_result_content_sha256':manifests.digest(result),
        'passed':True,'post_qa_validation':validation,'comparison':compared,
        'qa_view_classes_identity':view_identity,'exact_reviewed_row_replacements':1,
        'qa_evidence':{'archive_sha256':archive_sha,'member':qa_member,'member_sha256':bindings['qa_member_sha256'],'line':bindings['qa_line'],'text':qa_line,'rows':qa_rows},
        'review':{k:decision[k] for k in ('review_status','reviewer','reviewed_at','review_basis','actor')},
        'actor_independently_confirmed':False,'native_inputs_reverified':observed_native,
        'generated_id_reference_safety':{'passed':True,'allowed_types':sorted(SAFE_REFERENCE_TYPES),'scope':'All complete post-QA endpoint type inventories exclude generated attribute/relationship ID references.'},
        'raw_acceptance':copy.deepcopy(result['acceptance']),'raw_candidate_modified':False,'native_data_modified':False,
        'raw_result_unchanged':True,'raw_comparison_changed':False,'acceptance_changed':False,
        'persistent_application_authorized':False,'scratch_removed':True,'scratch_class_limit_bytes':CLASS_LIMIT,
        'reference_tree_extracted':False,'inversion_executed':False,'production_eligible':False,
        'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Reviewed exact historical adjustment in a temporary QA view only; original five raw outputs/result preserved. No generic termgroup normalization.'}
