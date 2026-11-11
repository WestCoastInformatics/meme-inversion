#!/usr/bin/env python3
"""Synthetic backend-contract checks; no exporter/deployment/capture is approved."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import check_nci_release_preflight as original
import check_nci_source_plan as source_fixture
import nci_backend_preflight as backend
import nci_configuration
import nci_release_preflight as v1
import nci_source_plan as plans


def fixture(historical=False, coherent=True):
    c, p, m, properties, old, _ = original.fixture(historical)
    if coherent:
        # Synthetic coherent-policy case only. The captured October metadata
        # actually has source-specific CA2/CNU flag differences; test it below
        # without changing any real policy/case/artifact.
        flags = {}
        for row in m['termgroups'] + [entry['metadata'] for entry in p['new_termgroups']]:
            selected = flags.setdefault(row['tty'], {key: row[key] for key in ('suppressible_flag', 'exclude_flag', 'norm_exclude_flag')})
            row.update(selected)
    generated = plans.generate(c, p, m, properties)
    groups = v1._rows(generated, 'src/termgroups.src', plans.TERMGROUP_FIELDS)
    version_sources = {row['version']: row['source'] for row in old['sources']}
    pairs = [{'source': version_sources[name.rsplit('/', 1)[0]], 'tty': name.rsplit('/', 1)[1]} for name in old['termgroups']]
    families = [{'terminology': row['source'], 'family': row['source_family']} for row in old['sources']]
    versions = [{'terminology': row['source'], 'version': c['replacement_baseline']['version'].removeprefix('NCI_'), 'current': True} for row in old['sources']]
    roots = [{'id': 900000 + i, 'terminology': 'SRC', 'version': 'latest', 'termType': 'RPT',
              'codeId': 'V-' + row['source'], 'branch': '', 'alternateTerminologyIds': {'NCIMTH-SRC': str(row['root_atom_id'])}}
             for i, row in enumerate(old['source_roots'])]
    definitions = {}
    for row in groups:
        definitions.setdefault(row['tty'], {'abbreviation': row['tty'], 'terminology': 'NCIMTH', 'version': 'latest',
            'suppressible': row['suppressible_flag'] == 'Y', 'exclude': row['exclude_flag'] == 'Y', 'normExclude': row['norm_exclude_flag'] == 'Y'})
    project = {'id': 1, 'terminology': 'NCIMTH', 'version': 'latest', 'branch': '', 'precedenceListId': 12}
    def raw_prec(identity):
        return {'id': identity, 'terminology': 'NCIMTH', 'version': 'latest',
                'precedence': {'keyValuePairs': [{'key': x['source'], 'value': x['tty']} for x in pairs]}}
    aliases = [{'source_name': row['version'], 'stripped_source': row['source'], 'version': c['replacement_baseline']['version'].removeprefix('NCI_')} for row in old['sources']]
    document = {'project': project, 'families': families, 'versions': versions, 'version_aliases': aliases, 'roots': roots,
                'precedences': {'default': raw_prec(11), 'project': raw_prec(12)}, 'term_types': list(definitions.values()),
                'fixture_notice': 'Synthetic response-like data only; no real exported response/deployment evidence.'}
    path = 'synthetic-export.json'
    binding = lambda pointer: {'path': path, 'json_pointer': pointer}
    def precedence(role, identity):
        return {'id': identity, 'terminology': 'NCIMTH', 'version': 'latest', 'entries': copy.deepcopy(pairs),
                'binding': binding('/precedences/' + role)}
    state = {'schema_version': 2, 'profile': backend.PROFILE,
        'scope': {key: copy.deepcopy(c[key]) for key in ('source', 'version', 'replacement_baseline')},
        'project': {'id': 1, 'terminology': 'NCIMTH', 'version': 'latest', 'branch': '', 'source_atom_id_key': 'NCIMTH-SRC',
                    'precedence_list_id': 12, 'binding': binding('/project')},
        'deployment': {'build_id': 'synthetic-build', 'artifact_sha256': 'a' * 64,
                       'backend_commit': '708f088babd3e5d16016ab9016af9fee01f2921b', 'evidence_path': path,
                       'graph_handlers': {'project': 'UmlsGraphResolutionHandler', 'SRC': 'DefaultGraphResolutionHandler'}},
        'capture': {'exporter_profile': 'synthetic-only', 'started_at': '2026-11-10T00:00:00Z', 'completed_at': '2026-11-10T00:01:00Z',
                    'consistency_boundary': {'profile': 'synthetic-only', 'state_id': 'synthetic-state', 'evidence_path': path},
                    'completeness_evidence': {role: path for role in ('source_versions', 'families', 'source_roots', 'default_precedence', 'project_precedence', 'term_types')}},
        'raw_exports': [],
        'families': [{'source': row['terminology'], 'source_family': row['family'], 'binding': binding('/families/' + str(i))} for i, row in enumerate(families)],
        'source_versions': [{'source': row['terminology'], 'backend_version': row['version'], 'current': row['current'], 'binding': binding('/versions/' + str(i))} for i, row in enumerate(versions)],
        'version_aliases': [{'versioned_source': row['source_name'], 'source': row['stripped_source'], 'backend_version': row['version'], 'binding': binding('/version_aliases/' + str(i))} for i, row in enumerate(aliases)],
        'replacement_sources': [{'source': row['source'], 'backend_version': c['replacement_baseline']['version'].removeprefix('NCI_')} for row in old['sources']],
        'source_roots': [{'source': old['source_roots'][i]['source'], 'source_atom_id': old['source_roots'][i]['root_atom_id'],
                          'backend_atom_id': row['id'], 'atom_terminology': row['terminology'], 'atom_version': row['version'],
                          'term_type': row['termType'], 'code_id': row['codeId'], 'branch': row['branch'], 'binding': binding('/roots/' + str(i))} for i, row in enumerate(roots)],
        'precedence_lists': {'default': precedence('default', 11), 'project': precedence('project', 12)},
        'term_types': [{'tty': row['abbreviation'], 'terminology': row['terminology'], 'version': row['version'], 'suppressible': row['suppressible'], 'exclude': row['exclude'], 'norm_exclude': row['normExclude'], 'binding': binding('/term_types/' + str(i))} for i, row in enumerate(document['term_types'])]}
    args = [c, p, m, properties, state, None, {}]
    return repack(args, document)


def repack(args, document=None):
    args = copy.deepcopy(args)
    if document is not None:
        raw = json.dumps(document, sort_keys=True).encode()
        args[6] = {'synthetic-export.json': raw}
        args[4]['raw_exports'] = [{'path': 'synthetic-export.json', 'sha256': plans.sha(raw), 'bytes': len(raw), 'encoding': 'json'}]
    args[5] = v1.content_sha256(args[4])
    return args


def raw_document(args):
    return json.loads(args[6]['synthetic-export.json'])


def check():
    checks = []
    def good(value, label):
        assert value, label
        checks.append(label)
    def reject(args, label, rehash=True):
        try:
            backend.analyze_backend(*(repack(args) if rehash else args))
        except (ValueError, KeyError):
            checks.append(label)
        else:
            raise AssertionError(label)
    def codes(report):
        return {row['code'] for row in report['semantic_findings']}
    args = fixture();before = copy.deepcopy(args)
    result = backend.analyze_backend(*args)
    good(result['semantic_status'] == 'PASS', 'Complete raw-bound synthetic state passes bounded semantic review')
    good(result['status'] == 'BLOCKED_PENDING_CAPTURE_VERIFICATION' and len(result['capture_findings']) == 6,
         'Complete synthetic data retains all six deployment/exporter/handler/project/completeness/consistency blockers')
    good(not result['production_eligible'] and not result['execution_authorized'], 'No preview can authorize execution or production')
    good(args == before, 'Every configuration/plan/model/state/raw input remains unchanged')
    good(result == backend.analyze_backend(*args), 'Same frozen bytes produce the same deterministic result')
    good(result['replacement_baseline']['version'] == 'NCI_2026_08E', 'October uses explicit August replacement, without an inferred September')
    changed = fixture();document = raw_document(changed)
    for index, row in enumerate(changed[4]['source_versions']):
        if row['source'] == 'NCI':
            row['backend_version'] = 'backend-august-state'
            document['versions'][index]['version'] = row['backend_version']
    for index, row in enumerate(changed[4]['version_aliases']):
        if row['source'] == 'NCI':
            row['backend_version'] = 'backend-august-state'
            document['version_aliases'][index]['version'] = row['backend_version']
    for row in changed[4]['replacement_sources']:
        if row['source'] == 'NCI':
            row['backend_version'] = 'backend-august-state'
    explicit = backend.analyze_backend(*repack(changed, document))
    good(explicit['semantic_status'] == 'PASS' and explicit['replacement_baseline']['version'] == 'NCI_2026_08E',
         'Explicit primary alias can bind a backend version distinct from the NCIt release suffix, preserving common chronology')
    good(result['bindings']['verified_raw_rows'] and result['bindings']['raw_exports'], 'Results bind raw bytes and each verified JSON row location')
    good(result['bindings']['raw_exports']['synthetic-export.json']['sha256'] == plans.sha(args[6]['synthetic-export.json']),
         'Raw-export bindings retain actual byte hashes independently from source-version alias maps')
    good(all('/' not in pair['source'] and '_' not in pair['tty'] for role in result['precedence_previews'].values() for pair in role),
         'Precedence previews retain root sources and TTYs rather than fabricated versioned rank identities')
    good(not any('UNRESOLVED' in code for code in codes(result)), 'Existing high/low labels normalizing to the same installed pair are valid')
    good(any(row['source'] == 'CTCAE_3' for row in result['precedence_previews']['default']),
         'An embedded underscore in a source abbreviation is preserved by exact metadata mapping')
    good(args[4]['source_roots'][0]['source_atom_id'] != args[4]['source_roots'][0]['backend_atom_id'], 'Source SAID remains explicitly distinct from backend atom identity')
    captured = backend.analyze_backend(*fixture(coherent=False))
    good({'CA2', 'CNU'} <= {row['identifier'] for row in captured['semantic_findings'] if row['code'] == 'CONFLICTING_GLOBAL_TTY_FLAGS'},
         'Captured source-specific CA2/CNU flag differences remain review findings, not silently corrected policy')
    historical = fixture(True);doc = raw_document(historical)
    for role in ('default', 'project'):
        historical[4]['precedence_lists'][role]['entries'].append({'source': 'CELLOSAURUS', 'tty': 'SY'})
        doc['precedences'][role]['precedence']['keyValuePairs'].append({'key': 'CELLOSAURUS', 'value': 'SY'})
    report = backend.analyze_backend(*repack(historical, doc))
    good('DEFAULT_PRECEDENCE_LOW_MISSING' not in codes(report) and 'PROJECT_PRECEDENCE_UNRESOLVED' not in codes(report),
         'Captured CELLOSAURUS/SY rank can satisfy new-source dependencies without a fictitious current VSAB/SY row')
    good(sum(x['code'] == 'HISTORICAL_EXCEPTION_REQUIRES_REVIEW' for x in report['semantic_findings']) == 2,
         'Real rank membership would not automatically approve either retained historical exception')
    good(any(row['code'] == 'EXISTING_RANK_PAIR_RETAINED' and row['identifier'] == 'default:CELLOSAURUS/SY' for row in report['observations']),
         'An extra existing rank anchor omitted by this metadata batch is retained rather than falsely treated as deletion')
    historical[4]['precedence_lists']['project']['entries'].pop();doc['precedences']['project']['precedence']['keyValuePairs'].pop()
    report = backend.analyze_backend(*repack(historical, doc))
    good('PROJECT_PRECEDENCE_UNRESOLVED' in codes(report) and 'DEFAULT_PRECEDENCE_LOW_MISSING' not in codes(report),
         'Default and project dependencies are validated separately; their entries are never unioned')
    changed = fixture();document = raw_document(changed)
    for role in ('default', 'project'):
        changed[4]['precedence_lists'][role]['entries'].append({'source': 'BLOODPAC', 'tty': 'PT'})
        document['precedences'][role]['precedence']['keyValuePairs'].append({'key': 'BLOODPAC', 'value': 'PT'})
    good('NEW_RANK_PAIR_ALREADY_PRESENT' in codes(backend.analyze_backend(*repack(changed, document))),
         'New termgroup decisions cannot recreate already present root-source/TTY rank pairs')
    changed = fixture();document = raw_document(changed)
    index = changed[4]['precedence_lists']['project']['entries'].index({'source': 'NCI', 'tty': 'PT'})
    changed[4]['precedence_lists']['project']['entries'].pop(index)
    document['precedences']['project']['precedence']['keyValuePairs'].pop(index)
    good('UNDECLARED_RANK_PAIR_ADDITION' in codes(backend.analyze_backend(*repack(changed, document))),
         'Missing established project pairs require an explicit reconciliation decision')
    planned, findings = backend._insert_pairs([('EXT', 'PT')], [(('NEW', 'PT'), ('NEW', 'SY')), (('NEW', 'SY'), ('EXT', 'PT'))], 'TEST')
    good(planned == [('NEW', 'PT'), ('NEW', 'SY'), ('EXT', 'PT')] and not findings, 'Pending new rank pairs resolve across repeated dependency passes')
    _, findings = backend._insert_pairs([], [(('NEW', 'PT'), ('NEW', 'SY')), (('NEW', 'SY'), ('NEW', 'PT'))], 'TEST')
    good(len(findings) == 2, 'A genuine cycle among absent pending rank pairs cannot make insertion progress')
    changed = fixture();document = raw_document(changed)
    changed[4]['term_types'][0]['suppressible'] = not changed[4]['term_types'][0]['suppressible']
    document['term_types'][0]['suppressible'] = changed[4]['term_types'][0]['suppressible']
    good('EXISTING_TTY_FLAG_CHANGE_NOT_APPLIED' in codes(backend.analyze_backend(*repack(changed, document))),
         'Existing global TTY flags cannot be silently changed by generated source metadata')
    changed = fixture();changed[4]['raw_exports'][0]['encoding'] = 'opaque'
    report = backend.analyze_backend(*repack(changed))
    good(report['semantic_status'] == 'NOT_EVALUATED' and any(x['code'] == 'RAW_BINDING_ENCODING_UNSUPPORTED' for x in report['capture_findings']),
         'Pinned opaque bytes cannot establish unverified normalized row meanings')
    for label, change in [
        ('Changed state hash fails closed', lambda a: a[4]['project'].update(source_atom_id_key='WRONG-SRC')),
        ('A v1 artifact is not implicitly upgraded', lambda a: a[4].update(profile='ncimeta-installed-state-v1')),
        ('Client review booleans cannot confer deployment approval', lambda a: a[4]['deployment'].update(reviewed=True)),
        ('Wrong project source-SAID key is rejected', lambda a: a[4]['project'].update(source_atom_id_key='NCI-SRC')),
        ('Backend atom ID cannot substitute for source SAID', lambda a: a[4]['source_roots'][0].update(source_atom_id=a[4]['source_roots'][0]['backend_atom_id'])),
        ('Source root must be SRC/RPT', lambda a: a[4]['source_roots'][0].update(term_type='VPT')),
        ('Source root code must match exact V-RSAB selector', lambda a: a[4]['source_roots'][0].update(code_id='V-WRONG')),
        ('Duplicate or ambiguous source root is rejected', lambda a: a[4]['source_roots'].append(copy.deepcopy(a[4]['source_roots'][0]))),
        ('Floating point IDs cannot impersonate exact backend IDs', lambda a: a[4]['source_roots'][0].update(backend_atom_id=float(a[4]['source_roots'][0]['backend_atom_id']))),
        ('Boolean IDs cannot impersonate source SAIDs', lambda a: a[4]['source_roots'][0].update(source_atom_id=True)),
        ('Boolean IDs cannot impersonate backend atom IDs', lambda a: a[4]['source_roots'][0].update(backend_atom_id=True)),
        ('Wrong current flag cannot differ from raw source metadata', lambda a: a[4]['source_versions'][0].update(current=False)),
        ('Family classification must match its raw Java property', lambda a: a[4]['families'][0].update(source_family='OTHER')),
        ('Version aliases must match explicit captured metadata fields', lambda a: a[4]['version_aliases'][0].update(versioned_source='NCI_GUESSED')),
        ('Reordered precedence cannot differ from raw captured order', lambda a: a[4]['precedence_lists']['default']['entries'].reverse()),
        ('Project precedence ID must match raw project assignment', lambda a: a[4]['project'].update(precedence_list_id=111)),
        ('Generic TTY definitions cannot use another project scope', lambda a: a[4]['term_types'][0].update(terminology='OTHER')),
        ('Boolean completeness claims cannot replace evidence references', lambda a: a[4]['capture']['completeness_evidence'].update(source_roots=True)),
        ('Nonexistent raw JSON rows are rejected', lambda a: a[4]['source_roots'][0]['binding'].update(json_pointer='/roots/999999')),
        ('Parent path raw exports are rejected', lambda a: a[4]['raw_exports'][0].update(path='../outside.json')),
        ('Undeclared capture evidence is rejected', lambda a: a[4]['deployment'].update(evidence_path='undeclared.json')),
        ('Changed common baseline scope is rejected', lambda a: a[4]['scope']['replacement_baseline'].update(version='NCI_2026_09D')),
        ('Impossible capture time order is rejected', lambda a: a[4]['capture'].update(completed_at='2026-11-09T00:00:00Z')),
    ]:
        changed = fixture();change(changed)
        reject(changed, label, rehash=label != 'Changed state hash fails closed')
    changed = fixture();changed[6]['synthetic-export.json'] += b' '
    reject(changed, 'Changed raw-export bytes fail their selected hash/length')
    changed = fixture();document = raw_document(changed)
    index = next(i for i, row in enumerate(changed[4]['version_aliases']) if row['source'] == 'NCI')
    changed[4]['version_aliases'][index]['versioned_source'] = changed[0]['version']
    document['version_aliases'][index]['source_name'] = changed[0]['version']
    reject(repack(changed, document), 'Captured/generated aliases for the same VSAB cannot disagree even when raw bytes match')
    changed = fixture();changed[6]['undeclared.json'] = b'{}'
    reject(changed, 'Undeclared raw files cannot enter capture evidence')
    changed = fixture();raw = b'{"id":1,"id":1}'
    changed[6]['synthetic-export.json'] = raw;changed[4]['raw_exports'][0].update(sha256=plans.sha(raw), bytes=len(raw))
    reject(changed, 'Duplicate keys in raw JSON fail even when the supplied byte hash matches')
    old = original.fixture()
    good(v1.analyze(*old)['profile'] == 'nci-release-preflight-v1', 'The existing v1 synthetic/legacy analyzer remains available unchanged')
    c, artifacts, template, model_file, plan = source_fixture.fixture()
    generated = nci_configuration.generate(c, artifacts, template, model_file)
    historical_case = json.loads((Path(__file__).resolve().parents[1] / 'docs/inversion-review/case-catalog/nci-generated-configuration.json').read_text())
    lock = {'artifact_type': 'ncimeta-dev-replay-lock', 'schema_version': 1,
            'configuration': c, 'request': {'source': 'NCI', 'version': c['version'], 'case_variant': 'source-plan'},
            'case': {'configuration': c, 'artifacts': artifacts, 'legacy_case': historical_case['legacy_case'],
                     'configuration_generation': {'profile': plans.PROFILE, 'repository_path': template['repository_path'],
                     'sha256': template['sha256'], 'metadata_repository_path': model_file['repository_path'], 'metadata_sha256': model_file['sha256']}},
            'configuration_generation': generated}
    lock['lock_sha256'] = v1.content_sha256(lock)
    lock_before = copy.deepcopy(lock)
    good(backend.inputs_from_lock(lock)[0] == c and lock == lock_before, 'V2 consumes an existing frozen source-plan lock without mutating its historical recipe')
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch);(root / 'raw').mkdir()
        original_args = fixture(True, coherent=False)
        (root / 'lock.json').write_text(json.dumps(lock))
        (root / 'state.json').write_text(json.dumps(original_args[4]))
        for name, raw in original_args[6].items():
            (root / 'raw' / name).write_bytes(raw)
        output = root / 'report.json'
        command = [sys.executable, '-B', str(Path(__file__).with_name('nci_backend_preflight.py')), '--lock', str(root / 'lock.json'),
                   '--installed-state', str(root / 'state.json'), '--installed-state-sha256', original_args[5],
                   '--raw-export-directory', str(root / 'raw'), '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        good(result.returncode == 3 and json.loads(output.read_text())['status'] == 'BLOCKED_PENDING_CAPTURE_VERIFICATION',
             'Standalone CLI retains a blocked report and exits3 consistently with the common preview')
        good(not output.stat().st_mode & 0o222, 'Standalone report is read-only')
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        good(result.returncode == 2 and output.exists() and 'Traceback' not in result.stderr, 'Standalone output collision preserves the previous report and gives clean invalid-input status2')
        invalid_output = root / 'invalid-report.json'
        invalid_command = list(command)
        invalid_command[invalid_command.index(original_args[5])] = '0' * 64
        invalid_command[invalid_command.index(str(output))] = str(invalid_output)
        result = subprocess.run(invalid_command, capture_output=True, text=True, timeout=30)
        good(result.returncode == 2 and not invalid_output.exists() and not result.stdout
             and result.stderr and 'Traceback' not in result.stderr, 'Tampered input exits2 with clean stderr and produces no report')
        internal_output = root / 'internal-report.json'
        internal_command = list(command[2:]);internal_command[internal_command.index(str(output))] = str(internal_output)
        stderr = io.StringIO()
        with patch.object(sys, 'argv', internal_command), patch.object(backend, 'analyze_backend', side_effect=RuntimeError('fixture internal failure')), contextlib.redirect_stderr(stderr):
            status = backend.main()
        good(status == 1 and not internal_output.exists() and 'Unexpected preflight error' in stderr.getvalue(),
             'Unexpected internal errors use status1 and produce no review report')
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'details': checks}, indent=2))
    return checks


if __name__ == '__main__':
    check()
