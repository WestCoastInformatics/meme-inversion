#!/usr/bin/env python3
"""Read-only NCIt publisher/decision discovery through verified artifact streams.

This is a preparation report, never an execution or acceptance decision. The
coordinator supplies open_role(ref, role); it verifies the selected file/member
and its container. No URI is opened here and no output/source tree is written.
"""
from collections import Counter
import copy
import hashlib
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

import nci_source_plan as plans
from execute_release_nci import _properties

ROLES = ('annotationDeclaration', 'objectDeclaration', 'classDeclaration', 'relations', 'hierarchy')
STATE_ROLES = ('sources-src', 'termgroups-src', 'nci-configuration')
MAX_VOCABULARY = 20000
MAX_LINE_BYTES = 2 * 1024**2
MAX_VOCABULARY_BYTES = 16 * 1024**2


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r'NCI_[0-9]{4}_(0[1-9]|1[0-2])[A-Z]', value):
        raise ValueError('An exact NCIt source version is required')
    return value[4:]


def _lines(handle):
    while True:
        raw=handle.readline(MAX_LINE_BYTES+1)
        if not raw:return
        if len(raw)>MAX_LINE_BYTES:raise ValueError('Record exceeds bounded discovery line size')
        yield raw


def _metadata(handle, fields):
    rows = []
    for raw in _lines(handle):
        if len(raw) > MAX_LINE_BYTES or not raw.endswith(b'\n') or b'\r' in raw or b'\x00' in raw:
            raise ValueError('Metadata requires bounded UTF-8 pipe records with final LF')
        values = raw[:-1].decode('utf-8').split('|')
        if len(values) != len(fields) + 1 or values[-1] != '':
            raise ValueError('Metadata field count/trailing delimiter differs')
        rows.append(dict(zip(fields, values[:-1])))
        if len(rows) > MAX_VOCABULARY:
            raise ValueError('Metadata exceeds the bounded representation vocabulary')
    if not rows or len({x[fields[0]] for x in rows}) != len(rows):
        raise ValueError('Empty or duplicate metadata identities')
    return rows


def analyze(configuration, artifacts, open_role):
    """Collect full observed counts and unresolved decisions without guessing."""
    issues, decisions, required = [], [], []
    facts = {'source': 'NCI', 'execution_authorized': False, 'production_eligible': False,
             'publisher_scan_complete': False, 'calendar_predecessor_inferred': False,
             'scope': 'Physically verified declared inputs and representation discovery; no database/export coherence assertion'}

    def issue(code, message, path, severity='error'):
        item = {'code': code, 'severity': severity, 'message': str(message), 'path': path}
        if item not in issues:issues.append(item)

    def decision(kind, key, message, occurrences=None):
        value = {'kind': kind, 'key': key, 'status': 'requires-review', 'reason': message}
        if occurrences is not None:value['occurrences'] = occurrences
        if value not in decisions:decisions.append(value)
        issue('NCI_' + kind.upper().replace('-', '_'), message, 'discovery/' + kind + '/' + key, 'decision')

    def need(ref, role, reason, path):
        value = {'artifact': ref, 'role': role, 'reason': reason, 'path': path}
        if value not in required:required.append(value)

    def artifact(ref, kind, version, path):
        value = artifacts.get(ref) if isinstance(artifacts, dict) and isinstance(ref, str) else None
        if (not isinstance(value, dict) or value.get('artifact_type') != kind or
                value.get('source') != 'NCI' or value.get('version') != version or not isinstance(value.get('data'), dict)):
            need(ref, None, 'Typed predecessor/current-release bound ' + kind + ' data', path)
            issue('NCI_ARTIFACT_REQUIRED', 'Missing or mismatched ' + kind + ' artifact: ' + str(ref), path)
            return None
        return value

    def role(ref, value, name, reason):
        path = 'artifacts/' + str(ref) + '/files/' + name
        need(ref, name, reason, path)
        files = value.get('files') if value else None
        matches = [x for x in files if isinstance(x, dict) and x.get('role') == name] if isinstance(files, list) else []
        if len(matches) != 1:
            issue('NCI_INPUT_ROLE_REQUIRED', 'Exactly one declared file for role ' + name + ' is required', path)
            return None
        return matches[0]

    def checked(code, path, operation):
        try:return operation()
        except (ValueError, KeyError, TypeError, IndexError, UnicodeError, OSError) as error:
            issue(code, error, path)
            return None

    def transition():
        if not isinstance(configuration, dict) or configuration.get('source') != 'NCI':
            raise ValueError('Canonical source NCI is required')
        current = _version(configuration.get('version'));prior = configuration.get('replacement_baseline')
        if (not isinstance(prior, dict) or set(prior) != {'source', 'version'} or prior['source'] != 'NCI'
                or _version(prior['version']) >= current):
            raise ValueError('An explicit earlier NCIt replacement baseline is required; skipped months are supported')
        inputs = configuration.get('inputs')
        if not isinstance(inputs, dict) or inputs.get('source_data_stage') != 'publisher':
            raise ValueError('Discovery supports the existing five-role NCIt publisher bundle')
        return current, prior, inputs

    selected = checked('NCI_TRANSITION_INVALID', 'configuration', transition)
    if selected is None:return {'issues': issues, 'decisions': decisions, 'facts': facts, 'required_inputs': required}
    current, prior, inputs = selected;version = configuration['version']
    facts.update(version=version, replacement_baseline=copy.deepcopy(prior),
                 predecessor_selection='Explicit inserted predecessor; calendar adjacency is not required')
    variables = {'release': current, 'replacement_release': _version(prior['version'])}

    source_refs = inputs.get('source_data')
    publisher_ref = source_refs[0] if isinstance(source_refs, list) and len(source_refs) == 1 else None
    if publisher_ref is None:issue('NCI_PUBLISHER_BUNDLE_REQUIRED', 'One explicit publisher bundle is required', 'configuration/inputs/source_data')
    publisher = artifact(publisher_ref, 'publisher-bundle', version, 'configuration/inputs/source_data')
    policy_ref = configuration.get('policy_ref');policy = artifact(policy_ref, 'policy', version, 'configuration/policy_ref')
    plan_ref = inputs.get('source_plan');plan_artifact = artifact(plan_ref, 'source-plan', version, 'configuration/inputs/source_plan')
    state_ref = inputs.get('reference_ncimeta');state = artifact(state_ref, 'ncimeta-state', version, 'configuration/inputs/reference_ncimeta')
    root_ref = inputs.get('identity_state');root = artifact(root_ref, 'identity-state', prior['version'], 'configuration/inputs/identity_state')
    plan = plan_artifact['data'] if plan_artifact else None
    model = policy['data'].get('metadata_model') if policy else None
    props = policy['data'].get('properties') if policy else None
    if props is None and state:props = state['data'].get('properties')
    catalog, source_names, group_names = set(), set(), set()
    generated = None

    def representation():
        if (not policy or policy['data'].get('profile') != plans.PROFILE or not isinstance(model, dict)
                or model.get('schema_version') != 1 or model.get('source') != 'NCI'):
            raise ValueError('A reviewed nci-source-plan-v1 metadata model is required')
        if not isinstance(props, dict) or not props or any(not isinstance(k, str) or not isinstance(v, str) for k,v in props.items()):
            raise ValueError('Literal representation properties are required')
        result = {k: plans.render(v, variables) for k,v in props.items()}
        if result.get('VSAB') != version or result.get('RSAB') != 'NCI':
            raise ValueError('Representation policy source/version differs from the request')
        for key in ('publisher_termgroups', 'publisher_properties', 'relationship_roles'):
            if not isinstance(model.get(key), list):raise ValueError('Complete reviewed publisher vocabulary is required: ' + key)
        if not isinstance(model.get('publisher_labels'), dict):raise ValueError('Reviewed publisher labels are required')
        pairs = model['publisher_termgroups']
        if any(not isinstance(x, list) or len(x) != 2 or any(not isinstance(v, str) or not v for v in x) for x in pairs):
            raise ValueError('Publisher termgroups must be explicit source/TTY pairs')
        if len({tuple(x) for x in pairs}) != len(pairs):raise ValueError('Duplicate publisher source/TTY bindings')
        if not plan:raise ValueError('Explicit source plan required, including empty addition arrays')
        plans.keys(plan, ('schema_version','source','version','replacement_baseline','comparison_baseline',
                          'publisher_history','new_subsources','new_termgroups','property_updates','historical_exceptions'), 'source plan')
        if type(plan['schema_version']) is not int or plan['schema_version']!=1:raise ValueError('Unsupported source-plan schema')
        for key in ('source', 'version', 'replacement_baseline', 'comparison_baseline', 'publisher_history'):
            if plan.get(key) != configuration.get(key):raise ValueError('Source plan differs from common configuration: ' + key)
        for key in ('new_subsources', 'new_termgroups', 'historical_exceptions'):
            if not isinstance(plan.get(key), list):raise ValueError('Explicit source-plan array required: ' + key)
        if not isinstance(plan.get('property_updates'), dict):raise ValueError('Typed property_updates object required')
        for value in plan['historical_exceptions']:
            plans.keys(value,('kind','identifier','reason','version','native_sha256'),'historical exception')
            if (value['kind'] not in ('unmapped-publisher-source','unverified-termgroup-ranking') or value['version']!=version
                    or not plans.text(value['reason']).strip() or not plans.text(value['identifier']).strip() or not isinstance(value['native_sha256'],dict)):
                raise ValueError('Historical exception is not bound to an explicit captured release')
        bounds = configuration.get('source_atom_ids')
        if isinstance(bounds, dict) and all(type(bounds.get(k)) is int and bounds[k] > 0 for k in ('start', 'end')):
            rendered = plans.generate(configuration, plan, model, result)
            return rendered, True
        # Discovery precedes allocation. Validate metadata/plan structure using
        # their exact helpers without inventing an atom range or generating files.
        sources = [plans.row(x, plans.SOURCE_FIELDS, variables) for x in model['sources']]
        groups = [plans.row(x, plans.TERMGROUP_FIELDS, variables) for x in model['termgroups']]
        previous_sources={x['stripped_source']+'_'+variables['replacement_release'] for x in sources}
        previous_groups={x['termgroup_name'].replace('_'+current+'/', '_'+variables['replacement_release']+'/') for x in groups}
        previous_groups.update(x['identifier'] for x in plan['historical_exceptions'] if x['kind']=='unverified-termgroup-ranking')
        for binding, value in sorted(model.get('property_bindings', {}).items()):
            binding = plans.render(binding, variables);value = plans.render(value, variables)
            if not (binding.startswith(('vsab.','rsab.','in2tty.','in2Otty.','inl2tty.')) or binding.endswith('.RSSN')):
                raise ValueError('Unreviewed persistent metadata-policy property')
            if binding in result and result[binding] != value:raise ValueError('Persistent binding conflicts with policy')
            result[binding] = value
        declared = {tuple(x) for x in pairs}
        new_sources, new_groups = set(), set()
        for addition in plan['new_subsources']:
            plans.keys(addition, ('metadata','after_source','publisher_names','root'), 'new subsource')
            entry = plans.row(addition['metadata'], plans.SOURCE_FIELDS, variables)
            source = plans.identifier(entry['stripped_source'])
            if source in new_sources:raise ValueError('Duplicate new-subsource decision')
            new_sources.add(source);sources = [x for x in sources if x['stripped_source'] != source]
            plans.insert(sources, entry, plans.identifier(addition['after_source']), 'stripped_source')
            plans.keys(addition['root'], ('preferred_term','short_name'), 'root')
            if any(not plans.text(addition['root'][k]).strip() for k in ('preferred_term','short_name')):raise ValueError('Complete reviewed root names required')
            aliases = addition['publisher_names']
            if not isinstance(aliases,list) or not aliases or len(set(aliases)) != len(aliases):raise ValueError('Unique publisher aliases required')
            for alias in aliases:
                if not plans.text(alias).strip() or any(c in alias for c in "='\""):raise ValueError('Invalid publisher alias')
                for key,value in (('vsab.'+alias,entry['source_name']),('rsab.'+alias,source)):
                    if key in result and result[key] != value:raise ValueError('Addition conflicts with existing representation')
                    result[key] = value
        for key,value in plan['property_updates'].items():
            if not re.fullmatch(r'(in2tty|in2Otty|inl2tty)\.[A-Za-z0-9_-]+',key):raise ValueError('Unreviewed property update')
            if key in result and result[key] != value:raise ValueError('Term-type mapping conflicts with policy')
            if key not in result and key.split('.',1)[1] in {x[1] for x in pairs}:raise ValueError('Existing native term type cannot be reinterpreted')
            result[key] = plans.identifier(value)
        for addition in plan['new_termgroups']:
            plans.keys(addition, ('metadata','after_termgroup','input_ttys'), 'new termgroup')
            entry = plans.row(addition['metadata'], plans.TERMGROUP_FIELDS, variables)
            if entry['termgroup_name'] in new_groups:raise ValueError('Duplicate new-termgroup decision')
            new_groups.add(entry['termgroup_name']);groups = [x for x in groups if x['termgroup_name'] != entry['termgroup_name']]
            plans.insert(groups,entry,plans.render(addition['after_termgroup'],variables),'termgroup_name')
            vsab,tty = entry['termgroup_name'].rsplit('/',1)
            aliases = ['NCI'] if vsab == version else [k[5:] for k,v in result.items() if k.startswith('vsab.') and v == vsab]
            incoming = addition['input_ttys']
            if not aliases or not isinstance(incoming,list) or not incoming or len(set(incoming)) != len(incoming):raise ValueError('Explicit publisher/term-type bindings required')
            for item in incoming:
                plans.identifier(item)
                outputs = {item} if item in ('PT','SY') else {result[k+'.'+item] for k in ('in2tty','in2Otty','inl2tty') if k+'.'+item in result}
                if outputs != {tty}:raise ValueError('New native type requires an unambiguous reviewed output mapping')
                declared.update((alias,item) for alias in aliases)
        source_ids = {x['source_name'] for x in sources}
        for entry in sources:
            if entry['source_name'] != entry['normalized_source'] or entry['source_name'] != entry['stripped_source']+'_'+current or entry['version'] != current or entry['source_family'] != 'NCI' or entry['restriction_level'] not in ('0','1','2','3') or not entry['official_name'].strip():raise ValueError('Inconsistent source metadata')
        for entry in groups:
            vsab,tty = entry['termgroup_name'].rsplit('/',1)
            if vsab not in source_ids or tty != entry['tty'] or any(entry[k] not in ('Y','N') for k in plans.TERMGROUP_FIELDS[2:5]):raise ValueError('Inconsistent termgroup metadata/flags')
        if any(not any(name.startswith(x+'_'+current+'/') for name in new_groups) for x in new_sources):raise ValueError('New subsource needs explicit termgroup metadata')
        previous_sources-={x+'_'+variables['replacement_release'] for x in new_sources}
        previous_groups-={x.replace('_'+current+'/', '_'+variables['replacement_release']+'/') for x in new_groups}
        previous_groups={name for name in previous_groups if not any(name.startswith(x+'_'+variables['replacement_release']+'/') for x in new_sources)}
        plans.ranking(sources,'source_name','low_source',previous_sources)
        plans.ranking(groups,'termgroup_name','low_termgroup',previous_groups)
        primary=[x for x in sources if x['source_name']==version]
        if len(primary)!=1 or primary[0]['low_source']!=prior['version']:raise ValueError('Source metadata predecessor differs from request')
        return {'properties': result, 'source_names': sorted(source_ids), 'publisher_termgroups': sorted(declared),
                'new_subsources': sorted(new_sources), 'new_termgroups': len(new_groups)}, False

    built = checked('NCI_REPRESENTATION_PLAN_INVALID', 'configuration/inputs/source_plan', representation)
    if built:
        generated, final_validated = built;props = generated['properties'];catalog = {tuple(x) for x in generated['publisher_termgroups']};source_names = set(generated['source_names'])
        facts.update(explicit_new_subsources=generated['new_subsources'],explicit_new_termgroups=generated['new_termgroups'],
                     final_metadata_plan_validation=final_validated)
        if not final_validated:issue('NCI_ALLOCATION_PENDING', 'Representation discovery precedes allocation; final generation still requires reviewed ID bounds', 'configuration/source_atom_ids', 'warning')

    # Read state independently of publisher scanning so missing state does not
    # conceal new publisher values or stop a useful partial preparation report.
    state_rows = {}
    if state:
        data = state['data']
        if data.get('profile') != 'nci-preserved-preparation-v1':
            issue('NCI_FRESH_STATE_UNVERIFIED', 'A fresh NCImeta capture needs deployed exporter/project/completeness/coherence verification; this scanner cannot establish it', 'configuration/inputs/reference_ncimeta', 'decision')
        elif data.get('replacement_baseline') != prior:
            issue('NCI_STATE_BASELINE_MISMATCH', 'Preserved metadata is bound to a different inserted predecessor', 'configuration/inputs/reference_ncimeta')
        else:
            for name in STATE_ROLES:
                if not role(state_ref,state,name,'Preserved conversion metadata; not a fresh installed-state proof'):continue
                def read_state(name=name):
                    with open_role(state_ref,name) as handle:
                        if name == 'nci-configuration':
                            raw = handle.read(16*1024**2+1)
                            if len(raw)>16*1024**2:raise ValueError('Configuration exceeds bounded text scope')
                            return _properties(raw)
                        return _metadata(handle,plans.SOURCE_FIELDS if name=='sources-src' else plans.TERMGROUP_FIELDS)
                value = checked('NCI_STATE_INPUT_INVALID','artifacts/'+state_ref+'/files/'+name,read_state)
                if value is not None:state_rows[name] = value
            if 'nci-configuration' in state_rows and state_rows['nci-configuration'] != data.get('properties'):
                issue('NCI_STATE_PROPERTIES_MISMATCH','Physical configuration differs from its declared effective properties','configuration/inputs/reference_ncimeta')
            if 'sources-src' in state_rows:
                primary = [x for x in state_rows['sources-src'] if x['source_name']==version]
                if len(primary)!=1 or primary[0]['low_source']!=prior['version']:
                    issue('NCI_STATE_PREDECESSOR_MISMATCH','Physical source metadata does not identify the explicit inserted predecessor','configuration/replacement_baseline')
                source_names = {x['source_name'] for x in state_rows['sources-src']}
            if 'termgroups-src' in state_rows:group_names = {x['termgroup_name'] for x in state_rows['termgroups-src']}
            facts['preserved_metadata_roles_verified'] = sorted(state_rows)
            facts['fresh_installed_state_authenticated'] = False
            issue('NCI_PRESERVED_STATE_SCOPE','Preserved metadata/root inputs support their captured scope; catalog ranks do not prove a coherent fresh installed-state export','configuration/inputs/reference_ncimeta','warning')
    if not configuration.get('replay'):
        facts['installed_subsource_roots_and_ranks_authenticated']=False
        decision('installed-state-review',prior['version'],'An upcoming-release plan needs verified installed subsource/root/rank evidence; representation-catalog membership does not prove prior insertion')
    if root:
        value=root['data']
        if (value.get('profile')!='saved-hierarchy-root-v1' or value.get('replacement_baseline')!=prior
                or type(value.get('root_atom_id')) is not int or value['root_atom_id']<=0
                or any(not isinstance(value.get(k),str) or not value[k] for k in ('root_code','root_name'))):
            issue('NCI_ROOT_STATE_INVALID','Saved hierarchy root needs a positive source alternate ID and the explicit inserted predecessor','configuration/inputs/identity_state')
        else:
            facts['saved_root_bound_to_predecessor']=True
            physical=state_rows.get('nci-configuration',{})
            expected={'HC.RootNodeSaid':str(value['root_atom_id']),'HC.RootNodeCode':value['root_code'],'HC.RootNodeName':value['root_name']}
            if physical and any(physical.get(k)!=v for k,v in expected.items()):
                issue('NCI_ROOT_CONFIGURATION_MISMATCH','Saved root and physical configuration disagree','configuration/inputs/identity_state')

    observed,used,relationship_roles,maps,qualifiers=Counter(),Counter(),Counter(),Counter(),Counter()
    labels={};native={};successful=[];vocabulary_bytes=[0]
    def vocabulary(value):
        vocabulary_bytes[0]+=sum(len(x.encode()) for x in value) if isinstance(value,tuple) else len(value.encode())
        if vocabulary_bytes[0]>MAX_VOCABULARY_BYTES:raise ValueError('Observed vocabulary exceeds bounded discovery text size')
    def count(counter,key):
        if key not in counter:vocabulary(key)
        counter[key]+=1
        if len(counter)>MAX_VOCABULARY:raise ValueError('Observed vocabulary exceeds bounded discovery scope')
    for name in ROLES:
        descriptor=role(publisher_ref,publisher,name,'Complete current publisher export')
        if descriptor is None:continue
        def scan(name=name,descriptor=descriptor):
            digest=hashlib.sha256();size=rows=0
            with open_role(publisher_ref,name) as handle:
                for raw in _lines(handle):
                    rows+=1;size+=len(raw);digest.update(raw)
                    if len(raw)>MAX_LINE_BYTES or not raw.endswith(b'\n') or b'\x00' in raw:raise ValueError('Malformed or oversized publisher record at row '+str(rows))
                    body=raw[:-1]
                    if body.endswith(b'\r'):body=body[:-1]
                    if b'\r' in body:raise ValueError('Embedded publisher carriage return is uncharacterized')
                    line=body.decode('utf-8')
                    for old,new in plans.NORMALIZATIONS:line=re.sub(old,new,line,count=1)
                    f=line.split('|');minimum={'annotationDeclaration':1,'objectDeclaration':1,'classDeclaration':3,'relations':4,'hierarchy':2}[name]
                    if len(f)<minimum or not f[0] or (name=='hierarchy' and not f[1]):raise ValueError('Malformed publisher role at row '+str(rows))
                    if name=='classDeclaration':
                        count(used,f[1])
                        for index in range(3,len(f)-1,2):
                            if f[index]:count(qualifiers,f[index])
                        if f[1]=='P90':
                            if len(f)<7 or f[3]!='P383' or f[5]!='P384' or not f[4] or not f[6]:raise ValueError('Unreviewed P90 source/TTY qualifier layout at row '+str(rows))
                            count(observed,(f[6],f[4]))
                        elif f[1]=='P108':count(observed,('NCI','PT'))
                        elif f[1]=='P375':count(maps,f[4] if len(f)>4 else '')
                    elif name in ('annotationDeclaration','objectDeclaration') and len(f)>1 and 'label' in f[1]:
                        if len(f)<3:raise ValueError('Missing publisher declaration label')
                        if f[0] in labels and labels[f[0]]!=f[2]:raise ValueError('Conflicting publisher label: '+f[0])
                        if f[0] not in labels:vocabulary(f[0]);vocabulary(f[2])
                        labels[f[0]]=f[2]
                        if len(labels)>MAX_VOCABULARY:raise ValueError('Publisher label vocabulary exceeds bounded scope')
                    elif name=='relations':count(relationship_roles,f[2])
            if not rows:raise ValueError('Empty publisher role')
            if descriptor.get('sha256')!=digest.hexdigest() or descriptor.get('bytes')!=size:raise ValueError('Observed publisher bytes differ from descriptor')
            return {'sha256':digest.hexdigest(),'bytes':size,'rows':rows}
        value=checked('NCI_PUBLISHER_INPUT_INVALID','artifacts/'+str(publisher_ref)+'/files/'+name,scan)
        if value is not None:native[name]=value;successful.append(name)
    facts.update(publisher_scan_complete=set(successful)==set(ROLES),publisher_inputs=native,
                 observed_publisher_termgroups=[{'publisher_source':a,'input_tty':t,'occurrences':n} for (a,t),n in sorted(observed.items())],
                 publisher_properties_observed=len(used),qualifier_properties_observed=len(qualifiers),relationship_roles_observed=len(relationship_roles))
    if not generated:
        issue('NCI_REPRESENTATION_COMPARISON_PENDING','Observed values cannot be declared reviewed without a valid catalog and source plan','configuration/policy_ref','decision')
    else:
        tokens={}
        for pair in sorted(catalog|set(observed)):
            token=''.join(pair)
            if token in tokens and tokens[token]!=pair:decision('ambiguous-native-token',token,'Different publisher source/TTY pairs share one native TREF token')
            tokens[token]=pair
        for (alias,tty),number in sorted(observed.items()):
            key=alias+'/'+tty
            if (alias,tty) not in catalog:decision('publisher-termgroup',key,'Publisher source/TTY needs an explicit reviewed catalog/addition binding',number)
            mapped=props.get('VSAB') if alias==props.get('RSAB') else props.get('vsab.'+alias)
            if mapped not in source_names:
                decision('subsource',alias,'Publisher source lacks a reviewed mapping and source metadata',sum(n for (a,_),n in observed.items() if a==alias))
                continue
            targets={tty} if tty in ('PT','SY') else {props[prefix+'.'+tty] for prefix in ('in2tty','in2Otty') if prefix+'.'+tty in props}
            if alias=='NCI' and 'inl2tty.'+tty in props:targets.add(props['inl2tty.'+tty])
            if not targets:decision('term-type-mapping',key,'Native term type has no characterized output mapping',number)
            for output in sorted(targets):
                termgroup=mapped+'/'+output
                if termgroup not in group_names:decision('termgroup-metadata',termgroup,'Mapped output termgroup lacks verified metadata',number)
        known=set(model['publisher_properties']);known_roles=set(model['relationship_roles']);known_labels=model['publisher_labels']
        for key in sorted(set(used)-known):decision('publisher-property',key,'Publisher property is absent from the reviewed vocabulary',used[key])
        for key in sorted(set(relationship_roles)-known_roles):decision('relationship-role',key,'Relationship role is absent from the reviewed vocabulary',relationship_roles[key])
        for key in sorted(set(used)|set(relationship_roles)|set(qualifiers)):
            if key in known_labels and labels.get(key)!=known_labels[key]:decision('publisher-label',key,'Publisher representation label is missing or changed')
            elif key in qualifiers and key not in known_labels:decision('qualifier-property',key,'Publisher qualifier has no reviewed label/representation')
        for value,number in sorted(maps.items()):
            if value not in ('Has Synonym','Broader Than','Narrower Than','Related To'):decision('maps-to-relationship',value,'Maps_To relationship value requires an explicit representation decision',number)
    exceptions=plan.get('historical_exceptions') if plan else None
    if isinstance(exceptions,list) and exceptions and all(isinstance(x,dict) for x in exceptions):
        files=publisher.get('files') if publisher else []
        files=files if isinstance(files,list) else []
        identities={PurePosixPath(descriptor.get('archive_member',urlsplit(descriptor.get('uri','')).path)).name:native[name]['sha256'] for name in native for descriptor in files if isinstance(descriptor,dict) and descriptor.get('role')==name}
        complete=len(identities)==len(native)==len(ROLES)
        facts['retained_historical_exceptions']=[{'kind':x.get('kind'),'identifier':x.get('identifier'),'exact_native_hashes_match':complete and x.get('native_sha256')==identities} for x in exceptions]
        issue('NCI_HISTORICAL_FINDINGS_NOT_OPERATIONAL_APPROVAL','Recorded historical findings remain review inputs; they do not approve missing mappings for an upcoming release','configuration/inputs/source_plan','warning')
    return {'issues':issues,'decisions':decisions,'facts':facts,'required_inputs':required}
