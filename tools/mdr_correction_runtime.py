#!/usr/bin/env python3
"""Switch only the already characterized shared hierarchy pair for MDR testing."""
import base64
import json
import os
from pathlib import Path
import shutil
import tempfile

import replay_framework_core as replay
from replay_process import runtime_lock


def switch(package,restore=False):
    replay.verify_capsule(package)
    if package.get('case_variant')!='consistent-history-context':raise RuntimeError('Only corrected MDR runtime cases are accepted')
    root=replay.ROOT;library=root/'INV/lib/Hierarchy.pm';receipt=root/'candidate-runtime.json'
    control=root/'qa/replay-requests';backup=control/(package['run_id']+'.runtime-before');override=package['runtime_override']
    if override['relative_path']!='INV/lib/Hierarchy.pm':raise RuntimeError('Only the characterized hierarchy dependency may change')
    def verify(items):
        if len(items)!=169:raise RuntimeError('Complete shared runtime is required')
        for item in items:replay.require(root/item['relative_path'],item['sha256'])
    def replace(raw,path,mode):
        fd,name=tempfile.mkstemp(prefix='.'+path.name+'.mdr-',dir=str(path.parent));temporary=Path(name)
        try:
            with os.fdopen(fd,'wb') as handle:handle.write(raw)
            temporary.chmod(mode);os.replace(temporary,path)
        finally:temporary.unlink(missing_ok=True)
    with runtime_lock(root):
        from replay_mth_core import idle
        idle()
        if library.is_symlink() or receipt.is_symlink() or backup.is_symlink():raise RuntimeError('Unexpected runtime path symlink')
        if restore:
            verify(package['runtime_files']);record=json.loads((backup/'switch.json').read_text())
            replay.require(backup/'Hierarchy.pm',override['prior_sha256'])
            active_receipt=receipt.read_bytes() if receipt.exists() else None;active_mode=receipt.stat().st_mode&0o777 if receipt.exists() else None
            replace((backup/'Hierarchy.pm').read_bytes(),library,record['library_mode'])
            try:
                if record['previous_receipt']:
                    replay.require(backup/'candidate-runtime.json',record['previous_receipt_sha256'])
                    replace((backup/'candidate-runtime.json').read_bytes(),receipt,record['previous_receipt_mode'])
                else:receipt.unlink(missing_ok=True)
                verify(package['prior_runtime_files'])
            except BaseException:
                replace(base64.b64decode(override['data_b64']),library,record['library_mode'])
                if active_receipt is not None:replace(active_receipt,receipt,active_mode)
                else:receipt.unlink(missing_ok=True)
                raise
            result={'status':'production-runtime-restored','files_verified':169,'runtime_ref':package['prior_runtime_ref'],'run_id':package['run_id']}
            replay.save(backup/'restore.json',result);return result
        verify(package['prior_runtime_files'])
        replay.require(library,override['prior_sha256']);replay.capacity(package)
        before=library.read_bytes();mode=library.stat().st_mode&0o777
        old_receipt=receipt.read_bytes() if receipt.exists() else None;old_mode=receipt.stat().st_mode&0o777 if receipt.exists() else None
        backup.mkdir();(backup/'Hierarchy.pm').write_bytes(before);(backup/'Hierarchy.pm').chmod(0o400)
        record={'run_id':package['run_id'],'library_mode':mode,'previous_receipt':old_receipt is not None,
                'previous_receipt_mode':old_mode,'previous_receipt_sha256':replay.sha(receipt) if old_receipt is not None else None}
        if old_receipt is not None:(backup/'candidate-runtime.json').write_bytes(old_receipt);(backup/'candidate-runtime.json').chmod(0o400)
        replay.save(backup/'switch.json',record)
        raw=base64.b64decode(override['data_b64'],validate=True)
        if __import__('hashlib').sha256(raw).hexdigest()!=override['sha256']:raise RuntimeError('Runtime override payload differs')
        try:
            replace(raw,library,mode);verify(package['runtime_files'])
            result={'status':'mdr-correction-runtime-activated','run_id':package['run_id'],'runtime_ref':package['runtime_ref'],'files_verified':169,'preserved_runtime':str(backup)}
            replay.save(receipt,result);replay.save(backup/'activation.json',result);return result
        except BaseException:
            replace(before,library,mode)
            if old_receipt is not None:replace(old_receipt,receipt,old_mode)
            else:receipt.unlink(missing_ok=True)
            verify(package['prior_runtime_files']);raise
