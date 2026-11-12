#!/usr/bin/env python3
"""Offline MTH preparation discovery; observations never approve release choices.

Only the caller's verified binary ``open_role(ref, role)`` streams are read.
Prepared MRSAB is subset evidence, never evidence that omitted publisher sources
were removed. Publisher completeness below is an explicitly reviewed declaration,
not an independent authentication of the publisher's distribution.
"""
import release_mth as mth


INVENTORY_SCOPE = 'full-publisher-release'
RRF_WIDTHS = {'MRSAB.RRF': 25, 'MRRANK.RRF': 4, 'MRAUI.RRF': 9, 'MRCUI.RRF': 7}
MAX_RECORD_BYTES = 2 * 1024**2
MAX_INVENTORY_ITEMS = 100_000
MAX_PRIOR_CUIS = 10_000_000
MAX_HISTORY_RELEASES = 512


def _lines(handle):
    """Reject oversized physical records before decoding or splitting them."""
    while True:
        raw = handle.readline(MAX_RECORD_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError('Record exceeds the ' + str(MAX_RECORD_BYTES) + '-byte discovery limit')
        yield raw


def analyze(configuration, artifacts, open_role):
    """Return discovery issues, observations and required inputs without writes.

    Full inventory is supported only for a selected publisher-bundle with
    data.inventory_evidence binding its MRSAB descriptor SHA, current publisher
    release, full-publisher-release scope, review_status and nonempty review_id.
    Such discovery does not implement MetamorphoSys or publisher conversion.
    Null final ID bounds are a later decision, never a reason to skip discovery.
    """
    config = configuration if isinstance(configuration, dict) else {}
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    inputs = config.get('inputs') if isinstance(config.get('inputs'), dict) else {}
    issues, decisions, required = [], [], []
    seen_issues, seen_required = set(), set()
    facts = {'source': 'MTH', 'version': config.get('version'),
             'execution_eligible': False, 'publisher_preparation_executed': False,
             'historical_database_reconstruction_required': False,
             'inventory_completeness_independently_authenticated': False,
             'scanned_roles': [], 'absence_is_removal_evidence': False,
             'retained_reviewed_source_choices': [],
             'physical_scan_limits': {'record_bytes': MAX_RECORD_BYTES, 'inventory_items': MAX_INVENTORY_ITEMS,
                                      'prior_CUIs': MAX_PRIOR_CUIS, 'history_release_values': MAX_HISTORY_RELEASES}}

    def path(ref, suffix=''):
        return '/artifacts/' + str(ref).replace('~', '~0').replace('/', '~1') + suffix

    def issue(code, message, at, severity='error'):
        key = (code, message, at, severity)
        if key not in seen_issues:
            seen_issues.add(key)
            issues.append({'code': code, 'severity': severity, 'message': message, 'path': at})

    def need(ref, role, reason, at):
        key = (ref, role, reason, at)
        if key not in seen_required:
            seen_required.add(key)
            required.append({'artifact': ref, 'role': role, 'reason': reason, 'path': at})

    def artifact(ref, kind, at, version=None):
        value = artifacts.get(ref) if isinstance(ref, str) else None
        if not isinstance(value, dict) or value.get('artifact_type') != kind:
            issue('MTH_DISCOVERY_ARTIFACT_REQUIRED', 'Supply the declared ' + kind + ' artifact.', at, 'decision')
            need(ref, kind, 'Declared ' + kind + ' evidence is absent.', at)
            return {}, {}
        if value.get('source') != 'MTH' or (version is not None and value.get('version') != version):
            issue('MTH_DISCOVERY_ARTIFACT_RELEASE', 'Artifact source/version differs from the selected role.', path(ref))
        data = value.get('data')
        if not isinstance(data, dict):
            issue('MTH_DISCOVERY_ARTIFACT_DATA', 'Typed artifact data must be an object.', path(ref, '/data'))
            data = {}
        return value, data

    def descriptors(ref):
        value = artifacts.get(ref, {}) if isinstance(ref, str) else {}
        files = value.get('files', []) if isinstance(value, dict) else []
        files = files if isinstance(files, list) else []
        result = {}
        for item in files:
            if isinstance(item, dict) and isinstance(item.get('role'), str):
                result.setdefault(item['role'], []).append(item)
        return result

    def closure(ref, roles, reason):
        found = descriptors(ref)
        for role in sorted(roles):
            if len(found.get(role, [])) != 1:
                issue('MTH_DISCOVERY_INPUT_CLOSURE', reason + ': exactly one ' + role + ' is required.',
                      path(ref, '/files'), 'decision' if not found.get(role) else 'error')
                need(ref, role, reason, path(ref, '/files'))
        return all(len(found.get(role, [])) == 1 for role in roles)

    def scan(ref, role, parser):
        if len(descriptors(ref).get(role, [])) != 1:
            issue('MTH_DISCOVERY_INPUT_UNAVAILABLE', 'The selected input role is missing or duplicated: ' + role + '.',
                  path(ref, '/files'), 'decision' if not descriptors(ref).get(role) else 'error')
            need(ref, role, 'Verified bytes are required for this discovery observation.', path(ref, '/files'))
            return None
        try:
            # The context exit verifies/drains the selected bytes too. Discard
            # observations if either the body or the verification exit fails.
            with open_role(ref, role) as handle:
                result = parser(handle)
            facts['scanned_roles'].append({'artifact': ref, 'role': role})
            return result
        except (ValueError, OSError, UnicodeError) as exc:
            issue('MTH_DISCOVERY_INPUT_UNAVAILABLE', 'Cannot verify/parse ' + role + ': ' + str(exc), path(ref, '/files'))
            need(ref, role, 'Supply readable, unchanged, dialect-valid verified input bytes.', path(ref, '/files'))
            return None

    def native(handle, role):
        for number, raw in enumerate(_lines(handle), 1):
            if not isinstance(raw, bytes) or not raw.endswith(b'|\n') or b'\r' in raw or b'\0' in raw:
                raise ValueError(role + ': invalid native record terminator at row ' + str(number))
            fields = raw[:-2].decode('utf-8').split('|')
            if len(fields) != RRF_WIDTHS[role]:
                raise ValueError(role + ': wrong field count at row ' + str(number))
            yield fields

    def token(value):
        return isinstance(value, str) and mth.TOKEN.fullmatch(value) is not None

    def release(value):
        return isinstance(value, str) and mth.RELEASE.fullmatch(value) is not None

    def reviewed(value):
        return (isinstance(value, dict) and value.get('review_status') == 'reviewed' and
                value.get('proposed', False) is False and value.get('proposal', False) is False)

    def disposition_is(row, values):
        return isinstance(row.get('disposition'), str) and row['disposition'] in values

    def read_mrsab(handle):
        rows, versions = [], set()
        for fields in native(handle, 'MRSAB.RRF'):
            vsab, rsab, current, sabin = fields[2], fields[3], fields[21], fields[22]
            if not token(vsab) or not token(rsab) or current not in ('Y', 'N') or sabin not in ('Y', 'N'):
                raise ValueError('MRSAB identity/CURVER/SABIN is malformed')
            if vsab in versions:
                raise ValueError('MRSAB repeats a VSAB: ' + vsab)
            if len(versions) >= MAX_INVENTORY_ITEMS:
                raise ValueError('MRSAB exceeds the distinct inventory discovery limit')
            versions.add(vsab)
            rows.append({'source': rsab, 'version': vsab, 'current': current == 'Y',
                         'in_subset': sabin == 'Y', 'source_family': fields[5]})
        if not rows:
            raise ValueError('MRSAB inventory is empty')
        return rows

    def read_sources(handle):
        values = {}
        for raw in _lines(handle):
            line = raw.decode('utf-8').rstrip('\n')
            if not line or line.startswith(' '):
                continue
            fields = line.split('|')
            if len(fields) != 2 or not all(token(x) for x in fields) or fields[0] in values:
                raise ValueError('Saved current_sources is malformed or ambiguous')
            if len(values) >= MAX_INVENTORY_ITEMS:
                raise ValueError('Saved current_sources exceeds the distinct inventory discovery limit')
            values[fields[0]] = fields[1]
        if not values:
            raise ValueError('Saved current_sources is empty')
        return values

    def read_precedence(handle):
        values = {}
        for raw in _lines(handle):
            line = raw.decode('utf-8').rstrip('\n')
            if not line or line.startswith(' '):
                continue
            fields = line.split('|')
            identity = fields[0].split('/')
            if (len(fields) != 2 or len(identity) != 2 or not all(token(x) for x in identity) or
                    not fields[1].isdigit() or fields[0] in values):
                raise ValueError('Saved precedence has malformed or repeated termgroup identities')
            if len(values) >= MAX_INVENTORY_ITEMS:
                raise ValueError('Saved precedence exceeds the distinct inventory discovery limit')
            values[fields[0]] = int(fields[1])
        if not values:
            raise ValueError('Saved precedence is empty')
        return values

    def read_ranks(handle):
        rows, identities = [], set()
        for fields in native(handle, 'MRRANK.RRF'):
            rank, source, tty, suppress = fields
            if (not rank.isdigit() or not token(source) or not token(tty) or not token(suppress) or
                    (source, tty) in identities):
                raise ValueError('MRRANK contains malformed or repeated source/TTY identities')
            if len(identities) >= MAX_INVENTORY_ITEMS:
                raise ValueError('MRRANK exceeds the distinct inventory discovery limit')
            identities.add((source, tty))
            rows.append({'rank': int(rank), 'source': source, 'term_type': tty, 'suppress': suppress})
        if not rows:
            raise ValueError('MRRANK is empty')
        return rows

    def read_identity(handle):
        rows, cuis, minimum, maximum = 0, set(), None, None
        for raw in _lines(handle):
            fields = raw.decode('utf-8').rstrip('\n').split('|')
            if (not raw.endswith(b'\n') or b'\r' in raw or b'\0' in raw or len(fields) != 2 or
                    not re_cui(fields[0]) or not fields[1].isdigit() or int(fields[1]) <= 0 or fields[0] in cuis):
                raise ValueError('Last-inserted CUI map is malformed or repeats a CUI')
            if len(cuis) >= MAX_PRIOR_CUIS:
                raise ValueError('Last-inserted CUI map exceeds the distinct CUI discovery limit')
            cuis.add(fields[0])
            said = int(fields[1])
            minimum = said if minimum is None else min(minimum, said)
            maximum = said if maximum is None else max(maximum, said)
            rows += 1
        if not rows:
            raise ValueError('Last-inserted CUI map is empty')
        return {'rows': rows, 'unique_CUIs': len(cuis), 'minimum_SAID': minimum, 'maximum_SAID': maximum}

    def re_cui(value):
        return len(value) > 1 and value.startswith('C') and value[1:].isdigit()

    def read_termgroups(handle):
        rows, identities = [], set()
        for raw in _lines(handle):
            if not raw.endswith(b'|\n'):
                raise ValueError('Prepared termgroups.src needs native trailing pipe/newline')
            fields = raw[:-2].decode('utf-8').split('|')
            if len(fields) != 6 or fields[0] in identities or not fields[0] or not fields[1]:
                raise ValueError('Prepared termgroups.src is malformed or ambiguous')
            if any(len(x.split('/')) != 2 or not all(token(y) for y in x.split('/')) for x in fields[:2]):
                raise ValueError('Prepared termgroups.src has malformed termgroup references')
            if len(identities) >= MAX_INVENTORY_ITEMS:
                raise ValueError('Prepared termgroups.src exceeds the distinct inventory discovery limit')
            identities.add(fields[0])
            rows.append({'termgroup': fields[0], 'below_termgroup': fields[1]})
        if not rows:
            raise ValueError('Prepared termgroups.src is empty')
        return rows

    version, stage = config.get('version'), inputs.get('source_data_stage')
    if config.get('source') != 'MTH' or not release(version):
        issue('MTH_DISCOVERY_RELEASE', 'Use an explicit MTH_YYYYAA or MTH_YYYYAB current release.', '/configuration/version')
    selected = inputs.get('source_data', [])
    if not isinstance(selected, list) or len(selected) != 1 or not isinstance(selected[0], str):
        issue('MTH_DISCOVERY_BUNDLE', 'Select exactly one current publisher or prepared bundle.', '/configuration/inputs/source_data')
        selected = []
    bundle_ref = selected[0] if selected else None
    kind = {'prepared': 'prepared-bundle', 'publisher': 'publisher-bundle'}.get(stage)
    if kind is None:
        issue('MTH_DISCOVERY_STAGE', 'Select publisher or prepared input discovery explicitly.', '/configuration/inputs/source_data_stage')
        bundle, bundle_data = {}, {}
    else:
        bundle, bundle_data = artifact(bundle_ref, kind, '/configuration/inputs/source_data', version)
    plan_ref, state_ref, identity_ref = (inputs.get(key) for key in ('source_plan', 'reference_ncimeta', 'identity_state'))
    _, plan = artifact(plan_ref, 'source-plan', '/configuration/inputs/source_plan', version)
    state_artifact, state = artifact(state_ref, 'ncimeta-state', '/configuration/inputs/reference_ncimeta', version)
    baseline = config.get('replacement_baseline')
    valid_baseline = (isinstance(baseline, dict) and baseline.get('source') == 'MTH' and
                      release(baseline.get('version')) and release(version) and baseline['version'] < version)
    if not valid_baseline:
        issue('MTH_DISCOVERY_INSERTED_BASELINE', 'Select the actual last-inserted MTH identity baseline; do not infer it from publisher previous.',
              '/configuration/replacement_baseline', 'decision')
    baseline_version = baseline.get('version') if valid_baseline else None
    identity_artifact, identity = artifact(identity_ref, 'identity-state', '/configuration/inputs/identity_state', baseline_version)
    facts['replacement_baseline'] = baseline
    facts['prepared_bundle_closure_declared'] = False
    if stage == 'prepared':
        facts['prepared_bundle_closure_declared'] = closure(bundle_ref, mth.RRF_ROLES, 'Complete preserved prepared conversion bundle')
        facts['preserved_metadata_closure_declared'] = closure(state_ref, mth.METADATA_ROLES, 'Preserved metadata and installed/ranking snapshot')
        # Preserve the canonical source validator's producer, disposition and
        # final-range semantics. Discovery changes no existing admission rules.
        try:
            preflight = mth.analyze(config, artifacts)
            for item in preflight['issues']:
                issue(item['code'], item['message'], item['path'],
                      'decision' if item['severity'] == 'blocker' else item['severity'])
            facts['prepared_preflight_facts'] = preflight['facts']
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            issue('MTH_DISCOVERY_DECLARATION', 'Malformed source declaration: ' + str(exc), '/configuration')
    else:
        closure(bundle_ref, {'MRSAB.RRF'}, 'Publisher source inventory')
        closure(state_ref, {'ncimid.sources', 'ncimid.termgroups'}, 'Saved installed-source and precedence state')
        issue('MTH_DISCOVERY_PUBLISHER_PREPARATION_UNIMPLEMENTED',
              'Publisher inventory discovery does not run MetamorphoSys or produce the eleven prepared RRF inputs and eight metadata inputs.',
              '/configuration/inputs/source_data_stage', 'decision')
        need(None, 'prepared-bundle', 'Native conversion requires a separately produced complete prepared bundle; preserved valid inputs are sufficient.',
             '/configuration/inputs/source_data')
    closure(identity_ref, {'cui_said_map'}, 'Last-inserted retained-CUI identity state')
    for ref, data in ((plan_ref, plan), (state_ref, state), (identity_ref, identity)):
        if data.get('replacement_baseline') != baseline:
            issue('MTH_DISCOVERY_BASELINE_CONFLICT', 'Saved declaration and explicit last-inserted baseline differ.', path(ref, '/data/replacement_baseline'))
    if identity.get('identity_role') != 'last-inserted-cui-map':
        issue('MTH_DISCOVERY_IDENTITY_ROLE', 'CUI identity retention needs the last-inserted map, independently of publisher-previous preparation.',
              path(identity_ref, '/data/identity_role'), 'decision')
    inventory = scan(bundle_ref, 'MRSAB.RRF', read_mrsab)
    ranks = scan(bundle_ref, 'MRRANK.RRF', read_ranks)
    installed = scan(state_ref, 'ncimid.sources', read_sources)
    precedence = scan(state_ref, 'ncimid.termgroups', read_precedence)
    termgroups = scan(state_ref, 'src/termgroups.src', read_termgroups) if stage == 'prepared' else None
    facts['prior_identity'] = scan(identity_ref, 'cui_said_map', read_identity)
    declared_installed = state.get('installed_sources')
    if installed is not None:
        observed = [{'source': source, 'version': value} for source, value in sorted(installed.items())]
        facts['installed_sources'] = observed
        if (not isinstance(declared_installed, list) or any(not isinstance(x, dict) for x in declared_installed) or
                sorted(declared_installed, key=lambda x: str(x.get('source'))) != observed):
            issue('MTH_DISCOVERY_INSTALLED_CHANGED', 'Verified current_sources bytes differ from the typed saved installed-source declaration.',
                  path(state_ref, '/data/installed_sources'))
        if installed.get('MTH') != baseline_version:
            issue('MTH_DISCOVERY_INSTALLED_BASELINE', 'Saved installed MTH version differs from the requested identity baseline.', path(state_ref))
    full_inventory = False
    evidence = bundle_data.get('inventory_evidence')
    mrsab_descriptors = descriptors(bundle_ref).get('MRSAB.RRF', [])
    if stage == 'publisher' and isinstance(evidence, dict):
        full_inventory = (bundle.get('source') == 'MTH' and bundle.get('version') == version and
                          evidence.get('scope') == INVENTORY_SCOPE and reviewed(evidence) and
                          isinstance(evidence.get('review_id'), str) and bool(evidence['review_id'].strip()) and
                          release(version) and evidence.get('publisher_release') == version[4:] and
                          bundle_data.get('publisher_release', version[4:]) == version[4:] and
                          len(mrsab_descriptors) == 1 and evidence.get('mrsab_sha256') == mrsab_descriptors[0].get('sha256') and
                          inventory is not None)
        if not full_inventory:
            issue('MTH_DISCOVERY_INVENTORY_EVIDENCE', 'Full inventory needs reviewed full-publisher-release scope, review identity, current publisher release and selected MRSAB SHA binding.',
                  path(bundle_ref, '/data/inventory_evidence'), 'decision')
    facts['inventory_coverage'] = ('declared-reviewed-full-publisher-inventory' if full_inventory else
                                    'prepared-subset-only' if stage == 'prepared' else 'publisher-inventory-scope-unproven')
    facts['full_publisher_inventory_declared_and_scanned'] = full_inventory
    if not full_inventory:
        issue('MTH_DISCOVERY_FULL_INVENTORY_REQUIRED', 'Complete upcoming-release source discovery requires a reviewed full publisher MRSAB inventory; subset omissions cannot establish publisher absence.',
              '/configuration/inputs/source_data', 'decision')
        need(None, 'MRSAB.RRF', 'Reviewed full-publisher-release inventory with release and MRSAB SHA binding.',
             '/configuration/inputs/source_data')

    chain = plan.get('publisher_release_chain')
    valid_chain = (isinstance(chain, list) and len(chain) >= 2 and all(release(x) for x in chain) and
                   len(set(chain)) == len(chain) and chain == sorted(chain) and
                   valid_baseline and chain[0] == baseline_version and chain[-1] == version)
    if not valid_chain:
        issue('MTH_DISCOVERY_HISTORY_CHAIN', 'Review the explicit publisher release chain from last inserted through current; no calendar inference is made.',
              path(plan_ref, '/data/publisher_release_chain'), 'decision')
    previous = plan.get('publisher_previous')
    if (not isinstance(previous, dict) or previous.get('source') != 'MTH' or not valid_chain or
            previous.get('version') != chain[-2]):
        issue('MTH_DISCOVERY_PUBLISHER_PREVIOUS', 'Publisher previous must independently match the penultimate declared publisher release, not a substituted inserted baseline.',
              path(plan_ref, '/data/publisher_previous'), 'decision')
    facts['publisher_previous'] = previous
    facts['publisher_release_chain'] = chain
    history_refs = config.get('publisher_history', [])
    history_refs = history_refs if isinstance(history_refs, list) else []
    history_sources = [(bundle_ref, bundle_data)]
    for ref in history_refs:
        extra, data = artifact(ref, 'publisher-history', '/configuration/publisher_history')
        if not valid_chain or extra.get('version') not in chain:
            issue('MTH_DISCOVERY_HISTORY_RELEASE', 'Extra history must identify an explicitly selected transition release.', path(ref, '/version'))
        closure(ref, {'MRAUI.RRF', 'MRCUI.RRF'}, 'Selected historical identity/merge records')
        history_sources.append((ref, data))
    selection = plan.get('history_selection')
    selection = selection if isinstance(selection, dict) else {}
    facts['history_requirements'] = {}
    facts['observed_history_versions'] = {}
    for kind in mth.HISTORY_KINDS:
        expected = (chain if kind == 'moved_aui_releases' else chain[:-1]) if valid_chain else []
        requested = selection.get(kind)
        if not reviewed(selection) or requested != expected or not valid_chain:
            issue('MTH_DISCOVERY_HISTORY_SELECTION', 'Review complete transition history separately for moved AUIs, CUI merges and bequeathal.',
                  path(plan_ref, '/data/history_selection/' + kind), 'decision')
        coverage = set()
        for ref, data in history_sources:
            declared = data.get('history_coverage', {})
            values = declared.get(kind) if isinstance(declared, dict) else None
            if isinstance(values, list) and all(release(x) for x in values) and len(set(values)) == len(values):
                coverage.update(values)
        missing = sorted(set(expected) - coverage)
        facts['history_requirements'][kind] = {'required': expected, 'declared_coverage': sorted(coverage), 'missing': missing}
        if missing:
            role = 'MRAUI.RRF' if kind == 'moved_aui_releases' else 'MRCUI.RRF'
            issue('MTH_DISCOVERY_HISTORY_GAP', 'No declared complete history coverage for ' + ', '.join(missing) + '; zero observed rows cannot prove coverage.',
                  path(plan_ref, '/data/history_selection/' + kind), 'decision')
            need(None, role, kind + ' complete producer coverage for ' + ', '.join(missing), '/configuration/publisher_history')
    for ref, data in history_sources:
        for role, index in (('MRAUI.RRF', 2), ('MRCUI.RRF', 1)):
            if role not in descriptors(ref):
                continue
            def read_history(handle, role=role, index=index):
                counts = {}
                for fields in native(handle, role):
                    value = fields[index]
                    identity = value if value.startswith('MTH_') else 'MTH_' + value
                    if not release(identity):
                        raise ValueError('History VER is not a canonical publisher release')
                    if identity not in counts and len(counts) >= MAX_HISTORY_RELEASES:
                        raise ValueError('History exceeds the distinct release-value discovery limit')
                    counts[identity] = counts.get(identity, 0) + 1
                return counts
            observed = scan(ref, role, read_history)
            if observed is not None:
                facts['observed_history_versions'][str(ref) + '/' + role] = observed
    facts['history_row_absence_proves_complete_coverage'] = False

    rows = plan.get('dispositions', [])
    rows = rows if isinstance(rows, list) else []
    by_source, mapping = {}, {}
    mappings = plan.get('vsab_mappings', [])
    for row in mappings if isinstance(mappings, list) else []:
        if not isinstance(row, dict) or not all(token(row.get(k)) for k in ('source', 'publisher_version', 'version')):
            issue('MTH_DISCOVERY_MAPPING', 'Publisher-to-NCImeta VSAB mappings must be explicit typed identities.', path(plan_ref, '/data/vsab_mappings'))
            continue
        key = (row['source'], row['publisher_version'])
        if key in mapping:
            issue('MTH_DISCOVERY_MAPPING_AMBIGUOUS', 'Repeated publisher source/version mapping needs review.', path(plan_ref, '/data/vsab_mappings'))
        mapping[key] = row['version']
    plan_reviewed = reviewed(plan) and isinstance(plan.get('review_id'), str) and bool(plan.get('review_id', '').strip())
    if not plan_reviewed:
        issue('MTH_DISCOVERY_PLAN_REVIEW', 'Source discovery preserves proposals; an identified review must approve the source plan.', path(plan_ref, '/data'), 'decision')
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not token(row.get('source')) or not token(row.get('version')):
            issue('MTH_DISCOVERY_DISPOSITION', 'Saved source choices must contain typed source and NCImeta version.', path(plan_ref, '/data/dispositions/' + str(index)))
            continue
        by_source.setdefault(row['source'], []).append(row)
    current, versions_to_source = {}, {}
    for row in inventory or []:
        versions_to_source[row['version']] = row['source']
        if row['current']:
            current.setdefault(row['source'], []).append(row['version'])
    facts['observed_source_versions'] = inventory if inventory is not None else []
    facts['observed_current_source_count'] = len(current)
    for source in sorted(set(current) | set(by_source) | set(installed or {})):
        observed = current.get(source, [])
        saved = by_source.get(source, [])
        active = [row for row in saved if disposition_is(row, mth.ACTIVE)]
        prior = installed.get(source) if installed is not None else None
        reasons = []
        if len(observed) > 1:
            issue('MTH_DISCOVERY_CURRENT_AMBIGUOUS', 'Multiple CURVER=Y versions for ' + source + '; discovery does not choose one.', path(bundle_ref, '/files'))
            reasons.append('ambiguous-current-publisher-version')
        if len(active) > 1:
            issue('MTH_DISCOVERY_ACTIVE_AMBIGUOUS', 'More than one active saved source choice needs review for ' + source + '.', path(plan_ref, '/data/dispositions'))
            reasons.append('ambiguous-saved-active-choice')
        if not observed:
            # Prepared absence is neither an inventory finding nor a proposed
            # REMOVE. Even full-inventory absence requires a staff decision.
            if full_inventory and prior is not None and source not in by_source:
                reasons.append('installed-source-absent-from-declared-current-inventory')
            elif full_inventory and active:
                reasons.append('active-saved-source-absent-from-declared-current-inventory')
            elif not full_inventory:
                continue
        if observed and not saved:
            reasons.append('newly-observed-source' if prior is None and installed is not None else 'source-choice-missing')
        if saved and (not plan_reviewed or any(not reviewed(row) for row in saved)):
            reasons.append('saved-choice-unreviewed')
        for row in saved:
            disposition = row.get('disposition') if isinstance(row.get('disposition'), str) else ''
            if disposition not in mth.DISPOSITIONS:
                reasons.append('invalid-or-undecided-disposition')
            if 'prior_version' not in row or (disposition in {'KEEP', 'UPDATE', 'REMOVE'} and row.get('prior_version') != prior):
                reasons.append('saved-installed-version-conflict')
            if disposition == 'NEW' and (row.get('prior_version') is not None or prior is not None):
                reasons.append('new-source-already-installed')
            if disposition == 'KEEP' and row.get('version') != prior:
                reasons.append('keep-target-differs-from-installed')
            if disposition == 'UPDATE' and row.get('version') == prior and stage == 'publisher':
                reasons.append('same-version-update-needs-prepared-background-exclusion-evidence')
            if not isinstance(row.get('excluded_termgroups'), list) or any(not token(x) for x in row.get('excluded_termgroups', [])):
                reasons.append('termgroup-exclusions-unresolved')
            if disposition in mth.ACTIVE:
                publisher = row.get('publisher_version')
                if not token(publisher) or mapping.get((source, publisher)) != row.get('version'):
                    reasons.append('publisher-vsab-mapping-unresolved')
                expected_native = publisher if stage == 'publisher' else row.get('version')
                if observed and disposition != 'KEEP' and expected_native not in observed:
                    reasons.append('saved-choice-not-current-in-selected-inventory')
            if disposition == 'SPECIAL':
                policy = artifacts.get(config.get('policy_ref'), {})
                policy_data = policy.get('data', {}) if isinstance(policy, dict) else {}
                rules = policy_data.get('special_disposition_rules', []) if isinstance(policy_data, dict) else []
                if not token(row.get('special_handling')) or not isinstance(rules, list) or row.get('special_handling') not in rules:
                    reasons.append('special-handling-policy-unresolved')
        record = {'code': 'MTH_SOURCE_CHOICE', 'source': source, 'observed_current_versions': observed,
                  'installed_version': prior, 'saved_choices': saved,
                  'status': 'unresolved' if reasons else 'retained-reviewed-choice',
                  'reasons': sorted(set(reasons)), 'path': path(plan_ref, '/data/dispositions')}
        if reasons:
            decisions.append(record)
            issue('MTH_DISCOVERY_SOURCE_DECISION', source + ' requires review: ' + ', '.join(sorted(set(reasons))) + '.',
                  record['path'], 'decision')
        else:
            facts['retained_reviewed_source_choices'].append(record)

    rank_observations = []
    if ranks is not None and precedence is not None:
        for row in ranks:
            native_source, tty = row['source'], row['term_type']
            source = versions_to_source.get(native_source, native_source if native_source in current else None)
            if source is None:
                issue('MTH_DISCOVERY_RANK_SOURCE', 'MRRANK source has no unambiguous selected MRSAB identity: ' + native_source + '.', path(bundle_ref, '/files'))
                continue
            active = [x for x in by_source.get(source, []) if disposition_is(x, {'NEW', 'UPDATE'})]
            for choice in active:
                exclusions = choice.get('excluded_termgroups', [])
                if isinstance(exclusions, list) and tty in exclusions:
                    continue
                target = choice['version'] + '/' + tty
                same_tty_prior = (choice.get('prior_version') + '/' + tty) if token(choice.get('prior_version')) else None
                rank_observations.append({'source': source, 'publisher_rank': row['rank'], 'term_type': tty,
                                          'NCImeta_termgroup': target,
                                          'same_term_type_prior_present': same_tty_prior in precedence,
                                          'ranking_target_selected': False})
                # Rank numbers are observations only. Choosing an insertion
                # target through predecessor traversal is a separate decision.
        for row in termgroups or []:
            target = row['below_termgroup']
            if target not in precedence:
                issue('MTH_DISCOVERY_RANK_TARGET_MISSING', 'Prepared termgroup ranking target is absent from saved precedence: ' + target + '.',
                      path(state_ref, '/files'), 'decision')
                decisions.append({'code': 'MTH_TERMGROUP_RANKING', 'status': 'unresolved', **row,
                                  'reason': 'Saved precedence does not prove the insertion target.', 'path': path(state_ref, '/files')})
        generated = {row['termgroup'] for row in termgroups or []}
        for row in rank_observations:
            if row['NCImeta_termgroup'] not in generated:
                issue('MTH_DISCOVERY_RANK_REVIEW', 'Review an explicit ranking target for ' + row['NCImeta_termgroup'] + '; publisher rank does not select an NCImeta insertion point.',
                      path(state_ref, '/files'), 'decision')
                decisions.append({'code': 'MTH_TERMGROUP_RANKING', 'status': 'unresolved', **row,
                                  'path': path(state_ref, '/files')})
    facts['termgroup_observations'] = rank_observations
    facts['saved_precedence_count'] = len(precedence) if precedence is not None else None
    facts['ranking_targets_verified'] = bool(stage == 'prepared' and termgroups and precedence is not None and ranks is not None and
                                             not any(x['code'] in {'MTH_DISCOVERY_RANK_TARGET_MISSING', 'MTH_DISCOVERY_RANK_REVIEW',
                                                                   'MTH_DISCOVERY_RANK_SOURCE'} for x in issues))
    if config.get('source_atom_ids') is None:
        issue('MTH_DISCOVERY_FINAL_RANGE_PENDING', 'A final separately evidenced allocation is required before conversion, after preliminary discovery/estimation.',
              '/configuration/source_atom_ids', 'decision')
        need(None, 'id-allocation', 'Final MTH allocation with two reserved SRC positions; no allocation is made by discovery.',
             '/configuration/source_atom_ids')
    facts['source_choices_unresolved'] = sum(row.get('status') == 'unresolved' and row['code'] == 'MTH_SOURCE_CHOICE' for row in decisions)
    facts['coverage_limitations'] = ['Verified selected input streams only; no DB calls, MetamorphoSys, allocation, execution or approval.',
                                    'Declared complete history is separate from observed row presence or absence.',
                                    'Publisher rank values do not select NCImeta ranking targets.']
    return {'issues': issues, 'decisions': decisions, 'facts': facts, 'required_inputs': required}
