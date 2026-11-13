#!/usr/bin/env python3
"""Tiny actual SNOMED native runs with no current official-output oracle.

Both fixtures use pinned canonical Git code/shared INV, fresh native RF2 inputs,
saved metadata and declared dev ID ranges. No generated output is seeded or used
to construct the candidate. Temporary fixture data is removed on exit.
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

import check_execute_release_snomed as fixtures
import execute_release_snomed as execute
import release_execution
import release_snomed

ROOT = Path(__file__).resolve().parents[1]
ENGINE = '2e77f7b9fce17e71ead1ec719e36428684e34922'
RUNTIME = '3b125edc1d29f7c7a91673da2a8d752bb0adff44'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_records(records, destination):
    for record in records:
        if record['kind'] != 'file':raise AssertionError('Tiny native code requires regular pinned Git blobs')
        raw = base64.b64decode(record['data_b64'], validate=True)
        assert hashlib.sha256(raw).hexdigest() == record['sha256']
        path = destination / record['relative_path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw);path.chmod(int(record['mode'],8))


def fixture(directory,index,code,runtime):
    manifest = fixtures.fixture(index)
    config, artifacts = manifest['configuration'],manifest['artifacts']
    manifest['purpose'] = 'shadow';config.pop('replay',None)
    for key in [name for name,artifact in artifacts.items() if artifact['artifact_type']=='reference-inversion']:del artifacts[key]
    config['engine_ref'] = ENGINE;artifacts[config['policy_ref']]['data']['engine_ref'] = ENGINE
    origin = directory/'input-cache';origin.mkdir()
    native_ref = config['inputs']['source_data'][0]
    package = artifacts[native_ref]['data']['package_name']
    for reference,artifact in artifacts.items():
        for entry in artifact['files']:
            original = entry['uri'].removeprefix('repo:');raw = (ROOT/original).read_bytes()
            if reference == native_ref:
                parts = Path(original).parts;package_parts = Path(package).parts
                positions = [n for n in range(len(parts)) if parts[n:n+len(package_parts)] == package_parts]
                assert len(positions)==1
                path = origin.joinpath(*parts[positions[0]:])
            else:path = origin/reference/Path(original).name
            if entry['role']=='rf2-descriptions':
                # The declaration-only examples deliberately omit a root
                # description/preferred synonym. The native hierarchy uses PT.
                date = artifacts[native_ref]['data']['effective_time_bounds']['minimum']
                raw += ('100013\t'+date+'\t1\t900000000000207008\t138875005\ten\t900000000000003001\tSNOMED CT fixture root (SNOMED RT+CTV3)\t900000000000448009\n').encode()
                raw += ('100014\t'+date+'\t1\t900000000000207008\t138875005\ten\t900000000000013009\tSNOMED CT fixture root\t900000000000448009\n').encode()
            elif entry['role']=='rf2-language':
                date = artifacts[native_ref]['data']['effective_time_bounds']['minimum']
                raw += ('fixture-root-language\t'+date+'\t1\t900000000000207008\t900000000000509007\t100014\t900000000000548007\n').encode()
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o444)
            entry.update(uri=path.as_uri(),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    recipe = execute.build_plan(config,artifacts,code)
    inv = directory/'MEME5/inv';target = inv/'sources'/config['version'];target.mkdir(parents=True)
    _copy_records(code,target);_copy_records(runtime,inv/'INV')
    for name in ('bin','src','tmp','etc/qa','orig'):(target/name).mkdir(parents=True,exist_ok=True)
    for entry in recipe['input_files']:
        descriptor = next(value for value in artifacts[entry['artifact']]['files'] if value['role']==entry['role'])
        destination = target/entry['destination'];destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(Path(descriptor['uri'].removeprefix('file://')).read_bytes());destination.chmod(0o444)
    for entry in recipe['generated_files']:
        path = target/entry['relative_path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(base64.b64decode(entry['data_b64']));path.chmod(int(entry['mode'],8))
    run = directory/'native-logs';run.mkdir()
    env = dict(os.environ,INV_HOME=str(inv/'INV'),PATH_TO_PERL='/usr/bin/perl',LC_ALL='C',LC_COLLATE='C',LANG='C')
    return manifest,recipe,target,run,env


def run_tiny(recipe,target,run,env):
    result = []
    for stage in recipe['stages']:
        output = stage.get('stdout')
        if output:
            with (target/output).open('wb') as handle:
                child = subprocess.run(stage['argv'],cwd=target/stage['cwd'],env=env,stdout=handle,stderr=subprocess.PIPE,timeout=30)
        else:
            child = subprocess.run(stage['argv'],cwd=target/stage['cwd'],env=env,capture_output=True,timeout=30)
            (run/(stage['name']+'.stdout')).write_bytes(child.stdout)
        (run/(stage['name']+'.stderr')).write_bytes(child.stderr)
        assert child.returncode == 0,(stage['name'],child.stderr.decode(errors='replace')[-1500:])
        result.append({'stage':stage['name'],'exit_status':child.returncode})
    return result


def check():
    checks = []
    def good(value,label):assert value,label;checks.append(label)
    def reject(action,label):
        try:action()
        except (ValueError,KeyError):checks.append(label);return
        raise AssertionError(label)
    code = release_execution._tree(ENGINE,execute.PACKAGE)
    runtime = release_execution._tree(RUNTIME,'INV')
    results = []
    for index in range(2):
        with tempfile.TemporaryDirectory(prefix='shadow-snomed-native-') as temporary:
            manifest,recipe,target,run,env = fixture(Path(temporary).resolve(),index,code,runtime)
            config,artifacts = manifest['configuration'],manifest['artifacts'];label = config['version']
            good('replay' not in config and all(a['artifact_type']!='reference-inversion' for a in artifacts.values()),'shadow plan has no replay/oracle artifact: '+label)
            good(not any((target/name).exists() for name in recipe['output_files']),'no output SRC files seed native conversion: '+label)
            good(recipe==execute.build_plan(config,artifacts,code),'same frozen canonical code deterministically plans unseeded shadow inputs: '+label)
            declaration = release_snomed.analyze(config,artifacts)
            good(not any(x['severity'] in ('error','blocker') for x in declaration['issues']),'source declaration validation has no official-output dependency: '+label)
            validated = execute.validate_inputs(recipe,target)
            good(validated['passed'],'full native Snapshot/metadata validation passes before conversion: '+label+' '+str(validated['issues']))
            inputs = {item['destination']:digest(target/item['destination']) for item in recipe['input_files']}
            stages = run_tiny(recipe,target,run,env)
            good(len(stages)==5 and all(s['exit_status']==0 for s in stages),'all5actual Perl/native cleanup stages finish without an official output: '+label)
            current = execute.validate_outputs(recipe,target)
            assert current['passed'],(label,current)
            good(current['passed'],'independent release-aware validation passes genuine native output: '+label)
            good(all(digest(target/name)==sha for name,sha in inputs.items()),'all supplied native/metadata inputs remain unchanged after conversion: '+label)
            atoms = [raw.split('|') for raw in (target/'src/classes_atoms.src').read_text().splitlines()]
            good({row[9] for row in atoms if row[1]==label} >= {'100010','100011','100013','100014'},'native description identities including the fixture root are independently retained: '+label)
            good(any(row[7]=='SNOMED CT fixture root (SNOMED RT+CTV3)' for row in atoms),'actual native term content survives without an output constructor: '+label)
            good({(row[9],row[2].split('/')[-1],row[10]) for row in atoms}=={
                ('100010','FN','100001'),('100011','PT','100001'),('100013','FN','138875005'),('100014','PT','138875005')},
                'independent native golden preserves FN/preferred terms and both concept identities: '+label)
            context = (target/'src/contexts.src').read_text().splitlines()[0].split('|')
            good((context[1],context[2],context[11],context[14])==('PAR','isa','100001','138875005'),
                 'independent native golden preserves ISA child/parent direction and original concept identities: '+label)
            good(all(config['source_atom_ids']['start']<=int(row[0])<=config['source_atom_ids']['end'] for row in atoms),'every emitted atom stays in this fixture dev allocation: '+label)
            if index==0:
                for kind,mutate in [
                    ('Full view',lambda c,a:c['source_options'].update(rf2_view='Full')),
                    ('missing allocation',lambda c,a:c.update(source_atom_ids=None)),
                    ('reversed allocation',lambda c,a:c['source_atom_ids'].update(end=1)),
                    ('live MRDOC',lambda c,a:a[c['inputs']['source_plan']]['data'].update(mrdoc_required=True)),
                    ('missing native role',lambda c,a:a[c['inputs']['source_data'][0]]['files'].pop()),
                    ('missing explicit target versions',lambda c,a:a[c['policy_ref']]['data'].pop('mapping_targets')),
                ]:
                    bad = copy.deepcopy(manifest);mutate(bad['configuration'],bad['artifacts'])
                    reject(lambda:execute.build_plan(bad['configuration'],bad['artifacts'],code),'shadow still rejects '+kind+' before native execution')
                bad_path = target/recipe['validation']['native_paths']['rf2-relationships'];original = bad_path.read_bytes();bad_path.chmod(0o644)
                changed = original.replace(b'116680003',b'999999999')
                bad_path.write_bytes(changed);bad_path.chmod(0o444)
                bad_recipe = copy.deepcopy(recipe);entry = bad_recipe['validation']['input_fingerprints'][recipe['validation']['native_paths']['rf2-relationships']]
                entry.update(sha256=hashlib.sha256(changed).hexdigest(),bytes=len(changed))
                good(not execute.validate_inputs(bad_recipe,target)['passed'],'new unreviewed native relationship type remains blocked without an oracle')
                bad_path.chmod(0o644);bad_path.write_bytes(original);bad_path.chmod(0o444)
                output = target/'src/attributes.src';before = output.read_bytes();rows = before.splitlines();first = rows[0].split(b'|');first[10] = b'ATTRIBUTE_ID';rows[0] = b'|'.join(first)
                output.write_bytes(b'\n'.join(rows)+b'\n')
                good(not execute.validate_outputs(recipe,target)['passed'],'shadow output validation remains strict after native generation')
                output.write_bytes(before)
            results.append({'version':label,'replacement_baseline':config['replacement_baseline'],'stages':stages,'validation_passed':current['passed'],
                            'output_files':current['facts']['files'],'official_output_used':False,'compared':False})
    good(results[0]['version']!=results[1]['version'] and results[0]['replacement_baseline']!=results[1]['replacement_baseline'],'two different publications/packages/predecessors share unchanged source code')
    print(json.dumps({'passed':len(checks),'checks':checks,'native_fixtures':results},indent=2))


if __name__=='__main__':check()
