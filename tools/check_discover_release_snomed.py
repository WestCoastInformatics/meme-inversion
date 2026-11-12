#!/usr/bin/env python3
"""Confined physical-discovery fixtures; no server, allocation or inversion."""
import base64
from contextlib import contextmanager
import copy
import hashlib
import io
import json
from pathlib import Path

import discover_release_snomed as discover

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    manifest = json.loads((ROOT / 'docs/inversion-review/release-manifest-examples/snomed.json').read_text())
    payload = {(reference, entry['role']):(ROOT / entry['uri'].removeprefix('repo:')).read_bytes()
               for reference, artifact in manifest['artifacts'].items() for entry in artifact['files']}
    payload[('native-release','rf2-concepts')] += b'116680003\t20200131\t1\t900000000000207008\t900000000000074008\n'
    payload[('native-release','rf2-descriptions')] += b'100012\t20200131\t1\t900000000000207008\t116680003\ten\t900000000000003001\tIs a (attribute)\t900000000000448009\n'
    return manifest, payload


def run(manifest, payload, fail=None):
    opened = []
    @contextmanager
    def reader(reference, role):
        key = reference, role;opened.append(key)
        if key == fail:raise ValueError('Verified bytes changed')
        if key not in payload:raise OSError('Missing saved input')
        yield io.BytesIO(payload[key])
    return discover.analyze(manifest['configuration'], manifest['artifacts'], reader), opened


def append(payload, role, values):
    payload[('native-release',role)] += ('\t'.join(values) + '\n').encode()


def association_fixture():
    manifest,payload = fixture();native = manifest['artifacts']['native-release'];policy = manifest['artifacts']['representation-policy']
    reason = 'Reviewed preserved membership representation for this exact native identifier and producer.'
    identifier = '900001';label = 'Fixture historical association reference set (foundation metadata concept)'
    append(payload,'rf2-concepts',[identifier,'20200131','1','900000000000207008','900000000000074008'])
    append(payload,'rf2-descriptions',['100013','20200131','1','900000000000207008',identifier,'en','900000000000003001',label,'900000000000448009'])
    append(payload,'rf2-association',['fixture-association','20200131','1','900000000000207008',identifier,'100001','138875005'])
    native['data']['discovery']['association_refsets'] = [identifier]
    native['data']['discovery']['labels'][identifier] = label
    native['data']['discovery']['relationship_types'] = ['116680003']
    archive = 'a'*64
    for entry in native['files']:
        entry['archive_sha256'] = archive;entry['sha256'] = hashlib.sha256(payload[('native-release',entry['role'])]).hexdigest()
    cfg = b'RSAB=SNOMEDCT_US\nVSAB=SNOMEDCT_US_2027_03_01\nRelease=Snapshot\nSCT.RELMAP.1=Is a (attribute)|isa|inverse_isa|CHD\n'
    producer = b'preserved membership producer'
    payload[('representation-policy','archived-sct.cfg')] = cfg
    payload[('representation-policy','archived-invert_rf2.pl')] = producer
    policy['files'] = [{'role':'archived-sct.cfg','sha256':hashlib.sha256(cfg).hexdigest(),'archive_sha256':archive},
                       {'role':'archived-invert_rf2.pl','sha256':hashlib.sha256(producer).hexdigest(),'archive_sha256':archive}]
    policy['data']['mappings']['association_refsets'][identifier] = {'decision':'membership-only','reason':reason}
    policy['data']['association_membership_review'] = {'schema_version':1,'source':'SNOMEDCT_US','version':manifest['configuration']['version'],
        'association_refsets':{identifier:{'reason':reason,'fn_labels':[label]}},'cfg_data_b64':base64.b64encode(cfg).decode(),
        'cfg_sha256':hashlib.sha256(cfg).hexdigest(),'producer_sha256':hashlib.sha256(producer).hexdigest(),'archive_sha256':archive,
        'native_sha256':{entry['role']:entry['sha256'] for entry in native['files']}}
    return manifest,payload,identifier


def check():
    checks = []
    def good(value,label):assert value,label;checks.append(label)
    def codes(result):return {value['code'] for value in result['issues']}
    manifest,payload = fixture();before = copy.deepcopy((manifest,payload));result,opened = run(manifest,payload)
    good(codes(result) == {'SNOMED_MRDOC_REQUIRED'},'known complete core data retains only honest operational MRDOC blockers')
    good(result['facts']['core_native_scan_complete'] and len(result['facts']['scanned_roles']) == 14,'all14 Snapshot roles are physically scanned')
    good(len(opened) == len(set(opened)) == 18,'each14native/fourmetadata role read once without output data or a prior folder')
    good(result['facts']['earlier_snapshot_dates_accepted'],'valid Snapshot effective dates before package date are accepted')
    good(not result['facts']['execution_enabled'] and result['facts']['native_validation_still_required'],'discovery never grants execution or substitutes for native validation')
    good((manifest,payload) == before,'source artifacts/native bytes remain untouched')
    good({x['role'] for x in result['required_inputs'] if x['required_for']=='operational-mrdoc'} == set(discover.MRDOC_ROLES),'all three missing MRDOC snapshots are explicitly named')
    good(not result['decisions'],'configured observations live in facts; decisions contains unresolved proposals only')
    relation = result['facts']['configured_representations']['relationship_types']['116680003']
    good(relation['configured_mapping']['inverse_rela']=='inverse_isa' and relation['current_fn_labels']==['Is a (attribute)'],'known stableID mapping and physical FN label reported with inverse')
    m,p=fixture()
    for identifier,refset in [('generic-1','999701'),('generic-2','999702'),('generic-3','999701')]:
        append(p,'rf2-simple-refset',[identifier,'20200131','1','900000000000207008',refset,'100001'])
    r,_=run(m,p)
    good(r['facts']['refset_ids_by_role']['rf2-simple-refset']=={'999701':2,'999702':1},'every active generic simple-refset ID and duplicate occurrence is counted without extra reads')
    good(not r['facts']['generic_membership_review']['newness_determined'] and not r['facts']['generic_membership_review']['membership_label_semantics_reviewed'],'generic membership newness and label review remain explicit unresolved questions without a full prior inventory')
    old_limit=discover.MAX_IDENTIFIERS;discover.MAX_IDENTIFIERS=1
    try:bounded,_=run(m,p)
    finally:discover.MAX_IDENTIFIERS=old_limit
    good('rf2-simple-refset' in bounded['facts']['failed_roles'] and not bounded['facts']['core_native_scan_complete'],'generic refset inventory cap fails closed instead of silently truncating IDs')
    m,p=fixture();p[('native-release','rf2-relationships')] = p[('native-release','rf2-relationships')].replace(b'116680003\t',b'999001\t');r,_=run(m,p)
    good('SNOMED_MAPPING_REQUIRED' in codes(r) and any(x['identifier']=='999001' and x['status']=='unresolved' for x in r['decisions']),'new relationship ID is an explicit unresolved decision, never an XX fallback')
    m,p=fixture();del m['artifacts']['representation-policy']['data']['mappings']['relationship_types']['116680003']['inverse_rela'];r,_=run(m,p)
    good('SNOMED_MAPPING_FIELDS' in codes(r),'missing RELA inverse requires review before conversion')
    m,p=fixture();append(p,'rf2-relationships',['100021','20200131','1','900000000000207008','100001','138875005','0','999002','900000000000011006','900000000000451002']);append(p,'rf2-descriptions',['100014','20200131','1','900000000000207008','999002','en','900000000000003001','Is a (attribute)','900000000000448009']);r,_=run(m,p)
    good('SNOMED_AMBIGUOUS_LABEL' in codes(r),'duplicate FN label across observed type IDs is reported as ambiguity')
    m,p=fixture();p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'Is a (attribute)',b'Changed type name (attribute)');r,_=run(m,p)
    good('SNOMED_CHANGED_TYPE_LABEL' in codes(r),'changed native FN label requires an identifier-bound decision')
    m,p=fixture();m['artifacts']['source-plan']['data']['label_decisions']={'116680003':{'previous_label':'Is a (attribute)','current_label':'Changed type name (attribute)','reason':'Explicit reviewed label change'}};p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'Is a (attribute)',b'Changed type name (attribute)');r,_=run(m,p)
    good('SNOMED_CHANGED_TYPE_LABEL' not in codes(r),'exact supplied identifier/old/new/reason acknowledgment is recognized without inventing mapping')
    m,p=fixture();p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'100012\t20200131\t1',b'100012\t20200131\t0');r,_=run(m,p)
    good(r['facts']['native_fn_labels']['116680003']==['Is a (attribute)'] and 'SNOMED_CHANGED_TYPE_LABEL' not in codes(r),'inactive FN labels for active relationship types remain visible as captured producer resolves before suppression')
    m,p=fixture();p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'Is a (attribute)',b'Is  a (attribute)');r,_=run(m,p)
    good('SNOMED_LABEL_NORMALIZATION_REVIEW' in codes(r),'nontrivial legacy space normalization is an explicit conservative decision')
    m,p=fixture();p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'Is a (attribute)','Is\u00a0a (attribute)'.encode());r,_=run(m,p)
    good('SNOMED_LABEL_NORMALIZATION_REVIEW' in codes(r),'Unicode normalization is never silently inferred for FN mapping labels')
    m,p=fixture();m['artifacts']['native-release']['data']['rf2_view']='Full';r,opened=run(m,p)
    good('SNOMED_DISCOVERY_CONTRACT' in codes(r) and not opened,'Full package cannot be read as a Snapshot capability')
    m,p=fixture();m['artifacts']['native-release']['files'][0]['uri']='repo:wrong.txt';r,_=run(m,p)
    good('SNOMED_MEMBER_IDENTITY' in codes(r) and not r['facts']['core_native_scan_complete'],'declared package role/member mismatch blocks complete physical discovery')
    m,p=fixture();m['artifacts']['native-release']['data']['headers']['rf2-concepts']=['invented'];r,_=run(m,p)
    good('SNOMED_DECLARED_HEADER' in codes(r),'stale declared header cannot contradict the verified role schema silently')
    m,p=fixture();p[('native-release','rf2-language')]=p[('native-release','rf2-language')].replace(b'900000000000509007',b'900000000000508004');r,_=run(m,p)
    good('SNOMED_LANGUAGE_REFSET_REQUIRED' not in codes(r),'canonical GB language preference refset508004 is accepted')
    m,p=fixture();p[('native-release','rf2-language')]=p[('native-release','rf2-language')].replace(b'900000000000509007',b'900000000000508007');r,_=run(m,p)
    good('SNOMED_LANGUAGE_REFSET_REQUIRED' in codes(r),'incorrect508007 language refset remains unreviewed')
    m,p=fixture();m['artifacts']['native-release']['files']=[x for x in m['artifacts']['native-release']['files'] if x['role']!='rf2-language'];r,_=run(m,p)
    good('SNOMED_MISSING_RF2_ROLE' in codes(r) and not r['facts']['core_native_scan_complete'],'missing required RF2 dependency remains unresolved')
    m,p=fixture();m['artifacts']['native-release']['files'].append(copy.deepcopy(m['artifacts']['native-release']['files'][0]));r,_=run(m,p)
    good('SNOMED_DUPLICATE_FILE_ROLE' in codes(r),'duplicate role declaration is rejected')
    m,p=fixture();r,_=run(m,p,('native-release','rf2-concepts'))
    good('SNOMED_NATIVE_SCAN' in codes(r) and 'rf2-concepts' in r['facts']['failed_roles'],'coordinator byte-verification failure is an explicit source input error')
    m,p=fixture();p[('native-release','rf2-relationships')]+=p[('native-release','rf2-relationships')].splitlines(keepends=True)[1];r,_=run(m,p)
    good('SNOMED_NATIVE_SCAN' in codes(r),'duplicate Snapshot row ID is detected through full scan')
    m,p=fixture();p[('native-release','rf2-relationships')]=p[('native-release','rf2-relationships')].replace(b'20200131',b'20300131');r,_=run(m,p)
    good('SNOMED_NATIVE_SCAN' in codes(r),'future native effective date cannot pass discovery')
    m,p=fixture();m['configuration']['replacement_baseline']={'source':'SNOMEDCT_US','version':'SNOMEDCT_US_2024_09_01'};m['artifacts']['source-plan']['data']['replacement_baseline']=copy.deepcopy(m['configuration']['replacement_baseline']);p[('ncimeta-snapshot','sources-src')]=p[('ncimeta-snapshot','sources-src')].replace(b'SNOMEDCT_US_2026_03_01',b'SNOMEDCT_US_2024_09_01');r,_=run(m,p)
    good('SNOMED_REPLACEMENT_REQUIRED' not in codes(r) and 'SNOMED_METADATA_SCAN' not in codes(r),'explicit nonadjacent inserted predecessor accepted without calendar inference')
    m,p=fixture();m['configuration']['replacement_baseline']=None;r,_=run(m,p)
    good('SNOMED_REPLACEMENT_REQUIRED' in codes(r),'missing inserted predecessor is a decision, never inferred')
    m,p=fixture();m['artifacts']['ncimeta-snapshot']['data']['metadata_format']={x:{'terminal_delimiter':True} for x in ('sources-src','termgroups-src')}
    for role in ('sources-src','termgroups-src'):p[('ncimeta-snapshot',role)]=p[('ncimeta-snapshot',role)].replace(b'\n',b'|\n')
    r,_=run(m,p);good('SNOMED_METADATA_SCAN' not in codes(r),'explicit terminal metadata delimiter format is preserved')
    m,p=fixture();p[('ncimeta-snapshot','sources-src')]=b'';r,_=run(m,p)
    good('SNOMED_METADATA_SCAN' in codes(r),'empty metadata role cannot establish closure')
    m,p=fixture();m['artifacts']['ncimeta-snapshot']['data']['snapshot_id']='different';r,_=run(m,p)
    good('SNOMED_METADATA_BOUNDARY_REQUIRED' in codes(r),'saved metadata coherent boundary must match provenance')
    m,p=fixture();m['artifacts']['source-plan']['data']['mrdoc_required']=True
    for role in discover.MRDOC_ROLES:
        m['artifacts']['ncimeta-snapshot']['files'].append({'role':role,'uri':'repo:metadata-'+role});p[('ncimeta-snapshot',role)]=b'saved snapshot bytes\n'
    r,_=run(m,p)
    good(r['facts']['operational_metadata_inputs_read'] and not r['facts']['mrdoc_semantics_validated'] and 'SNOMED_MRDOC_CAPABILITY_REQUIRED' in codes(r),'present MRDOC bytes do not imply an implemented operational generation/content validation capability')
    m,p,identifier=association_fixture();r,_=run(m,p)
    good('SNOMED_MEMBERSHIP_REVIEW' not in codes(r) and 'SNOMED_MEMBERSHIP_PHYSICAL_BINDING' not in codes(r) and r['facts']['configured_representations']['association_refsets'][identifier]['status']=='configured-membership-only','exact archive/producer/config/native-ID-and-label membership-only review recognized')
    good(set(r['facts']['membership_evidence_roles_read'])=={'archived-sct.cfg','archived-invert_rf2.pl'},'membership review physically reads both cfg and producer through the verified-input provider')
    m,p,identifier=association_fixture();r,_=run(m,p,('representation-policy','archived-invert_rf2.pl'))
    good('SNOMED_MEMBERSHIP_INPUT' in codes(r) and 'SNOMED_MEMBERSHIP_PHYSICAL_BINDING' in codes(r),'failed producer byte verification prevents configured membership-only status')
    m,p,identifier=association_fixture();p[('native-release','rf2-descriptions')]=p[('native-release','rf2-descriptions')].replace(b'Fixture historical association reference set',b'Changed association reference set');r,_=run(m,p)
    good('SNOMED_MEMBERSHIP_PHYSICAL_BINDING' in codes(r),'membership-only waiver cannot follow changed actual native labels')
    m,p,identifier=association_fixture();m['artifacts']['representation-policy']['data']['association_membership_review']['producer_sha256']='0'*64;r,_=run(m,p)
    good('SNOMED_MEMBERSHIP_REVIEW' in codes(r),'unbound membership-only producer evidence rejected')
    m,p=fixture();old=discover.MAX_COMPONENTS;discover.MAX_COMPONENTS=1
    try:r,_=run(m,p)
    finally:discover.MAX_COMPONENTS=old
    good('SNOMED_NATIVE_SCAN' in codes(r) and not r['facts']['core_native_scan_complete'],'bounded scanner fails closed when identity inventory exceeds its reviewed cap')
    m,p=fixture();p[('native-release','rf2-concepts')]=p[('native-release','rf2-concepts')].rstrip(b'\n');r,_=run(m,p)
    good('SNOMED_NATIVE_SCAN' in codes(r) and r['facts']['observations_include_failed_roles'],'unterminated native row cannot establish complete physical inventory')
    m,p=fixture();p[('native-release','rf2-concepts')]=p[('native-release','rf2-concepts')].replace(b'138875005',b'13887\x0005');r,_=run(m,p)
    good('SNOMED_NATIVE_SCAN' in codes(r),'NUL in native row rejected before any value discovery')
    print(json.dumps({'passed':len(checks),'checks':checks},indent=2))


if __name__ == '__main__':check()
