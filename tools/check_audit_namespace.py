#!/usr/bin/env python3
"""Exercise the actual audit account guard in both Linux namespace mappings."""
import json
import os
from pathlib import Path
import pwd
import socket
import sys
import tempfile

from replay_process import execute, runtime_lock

ROOT = Path('/local/content/MEME/MEME5/inv')


def check():
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Namespace integration fixtures require tomcata on dev')
    values = []
    parent_network = os.readlink('/proc/self/ns/net')
    code = '''import json,os,pwd,sys
sys.path.insert(0,sys.argv[1])
from replay_mth_core import guard
error=None
try:guard()
except RuntimeError as failure:error=str(failure)
print(json.dumps({'uid':os.getuid(),'account':pwd.getpwuid(os.getuid()).pw_name,'guard_passed':error is None,'guard_error':error,'uid_map':open('/proc/self/uid_map').read(),'network_namespace':os.readlink('/proc/self/ns/net')}))
'''
    with runtime_lock(ROOT), tempfile.TemporaryDirectory(prefix='.audit-namespace-fixtures-', dir=str(ROOT / 'sources')) as temporary:
        root = Path(temporary)
        for mapping in ('root', 'current'):
            out, err = root / (mapping + '.json'), root / (mapping + '.err')
            metrics = execute([sys.executable, '-B', '-c', code, str(Path(__file__).parent)], cwd=root,
                              stdout=out, stderr=err, env=os.environ.copy(), progress=lambda metrics: None,
                              timeout=60, namespace_user=mapping)
            result = json.loads(out.read_text())
            assert metrics['exit_status'] == 0 and metrics['namespace_user'] == mapping
            assert result['network_namespace'] != parent_network
            values.append(mapping + ' mapping retains separate network namespace')
            if mapping == 'root':
                assert result['uid'] == 0 and not result['guard_passed']
                values.append('Actual audit guard rejects mapped root identity')
            else:
                assert result['uid'] == os.getuid() and result['account'] == 'tomcata' and result['guard_passed']
                values.append('Actual audit guard accepts preserved tomcata identity offline')
    return values


if __name__ == '__main__':
    values = check()
    for value in values:print('PASS', value)
    print(len(values), 'audit namespace integration checks passed')
