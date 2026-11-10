#!/usr/bin/env python3
"""Golden captured-spec, frozen-input and actual Perl MTH preview checks."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile

import mth_configuration as mth

ROOT = Path(__file__).resolve().parents[1]


def frozen_fixture(variant='consistent-retained-identities'):
    """Read the reviewed case and fetch its exact Git producer bytes."""
    case = json.loads((ROOT / 'docs/inversion-review/case-catalog' /
                       ('mth-' + variant + '.json')).read_text())
    config = copy.deepcopy(case['configuration'])
    files = []
    for item in case['source_files']:
        if item['relative_path'] not in mth.TEMPLATE_NAMES:
            continue
        record = copy.deepcopy(item)
        if record['kind'] == 'file':
            path = 'sources/' + config['version'] + '/' + record['relative_path']
            raw = subprocess.check_output(['git', '-C', str(ROOT), 'show', config['engine_ref'] + ':' + path])
            assert mth.sha(raw) == record['sha256']
            record.update(repository_path=path, data_b64=base64.b64encode(raw).decode(), bytes=len(raw))
        files.append(record)
    return {'configuration': config, 'case': case, 'case_sha256': mth.digest(case),
            'code_files': files}


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def reject(action, label):
        try:
            action()
        except (ValueError, KeyError, TypeError):
            passed.append(label)
        else:
            raise AssertionError(label)

    lock = frozen_fixture()
    original = copy.deepcopy(lock)
    recipe = mth.preview_from_lock(lock)
    templates = {item['relative_path']: item for item in lock['code_files']}
    good(recipe == mth.generate(lock['configuration'], lock['case']['artifacts'], templates),
         'Frozen-lock adapter and pure generator produce the same recipe')
    good(lock == original, 'Preview leaves all input configuration, artifacts and producer bytes unchanged')
    good(json.loads(json.dumps(recipe)) == recipe and recipe == mth.preview_from_lock(lock),
         'Recipe is JSON-stable and repeated previews are deterministic')
    outputs = {item['relative_path']: item for item in recipe['files']}
    good(set(outputs) == {'range3.spec', 'src/inv1.spec', 'src/inv2.spec', 'src/inv3.spec',
                          'ncisources.spec', 'sab.vsab.map', 'src_data'},
         'Only reviewed settings, specs and saved policy data are emitted; no executable copied')
    for name, item in outputs.items():
        golden = base64.b64decode(templates[name]['data_b64'])
        raw = base64.b64decode(item['data_b64'])
        good(raw == golden and item['sha256'] == templates[name]['sha256'] and item['mode'] == '0o444',
             'Independent captured Git golden matches read-only preview: ' + name)
    allocations = recipe['bindings']['legacy_allocation']
    good(allocations == {'SourceAtomIdBase': 769443593, 'SourceAtomIdLimit': 773943592,
                          'SRCbuilder_start': 769443591, 'reserved_SRC_atoms': 2},
         'Complete historical bounds retain the independently captured SRCbuilder offset')
    good(recipe['bindings']['replacement_baseline'] == {'source': 'MTH', 'version': 'MTH_2025AB'} and
         recipe['bindings']['publisher_previous']['version'] == 'MTH_2025AB' and
         recipe['bindings']['publisher_previous']['evidence'] == ['invert1.s:set prevrel', 'prev:captured symlink'],
         'Replacement and publisher-previous roles retain separate explicit evidence')
    good(len(recipe['bindings']['source_decisions']) == 201 and len(recipe['bindings']['vsab_mappings']) == 44,
         'All 201 saved source/version decisions and 44 VSAB mappings are exposed')
    rows = recipe['bindings']['source_decisions']
    good([row['disposition'] for row in rows if row['source'] == 'SNOMEDCT_US'] == ['EXCLUDE', 'UPDATE'] and
         [row['disposition'] for row in rows if row['source'] == 'LNC'] == ['UPDATE'],
         'Multiple historical versions retain distinct decisions without conflating RSAB and VSAB')
    good(recipe['coverage'] == {'source_data_stage': 'prepared', 'range_stage': 'final',
                                'generated_specs_match_captured_effective_specs': True,
                                'source_decisions': 'preserved reviewed files; no new dispositions generated',
                                'publisher_preparation_executed': False, 'native_inversion_executed': False,
                                'production_eligible': False},
         'Prepared-input preview has explicit reduced workflow coverage and grants no production eligibility')
    old_recipe = mth.preview_from_lock(frozen_fixture('as-produced'))
    good(old_recipe['bindings']['engine_ref'] != recipe['bindings']['engine_ref'] and
         next(x['sha256'] for x in old_recipe['files'] if x['relative_path'] == 'src/inv1.spec') !=
         outputs['src/inv1.spec']['sha256'],
         'Original and corrected frozen engine policies remain distinct and independently reproducible')
    for label, mutation in [
        ('different source', lambda c: c.update(source='NCI')),
        ('different release', lambda c: c.update(version='MTH_2026AB')),
        ('unresolved engine', lambda c: c.update(engine_ref='HEAD')),
        ('undeclared replacement', lambda c: c.update(replacement_baseline=None)),
        ('changed replacement', lambda c: c['replacement_baseline'].update(version='MTH_2025AA')),
        ('implicit publisher history', lambda c: c.pop('publisher_history')),
        ('additional publisher history', lambda c: c['publisher_history'].append({'source': 'MTH', 'version': 'MTH_2025AA'})),
        ('additional comparison stage', lambda c: c.update(comparison_baseline={'source': 'MTH', 'version': 'MTH_2025AB'})),
        ('publisher input stage', lambda c: c['inputs'].update(source_data_stage='publisher')),
        ('MetamorphoSys option in prepared case', lambda c: c['source_options'].update(metamorphosys_profile_ref='unknown')),
        ('missing native bundle', lambda c: c['inputs'].update(source_data=[])),
        ('multiple native bundles', lambda c: c['inputs']['source_data'].append(c['inputs']['source_data'][0])),
        ('boolean ID bound', lambda c: c['source_atom_ids'].update(start=True)),
        ('changed captured start', lambda c: c['source_atom_ids'].update(start=769443590)),
        ('changed captured end', lambda c: c['source_atom_ids'].update(end=773943593)),
        ('reversed bounds', lambda c: c['source_atom_ids'].update(end=1)),
        ('new production allocation label', lambda c: c['source_atom_ids'].update(bound_kind='production-reservation')),
        ('extra ID setting', lambda c: c['source_atom_ids'].update(offset=2)),
    ]:
        config = copy.deepcopy(lock['configuration'])
        mutation(config)
        reject(lambda: mth.generate(config, lock['case']['artifacts'], templates), 'Reject ' + label)
    for name in ('old', 'prev'):
        bad = copy.deepcopy(templates)
        bad[name]['target'] = '../MTH_2025AA'
        reject(lambda: mth.generate(lock['configuration'], lock['case']['artifacts'], bad),
               'Reject changed captured ' + name + ' role even when the other role still matches')
    for label, mutation in [
        ('modified frozen bytes', lambda t: t['inv1.spec'].update(data_b64='Y2hhbmdlZA==')),
        ('substituted repository producer', lambda t: t['inv1.spec'].update(repository_path='sources/old/inv1.spec')),
        ('missing source decisions', lambda t: t.pop('ncisources.spec')),
        ('extra unreviewed template', lambda t: t.update(extra=t['inv1.spec'])),
    ]:
        bad = copy.deepcopy(templates)
        mutation(bad)
        reject(lambda: mth.generate(lock['configuration'], lock['case']['artifacts'], bad), 'Reject ' + label)
    for label, mutation in [
        ('different effective configuration', lambda l: l['configuration']['source_atom_ids'].update(end=773943593)),
        ('changed reviewed case bytes', lambda l: l['case']['known_limits'].append('waiver')),
        ('duplicate frozen file', lambda l: l['code_files'].append(copy.deepcopy(l['code_files'][0]))),
        ('changed frozen descriptor', lambda l: l['code_files'][0].update(mode='0o777')),
        ('missing frozen producer', lambda l: l.update(code_files=[x for x in l['code_files'] if x['relative_path'] != 'inv1.spec'])),
    ]:
        bad = copy.deepcopy(lock)
        mutation(bad)
        reject(lambda: mth.preview_from_lock(bad), 'Reject ' + label)
    # Rebinding an artifact hash cannot make an incomplete dependency valid.
    for label, key, mutation in [
        ('missing prepared RRF role', 'source_data', lambda v: v['files'].pop()),
        ('wrong prepared release', 'source_data', lambda v: v.update(umls_release='2025AB')),
        ('duplicate prepared RRF role', 'source_data', lambda v: v['files'].append(copy.deepcopy(v['files'][0]))),
        ('unsafe prepared path', 'source_data', lambda v: v['files'][0].update(relative_path='../MRCONSO.RRF')),
        ('malformed prepared identity', 'source_data', lambda v: v['files'][0]['identity'].update(sha256='bad')),
        ('missing metadata role', 'reference_ncimeta', lambda v: v.pop()),
        ('duplicate metadata role', 'reference_ncimeta', lambda v: v.append(copy.deepcopy(v[0]))),
        ('wrong prior identity version', 'identity_state', lambda v: v['prior_map'].update(path='MTH_2025AA/src/cui_said_map')),
        ('empty prior identity map', 'identity_state', lambda v: v['prior_map'].update(newline_count=0)),
        ('mismatched transition plan', 'source_plan', lambda v: v['replacement_baseline'].update(version='MTH_2025AA')),
        ('missing history closure', 'source_plan', lambda v: v.pop('no_additional_history_required')),
    ]:
        config, artifacts = copy.deepcopy(lock['configuration']), copy.deepcopy(lock['case']['artifacts'])
        reference = config['inputs'][key][0] if key == 'source_data' else config['inputs'][key]
        item = copy.deepcopy(artifacts[reference])
        mutation(item['value'])
        new_ref = 'sha256:' + mth.digest(item['value'])
        artifacts[new_ref] = item
        config['inputs'][key] = [new_ref] if key == 'source_data' else new_ref
        reject(lambda: mth.generate(config, artifacts, templates), 'Reject hash-rebound ' + label)
    bad = copy.deepcopy(lock['case']['artifacts'])
    reference = lock['configuration']['inputs']['source_data'][0]
    bad[reference]['value']['version'] = 'MTH_2025AB'
    reject(lambda: mth.generate(lock['configuration'], bad, templates), 'Reject unbound changed artifact contents')
    raw = base64.b64decode(templates['ncisources.spec']['data_b64'])
    for label, changed in [
        ('undecided disposition', raw.replace(b'|UPDATE|', b'|--NEW?--|', 1)),
        ('duplicate source/version', raw + raw.splitlines(keepends=True)[0]),
        ('duplicate active RSAB', raw + b'MTH|MTH_2025AB|KEEP|\n'),
        ('missing MTH disposition', b'\n'.join(x for x in raw.splitlines() if not x.startswith(b'MTH|')) + b'\n'),
        ('unsupported qualifier', raw.replace(b'exclude termgroups: XM', b'ignore errors', 1)),
    ]:
        reject(lambda: mth.source_decisions(changed), 'Reject ' + label)
    for label, changed in [
        ('missing mapping header', b'MTH|MTH|MTH_2026AA\n'),
        ('duplicate mapping source', base64.b64decode(templates['sab.vsab.map']['data_b64']) + b'MTH|MTH|MTH_2026AA\n'),
        ('wrong MTH mapping release', base64.b64decode(templates['sab.vsab.map']['data_b64']).replace(b'MTH|MTH|MTH_2026AA', b'MTH|MTH|MTH_2025AB')),
    ]:
        reject(lambda: mth.vsab_mappings(changed), 'Reject ' + label)
    # Execute the frozen Perl consumer on a tiny fixture. The only spec edit is
    # relocating SourceDir into the temporary fixture; the emitted policy stays.
    with tempfile.TemporaryDirectory(prefix='mth-generated-spec-') as temporary:
        directory = Path(temporary)
        engine = lock['configuration']['engine_ref']
        perl = subprocess.check_output(['git', '-C', str(ROOT), 'show', engine + ':sources/MTH_2026AA/autoinv.pl'])
        (directory / 'autoinv.pl').write_bytes(perl)
        generated = base64.b64decode(outputs['src/inv1.spec']['data_b64']).decode().replace(
            '/local/content/MEME/MEME5/inv/sources/MTH_2026AA/src', str(directory))
        (directory / 'inv1.spec').write_text(generated)
        (directory / 'range3.spec').write_bytes(base64.b64decode(outputs['range3.spec']['data_b64']))
        for name, text in [('class_src', ''), ('vcodes_updated', ''), ('auis_nonupdatedSAB_moved', ''),
                           ('sabs_updated_umls', 'TEST\n')]:
            (directory / name).write_text(text)
        row = 'C1|ENG|P|L1|PF|S1|Y|A1||||TEST|PT|T1|Alpha|0|N||\n'
        (directory / 'MRCONSO.RRF').write_text(row)
        run = subprocess.run(['/usr/bin/perl', 'autoinv.pl', 'range3.spec', 'inv1.spec'],
                             cwd=directory, capture_output=True, text=True, timeout=30)
        good(run.returncode == 0 and (directory / 'classes_atoms.src').read_text() ==
             '769443594|TEST|TEST/PT|T1|R|Y|A|Alpha|N||||ENG|needs_order_id|N|C1|A1\n' and
             (directory / 'aui_said_map').read_text() == 'A1|C1|N|769443594\n',
             'Actual frozen Perl consumer uses generated spec and increments base before first ordinary atom')
        (directory / 'range3.spec').write_text('SourceAtomIdBase|769443593\nSourceAtomIdLimit|769443594\n')
        (directory / 'MRCONSO.RRF').write_text(row + row.replace('C1|', 'C2|', 1).replace('|A1|', '|A2|'))
        run = subprocess.run(['/usr/bin/perl', 'autoinv.pl', 'range3.spec', 'inv1.spec'],
                             cwd=directory, capture_output=True, text=True, timeout=30)
        good(run.returncode != 0 and 'SourceAtomIdLimit 769443594 exceeded' in run.stderr,
             'Actual frozen Perl consumer enforces inclusive upper bound before emitting an out-of-range atom')
    return passed


if __name__ == '__main__':
    values = check()
    for value in values:
        print('PASS', value)
    print(len(values), 'MTH configuration preview checks passed')
