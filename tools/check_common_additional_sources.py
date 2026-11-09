#!/usr/bin/env python3
"""Check real common MDR/RADLEX dispatch and fail-closed correction acceptance.

Native execution is stubbed; filesystem snapshots, copies, hashes, packages and
the common control/audit paths are real. Producer/native audit fixtures are separate.
"""
import base64
import copy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import audit_mdr_corrections as audit
import inversion_worker as common
import replay_framework_core as framework
import replay_mth_core


def adapters():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='common-additional-adapters-') as temporary:
        for source,version in [('MDR','MDR_29_1'),('RADLEX','RADLEX_4_3')]:
            root=Path(temporary)/source;target=root/'sources'/version;outer=root/'qa/fixture';outer.mkdir(parents=True)
            data={'source':source,'version':version,'run_id':'fixture-run','engine_ref':framework.MDR_ENGINE if source=='MDR' else framework.ENGINE,
                  'runtime_ref':framework.MDR_RUNTIME if source=='MDR' else framework.PRODUCTION_RUNTIME,
                  'apparatus_ref':'fixture','capsule_sha256':'fixture','case_variant':'consistent-history-context' if source=='MDR' else 'as-produced','perl_hash_seed':'1'}
            lock={'request':{'source':source},'run_id':'fixture-run'}
            def prepare(package):
                for name in ['bin','src','tmp','etc']:(target/name).mkdir(parents=True,exist_ok=True)
                assert not any((target/'src'/name).exists() for name in framework.comparison.OUTPUTS)
                return {'generated_outputs_seeded':False}
            commands=[]
            def execute(command,**kwargs):
                script=Path(command[-1]).name;commands.append((script,'-c' in command))
                if '-c' not in command:
                    if script in ('invert_mdr.pl','makesrc.pl'):
                        for name in framework.comparison.OUTPUTS:(target/'src'/name).write_bytes(('native '+name+'\n').encode())
                    elif script=='append_atn.pl':(target/'src/attributes.src').write_bytes(b'native plus history\n')
                    elif script=='remove_dup_rels.pl':(target/'tmp/relationships_no_dups_no_self_refs.tmp').write_bytes(b'clean relationships\n')
                    elif script=='remove_dup_classes.pl':
                        (target/'tmp/classes_unique.txt').write_bytes(b'clean atoms\n');(target/'tmp/mergefacts_new.txt').write_bytes(b'clean merges\n')
                    elif script=='remove_dup_attributes.pl':(target/'tmp/attributes_unique.txt').write_bytes(b'clean attributes\n')
                return {'exit_status':0,'network':'disabled'}
            def compare(*args):return {'files':{name:{'candidate':framework.comparison.file_info(target/'src'/name)} for name in framework.comparison.OUTPUTS},'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW' if source=='MDR' else 'PASS_EQUIVALENT'}}
            with patch.object(common,'package',return_value=data),patch.object(framework,'ROOT',root),patch.object(framework,'prepare',side_effect=prepare) as preparation,patch.object(framework,'verify_capsule'),patch.object(framework,'verify_inputs'),patch.object(framework,'capacity',side_effect=AssertionError('Common preflight already checked the reviewed budget')),patch.object(replay_mth_core,'idle'),patch.object(framework,'execute',side_effect=execute),patch.object(framework.comparison,'compare',side_effect=compare),patch.object(audit,'audit',side_effect=AssertionError('Common outer audit owns acceptance')):
                common.prepare(lock,target);result=common.convert(lock,target,outer,None)
                assert preparation.call_count==1 and result['common_adapter_integration_executed']
                assert len(commands)==(4 if source=='MDR' else 8)
                inner=target/'etc/qa/replay-runs/fixture-run'
                if source=='MDR':
                    assert (inner/'before-history.attributes.src').read_bytes()==b'native attributes.src\n'
                    assert (target/'src/attributes.src').read_bytes()==b'native plus history\n'
                    assert result['acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW' and not (inner/'correction-audit.json').exists()
                    checks.append('Common MDR prepares once, preserves pre-history bytes, appends history and leaves correction acceptance to the outer audit')
                else:
                    assert all((inner/('before-cleanup.'+name)).is_file() for name in ['classes_atoms.src','attributes.src','relationships.src','mergefacts.src'])
                    assert (target/'src/classes_atoms.src').read_bytes()==b'clean atoms\n' and (target/'src/attributes.src').read_bytes()==b'clean attributes\n'
                    assert (target/'src/relationships.src').read_bytes()==b'clean relationships\n' and (target/'src/mergefacts.src').read_bytes()==b'clean merges\n'
                    checks.append('Common RADLEX prepares once and performs all three original cleanup stages with their actual output copies')
                assert result['input_engine_runtime_and_output_hashes_verified_after_run'];checks.append(source+' adapter returns all five recorded output hashes')
    return checks


def fixture(root):
    target=root/'sources/MDR_29_1';(target/'src').mkdir(parents=True);run=root/'qa/replay-requests/fixture-mdr';run.mkdir(parents=True)
    files={}
    for name in framework.comparison.OUTPUTS:
        path=target/'src'/name;path.write_bytes(('candidate '+name+'\n').encode());files[name]={'candidate':{'sha256':common.sha(path)}}
    files['attributes.src']['attribute_diagnostics']={'positive_unique_ids':True}
    request={'source':'MDR','version':'MDR_29_1','engine_ref':common.MDR_CORRECTION_ENGINE,'case_variant':'consistent-history-context','comparison_profile':'reviewed-corrections'}
    lock={'request':request,'run_id':run.name,'apparatus_ref':'1'*40,'runtime_ref':framework.MDR_RUNTIME,'configuration':{'source_options':{'language':'ENG'}},
          'case':{'correction_audit':copy.deepcopy(common.MDR_CORRECTION_AUDIT),'legacy_case':{'source':'MDR','version':'MDR_29_1','reference_files':[{'output_name':name} for name in files]}},
          'modules_b64':{'audit_mdr_corrections.py':base64.b64encode(Path(audit.__file__).read_bytes()).decode()},'code_files':[],'runtime_files':[]}
    result={'source':'MDR','version':'MDR_29_1','run_id':run.name,'engine_ref':request['engine_ref'],'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW'},
            'comparison':{'files':files,'structure':{'candidate':{'checks_passed':True}}}}
    report={'status':'PASS_REVIEWED_CORRECTIONS','run_id':run.name,'engine_ref':request['engine_ref'],'runtime_ref':framework.MDR_RUNTIME,
            'conversion_apparatus_ref':lock['apparatus_ref'],'audit_tool_sha256':common.sha(Path(audit.__file__)),
            'raw_comparison_status':'DIFFERENCES_REQUIRE_REVIEW','independent_validation_passed':True,'raw_comparison_rewritten':False,'production_eligible':False,
            'expected_attribute_sha256':files['attributes.src']['candidate']['sha256']}
    return lock,target,run,result,report


def acceptance():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='common-mdr-acceptance-') as temporary:
        for mode in ['pass','failed-candidate-validation','duplicate-attribute-id','child-failure','wrong-run','wrong-runtime','wrong-attribute-prediction','changed-raw','changed-output','missing-report']:
            lock,target,run,result,report=fixture(Path(temporary)/mode);original=copy.deepcopy(result)
            if mode=='failed-candidate-validation':result['comparison']['structure']['candidate']['checks_passed']=False
            if mode=='duplicate-attribute-id':result['comparison']['files']['attributes.src']['attribute_diagnostics']['positive_unique_ids']=False
            def child(command,**options):
                assert Path(command[2]).name=='audit_mdr_corrections.py' and options['namespace_user']=='current'
                assert json.loads((run/'raw-result.json').read_text())==original
                if mode=='child-failure':raise RuntimeError('synthetic child failure')
                if mode=='wrong-run':report['run_id']='other-run'
                if mode=='wrong-runtime':report['runtime_ref']=framework.PRODUCTION_RUNTIME
                if mode=='wrong-attribute-prediction':report['expected_attribute_sha256']='0'*64
                if mode!='missing-report':common.save(run/'correction-audit.json',report)
                if mode=='changed-raw':(run/'raw-result.json').chmod(0o600);(run/'raw-result.json').write_text('{}\n')
                if mode=='changed-output':(target/'src/attributes.src').write_bytes(b'unexplained edit\n')
                return {'exit_status':0,'network':'disabled','namespace_user':'current'}
            with patch.object(common,'execute',side_effect=child),patch.object(framework,'verify_inputs') as verify:
                if mode=='pass':
                    common.review_corrections(lock,target,run,result)
                    assert result['acceptance']['status']=='PASS_REVIEWED_CORRECTIONS' and result['raw_acceptance']==original['acceptance']
                    assert result['comparison']==original['comparison'] and json.loads((run/'raw-result.json').read_text())==original and verify.call_count==1
                    assert not (run/'raw-result.json').stat().st_mode&0o222
                    checks.append('Common MDR accepts only a bound complete-file prediction and retains unchanged raw comparison with post-audit input/output checks')
                else:
                    try:common.review_corrections(lock,target,run,result)
                    except (ValueError,RuntimeError):checks.append('Common MDR audit fails closed: '+mode)
                    else:raise AssertionError('Invalid correction accepted: '+mode)
    return checks


def check():return adapters()+acceptance()


if __name__=='__main__':
    for item in check():print('PASS',item)
