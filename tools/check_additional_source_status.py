#!/usr/bin/env python3
"""Exercise actual read-only CLI parsing for additional-source characterizations."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import inversion_remote as remote


def check():
    checks=[]
    with tempfile.TemporaryDirectory(prefix='additional-source-status-') as temporary:
        for source in ('MDR','RADLEX'):
            for operation in ('status','collect'):
                output=Path(temporary)/(source+'-'+operation+'.json')
                record={'source':source,'run_id':'fixture-run','records':{'status.json':{'status':'complete'}}}
                argv=['inversion_remote.py','--socket','/tmp/fixture.sock',operation,'--source',source,'--run-id','fixture-run','--output',str(output)]
                with patch.object(sys,'argv',argv),patch.object(remote,'remote',return_value=record) as call,redirect_stdout(io.StringIO()):remote.main()
                program=call.call_args.args[0]
                assert source in program and output.is_file() and remote.load(output)==record
                compile(program.split('\n',1)[1].rsplit('\nNCIM_COMMON_READ',1)[0],'<read-only-status>','exec')
                checks.append(source+' '+operation+' accepts the CLI source and retrieves read-only evidence')
    return checks


if __name__=='__main__':
    for result in check():print('PASS',result)
