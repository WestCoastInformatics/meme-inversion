#!/usr/bin/env python3
"""Exercise MDR worker orchestration with real preservation/snapshots/control IO."""
import json
from pathlib import Path
import tempfile
import sys
from contextlib import nullcontext
from unittest.mock import patch

import audit_mdr_corrections
import inversion_worker
import replay_framework_core as replay
import replay_mth_core
import prepare_snomed_candidate


def check():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='mdr-worker-') as temporary:
        for label,previous_status,mutate in [('completed-predecessor','complete',False),('failed-predecessor','failed',False),('late-output-change','failed',True)]:
            root=Path(temporary)/label;target=root/'sources/MDR_29_1';(target/'src').mkdir(parents=True);(target/'etc').mkdir();target.chmod(0o700)
            previous=root/'qa/replay-requests/previous-run';previous.mkdir(parents=True);run=previous.parent/'mdr-fixture';run.mkdir()
            for name in replay.comparison.OUTPUTS:(target/'src'/name).write_bytes(('previous '+name+'\n').encode())
            state={'source':'MDR','version':'MDR_29_1','run_id':'previous-run','engine_ref':replay.MDR_ENGINE,'status':previous_status,'error':'synthetic failure'}
            replay.save(target/'etc/replay-active-run.json',state);replay.save(previous/'status.json',state)
            if previous_status=='complete':replay.save(previous/'result.json',{'run_id':'previous-run','engine_ref':replay.MDR_ENGINE,'comparison':{'files':{name:{'candidate':replay.comparison.file_info(target/'src'/name)} for name in replay.comparison.OUTPUTS}}})
            package={'source':'MDR','version':'MDR_29_1','run_id':'mdr-fixture','engine_ref':replay.MDR_ENGINE,'runtime_ref':replay.MDR_RUNTIME,'case_variant':'consistent-history-context','perl_hash_seed':'1','capsule_sha256':'fixture','apparatus_ref':'fixture'}
            def prepare(data):
                (target/'bin').mkdir(parents=True);(target/'etc').mkdir();(target/'src').mkdir()
                return {'generated_outputs_seeded':False}
            calls=[]
            def execute(command,**kwargs):
                calls.append(command[-1])
                if command[-1].endswith('invert_mdr.pl') and '-c' not in command:
                    for name in replay.comparison.OUTPUTS:(target/'src'/name).write_bytes(b'fresh core\n')
                if command[-1].endswith('append_atn.pl') and '-c' not in command:(target/'src/attributes.src').write_bytes(b'fresh core plus history\n')
                return {'exit_status':0,'network':'disabled'}
            def compare(*args):return {'files':{name:{'candidate':replay.comparison.file_info(target/'src'/name)} for name in replay.comparison.OUTPUTS},'acceptance':{'status':'DIFFERENCES_REQUIRE_REVIEW'}}
            def audit(*args):
                assert (run/'before-history.attributes.src').read_bytes()==b'fresh core\n'
                if mutate:(target/'src/attributes.src').write_bytes(b'unexpected late edit\n')
                return {'status':'PASS_REVIEWED_CORRECTIONS'}
            def publish(source,destination):
                if destination.exists():raise FileExistsError(destination)
                source.rename(destination)
            publisher=patch.object(prepare_snomed_candidate,'publish',side_effect=publish) if sys.platform=='darwin' else nullcontext()
            with publisher,patch.object(replay,'ROOT',root),patch.object(replay,'verify_capsule'),patch.object(replay,'verify_inputs'),patch.object(replay,'capacity'),patch.object(replay_mth_core,'idle'),patch.object(replay,'prepare',side_effect=prepare),patch.object(replay,'execute',side_effect=execute),patch.object(replay.comparison,'compare',side_effect=compare),patch.object(audit_mdr_corrections,'audit',side_effect=audit):
                package['previous_source_receipt']=replay.inspect_previous(package,'previous-run');path=run/'characterization.lock.json';replay.save(path,package)
                if mutate:
                    try:replay.worker(path)
                    except RuntimeError:pass
                    else:raise AssertionError('Late output mutation was accepted')
                    assert json.loads((run/'status.json').read_text())['status']=='failed' and not (run/'result.json').exists()
                    checks.append('Late output change after audit leaves a failed job without accepted results')
                else:
                    replay.worker(path);final=json.loads((run/'result.json').read_text())
                    assert final['acceptance']['status']=='PASS_REVIEWED_CORRECTIONS' and final['raw_acceptance']['status']=='DIFFERENCES_REQUIRE_REVIEW'
                    assert (run/'before-history.attributes.src').read_bytes()==b'fresh core\n' and (target/'src/attributes.src').read_bytes()==b'fresh core plus history\n'
                    assert len(calls)==4 and (run/'raw-result.json').is_file()
                    preserved=target.with_name('MDR_29_1.before-mdr-fixture');assert preserved.is_dir() and preserved.stat().st_mode&0o222==0
                    checks.append('Actual worker preserves '+previous_status+' predecessor, captures pre-history output, appends, compares, audits and verifies final hashes')
            for path in root.rglob('*'):
                if not path.is_symlink():path.chmod(0o700 if path.is_dir() else 0o600)
    return checks


if __name__=='__main__':
    for item in check():print('PASS',item)
