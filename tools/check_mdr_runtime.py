#!/usr/bin/env python3
"""Verify the MDR runtime switch, exact restoration and failure rollback."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import mdr_correction_runtime as runtime
import replay_framework_core as replay
import replay_mth_core


def check():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='mdr-runtime-') as temporary:
        for mode in ['success','activation-failure','restoration-failure','unknown-runtime']:
            root=Path(temporary)/mode;(root/'INV/lib').mkdir(parents=True);(root/'qa/replay-requests').mkdir(parents=True)
            prior=[]
            for index in range(169):
                name='INV/lib/Hierarchy.pm' if index==0 else 'INV/file-'+str(index)
                path=root/name;path.write_bytes(b'original\n');prior.append({'relative_path':name,'sha256':replay.sha(path)})
            desired=[dict(item) for item in prior];desired[0]['sha256']=hashlib.sha256(b'stable\n').hexdigest()
            receipt=root/'candidate-runtime.json';receipt.write_bytes(b'{"original":true}\n');receipt.chmod(0o640)
            package={'run_id':'mdr-runtime-fixture','case_variant':'consistent-history-context','runtime_ref':replay.MDR_RUNTIME,'prior_runtime_ref':'production-fixture',
                     'runtime_files':desired,'prior_runtime_files':prior,'runtime_override':{'relative_path':'INV/lib/Hierarchy.pm','sha256':desired[0]['sha256'],'prior_sha256':prior[0]['sha256'],'data_b64':base64.b64encode(b'stable\n').decode()}}
            with patch.object(replay,'ROOT',root),patch.object(replay,'verify_capsule'),patch.object(replay,'capacity'),patch.object(replay_mth_core,'idle'):
                library=root/'INV/lib/Hierarchy.pm';original=replay.require;failed=False
                def injected(path,sha):
                    nonlocal failed
                    if not failed and path==library and sha==desired[0]['sha256'] and library.read_bytes()==b'stable\n':
                        failed=True;raise RuntimeError('injected verification failure')
                    return original(path,sha)
                if mode=='unknown-runtime':
                    library.write_bytes(b'unknown\n')
                    try:runtime.switch(package)
                    except RuntimeError:checks.append('Unknown installed runtime is rejected before replacement')
                    else:raise AssertionError('Unknown runtime accepted')
                    assert library.read_bytes()==b'unknown\n';continue
                if mode=='activation-failure':
                    with patch.object(replay,'require',side_effect=injected):
                        try:runtime.switch(package)
                        except RuntimeError:pass
                        else:raise AssertionError('Injected failure accepted')
                    assert library.read_bytes()==b'original\n' and receipt.read_bytes()==b'{"original":true}\n'
                    checks.append('Failed activation restores original library and receipt bytes');continue
                activation=runtime.switch(package);assert activation['files_verified']==169 and library.read_bytes()==b'stable\n'
                active_receipt=receipt.read_bytes()
                if mode=='restoration-failure':
                    def restore_failure(path,sha):
                        nonlocal failed
                        if not failed and path==library and sha==prior[0]['sha256'] and library.read_bytes()==b'original\n':
                            failed=True;raise RuntimeError('injected restoration verification failure')
                        return original(path,sha)
                    with patch.object(replay,'require',side_effect=restore_failure):
                        try:runtime.switch(package,restore=True)
                        except RuntimeError:pass
                        else:raise AssertionError('Injected restore failure accepted')
                    assert library.read_bytes()==b'stable\n' and receipt.read_bytes()==active_receipt
                    checks.append('Failed restoration retains matching active library and metadata');continue
                backup=root/'qa/replay-requests/mdr-runtime-fixture.runtime-before/Hierarchy.pm'
                assert backup.read_bytes()==b'original\n' and backup.stat().st_mode&0o222==0
                checks.append('Original shared library is preserved read-only before activation')
                restored=runtime.switch(package,restore=True)
                assert restored['files_verified']==169 and library.read_bytes()==b'original\n' and receipt.read_bytes()==b'{"original":true}\n' and receipt.stat().st_mode&0o777==0o640
                checks.append('All 169 production runtime hashes and exact previous metadata/modes are restored')
    return checks


if __name__=='__main__':
    for item in check():print('PASS',item)
