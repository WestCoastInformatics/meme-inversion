#!/usr/bin/env python3
"""Characterize captured MTH preparation defects and confined fix proposals.

Captured files are never edited. Proposed changes exist only in a temporary
directory. No complete shell script, API, database or publisher workflow runs.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'sources/MTH_2026AA'


def mrsab(source, version, current='Y'):
    fields = [''] * 25
    fields[0:7] = ['C0000001', 'C0000002', version, source, source + ' title', source, version]
    fields[21:23] = [current, 'Y']
    return '|'.join(fields) + '|\n'


def run_guess(directory, old, current, producer):
    (directory / 'old').mkdir(exist_ok=True)
    (directory / 'Meta').mkdir(exist_ok=True)
    (directory / 'old/ncisources.spec').write_text(old)
    (directory / 'Meta/MRSAB.RRF').write_text(current)
    script = directory / 'guess-candidate.pl'
    script.write_text(producer)
    return subprocess.run(['/usr/bin/perl', str(script)], cwd=directory,
                          capture_output=True, text=True, timeout=30)


def candidates(producer):
    wrong = "} elsif ($oTYPE = 'SPECIAL') {"
    assert producer.count(wrong) == 1
    equality = producer.replace(wrong, "} elsif ($oTYPE eq 'SPECIAL') {")
    branch = '\t    $TYPE = $oTYPE;\n\t}\n\t&getOLD;'
    assert equality.count(branch) == 1
    reject_unknown = equality.replace(branch,
        '\t    $TYPE = $oTYPE;\n\t} else {\n'
        '\t    die "Unknown prior disposition $oTYPE for $RSAB\\n";\n'
        '\t}\n\t&getOLD;')
    return equality, reject_unknown


def validation_commands():
    script = (SOURCE / 'preinvert2.s').read_text()
    expected = [line for line in script.splitlines() if line.startswith("awk -F\\| '$2==")]
    missing = [line for line in script.splitlines() if line.startswith('set bad=`')]
    assert len(expected) == len(missing) == 1
    # Run only these actual read-only data commands, with their output file in
    # the fixture. The surrounding tcsh/API/MetamorphoSys code is never invoked.
    check_missing = missing[0].split('`')[1]
    fixed = expected[0].replace('$2=="KEEP"', '$3=="KEEP"').replace('$2 == "UPDATE"', '$3 == "UPDATE"')
    assert fixed != expected[0]
    return expected[0], fixed, check_missing


def run_validation(directory, decisions, inventory, expected_command, missing_command):
    (directory / 'ncisources.spec').write_text(decisions)
    (directory / 'ncimid.sources').write_text(inventory)
    result = subprocess.run(['/bin/sh', '-c', expected_command], cwd=directory,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    missing = subprocess.run(['/bin/sh', '-c', missing_command], cwd=directory,
                             capture_output=True, text=True, timeout=30)
    assert missing.returncode == 0, missing.stderr
    return (directory / 'sources.expected').read_text(), missing.stdout


def check():
    checks = []

    def good(condition, label):
        assert condition, label
        checks.append(label)

    producer = (SOURCE / 'guess.ncisources.spec.pl').read_text()
    equality, proposed = candidates(producer)
    actual_cmd, fixed_cmd, missing_cmd = validation_commands()
    before = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in
              ('guess.ncisources.spec.pl', 'preinvert1.s', 'preinvert2.s', 'genmmsysconfigs.pl')}
    with tempfile.TemporaryDirectory(prefix='mth-preparation-defects-') as temporary:
        directory = Path(temporary)
        # The unresolved previous decision is realistic output from the same
        # helper for a previously unseen source, which must be reviewed.
        old = 'AOD|AOD_2000|KEEP|\nBROKEN|BROKEN_1|--NEW?--|\n'
        current = mrsab('AOD', 'AOD_2000') + mrsab('BROKEN', 'BROKEN_2')
        actual = run_guess(directory, old, current, producer)
        good(actual.returncode == 0 and actual.stdout == 'AOD|AOD_2000|KEEP|\nBROKEN|BROKEN_2|SPECIAL|\n',
             'Actual captured helper silently changes an unresolved prior disposition into SPECIAL')
        (directory / 'ncisources.spec').write_text(actual.stdout)
        (directory / 'template.prop').write_text('gov.nih.nlm.umls.mmsys.filter.SourcesFilter.selected_sources=\n')
        downstream = subprocess.run(['/usr/bin/perl', str(SOURCE / 'genmmsysconfigs.pl')],
                                    cwd=directory, capture_output=True, text=True, timeout=30)
        good(downstream.returncode == 0 and (directory / 'ncirest.prop').read_text() ==
             'gov.nih.nlm.umls.mmsys.filter.SourcesFilter.selected_sources=AOD|AOD;SRC|SRC\n',
             'Actual subset-config producer excludes the silently recast SPECIAL source from selected sources')
        weak = run_guess(directory, old, current, equality)
        good(weak.returncode == 0 and weak.stdout == 'AOD|AOD_2000|KEEP|\nBROKEN|BROKEN_2|KEEP|\n',
             'Equality-only patch still silently reuses the previous source disposition')
        corrected = run_guess(directory, old, current, proposed)
        good(corrected.returncode != 0 and 'Unknown prior disposition --NEW?-- for BROKEN' in corrected.stderr,
             'Proposed comparison plus rejecting else stops on the unresolved prior disposition')
        # Exercise only the actual two caller lines, with the proposed helper
        # confined to the fixture. No updatevsabs/API/full tcsh script runs.
        if not Path('/bin/tcsh').is_file():
            raise RuntimeError('The caller-propagation fixture requires local /bin/tcsh')
        helper = directory / 'guess.ncisources.spec.pl'
        helper.write_text(proposed)
        helper.chmod(0o750)
        (directory / 'ncisources.spec').write_text('previously reviewed plan\n')
        caller_file = directory / 'confined-caller.s'
        caller_file.write_text('./guess.ncisources.spec.pl >ncisources.spec\ncp -p ncisources.spec{,.guessed}\n')
        caller = subprocess.run(['/bin/tcsh', '-f', str(caller_file)],
                                cwd=directory, capture_output=True, text=True, timeout=30)
        good(caller.returncode == 0 and 'Unknown prior disposition' in caller.stderr and
             (directory / 'ncisources.spec').read_text() == 'AOD|AOD_2000|KEEP|\n' and
             (directory / 'ncisources.spec.guessed').read_text() == 'AOD|AOD_2000|KEEP|\n',
             'Actual tcsh caller lines ignore helper failure and publish its partial guessed plan')
        reviewed = 'previously reviewed plan\n'
        (directory / 'ncisources.spec').write_text(reviewed)
        caller_file.write_text(
            './guess.ncisources.spec.pl >ncisources.spec.candidate\n'
            'if ($status != 0) exit 1\n'
            '/bin/mv -f ncisources.spec.candidate ncisources.spec\n'
            'cp -p ncisources.spec{,.guessed}\n')
        caller = subprocess.run(['/bin/tcsh', '-f', str(caller_file)],
                                cwd=directory, capture_output=True, text=True, timeout=30)
        good(caller.returncode != 0 and (directory / 'ncisources.spec').read_text() == reviewed,
             'Confined caller proposal propagates helper failure and preserves the reviewed plan')
        for disposition in ('', 'DEFER', 'unknown'):
            invalid = old.replace('--NEW?--', disposition)
            got = run_guess(directory, invalid, current, proposed)
            good(got.returncode != 0 and 'Unknown prior disposition' in got.stderr,
                 'Proposed rejection also covers invalid prior disposition ' + repr(disposition))
        # Every legitimate prior disposition plus new/noncurrent/removed source
        # handling, version changes, MTH forced UPDATE and inherited qualifiers.
        old_valid = ('AOD|AOD_2000|KEEP|\nCVX|CVX_2025|UPDATE|exclude termgroups: XM\n'
                     'EXCLUDED|EXCLUDED_1|EXCLUDE|\nGONE|GONE_1|UPDATE|\n'
                     'MTH|MTH_2025AB|KEEP|exclude termgroups: CV,XM\n'
                     'PRIORNEW|PRIORNEW_1|NEW|\nREMOVED|REMOVED_1|REMOVE|\n'
                     'SPECIAL|SPECIAL_1|SPECIAL|\n')
        new_valid = ''.join(mrsab(*row) for row in
                           [('AOD', 'AOD_2000'), ('CVX', 'CVX_2026'), ('EXCLUDED', 'EXCLUDED_2'),
                            ('MTH', 'MTH_2026AA'), ('NEWONE', 'NEWONE_1'),
                            ('NONCURRENT', 'NONCURRENT_1', 'N'), ('PRIORNEW', 'PRIORNEW_1'),
                            ('REMOVED', 'REMOVED_1'), ('SPECIAL', 'SPECIAL_2')])
        golden = ('AOD|AOD_2000|KEEP|\nCVX|CVX_2026|UPDATE|exclude termgroups: XM\n'
                  'EXCLUDED|EXCLUDED_2|EXCLUDE|\nGONE|GONE_1|REMOVE|\n'
                  'MTH|MTH_2026AA|UPDATE|exclude termgroups: CV,XM\n'
                  'NEWONE|NEWONE_1|--NEW?--|\nNONCURRENT|NONCURRENT_1|EXCLUDE|\n'
                  'PRIORNEW|PRIORNEW_1|KEEP|\nREMOVED|REMOVED_1|EXCLUDE|\n'
                  'SPECIAL|SPECIAL_2|SPECIAL|\n')
        valid_actual = run_guess(directory, old_valid, new_valid, producer)
        valid_fixed = run_guess(directory, old_valid, new_valid, proposed)
        good(valid_actual.returncode == valid_fixed.returncode == 0 and valid_actual.stdout == valid_fixed.stdout == golden,
             'Actual helper and confined proposal are byte-compatible for all six valid prior dispositions and normal transitions')
        # A KEEP or UPDATE must identify a source in the frozen installed-source
        # inventory; NEW/EXCLUDE/REMOVE/SPECIAL are not part of this old check.
        inventory = ' SAB| VSAB\nAOD|AOD_2000\n'
        for disposition in ('KEEP', 'UPDATE'):
            decisions = 'AOD|AOD_2000|KEEP|\nCVX|CVX_2026|' + disposition + '|\n'
            old_expected, old_missing = run_validation(directory, decisions, inventory, actual_cmd, missing_cmd)
            good(old_expected == old_missing == '',
                 'Actual field-2 command misses an absent installed source marked ' + disposition)
            new_expected, new_missing = run_validation(directory, decisions, inventory, fixed_cmd, missing_cmd)
            good(new_expected == 'AOD\nCVX\n' and new_missing == 'CVX\n',
                 'Proposed field-3 command identifies the absent ' + disposition + ' source')
        decisions = ('AOD|AOD_2000|KEEP|\nCVX|CVX_2026|UPDATE|\nNEWONE|NEWONE_1|NEW|\n'
                     'EXCLUDED|EXCLUDED_1|EXCLUDE|\nREMOVED|REMOVED_1|REMOVE|\nSPECIAL|SPECIAL_1|SPECIAL|\n')
        complete = inventory + 'CVX|CVX_2025\n'
        _, actual_missing = run_validation(directory, decisions, complete, actual_cmd, missing_cmd)
        fixed_expected, fixed_missing = run_validation(directory, decisions, complete, fixed_cmd, missing_cmd)
        good(actual_missing == fixed_missing == '' and fixed_expected == 'AOD\nCVX\n',
             'Valid installed KEEP/UPDATE sources pass and other dispositions are not wrongly required to exist')
        sources_expected = subprocess.run(['/bin/sh', '-c', fixed_cmd], cwd=directory,
                                          capture_output=True, text=True, timeout=30)
        good(sources_expected.returncode == 0 and (directory / 'sources.expected').read_text() == 'AOD\nCVX\n',
             'Fixed validation reads actual disposition field without changing source/version semantics')
    good(before == {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in before},
         'All captured preparation producers remain byte-for-byte unchanged')
    return checks


if __name__ == '__main__':
    checks = check()
    print(json.dumps({'status': 'PASS_PREPARATION_DEFECT_CHARACTERIZATION', 'checks_passed': len(checks),
                      'checks': checks, 'captured_source_modified': False,
                      'full_shell_workflow_executed': False, 'server_accessed': False}, indent=2))
