#!/usr/bin/env python3
"""Confined synthetic TAR capture/curation tests; no server or native run."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

import capture_archived_snomed as capture
import check_execute_release_snomed as fixtures
import curate_archived_snomed as curator
import inspect_inversion_archive as inventory_tool


ASSOCIATION_ID = '900000000000531004'
ASSOCIATION_LABEL = 'REFERS TO concept association reference set (foundation metadata concept)'
ASSOCIATION_SRUI = '11111111-2222-3333-4444-555555555555'


def archive_fixture(root, terminal=False, index=0, membership=False, membership_label=ASSOCIATION_LABEL):
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
        if membership:
            if item['role']=='rf2-concepts':raw+=(ASSOCIATION_ID+'\t20200131\t1\t900000000000207008\t900000000000074008\n').encode()
            if item['role']=='rf2-descriptions':raw+=('100013\t20200131\t1\t900000000000207008\t'+ASSOCIATION_ID+'\ten\t900000000000003001\t'+membership_label+'\t900000000000448009\n').encode()
            if item['role']=='rf2-association':raw+=(ASSOCIATION_SRUI+'\t20200131\t1\t900000000000207008\t'+ASSOCIATION_ID+'\t100011\t100001\n').encode()
        values[version+'/'+item['destination']]=raw
    values[version+'/etc/sct.cfg']=base64.b64decode(plan['generated_files'][0]['data_b64'])
    for script in ['invert_rf2.pl','rmdanglingattrs.pl']:
        values[version+'/bin/'+script]=subprocess.check_output(['git','-C',str(fixtures.ROOT),'show','3b125edc1d29f7c7a91673da2a8d752bb0adff44:sources/SNOMEDCT_US_2026_09_01/bin/'+script])
    outputs=fixtures.output_fixture(plan)
    if membership:
        value=ASSOCIATION_ID+'~TARGETCOMPONENT~100001'
        outputs['attributes.src'].append(['2','100011','S','SUBSET_MEMBER',value,version,'R','n','N','N','SOURCE_AUI',version,ASSOCIATION_SRUI,hashlib.md5(value.encode()).hexdigest(),''])
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


def membership_review(captured):
    """Test-only explicit review, built from a separately captured tiny archive."""
    return {'schema_version':1,'source':'SNOMEDCT_US','version':captured['version'],
            'archive_sha256':captured['archive']['sha256'],
            'cfg_sha256':captured['small_files']['etc/sct.cfg']['sha256'],
            'producer_sha256':captured['small_files']['bin/invert_rf2.pl']['sha256'],
            'native_sha256':{role:item['sha256'] for role,item in captured['native']['files'].items()},
            'association_refsets':{ASSOCIATION_ID:{'reason':'Synthetic explicit review: preserve native membership attributes and absent association edges.',
                'fn_labels':captured['native']['type_fsn_labels'][ASSOCIATION_ID]}}}


def stage_archive(manifest, archive, target):
    recipe=curator.execution.build_plan(manifest['configuration'],manifest['artifacts'])
    with tarfile.open(archive,'r:gz') as handle:
        for item in recipe['input_files']:
            entry=next(row for row in manifest['artifacts'][item['artifact']]['files'] if row['role']==item['role'])
            path=target/item['destination'];path.parent.mkdir(parents=True,exist_ok=True)
            with handle.extractfile(entry['archive_member']) as source,path.open('wb') as output:shutil.copyfileobj(source,output)
            path.chmod(0o444)
    for item in recipe['generated_files']:
        path=target/item['relative_path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(base64.b64decode(item['data_b64']));path.chmod(int(item['mode'],8))
    return recipe


def native_association_probe(root):
    """Run the exact production-derived function, with recording serializers."""
    producer=(fixtures.ROOT/curator.execution.PACKAGE/'bin/invert_rf2.pl').read_text()
    function=re.search(r'sub process_assocs \{.*?\} # end process_assocs',producer,re.S)[0]
    native=root/'association.txt'
    native.write_text('\t'.join(curator.release_snomed.HEADERS['rf2-association'])+'\n'+
                      '\t'.join([ASSOCIATION_SRUI,'20200131','1','900000000000207008',ASSOCIATION_ID,'100011','100001'])+'\n')
    harness='''use JSON::PP;
our @events;
{ package ProbeCfg; sub getReqEle { return $_[0]->{file}; } }
{ package ProbeAttr; sub dumpAttr { push @main::events,{kind=>'attribute',%{$_[1]}}; } }
{ package ProbeRel; sub dumpRel { push @main::events,{kind=>'relationship',%{$_[1]}}; } }
{ package ProbeMerge; sub dumpMerge { push @main::events,{kind=>'merge',%{$_[1]}}; } }
my $cfg=bless {file=>$ARGV[0]},'ProbeCfg'; my $CfgRef=\\$cfg;
my (%subsetCid,%relCid2info); my %active=('100011'=>1,'100001'=>1); my %conActive=('100001'=>1);
my $AttrCON=bless {},'ProbeAttr'; my $AttrSAUI=bless {},'ProbeAttr'; my $AttrREL=bless {},'ProbeAttr';
my $RelationA=bless {},'ProbeRel'; my $MergeSAME=bless {},'ProbeMerge'; my $defMod='900000000000207008';
'''+function+'\nprocess_assocs(); print JSON::PP->new->canonical->encode(\\@events);\n'
    return json.loads(subprocess.check_output(['/usr/bin/perl','-e',harness,str(native)]))


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
    with tempfile.TemporaryDirectory(prefix='snomed-membership-review-') as directory:
        root=Path(directory).resolve();archive,frozen,receipt=archive_fixture(root,membership=True)
        data=capture.capture(archive,frozen)
        engine=subprocess.check_output(['git','-C',str(fixtures.ROOT),'rev-parse','HEAD']).decode().strip()
        reject(lambda:curator.curate(data,frozen,receipt,engine),'An unmapped association remains blocked without a separate review')
        review=membership_review(data)
        before=json.dumps(review,sort_keys=True)
        manifest,evidence=curator.curate(data,frozen,receipt,engine,review)
        good(json.dumps(review,sort_keys=True)==before,'Curation does not add cfg bytes to or mutate the separately reviewed record')
        good(evidence['association_membership_review']==review and
             manifest['artifacts']['policy']['data']['mappings']['association_refsets'][ASSOCIATION_ID]['decision']=='membership-only',
             'An exact archive/native/label-bound absent association mapping is retained as membership-only')
        target=root/'candidate';target.mkdir();recipe=stage_archive(manifest,archive,target)
        result=curator.execution.validate_inputs(recipe,target)
        good(result['passed'] and result['facts']['membership_only_associations'][ASSOCIATION_ID]['eligible_membership_rows']==1,
             'Physical discovery validates reviewed membership-only rows with actual FN labels and active endpoints')
        for label,change in [
            ('native hash',lambda r:r['native_sha256'].update({'rf2-association':'0'*64})),
            ('cfg hash',lambda r:r.update(cfg_sha256='0'*64)),
            ('producer hash',lambda r:r.update(producer_sha256='0'*64)),
            ('archive hash',lambda r:r.update(archive_sha256='0'*64)),
            ('FN label',lambda r:r['association_refsets'][ASSOCIATION_ID].update(fn_labels=['A guessed label'])),
            ('empty reason',lambda r:r['association_refsets'][ASSOCIATION_ID].update(reason='')),
        ]:
            bad=copy.deepcopy(review);change(bad)
            reject(lambda:curator.curate(data,frozen,receipt,engine,bad),'Membership-only review rejects changed '+label)
        bad=copy.deepcopy(data);bad['native']['discovery']['relationship_types'].append(ASSOCIATION_ID)
        reject(lambda:curator.curate(bad,frozen,receipt,engine,review),'An association used as a native relationship type cannot be membership-only')
        for label,change in [
            ('guessed REL',lambda a:a['policy']['data']['mappings']['association_refsets'][ASSOCIATION_ID].update(rel='RO')),
            ('exclusion relabeling',lambda a:a['policy']['data']['mappings']['association_refsets'][ASSOCIATION_ID].update(decision='exclude')),
            ('cfg payload mutation',lambda a:a['policy']['data']['association_membership_review'].update(cfg_data_b64=base64.b64encode(b'not the cfg').decode())),
            ('missing review',lambda a:a['policy']['data'].pop('association_membership_review')),
        ]:
            bad=copy.deepcopy(manifest);change(bad['artifacts'])
            good(bool(curator.release_snomed.analyze(bad['configuration'],bad['artifacts'])['issues']),
                 'Source preflight rejects membership-only '+label)
            reject(lambda:curator.execution.build_plan(bad['configuration'],bad['artifacts']),
                   'Native planning rejects membership-only '+label)
        bad=copy.deepcopy(manifest)
        bad['artifacts']['policy']['data']['association_membership_review']['producer_sha256']='0'*64
        next(row for row in bad['artifacts']['policy']['files'] if row['role']=='archived-invert_rf2.pl')['sha256']='0'*64
        reject(lambda:curator.execution.build_plan(bad['configuration'],bad['artifacts']),
               'Matching changed evidence hashes cannot substitute another producer family')
        for label,changed_cfg in [
            ('another cfg source/version',base64.b64decode(manifest['artifacts']['policy']['data']['association_membership_review']['cfg_data_b64']).replace(recipe['version'].encode(),b'SNOMEDCT_US_2000_01_01')),
            ('a cfg mapping hidden by property expansion',base64.b64decode(manifest['artifacts']['policy']['data']['association_membership_review']['cfg_data_b64'])+('\nREVIEWED_LABEL = '+ASSOCIATION_LABEL+'\nSCT.RELMAP.9999 = <REVIEWED_LABEL>|related_to|inverse_related_to|RO\n').encode()),
        ]:
            bad=copy.deepcopy(manifest);proof=bad['artifacts']['policy']['data']['association_membership_review']
            proof.update(cfg_data_b64=base64.b64encode(changed_cfg).decode(),cfg_sha256=hashlib.sha256(changed_cfg).hexdigest())
            next(row for row in bad['artifacts']['policy']['files'] if row['role']=='archived-sct.cfg')['sha256']=proof['cfg_sha256']
            reject(lambda:curator.execution.build_plan(bad['configuration'],bad['artifacts']),
                   'Membership-only review rejects '+label+' even with matching evidence hashes')
        values=fixtures.output_fixture(recipe);version=recipe['version'];value=ASSOCIATION_ID+'~TARGETCOMPONENT~100001'
        member=['2','100011','S','SUBSET_MEMBER',value,version,'R','n','N','N','SOURCE_AUI',version,ASSOCIATION_SRUI,hashlib.md5(value.encode()).hexdigest(),'']
        values['attributes.src'].append(member);fixtures.write_outputs(target,values)
        validated=curator.execution.validate_outputs(recipe,target)
        good(validated['passed'] and validated['facts']['structure']['membership_only_validation']['expected_attributes']==1,
             'Independent output validation requires the exact preserved membership attribute and qualifier')
        bad=copy.deepcopy(values);bad['attributes.src'].pop();fixtures.write_outputs(target,bad)
        good(not curator.execution.validate_outputs(recipe,target)['passed'],'Missing reviewed membership attribute is an output validation failure')
        bad=copy.deepcopy(values);bad['attributes.src'][-1][12]='changed-native-uuid';fixtures.write_outputs(target,bad)
        good(not curator.execution.validate_outputs(recipe,target)['passed'],'Membership attribute native row identity cannot be changed')
        bad=copy.deepcopy(values);bad['relationships.src'][0][16]=ASSOCIATION_SRUI;fixtures.write_outputs(target,bad)
        good(not curator.execution.validate_outputs(recipe,target)['passed'],'A relationship emitted for a membership-only association is an output validation failure')
        native_events=native_association_probe(root)
        good(len(native_events)==1 and native_events[0]['kind']=='attribute' and native_events[0]['atn']=='SUBSET_MEMBER' and
             native_events[0]['atv']==value and native_events[0]['satui']==ASSOCIATION_SRUI,
             'Exact production process_assocs emits membership attributes and no edge when its relation mapping is absent')
    with tempfile.TemporaryDirectory(prefix='snomed-mapped-association-') as directory:
        root=Path(directory).resolve();archive,frozen,receipt=archive_fixture(root,membership=True,membership_label='Is a (attribute)')
        data=capture.capture(archive,frozen);review=membership_review(data)
        reject(lambda:curator.curate(data,frozen,receipt,engine,review),'An association with an established archived REL mapping cannot be declared membership-only')
    return passed


if __name__=='__main__':
    values=check()
    for label in values:print('PASS',label)
    print(len(values),'archived SNOMED capture/curation checks passed')
