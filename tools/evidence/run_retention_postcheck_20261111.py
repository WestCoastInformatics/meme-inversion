#!/usr/bin/env python3
"""Detached driver for the read-only approved-retention postcheck."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import sys
import time
import traceback


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2);handle.write('\n')
        handle.flush();os.fsync(handle.fileno())
    path.chmod(0o444)


def main(request_path):
    control = request_path.parent
    if socket.gethostname().split('.')[0] != 'ncias-d3777-c' or pwd.getpwuid(os.getuid()).pw_name != 'tomcata':
        raise RuntimeError('Postcheck requires tomcata on dev')
    request = json.loads(request_path.read_text())
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save(control / 'started.json', {'status': 'running', 'started_at': started, 'code_ref': request['verifier_code_ref']})
    begin = time.monotonic()
    try:
        for relative, expected in request['apparatus_sha256'].items():
            path = control / relative
            if path.is_symlink() or path.resolve() != path or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError('Frozen verifier/fixture apparatus changed')
        apparatus = control / 'apparatus'
        with (control / 'fixtures.stdout.log').open('x') as out, (control / 'fixtures.stderr.log').open('x') as err:
            subprocess.run([sys.executable, '-B', str(apparatus / 'check_retention_compaction_postcheck.py')],
                           cwd=control, stdin=subprocess.DEVNULL, stdout=out, stderr=err, check=True)
        sys.path.insert(0, str(apparatus));sys.dont_write_bytecode = True
        from evidence.verify_retention_compaction_20261111 import verify
        result = verify(request)
        result.update(code_ref=request['verifier_code_ref'], started_at=started,
                      completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      elapsed_seconds=round(time.monotonic() - begin, 2), independent_reader_fixtures_passed=13,
                      request_sha256=hashlib.sha256(request_path.read_bytes()).hexdigest())
        save(control / 'result.json', result)
        save(control / 'complete.json', {'status': 'complete', 'verdict': result['status'],
                                        'result_sha256': hashlib.sha256((control / 'result.json').read_bytes()).hexdigest()})
        print(result['status'], flush=True)
    except BaseException as error:
        save(control / 'failed.json', {'status': 'failed', 'error': str(error), 'started_at': started,
                                      'code_ref': request['verifier_code_ref']})
        traceback.print_exc();raise


if __name__ == '__main__':
    main(Path(sys.argv[1]))
