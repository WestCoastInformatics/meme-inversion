#!/usr/bin/env python3
"""Run the real NCIt inverter on small, isolated TREF fixtures.

Exercise first/subsequent preferred terms with and without publisher codes and
an intervening synonym. No publisher distribution, API or database is required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

VERSION = 'NCI_2026_10D'


def check(repo_root, script=None, inv_home=None, network_isolation=False):
    script = Path(script) if script else repo_root / 'sources' / VERSION / 'bin/invert_NCI.pl'
    inv_home = Path(inv_home) if inv_home else repo_root / 'INV'
    config = repo_root / 'sources' / VERSION / 'etc/nci.cfg'
    perl = shutil.which('perl')
    if not perl or not script.is_file() or not config.is_file() or not (inv_home / 'lib/NLMInv.pm').is_file():
        raise RuntimeError('The captured NCIt script, configuration and shared runtime are required')
    original1 = '|First FDA preferred term|C1||FDAPT|FDA_ORIG_1|\n'
    original2 = '|Second FDA preferred term|C2||FDAPT|FDA_ORIG_2|\n'
    no_original = '|FDA preferred term without publisher code|C2||FDAPT||\n'
    synonym = '|FDA synonym|C1||FDASY|FDA_SYN_1|\n'
    fixtures = {
        'publisher_code_first': [original1, synonym, no_original, original2],
        'two_publisher_codes_before_initialization': [original1, synonym, original2, no_original],
        'no_publisher_code_first': [no_original, synonym, original1, original2],
    }
    cases = []
    with tempfile.TemporaryDirectory(prefix='nci-pt-regression-') as directory:
        root = Path(directory)
        for name, rows in fixtures.items():
            target = root / name
            for relative in ['bin', 'etc/qa', 'orig', 'tmp', 'src']:
                (target / relative).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script, target / 'bin/invert_NCI.pl')
            # Keep real mappings and templates. The allocation is local to these
            # ephemeral files; no reservation service or production output is used.
            (target / 'etc/nci.cfg').write_bytes(config.read_bytes() + b'\nSaidStart = 100000000\n')
            metadata = []
            for source in ['NCI', 'FDA', 'BLOODPAC']:
                vsab = source + '_2026_10D'
                fields = [vsab, source + '_2026_08E', '0', vsab, source, '2026_10D', source,
                          source + ' fixture', '', '', '', '', '', '', '', 'ENG', '', '', 'UTF-8', 'Y']
                metadata.append('|'.join(fields) + '\n')
            (target / 'src/sources.src').write_text(''.join(metadata))
            (target / 'src/termgroups.src').write_text(
                'NCI_2026_10D/PT|PT|N|N|N|PT\nFDA_2026_10D/PT|PT|N|N|N|PT\n'
                'FDA_2026_10D/SY|SY|N|N|N|SY\n')
            (target / 'orig/MRCONSO.TREF').write_text(
                '|Parent concept|C1||NCIPT||\n|Child concept|C2||NCIPT||\n' + ''.join(rows))
            (target / 'orig/MRSAT.TREF').write_text('')
            (target / 'orig/MRREL.TREF').write_text('R1|C1|SOURCE_CUI|NCI|PAR|isa|C2|SOURCE_CUI|\n')
            env = dict(os.environ, INV_HOME=str(inv_home.resolve()), LANG='C', LC_ALL='C')
            command = [perl, 'invert_NCI.pl']
            if network_isolation:
                command = ['unshare', '--user', '--map-root-user', '--net'] + command
            process = subprocess.run(command, cwd=target / 'bin', env=env,
                                     capture_output=True, text=True, timeout=30)
            failures = []
            atoms = []
            output = target / 'src/classes_atoms.src'
            if process.returncode:
                failures.append('Inverter exited ' + str(process.returncode))
            if output.is_file():
                for row in output.read_text().splitlines():
                    fields = row.split('|')
                    if fields[1] == 'FDA_2026_10D':
                        atoms.append({'id': fields[0], 'termgroup': fields[2], 'code': fields[3],
                                      'name': fields[7], 'source_cui': fields[10]})
            observed = {row['code']: row for row in atoms}
            expected = {'FDA_ORIG_1': ('FDA_2026_10D/PT', 'C1'), 'FDA_ORIG_2': ('FDA_2026_10D/PT', 'C2'),
                        'C2': ('FDA_2026_10D/PT', 'C2'), 'FDA_SYN_1': ('FDA_2026_10D/SY', 'C1')}
            if len(atoms) != len(expected) or set(observed) != set(expected):
                failures.append('Preferred-term/synonym rows or publisher codes changed')
            for code, (termgroup, cui) in expected.items():
                row = observed.get(code)
                if row and (row['termgroup'], row['source_cui']) != (termgroup, cui):
                    failures.append(code + ': expected ' + termgroup + '/' + cui + ', got ' + row['termgroup'] + '/' + row['source_cui'])
            cases.append({'name': name, 'passed': not failures, 'exit_status': process.returncode,
                          'failures': failures, 'fda_atoms': atoms,
                          'log_tail': (process.stdout + process.stderr)[-2000:] if failures else ''})
    return {'script': str(script.resolve()), 'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
            'shared_runtime': str(inv_home.resolve()), 'config_sha256': hashlib.sha256(config.read_bytes()).hexdigest(),
            'all_passed': all(case['passed'] for case in cases), 'cases': cases,
            'network': 'disabled' if network_isolation else 'not isolated; fixtures perform no network operations',
            'scope': 'Real core inverter with synthetic TREF/metadata; no API, QA, insertion or publisher distribution'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--script', type=Path)
    parser.add_argument('--json-output', type=Path)
    parser.add_argument('--offline-namespace', action='store_true', help='Disable networking through a Linux user/network namespace')
    args = parser.parse_args()
    result = check(args.repo_root, args.script, network_isolation=args.offline_namespace)
    if args.json_output:
        args.json_output.write_text(json.dumps(result, indent=2) + '\n')
    for case in result['cases']:
        print(('PASS ' if case['passed'] else 'FAIL ') + case['name'])
        for failure in case['failures']:
            print('  ' + failure)
    raise SystemExit(0 if result['all_passed'] else 1)
