#!/usr/bin/env python3
"""Read-only source discovery using the existing release-manifest vocabulary."""
import ast
import base64
from contextlib import contextmanager
import hashlib
import importlib
import os
from pathlib import Path
import stat
import tarfile
import zipfile

import release_manifest as manifests

HANDLERS = {'nci-publisher-inputs-v1': ('NCI', 'discover_release_nci'),
            'snomed-us-snapshot-inputs-v1': ('SNOMEDCT_US', 'discover_release_snomed'),
            'mth-prepared-inputs-v1': ('MTH', 'discover_release_mth')}


class CheckedStream:
    def __init__(self, handle, expected):
        self.handle, self.expected = handle, expected
        self.hash = hashlib.sha256();self.bytes = 0

    def _record(self, raw):
        self.hash.update(raw);self.bytes += len(raw)
        if self.bytes > self.expected['bytes']:raise ValueError('Input exceeds declared byte count')
        return raw

    def read(self, size=-1):return self._record(self.handle.read(size))
    def readline(self, size=-1):return self._record(self.handle.readline(size))
    def __iter__(self):return self
    def __next__(self):
        raw = self.readline()
        if not raw:raise StopIteration
        return raw

    def finish(self):
        while self.read(4*1024**2):pass
        actual = {'sha256': self.hash.hexdigest(), 'bytes': self.bytes}
        if actual != {key:self.expected[key] for key in actual}:raise ValueError('Input SHA-256/size differs from manifest')
        return actual


class Inputs:
    """Streams selected inputs; no extraction, download or official oracle reads."""
    def __init__(self, artifacts):
        self.artifacts = artifacts;self.verified = {};self.archives = {};self.snapshots = {};self.paths = {}

    def finish(self):
        issues = []
        for path,before in self.snapshots.items():
            try:unchanged = manifests._stamp(path.lstat()) == before
            except OSError:unchanged = False
            if not unchanged:
                issues.append(manifests.issue('error','DISCOVERY_INPUT_CHANGED','Selected input changed during the full discovery scan',str(path)))
                for key,value in self.paths.items():
                    if value == path:self.verified.pop(key,None)
        return issues

    def descriptor(self, reference, role):
        artifact = self.artifacts.get(reference)
        if not artifact:raise ValueError('Missing artifact: ' + str(reference))
        if artifact['artifact_type'] == 'reference-inversion':raise ValueError('Discovery cannot consume official output')
        selected = [item for item in artifact['files'] if item['role'] == role]
        if len(selected) != 1:raise ValueError('One declared input role required: ' + str(reference) + '/' + role)
        return artifact, selected[0]

    def _archive(self, path, handle, item, stamp):
        key = (str(path), item['archive_format'], item['archive_sha256'], item['archive_bytes'])
        if key in self.archives:
            if self.archives[key]['stamp'] != stamp:raise ValueError('Archive changed since verification')
            return self.archives[key]['members']
        checksum, size = manifests._hash_stream(handle)
        if (checksum, size) != (item['archive_sha256'], item['archive_bytes']):raise ValueError('Archive SHA-256/size differs')
        handle.seek(0);members = {}
        if item['archive_format'] == 'zip':
            with zipfile.ZipFile(handle) as archive:
                for member in archive.infolist():
                    name = member.filename.rstrip('/');manifests._relative(name)
                    if name in members:raise ValueError('Duplicate archive member')
                    kind = stat.S_IFMT(member.external_attr >> 16)
                    members[name] = (member.file_size, not member.is_dir() and kind in (0, stat.S_IFREG))
        elif item['archive_format'] == 'tar.gz':
            with tarfile.open(fileobj=handle, mode='r|gz') as archive:
                for member in archive:
                    name = member.name.removeprefix('./').rstrip('/')
                    if name == '.':continue
                    manifests._relative(name)
                    if name in members:raise ValueError('Duplicate archive member')
                    members[name] = (member.size, member.isfile())
        else:raise ValueError('Unsupported archive format')
        if manifests._stamp(os.fstat(handle.fileno())) != stamp or manifests._stamp(path.lstat()) != stamp:
            raise ValueError('Archive changed during verification')
        self.archives[key] = {'stamp':stamp, 'members':members}
        return members

    @contextmanager
    def open(self, reference, role):
        key = (reference,role);self.verified.pop(key,None)
        artifact, item = self.descriptor(reference, role)
        path = manifests.location(item, artifact['provenance']['evidence_kind'] == 'synthetic-fixture')
        if path is None:raise ValueError('Acquire declared S3 inputs before offline discovery')
        try:
            with manifests._open(path) as handle:
                stamp = manifests._stamp(os.fstat(handle.fileno()))
                if path in self.snapshots and self.snapshots[path] != stamp:raise ValueError('Input changed after an earlier discovery read')
                self.snapshots.setdefault(path,stamp);self.paths[key] = path
                if 'archive_member' in item:
                    members = self._archive(path, handle, item, stamp)
                    if members.get(item['archive_member']) != (item['bytes'], True):raise ValueError('Selected member missing, nonregular or wrong size')
                    handle.seek(0)
                    if item['archive_format'] == 'zip':
                        with zipfile.ZipFile(handle) as archive, archive.open(item['archive_member']) as incoming:
                            source = CheckedStream(incoming, item);yield source;actual = source.finish()
                    else:
                        with tarfile.open(fileobj=handle, mode='r:gz') as archive:
                            selected = next((m for m in archive if m.name.removeprefix('./').rstrip('/') == item['archive_member']), None)
                            if selected is None or not selected.isfile():raise ValueError('Selected member changed')
                            with archive.extractfile(selected) as incoming:
                                source = CheckedStream(incoming, item);yield source;actual = source.finish()
                else:
                    source = CheckedStream(handle, item);yield source;actual = source.finish()
                if manifests._stamp(os.fstat(handle.fileno())) != stamp or manifests._stamp(path.lstat()) != stamp:
                    raise ValueError('Input changed during discovery')
                self.verified[(reference, role)] = {'artifact':reference, 'role':role, **actual,
                    'uri':item['uri'], 'archive_member':item.get('archive_member'), 'status':'VERIFIED'}
        except (tarfile.TarError, zipfile.BadZipFile, EOFError, NotImplementedError, RuntimeError) as error:
            raise ValueError('Cannot verify selected input: ' + str(error)) from error


def validate(manifest):
    return manifests.schema_errors(manifest, manifests.load(manifests.DOCS/'release-manifest.schema.json'))


def discover(manifest, schema_validated=False):
    issues = [] if schema_validated else validate(manifest)
    config = manifest.get('configuration', {});profile = manifest.get('profile')
    report = {'schema_version':1, 'artifact_type':'ncimeta-release-preparation-review',
        'manifest_sha256':manifests.digest(manifest), 'source':config.get('source'), 'version':config.get('version'),
        'profile':profile, 'issues':issues, 'decisions':[], 'facts':{}, 'required_inputs':[], 'input_files':[],
        'discovery_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'execution_eligible':False, 'production_eligible':False, 'inversion_executed':False,
        'scope':'Physical input discovery and unresolved preparation decisions only; never execution admission or a comparison verdict.'}
    if not issues:
        selected = HANDLERS.get(profile)
        if selected is None or selected[0] != config.get('source'):
            issues.append(manifests.issue('error', 'DISCOVERY_PROFILE_UNSUPPORTED', 'No reviewed discovery adapter for this source/profile', 'profile'))
        else:
            inputs = Inputs(manifest['artifacts'])
            try:
                adapter = importlib.import_module(selected[1])
                if getattr(adapter,'__file__',None):report['source_adapter_sha256'] = hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest()
                result = adapter.analyze(config, manifest['artifacts'], inputs.open)
                for key in ('issues', 'decisions', 'required_inputs'):report[key].extend(result.get(key, []))
                report['facts'] = result.get('facts', {})
            except (ValueError, KeyError, OSError, UnicodeError) as error:
                issues.append(manifests.issue('error', 'DISCOVERY_INPUT_FAILURE', str(error), 'artifacts'))
            changed = inputs.finish();issues.extend(changed)
            report['selected_input_set_unchanged'] = not changed
            report['input_files'] = sorted(inputs.verified.values(), key=lambda item:(item['artifact'],item['role']))
    invalid = any(item['severity'] == 'error' for item in issues)
    pending = bool(report['decisions']) or any(item['severity'] in ('decision', 'blocker') for item in issues)
    report['status'] = 'DISCOVERY_BLOCKED' if invalid else 'DECISIONS_REQUIRED' if pending else 'DISCOVERY_COMPLETE'
    report['discovery_complete'] = not invalid and not pending
    return report


def capsule(manifest):
    errors = validate(manifest)
    if errors:raise ValueError('Invalid discovery manifest: ' + errors[0]['message'])
    selected = HANDLERS.get(manifest['profile'])
    if selected is None or selected[0] != manifest['configuration']['source']:raise ValueError('Unsupported source discovery profile')
    import inversion_request as requests
    names = {'release_preparation.py', selected[1]+'.py'}
    available = {path.stem:path for path in (requests.ROOT/'tools').glob('*.py')};pending = list(names)
    while pending:
        name = pending.pop()
        for node in ast.walk(ast.parse((requests.ROOT/'tools'/name).read_bytes())):
            imports = [a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for imported in imports:
                dependency = imported.split('.')[0]
                if dependency in available and dependency+'.py' not in names:
                    names.add(dependency+'.py');pending.append(dependency+'.py')
    ref = requests.commit('HEAD');modules = {};provenance = []
    schema_path = 'docs/inversion-review/release-manifest.schema.json'
    if requests.blob(ref,schema_path) != (requests.ROOT/schema_path).read_bytes():raise ValueError('Commit consumed discovery schema first')
    for name in sorted(names):
        path = 'tools/'+name;raw = requests.blob(ref,path)
        if raw != (requests.ROOT/path).read_bytes():raise ValueError('Commit consumed discovery code first: '+path)
        modules[name] = base64.b64encode(raw).decode();provenance.append({'repository_path':path,'sha256':hashlib.sha256(raw).hexdigest()})
    result = {'artifact_type':'ncimeta-release-discovery-capsule', 'manifest':manifest,
        'manifest_sha256':manifests.digest(manifest), 'apparatus_ref':ref, 'modules_b64':modules, 'provenance':provenance,
        'schema_sha256':hashlib.sha256((manifests.DOCS/'release-manifest.schema.json').read_bytes()).hexdigest()}
    result['capsule_sha256'] = manifests.digest(result)
    return result
