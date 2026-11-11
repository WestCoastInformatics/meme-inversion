#!/usr/bin/env python3
"""Curate captured MTH archive DATA into a manifest, without acquisition.

Accepts either a normalized capture or the inventory/captures wrapper produced
by the read-only archive inventory tool (``mth_existing`` or
``result.mth_existing``). A supplement may add ``prepared``, ``prior_identity``
and ``reference_stage_evidence``. Missing closure produces a useful report and
no manifest; the tool never invents hashes, dispositions or predecessor data.

Normalized capture keys::

  version, archive:{uri,sha256,bytes}, members:{relative-path:descriptor},
  prepared:{files:[typed-file],mrsab_data_b64,subset_directory,
            history_coverage,history_coverage_evidence,
            facts:{MRAUI.RRF:{sha256,bytes,rows,malformed_rows,versions},
                   MRCUI.RRF:{...}}},
  prior_identity:{version,files:[typed-file],facts:{sha256,bytes,rows,
                 malformed_rows}},
  reference_stage_evidence:{reference_stage:"inversion-src",description:...}

Regular member descriptors contain sha256/bytes and optional data_b64; links
contain kind:"symlink"/target. Member paths are relative to the source release
directory. All original member descriptors come from one hash-bound archive.
Prepared and prior files may instead identify different archives or S3 objects.
No input URI is opened. Native materialization and physical scans remain gates.
The exact frozen standard archive_path becomes a local-cache URI. A complete
mth-prepared-capture-receipt can be supplied directly as prepared (with explicit
history coverage added); its known SHA values become standard local descriptors
and retain S3 object selectors for future acquisition. Uncaptured S3 declarations
remain remote declarations and cannot pass the native location gate.
"""
import argparse
import base64
from collections import Counter
import copy
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

import execute_release_mth as execution
import release_mth

DECISIONS = ('ncisources.spec', 'sab.vsab.map', 'src_data')
SHA = re.compile(r'[0-9a-f]{64}')
RELEASE = re.compile(r'MTH_[0-9]{4}(?:AA|AB)')
BARE_RELEASE = re.compile(r'[0-9]{4}(?:AA|AB)')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def _relative(path):
    if (not isinstance(path, str) or not path or '\\' in path or
            any(ord(char) < 32 or ord(char) == 127 for char in path)):
        raise ValueError('Unsafe captured member path')
    value = PurePosixPath(path)
    if value.is_absolute() or '..' in value.parts or value.as_posix() != path or path == '.':
        raise ValueError('Unsafe captured member path: ' + path)
    return path


def _identity(value, label):
    if (not isinstance(value, dict) or not isinstance(value.get('sha256'), str) or
            not SHA.fullmatch(value['sha256']) or type(value.get('bytes')) is not int or value['bytes'] < 0):
        raise ValueError('Missing valid SHA256/byte identity: ' + label)
    return {'sha256': value['sha256'], 'bytes': value['bytes']}


def _object_identity(value, expected_bytes):
    keys = {'ContentLength', 'ETag', 'LastModified', 'VersionId'}
    if (not isinstance(value, dict) or set(value) != keys or
            type(value.get('ContentLength')) is not int or value['ContentLength'] != expected_bytes or
            not isinstance(value.get('ETag'), str) or not re.fullmatch(r'"[^"\r\n]+"', value['ETag']) or
            not isinstance(value.get('LastModified'), str) or
            (value['VersionId'] is not None and (not isinstance(value['VersionId'], str) or not value['VersionId']))):
        raise ValueError('Complete matching frozen S3 object identity is required')
    instant = datetime.datetime.fromisoformat(value['LastModified'].replace('Z', '+00:00'))
    if instant.utcoffset() is None:
        raise ValueError('Frozen S3 LastModified must identify an instant with timezone')
    return copy.deepcopy(value)


def _prepared_capture(value, version):
    """Project a complete first-capture receipt onto its exact native cache."""
    if not isinstance(value, dict):
        raise ValueError('A prepared declaration or complete capture receipt object is required')
    result = copy.deepcopy(value)
    if result.get('artifact_type') != 'mth-prepared-capture-receipt':
        return result  # Plain declarations confer no captured-cache assurance.
    if (result.get('schema_version') != 1 or result.get('source') != 'MTH' or
            result.get('version') != version or result.get('complete') is not True):
        raise ValueError('Prepared capture receipt must be complete and identify the current MTH release')
    request = result['request']
    subset = result['subset_directory']
    if (not isinstance(request, dict) or request.get('source') != 'MTH' or request.get('version') != version or
            request.get('bucket') != 'nci-evs-meme' or request.get('subset_directory') != subset or
            not isinstance(subset, str) or not re.fullmatch(r'subset[1-9][0-9]*/METASUBSET', subset) or
            result.get('request_sha256') != release_mth.artifact_sha256(request)):
        raise ValueError('Prepared capture request identity, subset or SHA256 differs from its receipt')
    files = _files(result, release_mth.RRF_ROLES, 'Prepared capture')
    objects = request.get('objects', [])
    if (not isinstance(objects, list) or len(objects) != len(release_mth.RRF_ROLES) or
            any(not isinstance(item, dict) or not isinstance(item.get('role'), str) for item in objects) or
            {item['role'] for item in objects} != release_mth.RRF_ROLES):
        raise ValueError('Prepared capture request must pin the eleven distinct roles')
    selected = {item['role']: item for item in objects}
    if any(set(result.get(key, {})) != release_mth.RRF_ROLES for key in ('before_heads', 'after_heads', 'facts')):
        raise ValueError('Prepared capture must retain complete before/after HEADs and scan facts')
    acquisition, origins = {}, []
    for descriptor in files:
        role = descriptor['role'];item = selected[role]
        key = 'mr/umls/' + version[4:] + '/' + subset + '/' + role
        if set(item) != {'role', 'key', 'head'} or item['key'] != key:
            raise ValueError('Prepared capture selected a different standard object path')
        identity = _object_identity(item['head'], descriptor['bytes'])
        if result['before_heads'][role] != identity or result['after_heads'][role] != identity:
            raise ValueError('Prepared before/after HEAD identities differ from the pinned selection')
        facts = result['facts'][role]
        if (_identity(facts, role) != _identity(descriptor, role) or facts.get('malformed_rows') != 0 or
                type(facts.get('rows')) is not int or facts['rows'] < 0):
            raise ValueError('Prepared capture file identity differs from its complete native scan')
        origin = 's3://nci-evs-meme/' + key
        local_uri = Path('/local/content/MEME/MEME5', key).as_uri()
        original = {**descriptor, 'uri': origin}
        prior_projection = result.get('capture_provenance', {}).get('s3_files', [])
        if ((descriptor['uri'] != origin and not (descriptor['uri'] == local_uri and original in prior_projection)) or
                'archive_member' in descriptor):
            raise ValueError('Prepared capture descriptor differs from the selected S3 object')
        origins.append(original)
        descriptor['uri'] = local_uri
        acquisition[role] = {'key': key, 'object_identity': identity}
    result['files'] = files
    result['acquisition'] = {'bucket': 'nci-evs-meme', 'objects': acquisition}
    result['capture_provenance'] = {
        'artifact_type': result['artifact_type'], 'request_sha256': result['request_sha256'],
        'request': copy.deepcopy(request), 'before_heads': copy.deepcopy(result['before_heads']),
        'after_heads': copy.deepcopy(result['after_heads']), 's3_files': origins,
        'apparatus_sha256': result.get('apparatus_sha256'),
        'scope': 'Previously computed SHA256 bound to its exact standard local cache; native admission re-verifies physical bytes'}
    return result


def normalize(capture, supplement=None):
    """Normalize the two documented shapes; reject conflicting capture bytes."""
    value = copy.deepcopy(capture)
    if not isinstance(value, dict):
        raise ValueError('A captured evidence object is required')
    if isinstance(value.get('result'), dict):
        value = value['result']
    if 'mth_existing' in value:
        value = value['mth_existing']
    if not isinstance(value, dict):
        raise ValueError('A captured MTH evidence object is required')
    if 'inventory' in value:
        version, reference, inventory = value['version'], value['reference'], value['inventory']
        if inventory.get('version') != version or reference.get('version') != version:
            raise ValueError('Captured inventory/reference release mismatch')
        archive = {'uri': 's3://' + reference['bucket'] + '/' + reference['key'],
                   'sha256': reference['archive_sha256'], 'bytes': reference['archive_bytes']}
        if (inventory.get('archive_sha256'), inventory.get('archive_bytes')) != (archive['sha256'], archive['bytes']):
            raise ValueError('Captured inventory/reference archive mismatch')
        if 'archive_path' in reference:
            expected = '/local/content/MEME/MEME5/inv/sources/' + version + '.tgz'
            if (reference['archive_path'] != expected or inventory.get('archive_path', expected) != expected or
                    reference.get('source') != 'MTH' or reference['bucket'] != 'nci-evs-meme' or
                    reference['key'] != 'inv/sources/' + version + '.tgz' or
                    reference.get('archive_read_only') is not True or reference.get('extracted') is not False):
                raise ValueError('Frozen archive receipt must name the exact standard read-only current-release cache')
            identity = _object_identity(reference.get('object_identity'), archive['bytes'])
            archive['capture_provenance'] = {'s3_uri': archive['uri'], 'object_identity': identity,
                'archive_sha256': archive['sha256'], 'archive_bytes': archive['bytes'],
                'archive_path': expected, 'archive_read_only': True, 'extracted': False,
                'scope': 'Frozen archive capture receipt; physical cache bytes are independently verified by native admission'}
            archive['uri'] = Path(expected).as_uri()
        members = {}
        for entry in inventory['entries']:
            if entry['path'] == version:
                continue
            if not entry['path'].startswith(version + '/'):
                raise ValueError('Archive member lies outside the captured release')
            relative = _relative(entry['path'][len(version) + 1:])
            if relative in members:
                raise ValueError('Duplicate archive member: ' + relative)
            members[relative] = {**entry, 'bytes': entry['size']}
        for path, body in value.get('captures', {}).items():
            if not path.startswith(version + '/') or path[len(version) + 1:] not in members:
                raise ValueError('Captured body is absent from inventory: ' + path)
            relative = path[len(version) + 1:]
            if _identity(members[relative], relative) != _identity(body, relative):
                raise ValueError('Captured body/inventory identity mismatch: ' + path)
            members[relative]['data_b64'] = body['data_b64']
        value = {**{key: item for key, item in value.items() if key not in
                    ('reference', 'inventory', 'captures')}, 'archive': archive, 'members': members}
    if supplement is not None:
        if not isinstance(supplement, dict):
            raise ValueError('A supplemental evidence object is required')
        for key, item in supplement.items():
            if key in value and value[key] != item:
                raise ValueError('Supplement conflicts with captured evidence: ' + key)
            value[key] = copy.deepcopy(item)
    if not isinstance(value.get('version'), str) or not RELEASE.fullmatch(value['version']):
        raise ValueError('A canonical captured MTH release is required')
    if 'prepared' in value:
        value['prepared'] = _prepared_capture(value['prepared'], value['version'])
    archive = value['archive']
    _identity(archive, 'archive')
    if archive['bytes'] <= 0 or not isinstance(archive.get('uri'), str):
        raise ValueError('A nonempty archive with stable URI is required')
    if not isinstance(value.get('members'), dict):
        raise ValueError('Captured archive member inventory is required')
    for path, member in value['members'].items():
        _relative(path)
        if member.get('kind', 'file') == 'file':
            _identity(member, path)
        if 'data_b64' in member:
            raw = base64.b64decode(member['data_b64'], validate=True)
            if _identity(member, path) != {'sha256': digest(raw), 'bytes': len(raw)}:
                raise ValueError('Changed captured member bytes: ' + path)
    return value


def _body(capture, path):
    member = capture['members'].get(path, {})
    if member.get('kind', 'file') != 'file' or 'data_b64' not in member:
        raise ValueError('Captured regular-file body required: ' + path)
    return base64.b64decode(member['data_b64'], validate=True)


def _member(capture, path, role=None):
    member = capture['members'].get(path, {})
    if member.get('kind', 'file') != 'file':
        raise ValueError('Captured regular archive member required: ' + path)
    identity = _identity(member, path)
    archive = capture['archive']
    return {'role': role or path, 'uri': archive['uri'], **identity,
            'archive_member': capture['version'] + '/' + path,
            'archive_sha256': archive['sha256'], 'archive_bytes': archive['bytes'],
            'archive_format': archive.get('format', 'tar.gz')}


def _linked_release(capture, name):
    link = capture['members'].get(name, {})
    target = link.get('target', '')
    if link.get('kind') != 'symlink' or not re.fullmatch(r'\.\./MTH_[0-9]{4}(?:AA|AB)', target):
        raise ValueError('An explicit standard captured ' + name + ' release link is required')
    return target[3:]


def _history(capture):
    version = capture['version']
    script = _body(capture, 'invert1.s').decode()
    active = [line.strip() for line in script.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    variables = {}
    for line in active:
        match = re.fullmatch(r'set\s+(rel|prevrel[0-9]*)\s*=\s*[\'"]?([0-9]{4}(?:AA|AB))[\'"]?', line)
        if match:
            if match[1] in variables:
                raise ValueError('Duplicate captured release setting: ' + match[1])
            variables[match[1]] = match[2]
    if variables.get('rel') != version[4:]:
        raise ValueError('Captured invert1 current release differs from the archive')
    previous = _linked_release(capture, 'prev')
    if variables.get('prevrel') != previous[4:]:
        raise ValueError('Captured prev link and publisher-previous script setting disagree')

    def selected(role, field, output):
        lines = [line for line in active if 'Meta/' + role in line and output in line and line.startswith('awk ')]
        if len(lines) != 1:
            raise ValueError('One active captured history producer is required: ' + role + '/' + output)
        values = []
        for token in re.findall(r'\$' + str(field) + r'\s*==\s*"([^"]+)"', lines[0]):
            token = token.replace("'", '')
            if token.startswith('$'):
                token = variables.get(token[1:])
            if not isinstance(token, str) or not BARE_RELEASE.fullmatch(token):
                raise ValueError('Unresolved captured history release predicate')
            values.append('MTH_' + token)
        if not values or len(values) != len(set(values)):
            raise ValueError('Captured history release selection is missing or ambiguous')
        return sorted(values)

    moved = selected('MRAUI.RRF', 3, 'auis.moved')
    merges = selected('MRCUI.RRF', 2, 'cui_merges')
    spec = _body(capture, 'src/inv3.spec').decode()
    if ('DefineConst|MTHSAB|' + version) not in spec.splitlines():
        raise ValueError('Effective captured inv3 identifies a different current release')
    branches = {}
    for line in spec.splitlines():
        if not line.startswith('Scan|MRCUI'):
            continue
        relation = re.search(r"<REL>\s+eq\s+'(RB|RN|RO)'", line)
        releases = re.findall(r"<VER>\s+eq\s+'([0-9]{4}(?:AA|AB))'", line)
        if relation is None or not releases or relation[1] in branches or len(releases) != len(set(releases)):
            raise ValueError('Effective captured inv3 history branches need explicit consistent review')
        branches[relation[1]] = sorted('MTH_' + item for item in releases)
    if set(branches) != {'RB', 'RN', 'RO'} or len({tuple(item) for item in branches.values()}) != 1:
        raise ValueError('Effective captured inv3 bequeathal history selections disagree')
    return previous, {'moved_aui_releases': moved, 'cui_merge_releases': merges,
                      'bequeathal_releases': branches['RB']}


def _lineage(capture):
    current = capture['version']
    installed = []
    for line in _body(capture, 'ncimid.sources').decode().splitlines():
        if not line or line.startswith(' '):
            continue
        fields = line.split('|')
        if len(fields) != 2 or any(not release_mth.TOKEN.fullmatch(item) for item in fields):
            raise ValueError('Saved installed source identity is malformed')
        installed.append({'source': fields[0], 'version': fields[1]})
    if len({row['source'] for row in installed}) != len(installed):
        raise ValueError('Saved installed source identity is ambiguous')
    prior = [row['version'] for row in installed if row['source'] == 'MTH']
    sources = [line.split('|') for line in _body(capture, 'src/sources.src').decode().splitlines()
               if line.startswith(current + '|')]
    if (len(prior) != 1 or len(sources) != 1 or len(sources[0]) < 8 or
            sources[0][1] != prior[0] or sources[0][3:5] != [current, 'MTH'] or
            _linked_release(capture, 'old') != prior[0]):
        raise ValueError('Installed MTH, low-source metadata and old link must agree on the replacement baseline')
    if not RELEASE.fullmatch(prior[0]) or prior[0] >= current:
        raise ValueError('The inserted replacement baseline must precede current')
    previous, history = _history(capture)
    chain = sorted({current, prior[0], previous, *(item for rows in history.values() for item in rows)})
    if (chain[0] != prior[0] or chain[-1] != current or chain[-2] != previous or
            history['moved_aui_releases'] != chain or history['cui_merge_releases'] != chain[:-1] or
            history['bequeathal_releases'] != chain[:-1]):
        raise ValueError('Captured script/spec selections do not establish one complete explicit transition chain')
    return {'replacement_baseline': {'source': 'MTH', 'version': prior[0]},
            'publisher_previous': {'source': 'MTH', 'version': previous},
            'publisher_release_chain': chain, 'history_selection': history,
            'installed_sources': installed}


def _bounds(capture):
    rows = _body(capture, 'range3.spec').decode().splitlines()
    values = {}
    for row in rows:
        fields = row.split('|')
        if len(fields) != 2 or fields[0] not in ('SourceAtomIdBase', 'SourceAtomIdLimit') or not fields[1].isdigit() or fields[0] in values:
            raise ValueError('Captured final range must have exactly the two distinct integer settings')
        values[fields[0]] = int(fields[1])
    if set(values) != {'SourceAtomIdBase', 'SourceAtomIdLimit'}:
        raise ValueError('Captured final range settings are incomplete')
    start, end = values['SourceAtomIdBase'] - 2, values['SourceAtomIdLimit']
    if start <= 0 or start + 3 > end:
        raise ValueError('Captured final range cannot hold the SRC positions and ordinary atoms')
    return {'start': start, 'end': end, 'bound_kind': 'reserved-historical-range'}


def _files(value, roles, label):
    files = value.get('files', []) if isinstance(value, dict) else []
    if (not isinstance(files, list) or len(files) != len(roles) or
            any(not isinstance(item, dict) for item in files) or {item.get('role') for item in files} != set(roles)):
        raise ValueError(label + ' requires exactly: ' + ', '.join(sorted(roles)))
    for item in files:
        _identity(item, label + '/' + item['role'])
        if not isinstance(item.get('uri'), str) or not item['uri']:
            raise ValueError('An explicit preserved file URI is required: ' + label + '/' + item['role'])
        if 'archive_member' in item:
            _relative(item['archive_member'])
            _identity({'sha256': item.get('archive_sha256'), 'bytes': item.get('archive_bytes')}, 'containing archive')
            if item.get('archive_format') not in ('tar.gz', 'zip') or item['archive_bytes'] <= 0:
                raise ValueError('Complete containing archive identity is required')
    return copy.deepcopy(files)


def curate(capture, engine_ref, review_id=None, supplement=None):
    """Return {manifest:object|null,issues,facts}; never admit or execute a run."""
    issues, facts = [], {'native_execution_performed': False, 'production_eligible': False,
                         'historical_database_reconstruction_required': False,
                         'MetamorphoSys_executed': False,
                         'curation_scope': 'Present-day binding of original authoritative archived staff choices; no historical JSON attestation'}

    def attempt(code, path, function):
        try:
            return function()
        except (ValueError, KeyError, TypeError, UnicodeError) as error:
            issues.append({'severity': 'blocker', 'code': code, 'message': str(error), 'path': path})
            return None

    captured = attempt('MTH_CAPTURE_INVALID', '/capture', lambda: normalize(capture, supplement))
    if captured is None:
        return {'manifest': None, 'issues': issues, 'facts': facts}
    version = captured['version']
    facts.update(version=version, archive=copy.deepcopy(captured['archive']),
                 capture_sha256=release_mth.artifact_sha256(captured))
    lineage = attempt('MTH_CAPTURE_LINEAGE', '/capture/members', lambda: _lineage(captured))
    bounds = attempt('MTH_CAPTURE_RANGE', '/capture/members/range3.spec', lambda: _bounds(captured))
    if lineage is not None:
        facts.update(lineage)
    if bounds is not None:
        facts['historical_range'] = bounds
    metadata = attempt('MTH_CAPTURE_METADATA', '/capture/members',
                       lambda: [_member(captured, role) for role in sorted(release_mth.METADATA_ROLES)])
    decision_files = attempt('MTH_CAPTURE_DECISIONS', '/capture/members',
                             lambda: [_member(captured, role) for role in DECISIONS])
    def decision_summary():
        rows = [line.split('|') for line in _body(captured, 'ncisources.spec').decode().splitlines()]
        if any(len(row) != 4 or row[2] not in release_mth.DISPOSITIONS for row in rows):
            raise ValueError('Unresolved or malformed captured staff decision')
        return {'rows': len(rows), 'by_disposition': dict(sorted(Counter(row[2] for row in rows).items()))}
    facts['preserved_staff_decisions'] = attempt('MTH_CAPTURE_DECISION_SYNTAX', '/capture/members/ncisources.spec', decision_summary)
    if not isinstance(engine_ref, str) or not re.fullmatch('[0-9a-f]{40}', engine_ref):
        issues.append({'severity': 'blocker', 'code': 'MTH_CURATION_ENGINE', 'message': 'Supply an immutable canonical engine commit; Git package admission remains independent.', 'path': '/engine_ref'})
    if not isinstance(review_id, str) or not review_id.strip():
        issues.append({'severity': 'blocker', 'code': 'MTH_CURATION_REVIEW', 'message': 'An external preservation-curation review identity is required; no choices are automatically approved.', 'path': '/review_id'})
    prepared = captured.get('prepared', {})
    prepared_files = attempt('MTH_CAPTURE_PREPARED_CLOSURE', '/capture/prepared/files',
                              lambda: _files(prepared, release_mth.RRF_ROLES, 'Prepared bundle'))
    def mrsab_body():
        raw = base64.b64decode(prepared['mrsab_data_b64'], validate=True)
        descriptor = next(item for item in prepared_files or [] if item['role'] == 'MRSAB.RRF')
        if _identity(descriptor, 'MRSAB.RRF') != {'sha256': digest(raw), 'bytes': len(raw)}:
            raise ValueError('Captured MRSAB body differs from prepared descriptor')
        fields = [execution._fields(row) for row in raw.splitlines(keepends=True)]
        if (not fields or any(len(row) != 25 for row in fields) or
                not any(row[2:4] == [version.encode(), b'MTH'] for row in fields)):
            raise ValueError('Prepared MRSAB must prove its current native MTH release')
        return raw
    mrsab = attempt('MTH_CAPTURE_MRSAB', '/capture/prepared/mrsab_data_b64', mrsab_body) if prepared_files is not None else None
    def coverage():
        selection = lineage['history_selection']
        value = prepared['history_coverage']
        if not isinstance(prepared.get('history_coverage_evidence'), str) or not prepared['history_coverage_evidence'].strip():
            raise ValueError('Explicit preserved history completeness evidence is required; observed rows alone cannot establish zero-event windows')
        for kind in release_mth.HISTORY_KINDS:
            if (not isinstance(value.get(kind), list) or len(set(value[kind])) != len(value[kind]) or
                    any(not isinstance(item, str) or not RELEASE.fullmatch(item) for item in value[kind]) or
                    not set(selection[kind]) <= set(value[kind])):
                raise ValueError('Prepared history coverage does not cover the captured selection: ' + kind)
        for role in ('MRAUI.RRF', 'MRCUI.RRF'):
            descriptor = next(item for item in prepared_files if item['role'] == role)
            scanned = prepared['facts'][role]
            if (_identity(scanned, role) != _identity(descriptor, role) or type(scanned.get('rows')) is not int or
                    scanned['rows'] < 0 or scanned.get('malformed_rows') != 0 or not isinstance(scanned.get('versions'), dict)):
                raise ValueError('Hash-bound complete history scan facts are required: ' + role)
        return copy.deepcopy(value)
    history_coverage = attempt('MTH_CAPTURE_HISTORY_COVERAGE', '/capture/prepared', coverage) if lineage and prepared_files is not None else None
    projection = None
    if mrsab is not None:
        projection = attempt('MTH_CAPTURE_DECISION_PROJECTION', '/capture/members/ncisources.spec', lambda:
            execution.manifest_decisions_from_preserved(*[_body(captured, role) for role in DECISIONS],
                _body(captured, 'ncimid.sources'), mrsab, version, review_id=review_id))
    def prepared_selection():
        active = [row for row in projection['dispositions'] if row['disposition'] in release_mth.ACTIVE]
        if len({row['version'] for row in active}) != len(active):
            raise ValueError('Active VSAB decisions must be unambiguous for preserved subset projection')
        decisions = {row['version']: row for row in active}
        native = {fields[2].decode(): fields[3].decode()
                  for fields in [execution._fields(row) for row in mrsab.splitlines(keepends=True)]}
        selected, versions = set(), set()
        for line in _body(captured, 'src/vsab.updates').decode().splitlines():
            fields = line.split('|')
            if len(fields) != 2 or fields[1] in versions or fields[1] not in decisions:
                raise ValueError('Saved VSAB updates must select distinct active staff decisions')
            prior, target = fields;row = decisions[target]
            expected = '' if row['disposition'] == 'KEEP' else ('New' if row['disposition'] == 'NEW' else row['prior_version'])
            if prior != expected or native.get(target) != row['source']:
                raise ValueError('Saved VSAB updates differ from staff dispositions or prepared MRSAB identity')
            versions.add(target);selected.add(row['source'])
        return {'selected_sources': sorted(selected), 'selection_evidence': {
            'profile': 'mth-rest-subset-selection-v1',
            'ncisources_sha256': captured['members']['ncisources.spec']['sha256'],
            'vsab_updates_sha256': captured['members']['src/vsab.updates']['sha256'],
            'installed_sources_sha256': captured['members']['ncimid.sources']['sha256'],
            'mrsab_sha256': digest(mrsab),
            'scope': 'Actual saved VSAB updates projected against original staff decisions, installed source state and full prepared MRSAB; physical validation remains independent'}}
    selection = attempt('MTH_CAPTURE_PREPARED_SELECTION', '/capture/members/src/vsab.updates', prepared_selection) if projection is not None else None
    prior = captured.get('prior_identity', {})
    prior_files = attempt('MTH_CAPTURE_PRIOR_IDENTITY', '/capture/prior_identity/files',
                           lambda: _files(prior, {'cui_said_map'}, 'Prior CUI identity'))
    def prior_shape():
        if prior['version'] != lineage['replacement_baseline']['version']:
            raise ValueError('Prior CUI map identifies a different last-inserted baseline')
        scanned = prior['facts']
        if (_identity(scanned, 'prior scan') != _identity(prior_files[0], 'prior map') or
                type(scanned.get('rows')) is not int or scanned['rows'] <= 0 or scanned.get('malformed_rows') != 0):
            raise ValueError('Nonempty hash-bound prior identity scan facts are required')
        return copy.deepcopy(scanned)
    if lineage is not None and prior_files is not None:
        facts['prior_identity'] = attempt('MTH_CAPTURE_PRIOR_IDENTITY', '/capture/prior_identity', prior_shape)
    references = attempt('MTH_CAPTURE_REFERENCE_FILES', '/capture/members/src',
                           lambda: [_member(captured, 'src/' + name) for name in execution.OUTPUT_NAMES])
    def reference_stage():
        value = captured['reference_stage_evidence']
        if (value.get('reference_stage') != 'inversion-src' or not isinstance(value.get('description'), str) or
                not value['description'].strip()):
            raise ValueError('Explicit evidence must identify the current official outputs as inversion-src')
        return copy.deepcopy(value)
    stage = attempt('MTH_CAPTURE_REFERENCE_STAGE', '/capture/reference_stage_evidence', reference_stage)
    subset = prepared.get('subset_directory')
    if not isinstance(subset, str) or not re.fullmatch(r'subset[1-9][0-9]*/METASUBSET', subset):
        issues.append({'severity': 'blocker', 'code': 'MTH_CAPTURE_SUBSET', 'message': 'Identify the actual preserved standard subsetN/METASUBSET location.', 'path': '/capture/prepared/subset_directory'})
    if issues:
        return {'manifest': None, 'issues': issues, 'facts': facts}

    tool_hash = digest(Path(__file__).read_bytes())
    capture_id = captured.get('capture_id') or 'archive-curation:' + version + ':' + facts['capture_sha256'][:16]
    evidence_kind = captured.get('evidence_kind', 'captured')
    if evidence_kind not in ('captured', 'synthetic-fixture'):
        issues.append({'severity': 'blocker', 'code': 'MTH_CURATION_EVIDENCE_KIND',
                       'message': 'Curated bindings are present-day captured evidence, or explicit synthetic fixtures.',
                       'path': '/capture/evidence_kind'})
        return {'manifest': None, 'issues': issues, 'facts': facts}
    def artifact(kind, data, files=(), release=version):
        if any('archive_member' in item and item['uri'] == captured['archive']['uri'] for item in files):
            data = {**data, 'archive_capture_provenance': copy.deepcopy(captured['archive'].get('capture_provenance', {
                'origin_uri': captured['archive']['uri'], 'scope': 'Declared archive identity; no captured local-cache receipt supplied'}))}
        return {'schema_version': 1, 'artifact_type': kind, 'source': 'MTH', 'version': release,
                'provenance': {'producer': 'curate_archived_mth.py', 'producer_version': tool_hash,
                               'capture_id': capture_id, 'evidence_kind': evidence_kind},
                'files': list(files), 'data': data}
    baseline = lineage['replacement_baseline']
    plan_data = {key: value for key, value in projection.items() if key != 'observed_installed_sources'}
    plan_data.update({key: value for key, value in lineage.items() if key != 'installed_sources'})
    plan_data['history_selection']['review_status'] = 'reviewed'
    plan = artifact('source-plan', plan_data, decision_files)
    policy = artifact('policy', {'subset_profile': 'preserved-mth-rest-' + subset.split('/')[0] + '-v1',
                                 'special_disposition_rules': [], 'curation_scope': facts['curation_scope']})
    artifacts = {'mth-plan': plan, 'mth-policy': policy}
    artifacts['mth-prepared'] = artifact('prepared-bundle', {
        'publisher_release': version[4:], 'subset_directory': subset,
        'source_plan_ref': 'mth-plan', 'source_plan_sha256': release_mth.artifact_sha256(plan),
        'policy_ref': 'mth-policy', 'policy_sha256': release_mth.artifact_sha256(policy),
        'subset_profile': policy['data']['subset_profile'], 'history_coverage': history_coverage,
        'history_coverage_evidence': prepared['history_coverage_evidence'],
        **selection,
        **({'acquisition': copy.deepcopy(prepared['acquisition']),
            'prepared_capture_provenance': copy.deepcopy(prepared['capture_provenance'])}
           if 'acquisition' in prepared and 'capture_provenance' in prepared else {}),
        'curation_scope': facts['curation_scope']}, prepared_files)
    artifacts['mth-state'] = artifact('ncimeta-state', {
        'source_plan_ref': 'mth-plan', 'source_plan_sha256': release_mth.artifact_sha256(plan),
        'replacement_baseline': baseline, 'installed_sources': projection['observed_installed_sources'],
        'curation_scope': facts['curation_scope']}, metadata)
    artifacts['mth-identity'] = artifact('identity-state', {'replacement_baseline': baseline,
        'identity_role': 'last-inserted-cui-map'}, prior_files, release=baseline['version'])
    artifacts['mth-allocation'] = artifact('id-allocation', {**bounds, 'stage': 'final',
        'reserved_SRC_atoms': 2, 'production_reservation': False, 'new_allocation_performed': False},
        [_member(captured, 'range3.spec')])
    artifacts['mth-reference'] = artifact('reference-inversion', {**stage,
        'curation_scope': 'Original official archive member identities; current curation does not assert a fresh replay matched'}, references)
    artifacts['mth-environment'] = artifact('environment-profile', {'profile_id': 'meme-dev-v1'})
    artifacts['mth-validation'] = artifact('validation-profile', {'profile_id': 'mth-prepared-core-v1'})
    config = {'schema_version': 2, 'source': 'MTH', 'version': version, 'engine_ref': engine_ref,
        'policy_ref': 'mth-policy', 'environment_profile': 'mth-environment',
        'replacement_baseline': baseline, 'comparison_baseline': None, 'publisher_history': [],
        'inputs': {'source_data': ['mth-prepared'], 'source_data_stage': 'prepared',
                   'reference_ncimeta': 'mth-state', 'identity_state': 'mth-identity', 'source_plan': 'mth-plan'},
        'source_atom_ids': {**bounds, 'provenance_ref': 'mth-allocation'},
        'validation_profile': 'mth-validation', 'output_stage': 'inversion-src', 'source_options': {},
        'replay': {'reference_ref': 'mth-reference', 'reference_stage': 'inversion-src', 'comparison_profile': 'exact'}}
    checked = release_mth.analyze(config, artifacts)
    issues.extend(checked['issues'])
    facts['source_preflight'] = checked['facts']
    manifest = {'schema_version': 1, 'artifact_type': 'ncimeta-release-manifest',
                'profile': release_mth.PROFILE, 'purpose': 'historical-replay',
                'configuration': config, 'artifacts': artifacts}
    return {'manifest': None if any(item['severity'] in ('error', 'blocker') for item in issues) else manifest,
            'issues': issues, 'facts': facts}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('capture')
    parser.add_argument('--engine-ref', required=True)
    parser.add_argument('--review-id')
    parser.add_argument('--supplement')
    parser.add_argument('--output', help='New manifest file; never overwritten or emitted when closure is incomplete')
    parser.add_argument('--report', help='New curation report file; never overwritten')
    arguments = parser.parse_args()
    result = curate(load(arguments.capture), arguments.engine_ref, arguments.review_id,
                    load(arguments.supplement) if arguments.supplement else None)
    if arguments.output and result['manifest'] is not None:
        with Path(arguments.output).open('x') as handle:
            json.dump(result['manifest'], handle, indent=2);handle.write('\n')
    if arguments.report:
        with Path(arguments.report).open('x') as handle:
            json.dump(result, handle, indent=2);handle.write('\n')
    print(json.dumps({'manifest_complete': result['manifest'] is not None, 'issues': result['issues'],
                      'facts': result['facts']}, indent=2))
    return 0 if result['manifest'] is not None else 2


if __name__ == '__main__':
    sys.exit(main())
