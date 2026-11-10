#!/usr/bin/env python3
"""NCIt installed-state/preparation checks; synthetic inventories are not DB evidence."""
import base64
import copy
import json

import check_nci_source_plan as prior
import nci_configuration as configuration
import nci_release_preflight as preflight
import nci_source_plan as plans


def fixture(historical=False):
    """Return the analyzer's six arguments, using an explicitly synthetic inventory."""
    config, artifacts, template, model_file, plan = prior.fixture()
    model = plans.load(base64.b64decode(model_file['data_b64']))
    root = artifacts[config['inputs']['identity_state']]['value']
    properties = configuration.properties(configuration.render_template(config, template, root))
    if not historical:
        plan['historical_exceptions'] = []
        plan['new_termgroups'][1]['metadata']['low_termgroup'] = 'CELLOSAURUS_{{release}}/PT'
    generated = plans.generate(config, plan, model, properties)
    source_rows = preflight._rows(generated, 'src/sources.src', plans.SOURCE_FIELDS)
    group_rows = preflight._rows(generated, 'src/termgroups.src', plans.TERMGROUP_FIELDS)
    release = config['version'].removeprefix('NCI_')
    replacement = config['replacement_baseline']['version'].removeprefix('NCI_')
    new_sources = set(generated['new_subsources'])
    variables = {'release': release, 'replacement_release': replacement}
    new_groups = {plans.render(row['metadata']['termgroup_name'], variables)
                  for row in plan['new_termgroups']}
    sources = [{'source': row['stripped_source'],
                'version': row['stripped_source'] + '_' + replacement, 'source_family': 'NCI'}
               for row in source_rows if row['stripped_source'] not in new_sources]
    state = {'schema_version': 1, 'profile': preflight.PROFILE,
             'scope': {key: copy.deepcopy(config[key]) for key in ('source', 'replacement_baseline')},
             'capture': {'snapshot_id': 'synthetic-nci-state', 'captured_at': '2000-01-01T00:00:00Z',
                         'evidence_sha256': 'f' * 64},
             'complete_for': {'sources': True, 'source_roots': True, 'termgroups': True},
             'sources': sources, 'replacement_sources': [row['version'] for row in sources],
             'source_roots': [{'source': row['source'], 'root_atom_id': 1000 + i}
                              for i, row in enumerate(sources)],
             'termgroups': [row['termgroup_name'].replace('_' + release + '/', '_' + replacement + '/')
                            for row in group_rows if row['termgroup_name'] not in new_groups]}
    return config, plan, model, properties, state, preflight.content_sha256(state)


def check():
    checks = []

    def good(test, label):
        assert test, label
        checks.append(label)

    def run(arguments):
        arguments = copy.deepcopy(arguments)
        arguments[-1] = preflight.content_sha256(arguments[-2])
        return preflight.analyze(*arguments)

    def codes(arguments):
        return {item['code'] for item in run(arguments)['findings']}

    def rejects(arguments, label, rehash=True):
        arguments = copy.deepcopy(arguments)
        if rehash:
            arguments[-1] = preflight.content_sha256(arguments[-2])
        try:
            preflight.analyze(*arguments)
        except ValueError:
            checks.append(label)
        else:
            raise AssertionError(label)

    args = fixture()
    frozen = copy.deepcopy(args)
    result = preflight.analyze(*args)
    good(result['status'] == 'PASS_RELEASE_PREFLIGHT' and not result['findings'], 'Complete coherent synthetic state passes bounded preflight')
    good(args == frozen, 'All six analyzer inputs remain unchanged')
    good(result == preflight.analyze(*json.loads(json.dumps(args))), 'Saved JSON arguments reproduce the same result')
    good(result['replacement_baseline']['version'] == 'NCI_2026_08E', 'October explicitly replaces August without calendar inference')
    good(not result['production_eligible'] and not result['execution_authorized'], 'A successful preview cannot authorize production or execution')
    good(result['bindings']['installed_state_sha256'] == args[-1], 'Result binds exact selected state identity')
    good(result['bindings']['capture']['captured_at'].startswith('2000'), 'An old frozen capture is not rejected merely because of wall-clock age')
    good(result['decisions']['new_subsources'] == ['BLOODPAC'], 'Representation catalog membership does not suppress a genuinely new source-root decision')
    historical = list(fixture(historical=True))
    finding_codes = codes(historical)
    good({'HISTORICAL_EXCEPTION_REQUIRES_REVIEW', 'TERMGROUP_RANK_TARGET_MISSING'} <= finding_codes,
         'Historical October exceptions and absent external rank remain blocking findings')
    historical_result = run(historical)
    good(sum(row['code'] == 'HISTORICAL_EXCEPTION_REQUIRES_REVIEW' for row in historical_result['findings']) == 2,
         'Both October findings remain separately identifiable')
    # A captured extra termgroup can establish existence, but does not approve policy.
    historical[-2]['sources'].append({'source': 'CELLOSAURUS', 'version': 'CELLOSAURUS_2026_10D', 'source_family': 'NCI'})
    historical[-2]['termgroups'].append('CELLOSAURUS_2026_10D/SY')
    good('TERMGROUP_RANK_TARGET_MISSING' not in codes(historical)
         and 'HISTORICAL_EXCEPTION_REQUIRES_REVIEW' in codes(historical),
         'External target existence is distinguishable from semantic approval; a retained exception still blocks')
    changed = list(fixture());changed[-2]['sources'].append({'source': 'BLOODPAC', 'version': 'BLOODPAC_2026_08E', 'source_family': 'NCI'})
    changed[-2]['source_roots'].append({'source': 'BLOODPAC', 'root_atom_id': 4242})
    changed[-2]['termgroups'].append('BLOODPAC_2026_08E/PT')
    good({'NEW_SOURCE_ALREADY_INSTALLED', 'NEW_TERMGROUP_ALREADY_INSTALLED'} <= codes(changed),
         'New source/root and termgroup decisions cannot duplicate installed identities')
    changed = list(fixture());changed[-2]['source_roots'] = [x for x in changed[-2]['source_roots'] if x['source'] != 'NCI']
    good('SOURCE_ROOT_MISSING' in codes(changed), 'Known source metadata does not establish a missing installed source root')
    changed = list(fixture());changed[-2]['sources'] = [x for x in changed[-2]['sources'] if x['source'] != 'FDA']
    changed[-2]['replacement_sources'] = [x for x in changed[-2]['replacement_sources'] if x != 'FDA_2026_08E']
    changed[-2]['source_roots'] = [x for x in changed[-2]['source_roots'] if x['source'] != 'FDA']
    changed[-2]['termgroups'] = [x for x in changed[-2]['termgroups'] if not x.startswith('FDA_')]
    good({'UNDECLARED_NEW_SOURCE', 'SOURCE_RANK_TARGET_MISSING'} <= codes(changed), 'Missing installed source and prior ranking identity require explicit decisions')
    changed = list(fixture());changed[-2]['termgroups'].remove('NCI_2026_08E/PT')
    good({'UNDECLARED_NEW_TERMGROUP', 'TERMGROUP_RANK_TARGET_MISSING'} <= codes(changed), 'Missing established termgroup cannot be inferred from source metadata')
    changed = list(fixture());changed[-2]['sources'].append({'source': 'RETIRED', 'version': 'RETIRED_2026_08E', 'source_family': 'NCI'})
    changed[-2]['replacement_sources'].append('RETIRED_2026_08E')
    good('SOURCE_REMOVAL_UNREVIEWED' in codes(changed), 'An omitted replacement source requires reviewed removal policy')
    changed[-2]['replacement_sources'].remove('RETIRED_2026_08E')
    good('SOURCE_REMOVAL_UNREVIEWED' not in codes(changed), 'Retained historical metadata is not mistaken for an active source removal')
    changed = list(fixture());changed[-2]['termgroups'].append('NCI_2026_08E/RETIRED')
    good('TERMGROUP_REMOVAL_UNREVIEWED' in codes(changed), 'An omitted replacement termgroup requires reviewed removal policy')
    changed = list(fixture());changed[-2]['sources'].append({'source': 'NCI', 'version': 'NCI_2026_07D', 'source_family': 'NCI'})
    changed[-2]['termgroups'].append('NCI_2026_07D/RETIRED')
    good(run(changed)['status'] == 'PASS_RELEASE_PREFLIGHT', 'Extra historical versioned metadata does not create a false active-termgroup removal')
    changed = list(fixture());changed[-2]['sources'].append({'source': 'MSH', 'version': 'MSH2026', 'source_family': 'MSH'})
    changed[-2]['termgroups'].append('MSH2026/PN')
    changed[-2]['source_roots'].append({'source': 'MSH', 'root_atom_id': 999999})
    good(run(changed)['status'] == 'PASS_RELEASE_PREFLIGHT', 'External ranking-anchor versions retain explicit metadata identity without an inferred source prefix')
    changed = list(fixture());changed[-2]['sources'].append({'source': 'NCI', 'version': 'NCI_2026_10D', 'source_family': 'NCI'})
    good('CURRENT_VERSION_ALREADY_INSTALLED' in codes(changed), 'A proposed version already in installed metadata requires review')
    for label, change in [
        ('Changed state hash is rejected', lambda a: a[-2]['capture'].update(snapshot_id='changed')),
        ('Wrong snapshot source scope is rejected', lambda a: a[-2]['scope'].update(source='MTH')),
        ('Wrong replacement snapshot scope is rejected', lambda a: a[-2]['scope']['replacement_baseline'].update(version='NCI_2026_09D')),
        ('Missing selected installed baseline is rejected', lambda a: a[-2]['replacement_sources'].remove('NCI_2026_08E')),
        ('Unknown replacement identity is rejected', lambda a: a[-2]['replacement_sources'].append('NCI_1900_01D')),
        ('Duplicate replacement identity is rejected', lambda a: a[-2]['replacement_sources'].append('NCI_2026_08E')),
        ('Wrongly typed replacement identity is rejected', lambda a: a[-2]['replacement_sources'].append({})),
        ('Partial inventories are rejected', lambda a: a[-2]['complete_for'].update(termgroups=False)),
        ('Numeric truthy coverage is rejected', lambda a: a[-2]['complete_for'].update(sources=1)),
        ('Wrong inventory container type is rejected', lambda a: a[-2].update(termgroups={})),
        ('Duplicate source metadata is rejected', lambda a: a[-2]['sources'].append(copy.deepcopy(a[-2]['sources'][0]))),
        ('Missing source family is rejected', lambda a: a[-2]['sources'][0].pop('source_family')),
        ('Duplicate source root is rejected', lambda a: a[-2]['source_roots'].append(copy.deepcopy(a[-2]['source_roots'][0]))),
        ('Shared atom ID across distinct source roots is rejected', lambda a: a[-2]['source_roots'][1].update(root_atom_id=a[-2]['source_roots'][0]['root_atom_id'])),
        ('Unknown source-root field is rejected', lambda a: a[-2]['source_roots'][0].update(hierarchy_root=True)),
        ('Boolean source-root ID is rejected', lambda a: a[-2]['source_roots'][0].update(root_atom_id=True)),
        ('Unknown source root is rejected', lambda a: a[-2]['source_roots'][0].update(source='UNKNOWN')),
        ('Duplicate termgroup is rejected', lambda a: a[-2]['termgroups'].append(a[-2]['termgroups'][0])),
        ('Unknown termgroup version is rejected', lambda a: a[-2]['termgroups'].append('NCI_1900_01D/PT')),
        ('Injected term type is rejected', lambda a: a[-2]['termgroups'].append('NCI_2026_08E/PT|BAD')),
        ('Malformed capture time is rejected', lambda a: a[-2]['capture'].update(captured_at='yesterday')),
        ('Naive capture timestamp is rejected', lambda a: a[-2]['capture'].update(captured_at='2026-11-10T01:00:00')),
        ('Missing capture evidence identity is rejected', lambda a: a[-2]['capture'].update(evidence_sha256='')),
        ('Unknown snapshot fields are rejected', lambda a: a[-2].update(allow_missing=True)),
        ('Boolean schema version is rejected', lambda a: a[-2].update(schema_version=True)),
        ('Source plan/configuration baseline mismatch is rejected', lambda a: a[1]['replacement_baseline'].update(version='NCI_2026_09D')),
        ('Non-NCI configuration is rejected', lambda a: a[0].update(source='MTH')),
    ]:
        changed = list(fixture());change(changed)
        rejects(changed, label, rehash=label != 'Changed state hash is rejected')
    reordered = list(fixture())
    for key in ('sources', 'replacement_sources', 'source_roots', 'termgroups'):
        reordered[-2][key].reverse()
    report = run(reordered)
    good(report['findings'] == result['findings'] and report['coverage'] == result['coverage'], 'Unordered inventory rows cannot change findings or counts')
    print(json.dumps({'status': 'PASS', 'checks': len(checks), 'details': checks}, indent=2))
    return checks


if __name__ == '__main__':
    check()
