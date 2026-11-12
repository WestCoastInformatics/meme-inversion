#!/usr/bin/env python3
"""Confined MTH discovery checks using real RRF/state dialects and verified IO."""
import copy
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path

import discover_release_mth as discovery
import release_mth as mth

ROOT = Path(__file__).resolve().parents[1]


def rrf(fields):
    return ('|'.join(fields) + '|\n').encode()


def sab(source, version, current='Y', in_subset='Y'):
    fields = [''] * 25
    fields[2], fields[3], fields[5], fields[21], fields[22] = version, source, source, current, in_subset
    return rrf(fields)


def fixture():
    """Synthetic skipped-insertion case; publisher previous is NOT old."""
    manifest = json.loads((ROOT / 'docs/inversion-review/release-manifest-examples/mth.json').read_text())
    raw = {}
    for ref, artifact in manifest['artifacts'].items():
        for item in artifact['files']:
            raw[(ref, item['role'])] = (ROOT / item['uri'].removeprefix('repo:')).read_bytes()
    raw[('mth-prepared', 'MRSAB.RRF')] = (sab('MTH', 'MTH_2027AA') + sab('TEST', 'TEST_2026') +
                                           sab('NEWSOURCE', 'NEWSOURCE_1'))
    raw[('mth-prepared', 'MRRANK.RRF')] = (rrf(['1000', 'MTH_2027AA', 'SSN', 'N']) +
                                            rrf(['900', 'TEST_2026', 'PT', 'N']) +
                                            rrf(['800', 'NEWSOURCE_1', 'PT', 'N']))
    raw[('mth-state', 'ncimid.sources')] = b' SAB| VSAB\nMTH|MTH_2026AA\nTEST|TEST_2026\n'
    raw[('mth-state', 'ncimid.termgroups')] = b' Termgroup| Rank\nMTH_2026AA/SSN|1\nTEST_2026/PT|2\nSRC/VPT|3\n'
    raw[('mth-state', 'src/termgroups.src')] = (b'MTH_2027AA/SSN|MTH_2026AA/SSN|N|N|N|SSN|\n' +
                                                b'NEWSOURCE_1/PT|SRC/VPT|N|N|N|PT|\n')
    raw[('mth-identity', 'cui_said_map')] = b'C0000001|100\nC0000002|101\n'
    rebind(manifest, raw)
    return manifest, raw


def rebind(manifest, raw):
    for ref, artifact in manifest['artifacts'].items():
        for item in artifact['files']:
            if (ref, item['role']) in raw:
                value = raw[(ref, item['role'])]
                item.update(bytes=len(value), sha256=hashlib.sha256(value).hexdigest())
    artifacts, config = manifest['artifacts'], manifest['configuration']
    plan = artifacts[config['inputs']['source_plan']]
    artifacts['mth-prepared']['data']['source_plan_sha256'] = mth.artifact_sha256(plan)
    artifacts['mth-state']['data']['source_plan_sha256'] = mth.artifact_sha256(plan)
    artifacts['mth-prepared']['data']['policy_sha256'] = mth.artifact_sha256(artifacts[config['policy_ref']])


def reader(manifest, raw, failures=None, seen=None):
    """Verify on context EXIT too: late failures must discard parsed facts."""
    @contextmanager
    def open_role(ref, role):
        if seen is not None:
            seen.append((ref, role))
        matches = [item for item in manifest['artifacts'][ref]['files'] if item['role'] == role]
        if len(matches) != 1:
            raise ValueError('Missing/duplicate verified role')
        if failures and (ref, role) in failures:
            raise failures[(ref, role)]
        value = raw[(ref, role)]
        yield io.BytesIO(value)
        item = matches[0]
        if len(value) != item['bytes'] or hashlib.sha256(value).hexdigest() != item['sha256']:
            raise ValueError('Actual verified bytes changed')
    return open_role


def publisher_fixture():
    manifest, raw = fixture()
    artifact = manifest['artifacts']['mth-prepared']
    artifact['artifact_type'] = 'publisher-bundle'
    artifact['files'] = [item for item in artifact['files'] if item['role'] in {'MRSAB.RRF', 'MRRANK.RRF', 'MRAUI.RRF', 'MRCUI.RRF'}]
    # Full publisher MRSAB has publisher VSABs; it is not the normalized subset.
    # SABIN=N does not remove a current publisher source from discovery.
    raw[('mth-prepared', 'MRSAB.RRF')] = (sab('MTH', 'MTH') + sab('TEST', 'TEST2026') +
                                           sab('NEWSOURCE', 'NEWSOURCE1', in_subset='N'))
    raw[('mth-prepared', 'MRRANK.RRF')] = (rrf(['1000', 'MTH', 'SSN', 'N']) + rrf(['900', 'TEST', 'PT', 'N']) +
                                            rrf(['800', 'NEWSOURCE', 'PT', 'N']))
    manifest['configuration']['inputs']['source_data_stage'] = 'publisher'
    rebind(manifest, raw)
    artifact['data']['inventory_evidence'] = {
        'scope': 'full-publisher-release', 'publisher_release': '2027AA', 'review_status': 'reviewed',
        'review_id': 'SYNTHETIC-INVENTORY-REVIEW',
        'mrsab_sha256': next(item['sha256'] for item in artifact['files'] if item['role'] == 'MRSAB.RRF')}
    return manifest, raw


def check():
    passed = []

    def good(value, label):
        assert value, label
        passed.append(label)

    def analyze(manifest, raw, **kwargs):
        return discovery.analyze(manifest['configuration'], manifest['artifacts'], reader(manifest, raw, **kwargs))

    def has(result, code, severity=None):
        return any(row['code'] == code and (severity is None or row['severity'] == severity) for row in result['issues'])

    def mutate(label, change, code, severity=None, bind=True):
        manifest, raw = fixture()
        change(manifest, raw)
        if bind:
            rebind(manifest, raw)
        result = analyze(manifest, raw)
        good(has(result, code, severity), label)
        good(result['facts']['execution_eligible'] is False, label + ': no execution eligibility')
        return result

    manifest, raw = fixture()
    before = copy.deepcopy(manifest), copy.deepcopy(raw)
    seen = []
    result = analyze(manifest, raw, seen=seen)
    good(result['facts']['inventory_coverage'] == 'prepared-subset-only' and
         has(result, 'MTH_DISCOVERY_FULL_INVENTORY_REQUIRED', 'decision'),
         'A complete preserved subset is explicitly insufficient for complete upcoming-release inventory')
    good(result['facts']['prepared_bundle_closure_declared'] and result['facts']['preserved_metadata_closure_declared'],
         'Eleven RRF and eight metadata roles are declared without scanning all native content')
    good(result['facts']['ranking_targets_verified'] and not any(row['severity'] == 'error' for row in result['issues']),
         'Supplied valid ranking targets are checked against actual saved precedence')
    good(result['facts']['replacement_baseline']['version'] == 'MTH_2026AA' and
         result['facts']['publisher_previous']['version'] == 'MTH_2026AB',
         'Last inserted and uninserted publisher previous retain independent identities')
    good(len(result['facts']['retained_reviewed_source_choices']) == 3 and not result['decisions'] and
         all(row['status'] == 'retained-reviewed-choice' for row in result['facts']['retained_reviewed_source_choices']),
         'Saved reviewed source choices survive discovery without new invented dispositions')
    good(result['facts']['prior_identity'] == {'rows': 2, 'unique_CUIs': 2, 'minimum_SAID': 100, 'maximum_SAID': 101},
         'The actual last-inserted CUI map is parsed through verified streams')
    good(('mth-prepared', 'MRCONSO.RRF') not in seen and ('mth-prepared', 'MRREL.RRF') not in seen and
         ('mth-identity', 'cui_said_map') in seen,
         'Discovery reads selected metadata/identity/history only, without full atom or relationship scans')
    good((manifest, raw) == before and analyze(manifest, raw) == result and json.loads(json.dumps(result)) == result,
         'Discovery is deterministic, JSON compatible and leaves inputs unchanged')
    good(not result['facts']['history_row_absence_proves_complete_coverage'] and
         not result['facts']['inventory_completeness_independently_authenticated'],
         'Row observations never authenticate omitted history or full inventory completeness')
    good(all(set(row) == {'artifact', 'role', 'reason', 'path'} for row in result['required_inputs']),
         'Required inputs follow the shared artifact/role/reason/path contract')

    # A second release uses exactly the same logic, including a direct insertion.
    direct, values = fixture()
    current, prior = 'MTH_2026AB', 'MTH_2026AA'
    direct['configuration']['version'] = current
    for ref, artifact in direct['artifacts'].items():
        if artifact['artifact_type'] != 'identity-state':
            artifact['version'] = current
    plan = direct['artifacts']['mth-plan']['data']
    plan['publisher_previous'] = {'source': 'MTH', 'version': prior}
    plan['publisher_release_chain'] = [prior, current]
    plan['history_selection'] = {'review_status': 'reviewed', 'moved_aui_releases': [prior, current],
                                 'cui_merge_releases': [prior], 'bequeathal_releases': [prior]}
    plan['dispositions'][0]['version'] = current
    plan['vsab_mappings'][0]['version'] = current
    plan['src_root']['version'] = current
    direct['artifacts']['mth-prepared']['data'].update(publisher_release=current[4:], history_coverage={
        key: value for key, value in plan['history_selection'].items() if key != 'review_status'})
    values[('mth-prepared', 'MRSAB.RRF')] = values[('mth-prepared', 'MRSAB.RRF')].replace(b'MTH_2027AA', current.encode())
    values[('mth-prepared', 'MRRANK.RRF')] = values[('mth-prepared', 'MRRANK.RRF')].replace(b'MTH_2027AA', current.encode())
    values[('mth-state', 'src/termgroups.src')] = values[('mth-state', 'src/termgroups.src')].replace(b'MTH_2027AA', current.encode())
    rebind(direct, values)
    direct_result = analyze(direct, values)
    good(not any(row['severity'] == 'error' for row in direct_result['issues']) and
         direct_result['facts']['publisher_previous']['version'] == prior,
         'Same analyzer supports a second current release and a direct publisher/inserted transition')

    mutate('Missing RRF closure surfaces an exact input requirement',
           lambda m, r: m['artifacts']['mth-prepared'].update(files=[x for x in m['artifacts']['mth-prepared']['files'] if x['role'] != 'MRREL.RRF']),
           'MTH_DISCOVERY_INPUT_CLOSURE', 'decision')
    mutate('Duplicate metadata role cannot supply closure',
           lambda m, r: m['artifacts']['mth-state']['files'].append(copy.deepcopy(m['artifacts']['mth-state']['files'][-1])),
           'MTH_DISCOVERY_INPUT_CLOSURE', 'error')
    mutate('Missing prior identity is surfaced without replacing it with publisher previous',
           lambda m, r: m['configuration']['inputs'].update(identity_state=None), 'MTH_DISCOVERY_ARTIFACT_REQUIRED', 'decision')
    mutate('Wrong prior identity release is an error',
           lambda m, r: m['artifacts']['mth-identity'].update(version='MTH_2026AB'), 'MTH_DISCOVERY_ARTIFACT_RELEASE', 'error')
    mutate('Changed physical installed state cannot be silently replaced by typed data',
           lambda m, r: r.update({('mth-state', 'ncimid.sources'): b'MTH|MTH_2026AB\nTEST|TEST_2026\n'}),
           'MTH_DISCOVERY_INSTALLED_CHANGED', 'error')
    mutate('Changed prior CUI bytes fail late verified-stream hash checking',
           lambda m, r: r.update({('mth-identity', 'cui_said_map'): b'C0000001|999\n'}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error', bind=False)
    malformed = mutate('Duplicate retained CUI cannot prove identity preservation',
           lambda m, r: r.update({('mth-identity', 'cui_said_map'): b'C0000001|100\nC0000001|101\n'}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error')
    good(malformed['facts']['prior_identity'] is None, 'Failed prior parsing discards partial identity observations')
    mutate('Publisher previous cannot be replaced by last inserted across skipped publication',
           lambda m, r: m['artifacts']['mth-plan']['data']['publisher_previous'].update(version='MTH_2026AA'),
           'MTH_DISCOVERY_PUBLISHER_PREVIOUS', 'decision')
    mutate('Missing intervening history remains a required decision',
           lambda m, r: m['artifacts']['mth-prepared']['data']['history_coverage']['cui_merge_releases'].remove('MTH_2026AB'),
           'MTH_DISCOVERY_HISTORY_GAP', 'decision')
    mutate('Unreviewed history choices remain decisions',
           lambda m, r: m['artifacts']['mth-plan']['data']['history_selection'].update(review_status='proposed', approved=True),
           'MTH_DISCOVERY_HISTORY_SELECTION', 'decision')
    mutate('Zero history records do not fill an undeclared history window',
           lambda m, r: (r.update({('mth-prepared', 'MRCUI.RRF'): b''}),
                         m['artifacts']['mth-prepared']['data']['history_coverage'].update(cui_merge_releases=[])),
           'MTH_DISCOVERY_HISTORY_GAP', 'decision')
    mutate('Unrecognized history dialect is not a guessed version',
           lambda m, r: r.update({('mth-prepared', 'MRAUI.RRF'): rrf(['A1', 'C1', 'previous', 'A2', '', '', '', '', ''])}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error')
    late_history = mutate('Changed history bytes fail verified-stream identity checking',
           lambda m, r: r.update({('mth-prepared', 'MRCUI.RRF'): b''}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error', bind=False)
    good('mth-prepared/MRCUI.RRF' not in late_history['facts']['observed_history_versions'],
         'Unverified late history results are discarded rather than reported as zero rows')
    changed, values = fixture()
    values[('mth-prepared', 'MRAUI.RRF')] = b''.join(
        rrf(['A0000001', 'C0000001', ver, 'A0000002', 'C0000002', 'SY', '', 'Y', '1'])
        for ver in ('2004AC', '2005AC', '2006AC', '2006AD', '2007AC', '2026AA'))
    values[('mth-prepared', 'MRCUI.RRF')] = b''.join(
        rrf(['C0000001', ver, 'SY', '', '', 'C0000002', 'Y'])
        for ver in ('1991AA', '2002AD', '2006AC', '2026AA'))
    rebind(changed, values)
    quarterly = analyze(changed, values)
    good(not has(quarterly, 'MTH_DISCOVERY_INPUT_UNAVAILABLE') and
         quarterly['facts']['observed_history_versions']['mth-prepared/MRAUI.RRF'] == {
             'MTH_2004AC': 1, 'MTH_2005AC': 1, 'MTH_2006AC': 1, 'MTH_2006AD': 1, 'MTH_2007AC': 1, 'MTH_2026AA': 1} and
         quarterly['facts']['observed_history_versions']['mth-prepared/MRCUI.RRF'] == {
             'MTH_1991AA': 1, 'MTH_2002AD': 1, 'MTH_2006AC': 1, 'MTH_2026AA': 1},
         'Real-shaped native history retains earlier quarterly AC/AD and 1991AA observations')
    good(quarterly['facts']['history_requirements']['moved_aui_releases']['required'] ==
         ['MTH_2026AA', 'MTH_2026AB', 'MTH_2027AA'] and
         quarterly['facts']['history_requirements']['moved_aui_releases']['declared_coverage'] ==
         ['MTH_2026AA', 'MTH_2026AB', 'MTH_2027AA'],
         'Observed quarterly history does not extend or replace declared AA/AB transition windows')
    good(mth.RELEASE.fullmatch('MTH_2006AC') is None and mth.RELEASE.fullmatch('MTH_2006AD') is None,
         'Current source configuration and transition release grammar remain unchanged')
    for malformed_ver in ('2006AE', '2006AC-extra', '2006A', '20XXAD'):
        values[('mth-prepared', 'MRCUI.RRF')] = rrf(['C0000001', malformed_ver, 'SY', '', '', 'C0000002', 'Y'])
        rebind(changed, values)
        invalid = analyze(changed, values)
        good(has(invalid, 'MTH_DISCOVERY_INPUT_UNAVAILABLE') and
             'mth-prepared/MRCUI.RRF' not in invalid['facts']['observed_history_versions'],
             'Malformed native history VER fails closed: ' + malformed_ver)
    mutate('Proposed plan approval boolean does not approve saved choices',
           lambda m, r: m['artifacts']['mth-plan']['data'].update(review_status='proposed', approved=True),
           'MTH_DISCOVERY_PLAN_REVIEW', 'decision')
    changed = mutate('New observed source remains undecided when missing from saved plan',
           lambda m, r: r.update({('mth-prepared', 'MRSAB.RRF'): r[('mth-prepared', 'MRSAB.RRF')] + sab('FRESH', 'FRESH_1')}),
           'MTH_DISCOVERY_SOURCE_DECISION', 'decision')
    fresh = next(row for row in changed['decisions'] if row.get('source') == 'FRESH')
    good(fresh['saved_choices'] == [] and fresh['reasons'] == ['newly-observed-source'] and 'disposition' not in fresh,
         'New-source observation supplies no invented NEW/EXCLUDE disposition')
    mutate('Two current publisher versions cannot be selected implicitly',
           lambda m, r: r.update({('mth-prepared', 'MRSAB.RRF'): r[('mth-prepared', 'MRSAB.RRF')] + sab('TEST', 'TEST_2027')}),
           'MTH_DISCOVERY_CURRENT_AMBIGUOUS', 'error')
    mutate('Duplicate publisher identity is rejected by the physical parser',
           lambda m, r: r.update({('mth-prepared', 'MRSAB.RRF'): r[('mth-prepared', 'MRSAB.RRF')] + sab('OTHER', 'TEST_2026')}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error')
    mutate('Multiple active saved source choices require review',
           lambda m, r: m['artifacts']['mth-plan']['data']['dispositions'].append(copy.deepcopy(m['artifacts']['mth-plan']['data']['dispositions'][1])),
           'MTH_DISCOVERY_ACTIVE_AMBIGUOUS', 'error')
    mutate('Missing mapping cannot be derived from a matching string',
           lambda m, r: m['artifacts']['mth-plan']['data'].update(vsab_mappings=[]), 'MTH_DISCOVERY_SOURCE_DECISION', 'decision')
    mutate('Malformed typed disposition cannot crash partial discovery',
           lambda m, r: m['artifacts']['mth-plan']['data']['dispositions'][1].update(disposition=[]),
           'MTH_DISCOVERY_SOURCE_DECISION', 'decision')
    mutate('Null exclusion choices remain unresolved without crashing ranking discovery',
           lambda m, r: m['artifacts']['mth-plan']['data']['dispositions'][2].update(excluded_termgroups=None),
           'MTH_DISCOVERY_SOURCE_DECISION', 'decision')
    mutate('Ranking target must exist in actual saved precedence',
           lambda m, r: r.update({('mth-state', 'src/termgroups.src'): b'MTH_2027AA/SSN|UNKNOWN/PT|N|N|N|SSN|\n'}),
           'MTH_DISCOVERY_RANK_TARGET_MISSING', 'decision')
    mutate('A new TTY gets a ranking decision, never a guessed lower neighbor',
           lambda m, r: r.update({('mth-prepared', 'MRRANK.RRF'): r[('mth-prepared', 'MRRANK.RRF')] + rrf(['750', 'NEWSOURCE_1', 'SY', 'N'])}),
           'MTH_DISCOVERY_RANK_REVIEW', 'decision')
    mutate('Ambiguous saved termgroup identity fails parsing',
           lambda m, r: r.update({('mth-state', 'ncimid.termgroups'): b'TEST_2026/PT|1\nTEST_2026/PT|2\n'}),
           'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error')
    mutate('Final range is a later decision and does not prevent observations',
           lambda m, r: m['configuration'].update(source_atom_ids=None), 'MTH_DISCOVERY_FINAL_RANGE_PENDING', 'decision')

    # Callback failures must not terminate the rest of a partial scan.
    manifest, raw = fixture()
    partial = analyze(manifest, raw, failures={('mth-state', 'ncimid.sources'): OSError('confined unavailable state')})
    good(has(partial, 'MTH_DISCOVERY_INPUT_UNAVAILABLE', 'error') and partial['facts']['observed_current_source_count'] == 3,
         'OSError in one verified input leaves other independent inventory observations available')
    partial = analyze(manifest, raw, failures={('mth-prepared', 'MRSAB.RRF'): ValueError('confined archive hash mismatch')})
    good(partial['facts']['observed_source_versions'] == [] and partial['facts']['full_publisher_inventory_declared_and_scanned'] is False,
         'Archive/member verification failure never leaves a complete-inventory claim')

    publisher, values = publisher_fixture()
    pub_result = analyze(publisher, values)
    good(pub_result['facts']['inventory_coverage'] == 'declared-reviewed-full-publisher-inventory' and
         not has(pub_result, 'MTH_DISCOVERY_FULL_INVENTORY_REQUIRED'),
         'Current reviewed publisher MRSAB digest supplies explicitly declared full inventory coverage')
    good(any(row.get('source') == 'NEWSOURCE' for row in pub_result['facts']['retained_reviewed_source_choices']) and
         next(row for row in pub_result['facts']['observed_source_versions'] if row['source'] == 'NEWSOURCE')['in_subset'] is False,
         'SABIN=N does not hide a current source in the full publisher inventory')
    good(has(pub_result, 'MTH_DISCOVERY_PUBLISHER_PREPARATION_UNIMPLEMENTED', 'decision') and
         pub_result['facts']['publisher_preparation_executed'] is False and
         any(row['role'] == 'prepared-bundle' for row in pub_result['required_inputs']),
         'Publisher discovery cannot stand in for MetamorphoSys/prepared-input production')
    for field, value in [('scope', 'prepared'), ('publisher_release', '2026AB'), ('review_status', 'proposed'),
                         ('review_id', ''), ('mrsab_sha256', '0' * 64)]:
        changed = copy.deepcopy(publisher)
        changed['artifacts']['mth-prepared']['data']['inventory_evidence'][field] = value
        invalid = analyze(changed, values)
        good(has(invalid, 'MTH_DISCOVERY_INVENTORY_EVIDENCE', 'decision') and
             not invalid['facts']['full_publisher_inventory_declared_and_scanned'],
             'Full inventory evidence fails closed for changed ' + field)
    changed = copy.deepcopy(publisher)
    changed['artifacts']['mth-prepared']['data']['publisher_release'] = '2026AB'
    invalid = analyze(changed, values)
    good(not invalid['facts']['full_publisher_inventory_declared_and_scanned'],
         'Contradictory producer release cannot retain full inventory coverage through a review label')
    changed = copy.deepcopy(manifest)
    changed['artifacts']['mth-prepared']['data']['inventory_evidence'] = copy.deepcopy(publisher['artifacts']['mth-prepared']['data']['inventory_evidence'])
    invalid = analyze(changed, raw)
    good(invalid['facts']['inventory_coverage'] == 'prepared-subset-only',
         'A completeness declaration cannot promote a prepared subset to full publisher inventory')
    # An absent source is a review item only under declared full inventory.
    for full in (False, True):
        changed, values = publisher_fixture() if full else fixture()
        changed['artifacts']['mth-state']['data']['installed_sources'].append({'source': 'RETIRED', 'version': 'RETIRED_1'})
        values[('mth-state', 'ncimid.sources')] += b'RETIRED|RETIRED_1\n'
        rebind(changed, values)
        result = analyze(changed, values)
        retired = [row for row in result['decisions'] if row.get('source') == 'RETIRED']
        good((len(retired) == 1 and retired[0]['status'] == 'unresolved' and retired[0]['saved_choices'] == []) if full else not retired,
             'Installed source absence ' + ('requires review without choosing REMOVE under declared full inventory' if full else
                                             'does not become a removal finding from a prepared subset'))
    good(all(row['severity'] in {'error', 'decision', 'warning'} for row in pub_result['issues']),
         'Discovery severity vocabulary matches the common report contract')
    changed, values = publisher_fixture()
    changed['artifacts']['mth-plan']['data']['dispositions'][1]['disposition'] = 'UPDATE'
    rebind(changed, values)
    invalid = analyze(changed, values)
    good(any('same-version-update-needs-prepared-background-exclusion-evidence' in row.get('reasons', [])
             for row in invalid['decisions']),
         'Publisher discovery cannot apply the prepared nonselected-background UPDATE exception')
    changed, values = fixture()
    values[('mth-prepared', 'MRSAB.RRF')] = b'x' * (discovery.MAX_RECORD_BYTES + 1) + b'\n'
    rebind(changed, values)
    invalid = analyze(changed, values)
    good(has(invalid, 'MTH_DISCOVERY_INPUT_UNAVAILABLE') and
         any('byte discovery limit' in row['message'] for row in invalid['issues']),
         'Actual oversized physical line is rejected before splitting or inventory retention')
    for constant, small, message in [('MAX_INVENTORY_ITEMS', 2, 'distinct inventory'),
                                     ('MAX_PRIOR_CUIS', 1, 'distinct CUI'),
                                     ('MAX_HISTORY_RELEASES', 1, 'distinct release-value')]:
        normal = getattr(discovery, constant)
        try:
            setattr(discovery, constant, small)
            changed, values = fixture()
            invalid = analyze(changed, values)
            good(has(invalid, 'MTH_DISCOVERY_INPUT_UNAVAILABLE') and
                 any(message in row['message'] for row in invalid['issues']),
                 'Physical distinct-value cap fails closed: ' + constant)
        finally:
            setattr(discovery, constant, normal)
    changed, values = fixture()
    values[('mth-prepared', 'MRAUI.RRF')] = rrf(['A1', 'C0000001', '2026AA', 'A2', '', '', '', '', '']) * 10_000
    rebind(changed, values)
    aggregated = analyze(changed, values)
    good(aggregated['facts']['observed_history_versions']['mth-prepared/MRAUI.RRF'] == {'MTH_2026AA': 10_000},
         'History preserves complete row counts in a small VER aggregate rather than retaining records')
    return passed


if __name__ == '__main__':
    passed = check()
    print(json.dumps({'passed': len(passed), 'checks': passed}, indent=2))
