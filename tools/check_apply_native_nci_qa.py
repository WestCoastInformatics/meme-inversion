#!/usr/bin/env python3
"""Confined complete NCIt QA-view proofs; no server or native inversion."""
from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
from unittest.mock import patch

import apply_native_nci_qa as qa
import check_execute_release_nci as source


def ident(raw):return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def attribute(number,name,value,version):
    return ('|'.join([str(number),'10000','C',name,value,version,'R','Y','N','N','SRC_ATOM_ID','','',hashlib.md5(value.encode()).hexdigest(),''])+'\n').encode()


def reseal(lock,result,decision):
    lock['manifest_sha256']=qa.manifests.digest(lock['manifest']);lock['plan_sha256']=qa.manifests.digest(lock['plan'])
    lock['lock_sha256']=qa.manifests.digest({k:v for k,v in lock.items() if k!='lock_sha256'})
    result['lock_sha256']=decision['lock_sha256']=lock['lock_sha256']


@contextmanager
def fixture(change=None,version='NCI_2032_03B'):
    with tempfile.TemporaryDirectory(prefix='nci-reviewed-qa-fixture-') as directory:
        root=Path(directory).resolve();target=root/'sources'/version;target.mkdir(parents=True)
        scratch=root/'qa';scratch.mkdir()
        manifest,code,native=source.fixture(version,'NCI_2032_01A' if version=='NCI_2032_03B' else 'NCI_2033_04C')
        plan=source.execute.rebuild_plan(manifest['configuration'],manifest['artifacts'],code)
        source.stage(plan,native,target);source.outputs(plan,target)
        rows={role:(target/role).read_bytes() for role in qa.OUTPUTS}
        good_class=rows[qa.CLASS];rows[qa.CLASS]=good_class.replace(b'/PT|',b'/SY|',1)
        rows['src/attributes.src']=attribute(1,'DEFINITION','Alpha',version)+attribute(2,'CONTEXT','First',version)+attribute(3,'CONTEXT','Second',version)
        rows['src/contexts.src']+=rows['src/contexts.src'].replace(b'|isa|',b'|part_of|')
        reference=copy.deepcopy(rows);reference[qa.CLASS]=good_class
        reference['src/attributes.src']=attribute(1,'DEFINITION','Alpha',version)+attribute(2,'CONTEXT','Second',version)+attribute(3,'CONTEXT','First',version)
        reference['src/contexts.src']=b''.join(reversed(rows['src/contexts.src'].splitlines(keepends=True)))
        evidence=('Header\n\t****ERR: VUndefinedTG_10000 => '+version+'/SY\nOther finding is not an adjustment\n').encode()
        if change:change(rows,reference,plan,manifest)
        for role,raw in rows.items():(target/role).write_bytes(raw)
        archive=root/'sources'/(version+'.tgz');qa_member=version+'/etc/qa/report.err'
        with tarfile.open(archive,'w:gz') as out:
            for role,raw in reference.items():
                item=tarfile.TarInfo(version+'/'+role);item.size=len(raw);out.addfile(item,io.BytesIO(raw))
            item=tarfile.TarInfo(qa_member);item.size=len(evidence);out.addfile(item,io.BytesIO(evidence))
        archive_sha=ident(archive.read_bytes())['sha256']
        artifacts=manifest['artifacts'];config=manifest['configuration'];config['replay']={'reference_ref':'qa-oracle','reference_stage':'inversion-src','comparison_profile':'exact'}
        artifacts['qa-oracle']={'artifact_type':'reference-inversion','source':'NCI','version':version,'data':{'reference_stage':'inversion-src'},
            'files':[{'role':role,'uri':archive.as_uri(),'archive_format':'tar.gz','archive_sha256':archive_sha,'archive_bytes':archive.stat().st_size,
                      'archive_member':version+'/'+role,**ident(raw)} for role,raw in reference.items()]}
        lock={'schema_version':1,'artifact_type':'ncimeta-native-release-lock','run_id':'reviewed-qa-fixture',
              'configuration':config,'manifest':manifest,'manifest_sha256':qa.manifests.digest(manifest),'plan':plan,'plan_sha256':qa.manifests.digest(plan)}
        lock['lock_sha256']=qa.manifests.digest(lock)
        result={'source':'NCI','version':version,'run_id':lock['run_id'],'lock_sha256':lock['lock_sha256'],
                'declared_inputs_unchanged':True,'insertion_executed':False,'production_eligible':False,
                'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW','production_eligible':False},
                'comparison':{'validation':source.execute.validate_outputs(plan,target),
                    'files':{role:{'candidate':ident(raw),'reference':ident(reference[role]),'exact_match':raw==reference[role]} for role,raw in rows.items()}}}
        before=rows[qa.CLASS].splitlines(keepends=True)[0].decode();after=good_class.splitlines(keepends=True)[0].decode()
        native_bindings={version+'/'+item['relative_path']:qa._hash(target/item['relative_path']) for item in plan['validation']['native_inputs'].values()}
        decision={'schema_version':1,'artifact_type':'ncimeta-qa-adjustment','decision_id':'reviewed-test-termgroup','source':'NCI','version':version,
                  'stage':'post-inversion-QA','review_status':'reviewed','reviewer':'Confined test reviewer','reviewed_at':'2033-01-01T00:00:00Z',
                  'review_basis':'Explicit fixture review','actor':'unconfirmed','lock_sha256':lock['lock_sha256'],
                  'row_key':{'source_atom_id':'10000','source_cui':'C1','code':'C1','atom_name':'Alpha'},'output_role':qa.CLASS,
                  'before_row':before,'after_row':after,'before_row_sha256':ident(before.encode())['sha256'],'after_row_sha256':ident(after.encode())['sha256'],
                  'allowed_field_change':{'position':2,'name':'termgroup','before':version+'/SY','after':version+'/PT'},
                  'bindings':{'candidate_file_sha256':ident(rows[qa.CLASS])['sha256'],'official_file_sha256':ident(reference[qa.CLASS])['sha256'],
                              'official_archive_sha256':archive_sha,'native_inputs':native_bindings,'qa_member':qa_member,'qa_member_sha256':ident(evidence)['sha256'],'qa_line':2},
                  'application_authorized':False,'raw_comparison_changed':False}
        yield lock,target,result,decision,scratch


def check():
    checks=[]
    def good(value,label):assert value,label;checks.append(label)
    def reject(args,label,change=None):
        if change:change(*args)
        try:qa.apply_and_validate(*args)
        except (ValueError,OSError,KeyError,tarfile.TarError):checks.append(label);return
        raise AssertionError(label)
    with fixture() as args:
        before={str(p):(p.read_bytes(),p.stat().st_mode) for p in args[1].rglob('*') if p.is_file()};result=copy.deepcopy(args[2]);decision=copy.deepcopy(args[3])
        proof=qa.apply_and_validate(*args)
        good(proof['passed'] and proof['post_qa_validation']['passed'],'complete five-output post-QA validation passes despite original unknown-termgroup finding')
        good(not args[2]['comparison']['validation']['passed'] and proof['raw_acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW','original failed raw validation and strict comparison remain preserved')
        good(proof['qa_view_classes_identity']['sha256']==args[3]['bindings']['official_file_sha256'] and proof['exact_reviewed_row_replacements']==1,'one exact reviewed row creates the complete official classes hash')
        good(proof['comparison']['src/contexts.src']['full_row_multiset']['equal_preserving_all_row_bytes_and_multiplicity'] and not proof['comparison']['src/contexts.src']['ordered_bytes_equal'],'complete context row permutation is distinguished from content changes')
        view=proof['comparison']['src/attributes.src']['attribute_views']
        good(view['all_rows_dropping_only_generated_id']['equal_preserving_all_row_bytes_and_multiplicity'] and view['same_generated_identifier_set'] and view['non_context_full_rows_ordered_equal'],'full attribute equivalence checks only generated ID while exact non-CONTEXT rows and ID set stay preserved')
        good(proof['generated_id_reference_safety']['passed'] and not proof['persistent_application_authorized'],'known complete endpoint types exclude generated-ID references and persistent application')
        good(proof['review']['actor']=='unconfirmed' and not proof['actor_independently_confirmed'],'current review never establishes the historical actor')
        good(before=={str(p):(p.read_bytes(),p.stat().st_mode) for p in args[1].rglob('*') if p.is_file()} and args[2]==result and args[3]==decision,'all raw candidate/native/metadata bytes, modes and result/decision objects remain unchanged')
        good(proof['scratch_removed'] and not list(args[4].iterdir()) and not proof['reference_tree_extracted'],'only temporary class view is written and all scratch is removed')
        good(proof==qa.apply_and_validate(*args),'unchanged evidence produces deterministic complete proof')
    for key,value,label in [('review_status','proposed','unreviewed proposed decision rejected'),('reviewer','','missing reviewer rejected'),('reviewed_at','2033-01-01','review time without timezone rejected'),('lock_sha256','0'*64,'decision for another frozen request rejected'),('source','OTHER','decision for another source rejected'),('application_authorized',True,'persistent-application request rejected')]:
        with fixture() as args:reject(args,label,lambda l,t,r,d,s,key=key,value=value:d.update({key:value}))
    with fixture() as args:reject(args,'wrong reviewed semantic row key rejected',lambda l,t,r,d,s:d['row_key'].update(code='OTHER'))
    with fixture() as args:reject(args,'non-text reviewed row rejected as an explicit data error',lambda l,t,r,d,s:d.update(before_row=None))
    with fixture() as args:reject(args,'reviewed row-hash mutation rejected',lambda l,t,r,d,s:d.update(after_row_sha256='0'*64))
    with fixture() as args:reject(args,'extra atom-name field edit rejected',lambda l,t,r,d,s:d.update(after_row=d['after_row'].replace('Alpha','Other')))
    with fixture() as args:reject(args,'wrong allowed field position rejected',lambda l,t,r,d,s:d['allowed_field_change'].update(position=3))
    with fixture() as args:reject(args,'wrong official class file hash rejected',lambda l,t,r,d,s:d['bindings'].update(official_file_sha256='0'*64))
    with fixture() as args:reject(args,'wrong official archive hash rejected',lambda l,t,r,d,s:d['bindings'].update(official_archive_sha256='0'*64))
    with fixture() as args:reject(args,'changed complete native publisher hash binding rejected',lambda l,t,r,d,s:next(iter(d['bindings']['native_inputs'].values())).update(sha256='0'*64))
    with fixture() as args:reject(args,'incomplete native input binding set rejected',lambda l,t,r,d,s:d['bindings']['native_inputs'].pop(next(iter(d['bindings']['native_inputs']))))
    with fixture() as args:
        path=args[1]/next(iter(args[0]['plan']['validation']['native_inputs'].values()))['relative_path'];path.write_bytes(path.read_bytes()+b'changed\n')
        reject(args,'actual native publisher mutation rejected')
    with fixture() as args:
        path=args[1]/'src/relationships.src';path.write_bytes(path.read_bytes().replace(b'|RT|',b'|RB|'))
        reject(args,'actual raw output mutation rejected before QA view')
    with fixture() as args:
        path=args[1]/'src/termgroups.src';path.write_bytes(path.read_bytes()+b'unsafe\n')
        reject(args,'modified termgroup metadata cannot approve the overlay')
    with fixture() as args:reject(args,'wrong complete QA member hash rejected',lambda l,t,r,d,s:d['bindings'].update(qa_member_sha256='0'*64))
    with fixture() as args:reject(args,'another QA finding cannot authorize this exact adjustment',lambda l,t,r,d,s:d['bindings'].update(qa_line=3))
    with fixture() as args:
        lock,target,result,decision,scratch=args
        lock['manifest']['artifacts']['qa-oracle']['files'][0]['archive_member']=target.name+'/insert/classes_atoms.src'
        reseal(lock,result,decision)
        reject(args,'insertion-stage classes cannot substitute for current inversion output')
    with fixture() as args:
        lock,target,result,decision,scratch=args
        reference=lock['manifest']['artifacts']['qa-oracle'];item=next(x for x in reference['files'] if x['role']=='src/attributes.src')
        item['archive_member']=target.name+'/src/attributes.orig';reseal(lock,result,decision)
        reject(args,'attributes.orig requires explicit hash-bound pre-insertion stage proof')
    with fixture() as args:
        lock,target,result,decision,scratch=args;reference=lock['manifest']['artifacts']['qa-oracle'];archive=Path(qa.manifests.location(reference['files'][0],False))
        with tarfile.open(archive,'r:gz') as incoming:members={m.name:incoming.extractfile(m).read() for m in incoming if m.isfile()}
        original=target.name+'/src/attributes.orig';members[original]=members.pop(target.name+'/src/attributes.src')
        with tarfile.open(archive,'w:gz') as out:
            for name,raw in members.items():
                item=tarfile.TarInfo(name);item.size=len(raw);out.addfile(item,io.BytesIO(raw))
        archive_sha=ident(archive.read_bytes())['sha256']
        for item in reference['files']:
            item['archive_sha256']=archive_sha;item['archive_bytes']=archive.stat().st_size
            if item['role']=='src/attributes.src':item['archive_member']=original;attribute_hash=item['sha256']
        reference['data']['attribute_stage_proof']={'original_member':original,'original_sha256':attribute_hash,'archive_sha256':archive_sha}
        decision['bindings']['official_archive_sha256']=archive_sha;reseal(lock,result,decision)
        good(qa.apply_and_validate(*args)['passed'],'hash-proven original attributes member remains a valid inversion-stage oracle')
    def extra_class(rows,ref,plan,manifest):ref[qa.CLASS]+=ref[qa.CLASS].replace(b'10000',b'10001').replace(b'Alpha',b'Other')
    with fixture(extra_class) as args:reject(args,'extra class discrepancy cannot be concealed by one reviewed row')
    def rel_change(rows,ref,plan,manifest):ref['src/relationships.src']=ref['src/relationships.src'].replace(b'|RT|',b'|RB|')
    with fixture(rel_change) as args:reject(args,'extra relationship difference rejected')
    def context_change(rows,ref,plan,manifest):ref['src/contexts.src']=ref['src/contexts.src'].replace(b'|isa|',b'|different|')
    with fixture(context_change) as args:reject(args,'changed context field rejected despite valid structure')
    def context_duplicate(rows,ref,plan,manifest):ref['src/contexts.src']+=ref['src/contexts.src'].splitlines(keepends=True)[0]
    with fixture(context_duplicate) as args:reject(args,'context duplicate multiplicity remains part of equivalence')
    def attr_content(rows,ref,plan,manifest):ref['src/attributes.src']=ref['src/attributes.src'].replace(b'|First|',b'|Other|')
    with fixture(attr_content) as args:reject(args,'attribute content/hash change rejected')
    def bad_ref_ids(rows,ref,plan,manifest):ref['src/attributes.src']=ref['src/attributes.src'].replace(b'3|10000|',b'2|10000|')
    with fixture(bad_ref_ids) as args:reject(args,'duplicate reference attribute IDs cannot be discarded')
    def different_ref_id_set(rows,ref,plan,manifest):ref['src/attributes.src']=ref['src/attributes.src'].replace(b'3|10000|',b'4|10000|')
    with fixture(different_ref_id_set) as args:reject(args,'different reference generated-ID set rejected even with equal remaining fields')
    def generated_reference(rows,ref,plan,manifest):
        rows['src/attributes.src']=rows['src/attributes.src'].replace(b'|SRC_ATOM_ID|',b'|ATTRIBUTE_ID|')
        ref['src/attributes.src']=ref['src/attributes.src'].replace(b'|SRC_ATOM_ID|',b'|ATTRIBUTE_ID|')
    with fixture(generated_reference) as args:reject(args,'generated attribute ID references prohibit equivalence normalization')
    def noncontext_order(rows,ref,plan,manifest):
        version=manifest['configuration']['version'];extra=attribute(4,'DEFINITION','Beta',version)
        rows['src/attributes.src']+=extra;ref['src/attributes.src']=extra+ref['src/attributes.src']
    with fixture(noncontext_order) as args:reject(args,'non-CONTEXT full record ordering remains exact')
    with fixture(version='NCI_2033_06C') as args:good(qa.apply_and_validate(*args)['version']=='NCI_2033_06C','same policy supports another release without source/version/atom constants')
    with fixture() as args:
        original=qa.diagnostic._compare
        def mutate(name,path,handle,groups):
            value=original(name,path,handle,groups)
            if name=='contexts.src':
                raw=args[1]/'src/contexts.src';raw.write_bytes(raw.read_bytes()+b'\n')
            return value
        with patch.object(qa.diagnostic,'_compare',side_effect=mutate):reject(args,'concurrent raw output mutation invalidates the complete proof')
    with fixture() as args:
        cap=qa.CLASS_LIMIT;qa.CLASS_LIMIT=1
        try:reject(args,'temporary class payload size cap enforced before application')
        finally:qa.CLASS_LIMIT=cap
        good(not list(args[4].iterdir()),'rejected proof leaves no temporary class payload')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__=='__main__':check()
