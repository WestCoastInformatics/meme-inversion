#!/usr/bin/env python3
"""Cross-source admission, file-integrity, freeze and compatibility checks."""
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
import zipfile

import inversion_request as historical
import inversion_worker as worker
import release_manifest as release
from check_release_nci import fixture as nci_fixture
from check_release_mth import direct_example
from check_release_snomed import SECOND as SNOMED_SECOND

EXAMPLES = release.DOCS / 'release-manifest-examples'


def check():
    passed = []
    def good(value, label):
        assert value, label
        passed.append(label)
    def rejected(action, label):
        try:action()
        except (ValueError, RuntimeError, FileExistsError, KeyError):passed.append(label)
        else:raise AssertionError(label)
    def codes(report):return {item['code'] for item in report['issues']}
    examples = [release.load(EXAMPLES / (name + '.json')) for name in ('nci', 'snomed', 'mth')]
    for name, manifest in zip(('NCI', 'SNOMED', 'MTH'), examples):
        before = copy.deepcopy(manifest)
        with patch.object(historical, 'select_case', side_effect=AssertionError('Catalog must not admit manifests')):
            declared = release.preflight(manifest)
            verified = release.preflight(manifest, verify=True)
        good(declared['manifest_valid'] and declared['declarations_valid'], name + ' manifest uses the same common schema and preflight without historical case selection')
        good('INPUT_BYTES_UNVERIFIED' in codes(declared), name + ' declaration alone does not prove input bytes')
        good(all(row['status'] == 'VERIFIED' for row in verified['input_files']), name + ' actual tiny input fixtures match all declared identities')
        good(not any(row['severity'] == 'error' for row in verified['issues']), name + ' source and common contracts agree')
        good(not verified['execution_eligible'] and not verified['production_eligible'] and 'PREFLIGHT_NOT_EXECUTION_AUTHORITY' in codes(verified), name + ' valid preflight cannot enable native execution')
        good('SYNTHETIC_EVIDENCE' in codes(verified), name + ' synthetic fixtures remain explicitly blocked as release evidence')
        good(manifest == before, name + ' preflight does not rewrite operator inputs')
        good(verified['artifact_bindings'] == release.preflight(manifest, verify=True)['artifact_bindings'], name + ' artifact fingerprinting is deterministic')
    for manifest in [nci_fixture('NCI_2027_02A','NCI_2026_12B',False), release.load(SNOMED_SECOND), direct_example()]:
        result = release.preflight(manifest, verify=True)
        good(result['declarations_valid'] and all(row['status'] == 'VERIFIED' for row in result['input_files']),
             'Same common path handles second source transition: ' + manifest['configuration']['version'])
    base = examples[1]
    def invalid(label, change, code):
        manifest = copy.deepcopy(base);change(manifest)
        result = release.preflight(manifest, verify=True)
        good(code in codes(result), label)
        good(result['execution_eligible'] is False and result['production_eligible'] is False, label + ': eligibility remains false')
    invalid('Unknown previous-version synonym rejected',lambda m:m['configuration'].update(previous_version='any'), 'SCHEMA_INVALID')
    invalid('Unresolved artifact reference rejected',lambda m:m['configuration']['inputs']['source_data'].append('missing'),'ARTIFACT_REFERENCE_MISSING')
    invalid('Comparison outputs cannot be selected as publisher inputs',lambda m:m['artifacts']['native-release'].update(artifact_type='reference-inversion'),'ARTIFACT_ROLE_MISMATCH')
    invalid('Unsafe before-folder identity rejected',lambda m:m['configuration'].update(version=m['configuration']['version']+'.before-test'),'SOURCE_VERSION_PROFILE_MISMATCH')
    invalid('Different source predecessor rejected',lambda m:m['configuration']['replacement_baseline'].update(source='MTH'),'BASELINE_SOURCE_MISMATCH')
    invalid('Reversed inclusive range rejected',lambda m:m['configuration']['source_atom_ids'].update(end=1),'REVERSED_ID_RANGE')
    invalid('Equal-valued float allocation evidence rejected',lambda m:m['artifacts'][m['configuration']['source_atom_ids']['provenance_ref']]['data'].update(start=float(m['configuration']['source_atom_ids']['start'])),'ID_ALLOCATION_BINDING_MISMATCH')
    invalid('Boolean configured identifier rejected',lambda m:m['configuration']['source_atom_ids'].update(start=True),'SCHEMA_INVALID')
    invalid('Integral floating-point configured identifier rejected',lambda m:m['configuration']['source_atom_ids'].update(start=float(m['configuration']['source_atom_ids']['start'])),'INVALID_ID_RANGE_TYPES')
    invalid('Integral floating-point byte count rejected',lambda m:m['artifacts']['native-release']['files'][0].update(bytes=float(m['artifacts']['native-release']['files'][0]['bytes'])),'INVALID_BYTE_COUNT')
    invalid('Duplicate native role rejected',lambda m:m['artifacts']['native-release']['files'].append(copy.deepcopy(m['artifacts']['native-release']['files'][0])),'DUPLICATE_FILE_ROLE')
    invalid('URI traversal rejected',lambda m:m['artifacts']['native-release']['files'][0].update(uri='repo:tools/fixtures/release-manifests/../outside'),'INVALID_INPUT_LOCATION')
    invalid('Encoded URI control character rejected',lambda m:m['artifacts']['native-release']['files'][0].update(uri='file:///tmp/%00bad'),'INVALID_INPUT_LOCATION')
    invalid('Unreviewed validation profile blocked',lambda m:m['artifacts'][m['configuration']['validation_profile']]['data'].update(profile_id='disable-all'),'PROFILE_ARTIFACT_UNREVIEWED')
    invalid('Partial archive descriptor rejected',lambda m:m['artifacts']['native-release']['files'][0].update(archive_member='file.txt'),'SCHEMA_INVALID')
    def disguised_fixture(manifest):
        value=manifest['artifacts']['native-release'];value['provenance']['evidence_kind']='preserved'
        for file in value['files']:file['uri']=(release.ROOT/file['uri'].removeprefix('repo:')).as_uri()
    invalid('Known fixtures cannot become real evidence by changing URI spelling',disguised_fixture,'INVALID_INPUT_LOCATION')
    # Official replay references are current-release oracles; the prior comparison baseline has another role.
    oracle = copy.deepcopy(base);config=oracle['configuration'];arts=oracle['artifacts']
    arts['official'] = copy.deepcopy(arts['native-release']);arts['official']['artifact_type']='reference-inversion'
    arts['official']['data']['reference_stage']='inversion-src'
    config['replay']={'reference_ref':'official','reference_stage':'inversion-src','comparison_profile':'exact'}
    config['comparison_baseline']=copy.deepcopy(config['replacement_baseline'])
    result=release.preflight(oracle)
    good('COMPARISON_REFERENCE_MISMATCH' not in codes(result),'Current-release official oracle stays independent of prior comparison baseline')
    bad=copy.deepcopy(oracle);bad['artifacts']['official']['version']=config['comparison_baseline']['version']
    good('COMPARISON_REFERENCE_MISMATCH' in codes(release.preflight(bad)),'Prior source data cannot masquerade as a current official oracle')
    bad=copy.deepcopy(oracle);bad['configuration']['replay']['reference_stage']='insertion-package'
    good('COMPARISON_STAGE_MISMATCH' in codes(release.preflight(bad)),'Insertion-augmented reference cannot validate inversion-src output')
    bad=copy.deepcopy(oracle);bad['artifacts']['official']['data']['reference_stage']='insertion-package'
    good('REFERENCE_STAGE_PROVENANCE_MISMATCH' in codes(release.preflight(bad)),'Official artifact stage provenance must match the selected comparison stage')
    unknown=copy.deepcopy(base);unknown['profile']='not-registered'
    good(release.preflight(unknown)['status']=='BLOCKED','Unknown profile is retained as a readiness blocker')
    rejected(lambda:release.schema_errors({}, {'$ref':'https://example.invalid/schema.json'}),'Schema preflight cannot retrieve external references')
    for source,version,prior in [('MDR','MDR_30_0','MDR_29_1'),('RADLEX','RADLEX_5_0','RADLEX_4_3')]:
        manifest=copy.deepcopy(base);config=manifest['configuration'];config.update(source=source,version=version,replacement_baseline={'source':source,'version':prior},source_options={'language':'ENG'} if source=='MDR' else {})
        manifest['profile']=source.lower()+'-publisher-inputs-v1'
        for artifact in manifest['artifacts'].values():
            if artifact['source']!='NCIMETA':artifact.update(source=source,version=version)
        manifest['artifacts'][config['validation_profile']]['data']['profile_id']=source.lower()+'-core-v1'
        result=release.preflight(manifest)
        good(result['manifest_valid'] and result['status']=='BLOCKED' and not result['declarations_valid'] and 'SOURCE_PREFLIGHT_PENDING' in codes(result),source+' uses the common manifest contract but its new adapter stays explicitly pending')
    # Tiny archive fixtures exercise grouped streaming reads without extracting files.
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary).resolve();payloads={'one.txt':b'one\n','two.txt':b'two\n'}
        tar=root/'inputs.tgz';zipped=root/'inputs.zip'
        with tarfile.open(tar,'w:gz') as out:
            for name,raw in payloads.items():
                item=tarfile.TarInfo(name);item.size=len(raw);out.addfile(item,io.BytesIO(raw))
        with zipfile.ZipFile(zipped,'w') as out:
            for name,raw in payloads.items():out.writestr(name,raw)
        def artifact(path,fmt):
            raw=path.read_bytes()
            return {'bundle':{'provenance':{'evidence_kind':'preserved'},'files':[
                {'role':name,'uri':path.as_uri(),'archive_format':fmt,'archive_member':name,
                 'archive_sha256':hashlib.sha256(raw).hexdigest(),'archive_bytes':len(raw),
                 'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)} for name,body in payloads.items()]}}
        for path,fmt in [(tar,'tar.gz'),(zipped,'zip')]:
            before=set(root.iterdir());issues=[]
            rows=release.verify_files(artifact(path,fmt),True,issues)
            good(not issues and len(rows)==2 and all(row['status']=='VERIFIED' for row in rows),fmt+' verifies all selected members in the common grouped path')
            good(set(root.iterdir())==before,fmt+' verification creates no extraction tree or archive copy')
            values=artifact(path,fmt);values['bundle']['files'][0]['sha256']='1'*64;issues=[]
            release.verify_files(values,True,issues)
            good(any(row['code']=='INPUT_BYTES_NOT_VERIFIED' for row in issues),fmt+' member-content mismatch blocks verification')
        duplicate=root/'duplicate.zip'
        with zipfile.ZipFile(duplicate,'w') as out:
            out.writestr('one.txt',b'one\n');out.writestr('./one.txt',b'one\n')
        values=artifact(duplicate,'zip');issues=[];release.verify_files(values,True,issues)
        good(bool(issues),'Noncanonical/duplicate ZIP entries are rejected')
        with patch.object(zipfile.ZipFile,'open',side_effect=RuntimeError('encrypted ZIP')):
            issues=[];release.verify_files(artifact(zipped,'zip'),True,issues)
        good(any(row['code']=='INPUT_BYTES_NOT_VERIFIED' for row in issues),'Encrypted or unsupported ZIP errors become blockers instead of crashing')
        unsafe=root/'unsafe.tgz'
        for label,member in [('traversal',tarfile.TarInfo('../one.txt')),('selected-link',tarfile.TarInfo('one.txt'))]:
            if label=='selected-link':member.type=tarfile.SYMTYPE;member.linkname='/outside'
            with tarfile.open(unsafe,'w:gz') as out:out.addfile(member)
            issues=[];release.verify_files(artifact(unsafe,'tar.gz'),True,issues)
            good(any(row['code']=='INPUT_BYTES_NOT_VERIFIED' for row in issues),'Archive '+label+' rejected without extraction or link following')
        real=root/'plain';real.write_bytes(b'data');link=root/'linked';link.symlink_to(real)
        values={'plain':{'provenance':{'evidence_kind':'preserved'},'files':[{'role':'input','uri':link.as_uri(),'sha256':hashlib.sha256(b'data').hexdigest(),'bytes':4}]}}
        issues=[];release.verify_files(values,True,issues)
        good(bool(issues),'Linked input is not followed')
        values['plain']['files'][0]['uri']='s3://example-bucket/release/input.txt';issues=[]
        with patch.object(release,'_open',side_effect=AssertionError('No network or local open for S3')):
            rows=release.verify_files(values,True,issues)
        good(rows[0]['status']=='REMOTE_NOT_VERIFIED','S3 declarations never trigger implicit downloads')
        path=root/'duplicate.json';path.write_text('{"one":1,"one":2}')
        rejected(lambda:release.load(path),'Duplicate JSON keys are rejected')
        path.write_text('{"bad":NaN}');rejected(lambda:release.load(path),'Nonfinite JSON constants are rejected')
        output=root/'receipt.json';release.write_new(output,{'one':1})
        rejected(lambda:release.write_new(output,{'two':2}),'Existing receipt is never overwritten')
        good(not output.stat().st_mode & 0o222,'Common preflight receipt is not writable')
        mutation=root/'mutation';mutation.write_bytes(b'AAAA');before=mutation.stat();mutation.write_bytes(b'BBBB')
        os.utime(mutation,ns=(before.st_atime_ns,before.st_mtime_ns))
        good(release._stamp(mutation.stat())!=release._stamp(before),'Change time detects same-size content mutation even after restoring mtime')
        # Trust can be injected only in this confined test, never by the public CLI.
        proof={'git_ref':historical.commit('HEAD'),'committed':True,'files':[{'repository_path':'fixture','sha256':'a'*64}]}
        with patch.object(release,'provenance',return_value=proof):
            report=release.preflight(examples[0],verify=True);lock=release.freeze(examples[0],report)
            good(lock['artifact_type']=='ncimeta-release-preflight-lock' and lock['execution_eligible'] is False,'Frozen review lock is a separate non-executable artifact')
            rejected(lambda:worker.verify_lock(lock),'Historical worker rejects a release-preflight lock')
            for key,value in [('resolved_engine_ref','1'*40),('code_provenance',{'git_ref':'0'*40,'committed':True,'files':[]}),('execution_eligible',True)]:
                bad=copy.deepcopy(report);bad[key]=value;release._seal(bad)
                rejected(lambda:release.freeze(examples[0],bad),'Freeze rejects resealed tampering: '+key)
            stale=copy.deepcopy(report);stale['artifact_bindings']['publisher']['reference']='sha256:'+'2'*64;release._seal(stale)
            rejected(lambda:release.freeze(examples[0],stale),'Freeze rejects changed artifact bindings')
            local=copy.deepcopy(examples[0])
            for file in local['artifacts']['publisher']['files']:
                source=release.location(file,True);target=root/source.name;target.write_bytes(source.read_bytes());file['uri']=target.as_uri()
            snapshot=release.preflight(local,verify=True)
            changed=release.location(local['artifacts']['publisher']['files'][0],True);changed.write_bytes(changed.read_bytes()+b'changed')
            rejected(lambda:release.freeze(local,snapshot),'Freeze rejects verified input changed after preflight')
        good(release.provenance('release_nci')['git_ref'] is None or release.provenance('release_nci')['committed'],'Dirty code is never labeled as a committed Git execution')
        # The CLI must retain a blocked report and a distinct exit3 for unsupported admission.
        path=root/'unknown.json';path.write_text(json.dumps(unknown));out=root/'blocked.json'
        result=subprocess.run([sys.executable,'-B',str(release.ROOT/'tools/inversion_request.py'),'preflight-release',str(path),'--output',str(out)],capture_output=True,text=True)
        good(result.returncode==3 and release.load(out)['status']=='BLOCKED','Common CLI writes the unknown-profile blocker with exit3')
        result=subprocess.run([sys.executable,'-B',str(release.ROOT/'tools/inversion_request.py'),'preflight-release',str(path),'--output',str(out)],capture_output=True,text=True)
        good(result.returncode==2,'CLI refuses output collisions before further work')
    return passed


if __name__=='__main__':
    checks=check()
    for label in checks:print('PASS',label)
    print(len(checks),'common release-manifest checks passed')
